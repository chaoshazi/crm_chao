'''写入路径回归：写幂等、版本冲突、软删除、归属继承与字段校验。

AI 能力层会对 408/425/429/5xx 重试，因此写接口必须可幂等。
'''

from __future__ import annotations

import unittest

from tests import support


class IdempotencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def _create(self, key: str | None, body: dict | None = None):
        headers = dict(self.headers)
        if key:
            headers['Idempotency-Key'] = key
        return self.client.post(
            '/api/v1/tasks',
            json=body or {'subject': '幂等任务', 'target_id': 'lead-0001'},
            headers=headers,
        )

    def test_replay_returns_the_first_response_and_does_not_write_again(self) -> None:
        first = self._create('key-replay-1')
        second = self._create('key-replay-1')
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json(), second.json())
        listed = self.client.get(
            '/api/v1/tasks', params={'q': '幂等任务'}, headers=self.headers
        ).json()
        self.assertEqual(listed['total'], 1)

    def test_same_key_with_a_different_body_is_409(self) -> None:
        self._create('key-conflict-1')
        response = self._create('key-conflict-1', {'subject': '换了内容'})
        self.assertEqual(response.status_code, 409, response.text)

    def test_without_a_key_every_call_writes(self) -> None:
        self._create(None)
        self._create(None)
        listed = self.client.get(
            '/api/v1/tasks', params={'q': '幂等任务'}, headers=self.headers
        ).json()
        self.assertEqual(listed['total'], 2)

    def test_keys_are_scoped_per_actor(self) -> None:
        self._create('key-shared-1')
        admin = support.login_headers(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)
        response = self.client.post(
            '/api/v1/tasks',
            json={'subject': '他人同键任务'},
            headers=dict(admin, **{'Idempotency-Key': 'key-shared-1'}),
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_delete_replay_returns_the_same_body(self) -> None:
        record_id = self._create('key-del-create').json()['data']['id']
        headers = dict(self.headers, **{'Idempotency-Key': 'key-del-1'})
        first = self.client.delete('/api/v1/tasks/' + record_id, headers=headers)
        second = self.client.delete('/api/v1/tasks/' + record_id, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json(), second.json())

    def test_replay_does_not_write_a_second_audit_row(self) -> None:
        self._create('key-audit-1')
        self._create('key-audit-1')
        audit = self.client.get(
            '/api/v1/audit', params={'object_type': 'tasks'}, headers=self.headers
        ).json()['data']
        created = [row for row in audit if row.get('method') == 'POST']
        self.assertEqual(len(created), 1, audit)
        self.assertEqual(created[0].get('idempotency_key'), 'key-audit-1')


class VersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_patch_without_version_succeeds_and_bumps(self) -> None:
        before = self.client.get('/api/v1/leads/lead-0001', headers=self.headers).json()['data']
        after = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.headers
        ).json()['data']
        self.assertEqual(int(after['version']), int(before['version']) + 1)
        self.assertEqual(after['stage'], 'qualified')

    def test_patch_with_current_version_succeeds(self) -> None:
        current = self.client.get('/api/v1/leads/lead-0001', headers=self.headers).json()['data']
        response = self.client.patch(
            '/api/v1/leads/lead-0001',
            json={'version': current['version'], 'source': '官网表单'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_stale_version_is_409(self) -> None:
        current = self.client.get('/api/v1/leads/lead-0001', headers=self.headers).json()['data']
        response = self.client.patch(
            '/api/v1/leads/lead-0001',
            json={'version': int(current['version']) + 5, 'stage': 'qualified'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409, response.text)

    def test_updated_at_advances_on_write(self) -> None:
        before = self.client.get('/api/v1/leads/lead-0001', headers=self.headers).json()['data']
        after = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.headers
        ).json()['data']
        self.assertGreater(after['updated_at'], before['updated_at'])


class SoftDeleteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_deleted_record_disappears_from_reads_and_lists(self) -> None:
        response = self.client.delete('/api/v1/leads/lead-0002', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['id'], 'lead-0002')
        self.assertEqual(
            self.client.get('/api/v1/leads/lead-0002', headers=self.headers).status_code, 404
        )
        listed = self.client.get('/api/v1/leads', headers=self.headers).json()
        self.assertNotIn('lead-0002', [row['id'] for row in listed['data']])
        self.assertEqual(listed['total'], 1)

    def test_deleted_record_is_still_reachable_with_include_deleted(self) -> None:
        self.client.delete('/api/v1/leads/lead-0002', headers=self.headers)
        response = self.client.get(
            '/api/v1/leads/lead-0002',
            params={'include_deleted': 'true'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['id'], 'lead-0002')

    def test_deleting_twice_is_404(self) -> None:
        self.client.delete('/api/v1/leads/lead-0002', headers=self.headers)
        response = self.client.delete('/api/v1/leads/lead-0002', headers=self.headers)
        self.assertEqual(response.status_code, 404, response.text)


class PayloadHandlingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_unknown_fields_are_preserved_on_create(self) -> None:
        record = self.client.post(
            '/api/v1/leads',
            json={'company': '未知字段测试', 'custom_score': 87, 'custom_tag': 'vip'},
            headers=self.headers,
        ).json()['data']
        self.assertEqual(record['custom_score'], 87)
        self.assertEqual(record['custom_tag'], 'vip')

    def test_unknown_fields_are_preserved_on_update_and_reread(self) -> None:
        created = self.client.post(
            '/api/v1/leads', json={'company': '未知字段更新'}, headers=self.headers
        ).json()['data']
        self.client.patch(
            '/api/v1/leads/' + created['id'],
            json={'custom_note': '保留我'},
            headers=self.headers,
        )
        fetched = self.client.get(
            '/api/v1/leads/' + created['id'], headers=self.headers
        ).json()['data']
        self.assertEqual(fetched['custom_note'], '保留我')

    def test_unknown_fields_survive_an_unrelated_patch(self) -> None:
        created = self.client.post(
            '/api/v1/leads',
            json={'company': '未知字段共存', 'custom_owner_note': '原始值'},
            headers=self.headers,
        ).json()['data']
        self.client.patch(
            '/api/v1/leads/' + created['id'], json={'stage': 'contacted'}, headers=self.headers
        )
        fetched = self.client.get(
            '/api/v1/leads/' + created['id'], headers=self.headers
        ).json()['data']
        self.assertEqual(fetched['custom_owner_note'], '原始值')

    def test_missing_required_field_is_400(self) -> None:
        response = self.client.post('/api/v1/leads', json={'contact': '没公司'}, headers=self.headers)
        self.assertEqual(response.status_code, 400, response.text)

    def test_invalid_enum_is_400(self) -> None:
        response = self.client.post(
            '/api/v1/leads',
            json={'company': '枚举测试', 'stage': 'not-a-stage'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_invalid_enum_on_update_is_400(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'not-a-stage'}, headers=self.headers
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_invalid_amount_is_400_not_500(self) -> None:
        response = self.client.post(
            '/api/v1/opportunities',
            json={'name': '金额非法', 'amount': 'abc'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_invalid_email_is_400(self) -> None:
        response = self.client.post(
            '/api/v1/leads',
            json={'company': '邮箱非法', 'email': 'not-an-email'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_valid_email_is_accepted(self) -> None:
        response = self.client.post(
            '/api/v1/leads',
            json={'company': '邮箱合法', 'email': 'zhang.wei+crm@yuanshan.example'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['data']['email'], 'zhang.wei+crm@yuanshan.example')

    def test_invalid_email_on_update_is_400(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'email': 'nope'}, headers=self.headers
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_team_ids_read_shape_is_accepted_on_write(self) -> None:
        record = self.client.post(
            '/api/v1/leads',
            json={'company': '团队别名测试', 'team_ids': ['t-finance']},
            headers=self.headers,
        ).json()['data']
        self.assertEqual(record['team_ids'], ['t-finance'])
        expected = {
            'id',
            'version',
            'created_at',
            'updated_at',
            'owner_id',
            'company',
            'contact',
            'email',
            'phone',
            'source',
            'stage',
            'team_ids',
        }
        self.assertEqual(set(record), expected)

    def test_team_ids_alias_can_move_a_record_between_teams(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'team_ids': ['t-finance']}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['team_ids'], ['t-finance'])

    def test_empty_team_ids_clears_the_team(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'team_ids': []}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['team_ids'], [])

    def test_empty_body_is_400_not_500(self) -> None:
        response = self.client.post('/api/v1/leads', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 400, response.text)

    def test_target_id_inherits_ownership_and_team(self) -> None:
        record = self.client.post(
            '/api/v1/notes',
            json={'target_id': 'lead-0001', 'content': '归属继承'},
            headers=self.headers,
        ).json()['data']
        self.assertEqual(record['owner_id'], 'u-100')
        self.assertEqual(record['team_ids'], ['t-sales'])

    def test_actor_headers_attribute_writes_to_a_human(self) -> None:
        headers = support.service_headers(**{'X-Actor-Id': 'u-200',
                                             'X-Actor-Team-Ids': 't-finance'})
        record = self.client.post(
            '/api/v1/contacts', json={'name': '代填联系人'}, headers=headers
        ).json()['data']
        self.assertEqual(record['owner_id'], 'u-200')
        self.assertEqual(record['team_ids'], ['t-finance'])
        audit = self.client.get('/api/v1/audit', headers=self.headers).json()['data']
        latest = audit[0]
        self.assertEqual(latest['actor_id'], 'ai-agent')
        self.assertEqual(latest.get('on_behalf_of'), 'u-200')

    def test_service_writes_default_to_the_ai_agent_owner(self) -> None:
        record = self.client.post(
            '/api/v1/contacts', json={'name': 'AI 直建联系人'}, headers=self.headers
        ).json()['data']
        self.assertEqual(record['owner_id'], 'ai-agent')

    def test_explicit_owner_and_team_are_accepted(self) -> None:
        record = self.client.post(
            '/api/v1/leads',
            json={'company': '转派测试', 'owner_id': 'u-200', 'team_id': 't-finance'},
            headers=self.headers,
        ).json()['data']
        self.assertEqual(record['owner_id'], 'u-200')
        self.assertEqual(record['team_ids'], ['t-finance'])

    def test_reassign_owner_is_supported(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'owner_id': 'u-200'}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['owner_id'], 'u-200')


if __name__ == '__main__':
    unittest.main()

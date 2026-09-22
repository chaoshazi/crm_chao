'''写审计与种子数据回归。

审计是「谁在什么时候把哪条记录从什么改成什么」的唯一凭据，
人工修改与 AI 写回都必须落库，且不能泄露明文密码。
'''

from __future__ import annotations

import unittest

from tests import support

AUDIT_KEYS = {
    'id',
    'at',
    'tenant_id',
    'actor_id',
    'actor_kind',
    'on_behalf_of',
    'source',
    'method',
    'path',
    'object_type',
    'record_id',
    'before',
    'after',
    'idempotency_key',
}


class AuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.service = support.service_headers()
        self.admin = support.login_headers(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def _audit(self, **params) -> list[dict]:
        response = self.client.get('/api/v1/audit', params=params, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['data']

    def test_ai_create_is_recorded_with_source_ai(self) -> None:
        created = self.client.post(
            '/api/v1/tasks',
            json={'subject': '审计用任务', 'target_id': 'lead-0001'},
            headers=dict(self.service, **{'Idempotency-Key': 'audit-key-1'}),
        ).json()['data']
        rows = self._audit(object_type='tasks')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row), AUDIT_KEYS)
        self.assertEqual(row['source'], 'ai')
        self.assertEqual(row['actor_kind'], 'service')
        self.assertEqual(row['actor_id'], 'ai-agent')
        self.assertEqual(row['method'], 'POST')
        self.assertEqual(row['record_id'], created['id'])
        self.assertEqual(row['idempotency_key'], 'audit-key-1')
        self.assertIsNone(row['before'])
        self.assertEqual(row['after']['subject'], '审计用任务')

    def test_human_write_is_recorded_with_source_human(self) -> None:
        created = self.client.post(
            '/api/v1/leads', json={'company': '人工审计'}, headers=self.admin
        ).json()['data']
        row = self._audit(object_type='leads', record_id=created['id'])[0]
        self.assertEqual(row['source'], 'human')
        self.assertEqual(row['actor_kind'], 'user')
        self.assertEqual(row['actor_id'], 'u-admin')

    def test_update_records_before_and_after(self) -> None:
        self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.service
        )
        row = self._audit(object_type='leads', record_id='lead-0001')[0]
        self.assertEqual(row['method'], 'PATCH')
        self.assertEqual(row['before']['stage'], 'new')
        self.assertEqual(row['after']['stage'], 'qualified')

    def test_delete_is_recorded(self) -> None:
        self.client.delete('/api/v1/leads/lead-0002', headers=self.service)
        row = self._audit(object_type='leads', record_id='lead-0002')[0]
        self.assertEqual(row['method'], 'DELETE')
        self.assertIsNotNone(row['before'])
        self.assertIsNotNone(row['after'])

    def test_audit_is_ordered_newest_first(self) -> None:
        self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'contacted'}, headers=self.service
        )
        self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.service
        )
        rows = self._audit(object_type='leads', record_id='lead-0001')
        self.assertEqual(rows[0]['after']['stage'], 'qualified')
        self.assertEqual(rows[1]['after']['stage'], 'contacted')

    def test_audit_limit_is_respected(self) -> None:
        for index in range(3):
            self.client.patch(
                '/api/v1/leads/lead-0001',
                json={'source': '来源 ' + str(index)},
                headers=self.service,
            )
        self.assertEqual(len(self._audit(limit=2)), 2)

    def test_audit_never_contains_password_material(self) -> None:
        created = self.client.post(
            '/api/v1/users',
            json={
                'name': '审计密码检查',
                'email': 'auditpwd@example.com',
                'password': 'supersecret123',
            },
            headers=self.service,
        ).json()['data']
        row = self._audit(object_type='users', record_id=created['id'])[0]
        self.assertNotIn('password', row['after'])
        self.assertNotIn('password_hash', row['after'])
        self.assertNotIn('supersecret123', str(row))

    def test_audit_requires_auth(self) -> None:
        self.assertEqual(self.client.get('/api/v1/audit').status_code, 401)

    def test_audit_is_isolated_between_fresh_databases(self) -> None:
        self.assertEqual(self._audit(), [])


class SeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.service = support.service_headers()
        self.admin = support.login_headers(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def _ids(self, object_type: str) -> list[str]:
        response = self.client.get('/api/v1/' + object_type, headers=self.service)
        self.assertEqual(response.status_code, 200, response.text)
        return sorted(row['id'] for row in response.json()['data'])

    def test_demo_record_ids_match_the_ai_layer_fixtures(self) -> None:
        for object_type, expected in support.SEED_IDS.items():
            with self.subTest(object_type=object_type):
                self.assertEqual(self._ids(object_type), sorted(expected))

    def test_contacts_has_no_demo_rows(self) -> None:
        self.assertEqual(self._ids('contacts'), [])

    def test_demo_teams_exist(self) -> None:
        rows = {row['id']: row for row in self.client.get('/api/v1/teams', headers=self.admin).json()['data']}
        self.assertEqual(rows['t-sales']['name'], '销售一部')
        self.assertEqual(rows['t-finance']['name'], '金融事业部')

    def test_demo_users_have_expected_role_and_team(self) -> None:
        rows = {
            row['id']: row
            for row in self.client.get('/api/v1/users', headers=self.admin).json()['data']
        }
        self.assertEqual(sorted(rows), ['u-100', 'u-200', 'u-admin'])
        self.assertEqual(rows['u-100']['role'], 'manager')
        self.assertEqual(rows['u-100']['email'], 'chenxiao@example.com')
        self.assertEqual(rows['u-100']['team_ids'], ['t-sales'])
        self.assertEqual(rows['u-200']['role'], 'rep')
        self.assertEqual(rows['u-200']['email'], 'zhoumin@example.com')
        self.assertEqual(rows['u-200']['team_ids'], ['t-finance'])
        self.assertEqual(rows['u-admin']['role'], 'admin')

    def test_demo_record_values_are_preserved(self) -> None:
        lead = self.client.get('/api/v1/leads/lead-0001', headers=self.service).json()['data']
        self.assertEqual(lead['company'], '远山科技')
        self.assertEqual(lead['stage'], 'new')
        self.assertEqual(lead['owner_id'], 'u-100')
        self.assertEqual(lead['team_ids'], ['t-sales'])
        self.assertEqual(lead['version'], '1')
        opp = self.client.get('/api/v1/opportunities/opp-0001', headers=self.service).json()['data']
        self.assertEqual(opp['amount'], 268000)
        self.assertEqual(opp['version'], '3')

    def test_stats_counts_match_the_seed(self) -> None:
        counts = self.client.get('/api/v1/stats/overview', headers=self.service).json()['counts']
        self.assertEqual(counts['leads'], 2)
        self.assertEqual(counts['accounts'], 1)
        self.assertEqual(counts['opportunities'], 1)
        self.assertEqual(counts['activities'], 1)
        self.assertEqual(counts['tasks'], 1)
        self.assertEqual(counts['notes'], 1)
        self.assertEqual(counts['contacts'], 0)
        self.assertEqual(counts['users'], 3)

    def test_bootstrap_admin_can_log_in(self) -> None:
        support.login(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)

    def test_seeding_can_be_disabled(self) -> None:
        with support.crm(seed_demo=False) as (client, _settings):
            headers = support.login_headers(
                client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD
            )
            users = client.get('/api/v1/users', headers=headers).json()['data']
            self.assertEqual([row['id'] for row in users], ['u-admin'])
            self.assertEqual(client.get('/api/v1/leads', headers=headers).json()['total'], 0)
            self.assertEqual(client.get('/api/v1/teams', headers=headers).json()['data'], [])

    def test_every_demo_record_carries_a_team(self) -> None:
        for object_type in support.SEED_IDS:
            with self.subTest(object_type=object_type):
                rows = self.client.get('/api/v1/' + object_type, headers=self.service).json()['data']
                for row in rows:
                    self.assertEqual(len(row['team_ids']), 1, row)


if __name__ == '__main__':
    unittest.main()
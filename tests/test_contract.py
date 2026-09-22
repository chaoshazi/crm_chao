'''对接契约回归：接口形状与字段名必须与 AI 能力层逐字一致。

字段名镜像 D:/codex/app/integrations/crm/field_map.py 的 DEFAULT_FIELD_MAP。
改这里之前先确认那边同步改过，否则 AI 侧会把字段塞进 _extra。
'''

from __future__ import annotations

import unittest

from tests import support

# object_type -> 业务字段名（不含公共列）
OBJECT_FIELDS = {
    'leads': ('company', 'contact', 'email', 'phone', 'source', 'stage'),
    'contacts': ('name', 'account_id', 'title', 'email', 'phone'),
    'accounts': ('name', 'industry', 'scale', 'region'),
    'opportunities': (
        'name',
        'account_id',
        'amount',
        'currency',
        'stage',
        'expected_close_date',
    ),
    'activities': ('kind', 'subject', 'content', 'target_id', 'occurred_at'),
    'tasks': ('subject', 'due_at', 'target_id', 'priority'),
    'notes': ('target_id', 'content'),
    'users': ('name', 'email'),
}

# 每条记录都要有的公共列；users 的 team_ids 来自团队字段
COMMON_FIELDS = ('id', 'version', 'updated_at', 'owner_id', 'team_ids')

# 内部列绝不能出现在出参里
INTERNAL_FIELDS = ('tenant_id', 'team_id', 'created_by', 'deleted_at', 'password', 'password_hash')

SAMPLE_PAYLOADS = {
    'leads': {
        'company': '契约测试公司',
        'contact': '张三',
        'email': 'contract@example.com',
        'phone': '13900000000',
        'source': '官网表单',
        'stage': 'new',
    },
    'contacts': {
        'name': '李四',
        'account_id': 'acc-0001',
        'title': '技术总监',
        'email': 'lisi@example.com',
        'phone': '13900000001',
    },
    'accounts': {
        'name': '契约测试客户',
        'industry': '制造业',
        'scale': '500-1000 人',
        'region': '华北',
    },
    'opportunities': {
        'name': '契约测试商机',
        'account_id': 'acc-0001',
        'amount': 123456.78,
        'currency': 'CNY',
        'stage': 'negotiation',
        'expected_close_date': '2026-12-31',
    },
    'activities': {
        'kind': 'call',
        'subject': '契约测试沟通',
        'content': '确认字段映射',
        'target_id': 'lead-0001',
        'occurred_at': '2026-09-01T01:00:00+00:00',
    },
    'tasks': {
        'subject': '契约测试任务',
        'due_at': '2026-09-30T09:00:00+00:00',
        'target_id': 'lead-0001',
        'priority': 'high',
    },
    'notes': {'target_id': 'lead-0001', 'content': '契约测试备注'},
    'users': {
        'name': '契约测试用户',
        'email': 'contract-user@example.com',
        'team_id': 't-sales',
        'role': 'rep',
        'password': 'contract12345',
    },
}


class ContractShapeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_meta_lists_exactly_the_contract_objects(self) -> None:
        response = self.client.get('/api/v1/meta', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        names = {item['name'] for item in response.json()['objects']}
        self.assertEqual(names, set(OBJECT_FIELDS))

    def test_list_envelope_keys(self) -> None:
        payload = self.client.get('/api/v1/leads', headers=self.headers).json()
        self.assertEqual(set(payload), {'data', 'next_cursor', 'total'})
        self.assertIsInstance(payload['data'], list)
        self.assertIsInstance(payload['total'], int)
        self.assertIsNone(payload['next_cursor'])

    def test_single_record_envelope(self) -> None:
        payload = self.client.get('/api/v1/leads/lead-0001', headers=self.headers).json()
        self.assertEqual(set(payload), {'data'})
        self.assertEqual(payload['data']['id'], 'lead-0001')

    def test_created_records_expose_contract_fields(self) -> None:
        for object_type, body in SAMPLE_PAYLOADS.items():
            with self.subTest(object_type=object_type):
                created = self.client.post(
                    '/api/v1/' + object_type, json=body, headers=self.headers
                )
                self.assertEqual(created.status_code, 201, created.text)
                record = created.json()['data']
                for field in COMMON_FIELDS + OBJECT_FIELDS[object_type]:
                    self.assertIn(field, record, object_type + '.' + field)
                for field in INTERNAL_FIELDS:
                    self.assertNotIn(field, record, object_type + '.' + field)

    def test_get_returns_same_field_names_as_create(self) -> None:
        created = self.client.post(
            '/api/v1/accounts', json={'name': '字段集合一致性'}, headers=self.headers
        ).json()['data']
        fetched = self.client.get(
            '/api/v1/accounts/' + created['id'], headers=self.headers
        ).json()['data']
        self.assertEqual(set(fetched), set(created))

    def test_write_only_fields_are_never_serialized(self) -> None:
        created = self.client.post(
            '/api/v1/users',
            json=SAMPLE_PAYLOADS['users'],
            headers=self.headers,
        ).json()['data']
        self.assertNotIn('password', created)
        self.assertNotIn('password_hash', created)
        listed = self.client.get('/api/v1/users', headers=self.headers).json()['data']
        self.assertTrue(listed)
        for row in listed:
            self.assertNotIn('password', row)
            self.assertNotIn('password_hash', row)

    def test_list_rows_expose_contract_fields(self) -> None:
        for object_type, fields in OBJECT_FIELDS.items():
            with self.subTest(object_type=object_type):
                created = self.client.post(
                    '/api/v1/' + object_type,
                    json=SAMPLE_PAYLOADS[object_type],
                    headers=self.headers,
                )
                self.assertEqual(created.status_code, 201, created.text)
                record_id = created.json()['data']['id']
                payload = self.client.get('/api/v1/' + object_type, headers=self.headers).json()
                rows = {row['id']: row for row in payload['data']}
                self.assertIn(record_id, rows)
                row = rows[record_id]
                for field in COMMON_FIELDS + fields:
                    self.assertIn(field, row, object_type + '.' + field)

    def test_team_ids_is_a_list_never_a_scalar(self) -> None:
        for object_type in OBJECT_FIELDS:
            with self.subTest(object_type=object_type):
                payload = self.client.get('/api/v1/' + object_type, headers=self.headers).json()
                for row in payload['data']:
                    self.assertIsInstance(row['team_ids'], list)

    def test_numeric_and_null_types_are_json_native(self) -> None:
        record = self.client.post(
            '/api/v1/opportunities',
            json={'name': '金额类型测试', 'amount': 1000.5},
            headers=self.headers,
        ).json()['data']
        self.assertIsInstance(record['amount'], (int, float))
        self.assertIsNone(record['currency'])
        self.assertIsNone(record['account_id'])
        self.assertIsNone(record['expected_close_date'])

    def test_unknown_object_type_is_404(self) -> None:
        response = self.client.get('/api/v1/not_an_object', headers=self.headers)
        self.assertEqual(response.status_code, 404, response.text)

    def test_unknown_path_under_api_stays_json_404(self) -> None:
        response = self.client.get('/api/v1/leads/lead-0001/does-not-exist', headers=self.headers)
        self.assertEqual(response.status_code, 404, response.text)


class PaginationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()
        for index in range(5):
            response = self.client.post(
                '/api/v1/leads',
                json={'company': '分页测试 ' + str(index)},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 201, response.text)

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_cursor_walk_covers_every_record_once(self) -> None:
        seen: list[str] = []
        cursor = None
        pages = 0
        while True:
            params = {'limit': 2}
            if cursor:
                params['cursor'] = cursor
            payload = self.client.get('/api/v1/leads', params=params, headers=self.headers).json()
            pages += 1
            self.assertLessEqual(len(payload['data']), 2)
            seen.extend(row['id'] for row in payload['data'])
            cursor = payload['next_cursor']
            if not cursor:
                break
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 7)
        self.assertGreater(pages, 1)

    def test_total_is_stable_across_pages(self) -> None:
        first = self.client.get(
            '/api/v1/leads', params={'limit': 1}, headers=self.headers
        ).json()
        second = self.client.get(
            '/api/v1/leads', params={'limit': 1, 'cursor': first['next_cursor']}, headers=self.headers
        ).json()
        self.assertEqual(first['total'], 7)
        self.assertEqual(second['total'], 7)

    def test_updated_since_filters_out_older_records(self) -> None:
        payload = self.client.get(
            '/api/v1/leads',
            params={'updated_since': '2999-01-01T00:00:00+00:00'},
            headers=self.headers,
        ).json()
        self.assertEqual(payload['total'], 0)
        self.assertEqual(payload['data'], [])

    def test_updated_since_epoch_returns_everything(self) -> None:
        payload = self.client.get(
            '/api/v1/leads',
            params={'updated_since': '1970-01-01T00:00:00+00:00'},
            headers=self.headers,
        ).json()
        self.assertEqual(payload['total'], 7)

    def test_bad_updated_since_is_400(self) -> None:
        response = self.client.get(
            '/api/v1/leads', params={'updated_since': 'yesterday'}, headers=self.headers
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_limit_above_max_is_clamped_to_max_page_size(self) -> None:
        response = self.client.get(
            '/api/v1/leads', params={'limit': 9999}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['data']), 7)

    def test_zero_limit_is_400(self) -> None:
        response = self.client.get(
            '/api/v1/leads', params={'limit': 0}, headers=self.headers
        )
        self.assertEqual(response.status_code, 400, response.text)


class StageWriteTest(unittest.TestCase):
    '''AI 侧的推阶段/赢单写回必须可用，closed_won 尤其关键。'''

    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.headers = support.service_headers()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_opportunity_can_be_stamped_closed_won(self) -> None:
        response = self.client.patch(
            '/api/v1/opportunities/opp-0001',
            json={'stage': 'closed_won'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['stage'], 'closed_won')

    def test_lead_can_be_stamped_closed_won(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'closed_won'}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['stage'], 'closed_won')

    def test_stage_survives_a_reread(self) -> None:
        self.client.patch(
            '/api/v1/opportunities/opp-0001',
            json={'stage': 'closed_won'},
            headers=self.headers,
        )
        payload = self.client.get('/api/v1/opportunities/opp-0001', headers=self.headers).json()
        self.assertEqual(payload['data']['stage'], 'closed_won')


if __name__ == '__main__':
    unittest.main()

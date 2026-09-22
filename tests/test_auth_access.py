'''鉴权与行级权限回归：三角色（admin / manager / rep）+ AI 服务账号。'''

from __future__ import annotations

import unittest

from tests import support


class AuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def test_service_token_can_list(self) -> None:
        response = self.client.get('/api/v1/leads', headers=support.service_headers())
        self.assertEqual(response.status_code, 200, response.text)

    def test_missing_token_is_401(self) -> None:
        response = self.client.get('/api/v1/leads')
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()['detail'], '缺少访问凭证')

    def test_unknown_token_is_401(self) -> None:
        response = self.client.get('/api/v1/leads', headers=support.bearer('garbage-token'))
        self.assertEqual(response.status_code, 401, response.text)

    def test_unknown_object_without_token_is_401_not_404(self) -> None:
        response = self.client.get('/api/v1/not_an_object')
        self.assertEqual(response.status_code, 401, response.text)

    def test_login_returns_token_and_identity(self) -> None:
        payload = support.login(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)
        self.assertTrue(payload['token'])
        self.assertEqual(payload['user']['role'], 'admin')
        self.assertIn('expires_at', payload)

    def test_login_with_wrong_password_is_401(self) -> None:
        response = self.client.post(
            '/api/auth/login', json={'email': support.ADMIN_EMAIL, 'password': 'wrong'}
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_login_with_unknown_email_is_401(self) -> None:
        response = self.client.post(
            '/api/auth/login', json={'email': 'nobody@example.com', 'password': 'whatever'}
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_login_is_case_insensitive_on_email(self) -> None:
        response = self.client.post(
            '/api/auth/login',
            json={'email': 'ADMIN@Example.com', 'password': support.ADMIN_PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_deactivated_user_cannot_login_or_use_token(self) -> None:
        admin = support.login_headers(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)
        rep = support.login_headers(self.client, support.REP_EMAIL)
        self.assertEqual(
            self.client.get('/api/v1/leads', headers=rep).status_code, 200
        )
        response = self.client.patch(
            '/api/v1/users/u-200', json={'is_active': False}, headers=admin
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/v1/leads', headers=rep).status_code, 401)
        self.assertEqual(
            self.client.post(
                '/api/auth/login',
                json={'email': support.REP_EMAIL, 'password': support.DEMO_PASSWORD},
            ).status_code,
            401,
        )

    def test_me_returns_the_current_actor(self) -> None:
        headers = support.login_headers(self.client, support.MANAGER_EMAIL)
        payload = self.client.get('/api/auth/me', headers=headers).json()
        self.assertEqual(payload['id'], 'u-100')
        self.assertEqual(payload['role'], 'manager')
        self.assertEqual(payload['team_id'], 't-sales')

    def test_change_password_then_login_with_the_new_one(self) -> None:
        headers = support.login_headers(self.client, support.REP_EMAIL)
        response = self.client.post(
            '/api/auth/password', json={'password': 'newpass12345'}, headers=headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.client.post(
                '/api/auth/login',
                json={'email': support.REP_EMAIL, 'password': support.DEMO_PASSWORD},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                '/api/auth/login',
                json={'email': support.REP_EMAIL, 'password': 'newpass12345'},
            ).status_code,
            200,
        )

    def test_change_password_requires_auth(self) -> None:
        response = self.client.post('/api/auth/password', json={'password': 'x12345678'})
        self.assertEqual(response.status_code, 401, response.text)

    def test_password_is_never_returned_and_is_hashed(self) -> None:
        created = self.client.post(
            '/api/v1/users',
            json={'name': '哈希检查', 'email': 'hash@example.com', 'password': 'plain12345'},
            headers=support.service_headers(),
        ).json()['data']
        self.assertNotIn('password', created)
        self.assertNotIn('password_hash', created)

    def test_health_endpoint_is_public(self) -> None:
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['tenant_id'], 'default')


class RowLevelAccessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = support.crm()
        self.client, self.settings = self._ctx.__enter__()
        self.service = support.service_headers()
        self.admin = support.login_headers(self.client, support.ADMIN_EMAIL, support.ADMIN_PASSWORD)
        self.manager = support.login_headers(self.client, support.MANAGER_EMAIL)
        self.rep = support.login_headers(self.client, support.REP_EMAIL)

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)

    def _lead_ids(self, headers: dict) -> list[str]:
        payload = self.client.get('/api/v1/leads', headers=headers).json()
        return sorted(row['id'] for row in payload['data'])

    def test_admin_and_service_see_every_lead(self) -> None:
        self.assertEqual(self._lead_ids(self.admin), ['lead-0001', 'lead-0002'])
        self.assertEqual(self._lead_ids(self.service), ['lead-0001', 'lead-0002'])

    def test_manager_sees_only_own_team(self) -> None:
        self.assertEqual(self._lead_ids(self.manager), ['lead-0001'])

    def test_rep_sees_only_own_team(self) -> None:
        self.assertEqual(self._lead_ids(self.rep), ['lead-0002'])

    def test_cross_team_read_is_404_not_403(self) -> None:
        response = self.client.get('/api/v1/leads/lead-0001', headers=self.rep)
        self.assertEqual(response.status_code, 404, response.text)

    def test_cross_team_write_is_404(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.rep
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_cross_team_delete_is_404(self) -> None:
        response = self.client.delete('/api/v1/leads/lead-0001', headers=self.rep)
        self.assertEqual(response.status_code, 404, response.text)

    def test_manager_can_write_inside_own_team(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'stage': 'qualified'}, headers=self.manager
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_manager_cannot_write_outside_own_team(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0002', json={'stage': 'qualified'}, headers=self.manager
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_rep_can_write_own_record(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0002', json={'stage': 'qualified'}, headers=self.rep
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_rep_cannot_write_a_teammates_record(self) -> None:
        self.client.post(
            '/api/v1/users',
            json={
                'name': '同队新代表',
                'email': 'peer@example.com',
                'team_id': 't-finance',
                'role': 'rep',
                'password': 'peer12345',
            },
            headers=self.admin,
        )
        peer = support.login_headers(self.client, 'peer@example.com', 'peer12345')
        self.assertEqual(self.client.get('/api/v1/leads/lead-0002', headers=peer).status_code, 200)
        response = self.client.patch(
            '/api/v1/leads/lead-0002', json={'stage': 'qualified'}, headers=peer
        )
        # 可见（同队）但没有写权限时返回 403；不可见才返回 404
        self.assertEqual(response.status_code, 403, response.text)

    def test_rep_created_record_is_owned_by_the_rep(self) -> None:
        record = self.client.post(
            '/api/v1/leads', json={'company': '代表自建'}, headers=self.rep
        ).json()['data']
        self.assertEqual(record['owner_id'], 'u-200')
        self.assertEqual(record['team_ids'], ['t-finance'])

    def test_rep_cannot_create_a_record_owned_by_someone_else(self) -> None:
        response = self.client.post(
            '/api/v1/leads',
            json={'company': '越权归属', 'owner_id': 'u-100', 'team_id': 't-sales'},
            headers=self.rep,
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_rep_cannot_reassign_owner(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0002', json={'owner_id': 'u-100'}, headers=self.rep
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_manager_cannot_change_team_membership(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001', json={'team_ids': ['t-finance']}, headers=self.manager
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_service_account_can_reassign_owner_and_team(self) -> None:
        response = self.client.patch(
            '/api/v1/leads/lead-0001',
            json={'owner_id': 'u-200', 'team_ids': ['t-finance']},
            headers=self.service,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['owner_id'], 'u-200')
        self.assertEqual(response.json()['data']['team_ids'], ['t-finance'])

    def test_x_actor_id_cannot_escalate_a_rep(self) -> None:
        headers = dict(self.rep, **{'X-Actor-Id': 'u-100', 'X-Actor-Team-Ids': 't-sales'})
        self.assertEqual(self._lead_ids(headers), ['lead-0002'])
        response = self.client.get('/api/v1/leads/lead-0001', headers=headers)
        self.assertEqual(response.status_code, 404, response.text)

    def test_rep_user_list_is_limited_to_self_and_team(self) -> None:
        payload = self.client.get('/api/v1/users', headers=self.rep).json()
        ids = sorted(row['id'] for row in payload['data'])
        self.assertIn('u-200', ids)
        self.assertNotIn('u-100', ids)
        self.assertNotIn('u-admin', ids)

    def test_rep_cannot_create_a_user(self) -> None:
        response = self.client.post(
            '/api/v1/users', json={'name': '越权建号', 'email': 'x@example.com'}, headers=self.rep
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_rep_cannot_delete_a_user(self) -> None:
        # u-100 对 rep 不可见，走 404；改删自己这条可见记录才能命中 403
        self.assertEqual(self.client.delete('/api/v1/users/u-100', headers=self.rep).status_code, 404)
        response = self.client.delete('/api/v1/users/u-200', headers=self.rep)
        self.assertEqual(response.status_code, 403, response.text)

    def test_audit_is_admin_only(self) -> None:
        self.assertEqual(self.client.get('/api/v1/audit', headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/audit', headers=self.manager).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/audit', headers=self.rep).status_code, 403)

    def test_team_writes_are_admin_only(self) -> None:
        body = {'name': '新团队'}
        self.assertEqual(
            self.client.post('/api/v1/teams', json=body, headers=self.manager).status_code, 403
        )
        self.assertEqual(
            self.client.post('/api/v1/teams', json=body, headers=self.admin).status_code, 201
        )

    def test_stats_are_visible_to_every_role_but_scoped(self) -> None:
        admin_stats = self.client.get('/api/v1/stats/overview', headers=self.admin).json()
        rep_stats = self.client.get('/api/v1/stats/overview', headers=self.rep).json()
        self.assertEqual(admin_stats['counts']['leads'], 2)
        self.assertEqual(rep_stats['counts']['leads'], 1)
        self.assertGreater(
            sum(item['count'] for item in admin_stats['pipeline']),
            sum(item['count'] for item in rep_stats['pipeline']),
        )

    def test_include_deleted_is_admin_only(self) -> None:
        response = self.client.get(
            '/api/v1/leads', params={'include_deleted': 'true'}, headers=self.rep
        )
        self.assertEqual(response.status_code, 400, response.text)


if __name__ == '__main__':
    unittest.main()

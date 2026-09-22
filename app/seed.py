'''演示数据。

与 D:/codex 的 fake 模式保持同 ID、同字段，这样把 AI 能力层的
AICRM_CRM_MODE 从 fake 切到 rest 之后，检索与问答结果可以直接对比。
'''

from __future__ import annotations

from typing import Any

DEMO_TEAMS: tuple[dict[str, Any], ...] = (
    {'id': 't-sales', 'name': '销售一部'},
    {'id': 't-finance', 'name': '金融事业部'},
)

DEMO_USERS: tuple[dict[str, Any], ...] = (
    {
        'id': 'u-100',
        'name': '陈晓',
        'email': 'chenxiao@example.com',
        'team_id': 't-sales',
        'role': 'manager',
        'password': 'sales12345',
    },
    {
        'id': 'u-200',
        'name': '周敏',
        'email': 'zhoumin@example.com',
        'team_id': 't-finance',
        'role': 'rep',
        'password': 'sales12345',
    },
)

DEMO_RECORDS: dict[str, tuple[dict[str, Any], ...]] = {
    'accounts': (
        {
            'id': 'acc-0001',
            'version': '1',
            'updated_at': '2026-09-01T02:00:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'name': '远山科技',
            'industry': '企业服务',
            'scale': '200-500 人',
            'region': '华东',
        },
    ),
    'leads': (
        {
            'id': 'lead-0001',
            'version': '1',
            'updated_at': '2026-09-01T02:00:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'company': '远山科技',
            'contact': '张伟',
            'email': 'zhangwei@yuanshan.example',
            'phone': '13800000001',
            'source': '官网表单',
            'stage': 'new',
        },
        {
            'id': 'lead-0002',
            'version': '1',
            'updated_at': '2026-09-05T06:30:00+00:00',
            'owner_id': 'u-200',
            'team_id': 't-finance',
            'company': '北岭资本',
            'contact': '李娜',
            'email': 'lina@beiling.example',
            'phone': '13800000002',
            'source': '展会',
            'stage': 'contacted',
        },
    ),
    'opportunities': (
        {
            'id': 'opp-0001',
            'version': '3',
            'updated_at': '2026-09-10T09:00:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'name': '远山科技 年度订阅',
            'account_id': 'acc-0001',
            'amount': 268000,
            'currency': 'CNY',
            'stage': 'negotiation',
            'expected_close_date': '2026-10-15',
        },
    ),
    'activities': (
        {
            'id': 'act-0001',
            'version': '1',
            'updated_at': '2026-09-09T03:20:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'kind': 'call',
            'subject': '电话沟通采购流程',
            'content': '客户要求补充数据合规说明，本周内提供。',
            'target_id': 'lead-0001',
            'occurred_at': '2026-09-09T03:00:00+00:00',
        },
    ),
    'tasks': (
        {
            'id': 'task-0001',
            'version': '1',
            'updated_at': '2026-09-09T03:30:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'subject': '整理数据合规说明并发送给客户',
            'due_at': '2026-09-12T10:00:00+00:00',
            'target_id': 'lead-0001',
            'priority': 'high',
            'status': 'open',
        },
    ),
    'notes': (
        {
            'id': 'note-0001',
            'version': '1',
            'updated_at': '2026-09-09T03:25:00+00:00',
            'owner_id': 'u-100',
            'team_id': 't-sales',
            'target_id': 'lead-0001',
            'content': '客户决策链：技术评估由张伟负责，预算由财务总监审批。',
        },
    ),
}
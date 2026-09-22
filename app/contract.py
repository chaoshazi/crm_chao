'''对外契约与业务字段元数据。

这个文件是两件事的唯一来源：

1. 对象类型与字段名必须与 D:/codex 的 app/integrations/crm/field_map.py 一致
   （AI 能力层按这些名字做字段映射，改这里等于改对接契约）；
2. 字段类型、必填、枚举与中文标签，供校验、建表、序列化与前端表单复用。

公共列（id / version / created_at / updated_at / owner_id / team_id / deleted_at）
由存储层统一提供，不写在各对象里。
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMON_FIELDS: tuple[str, ...] = (
    'id',
    'version',
    'created_at',
    'updated_at',
    'created_by',
    'owner_id',
    'team_id',
    'deleted_at',
)

STAGES: tuple[str, ...] = (
    'new',
    'contacted',
    'qualified',
    'proposal',
    'negotiation',
    'closed_won',
    'closed_lost',
)
STAGE_LABELS: dict[str, str] = {
    'new': '新线索',
    'contacted': '已联系',
    'qualified': '已确认',
    'proposal': '方案报价',
    'negotiation': '谈判中',
    'closed_won': '赢单',
    'closed_lost': '输单',
}
ACTIVITY_KINDS: tuple[str, ...] = ('call', 'email', 'meeting', 'visit', 'note')
ACTIVITY_KIND_LABELS: dict[str, str] = {
    'call': '电话',
    'email': '邮件',
    'meeting': '会议',
    'visit': '拜访',
    'note': '记录',
}
TASK_PRIORITIES: tuple[str, ...] = ('low', 'normal', 'high')
TASK_PRIORITY_LABELS: dict[str, str] = {'low': '低', 'normal': '中', 'high': '高'}
TASK_STATUSES: tuple[str, ...] = ('open', 'done')
TASK_STATUS_LABELS: dict[str, str] = {'open': '进行中', 'done': '已完成'}
USER_ROLES: tuple[str, ...] = ('admin', 'manager', 'rep')
ROLE_LABELS: dict[str, str] = {
    'admin': '管理员',
    'manager': '销售主管',
    'rep': '销售',
    'service': '服务账号',
}
SERVICE_ROLE = 'service'

STR_KINDS = frozenset({'str', 'text', 'email', 'phone', 'enum', 'ref'})
ENUM_OPTIONS: dict[str, tuple[str, ...]] = {
    'stage': STAGES,
    'kind': ACTIVITY_KINDS,
    'priority': TASK_PRIORITIES,
    'status': TASK_STATUSES,
    'role': USER_ROLES,
}
ENUM_LABELS: dict[str, dict[str, str]] = {
    'stage': STAGE_LABELS,
    'kind': ACTIVITY_KIND_LABELS,
    'priority': TASK_PRIORITY_LABELS,
    'status': TASK_STATUS_LABELS,
    'role': ROLE_LABELS,
}


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    label: str
    required: bool = False
    ref: str | None = None
    in_list: bool = False
    filterable: bool = False
    write_only: bool = False

    @property
    def options(self) -> tuple[str, ...]:
        return ENUM_OPTIONS.get(self.name, ())

    def to_public(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'kind': self.kind,
            'label': self.label,
            'required': self.required,
            'ref': self.ref,
            'in_list': self.in_list,
            'filterable': self.filterable,
            'write_only': self.write_only,
            'options': [
                {'value': value, 'label': ENUM_LABELS.get(self.name, {}).get(value, value)}
                for value in self.options
            ],
        }


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    label: str
    singular: str
    id_prefix: str
    fields: tuple[Field, ...]
    title_field: str
    default_sort: str = 'updated_at'
    default_order: str = 'desc'
    related_by: tuple[str, ...] = ()

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields)

    @property
    def list_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.in_list and not item.write_only)

    @property
    def filterable_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.filterable)

    @property
    def search_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.kind in STR_KINDS)

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.required)

    def field(self, name: str) -> Field | None:
        for item in self.fields:
            if item.name == name:
                return item
        return None

    def to_public(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'label': self.label,
            'singular': self.singular,
            'title_field': self.title_field,
            'default_sort': self.default_sort,
            'default_order': self.default_order,
            'list_fields': list(self.list_fields),
            'filterable_fields': list(self.filterable_fields),
            'required_fields': list(self.required_fields),
            'related_by': list(self.related_by),
            'fields': [item.to_public() for item in self.fields],
        }


OBJECTS: dict[str, ObjectSpec] = {
    'leads': ObjectSpec(
        name='leads',
        label='线索',
        singular='线索',
        id_prefix='lead',
        title_field='company',
        related_by=('target_id',),
        fields=(
            Field('company', 'str', '公司', required=True, in_list=True),
            Field('contact', 'str', '联系人', in_list=True),
            Field('email', 'email', '邮箱', in_list=True),
            Field('phone', 'phone', '电话'),
            Field('source', 'str', '来源', in_list=True, filterable=True),
            Field('stage', 'enum', '阶段', in_list=True, filterable=True),
        ),
    ),
    'contacts': ObjectSpec(
        name='contacts',
        label='联系人',
        singular='联系人',
        id_prefix='con',
        title_field='name',
        fields=(
            Field('name', 'str', '姓名', required=True, in_list=True),
            Field('account_id', 'ref', '所属客户', ref='accounts', in_list=True, filterable=True),
            Field('title', 'str', '职位', in_list=True),
            Field('email', 'email', '邮箱', in_list=True),
            Field('phone', 'phone', '电话'),
        ),
    ),
    'accounts': ObjectSpec(
        name='accounts',
        label='客户',
        singular='客户',
        id_prefix='acc',
        title_field='name',
        fields=(
            Field('name', 'str', '客户名称', required=True, in_list=True),
            Field('industry', 'str', '行业', in_list=True, filterable=True),
            Field('scale', 'str', '规模'),
            Field('region', 'str', '区域', in_list=True, filterable=True),
        ),
    ),
    'opportunities': ObjectSpec(
        name='opportunities',
        label='商机',
        singular='商机',
        id_prefix='opp',
        title_field='name',
        fields=(
            Field('name', 'str', '商机名称', required=True, in_list=True),
            Field('account_id', 'ref', '所属客户', ref='accounts', in_list=True, filterable=True),
            Field('amount', 'decimal', '金额', in_list=True),
            Field('currency', 'str', '币种'),
            Field('stage', 'enum', '阶段', in_list=True, filterable=True),
            Field('expected_close_date', 'date', '预计成交日', in_list=True),
        ),
    ),
    'activities': ObjectSpec(
        name='activities',
        label='活动',
        singular='活动',
        id_prefix='act',
        title_field='subject',
        related_by=('target_id',),
        fields=(
            Field('kind', 'enum', '类型', required=True, in_list=True, filterable=True),
            Field('subject', 'str', '主题', required=True, in_list=True),
            Field('content', 'text', '内容'),
            Field('target_id', 'ref', '关联记录', ref='any', in_list=True, filterable=True),
            Field('occurred_at', 'datetime', '发生时间', in_list=True),
        ),
    ),
    'tasks': ObjectSpec(
        name='tasks',
        label='任务',
        singular='任务',
        id_prefix='task',
        title_field='subject',
        related_by=('target_id',),
        fields=(
            Field('subject', 'str', '任务', required=True, in_list=True),
            Field('due_at', 'datetime', '截止时间', in_list=True),
            Field('target_id', 'ref', '关联记录', ref='any', in_list=True, filterable=True),
            Field('priority', 'enum', '优先级', in_list=True, filterable=True),
            Field('status', 'enum', '状态', in_list=True, filterable=True),
        ),
    ),
    'notes': ObjectSpec(
        name='notes',
        label='备注',
        singular='备注',
        id_prefix='note',
        title_field='target_id',
        related_by=('target_id',),
        fields=(
            Field('target_id', 'ref', '关联记录', ref='any', required=True, in_list=True),
            Field('content', 'text', '内容', required=True, in_list=True),
        ),
    ),
    'users': ObjectSpec(
        name='users',
        label='用户',
        singular='用户',
        id_prefix='usr',
        title_field='name',
        fields=(
            Field('name', 'str', '姓名', required=True, in_list=True),
            Field('email', 'email', '邮箱', required=True, in_list=True),
            Field('team_id', 'ref', '团队', ref='teams', in_list=True, filterable=True),
            Field('role', 'enum', '角色', in_list=True, filterable=True),
            Field('is_active', 'bool', '启用'),
            Field('password', 'password', '密码', write_only=True),
        ),
    ),
}

OBJECT_NAMES: tuple[str, ...] = tuple(OBJECTS)
TEAMS_OBJECT = 'teams'
DEFAULT_ROLE = 'rep'


def get_object(name: str) -> ObjectSpec | None:
    return OBJECTS.get(str(name or '').strip())


def is_object_type(name: str) -> bool:
    return str(name or '') in OBJECTS


def meta_payload() -> dict[str, Any]:
    '''给前端与联调工具的对象元数据。'''
    return {
        'objects': [OBJECTS[name].to_public() for name in OBJECT_NAMES],
        'object_names': list(OBJECT_NAMES),
        'stages': list(STAGES),
        'stage_labels': STAGE_LABELS,
        'roles': list(USER_ROLES),
        'role_labels': ROLE_LABELS,
    }
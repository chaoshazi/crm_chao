export type Json = Record<string, unknown>;

export type Actor = {
  id: string;
  name: string;
  role: string;
  team_id: string | null;
  kind: string;
};

export type FieldOption = { value: string; label: string };

export type FieldMeta = {
  name: string;
  kind: string;
  label: string;
  required: boolean;
  ref: string | null;
  in_list: boolean;
  filterable: boolean;
  write_only: boolean;
  options: FieldOption[];
};

export type ObjectMeta = {
  name: string;
  label: string;
  singular: string;
  title_field: string;
  default_sort: string;
  default_order: string;
  list_fields: string[];
  filterable_fields: string[];
  required_fields: string[];
  related_by: string[];
  fields: FieldMeta[];
};

export type Meta = {
  objects: ObjectMeta[];
  object_names: string[];
  stages: string[];
  stage_labels: Record<string, string>;
  roles: string[];
  role_labels: Record<string, string>;
  actor: Actor;
};

export type RecordItem = {
  id: string;
  version?: string;
  created_at?: string;
  updated_at?: string;
  owner_id?: string | null;
  team_ids?: string[];
} & Record<string, unknown>;

export type ListResponse = {
  data: RecordItem[];
  next_cursor: string | null;
  total: number;
};

export type Team = {
  id: string;
  name: string;
  version: string;
  member_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type Stats = {
  counts: Record<string, number>;
  pipeline: { stage: string; count: number; amount: number }[];
  pipeline_amount: number;
  won_amount: number;
  open_tasks: number;
  recent_activities: RecordItem[];
};

export type AuditEntry = {
  id: number;
  at: string;
  actor_id: string;
  actor_kind: string;
  on_behalf_of: string | null;
  source: string;
  method: string;
  path: string;
  object_type: string;
  record_id: string | null;
  before: Json | null;
  after: Json | null;
  idempotency_key: string | null;
};
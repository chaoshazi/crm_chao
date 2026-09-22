import { useCallback, useEffect, useState } from 'react';

import { api } from '../lib/api';
import { cellText, fieldOf, formatDateTime, objectOf, type RefContext } from '../lib/format';
import type { Actor, Meta, ObjectMeta, RecordItem, Team } from '../lib/types';
import { RecordForm, type RefOption } from './RecordForm';
import { Alert, Button, Card, Empty, Modal } from './ui';

type Related = { object: ObjectMeta; field: string; rows: RecordItem[] };

export function RecordDetail({
  objectName,
  recordId,
  meta,
  ctx,
  users,
  teams,
  canAssign,
  refOptions,
  onBack,
  onOpen,
}: {
  objectName: string;
  recordId: string;
  meta: Meta;
  ctx: RefContext;
  users: Actor[];
  teams: Team[];
  canAssign: boolean;
  refOptions: Record<string, RefOption[]>;
  onBack: () => void;
  onOpen: (objectName: string, id: string) => void;
}) {
  const object = objectOf(meta, objectName);
  const [record, setRecord] = useState<RecordItem | null>(null);
  const [related, setRelated] = useState<Related[]>([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [quick, setQuick] = useState<{ object: ObjectMeta; target: string } | null>(null);

  const load = useCallback(async () => {
    if (!object) {
      return;
    }
    try {
      const result = await api.get(object.name, recordId);
      setRecord(result.data);
      setError('');
    } catch (err) {
      setRecord(null);
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [object, recordId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!record) {
      setRelated([]);
      return;
    }
    let cancelled = false;
    const linkable = meta.objects.filter(
      (item) =>
        item.name !== objectName &&
        (fieldOf(item, 'target_id') !== null || fieldOf(item, 'account_id') !== null),
    );
    Promise.all(
      linkable.map(async (item) => {
        const field = fieldOf(item, 'account_id') !== null && item.name === 'opportunities' ? 'account_id' : fieldOf(item, 'target_id') !== null ? 'target_id' : 'account_id';
        const result = await api.list(item.name, { [field]: recordId, order: 'desc', limit: 10 });
        return { object: item, field, rows: result.data };
      }),
    )
      .then((items) => {
        if (!cancelled) {
          setRelated(items.filter((item) => item.rows.length > 0));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [record, meta, objectName, recordId]);

  const remove = async () => {
    if (!object) {
      return;
    }
    if (!window.confirm('确认删除这条' + object.singular + '？删除是软删除，可联系管理员恢复。')) {
      return;
    }
    try {
      await api.remove(object.name, recordId);
      onBack();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!object) {
    return <Empty text='未知对象类型' />;
  }

  const title = record
    ? cellText(fieldOf(object, object.title_field), record[object.title_field], ctx, {
        truncate: 120,
      })
    : recordId;

  const quickObject = (name: string) => meta.objects.find((item) => item.name === name) ?? null;
  const notesObject = quickObject('notes');
  const tasksObject = quickObject('tasks');

  return (
    <div className='flex h-full flex-col gap-3'>
      <Card
        title={object.label + '详情：' + title}
        extra={
          <span className='flex gap-2'>
            <Button tone='ghost' onClick={onBack}>
              返回列表
            </Button>
            <Button onClick={() => setEditing(true)} disabled={!record}>
              编辑
            </Button>
            <Button tone='danger' onClick={() => void remove()} disabled={!record}>
              删除
            </Button>
          </span>
        }
      >
        {error ? <Alert text={error} /> : null}
        {!record ? (
          <Empty text='加载中…' />
        ) : (
          <>
            <div className='mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-400'>
              <span>{record.id}</span>
              <span>· 版本 {String(record.version ?? '1')}</span>
              <span>· 负责人 {ctx.userNames[String(record.owner_id ?? '')] ?? record.owner_id ?? '未分配'}</span>
              <span>· 归属 {(record.team_ids ?? [])[0] ? ctx.teamNames[String((record.team_ids ?? [])[0])] ?? (record.team_ids ?? [])[0] : '—'}</span>
              <span>· 更新于 {formatDateTime(record.updated_at)}</span>
            </div>
            <dl className='grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2'>
              {object.fields
                .filter((field) => field.kind !== 'password')
                .map((field) => (
                  <div key={field.name} className='flex gap-2 border-b border-slate-800/60 py-1 text-sm'>
                    <dt className='w-28 shrink-0 text-slate-400'>{field.label}</dt>
                    <dd className='text-slate-200'>
                      {cellText(field, record[field.name], ctx, { truncate: 200 })}
                    </dd>
                  </div>
                ))}
            </dl>
            <div className='mt-3 flex gap-2'>
              {notesObject ? (
                <Button onClick={() => setQuick({ object: notesObject, target: recordId })}>
                  添加备注
                </Button>
              ) : null}
              {tasksObject ? (
                <Button onClick={() => setQuick({ object: tasksObject, target: recordId })}>
                  添加任务
                </Button>
              ) : null}
            </div>
          </>
        )}
      </Card>

      {related.map((item) => (
        <Card key={item.object.name} title={item.object.label + '（' + item.rows.length + '）'}>
          <div className='scroll-thin overflow-auto'>
            <table className='w-full border-collapse text-sm'>
              <thead>
                <tr className='border-b border-slate-800 text-left text-xs text-slate-400'>
                  {item.object.list_fields.map((name) => (
                    <th key={name} className='whitespace-nowrap px-2 py-2 font-medium'>
                      {fieldOf(item.object, name)?.label ?? name}
                    </th>
                  ))}
                  <th className='px-2 py-2 font-medium'>更新时间</th>
                </tr>
              </thead>
              <tbody>
                {item.rows.map((row) => (
                  <tr
                    key={row.id}
                    className='cursor-pointer border-b border-slate-800/60 hover:bg-slate-800/40'
                    onClick={() => onOpen(item.object.name, row.id)}
                  >
                    {item.object.list_fields.map((name) => (
                      <td key={name} className='px-2 py-2 text-slate-200'>
                        {cellText(fieldOf(item.object, name), row[name], ctx)}
                      </td>
                    ))}
                    <td className='whitespace-nowrap px-2 py-2 text-slate-400'>
                      {formatDateTime(row.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}

      {related.length === 0 && record ? (
        <Card title='关联记录'>
          <Empty text='暂无关联的备注、任务或活动' />
        </Card>
      ) : null}

      {editing && record ? (
        <Modal title={'编辑' + object.singular} onClose={() => setEditing(false)}>
          <RecordForm
            object={object}
            value={record}
            refOptions={refOptions}
            users={users}
            teams={teams}
            canAssign={canAssign}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => {
              setEditing(false);
              setRecord(updated);
            }}
          />
        </Modal>
      ) : null}

      {quick ? (
        <Modal
          title={'添加' + quick.object.singular}
          onClose={() => setQuick(null)}
        >
          <RecordForm
            object={quick.object}
            value={null}
            prefill={{ target_id: quick.target }}
            refOptions={refOptions}
            users={users}
            teams={teams}
            canAssign={canAssign}
            onCancel={() => setQuick(null)}
            onSaved={() => {
              setQuick(null);
              void load();
            }}
          />
        </Modal>
      ) : null}
    </div>
  );
}

import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import { cellText, fieldOf, formatMoney, objectOf, type RefContext } from '../lib/format';
import type { Meta, Stats } from '../lib/types';
import { Alert, Card, Empty } from './ui';

const CARD_OBJECTS = ['leads', 'accounts', 'opportunities', 'tasks'] as const;

export function Dashboard({
  meta,
  ctx,
  onOpenObject,
  onOpen,
}: {
  meta: Meta;
  ctx: RefContext;
  onOpenObject: (objectName: string) => void;
  onOpen: (objectName: string, id: string) => void;
}) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const activities = objectOf(meta, 'activities');

  return (
    <div className='flex flex-col gap-3'>
      {error ? <Alert text={error} /> : null}
      <div className='grid grid-cols-2 gap-3 md:grid-cols-4'>
        {CARD_OBJECTS.map((name) => {
          const object = objectOf(meta, name);
          if (!object) {
            return null;
          }
          return (
            <button
              key={name}
              type='button'
              onClick={() => onOpenObject(name)}
              className='rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-left hover:border-sky-700'
            >
              <p className='text-xs text-slate-400'>{object.label}</p>
              <p className='mt-1 text-2xl font-semibold text-slate-100'>
                {stats ? stats.counts[name] ?? 0 : '—'}
              </p>
            </button>
          );
        })}
      </div>

      <div className='grid grid-cols-1 gap-3 md:grid-cols-3'>
        <Card title='管道金额'>
          <p className='text-2xl font-semibold text-slate-100'>
            {stats ? formatMoney(stats.pipeline_amount) : '—'}
          </p>
          <p className='mt-1 text-xs text-slate-500'>全部未关闭商机金额合计</p>
        </Card>
        <Card title='赢单金额'>
          <p className='text-2xl font-semibold text-emerald-300'>
            {stats ? formatMoney(stats.won_amount) : '—'}
          </p>
          <p className='mt-1 text-xs text-slate-500'>阶段为赢单的商机金额合计</p>
        </Card>
        <Card title='待办任务'>
          <p className='text-2xl font-semibold text-sky-300'>{stats ? stats.open_tasks : '—'}</p>
          <p className='mt-1 text-xs text-slate-500'>状态不是已完成的未删除任务</p>
        </Card>
      </div>

      <Card title='商机阶段分布'>
        {!stats || stats.pipeline.length === 0 ? (
          <Empty text='还没有商机数据' />
        ) : (
          <table className='w-full border-collapse text-sm'>
            <thead>
              <tr className='border-b border-slate-800 text-left text-xs text-slate-400'>
                <th className='px-2 py-2 font-medium'>阶段</th>
                <th className='px-2 py-2 font-medium'>数量</th>
                <th className='px-2 py-2 font-medium'>金额</th>
              </tr>
            </thead>
            <tbody>
              {stats.pipeline.map((item) => (
                <tr key={item.stage} className='border-b border-slate-800/60'>
                  <td className='px-2 py-2 text-slate-200'>
                    {meta.stage_labels[item.stage] ?? item.stage}
                  </td>
                  <td className='px-2 py-2 text-slate-300'>{item.count}</td>
                  <td className='px-2 py-2 text-slate-300'>{formatMoney(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title='最近活动'>
        {!stats || stats.recent_activities.length === 0 ? (
          <Empty text='还没有活动记录' />
        ) : (
          <ul className='divide-y divide-slate-800/60'>
            {stats.recent_activities.map((item) => (
              <li
                key={item.id}
                className='cursor-pointer py-2 text-sm hover:bg-slate-800/40'
                onClick={() => onOpen('activities', item.id)}
              >
                <span className='text-slate-200'>
                  {cellText(fieldOf(activities, 'subject'), item.subject, ctx, { truncate: 60 })}
                </span>
                <span className='ml-2 text-xs text-slate-500'>
                  {cellText(fieldOf(activities, 'kind'), item.kind, ctx)} ·{' '}
                  {cellText(fieldOf(activities, 'target_id'), item.target_id, ctx)} ·{' '}
                  {String(item.occurred_at ?? '').slice(0, 16).replace('T', ' ')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
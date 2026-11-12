import {useState} from 'react';
import * as api from '../api/batchReviews';
import * as studiesApi from '../api/studies';
import {useResource} from '../hooks/useResource';
import {refreshResources} from '../stores/resources';
import {batchLabels} from '../constants/enums';
import PageTitle from '../components/common/PageTitle';
import Notice from '../components/common/Notice';
import EmptyState from '../components/common/EmptyState';
import type {User} from '../types/entities';
import type {BatchReview as Batch, BatchItem} from '../types/entities';

const pct = (v: number | null) => (v == null ? '—' : (v * 100).toFixed(1) + '%');
const num = (v: number | null, d = 4) => (v == null ? '—' : v.toFixed(d));

function ItemBadge({status}: {status: string}) {
  return <span className={'badge ' + (status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending')}>{batchLabels[status] || status}</span>;
}

function BatchCard({batch, user, onMessage}: {batch: Batch; user: User; onMessage: (m: string) => void}) {
  const [open, setOpen] = useState(false);
  const s = batch.summary || ({} as Batch['summary']);
  return (
    <article className="record" style={{flexWrap: 'wrap', alignItems: 'start'}}>
      <div style={{flex: 1}}>
        <div className="toolbar" style={{margin: 0}}>
          <b>{batch.name}</b>
          <ItemBadge status={batch.status} />
          <small>{batch.id} · {batch.items.length} 个方案</small>
        </div>
        <small>创建 {batch.created_at} · 更新 {batch.updated_at}</small>
        {s.item_total ? (
          <div className="gap-summary" style={{marginTop: 12, gridTemplateColumns: 'repeat(5, minmax(0, 1fr))'}}>
            <div><small>完成 / 失败 / 待跑</small><b>{s.completed_count} / {s.failed_count} / {s.pending_count}</b></div>
            <div><small>RTS 加权 MAE（分母 {s.rts_weight_denominator}）</small><b>{num(s.rts_weighted_mae)}</b></div>
            <div><small>PCHIP 加权 MAE（分母 {s.pchip_weight_denominator}）</small><b>{num(s.pchip_weighted_mae)}</b></div>
            <div><small>有噪观测区间覆盖（{s.coverage_denominator} 点）</small><b>{pct(s.rts_observation_interval_coverage)}</b></div>
            <div><small>边缘不可估单列</small><b>{s.edge_unestimable_count} 点</b></div>
          </div>
        ) : null}
        <small>{s.aggregation_rule}</small>
        {batch.error && <Notice error={batch.error} />}
      </div>
      <div className="actions">
        <button onClick={() => setOpen(!open)}>{open ? '收起逐项留痕' : '展开逐项留痕'}</button>
        {user.role !== 'viewer' && batch.status !== 'completed' && (
          <button className="primary" onClick={async () => {
            try { await api.resume(batch.id); refreshResources(); onMessage('续跑已提交：已完成且未变更项不重复计算'); }
            catch (e: any) { onMessage(e.message); }
          }}>中断续跑 ↻</button>
        )}
      </div>
      {open && (
        <section className="table-scroll" style={{width: '100%'}}>
          <table>
            <thead><tr><th>方案</th><th>测站</th><th>状态</th><th>遮挡点</th><th>RTS MAE</th><th>PCHIP 可估/MAE</th><th>边缘不可估</th><th>输入指纹</th><th>失败原因</th></tr></thead>
            <tbody>
              {batch.items.map((it: BatchItem) => (
                <tr key={it.study_id}>
                  <td>{it.study_id}</td>
                  <td>{it.detail?.station || '—'}</td>
                  <td><ItemBadge status={it.status} /></td>
                  <td>{it.detail?.metrics.target_count ?? '—'}</td>
                  <td>{it.detail ? num(it.detail.metrics.rts_mae_all) : '—'}</td>
                  <td>{it.detail ? `${it.detail.metrics.pchip_available_count} / ${num(it.detail.metrics.pchip_mae_all)}` : '—'}</td>
                  <td>{it.detail ? it.detail.edge_unestimable.length : '—'}</td>
                  <td><small title={it.fingerprint}>{it.fingerprint.slice(0, 10)}{it.previous_fingerprint ? '（旧 ' + it.previous_fingerprint.slice(0, 8) + ' 已作废）' : ''}</small></td>
                  <td>{it.error || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {s.edge_unestimable_count > 0 && (
            <>
              <h3 style={{fontSize: 14, margin: '16px 0 8px'}}>边缘不可估明细（不进入 PCHIP 分母）</h3>
              <table>
                <thead><tr><th>方案</th><th>测站</th><th>小时</th><th>原因</th></tr></thead>
                <tbody>{s.edge_unestimable.map((e, i) => <tr key={i}><td>{e.study_id}</td><td>{e.station}</td><td>{e.time_hour}</td><td>{e.reason}</td></tr>)}</tbody>
              </table>
            </>
          )}
          {batch.items.some(it => it.detail) && (
            <>
              <h3 style={{fontSize: 14, margin: '16px 0 8px'}}>逐项独立遮挡误差（原始缺失不进分母）</h3>
              {batch.items.filter(it => it.detail).map(it => (
                <div key={it.study_id}>
                  <small>{it.study_id} · {it.detail!.station}</small>
                  <table>
                    <thead><tr><th>小时</th><th>遮挡真值</th><th>RTS 预测 / 误差</th><th>PCHIP 预测 / 误差</th><th>P+R 区间覆盖</th></tr></thead>
                    <tbody>
                      {it.detail!.validation.map(p => (
                        <tr key={p.time_hour}>
                          <td>{p.time_hour}</td>
                          <td>{num(p.validation_truth)}</td>
                          <td>{num(p.rts_prediction)} / {num(p.rts_error)}</td>
                          <td>{p.pchip_estimable ? `${num(p.pchip_prediction)} / ${num(p.pchip_error)}` : '边缘不可估'} </td>
                          <td>{p.rts_covered ? '覆盖' : '未覆盖'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <h3 style={{fontSize: 14, margin: '16px 0 8px'}}>原始缺口补值留痕（{it.detail!.filled_gaps.length} 个）</h3>
                  <table>
                    <thead><tr><th>小时</th><th>RTS 补值</th><th>PCHIP 补值</th></tr></thead>
                    <tbody>{it.detail!.filled_gaps.slice(0, 40).map(g => <tr key={g.time_hour}><td>{g.time_hour}</td><td>{num(g.rts_output)}</td><td>{g.pchip_output == null ? '边缘不可估' : num(g.pchip_output)}</td></tr>)}</tbody>
                  </table>
                  {it.detail!.filled_gaps.length > 40 && <small>仅预览前 40 个补值，完整结果在批次 JSON 产物中。</small>}
                </div>
              ))}
            </>
          )}
        </section>
      )}
    </article>
  );
}

export default function BatchReviews({user}: {user: User}) {
  const {data, error} = useResource(api.list, [] as Batch[]);
  const {data: studies} = useResource(studiesApi.list, []);
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState('夜间批量复核');
  const [message, setMessage] = useState('');
  const toggle = (id: string) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  return (
    <>
      <PageTitle chapter="07" title="一晚复核多个连续遮挡方案，坏方案不拖垮整批" description="逐项保留补值、独立遮挡误差与失败原因；中断续跑跳过已完成项；数据或参数变更时按输入指纹拒绝沿用旧结果。汇总按有效遮挡点加权，原始缺失不进分母，边缘不可估单列。" />
      <Notice error={error || message} />
      {user.role !== 'viewer' && (
        <form className="paper form-grid" onSubmit={async e => {
          e.preventDefault();
          if (!selected.length) { setMessage('请至少勾选一个重建方案'); return; }
          try { await api.create({name, study_ids: selected}); refreshResources(); setMessage('批量复核已提交，结果逐项落盘；可随时中断续跑。'); setSelected([]); }
          catch (e: any) { setMessage(e.message); }
        }}>
          <label>批次名称<input aria-label="批次名称" value={name} onChange={e => setName(e.target.value)} /></label>
          <label>选择重建方案（{selected.length} 个已选）
            <div style={{marginTop: 8, display: 'grid', gap: 6}}>
              {studies.map(su => (
                <label key={su.id} style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                  <input style={{width: 'auto', margin: 0}} type="checkbox" checked={selected.includes(su.id)} onChange={() => toggle(su.id)} />
                  <span>{su.name} <small style={{display: 'inline'}}>{su.id}</small></span>
                </label>
              ))}
            </div>
          </label>
          <button className="primary">提交离线批量复核</button>
        </form>
      )}
      <section className="paper">
        <h2>批量复核批次</h2>
        {data.length ? data.map(b => <BatchCard key={b.id} batch={b} user={user} onMessage={setMessage} />) : <EmptyState text="勾选重建方案并提交后，批量复核结果显示在这里。" />}
      </section>
    </>
  );
}

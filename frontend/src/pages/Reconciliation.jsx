import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronRight, ClipboardCheck, DatabaseZap, Search, Sparkles } from 'lucide-react'

export function Reconciliation({ data, onSelectAnomaly }) {
  const [selected, setSelected] = useState(data?.rows?.[0]?.id)
  useEffect(() => { if (!selected && data?.rows?.[0]?.id) setSelected(data.rows[0].id) }, [data, selected])
  const active = data?.rows?.find((row) => row.id === selected)
  const controlId = data?.summary?.anomaly_id
  const scale = active ? Math.max(active.wms, active.erp, active.tms, active.physical) : 1
  const bar = (value) => `${Math.min(100, value / scale * 100)}%`

  return <div className="page reconciliation-page">
    <section className="page-lead"><div><span className="eyebrow"><DatabaseZap size={14} /> Inventory truth layer</span><h2>Reconcile facts, not just balances.</h2><p>Trace every WMS, ERP, TMS and physical-count divergence back to the transaction that made the systems disagree.</p></div><div className="reconcile-brief"><ClipboardCheck size={20} /><div><strong>{data?.summary?.review_items || 0} records need review</strong><span>{data?.summary?.total_variance || 0} units total variance</span></div></div></section>
    <section className="reconcile-layout"><article className="reconcile-table card-surface"><div className="reconcile-toolbar"><div><h3>Balance comparison</h3><span>Last physical count {data?.summary?.last_count}</span></div><label className="table-search"><Search size={16} /><input placeholder="Filter inventory" /></label></div><div className="inventory-head"><span>Part & location</span><span>WMS</span><span>ERP</span><span>TMS</span><span>Physical</span><span>Variance</span><span /></div>{data?.rows?.map((row) => <button className={`inventory-row ${selected === row.id ? 'selected' : ''}`} key={row.id} onClick={() => setSelected(row.id)}><span><strong>{row.sku}</strong><small>{row.description} · {row.bin}</small></span><b>{row.wms}</b><b>{row.erp}</b><b>{row.tms}</b><b>{row.physical}</b><em className={row.risk}>{row.variance === 0 ? 'Balanced' : `${row.variance > 0 ? '+' : ''}${row.variance}`}</em><ChevronRight size={16} /></button>)}</article>
      <aside className="reconcile-detail card-surface">{active ? <><span className="eyebrow"><Sparkles size={14} /> Reconciliation agent</span><h3>{active.sku}: source of truth</h3><div className="truth-value"><strong>{active.physical}</strong><span>verified units</span></div><p className="root-cause-text">{active.root}</p><div className="balance-bars"><div><span>WMS</span><i><b style={{ width: bar(active.wms) }} /></i><strong>{active.wms}</strong></div><div><span>ERP</span><i><b style={{ width: bar(active.erp) }} /></i><strong>{active.erp}</strong></div><div><span>TMS</span><i><b style={{ width: bar(active.tms) }} /></i><strong>{active.tms}</strong></div><div><span>Count</span><i><b style={{ width: bar(active.physical) }} /></i><strong>{active.physical}</strong></div></div>{controlId && <button className="primary-button full" onClick={() => onSelectAnomaly?.({ id: controlId })}>Open reconciliation control</button>}</> : null}</aside>
    </section>
    <section className="audit-timeline card-surface"><div className="section-title"><div><span className="eyebrow"><CheckCircle2 size={14} /> Transaction archaeology</span><h3>The divergence timeline</h3></div></div><div className="timeline-row">{data?.timeline?.map((event) => <div className={`timeline-event ${event.state}`} key={event.time}><i /><span>{event.time}</span><strong>{event.event}</strong><small>{event.system}</small></div>)}</div></section>
  </div>
}

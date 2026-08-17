import { Check, CircleAlert, Clock3, FileDown, X } from 'lucide-react'
import { api } from '../api'
import { currency, severityLabel } from '../utils'

export function AnomalyDrawer({ anomaly, onClose, onApply, applying }) {
  if (!anomaly) return null
  return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
    <aside className="anomaly-drawer" role="dialog" aria-modal="true" aria-label="Anomaly details" onMouseDown={(event) => event.stopPropagation()}>
      <button className="drawer-close icon-button" onClick={onClose} aria-label="Close details"><X size={20} /></button>
      <div className="drawer-head"><span className={`severity-pill ${anomaly.severity}`}>{severityLabel(anomaly.severity)}</span><span className="anomaly-id">{anomaly.id}</span><h2>{anomaly.title}</h2><p>{anomaly.summary}</p></div>
      <div className="drawer-stats"><div><span>Exposure</span><strong>{currency(anomaly.impact)}</strong></div><div><span>Time to impact</span><strong><Clock3 size={15} />{anomaly.time_to_impact}</strong></div><div><span>Confidence</span><strong>{anomaly.confidence}%</strong></div></div>
      <section><h3>Root-cause assessment</h3><p className="root-cause"><CircleAlert size={17} />{anomaly.root_cause}</p></section>
      <section><h3>Verified evidence</h3><div className="evidence-list">{anomaly.evidence.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong><small>{item.source}</small></div>)}</div></section>
      <section><h3>Recommended controls</h3><div className="action-stack">{anomaly.actions.map((action) => <article className="fix-card" key={action.id}><div><span>{action.owner} · {action.eta}</span><h4>{action.title}</h4><p>{action.description}</p><small>{action.confidence}% confidence · {currency(action.impact_saved)} protected</small></div><button className={action.status === 'applied' ? 'applied' : 'apply-button'} disabled={applying || action.status === 'applied'} onClick={() => onApply(anomaly.id, action.id)}>{action.status === 'applied' ? <><Check size={15} />Applied</> : 'Preview and request approval'}</button></article>)}</div></section>
      <a className="soft-button report-button" href={api.reportUrl(anomaly.id)} download={`control_tower_incident_${anomaly.id}.md`}><FileDown size={15} />Export incident report</a>
    </aside>
  </div>
}

import { useEffect, useState } from 'react'
import { BellRing, Clock, Hash, X } from 'lucide-react'
import { api } from '../api'

/** Preview of the notifications that would reach the shift manager. */
export function EscalationPanel({ open, onClose, onSelectAnomaly }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!open) return
    setData(null); setError('')
    api.escalations().then(setData).catch((cause) => setError(cause.message))
  }, [open])
  if (!open) return null
  return <div className="escalation-shell" role="dialog" aria-label="Escalation previews">
    <div className="escalation-panel card-surface">
      <div className="tour-head"><span className="eyebrow"><BellRing size={13} /> Shift-manager escalations</span><button className="icon-button" onClick={onClose} aria-label="Close escalations"><X size={14} /></button></div>
      {error && <p className="whatif-error">{error}</p>}
      {data && data.items.length === 0 && <p className="escalation-empty">No open critical or high findings — nobody needs to be woken up.</p>}
      {data?.items.map((item) => <button key={item.id} className="escalation-card" onClick={() => { onSelectAnomaly?.({ id: item.id }); onClose() }}>
        <div className="escalation-meta"><span className={`severity-pill ${item.severity}`}>{item.severity}</span><span className="escalation-channel"><Hash size={11} />{item.channel.replace('#', '')}</span><span className="escalation-clock"><Clock size={11} />{item.time_to_impact}</span></div>
        <strong>{item.subject}</strong>
        <small>To: {item.to}</small>
        <p>{item.body}</p>
      </button>)}
      {data && <p className="system-footnote">{data.note}</p>}
    </div>
  </div>
}

import { BellRing, Check, ExternalLink, X } from 'lucide-react'

function notificationTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function NotificationPanel({ open, onClose, notifications = [], onRead, onOpenChange }) {
  if (!open) return null
  return <div className="notification-shell" role="dialog" aria-label="Workflow notifications">
    <section className="notification-panel card-surface">
      <div className="tour-head"><span className="eyebrow"><BellRing size={13} /> Workflow notifications</span><button className="icon-button" onClick={onClose} aria-label="Close notifications"><X size={14} /></button></div>
      <p className="notification-intro">Every request update is sent to the people who must act, the person who requested it, and the people who already decided.</p>
      {!notifications.length && <div className="notification-empty"><Check size={20} /><strong>No new workflow notifications</strong><span>The panel will update when a request changes owner or status.</span></div>}
      <div className="notification-list">{notifications.map((item) => <article className={`notification-card ${item.read ? 'read' : 'unread'}`} key={item.notification_id}>
        <div className="notification-card-top"><span className="notification-dot" /><time>{notificationTime(item.created_at)}</time>{!item.read && <span className="notification-new">New</span>}</div>
        <strong>{item.title}</strong><p>{item.message}</p>
        <div className="notification-card-actions">{item.request_id && <button className="text-button" onClick={() => { onRead?.(item); onOpenChange?.(item.request_id); onClose?.() }}>Open request <ExternalLink size={13} /></button>}{!item.read && <button className="text-button" onClick={() => onRead?.(item)}>Mark as read</button>}</div>
      </article>)}</div>
    </section>
  </div>
}

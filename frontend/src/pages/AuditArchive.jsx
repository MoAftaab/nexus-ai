import { useEffect, useMemo, useState } from 'react'
import { BadgeCheck, CircleX, Clock3, FileClock, FileSpreadsheet, Search, ShieldCheck, UserRoundCheck } from 'lucide-react'
import { api } from '../api'

function formatTimestamp(value) {
  if (!value) return 'Not recorded'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Invalid timestamp'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(parsed)
}

function titleCase(value) {
  return String(value || 'pending').replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

export function AuditArchive() {
  const [events, setEvents] = useState([])
  const [requests, setRequests] = useState([])
  const [chainVerified, setChainVerified] = useState(false)
  const [query, setQuery] = useState('')
  const [site, setSite] = useState('all')
  const [status, setStatus] = useState('all')
  const [decision, setDecision] = useState('all')
  const [expanded, setExpanded] = useState('')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.audit(), api.auditRequests()])
      .then(([eventPayload, requestPayload]) => {
        setEvents(eventPayload.items || [])
        setRequests(requestPayload.items || [])
        setChainVerified(Boolean(eventPayload.chain_verified && requestPayload.chain_verified))
      })
      .catch((cause) => setError(cause.message))
      .finally(() => setLoading(false))
  }, [])

  const sites = useMemo(() => [...new Set([...requests.map((item) => item.site_id), ...events.map((item) => item.site_id)].filter((value) => value && value !== '*'))].sort(), [events, requests])
  const visible = useMemo(() => requests.filter((item) => {
    const searchable = `${item.request_id} ${item.title} ${item.requester_name} ${item.final_approver_name || ''} ${item.decision_comment || ''}`.toLowerCase()
    return (site === 'all' || item.site_id === site)
      && (status === 'all' || item.status === status)
      && (decision === 'all' || item.decision === decision)
      && searchable.includes(query.trim().toLowerCase())
  }), [decision, query, requests, site, status])

  const totals = useMemo(() => ({
    requests: visible.length,
    decided: visible.filter((item) => item.decided_at).length,
    approved: visible.filter((item) => item.decision === 'approved').length,
    rejected: visible.filter((item) => item.decision === 'rejected').length,
  }), [visible])

  const download = async () => {
    setExporting(true); setError('')
    try {
      const { blob, filename } = await api.downloadAuditWorkbook({ site_id: site, search: query, status, decision })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url; link.download = filename; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    } catch (cause) { setError(cause.message) } finally { setExporting(false) }
  }

  return <div className="page archive-page">
    <section className="page-lead audit-lead"><div><span className="eyebrow"><ShieldCheck size={14} /> Auditor-only evidence</span><h2>Every request. Every decision. Every timestamp.</h2><p>A request-level governance ledger with named approvers, exact requested and decided times, comments, policy routes, and immutable evidence.</p></div><button className="primary-button export-workbook" disabled={exporting} onClick={download}><FileSpreadsheet size={16} />{exporting ? 'Building workbook…' : 'Export Excel'}</button></section>

    <section className="audit-stat-grid" aria-label="Audit summary">
      <article className="audit-stat card-surface"><span className="premium-icon tone-blue"><FileClock size={18} /></span><div><small>Requests in view</small><strong>{totals.requests}</strong></div></article>
      <article className="audit-stat card-surface"><span className="premium-icon tone-vivid"><UserRoundCheck size={18} /></span><div><small>Human decisions</small><strong>{totals.decided}</strong></div></article>
      <article className="audit-stat card-surface"><span className="premium-icon tone-green"><BadgeCheck size={18} /></span><div><small>Approved</small><strong>{totals.approved}</strong></div></article>
      <article className="audit-stat card-surface"><span className="premium-icon tone-coral"><CircleX size={18} /></span><div><small>Rejected</small><strong>{totals.rejected}</strong></div></article>
      <article className={`audit-stat card-surface chain-state ${chainVerified ? 'verified' : 'attention'}`}><span className="premium-icon tone-neon"><ShieldCheck size={18} /></span><div><small>Immutable chain</small><strong>{chainVerified ? 'Verified' : 'Review'}</strong></div></article>
    </section>

    <section className="toolbar audit-toolbar card-surface"><label className="table-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Request, person, comment…" /></label><select value={site} onChange={(event) => setSite(event.target.value)}><option value="all">All sites</option>{sites.map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option>{[...new Set(requests.map((item) => item.status).filter(Boolean))].sort().map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select><select value={decision} onChange={(event) => setDecision(event.target.value)}><option value="all">All decisions</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="returned">Returned</option></select></section>
    {error && <p className="form-error">{error}</p>}

    <section className="card-surface audit-ledger">
      <div className="audit-table-wrap"><table className="audit-request-table"><thead><tr><th>Request</th><th>Status / decision</th><th>Requested by</th><th>Requested at</th><th>Decided by</th><th>Decided at</th><th>Approval route</th></tr></thead><tbody>{visible.map((item) => { const toggle = () => setExpanded(expanded === item.request_id ? '' : item.request_id); const assigneeLabel = (stage) => stage.assigned_name || (stage.decided_by ? 'Assignment not recorded (legacy)' : 'Unassigned'); return <tr key={item.request_id} tabIndex={0} className={expanded === item.request_id ? 'expanded' : ''} onClick={toggle} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle() } }}><td><strong>{item.title}</strong><small>{item.request_id} · {titleCase(item.site_id)}</small></td><td><span className={`audit-decision ${item.decision || 'pending'}`}>{titleCase(item.decision || item.status)}</span>{item.decision_comment && <small>{item.decision_comment}</small>}</td><td><strong>{item.requester_name}</strong><small>{item.requester_id}</small></td><td><time>{formatTimestamp(item.requested_at)}</time><small>Submitted {formatTimestamp(item.submitted_at)}</small></td><td><strong>{item.final_approver_name || 'Awaiting decision'}</strong><small>{item.final_approver_id || 'No approver yet'}</small></td><td><time>{formatTimestamp(item.decided_at)}</time></td><td><div className="audit-route">{item.approval_stages.map((stage) => <span title={`${titleCase(stage.required_role)} · ${assigneeLabel(stage)} · ${formatTimestamp(stage.decided_at)}`} className={stage.status} key={`${item.request_id}-${stage.stage}`}>{stage.required_role?.split('_').map((word) => word[0]).join('').toUpperCase()}</span>)}</div>{expanded === item.request_id && <div className="audit-route-detail">{item.approval_stages.map((stage) => <p key={stage.stage}><b>{titleCase(stage.required_role)}</b><span>{assigneeLabel(stage)}</span><time>{stage.decision ? `${titleCase(stage.decision)} · ${formatTimestamp(stage.decided_at)}` : titleCase(stage.status)}</time></p>)}</div>}</td></tr> })}</tbody></table></div>
      {!visible.length && !loading && <div className="empty-state"><FileClock size={23} /><h3>No governed requests match</h3><p>Change a filter or create and submit a request.</p></div>}
      {loading && <div className="empty-state"><Clock3 className="spin" size={23} /><h3>Loading governance ledger…</h3></div>}
    </section>

    <details className="card-surface immutable-events"><summary><span><ShieldCheck size={16} /> Immutable event log</span><b>{events.length} events</b></summary><div className="archive-list">{events.map((event) => <article className="archive-event" key={event.id}><span className="archive-icon"><ShieldCheck size={16} /></span><div><strong>{titleCase(event.event)}</strong><p>{event.actor_name || event.actor} · {titleCase(event.role || 'system')} · {event.site_id || 'global'}</p><small>{event.request_id || 'Dataset run event'} · {formatTimestamp(event.at)}</small></div><code>{event.current_hash ? `${event.current_hash.slice(0, 12)}…` : 'legacy event'}</code></article>)}</div></details>
  </div>
}

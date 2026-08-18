import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, Clock3, Eye, Filter, GitPullRequest, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { api } from '../api'
import { ApprovalHierarchy } from '../components/ApprovalHierarchy'
import { WorkflowCoordination } from '../components/WorkflowCoordination'
import { currency, severityLabel } from '../utils'
import { statusLabel } from '../utils/workflow'

function valueLabel(value) {
  if (value === null || value === undefined || value === '') return 'No value'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function ChangeControl({ principal, focusRequestId, onWorkflowChanged }) {
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [comment, setComment] = useState('')
  const [rollbackComment, setRollbackComment] = useState('')
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try {
      const response = await api.changes(status ? { status } : {})
      setItems(response.items)
      if (focusRequestId) {
        const focused = response.items.find((item) => item.request_id === focusRequestId)
        if (focused) setSelected(await api.change(focused.request_id))
      } else if (selected?.request_id) setSelected(await api.change(selected.request_id))
    } catch (cause) { setError(cause.message) }
  }, [focusRequestId, selected?.request_id, status])
  useEffect(() => { void load() }, [load])
  const allowedActions = selected?.allowed_actions || []
  const canDecide = ['approve', 'reject', 'return'].some((action) => allowedActions.includes(action))
  const submit = async () => {
    setSubmitting(true); setError('')
    try {
      if (selected.status === 'returned') await api.reviseChange(selected.request_id)
      await api.submitChange(selected.request_id)
      await load(); await onWorkflowChanged?.()
    } catch (cause) { setError(cause.message) } finally { setSubmitting(false) }
  }
  const decide = async (decision) => {
    setBusy(true); setError('')
    try { await api.decideChange(selected.request_id, decision, comment); setComment(''); await load(); await onWorkflowChanged?.() } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  const rollback = async () => {
    setBusy(true); setError('')
    try { await api.rollbackChange(selected.request_id, rollbackComment); setRollbackComment(''); await load(); await onWorkflowChanged?.() } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  const previewRows = useMemo(() => selected?.data_preview || [], [selected])
  const waitingForRequester = selected && ['draft', 'returned'].includes(selected.status) && selected.requested_by !== principal?.user_id
  return <div className="page change-control-page">
    <section className="page-lead change-lead"><div><span className="eyebrow"><GitPullRequest size={14} /> Change ledger</span><h2>Move risk through one visible chain.</h2><p>Every approval reads the same source snapshot, policy version, and exact assignee, so operators, approvers, and auditors always see what happens next.</p></div><div className="change-kpi"><span>My decision queue</span><strong>{items.filter((item) => item.allowed_actions?.includes('approve')).length}</strong></div></section>
    <section className="change-grid"><article className="card-surface change-list"><div className="section-title"><div><span className="eyebrow"><Filter size={14} /> Requests</span><h3>Current change ledger</h3></div><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All stages</option><option value="waiting_for_details">Waiting for requested details</option><option value="awaiting_lead">Waiting for Operations Lead</option><option value="awaiting_manager">Waiting for Operations Manager</option><option value="awaiting_quality_compliance">Waiting for Quality and Compliance</option><option value="awaiting_director">Waiting for Supply Chain Director</option><option value="verified">Approved and verified</option><option value="rolled_back">Rolled back to original source data</option></select></div>{items.map((item) => <button className={`change-row ${selected?.request_id === item.request_id ? 'selected' : ''}`} key={item.request_id} onClick={() => setSelected(item)}><span className={`severity-mark ${item.severity}`} /><div><strong>{item.title}</strong><small>{item.request_id} · {item.site_id} · {statusLabel(item.status)}</small></div><b>{currency(item.impact_euros)}</b><ArrowRight size={15} /></button>)}{!items.length && <div className="empty-state"><GitPullRequest size={21} /><h3>No change requests in this view</h3><p>Preview a control from Risk Intelligence to start the governed path.</p></div>}</article>
      <aside className="card-surface change-detail">{selected ? <><div className="drawer-head"><span className={`severity-pill ${selected.severity}`}>{severityLabel(selected.severity)}</span><span className="anomaly-id">{selected.request_id}</span><h2>{selected.title}</h2><p>{selected.site_id} · requested by {selected.requested_by}</p></div><div className="detail-chip-row"><span>Impact <b>{currency(selected.impact_euros)}</b></span><span>Policy <b>Version {selected.policy_version}</b></span><span>Source <b>{selected.source_hash.slice(0, 10)}…</b></span></div><div className="current-owner"><Eye size={15} /><div><span>Current owner</span><strong>{selected.current_owner?.label || 'System'}</strong></div><small>{selected.current_owner?.user_ids?.length ? `Assigned account: ${selected.current_owner.user_ids.join(', ')}` : 'No further human decision is waiting.'}</small></div>{waitingForRequester && <div className="workflow-notice"><Clock3 size={17} /><div><strong>No approval button yet</strong><p>This request is still with {selected.requested_by}. The requester must select <b>Submit for approval</b>; the server will then assign one named approver.</p></div></div>}<ApprovalHierarchy request={selected} onSubmit={allowedActions.includes('submit') ? submit : undefined} submitting={submitting} /><WorkflowCoordination request={selected} onChanged={async () => { await load(); await onWorkflowChanged?.() }} /><div className="snapshot-summary"><div><span>Before</span><strong>{selected.before_snapshot?.records?.length === 1 ? '1 record saved' : `${selected.before_snapshot?.records?.length || 0} records saved`}</strong></div><ArrowRight size={15} /><div><span>Proposed fields</span><strong>{selected.proposed_snapshot?.fields?.join(', ') || 'No fields'}</strong></div><ArrowRight size={15} /><div><span>After</span><strong>{selected.after_snapshot ? 'Captured and verified' : 'Captured after approval'}</strong></div></div><section className="data-preview"><div className="section-title"><div><span className="eyebrow"><Eye size={14} /> Saved data preview</span><h3>Before, proposed, and after</h3></div><span className="preview-count">{previewRows.length} field changes</span></div><p className="preview-help">This is the exact data that approvers review. The after column is filled only after the approved change is applied and verified.</p>{previewRows.length ? <div className="preview-table-wrap"><table className="preview-table"><thead><tr><th>Data table</th><th>Record</th><th>Field</th><th>Before</th><th>Proposed</th><th>After</th></tr></thead><tbody>{previewRows.slice(0, 40).map((row, index) => <tr key={`${row.table}-${row.record_key}-${row.field}-${index}`}><td>{row.table}</td><td>{row.record_key}</td><td>{row.field}</td><td>{valueLabel(row.before)}</td><td className="proposed-value">{valueLabel(row.proposed)}</td><td className={row.after !== undefined && row.after !== null ? 'after-value' : ''}>{valueLabel(row.after)}</td></tr>)}</tbody></table></div> : <div className="notification-empty"><ShieldCheck size={18} /><span>No field-level changes were found in this snapshot.</span></div>}<div className="effect-card"><div><span>Expected effect</span><strong>{currency(selected.effect?.value_protected || selected.impact_euros)} protected</strong></div><div><span>Current effect</span><strong>{statusLabel(selected.effect?.status || 'planned')}</strong></div><p>{selected.effect?.corrections || 'No source correction has been executed yet.'}</p></div></section>{canDecide && <div className="approval-panel"><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Decision comment - required for rejection or return" /><div>{allowedActions.includes('return') && <button className="soft-button" disabled={busy} onClick={() => decide('returned')}><Clock3 size={15} />Return for changes</button>}{allowedActions.includes('reject') && <button className="danger-button" disabled={busy} onClick={() => decide('rejected')}><X size={15} />Reject</button>}{allowedActions.includes('approve') && <button className="primary-button" disabled={busy} onClick={() => decide('approved')}><Check size={15} />Approve and move forward</button>}</div></div>}{selected.rollback_available && <div className="rollback-panel"><div><span className="eyebrow"><RotateCcw size={14} /> Director rollback</span><h3>Restore the original source data</h3><p>Rollback is available because this request is verified. The system checks that the live source still matches the saved after preview before restoring the before preview.</p></div><textarea value={rollbackComment} onChange={(event) => setRollbackComment(event.target.value)} placeholder="Explain why the verified change must be rolled back" /><button className="danger-button" disabled={busy || !rollbackComment.trim()} onClick={rollback}><RotateCcw size={15} />Rollback verified change</button></div>}{error && <p className="form-error">{error}</p>}</> : <div className="empty-state"><GitPullRequest size={24} /><h3>Select a request</h3><p>The full before, proposed, and after record appears here.</p></div>}</aside></section>
  </div>
}

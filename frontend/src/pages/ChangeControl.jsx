import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Check, Clock3, Eye, Filter, GitPullRequest, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { api } from '../api'
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
  const selectedIdRef = useRef(null)
  useEffect(() => { selectedIdRef.current = selected?.request_id || null }, [selected?.request_id])
  const load = useCallback(async () => {
    try {
      const response = await api.changes(status ? { status } : {})
      setItems(response.items.map((item) => ({ ...item, source_hash: item.source_hash || '' })))
      const targetId = focusRequestId || selectedIdRef.current
      const focused = response.items.find((item) => item.request_id === targetId)
      if (focused) setSelected(await api.change(focused.request_id))
      else if (targetId) setSelected(null)
    } catch (cause) { setError(cause.message) }
  }, [focusRequestId, status])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!selected?.request_id || selected.source_hash) return
    void api.change(selected.request_id).then(setSelected).catch((cause) => setError(cause.message))
  }, [selected?.request_id, selected?.source_hash])
  const selectRequest = async (requestId) => {
    setError('')
    try { setSelected(await api.change(requestId)) } catch (cause) { setError(cause.message) }
  }
  const allowedActions = selected?.allowed_actions || []
  const canDecide = ['approve', 'reject', 'return', 'submit'].some((action) => allowedActions.includes(action))
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
  return (
    <div className="page change-control-page">
      <div className="change-grid">
        <article className="card-surface change-list">
          <div className="section-title">
            <div>
              <span className="eyebrow"><Filter size={14} /> Requests</span>
              <h3>Current change ledger</h3>
            </div>
            <div className="change-toolbar-actions">
              <span className="change-kpi-chip">
                Queue: {items.filter((item) => item.allowed_actions?.includes('approve')).length}
              </span>
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">All stages</option>
                <option value="submitted">Submitted</option>
                <option value="draft">Draft</option>
                <option value="waiting_for_details">Waiting for requested details</option>
                <option value="awaiting_lead">Waiting for Operations Lead</option>
                <option value="awaiting_manager">Waiting for Operations Manager</option>
                <option value="awaiting_quality_compliance">Waiting for Quality and Compliance</option>
                <option value="awaiting_director">Waiting for Supply Chain Director</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="returned">Returned for changes</option>
                <option value="cancelled">Cancelled</option>
                <option value="verified">Approved and verified</option>
                <option value="rolled_back">Rolled back to original source data</option>
              </select>
            </div>
          </div>

          <div className="change-rows-scroll">
            {items.map((item) => (
              <button
                className={`change-row ${selected?.request_id === item.request_id ? 'selected' : ''}`}
                key={item.request_id}
                onClick={() => void selectRequest(item.request_id)}
              >
                <span className={`severity-mark ${item.severity}`} />
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.request_id} · {item.site_id} · {statusLabel(item.status)}</small>
                </div>
                <b>{currency(item.impact_euros)}</b>
                <ArrowRight size={15} />
              </button>
            ))}
            {!items.length && (
              <div className="empty-state">
                <GitPullRequest size={21} />
                <h3>No change requests in this view</h3>
                <p>Preview a control from Risk Intelligence to start the governed path.</p>
              </div>
            )}
          </div>
        </article>

        <aside className="card-surface change-detail">
          {selected ? (
            <>
              <div className="change-detail-head">
                <div className="change-head-top">
                  <div className="change-title-group">
                    <span className={`severity-pill ${selected.severity}`}>{severityLabel(selected.severity)}</span>
                    <span className="anomaly-id">{selected.request_id}</span>
                    <h2>{selected.title}</h2>
                  </div>
                  <div className="change-chips">
                    <span>{selected.site_id} · by {selected.requested_by}</span>
                    <span>Impact: <b>{currency(selected.impact_euros)}</b></span>
                    <span>Policy: <b>V{selected.policy_version}</b></span>
                    <span>Owner: <b>{selected.current_owner?.label || 'System'}</b></span>
                  </div>
                </div>
              </div>

              <div className="change-detail-body">
                {/* Row 1: Two Balanced Operations Cards */}
                <div className="change-detail-top-grid">
                  {/* Left: Snapshot Archaeology */}
                  <div className="change-subcard snapshot-card">
                    <div className="subcard-head">
                      <span className="eyebrow"><GitPullRequest size={12} /> Snapshot Archaeology</span>
                      <small>SHA: {selected.source_hash ? `${selected.source_hash.slice(0, 8)}…` : 'Verified'}</small>
                    </div>
                    <div className="snapshot-pipeline">
                      <div className="pipeline-node">
                        <span className="node-tag">Before</span>
                        <strong className="node-val">{selected.before_snapshot?.records?.length || 1} record</strong>
                      </div>
                      <ArrowRight size={13} className="pipeline-arrow" />
                      <div className="pipeline-node proposed">
                        <span className="node-tag">Proposed</span>
                        <strong className="node-val">{selected.proposed_snapshot?.fields?.join(', ') || 'None'}</strong>
                      </div>
                      <ArrowRight size={13} className="pipeline-arrow" />
                      <div className="pipeline-node">
                        <span className="node-tag">After</span>
                        <strong className="node-val">{selected.after_snapshot ? 'Verified' : 'On approval'}</strong>
                      </div>
                    </div>
                  </div>

                  {/* Right: Governed Actions & Owner */}
                  <div className="change-subcard governance-card">
                    <div className="subcard-head">
                      <span className="eyebrow"><Eye size={12} /> Governance & Controls</span>
                      <small>Assigned: {selected.current_owner?.user_ids?.join(', ') || 'Active'}</small>
                    </div>
                    <WorkflowCoordination request={selected} onChanged={async () => { await load(); await onWorkflowChanged?.() }} />
                  </div>
                </div>

                {waitingForRequester && (
                  <div className="workflow-notice">
                    <Clock3 size={15} />
                    <div>
                      <strong>Awaiting Requester Submission</strong>
                      <p>This request is with {selected.requested_by}. Click <b>Submit for approval</b> below to start the workflow.</p>
                    </div>
                  </div>
                )}

                {/* Row 2: Saved Data Preview Table */}
                <section className="data-preview">
                  <div className="section-title">
                    <div>
                      <span className="eyebrow"><Eye size={13} /> Saved data preview</span>
                      <h3>Before, proposed, and after</h3>
                    </div>
                    <span className="preview-count">{previewRows.length} field-level modifications</span>
                  </div>
                  {previewRows.length ? (
                    <div className="preview-table-wrap">
                      <table className="preview-table">
                        <thead>
                          <tr>
                            <th>Data Table</th>
                            <th>Record ID</th>
                            <th>Field</th>
                            <th>Before Value</th>
                            <th>Proposed Value</th>
                            <th>After Approval</th>
                          </tr>
                        </thead>
                        <tbody>
                          {previewRows.slice(0, 6).map((row, index) => (
                            <tr key={`${row.table}-${row.record_key}-${row.field}-${index}`}>
                              <td>{row.table}</td>
                              <td>{row.record_key}</td>
                              <td>{row.field}</td>
                              <td>{valueLabel(row.before)}</td>
                              <td className="proposed-value">{valueLabel(row.proposed)}</td>
                              <td className={row.after !== undefined && row.after !== null ? 'after-value' : ''}>{valueLabel(row.after)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="notification-empty">
                      <ShieldCheck size={16} />
                      <span>No field-level changes in this snapshot.</span>
                    </div>
                  )}
                </section>

                {/* Row 3: ERP Execution & System Matrix (4 Metric Cards) */}
                <div className="change-erp-matrix">
                  <div className="erp-metric-cell">
                    <span>Value Protected</span>
                    <strong>{currency(selected.effect?.value_protected || selected.impact_euros)}</strong>
                    <small>Total exposure: {currency(selected.impact_euros)}</small>
                  </div>
                  <div className="erp-metric-cell">
                    <span>Target ERP Table</span>
                    <strong>{previewRows[0]?.table || 'outbound_orders'}</strong>
                    <small>Record: {previewRows[0]?.record_key || selected.site_id}</small>
                  </div>
                  <div className="erp-metric-cell">
                    <span>Governance State</span>
                    <strong className="status-highlight">{statusLabel(selected.effect?.status || selected.status || 'planned')}</strong>
                    <small>{selected.effect?.corrections || 'Target correction planned'}</small>
                  </div>
                  <div className="erp-metric-cell">
                    <span>Policy Compliance</span>
                    <strong>Version {selected.policy_version}</strong>
                    <small>Plant SLA Verified</small>
                  </div>
                </div>

                {selected.rollback_available && (
                  <div className="rollback-panel">
                    <div>
                      <span className="eyebrow"><RotateCcw size={13} /> Director rollback</span>
                      <h3>Restore original source data</h3>
                    </div>
                    <input
                      type="text"
                      className="comment-input"
                      value={rollbackComment}
                      onChange={(event) => setRollbackComment(event.target.value)}
                      placeholder="Reason for rollback..."
                    />
                    <button className="danger-button" disabled={busy || !rollbackComment.trim()} onClick={rollback}>
                      <RotateCcw size={13} />Rollback
                    </button>
                  </div>
                )}
                {error && <p className="form-error">{error}</p>}
              </div>

              {canDecide && (
                <div className="approval-panel">
                  {['approve', 'reject', 'return'].some((action) => allowedActions.includes(action)) && (
                    <input
                      type="text"
                      className="comment-input"
                      value={comment}
                      onChange={(event) => setComment(event.target.value)}
                      placeholder="Decision comment (required for reject / return)..."
                    />
                  )}
                  <div className="approval-actions">
                    {allowedActions.includes('submit') && (
                      <button className="primary-button" disabled={submitting} onClick={submit}>
                        <Check size={14} />
                        {submitting ? 'Submitting...' : 'Submit for approval'}
                      </button>
                    )}
                    {allowedActions.includes('return') && (
                      <button className="soft-button" disabled={busy} onClick={() => decide('returned')}>
                        <Clock3 size={14} />Return
                      </button>
                    )}
                    {allowedActions.includes('reject') && (
                      <button className="danger-button" disabled={busy} onClick={() => decide('rejected')}>
                        <X size={14} />Reject
                      </button>
                    )}
                    {allowedActions.includes('approve') && (
                      <button className="primary-button" disabled={busy} onClick={() => decide('approved')}>
                        <Check size={14} />Approve
                      </button>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <GitPullRequest size={24} />
              <h3>Select a request</h3>
              <p>The full before, proposed, and after record appears here.</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

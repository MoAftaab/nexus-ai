import { ArrowRight, Check, CircleDot, Clock3, GitBranch, RotateCcw, X } from 'lucide-react'
import { getApprovalRoute, statusLabel, workflowRoleLabels } from '../utils/workflow'

function stageVisual(status, requestStatus) {
  if (status === 'completed') return { className: 'completed', icon: <Check size={14} />, text: 'Approved and moved forward' }
  if (status === 'active') return { className: 'active', icon: <CircleDot size={14} />, text: 'Waiting for this decision' }
  if (status === 'paused') return { className: 'returned', icon: <Clock3 size={14} />, text: 'Paused for requested details' }
  if (status === 'rejected') return { className: 'rejected', icon: <X size={14} />, text: 'Rejected and stopped' }
  if (requestStatus === 'returned' && status === 'waiting') return { className: 'returned', icon: <RotateCcw size={14} />, text: 'Returned for changes' }
  if (status === 'planned') return { className: 'planned', icon: <Clock3 size={14} />, text: 'Next approval stage' }
  return { className: 'waiting', icon: <Clock3 size={14} />, text: 'Waiting' }
}

function routeForRequest(request) {
  return (request.steps || request.approval_route)?.map((step) => ({ ...step, label: workflowRoleLabels[step.required_role || step.role] || step.required_role || step.role })) || []
}

export function ApprovalHierarchy({ request, preview, compact = false, onOpenLedger, onSubmit, submitting = false }) {
  const isPreview = !request && Boolean(preview)
  const stages = request ? routeForRequest(request) : (preview?.approval_route || getApprovalRoute(preview || {})).map((stage) => ({ ...stage, status: 'planned' }))
  if (!stages.length) return <section className={`approval-hierarchy empty ${compact ? 'compact' : ''}`}><GitBranch size={16} /><div><strong>No approval route selected</strong><span>Choose a control to see who receives the request.</span></div></section>

  const completed = stages.filter((stage) => stage.status === 'completed').length
  const active = stages.find((stage) => ['active', 'paused'].includes(stage.status))
  const requestStatus = request?.status || ''
  const displayStatus = isPreview ? 'Ready to submit' : statusLabel(requestStatus)
  const statusClass = isPreview ? 'preview' : requestStatus === 'verified' ? 'success' : requestStatus === 'rolled_back' ? 'returned' : requestStatus === 'rejected' || requestStatus === 'stale' ? 'danger' : ['returned', 'waiting_for_details'].includes(requestStatus) ? 'returned' : active ? 'active' : 'neutral'

  return <section className={`approval-hierarchy ${compact ? 'compact' : ''}`} aria-label="Approval hierarchy">
    <div className="approval-hierarchy-head">
      <div><span className="eyebrow"><GitBranch size={14} /> Approval hierarchy</span><strong>{displayStatus}</strong><small>{isPreview ? 'The route is calculated from risk, impact, site, and quality requirements.' : `${completed} of ${stages.length} approval stages completed.`}</small></div>
      <span className={`flow-status ${statusClass}`}>{isPreview ? 'Route preview' : statusLabel(requestStatus)}</span>
    </div>
    <div className="approval-flow-track">{stages.map((stage, index) => { const visual = stageVisual(stage.status, request?.status); return <div className={`approval-flow-stage ${visual.className}`} key={stage.id || stage.role}>
      <div className="approval-flow-marker">{visual.icon}</div>
      <div className="approval-flow-copy"><strong>{stage.label || workflowRoleLabels[stage.role] || stage.role}</strong><span>{visual.text}</span></div>
      {index < stages.length - 1 && <ArrowRight className="approval-flow-arrow" size={16} />}
    </div> })}</div>
    {!compact && request?.audit_history && <div className="auditor-history"><div><span>Requested by</span><strong>{request.audit_history.requested_by?.display_name}</strong><time>{request.audit_history.requested_at ? new Date(request.audit_history.requested_at).toLocaleString() : '—'}</time></div>{request.audit_history.submitted_at && <div><span>Submitted for approval</span><strong>{request.audit_history.requested_by?.display_name}</strong><time>{new Date(request.audit_history.submitted_at).toLocaleString()}</time></div>}{request.audit_history.approvals.map((approval) => <div key={`${approval.stage}-${approval.decided_at}`}><span>{approval.decision?.replaceAll('_', ' ') || approval.status}</span><strong>{approval.approver?.display_name || 'System'}</strong><time>{approval.decided_at ? new Date(approval.decided_at).toLocaleString() : '—'}</time>{approval.comment && <em>{approval.comment}</em>}</div>)}</div>}
    <div className="approval-hierarchy-foot"><span>{requestStatus === 'waiting_for_details' ? 'The requester has the detail request; the named approver remains reserved.' : active ? `${active.label || workflowRoleLabels[active.required_role]} has the request` : isPreview ? 'Requester submission starts the first stage' : statusLabel(requestStatus)}</span>{request?.after_snapshot && requestStatus !== 'rolled_back' && <span className="flow-complete"><Check size={13} /> Final result verified</span>}{requestStatus === 'rolled_back' && <span className="flow-complete rollback-state"><RotateCcw size={13} /> Original state restored</span>}{onSubmit && ['draft', 'returned'].includes(requestStatus) && <button className="text-button" disabled={submitting} onClick={onSubmit}>{submitting ? requestStatus === 'returned' ? 'Refreshing preview...' : 'Submitting...' : requestStatus === 'returned' ? 'Refresh preview and submit' : 'Submit for approval'} <ArrowRight size={14} /></button>}{onOpenLedger && <button className="text-button" onClick={onOpenLedger}>Open change ledger <ArrowRight size={14} /></button>}</div>
  </section>
}

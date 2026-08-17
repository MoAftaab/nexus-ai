import { useEffect, useMemo, useState } from 'react'
import { BellRing, CheckCircle2, ClipboardList, Route, Send, UserRoundCog } from 'lucide-react'
import { api } from '../api'

const coordinationActions = ['request_details', 'respond_details', 'delegate', 'send_reminder', 'prepare_escalation']

export function WorkflowCoordination({ request, onChanged }) {
  const allowed = request?.allowed_actions || []
  const available = coordinationActions.filter((action) => allowed.includes(action))
  const [mode, setMode] = useState('')
  const [text, setText] = useState('')
  const [recipient, setRecipient] = useState('')
  const [recipients, setRecipients] = useState([])
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState('')
  const openDetail = useMemo(() => request?.detail_requests?.find((item) => item.status === 'open'), [request])

  useEffect(() => {
    setMode(''); setText(''); setRecipient(''); setRecipients([]); setPreview(null); setError(''); setReceipt('')
  }, [request?.request_id])

  if (!available.length && !openDetail) return null

  const choose = async (nextMode) => {
    setMode(nextMode); setText(''); setPreview(null); setError(''); setReceipt('')
    if (nextMode === 'delegate' || nextMode === 'escalation') {
      try {
        const result = await api.eligibleWorkflowRecipients(request.request_id, nextMode === 'delegate' ? 'delegation' : 'escalation')
        setRecipients(result.items || [])
        setRecipient(result.items?.length === 1 ? result.items[0].user_id : '')
      } catch (cause) { setError(cause.message) }
    }
  }

  const complete = async () => {
    if (!text.trim()) return
    setBusy(true); setError(''); setReceipt('')
    try {
      if (mode === 'request_details') {
        await api.requestChangeDetails(request.request_id, { question: text, requested_fields: [], due_hours: 24 })
        setReceipt('Detail request delivered to the named requester.')
      } else if (mode === 'respond_details') {
        await api.respondChangeDetails(request.request_id, openDetail.detail_request_id, { response: text, evidence_attachments: [] })
        setReceipt('Response delivered; the same approver now owns the resumed stage.')
      } else if (mode === 'delegate') {
        await api.delegateChange(request.request_id, { assignee_user_id: recipient, reason: text })
        setReceipt('The stage was reassigned and both users were notified.')
      } else {
        const kind = mode === 'escalation' ? 'escalation' : 'reminder'
        if (!preview) {
          setPreview(await api.previewWorkflowAction(request.request_id, kind, { reason: text, recipient_user_id: recipient || null }))
          return
        }
        await api.confirmWorkflowAction(request.request_id, kind, preview.action_id)
        setReceipt(`${kind === 'reminder' ? 'Reminder' : 'Escalation'} delivered with an auditable receipt.`)
      }
      setMode(''); setText(''); setPreview(null)
      await onChanged?.()
    } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }

  const actions = [
    ['request_details', ClipboardList, 'Request details'],
    ['respond_details', Send, 'Respond with details'],
    ['delegate', UserRoundCog, 'Delegate stage'],
    ['send_reminder', BellRing, 'Send reminder'],
    ['prepare_escalation', Route, 'Prepare escalation'],
  ].filter(([action]) => available.includes(action))
  const modeKey = mode === 'escalation' ? 'prepare_escalation' : mode === 'reminder' ? 'send_reminder' : mode

  return <section className="workflow-coordination" aria-label="Governed workflow actions">
    <div className="workflow-coordination-head"><div><span>Governed coordination</span><strong>Only server-authorized actions appear</strong></div><small>Every confirmation is rechecked and audited.</small></div>
    <div className="workflow-action-pills">{actions.map(([action, Icon, label]) => <button className={modeKey === action ? 'active' : ''} type="button" key={action} onClick={() => choose(action === 'prepare_escalation' ? 'escalation' : action === 'send_reminder' ? 'reminder' : action)}><Icon size={14} />{label}</button>)}</div>
    {mode && <div className="workflow-action-compose">
      {(mode === 'delegate' || mode === 'escalation') && <label><span>Eligible recipient</span><select value={recipient} onChange={(event) => setRecipient(event.target.value)}><option value="">Select a verified recipient</option>{recipients.map((item) => <option key={item.user_id} value={item.user_id}>{item.display_name} · {item.role.replaceAll('_', ' ')}</option>)}</select></label>}
      {mode === 'respond_details' && openDetail && <div className="workflow-detail-prompt"><ClipboardList size={15} /><div><strong>{openDetail.question || 'Additional evidence requested'}</strong><small>{openDetail.requested_fields?.join(', ') || 'Provide a factual response for the assigned approver.'}</small></div></div>}
      {preview && <div className="workflow-preview-card"><Route size={16} /><div><span>Confirm delivery to</span><strong>{preview.payload?.recipient_name} · {preview.payload?.recipient_role?.replaceAll('_', ' ')}</strong><small>{preview.payload?.current_stage?.replaceAll('_', ' ')} · SLA {preview.payload?.sla?.elapsed_percent ?? '—'}%</small></div></div>}
      {!preview && <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder={mode === 'respond_details' ? 'Provide the requested facts and evidence references' : mode === 'request_details' ? 'Specify exactly what evidence or information is required' : 'Give a factual reason for this governed action'} />}
      <div className="workflow-compose-actions"><button type="button" className="soft-button" onClick={() => { setMode(''); setPreview(null) }}>Cancel</button><button type="button" className="primary-button" disabled={busy || (!preview && (!text.trim() || ((mode === 'delegate' || mode === 'escalation') && !recipient)))} onClick={complete}><CheckCircle2 size={14} />{preview ? 'Confirm and send' : mode === 'reminder' || mode === 'escalation' ? 'Create factual preview' : 'Confirm action'}</button></div>
    </div>}
    {receipt && <p className="workflow-receipt"><CheckCircle2 size={14} />{receipt}</p>}
    {error && <p className="form-error">{error}</p>}
  </section>
}

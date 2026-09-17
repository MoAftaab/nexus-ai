import { BellRing, CheckCircle2, ChevronRight, Clock3, Database, MapPin, Radio, Send, ShieldCheck, ThumbsDown, ThumbsUp, UserRound, X } from 'lucide-react'
import { Markdown } from '../Markdown'
import { WaltAgentFlow } from './WaltAgentFlow'

export function WaltMessage({ message, loading, architecture, onChoice, onConfirmAction, onDismissAction, onFeedback, onSelectAnomaly }) {
  const assistant = message.role === 'assistant'
  const action = message.action
  return <article className={`walt-chat-message ${message.role}`}>
    {assistant && !message.content && loading
      ? <div className="walt-typing" aria-label="WALT is processing"><i /><i /><i /><span>Consulting 7 specialist agents…</span></div>
      : assistant
        ? <Markdown text={message.content || ''} onCite={(id) => onSelectAnomaly?.({ id })} />
        : <p>{message.content}</p>}
    {assistant && message.choices?.length > 0 && <div className="walt-command-choices" aria-label="Choose a governed request">
      {message.choices.map((choice) => <button type="button" key={choice.request_id} onClick={() => onChoice?.(choice.prompt)}>
        <span>{choice.request_id}</span><small>{choice.label.split(' · ', 2)[1] || choice.status}</small>
      </button>)}
    </div>}
    {assistant && message.suggestions?.length > 0 && <div className="walt-suggestion-actions" aria-label="Explore an available control">
      <span className="walt-suggestion-label">Explore an available control</span>
      {message.suggestions.map((suggestion) => <button
        type="button"
        key={suggestion}
        onClick={() => onChoice?.(`Walk me through this control before I approve it: "${suggestion}". What are the steps, risks and verification?`)}
      >
        <span>{suggestion}</span><ChevronRight size={12} />
      </button>)}
    </div>}
    {assistant && action && <section className="walt-action-card" data-status={action.status || 'previewed'} aria-label={`${action.kind} confirmation`}>
      <header><span><BellRing size={14} /></span><div><strong>{action.kind === 'escalation' ? 'Escalation ready' : 'Approval reminder ready'}</strong><small>Human confirmation required</small></div></header>
      <dl>
        <div><dt><UserRound size={12} />Recipient</dt><dd>{action.recipient_name}</dd></div>
        <div><dt><ShieldCheck size={12} />Request</dt><dd>{action.request_id}</dd></div>
        <div><dt><MapPin size={12} />Site</dt><dd>{action.site_id}</dd></div>
        <div><dt><Clock3 size={12} />SLA</dt><dd>{action.sla?.overdue ? 'Overdue' : action.sla?.deadline ? `Due ${new Date(action.sla.deadline).toLocaleString()}` : 'No deadline'}</dd></div>
      </dl>
      {action.status === 'confirmed' ? <div className="walt-action-result"><CheckCircle2 size={15} /><span>Sent and audit-recorded{action.confirmed_at ? ` · ${new Date(action.confirmed_at).toLocaleString()}` : ''}</span></div>
        : action.status === 'dismissed' ? <div className="walt-action-result is-muted"><X size={14} /><span>Not sent</span></div>
          : <div className="walt-action-controls">
            <button type="button" className="confirm" disabled={loading || action.status === 'confirming'} onClick={() => onConfirmAction?.(message.id, action)}><Send size={13} />{action.status === 'confirming' ? 'Sending…' : 'Confirm & notify now'}</button>
            <button type="button" disabled={loading} onClick={() => onDismissAction?.(message.id)}>Not now</button>
          </div>}
      {action.status === 'failed' && <p className="walt-action-failure">{action.error}</p>}
    </section>}
    {assistant && message.content && <>
      {message.trace?.length > 0 && !loading && <WaltAgentFlow trace={message.trace} architecture={architecture} />}
      <footer>
        {['codecraft', 'openai', 'ollama'].includes(message.source) ? <Radio size={11} /> : message.source === 'governance' ? <ShieldCheck size={11} /> : <Database size={11} />}
        <span>{['codecraft', 'openai', 'ollama'].includes(message.source) ? `${architecture?.provider_label || 'Mesh LLM'} · 7 specialist agents + Orchestrator (WALT)` : message.source === 'governance' ? 'Verified identity & workflow policy' : message.source === 'request_cancelled' ? 'Request stopped by operator' : 'Grounded operational twin'}{message.confidence ? ` · ${message.confidence} confidence` : ''}{message.sourceRefs?.length ? ` · ${message.sourceRefs.slice(0, 3).join(', ')}` : ''}</span>
      </footer>
      {message.id && !loading && <div className="walt-message-feedback" aria-label="Rate WALT response">
        <span>Was this useful?</span>
        <button type="button" className={message.feedback === 'helpful' ? 'selected' : ''} onClick={() => onFeedback?.(message.id, 'helpful')} aria-label="Helpful"><ThumbsUp size={11} /></button>
        <button type="button" className={message.feedback === 'not_helpful' ? 'selected' : ''} onClick={() => onFeedback?.(message.id, 'not_helpful')} aria-label="Not helpful"><ThumbsDown size={11} /></button>
      </div>}
    </>}
  </article>
}

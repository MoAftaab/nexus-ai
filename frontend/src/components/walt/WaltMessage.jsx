import { BellRing, CheckCircle2, ChevronRight, Clock3, Database, MapPin, Radio, Send, ShieldCheck, ThumbsDown, ThumbsUp, UserRound, X } from 'lucide-react'
import { Markdown } from '../Markdown'
import { WaltAgentFlow } from './WaltAgentFlow'

export function WaltMessage({ message, loading, architecture, onChoice, onConfirmAction, onDismissAction, onFeedback, onSelectAnomaly }) {
  const assistant = message.role === 'assistant'
  const action = message.action
  const thinkingPhase = message.loadingPhase || (message.trace?.length ? 'evidence' : 'routing')
  const thinkingCopy = {
    routing: 'Routing your question to the right WALT capability',
    evidence: 'Checking the official Hackathon SAP evidence',
    synthesizing: 'Comparing signals and preparing a grounded answer',
    verified: 'Verifying the response before it reaches you',
  }
  const phaseIndex = { routing: 0, evidence: 1, synthesizing: 2, verified: 2 }[thinkingPhase] ?? 0
  const thinkingAgents = ['Ingestion', 'Data quality', 'Anomaly', 'Correlation', 'Impact', 'Action', 'WALT']
  return <article className={`walt-chat-message ${message.role}`}>
    {assistant && loading && <div className="walt-thinking-card" role="status" aria-live="polite" aria-label="WALT is thinking">
      <div className="walt-thinking-beacon"><Sparkles size={13} /></div>
      <div className="walt-thinking-copy">
        <strong>WALT is thinking · 7 agents live</strong>
        <span>{thinkingCopy[thinkingPhase] || thinkingCopy.routing}</span>
      </div>
      <div className="walt-thinking-agents" aria-label="Seven WALT agents are working">
        {thinkingAgents.map((agent, index) => <span key={agent} style={{ '--thinking-agent-delay': `${index * 90}ms` }}><i />{agent}</span>)}
      </div>
      <div className="walt-thinking-steps" aria-hidden="true">
        {['Route', 'Evidence', 'Answer'].map((label, index) => <span className={index <= phaseIndex ? 'is-active' : ''} key={label}><i />{label}</span>)}
      </div>
      <div className="walt-thinking-progress" aria-hidden="true"><i style={{ '--thinking-progress': `${Math.max(18, (phaseIndex + 1) * 33)}%` }} /></div>
    </div>}
    {assistant && message.content
      ? <Markdown text={message.content} onCite={(id) => onSelectAnomaly?.({ id })} />
      : !assistant ? <p>{message.content}</p> : null}
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
      {message.trace?.length > 0 && !(message.trace.length === 1 && message.trace[0].agent === 'WALT') && <WaltAgentFlow trace={message.trace} architecture={architecture} streaming={loading} />}
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

import { useEffect, useRef } from 'react'
import { ArrowUp, ChevronDown, LockKeyhole, MessageSquarePlus, Minus, RefreshCw, Route, ShieldCheck, Sparkles, X } from 'lucide-react'
import { WaltMascot } from './WaltMascot'
import { WaltMessage } from './WaltMessage'

const fallbackQuestions = [
  'What needs attention first?',
  'Which control protects the most value?',
]

const activityCopy = {
  idle: 'Monitoring live operations',
  greeting: 'WALT is ready',
  listening: 'Listening to your question',
  thinking: 'Planning the evidence search',
  analysing: 'Analysing operational records',
  'walking-left': 'Moving to a safe position',
  'walking-right': 'Moving to a safe position',
  dragging: 'Repositioning WALT',
  waiting: 'Live operational evidence connected',
  speaking: 'Streaming a grounded response',
  success: 'Decision brief ready',
  warning: 'Priority risk requires attention',
  error: 'Evidence connection needs attention',
  review: 'Reviewing governed records',
  sleeping: 'Low-power watch mode',
  waking: 'WALT systems online',
}

export function WaltPanel({
  capabilities,
  closing,
  contextCards,
  error,
  input,
  lastQuestion,
  loading,
  messages,
  onClearChat,
  onClose,
  onCancel,
  onFeedback,
  onConfirmAction,
  onDismissAction,
  onInput,
  onInputBlur,
  onInputFocus,
  onMinimize,
  placement,
  requestActions,
  onRetry,
  onSend,
  riskCount,
  state,
}) {
  const messagesRef = useRef(null)
  const quickQuestions = capabilities?.question_starters?.length ? capabilities.question_starters.slice(0, 3) : fallbackQuestions
  const permittedActionLabels = new Map((capabilities?.permitted_actions || []).map((action) => [action.id, action.label]))
  const selectedPermissions = (requestActions || []).filter((action) => permittedActionLabels.has(action)).map((action) => permittedActionLabels.get(action))

  useEffect(() => {
    const element = messagesRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [messages, loading])

  return <section
    className={`walt-panel ${closing ? 'is-closing' : ''}`}
    data-compact={placement.height < 520}
    data-placement={placement.direction}
    style={{ left: `${placement.x}px`, top: `${placement.y}px`, width: `${placement.width}px`, height: `${placement.height}px` }}
    role="dialog"
    aria-modal="false"
    aria-label="WALT assistant"
  >
    <header className="walt-panel-header">
      <WaltMascot state={state} compact riskCount={riskCount} />
      <div className="walt-panel-identity">
        <strong>WALT</strong>
        <span>Warehouse Action &amp; Logistics Twin</span>
      </div>
      <div className="walt-panel-controls">
        <button className="walt-new-chat" type="button" disabled={loading} onClick={onClearChat} aria-label="Start a new WALT chat" title="Clear this conversation and start a new chat"><MessageSquarePlus size={14} /><span>New chat</span></button>
        <button type="button" onClick={onMinimize} aria-label="Minimize WALT"><Minus size={16} /></button>
        <button type="button" onClick={onClose} aria-label="Close WALT"><X size={16} /></button>
      </div>
    </header>

    <div className="walt-activity" data-state={state} aria-live="polite">
      <Sparkles size={12} /><span>{activityCopy[state] || activityCopy.idle}</span>
      {riskCount > 0 && <b>{riskCount} priority</b>}
    </div>

    <div className="walt-context-cards" aria-label="Live operational context">
      {contextCards.map((card) => <article key={card.id} data-tone={card.tone}>
        <span>{card.label}</span><strong>{card.value}</strong>
      </article>)}
    </div>

    {capabilities && <details className="walt-capability-guide" open={messages.length === 1}>
      <summary><span><Sparkles size={13} />What WALT can do for {capabilities.role_label}</span><ChevronDown size={13} /></summary>
      <div className="walt-capability-body">
        <div className="walt-capability-list">{capabilities.capabilities?.map((item) => <article key={item.id}><ShieldCheck size={13} /><div><strong>{item.label}</strong><p>{item.detail}</p></div></article>)}</div>
        <div className={`walt-escalation-scope ${capabilities.escalation?.available ? 'available' : ''}`}><Route size={14} /><div><strong>{capabilities.escalation?.available ? 'Escalation preparation available' : 'Escalation is role-scoped'}</strong><p>{capabilities.escalation?.detail}</p></div></div>
        <div className="walt-permission-scope"><LockKeyhole size={13} /><div><strong>Selected request permissions</strong><p>{selectedPermissions.length ? selectedPermissions.join(' · ') : 'No state-changing action is available for the selected request.'}</p></div></div>
        <small>{capabilities.disclaimer}</small>
      </div>
    </details>}

    <div className="walt-conversation" ref={messagesRef}>
      {messages.map((message, index) => <WaltMessage
        key={message.id || `${message.role}-${index}`}
        message={message}
        loading={loading && index === messages.length - 1}
        onChoice={(prompt) => onSend(prompt)}
        onConfirmAction={onConfirmAction}
        onDismissAction={onDismissAction}
        onFeedback={onFeedback}
      />)}
    </div>

    {messages.length === 1 && <div className="walt-quick-questions"><span className="walt-quick-label">Try asking WALT</span>
      {quickQuestions.map((question) => <button type="button" key={question} onClick={() => onSend(question)}>{question}<ArrowUp size={12} /></button>)}
    </div>}

    {error && <div className="walt-error" role="alert">
      <span>{error}</span>
      <button type="button" disabled={!lastQuestion || loading} onClick={onRetry}><RefreshCw size={12} />Retry</button>
    </div>}

    <form className="walt-chat-form" onSubmit={(event) => { event.preventDefault(); if (!loading) onSend() }}>
      <input
        value={input}
        onFocus={onInputFocus}
        onBlur={onInputBlur}
        onChange={(event) => onInput(event.target.value)}
        placeholder="Ask WALT about current operations…"
        aria-label="Ask WALT"
      />
      {loading
        ? <button type="button" className="cancel" onClick={onCancel} aria-label="Cancel WALT request"><span>Cancel</span><X size={15} /></button>
        : <button type="submit" disabled={!input.trim()} aria-label="Send to WALT"><span>Send</span><ArrowUp size={15} /></button>}
    </form>

    <footer className="walt-panel-footer">
      <p><ShieldCheck size={12} />Operational decisions must be verified by the responsible human approver.</p>
      <span>Popup conversation · stays on this page</span>
    </footer>
  </section>
}

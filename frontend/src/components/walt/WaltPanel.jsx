import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Bot, Database, MessageSquarePlus, Minus, Network, RefreshCw, ShieldCheck, Sparkles, X } from 'lucide-react'
import { WaltMascot } from './WaltMascot'
import { WaltMessage } from './WaltMessage'

const fallbackQuestions = [
  'What needs attention first?',
  'Which control protects the most value?',
  'Explain any master data or ATP risk',
]

const activityCopy = {
  idle: 'Monitoring live operations',
  greeting: 'WALT is ready',
  listening: 'Listening to your question',
  thinking: 'Planning the evidence search',
  analysing: 'Analysing operational records',
  'walking-left': 'Monitoring twin',
  'walking-right': 'Monitoring twin',
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

const HACKATHON_AGENTS = [
  { id: 'ingestion', name: 'Ingestion Agent', role: 'Data Ingestion & Normalisation', desc: 'Loads and normalises 6 Excel/SAP sheets, resolves keys, builds unified view.', status: 'connected' },
  { id: 'data_quality', name: 'Data-Quality Agent', role: 'Master Data Checks (A1–A6)', desc: 'Detects bad, missing, duplicate, and obsolete master data.', status: 'active' },
  { id: 'anomaly', name: 'Anomaly Agent', role: 'Operational Anomaly Detection (B1–F2)', desc: 'Detects inventory, bin, dispatch, PO, and vendor anomalies.', status: 'active' },
  { id: 'correlation', name: 'Correlation / Root-Cause Agent', role: 'Cross-System Linkage (X1–X2)', desc: 'Links related anomalies across systems and infers underlying cause (cascade tracing).', status: 'active' },
  { id: 'impact', name: 'Impact Agent', role: 'Impact & Prioritisation', desc: 'Scores business impact and prioritises worklist (€ exposure, P90 risk, scoring model).', status: 'active' },
  { id: 'remediation', name: 'Action / Remediation Agent', role: 'Action & Remediation', desc: 'Proposes fixes and routes for human approval (Change Control, Before/Proposed/After).', status: 'active' },
  { id: 'orchestrator', name: 'Orchestrator (WALT)', role: 'Multi-Agent Coordination', desc: 'Plans the flow, delegates to specialist agents, maintains immutable audit trail.', status: 'active' },
]

export function WaltPanel({
  capabilities,
  architecture,
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
  onSelectAnomaly,
  placement,
  requestActions,
  onRetry,
  onSend,
  riskCount,
  state,
}) {
  const [showAgents, setShowAgents] = useState(false)
  const messagesRef = useRef(null)
  const quickQuestions = capabilities?.question_starters?.length ? capabilities.question_starters.slice(0, 3) : fallbackQuestions

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
        <span>Warehouse Logistics Twin</span>
      </div>
      <div className="walt-panel-controls">
        <button
          className={`walt-agents-toggle ${showAgents ? 'active' : ''}`}
          type="button"
          onClick={() => setShowAgents((current) => !current)}
          aria-label="View 7 specialist agents"
          title="Inspect the 7 specialist agents"
        >
          <Bot size={13} />
          <span>7 Agents</span>
        </button>
        <button className="walt-new-chat" type="button" disabled={loading} onClick={onClearChat} aria-label="Start a new WALT chat" title="Clear this conversation and start a new chat">
          <MessageSquarePlus size={14} />
          <span>New</span>
        </button>
        <button type="button" onClick={onMinimize} aria-label="Minimize WALT" title="Minimize"><Minus size={16} /></button>
        <button type="button" onClick={onClose} aria-label="Close WALT" title="Close"><X size={16} /></button>
      </div>
    </header>

    <div className="walt-activity" data-state={state} aria-live="polite">
      <Sparkles size={12} />
      <span>{activityCopy[state] || activityCopy.idle}</span>
      <span className="walt-activity-pill">7 agents live</span>
      {riskCount > 0 && <b>{riskCount} priority</b>}
    </div>

    {showAgents && (
      <div className="walt-agents-modal">
        <div className="walt-agents-modal-header">
          <div className="walt-agents-modal-title">
            <Network size={14} />
            <strong>7 Multi-Agent Specialists</strong>
          </div>
          <button type="button" onClick={() => setShowAgents(false)} aria-label="Close agents roster"><X size={14} /></button>
        </div>
        <p className="walt-agents-modal-intro">
          WALT coordinates 7 specialist agents aligned to the Hackathon Architecture to inspect 6 SAP sheets and stage human-approved controls.
        </p>
        <div className="walt-agents-list">
          {HACKATHON_AGENTS.map((agent, index) => (
            <article key={agent.id} className="walt-agent-roster-card">
              <span className="walt-agent-num">{index + 1}</span>
              <div className="walt-agent-info">
                <div className="walt-agent-name-row">
                  <strong>{agent.name}</strong>
                  <span className="walt-agent-status-badge">{agent.status}</span>
                </div>
                <small className="walt-agent-role-tag">{agent.role}</small>
                <p>{agent.desc}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    )}

    <div className="walt-conversation" ref={messagesRef}>
      {messages.map((message, index) => <WaltMessage
        key={message.id || `${message.role}-${index}`}
        message={message}
        architecture={architecture}
        loading={loading && index === messages.length - 1}
        onChoice={(prompt) => onSend(prompt)}
        onConfirmAction={onConfirmAction}
        onDismissAction={onDismissAction}
        onFeedback={onFeedback}
        onSelectAnomaly={onSelectAnomaly}
      />)}
    </div>

    {messages.length === 1 && !loading && <div className="walt-quick-questions">
      <span className="walt-quick-label">Suggested questions</span>
      {quickQuestions.map((question) => <button type="button" key={question} onClick={() => onSend(question)}>
        <span>{question}</span>
        <ArrowUp size={12} />
      </button>)}
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
        placeholder="Ask WALT about operations, SAP sheets, or an anomaly…"
        aria-label="Ask WALT"
      />
      {loading
        ? <button type="button" className="cancel" onClick={onCancel} aria-label="Cancel WALT request"><span>Cancel</span><X size={15} /></button>
        : <button type="submit" disabled={!input.trim()} aria-label="Send to WALT"><span>Send</span><ArrowUp size={15} /></button>}
    </form>

    <footer className="walt-panel-footer">
      <p><ShieldCheck size={12} />Human-in-the-loop · Changes require human approval</p>
    </footer>
  </section>
}

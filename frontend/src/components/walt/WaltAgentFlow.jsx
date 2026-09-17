import { Check, ChevronDown, Network, Sparkles } from 'lucide-react'
import { agentPresentation } from '../../utils/agentLabels'

const HACKATHON_AGENTS = [
  { agent: 'Ingestion Agent', role: '6 SAP sheets' },
  { agent: 'Data-Quality Agent', role: 'Master data' },
  { agent: 'Anomaly Agent', role: 'B1–F2 signals', traceAgent: 'Sentinel' },
  { agent: 'Correlation / Root-Cause Agent', role: 'X1–X2 linkage', traceAgent: 'Correlator' },
  { agent: 'Impact Agent', role: '€ exposure', traceAgent: 'Impact' },
  { agent: 'Action / Remediation Agent', role: 'Human approval', traceAgent: 'Fix' },
  { agent: 'Orchestrator (WALT)', role: 'Decision brief', traceAgent: 'Control Tower' },
]

function agentTrace(trace = []) {
  const returned = new Map(trace.map((item) => [item.agent, item]))
  return HACKATHON_AGENTS.map((agent) => ({
    ...agent,
    ...(returned.get(agent.traceAgent) || returned.get(agent.agent) || {}),
  }))
}

export function WaltAgentFlow({ trace = [], streaming = false, architecture }) {
  const agents = agentTrace(trace)
  const hasTrace = trace.length > 0
  const knowledge = trace.find((item) => item.agent === 'Knowledge')
  const orchestrator = trace.find((item) => item.agent === 'Control Tower')
  const modelName = architecture?.model || trace
    .map((item) => item.detail?.match(/(?:gpt|llama|claude)[\w.:-]*/i)?.[0])
    .find(Boolean)
  const providerName = architecture?.provider_label ? `${architecture.provider_label} · ` : ''

  return <details className="walt-agent-flow">
    <summary>
      <span className="walt-agent-flow__icon"><Network size={12} /></span>
      <span><b>7-agent analysis</b><small>{hasTrace ? `${providerName}${modelName || 'Evidence mode'} · 7 agent handoffs complete` : `${providerName || ''}7 agents consulting in parallel`}</small></span>
      <ChevronDown className="walt-agent-flow__chevron" size={13} />
    </summary>
    <div className="walt-agent-flow__body">
      <div className="walt-agent-flow__specialists">
        {agents.map((item, index) => <div
          className={`walt-agent-chip ${item.status === 'degraded' ? 'is-degraded' : hasTrace ? 'is-done' : 'is-active'}`}
          style={{ '--agent-delay': `${index * 110}ms` }}
          key={item.agent}
          title={item.detail || `${agentPresentation(item.agent, item.role).role} specialist`}
        >
          <span>{hasTrace && item.status !== 'degraded' ? <Check size={9} strokeWidth={3} /> : index + 1}</span>
          <b>{agentPresentation(item.agent, item.role).name}</b>
          <small>{agentPresentation(item.agent, item.role).role}</small>
        </div>)}
      </div>
      <div className="walt-agent-handoff" aria-label="Specialists hand off evidence to the WALT Coordinator">
        <span className="walt-agent-handoff__line"><i /><i /><i /></span>
        <div className={streaming ? 'is-synthesizing' : 'is-complete'}>
          <Sparkles size={12} />
          <span><b>Orchestrator (WALT)</b><small>{streaming ? 'Synthesizing verified multi-agent answer' : 'Multi-agent answer synthesized'}</small></span>
        </div>
      </div>
      {(hasTrace || knowledge || orchestrator) && <p className="walt-agent-evidence">
        {knowledge?.detail || 'Role-curated operational evidence attached'}
        <span>•</span>
        {orchestrator?.detail || 'Specialist outputs merged by the orchestrator'}
      </p>}
    </div>
  </details>
}

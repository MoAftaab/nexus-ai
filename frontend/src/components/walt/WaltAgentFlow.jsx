import { Check, ChevronDown, Network, Sparkles } from 'lucide-react'
import { agentPresentation } from '../../utils/agentLabels'

const SPECIALISTS = [
  { agent: 'Sentinel' },
  { agent: 'Correlator' },
  { agent: 'Cascade' },
  { agent: 'Impact' },
  { agent: 'Fix' },
]

function specialistTrace(trace = []) {
  const returned = new Map(trace.map((item) => [item.agent, item]))
  return SPECIALISTS.map((specialist) => ({ ...specialist, ...returned.get(specialist.agent) }))
}

export function WaltAgentFlow({ trace = [], streaming = false }) {
  const specialists = specialistTrace(trace)
  const hasTrace = trace.length > 0
  const knowledge = trace.find((item) => item.agent === 'Knowledge')
  const orchestrator = trace.find((item) => item.agent === 'Control Tower')
  const completed = specialists.filter((item) => item.status && item.status !== 'degraded').length
  const modelName = trace
    .map((item) => item.detail?.match(/GPT-[\w.]+(?:\s+\w+)?/)?.[0])
    .find(Boolean)

  return <details className="walt-agent-flow" open={streaming}>
    <summary>
      <span className="walt-agent-flow__icon"><Network size={12} /></span>
      <span><b>Multi-agent analysis</b><small>{hasTrace ? `${modelName || 'Evidence mode'} · ${completed}/5 specialist handoffs` : '5 specialists consulting in parallel'}</small></span>
      <ChevronDown className="walt-agent-flow__chevron" size={13} />
    </summary>
    <div className="walt-agent-flow__body">
      <div className="walt-agent-flow__specialists">
        {specialists.map((item, index) => <div
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
          <span><b>WALT Coordinator</b><small>{streaming ? 'Combining one grounded answer' : 'Answer ready'}</small></span>
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

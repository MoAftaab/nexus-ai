import { useEffect, useState } from 'react'
import { Check, BrainCircuit } from 'lucide-react'

const fallbackSteps = [
  { name: 'Signal intake', detail: 'Parsing your question and attaching live context' },
  { name: 'Inventory', detail: 'Checking stock deltas and reconciliation records' },
  { name: 'Logistics', detail: 'Tracing dock, route and carrier dependencies' },
  { name: 'Documents', detail: 'Cross-checking extracted document evidence' },
  { name: 'Risk', detail: 'Scoring cascade exposure and deadlines' },
]

// Animated "mesh is thinking" steps shown inside the chat while the
// orchestrator prepares its first tokens. Uses the real specialist trace when
// the SSE trace event has arrived, else the roster, else a generic script.
// Real recent handoffs cycle underneath as overheard agent chatter.
export function AgentThinking({ agents, trace, communication }) {
  const steps = trace?.length
    ? trace.map((handoff) => ({ name: handoff.agent, detail: handoff.detail || handoff.role }))
    : agents?.length
      ? agents.map((agent) => ({ name: agent.name, detail: agent.role }))
      : fallbackSteps
  const all = [...steps, { name: 'Orchestrator', detail: 'Weighing specialist evidence into one recommendation' }]
  const [active, setActive] = useState(0)
  const [chatterIndex, setChatterIndex] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setActive((current) => Math.min(current + 1, all.length - 1)), 950)
    return () => window.clearInterval(timer)
  }, [all.length])
  useEffect(() => {
    if (!communication?.length) return
    const timer = window.setInterval(() => setChatterIndex((current) => current + 1), 1500)
    return () => window.clearInterval(timer)
  }, [communication?.length])
  const chatter = communication?.length ? communication[chatterIndex % communication.length] : null
  return <div className="agent-thinking" role="status" aria-label="Agents are reasoning">
    <span className="thinking-title"><BrainCircuit size={13} /> Mesh reasoning in progress</span>
    {all.map((step, index) => <div className={`thinking-row ${index < active ? 'done' : index === active ? 'active' : 'pending'}`} key={step.name + index}>
      <span className="thinking-orb">{index < active ? <Check size={9} strokeWidth={3} /> : <i />}</span>
      <div><strong>{step.name}</strong><small>{step.detail}</small></div>
      {index === active && <span className="thinking-dots"><span /><span /><span /></span>}
    </div>)}
    {chatter && <div className="thinking-chatter" key={chatterIndex}><b>{chatter.from}</b> → <b>{chatter.to}</b><span>“{chatter.message}”</span></div>}
  </div>
}

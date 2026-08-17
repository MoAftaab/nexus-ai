import { ArrowUpRight, Bot } from 'lucide-react'
import { agentPresentation } from '../utils/agentLabels'

export function AgentStatus({ agents, onOpen }) {
  return <section className="agent-status card-surface">
    <div className="section-title"><div><span className="eyebrow"><Bot size={14} /> AI operations mesh</span><h2>Specialists on watch</h2></div><button className="text-button" onClick={onOpen}>Open workspace <ArrowUpRight size={15} /></button></div>
    <div className="agent-row-list">
      {agents?.map((agent) => {
        const presentation = agentPresentation(agent.name, agent.role)
        return <div className="agent-row" key={agent.name}>
          <span className={`agent-orb ${agent.color}`}><i /></span><div><strong>{presentation.name}</strong><small>{presentation.role}</small></div><span className={`agent-state ${agent.state}`}>{agent.state}</span><p>{agent.signal}</p>
        </div>
      })}
    </div>
  </section>
}

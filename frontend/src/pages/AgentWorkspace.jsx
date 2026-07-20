import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Bot, BrainCircuit, CheckCheck, ChevronRight, LoaderCircle, Sparkles } from 'lucide-react'
import { Markdown } from '../components/Markdown'

const prompts = ["What needs attention first?", "What is the safest control to apply now?", "Show the evidence behind the inventory variance"]

export function AgentWorkspace({ agents, communication, onChatStream }) {
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'I’m connected to the live operational brief. Ask about a part, a cascade, a dock, or the safest control to apply.' }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef(null)
  // Scroll only the chat list; scrollIntoView would also scroll ancestor
  // containers (including the overflow-clipped app shell) and blank the page.
  useEffect(() => { const list = listRef.current; if (list) list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' }) }, [messages, loading])
  const send = async (prompt = input) => {
    const content = prompt.trim()
    if (!content || loading) return
    const history = messages.map(({ role, content: message }) => ({ role, content: message }))
    setMessages((current) => [...current, { role: 'user', content }]); setInput(''); setLoading(true)
    const assistantIndex = messages.length + 1
    setMessages((current) => [...current, { role: 'assistant', content: '', source: 'streaming', suggestions: [], trace: [] }])
    try {
      await onChatStream({ message: content, history }, (event, payload) => {
        setMessages((current) => current.map((item, index) => {
          if (index !== assistantIndex) return item
          if (event === 'trace') return { ...item, trace: payload }
          if (event === 'delta') return { ...item, content: item.content + payload.text }
          if (event === 'done') return { ...item, ...payload, suggestions: payload.suggested_actions || [] }
          return item
        }))
      })
    }
    catch (error) {
      setMessages((current) => current.map((item, index) => index === assistantIndex
        ? { ...item, source: 'nexus_deterministic', content: `I could not reach the intelligence layer: ${error.message}` }
        : item))
    }
    finally { setLoading(false) }
  }
  return <div className="page agents-page">
    <section className="page-lead"><div><span className="eyebrow"><BrainCircuit size={14} /> Agent collaboration layer</span><h2>Ask the mesh. Get a decision.</h2><p>Specialists validate facts first; the OpenAI reasoning layer turns their evidence into an explainable operational recommendation.</p></div><span className="mesh-live"><i />Live context attached</span></section>
    <section className="agent-workspace-layout"><aside className="agent-roster card-surface"><div className="section-title"><div><span className="eyebrow"><Bot size={14} /> The mesh</span><h3>Specialist agents</h3></div></div>{agents?.map((agent) => <div className="roster-agent" key={agent.name}><span className={`agent-orb ${agent.color}`}><i /></span><div><strong>{agent.name}</strong><small>{agent.role}</small></div><span>{agent.state}</span></div>)}<div className="handoff-trace"><span>Recent handoffs</span>{communication?.map((event) => <div key={`${event.from}-${event.time}`}><i /><p><b>{event.from}</b> → <b>{event.to}</b><small>{event.message}</small></p><time>{event.time}</time></div>)}</div></aside>
      <article className="chat-shell card-surface"><div className="chat-header"><div><span className="eyebrow"><Sparkles size={14} /> Nexus copilot</span><h3>Operations reasoning</h3></div><span className="chat-status"><i />Streaming</span></div><div className="message-list" ref={listRef}>{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar">{message.role === 'assistant' ? <Sparkles size={15} /> : 'AM'}</span><div>{message.role === 'assistant' && message.content ? <div className="message-bubble"><Markdown text={message.content} /></div> : <p>{message.content || (message.source === 'streaming' ? 'Preparing specialist handoffs…' : '')}</p>}{message.source && message.source !== 'streaming' && <small className="model-source">{message.source === 'openai' ? 'Five GPT-5.4 mini specialists + orchestrator' : 'Evidence mode — enable GPT-5.4 mini with a server-side key'}</small>}{message.trace?.length ? <details className="agent-trace"><summary>{message.trace.length} agent handoffs and Markdown context</summary>{message.trace.map((handoff) => <div key={`${handoff.agent}-${handoff.role}`}><b>{handoff.agent}</b><span>{handoff.role} · {handoff.status}</span><small>{handoff.detail}</small></div>)}</details> : null}{message.suggestions?.length ? <div className="suggestion-actions"><span className="suggestion-label">Ask a follow-up</span>{message.suggestions.map((suggestion) => <button key={suggestion} onClick={() => send(`Walk me through this control before I approve it: "${suggestion}". What are the steps, risks and verification?`)}>{suggestion}<ChevronRight size={13} /></button>)}</div> : null}</div></div>)}{loading && <div className="message assistant loading"><span className="message-avatar"><Sparkles size={15} /></span><div><LoaderCircle className="spin" size={18} /><span>Reviewing specialist evidence and Markdown controls…</span></div></div>}</div><div className="suggested-prompts">{prompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)}>{prompt}</button>)}</div><form className="chat-input" onSubmit={(event) => { event.preventDefault(); send() }}><textarea value={input} onChange={(event) => setInput(event.target.value)} rows="1" placeholder="Ask Nexus about the operation…" /><button className="send-button" disabled={!input.trim() || loading} aria-label="Send message"><ArrowUp size={18} /></button></form></article>
    </section>
    <section className="ai-principle"><CheckCheck size={18} /><p><b>Human-controlled operations.</b> Nexus can recommend and prepare corrective controls; an operator approves every operational change.</p></section>
  </div>
}

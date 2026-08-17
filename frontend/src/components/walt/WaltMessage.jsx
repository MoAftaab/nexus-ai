import { Database, Radio } from 'lucide-react'
import { Markdown } from '../Markdown'
import { WaltAgentFlow } from './WaltAgentFlow'

export function WaltMessage({ message, loading }) {
  const assistant = message.role === 'assistant'
  const hasAgentFlow = assistant && (loading || message.trace?.length > 0)
  return <article className={`walt-chat-message ${message.role} ${hasAgentFlow ? 'has-agent-flow' : ''}`}>
    {assistant && loading && <WaltAgentFlow trace={message.trace} streaming />}
    {assistant && !message.content && loading
      ? <div className="walt-typing" aria-label="WALT is processing"><i /><i /><i /><span>Reviewing live evidence</span></div>
      : assistant
        ? <Markdown text={message.content || ''} />
        : <p>{message.content}</p>}
    {assistant && message.content && <>
      {message.trace?.length > 0 && !loading && <WaltAgentFlow trace={message.trace} />}
      <footer>
        {message.source === 'openai' ? <Radio size={11} /> : <Database size={11} />}
        <span>{message.source === 'openai' ? '5 specialist agents + Control Tower synthesis' : 'Operational evidence'}</span>
      </footer>
    </>}
  </article>
}

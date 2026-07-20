import { Fragment } from 'react'

// Bold matches lazily across any content (so nested italics stay inside it);
// bare italic/code match unnested runs. Order matters: ** before *.
const inlinePattern = /(\*\*.+?\*\*|\*[^*\n]+\*|`[^`]+`)/g

function Inline({ text }) {
  return text.split(inlinePattern).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      const inner = part.slice(2, -2)
      // LLM output nests italics inside bold ("**bold *emph* rest**").
      return <strong key={index}><Inline text={inner} /></strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={index}>{part.slice(1, -1)}</em>
    return <Fragment key={index}>{part}</Fragment>
  })
}

/** Minimal chat-message markdown: headings, bullets, bold/italic/code. */
export function Markdown({ text }) {
  const blocks = []
  let bullets = null
  const flush = () => { if (bullets) { blocks.push({ type: 'list', items: bullets }); bullets = null } }
  for (const raw of (text || '').split('\n')) {
    const line = raw.trimEnd()
    const bullet = line.match(/^\s*[-•]\s+(.*)/)
    const heading = line.match(/^(#{1,4})\s+(.*)/)
    const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)/)
    if (bullet) { (bullets ||= []).push(bullet[1]) }
    else if (numbered) { flush(); blocks.push({ type: 'numbered', marker: numbered[1], text: numbered[2] }) }
    else if (heading) { flush(); blocks.push({ type: 'heading', text: heading[2] }) }
    else if (line.trim()) { flush(); blocks.push({ type: 'paragraph', text: line }) }
    else flush()
  }
  flush()
  return <div className="chat-markdown">
    {blocks.map((block, index) => {
      if (block.type === 'list') return <ul key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}><Inline text={item} /></li>)}</ul>
      if (block.type === 'numbered') return <p className="numbered" key={index}><b>{block.marker}.</b> <Inline text={block.text} /></p>
      if (block.type === 'heading') return <h4 key={index}><Inline text={block.text} /></h4>
      return <p key={index}><Inline text={block.text} /></p>
    })}
  </div>
}

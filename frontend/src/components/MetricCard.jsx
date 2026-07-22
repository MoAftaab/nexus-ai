import { ArrowDownRight, ArrowUpRight, ShieldCheck } from 'lucide-react'
import { currency, number } from '../utils'

export function MetricCard({ metric, index, scanning = false }) {
  const value = metric.format === 'currency' ? currency(metric.value) : metric.format === 'percent' ? `${metric.value}%` : number(metric.value)
  const positive = metric.tone === 'good'
  return <article className={`metric-card tone-${metric.tone} ${scanning ? 'discovering' : ''}`} style={{ '--delay': `${index * 80}ms`, '--discover-delay': `${index * 320}ms` }}>
    <div className="metric-card-top"><span>{metric.label}</span><div className="metric-icon">{positive ? <ShieldCheck size={17} /> : <span className="metric-sigil" />}</div></div>
    <strong>{value}</strong>
    <p className={positive ? 'positive' : ''}>{positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}{metric.trend}</p>
  </article>
}


import { ArrowUpRight, BadgeEuro, Gauge, ShieldAlert, ShieldCheck } from 'lucide-react'
import { currency, number } from '../utils'

export function MetricCard({ metric, index, scanning = false }) {
  const value = metric.format === 'currency' ? currency(metric.value) : metric.format === 'percent' ? `${metric.value}%` : number(metric.value)
  const positive = metric.tone === 'good'
  const Icon = metric.label === 'Exposure at risk'
    ? BadgeEuro
    : metric.label === 'Critical interventions'
      ? ShieldAlert
      : metric.label === 'Line readiness'
        ? Gauge
        : ShieldCheck
  return <article className={`metric-card tone-${metric.tone} ${scanning ? 'discovering' : ''}`} style={{ '--delay': `${index * 80}ms`, '--discover-delay': `${index * 320}ms` }}>
    <div className="metric-accent" aria-hidden="true" />
    <div className="metric-card-top"><span>{metric.label}</span><div className="metric-icon"><Icon size={13} /></div></div>
    <strong>{value}</strong>
    <small>{metric.detail}</small>
    <p className={positive ? 'positive' : ''}><ArrowUpRight size={11} />{metric.trend}</p>
  </article>
}

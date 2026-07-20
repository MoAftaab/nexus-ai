import { useMemo, useState } from 'react'
import { ArrowDownUp, Filter, Search, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { currency, severityLabel } from '../utils'

export function RiskIntelligence({ anomalies, onSelectAnomaly }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const visible = useMemo(() => (anomalies || []).filter((item) => {
    // The decision queue holds open work; contained findings live behind their own filter.
    if (filter === 'contained') return item.status === 'resolved'
    if (item.status === 'resolved') return false
    return (filter === 'all' || item.severity === filter) && `${item.title} ${item.sku} ${item.system}`.toLowerCase().includes(query.toLowerCase())
  }), [anomalies, filter, query])
  const containedCount = useMemo(() => (anomalies || []).filter((item) => item.status === 'resolved').length, [anomalies])
  return <div className="page intelligence-page">
    <section className="page-lead"><div><span className="eyebrow"><ShieldCheck size={14} /> Decision queue</span><h2>Ranked by what the line stands to lose.</h2><p>Each risk is scored from source confidence, cascade probability, time to impact, and preventable euro exposure.</p></div><div className="leaderboard-total"><span>{filter === 'contained' ? 'Exposure removed' : 'Open exposure'}</span><strong>{currency(visible.reduce((total, item) => total + item.impact, 0))}</strong></div></section>
    <section className="toolbar card-surface"><label className="table-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find part, system or anomaly…" /></label><div className="filter-set" role="group" aria-label="Filter by severity">{['all', 'critical', 'high', 'medium', 'low'].map((item) => <button className={filter === item ? 'active' : ''} key={item} onClick={() => setFilter(item)}>{item === 'all' ? 'All findings' : severityLabel(item)}</button>)}<button className={filter === 'contained' ? 'active contained-filter' : 'contained-filter'} onClick={() => setFilter('contained')}>Contained{containedCount > 0 ? ` · ${containedCount}` : ''}</button></div><button className="soft-button"><SlidersHorizontal size={16} />Filters</button></section>
    <section className="risk-table card-surface"><div className="risk-table-head"><span>Finding</span><span>Systems</span><span>Time to impact</span><span>Exposure <ArrowDownUp size={13} /></span><span>Control</span></div><div className="risk-table-body">{visible.map((item, index) => <button className={`risk-row ${item.status === 'resolved' ? 'contained-row' : ''}`} key={item.id} onClick={() => onSelectAnomaly(item)}><span className="risk-title"><i>0{index + 1}</i><span className={`severity-mark ${item.status === 'resolved' ? 'resolved' : item.severity}`} /><span><strong>{item.title}</strong><small>{item.id} · {item.sku} · {item.zone}</small></span></span><span className="system-tags">{item.system.split(' · ').map((system) => <em key={system}>{system}</em>)}</span><span className="deadline">{item.status === 'resolved' ? 'Contained' : item.time_to_impact}</span><strong className="impact-number">{currency(item.impact)}</strong><span className="control-preview"><b>{item.status === 'resolved' ? '✓ resolved' : `${item.actions[0]?.confidence}%`}</b><small>{item.actions[0]?.title}</small></span></button>)}</div>{visible.length === 0 && <div className="empty-state"><Filter size={24} />{filter === 'contained' ? <><h3>Nothing contained yet</h3><p>Approve every control on a finding and it moves here with its value.</p></> : <><h3>No open risks match this view</h3><p>The board is clear — change a filter, run a scan, or check Contained.</p></>}</div>}</section>
  </div>
}


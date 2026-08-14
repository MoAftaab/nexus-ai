import { useMemo } from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { ArrowUpRight, CircleAlert, Play, Radio, ScanLine, Sparkles } from 'lucide-react'
import { AgentStatus } from '../components/AgentStatus'
import { CascadeGraph, CascadeLegend, CascadeSummary } from '../components/CascadeGraph'
import { MetricCard } from '../components/MetricCard'
import { currency, timeAgo } from '../utils'

export function CommandCenter({ dashboard, workflow, anomalies, graph, onNavigate, onSelectAnomaly, onScan, scanning }) {
  // Resolved findings stay in the payload for containment accounting; every
  // "act on this" surface shows open work only.
  const open = useMemo(() => anomalies?.filter((item) => item.status !== 'resolved') || [], [anomalies])
  const primary = open[0]
  const critical = useMemo(() => open.filter((item) => item.severity === 'critical'), [open])
  return <div className="page command-page">
    <section className="command-hero">
      <div className="hero-copy"><span className="live-chip"><Radio size={13} />Live operational twin</span><h2>Keep every part of the line <em>in flow.</em></h2><p>Warehouse Control Tower AI maps small data defects to their downstream production impact before the shift feels them.</p></div>
      <div className="hero-actions"><span className="scan-state"><span className="pulse-dot" />Last scan {dashboard?.last_scan ? timeAgo(dashboard.last_scan) : 'now'}</span><button className="primary-button" onClick={onScan} disabled={scanning}><ScanLine size={16} />{scanning ? 'Scanning mesh…' : 'Run intelligence scan'}</button></div>
    </section>
    <section className={`metrics-grid ${scanning ? 'scanning' : ''}`}>{dashboard?.metrics?.map((metric, index) => <MetricCard metric={metric} index={index} scanning={scanning} key={metric.label} />)}{scanning && <span className="radar-sweep" aria-hidden="true" />}</section>
    {workflow && <section className="workflow-strip card-surface"><div><span>My decision queue</span><strong>{workflow.awaiting_my_decision}</strong></div><div><span>Value awaiting approval</span><strong>{currency(workflow.value_awaiting_approval)}</strong></div><div><span>Verified value protected</span><strong>{currency(workflow.verified_value_protected)}</strong></div><button className="text-button" onClick={() => onNavigate('changes')}>Open change ledger <ArrowUpRight size={15} /></button></section>}
    <section className="command-grid">
      <article className="map-card card-surface"><div className="section-title"><div><span className="eyebrow"><Sparkles size={14} /> Cascade intelligence</span><h2>What breaks next</h2></div><button className="text-button" onClick={() => onNavigate('cascade')}>Expand map <ArrowUpRight size={15} /></button></div>
        <div className="map-stage"><CascadeGraph graph={graph} compact onSelect={(node) => onSelectAnomaly({ id: node.anomaly_id || primary?.id })} /><CascadeSummary anomaly={primary} onExplore={() => onNavigate('cascade')} /></div><CascadeLegend />
      </article>
      <aside className="risk-queue card-surface"><div className="section-title"><div><span className="eyebrow"><CircleAlert size={14} /> Prioritized queue</span><h2>Fix before impact</h2></div><span className="queue-count">{open.length}</span></div>
        <div className="queue-list">{open.slice(0, 4).map((anomaly, index) => <button className="queue-item" key={anomaly.id} onClick={() => onSelectAnomaly(anomaly)}><span className={`queue-rank ${anomaly.severity}`}>0{index + 1}</span><div><strong>{anomaly.title}</strong><small>{anomaly.system} · {anomaly.time_to_impact}</small></div><span>{currency(anomaly.impact)}</span></button>)}</div>
        {open.length === 0 && <div className="queue-clear"><Sparkles size={17} /><strong>Every finding is contained.</strong><small>Run a scan or inject a live incident to give the mesh new work.</small></div>}
        <button className="quiet-button" onClick={() => onNavigate('intelligence')}>View all risks <ArrowUpRight size={15} /></button>
      </aside>
    </section>
    <section className="lower-grid">
      <AgentStatus agents={dashboard?.agents} onOpen={() => onNavigate('agents')} />
      <article className="exposure-card card-surface"><div className="section-title"><div><span className="eyebrow"><Play size={14} /> Shift forecast</span><h2>Exposure trajectory</h2></div><span className="chart-change">ML F1 {(dashboard?.ml_model?.f1 || 0) * 100}%</span></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={dashboard?.exposure_trend || []} margin={{ top: 8, right: 0, left: -30, bottom: 0 }}><defs><linearGradient id="exposure" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f0daa0" stopOpacity=".55" /><stop offset="100%" stopColor="#f0daa0" stopOpacity="0" /></linearGradient></defs><XAxis dataKey="h" axisLine={false} tickLine={false} tick={{ fill: '#b9a672', fontSize: 11 }} /><Tooltip cursor={{ stroke: '#f0daa0', strokeDasharray: '3 3' }} contentStyle={{ background: '#292347', border: '1px solid #82703f', borderRadius: 10 }} labelStyle={{ color: '#f5f3ed' }} /><Area type="monotone" dataKey="v" stroke="#f5f3ed" strokeWidth={2.5} fill="url(#exposure)" /></AreaChart></ResponsiveContainer></div><p><span className="pulse-dot" />Selected detector: {dashboard?.ml_model?.name?.replaceAll('_', ' ') || 'loading'} · accuracy {(dashboard?.ml_model?.accuracy || 0) * 100}%.</p></article>
    </section>
    {critical.length > 0 && <section className="contained-note"><span>System note</span><p><b>{critical.length} critical paths</b> are receiving active monitoring. Run a scan after applying a control to update the cascade forecast.</p></section>}
  </div>
}

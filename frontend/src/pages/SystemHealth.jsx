import { useEffect, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Cpu, Database, Gauge, RefreshCw, Server, Sparkles, XCircle } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { number, timeAgo } from '../utils'

const METRIC_KEYS = ['f1', 'accuracy', 'precision', 'recall']
const pct = (value) => `${(value * 100).toFixed(1)}%`
const modelLabel = (name) => (name || '').replaceAll('_', ' ')

const chartTheme = {
  tick: { fill: 'rgba(140,190,230,0.6)', fontSize: 10 },
  tooltip: { background: '#002733', border: '1px solid rgba(140,190,230,0.35)', borderRadius: 10 },
}

export function SystemHealth() {
  const [system, setSystem] = useState(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const load = async () => {
    setRefreshing(true)
    try { setSystem(await api.system()); setError('') }
    catch (cause) { setError(cause.message) }
    finally { setRefreshing(false) }
  }
  useEffect(() => { load() }, [])
  if (error) return <div className="page"><section className="card-surface empty-state"><XCircle size={22} /><h3>System endpoint unreachable</h3><p>{error}</p></section></div>
  if (!system) return <div className="page"><section className="card-surface empty-state"><Gauge size={22} /><h3>Measuring system health…</h3><p>Benchmarks, endpoint probes and score distributions are loading.</p></section></div>
  const { model, llm, endpoints = [], runtime, api: apiState } = system
  const benchmark = (model.candidates?.length ? model.candidates : [model]).map((candidate) => ({ ...candidate, label: modelLabel(candidate.name) }))
  return <div className="page system-page">
    <section className="page-lead"><div><span className="eyebrow"><Cpu size={14} /> Runtime observability</span><h2>Every model and endpoint, measured.</h2><p>The detector benchmark that selected the live model, real response times for each API surface, and the score distribution behind the inventory findings.</p></div>
      <button className="soft-button" onClick={load} disabled={refreshing}><RefreshCw size={15} className={refreshing ? 'spin' : ''} />Re-probe</button></section>

    <section className="outcome-stats">
      <div className="outcome-stat card-surface"><Server size={17} /><div><strong className={apiState?.status === 'healthy' ? '' : 'status-bad'}>{apiState?.status}</strong><span>API · checked {timeAgo(apiState?.checked_at)}</span></div></div>
      <div className="outcome-stat card-surface"><BrainCircuit size={17} /><div><strong>{modelLabel(model.name)}</strong><span>Selected detector · F1 {pct(model.f1)}</span></div></div>
      <div className="outcome-stat card-surface"><Sparkles size={17} /><div><strong>{llm.enabled ? llm.model : 'evidence mode'}</strong><span>{llm.enabled ? `${llm.specialists} specialists live` : 'No LLM key configured'}</span></div></div>
      <div className="outcome-stat card-surface"><Database size={17} /><div><strong>{number(runtime.records)}</strong><span>Twin records · {runtime.database} · seed {runtime.dataset_seed}</span></div></div>
    </section>

    <section className="system-grid">
      <article className="card-surface system-card">
        <div className="section-title"><div><span className="eyebrow"><BrainCircuit size={14} /> Detector benchmark</span><h3>Why {modelLabel(model.name)} is live</h3></div><span className="system-note">{model.validation} · {number(model.training_records)} labeled records</span></div>
        <div className="chart-wrap tall"><ResponsiveContainer width="100%" height="100%">
          <BarChart data={benchmark} margin={{ top: 12, right: 8, left: -22, bottom: 0 }} barGap={2}>
            <CartesianGrid stroke="rgba(140,190,230,0.07)" vertical={false} />
            <XAxis dataKey="label" axisLine={false} tickLine={false} tick={chartTheme.tick} />
            <YAxis domain={[0, 1]} tickFormatter={(value) => `${value * 100}%`} axisLine={false} tickLine={false} tick={chartTheme.tick} />
            <Tooltip cursor={{ fill: 'rgba(140,190,230,0.06)' }} contentStyle={chartTheme.tooltip} labelStyle={{ color: '#F5FBFC' }} formatter={(value, key) => [pct(value), key]} />
            {METRIC_KEYS.map((key, index) => <Bar key={key} dataKey={key} radius={[3, 3, 0, 0]} fill={['#FAAA3C', '#8CBEE6', '#008C82', '#E67364'][index]}>
              {benchmark.map((candidate) => <Cell key={candidate.name} opacity={candidate.selected ? 1 : .45} />)}
            </Bar>)}
          </BarChart>
        </ResponsiveContainer></div>
        <p className="system-footnote">All three candidates train on the same temporal split; the highest F1 wins because faults are rare and accuracy alone would reward calling everything normal. Dimmed bars are the passed-over candidates.</p>
      </article>

      <article className="card-surface system-card">
        <div className="section-title"><div><span className="eyebrow"><Activity size={14} /> API surface</span><h3>Endpoint probes</h3></div><span className="system-note">measured in-process just now</span></div>
        <div className="endpoint-list">{endpoints.map((check) => <div key={check.endpoint} className="endpoint-row">
          {check.status === 'healthy' ? <CheckCircle2 size={14} className="ok" /> : <XCircle size={14} className="bad" />}
          <code>{check.endpoint}</code>
          <span className="latency-bar"><i style={{ width: `${Math.min(100, check.latency_ms / 3)}%` }} /></span>
          <b>{check.latency_ms} ms</b>
        </div>)}</div>
        <p className="system-footnote">WebSocket stream at <code>{apiState?.websocket}</code> · scan #{number(runtime.scan_count)} · last scan {timeAgo(runtime.last_scan)}</p>
      </article>
    </section>

    <section className="system-grid">
      <article className="card-surface system-card">
        <div className="section-title"><div><span className="eyebrow"><Gauge size={14} /> Score distribution</span><h3>{number(model.scored_positions)} positions scored · {model.flagged_over_50} flagged ≥ .5</h3></div></div>
        <div className="chart-wrap tall"><ResponsiveContainer width="100%" height="100%">
          <BarChart data={system.score_distribution} margin={{ top: 12, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid stroke="rgba(140,190,230,0.07)" vertical={false} />
            <XAxis dataKey="bucket" axisLine={false} tickLine={false} tick={chartTheme.tick} label={{ value: 'anomaly score', position: 'insideBottom', offset: -2, fill: 'rgba(140,190,230,0.6)', fontSize: 9 }} />
            <YAxis scale="sqrt" axisLine={false} tickLine={false} tick={chartTheme.tick} />
            <Tooltip cursor={{ fill: 'rgba(140,190,230,0.06)' }} contentStyle={chartTheme.tooltip} labelStyle={{ color: '#F5FBFC' }} formatter={(value) => [number(value), 'positions']} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>{system.score_distribution.map((bucket, index) => <Cell key={bucket.bucket} fill={index >= 5 ? '#C2FE06' : '#003845'} />)}</Bar>
          </BarChart>
        </ResponsiveContainer></div>
        <p className="system-footnote">Square-root axis so the rare high-score tail stays visible next to {number(model.scored_positions)} healthy positions. Features: {model.features.join(', ')}.</p>
      </article>

      <article className="card-surface system-card">
        <div className="section-title"><div><span className="eyebrow"><Database size={14} /> Highest ML scores</span><h3>Positions the detector is watching</h3></div></div>
        <div className="score-table">
          <div className="score-head"><span>Position</span><span>SKU · zone</span><span>WMS</span><span>ERP</span><span>Physical</span><span>Score</span></div>
          {system.top_scored.map((row) => <div key={row.id} className="score-row">
            <code>{row.id}</code>
            <span className="score-sku">{row.sku}<small>{row.zone}</small></span>
            <b>{number(row.wms)}</b><b>{number(row.erp)}</b><b>{number(row.physical)}</b>
            <span className={`score-chip ${row.score >= .5 ? 'hot' : ''}`}>{(row.score * 100).toFixed(1)}%</span>
          </div>)}
        </div>
        <p className="system-footnote">Scores feed the Inventory reconciliation detector: a finding needs both a ≥25-unit spread and a model score ≥ .5, so statistical noise alone never pages an operator.</p>
      </article>
    </section>
  </div>
}

import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, ChevronsRight, CircleAlert, FlaskConical, LoaderCircle, Route, ShieldCheck, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import { CascadeGraph, CascadeLegend } from '../components/CascadeGraph'
import { Markdown } from '../components/Markdown'
import { api } from '../api'
import { currency } from '../utils'

function WhatIfPanel({ anomaly, onClose }) {
  const [scenarios, setScenarios] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setScenarios(null); setError('')
    Promise.all(anomaly.actions.map((action) => api.whatif(anomaly.id, action.id)))
      .then((results) => { if (!cancelled) setScenarios(results) })
      .catch((cause) => { if (!cancelled) setError(cause.message) })
    return () => { cancelled = true }
  }, [anomaly])
  return <div className="whatif-panel card-surface">
    <div className="whatif-head"><span className="eyebrow"><FlaskConical size={13} /> What-if simulation</span><button className="icon-button" onClick={onClose} aria-label="Close scenario panel"><X size={14} /></button></div>
    {error && <p className="whatif-error">{error}</p>}
    {!scenarios && !error && <div className="whatif-loading"><LoaderCircle className="spin" size={16} />Re-running Monte-Carlo with each control applied…</div>}
    {scenarios?.map((scenario) => <div key={scenario.action.id} className="whatif-scenario">
      <strong><ShieldCheck size={13} /> {scenario.action.title}</strong>
      <small>{scenario.action.owner} · ETA {scenario.action.eta} · confidence {scenario.action.confidence}%</small>
      <div className="whatif-compare">
        <div><span>Without control</span><b className="bad">{currency(scenario.baseline.expected_impact)}</b><small>{Math.round(scenario.baseline.propagation_probability * 100)}% propagation</small></div>
        <ChevronsRight size={15} />
        <div><span>Control applied</span><b className="good">{currency(scenario.mitigated.expected_impact)}</b><small>{Math.round(scenario.mitigated.propagation_probability * 100)}% propagation</small></div>
      </div>
      <div className="whatif-delta">Expected exposure avoided: <b>{currency(scenario.expected_impact_avoided)}</b></div>
    </div>)}
    <p className="system-footnote">Each scenario damps every edge's propagation probability by the control's residual risk and re-runs the same 1,000-trial simulation shown in the ribbon. Applying a control for real still requires approval in the control plan.</p>
  </div>
}

export function CascadeMap({ anomalies, graph, onLoadGraph, onSelectAnomaly }) {
  const open = (anomalies || []).filter((item) => item.status !== 'resolved')
  const [selected, setSelected] = useState(() => open[0]?.id || '')
  const [showWhatIf, setShowWhatIf] = useState(false)
  const [explanation, setExplanation] = useState(null) // null | {text, streaming}
  useEffect(() => {
    // Keep the selection valid: first open finding, and never a resolved one.
    if (open.length === 0) { if (selected) setSelected(''); return }
    if (!selected || !open.some((item) => item.id === selected)) setSelected(open[0].id)
  }, [anomalies, selected]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (selected) onLoadGraph(selected); setShowWhatIf(false); setExplanation(null) }, [selected, onLoadGraph])
  const active = open.find((item) => item.id === selected)
  const explain = useCallback(async () => {
    if (!selected) return
    setExplanation({ text: '', streaming: true })
    try {
      await api.explainCascade(selected, (event, payload) => {
        if (event === 'delta') setExplanation((current) => ({ text: (current?.text || '') + payload.text, streaming: true }))
        if (event === 'done') setExplanation((current) => ({ text: current?.text || '', streaming: false }))
      })
    } catch (cause) { setExplanation({ text: `The narrator is unavailable: ${cause.message}`, streaming: false }) }
  }, [selected])
  return <div className="page cascade-page">
    <section className="page-lead"><div><span className="eyebrow"><Route size={14} /> Operational dependency twin</span><h2>Trace the path from a signal to a stop.</h2><p>Every edge carries a modeled propagation probability. Click a node to inspect its operational consequence.</p></div><button className={`soft-button ${showWhatIf ? 'active-tool' : ''}`} onClick={() => setShowWhatIf((open) => !open)} disabled={!active?.actions?.length}><SlidersHorizontal size={16} />Scenario controls</button></section>
    <section className="cascade-layout"><aside className="cascade-picker card-surface"><div className="section-title"><div><span className="eyebrow"><CircleAlert size={14} /> Active sources</span><h3>Cascade inputs</h3></div><span>{open.length}</span></div><div className="source-list">{open.map((item) => <button key={item.id} className={`source-item ${selected === item.id ? 'selected' : ''}`} onClick={() => setSelected(item.id)}><span className={`source-health ${item.severity}`} /><div><strong>{item.title}</strong><small>{item.id} · {item.time_to_impact}</small></div><ChevronsRight size={16} /></button>)}{open.length === 0 && <div className="queue-clear"><ShieldCheck size={17} /><strong>All cascades contained.</strong><small>Inject a live incident or run a scan to trace a new path.</small></div>}</div></aside>
      <article className="full-map card-surface"><div className="full-map-header"><div><span className={`severity-pill ${active?.severity}`}>{active?.severity}</span><h3>{active?.title || 'Select a cascade'}</h3></div>{active && <div className="impact-stack"><span>Modeled exposure</span><strong>{currency(active.impact)}</strong></div>}</div>{graph?.simulation && <div className="simulation-ribbon"><span><b>{Math.round(graph.simulation.propagation_probability * 100)}%</b> propagation probability</span><span><b>{currency(graph.simulation.expected_impact)}</b> expected exposure</span><span><b>{currency(graph.simulation.p90_impact)}</b> P90 exposure</span><small>{graph.simulation.trials.toLocaleString()} Monte-Carlo trials</small><button className="text-button" onClick={explain} disabled={explanation?.streaming}><Sparkles size={13} />{explanation?.streaming ? 'Narrating…' : 'Explain this cascade'}</button></div>}
        {explanation && <div className="cascade-narration">{explanation.text ? <Markdown text={explanation.text} /> : <span className="whatif-loading"><LoaderCircle className="spin" size={14} />Reading the graph…</span>}{!explanation.streaming && <button className="icon-button narration-close" onClick={() => setExplanation(null)} aria-label="Dismiss explanation"><X size={13} /></button>}</div>}
        <div className="map-with-panel">
          <CascadeGraph graph={graph} onSelect={(node) => node.anomaly_id && onSelectAnomaly({ id: node.anomaly_id })} />
          {showWhatIf && active && <WhatIfPanel anomaly={active} onClose={() => setShowWhatIf(false)} />}
        </div>
        <div className="map-bottom"><CascadeLegend />{active && <button className="primary-button" onClick={() => onSelectAnomaly(active)}>Open control plan <ArrowLeft size={15} className="arrow-right" /></button>}</div></article>
    </section>
  </div>
}

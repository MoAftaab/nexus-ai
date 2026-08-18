import { useMemo } from 'react'
import { ArrowUpRight, CircleAlert, Radio, ScanLine, Sparkles } from 'lucide-react'
import { AgentStatus } from '../components/AgentStatus'
import { MetricCard } from '../components/MetricCard'
import { OperationsKpiCharts } from '../components/OperationsKpiCharts'
import { SystemExposureVisual } from '../components/SystemExposureVisual'
import { ValueSignalRibbon } from '../components/ValueSignalRibbon'
import { currency, timeAgo } from '../utils'
import { buildExecutiveMetrics } from '../utils/dashboardKpis'


export function CommandCenter({ dashboard, workflow, anomalies, onNavigate, onSelectAnomaly, onScan, scanning }) {
  // Resolved findings stay in the payload for containment accounting; every
  // "act on this" surface shows open work only.
  const open = useMemo(() => anomalies?.filter((item) => item.status !== 'resolved') || [], [anomalies])
  const critical = useMemo(() => open.filter((item) => item.severity === 'critical'), [open])
  const executiveMetrics = useMemo(() => buildExecutiveMetrics(dashboard, anomalies), [dashboard, anomalies])
  return <div className="page command-page">
    <div className="command-toolbar">
      <span className="scan-state"><span className="pulse-dot" />Last scan {dashboard?.last_scan ? timeAgo(dashboard.last_scan) : 'now'}</span>
      <button className="primary-button" onClick={onScan} disabled={scanning}><ScanLine size={16} />{scanning ? 'Scanning mesh…' : 'Run intelligence scan'}</button>
    </div>
    <section className={`metrics-grid ${scanning ? 'scanning' : ''}`}>{executiveMetrics.map((metric, index) => <MetricCard metric={metric} index={index} scanning={scanning} key={metric.label} />)}{scanning && <span className="radar-sweep" aria-hidden="true" />}</section>
    {workflow && <ValueSignalRibbon workflow={workflow} anomalies={anomalies} onOpenLedger={() => onNavigate('outcomes')} />}
    <section className="command-grid">
      <OperationsKpiCharts anomalies={anomalies} workflow={workflow} onNavigate={onNavigate} />
      <aside className="risk-queue card-surface">
        <div className="section-title">
          <div><span className="eyebrow"><CircleAlert size={14} /> Prioritized queue</span><h2>Fix before impact</h2></div>
          <span className="queue-count">{open.length}</span>
        </div>
        <div className="queue-list">
          {open.slice(0, 4).map((anomaly, index) => (
            <button className="queue-item" key={anomaly.id} onClick={() => onSelectAnomaly(anomaly)}>
              <span className={`queue-rank ${anomaly.severity}`}>0{index + 1}</span>
              <div><strong>{anomaly.title}</strong><small>{anomaly.system} · {anomaly.time_to_impact}</small></div>
              <span>{currency(anomaly.impact)}</span>
            </button>
          ))}
        </div>
        {open.length === 0 && <div className="queue-clear"><Sparkles size={17} /><strong>Every finding is contained.</strong><small>Run a scan or inject a live incident to give the mesh new work.</small></div>}
        <button className="quiet-button" onClick={() => onNavigate('intelligence')}>View all risks <ArrowUpRight size={15} /></button>
      </aside>
    </section>
    <section className="lower-grid">
      <AgentStatus agents={dashboard?.agents} onOpen={() => onNavigate('agents')} />
      <SystemExposureVisual anomalies={anomalies} />
    </section>
    {critical.length > 0 && <section className="contained-note"><span>System note</span><p><b>{critical.length} critical paths</b> are receiving active monitoring. Run a scan after applying a control to refresh the live risk telemetry.</p></section>}
  </div>
}

import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, ArrowUpRight, Clock3, Radio, ShieldCheck } from 'lucide-react'
import { currency } from '../utils'
import { buildApprovalPipeline, buildExposureBySeverity, buildRiskTimeline } from '../utils/dashboardKpis'

function ChartTooltip({ active, payload, label, valueLabel = 'Exposure' }) {
  if (!active || !payload?.length) return null
  return <div className="telemetry-tooltip"><strong>{payload[0]?.payload?.title || label}</strong><span>{valueLabel}: {valueLabel === 'Exposure' ? currency(payload[0].value) : payload[0].value}</span></div>
}

export function OperationsKpiCharts({ anomalies = [], workflow, onNavigate }) {
  const severityData = useMemo(() => buildExposureBySeverity(anomalies), [anomalies])
  const timelineData = useMemo(() => buildRiskTimeline(anomalies), [anomalies])
  const pipeline = useMemo(() => buildApprovalPipeline(workflow), [workflow])
  const open = anomalies.filter((item) => item.status !== 'resolved')
  const exposure = open.reduce((total, item) => total + (Number(item.impact) || 0), 0)
  const urgent = timelineData.filter((item) => item.minutes <= 120).length
  const pipelineMax = Math.max(1, ...pipeline.map((item) => item.requests))

  return <article className="operations-kpis card-surface">
    <div className="section-title telemetry-head"><div><span className="eyebrow"><Activity size={14} /> Operations decision board</span><h2>Risk exposure and action load</h2></div><div className="telemetry-actions"><span><Radio size={11} /> Live data</span><button className="text-button" onClick={() => onNavigate('intelligence')}>Drill through <ArrowUpRight size={15} /></button></div></div>
    <div className="telemetry-summary">
      <div><span>Open exposure</span><strong>{currency(exposure)}</strong></div>
      <div><span>Inside 2 hours</span><strong>{urgent}</strong></div>
      <div><span>Awaiting approval</span><strong>{workflow?.awaiting_my_decision ?? 0}</strong></div>
    </div>
    <div className="telemetry-charts">
      <section className="severity-visual"><div className="chart-label"><span>Exposure mix</span><small>{open.length} open findings</small></div><div className="donut-layout"><div className="donut-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={severityData} dataKey="exposure" nameKey="severity" innerRadius={43} outerRadius={66} paddingAngle={2} stroke="none">{severityData.map((entry) => <Cell key={entry.severity} fill={entry.color} />)}</Pie><Tooltip content={<ChartTooltip />} /></PieChart></ResponsiveContainer><div className="donut-center"><span>Total</span><strong>{currency(exposure)}</strong></div></div><div className="severity-legend">{severityData.map((entry) => <div key={entry.severity}><i style={{ background: entry.color }} /><span>{entry.severity}</span><strong>{currency(entry.exposure)}</strong><small>{entry.findings} findings</small></div>)}</div></div></section>
      <section><div className="chart-label"><span>Exposure by impact window</span><small>earliest first</small></div><div className="telemetry-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={timelineData} layout="vertical" margin={{ top: 8, right: 8, bottom: 0, left: 0 }}><CartesianGrid horizontal={false} stroke="var(--chart-grid)" /><XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 9 }} tickFormatter={(value) => `€${Math.round(value / 1000)}k`} /><YAxis type="category" dataKey="label" axisLine={false} tickLine={false} width={42} tick={{ fill: 'var(--text-muted)', fontSize: 9 }} /><Tooltip cursor={{ fill: 'var(--chart-hover)' }} content={<ChartTooltip />} /><Bar dataKey="exposure" radius={[0, 5, 5, 0]} maxBarSize={18}>{timelineData.map((entry) => <Cell key={entry.id} fill={entry.minutes <= 120 ? '#DA0C1F' : entry.minutes <= 720 ? '#FAAA3C' : '#008C82'} />)}</Bar></BarChart></ResponsiveContainer></div></section>
    </div>
    <div className="approval-telemetry"><div className="chart-label"><span><ShieldCheck size={13} /> Approval pipeline</span><small><Clock3 size={12} /> live workflow counts</small></div><div className="pipeline-bars">{pipeline.length ? pipeline.map((item) => <div key={item.stage}><span>{item.stage}</span><i><b style={{ width: `${Math.max(8, (item.requests / pipelineMax) * 100)}%` }} /></i><strong>{item.requests}</strong></div>) : <p>No governed requests are in flight.</p>}</div></div>
  </article>
}

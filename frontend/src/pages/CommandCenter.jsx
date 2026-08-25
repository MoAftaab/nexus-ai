import { useMemo } from 'react'
import {
  ArrowUpRight,
  BadgeEuro,
  CircleAlert,
  Flame,
  Gauge,
  Layers,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Timer,
  Zap,
} from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { compactCurrency, currency, timeAgo } from '../utils'
import {
  buildApprovalPipeline,
  buildExposureBySeverity,
  buildImpactHorizon,
  buildInsights,
  buildSystemExposure,
  minutesToImpact,
} from '../utils/dashboardKpis'

function DonutTip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="cc-tooltip">
      <strong>{payload[0]?.payload?.severity || ''}</strong>
      <span>{currency(payload[0].value)}</span>
    </div>
  )
}

export function CommandCenter({ dashboard, workflow, outcomes, anomalies, onNavigate, onSelectAnomaly, scanning }) {
  const open = useMemo(() => anomalies?.filter((a) => a.status !== 'resolved') || [], [anomalies])
  const resolved = useMemo(() => anomalies?.filter((a) => a.status === 'resolved') || [], [anomalies])
  const exposure = useMemo(() => open.reduce((s, a) => s + (Number(a.impact) || 0), 0), [open])
  const critical = useMemo(() => open.filter((a) => a.severity === 'critical').length, [open])
  const high = useMemo(() => open.filter((a) => a.severity === 'high').length, [open])
  const containment = useMemo(
    () => (anomalies?.length ? Math.round((resolved.length / anomalies.length) * 100) : 100),
    [anomalies, resolved]
  )
  const readiness = useMemo(
    () => dashboard?.metrics?.find((m) => m.label === 'Readiness index')?.value || 0,
    [dashboard]
  )

  const severityData = useMemo(() => buildExposureBySeverity(anomalies), [anomalies])
  const systemData = useMemo(() => buildSystemExposure(anomalies), [anomalies])
  const pipeline = useMemo(() => buildApprovalPipeline(workflow), [workflow])
  const insights = useMemo(
    () => buildInsights(anomalies, workflow, dashboard, outcomes),
    [anomalies, workflow, dashboard, outcomes]
  )
  const horizon = useMemo(() => buildImpactHorizon(anomalies), [anomalies])
  // Soonest-to-impact first, then largest exposure — the true "fix before impact" order.
  const queue = useMemo(
    () =>
      [...open].sort(
        (a, b) =>
          minutesToImpact(a.time_to_impact) - minutesToImpact(b.time_to_impact) ||
          (Number(b.impact) || 0) - (Number(a.impact) || 0)
      ),
    [open]
  )

  const pipelineMax = Math.max(1, ...pipeline.map((p) => p.requests))
  const systemMax = Math.max(1, ...systemData.map((s) => s.exposure))
  const protectedValue = Number(workflow?.verified_value_protected) || 0

  const topInsight = insights[0]
  const urgent = horizon[0]
  const horizonBand = horizon.filter((bucket) => bucket.exposure > 0)

  // The rail renders a fixed slice and never scrolls; CSS height queries
  // drop the tail rows on shorter viewports rather than squeezing them.
  const QUEUE_ROWS = 10
  const visibleQueue = queue.slice(0, QUEUE_ROWS)

  const kpis = [
    { label: 'Exposure at Risk', value: currency(exposure), sub: `${open.length} open findings`, tone: 'critical', icon: BadgeEuro },
    { label: 'Critical Actions', value: critical + high, sub: `${critical} critical · ${high} high`, tone: critical ? 'critical' : 'watch', icon: ShieldAlert },
    { label: 'Line Readiness', value: `${readiness}%`, sub: 'Severity-weighted index', tone: readiness >= 85 ? 'good' : 'watch', icon: Gauge },
    { label: 'Containment Rate', value: `${containment}%`, sub: `${resolved.length} of ${anomalies?.length || 0} resolved`, tone: containment >= 50 ? 'good' : 'watch', icon: ShieldCheck },
  ]

  return (
    <div className="page command-page cc-root">
      {/* Top toolbar */}
      <header className="cc-bar">
        <div className="cc-bar-left">
          <span className="cc-pulse">
            <span className="pulse-dot" />
            Last scan {dashboard?.last_scan ? timeAgo(dashboard.last_scan) : 'just now'}
          </span>
          {critical > 0 && (
            <span className="cc-critical-badge">
              <ShieldAlert size={11} />
              {critical} critical path{critical > 1 ? 's' : ''}
            </span>
          )}
          {topInsight && (
            <span className="cc-bar-insight">
              <Zap size={11} />
              {topInsight.text}
            </span>
          )}
        </div>
        <div className="cc-bar-right">
          <span className="cc-live">
            <Radio size={10} /> Live Data
          </span>
          <button className="cc-drill" onClick={() => onNavigate('intelligence')}>
            Risk Intelligence <ArrowUpRight size={13} />
          </button>
        </div>
      </header>

      {/* Executive KPI strip */}
      <section className="cc-kpi-strip">
        {kpis.map((kpi, i) => {
          const Icon = kpi.icon
          return (
            <article key={kpi.label} className={`cc-kpi cc-tone-${kpi.tone}`} style={{ '--i': i }}>
              <div className="cc-kpi-head">
                <span>{kpi.label}</span>
                <Icon size={13} />
              </div>
              <strong>{kpi.value}</strong>
              <small>{kpi.sub}</small>
            </article>
          )
        })}
      </section>

      {/* Analytics matrix */}
      <section className={`cc-matrix ${scanning ? 'scanning' : ''}`}>
        {/* Tile A — Impact horizon: exposure grouped by time to impact */}
        <div className="cc-card cc-tile-horizon">
          <div className="cc-card-head">
            <span><Timer size={12} /> Impact horizon</span>
            <small>{open.length} open · by deadline</small>
          </div>
          <div className="cc-horizon-body">
            <div className={`cc-horizon-lead ${urgent.findings ? '' : 'clear'}`}>
              <div className="cc-horizon-lead-main">
                <span className="cc-horizon-lead-badge">
                  {urgent.findings ? (
                    <>
                      <Flame size={11} className="cc-flame-icon" />
                      <span>Immediate (&lt;2h)</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={11} />
                      <span>Line Stable</span>
                    </>
                  )}
                </span>
                <div className="cc-horizon-lead-text">
                  <strong>{urgent.findings ? currency(urgent.exposure) : '€0'}</strong>
                  <em>{urgent.findings ? 'hits line within 2h' : 'no immediate threat'}</em>
                </div>
              </div>
              <div className="cc-horizon-lead-stat">
                <b>{urgent.findings}</b> of {open.length} findings
              </div>
            </div>

            {horizonBand.length ? (
              <div className="cc-horizon-band">
                {horizonBand.map((bucket) => (
                  <i key={bucket.label} style={{ flexGrow: bucket.exposure, background: bucket.color }} />
                ))}
              </div>
            ) : (
              <div className="cc-horizon-band" />
            )}

            <div className="cc-horizon-legend">
              {horizon.map((bucket) => {
                const exactExposure = currency(bucket.exposure)
                const displayExposure = compactCurrency(bucket.exposure)
                return (
                  <div
                    key={bucket.label}
                    className={`cc-horizon-item ${bucket.findings ? '' : 'empty'}`}
                    style={{ '--bucket': bucket.color }}
                    title={`${bucket.label}: ${exactExposure} (${bucket.findings} open findings, ${bucket.share}% share)`}
                  >
                    <div className="cc-horizon-item-top">
                      <span className="cc-horizon-tag">
                        <i className="cc-horizon-dot" />
                        {bucket.label}
                      </span>
                      <span className="cc-horizon-share">{bucket.share}%</span>
                    </div>
                    <div className="cc-horizon-item-value">
                      <strong title={exactExposure}>{displayExposure}</strong>
                    </div>
                    <div className="cc-horizon-item-bottom">
                      <span className="cc-horizon-count">
                        <b>{bucket.findings}</b> open
                      </span>
                      <div className="cc-horizon-meter">
                        <span style={{ width: `${Math.max(6, bucket.share)}%`, background: bucket.color }} />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Tile B — Severity mix */}
        <div className="cc-card cc-tile-donut">
          <div className="cc-card-head">
            <span><ShieldAlert size={12} /> Severity mix</span>
            <small>{open.length} open</small>
          </div>
          <div className="cc-donut-body">
            <div className="cc-donut-container">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityData}
                    dataKey="exposure"
                    nameKey="severity"
                    innerRadius="60%"
                    outerRadius="88%"
                    paddingAngle={severityData.length > 1 ? 3 : 0}
                    stroke="none"
                  >
                    {severityData.map((e) => (
                      <Cell key={e.severity} fill={e.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<DonutTip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="cc-donut-center-stat">
                <span>Exposure</span>
                <strong>{currency(exposure)}</strong>
              </div>
            </div>
            <div className="cc-donut-legend">
              {severityData.length ? (
                severityData.map((e) => (
                  <div key={e.severity} className="cc-legend-row">
                    <div className="cc-legend-label">
                      <i style={{ background: e.color }} />
                      <span>{e.severity}</span>
                    </div>
                    <div className="cc-legend-vals">
                      <strong>{currency(e.exposure)}</strong>
                      <small>{e.findings} finding{e.findings > 1 ? 's' : ''}</small>
                    </div>
                  </div>
                ))
              ) : (
                <p className="cc-empty-msg">No open exposure.</p>
              )}
            </div>
          </div>
        </div>

        {/* Tile C — System exposure */}
        <div className="cc-card cc-tile-systems">
          <div className="cc-card-head">
            <span><Layers size={12} /> System exposure</span>
            <small>top {systemData.length || 0}</small>
          </div>
          <div className="cc-sysbar-body">
            {systemData.length ? (
              systemData.map((s) => (
                <div key={s.system} className="cc-sysbar-row">
                  <span className="cc-sysbar-name" title={s.system}>{s.system}</span>
                  <i className="cc-sysbar-track">
                    <b style={{ width: `${Math.max(6, (s.exposure / systemMax) * 100)}%`, background: s.color }} />
                  </i>
                  <strong>{currency(s.exposure)}</strong>
                  <em>{s.share}%</em>
                </div>
              ))
            ) : (
              <p className="cc-empty-msg">No systems carrying exposure.</p>
            )}
          </div>
        </div>

        {/* Tile D — Approval pipeline */}
        <div className="cc-card cc-tile-pipeline">
          <div className="cc-card-head">
            <span><ShieldCheck size={12} /> Approval pipeline</span>
            <small>{workflow?.total || 0} requests</small>
          </div>
          <div className="cc-funnel-body">
            {pipeline.length ? (
              <div className="cc-funnel-list">
                {pipeline.map((p) => (
                  <div key={p.stage} className="cc-funnel-row">
                    <span>{p.stage}</span>
                    <i><b style={{ width: `${Math.max(14, (p.requests / pipelineMax) * 100)}%` }} /></i>
                    <strong>{p.requests}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <div className="cc-funnel-empty">
                <ShieldCheck size={17} />
                <strong>{currency(protectedValue)}</strong>
                <small>value protected · none in flight</small>
              </div>
            )}
            <button className="cc-tile-link" onClick={() => onNavigate('changes')}>
              Open Change Ledger <ArrowUpRight size={11} />
            </button>
          </div>
        </div>

        {/* Tile E — Priority queue */}
        <aside className="cc-card cc-tile-queue">
          <div className="cc-card-head">
            <span><CircleAlert size={12} /> Priority queue</span>
            <small>{open.length} open</small>
          </div>
          {open.length ? (
            <>
              <div className="cc-queue-list">
                {visibleQueue.map((a, i) => (
                  <button key={a.id} className="cc-queue-row" onClick={() => onSelectAnomaly(a)}>
                    <span className={`cc-queue-rank ${a.severity}`}>{String(i + 1).padStart(2, '0')}</span>
                    <div className="cc-queue-detail">
                      <strong>{a.title}</strong>
                      <div className="cc-queue-tags">
                        <span className="cc-sys-tag">{a.system}</span>
                        <span>·</span>
                        <span>{a.time_to_impact}</span>
                      </div>
                    </div>
                    <span className="cc-queue-val">{currency(a.impact)}</span>
                  </button>
                ))}
              </div>
              <button className="cc-queue-more" onClick={() => onNavigate('intelligence')}>
                View all {open.length} findings <ArrowUpRight size={12} />
              </button>
            </>
          ) : (
            <div className="cc-queue-clear">
              <Sparkles size={20} />
              <strong>Every finding is contained.</strong>
              <small>Run a scan or inject an incident to feed new work.</small>
            </div>
          )}
        </aside>

        {scanning && <span className="cc-sweep" aria-hidden="true" />}
      </section>
    </div>
  )
}

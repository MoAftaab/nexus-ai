import { useMemo } from 'react'
import {
  ArrowRight,
  BadgeEuro,
  CheckCircle2,
  CircleAlert,
  Database,
  Gauge,
  ShieldCheck,
  Sparkles,
  TimerReset,
} from 'lucide-react'
import { currency, number, timeAgo } from '../utils'
import { buildDataTrust, buildDecisionFocus, buildInterventionSnapshot } from '../utils/dashboardKpis'

function freshness(lastScan) {
  if (!lastScan) return { label: 'Unknown', tone: 'watch', detail: 'No scan timestamp' }
  const age = Math.max(0, (Date.now() - new Date(lastScan).getTime()) / 60000)
  if (!Number.isFinite(age)) return { label: 'Unknown', tone: 'watch', detail: 'Timestamp unavailable' }
  if (age <= 10) return { label: 'Fresh', tone: 'good', detail: `Scanned ${timeAgo(lastScan)}` }
  if (age <= 60) return { label: 'Watch', tone: 'watch', detail: `Scanned ${timeAgo(lastScan)}` }
  return { label: 'Stale', tone: 'critical', detail: `Scanned ${timeAgo(lastScan)}` }
}

function railStep({ icon: Icon, label, value, detail, tone = 'neutral', onClick }) {
  const content = <>
    <span className="decision-rail-icon"><Icon size={14} /></span>
    <span className="decision-rail-copy"><small>{label}</small><strong>{value}</strong><em>{detail}</em></span>
    {onClick && <ArrowRight className="decision-rail-arrow" size={14} />}
  </>
  return onClick
    ? <button type="button" className={`decision-rail-step tone-${tone}`} onClick={onClick}>{content}</button>
    : <div className={`decision-rail-step tone-${tone}`}>{content}</div>
}

export function CommandDecisionBoard({ dashboard, workflow, anomalies = [], outcomes, onNavigate, onSelectAnomaly }) {
  const focus = useMemo(() => buildDecisionFocus(anomalies, workflow), [anomalies, workflow])
  const intervention = useMemo(() => buildInterventionSnapshot(workflow, outcomes, anomalies), [workflow, outcomes, anomalies])
  const trust = useMemo(() => buildDataTrust(dashboard, anomalies), [dashboard, anomalies])
  const freshnessState = freshness(trust.lastScan)
  const finding = focus.anomaly
  const action = focus.action
  const actionStatus = action?.status ? action.status.replaceAll('_', ' ') : 'recommended'

  return <section className="command-decision-board" aria-label="Operational decision signals">
    <article className="decision-rail card-surface">
      <div className="decision-board-heading">
        <div><span className="eyebrow"><Sparkles size={14} /> Decision path</span><h2>The next decision that protects the line</h2><p>Follow one verified signal from exposure to human-controlled action.</p></div>
        <span className={`decision-status ${finding ? `severity-${finding.severity}` : 'clear'}`}><CircleAlert size={12} />{finding ? `${finding.severity} path` : 'No open path'}</span>
      </div>
      <div className="decision-rail-track">
        {railStep({
          icon: CircleAlert,
          label: 'Finding',
          value: finding?.id || 'Board clear',
          detail: finding?.title || 'No unresolved finding is waiting for intervention.',
          tone: finding?.severity || 'good',
          onClick: finding ? () => onSelectAnomaly(finding) : undefined,
        })}
        <ArrowRight className="decision-rail-connector" size={16} />
        {railStep({
          icon: BadgeEuro,
          label: 'Exposure',
          value: finding ? currency(finding.impact) : currency(0),
          detail: finding?.time_to_impact ? `Impact in ${finding.time_to_impact}` : 'Current modeled exposure',
          tone: finding?.severity || 'good',
          onClick: finding ? () => onSelectAnomaly(finding) : undefined,
        })}
        <ArrowRight className="decision-rail-connector" size={16} />
        {railStep({
          icon: ShieldCheck,
          label: 'Control',
          value: action?.title || 'No control attached',
          detail: action ? `${actionStatus} · ${action.owner || 'Operations'}` : 'Review the finding before acting.',
          tone: action ? 'good' : 'watch',
          onClick: finding ? () => onSelectAnomaly(finding) : undefined,
        })}
        <ArrowRight className="decision-rail-connector" size={16} />
        {railStep({
          icon: Gauge,
          label: 'Human decision',
          value: focus.awaitingDecision ? `${number(focus.awaitingDecision)} waiting` : 'Route ready',
          detail: focus.awaitingValue ? `${currency(focus.awaitingValue)} awaiting approval` : 'Open change control to review the route.',
          tone: focus.awaitingDecision ? 'watch' : 'neutral',
          onClick: () => onNavigate('changes'),
        })}
        <ArrowRight className="decision-rail-connector" size={16} />
        {railStep({
          icon: CheckCircle2,
          label: 'Verified value',
          value: currency(focus.protectedValue),
          detail: 'Approved and evidenced in the value ledger',
          tone: 'good',
          onClick: () => onNavigate('outcomes'),
        })}
      </div>
    </article>

    <div className="decision-support-grid">
      <article className={`decision-support-card impact-countdown card-surface tone-${finding?.severity || 'good'}`}>
        <div className="decision-support-head"><span className="eyebrow"><TimerReset size={14} /> Impact countdown</span><span className="decision-live-dot">Live</span></div>
        <div className="impact-countdown-value">{finding?.time_to_impact || 'Clear'}</div>
        <strong>{finding?.title || 'No immediate impact window'}</strong>
        <p>{finding ? `${finding.id} · ${currency(finding.impact)} modeled exposure` : 'The board has no unresolved finding with a known deadline.'}</p>
        {finding && <button type="button" className="text-button" onClick={() => onSelectAnomaly(finding)}>Open decision <ArrowRight size={14} /></button>}
      </article>

      <article className="decision-support-card intervention-card card-surface">
        <div className="decision-support-head"><span className="eyebrow"><ShieldCheck size={14} /> Intervention balance</span><button type="button" className="text-button" onClick={() => onNavigate('outcomes')}>Ledger <ArrowRight size={13} /></button></div>
        <div className="intervention-values"><div><small>Verified protected</small><strong>{currency(intervention.protectedValue)}</strong></div><div><small>Still exposed</small><strong>{currency(intervention.openExposure)}</strong></div></div>
        <div className="intervention-bar" aria-label={`${intervention.protectionRate}% of tracked value protected`}><i style={{ width: `${intervention.protectionRate}%` }} /></div>
        <div className="intervention-foot"><span>{intervention.protectionRate}% of tracked value protected</span><span>{intervention.resolved} resolved · {intervention.active} active</span></div>
        <p>Protected value comes from verified outcomes; open exposure is calculated from the live risk board.</p>
      </article>

      <article className="decision-support-card data-trust-card card-surface">
        <div className="decision-support-head"><span className="eyebrow"><Database size={14} /> Data trust &amp; freshness</span><button type="button" className="text-button" onClick={() => onNavigate('system')}>Inspect <ArrowRight size={13} /></button></div>
        <div className={`trust-banner tone-${freshnessState.tone}`}><span><span className="trust-pulse" />{freshnessState.label}</span><small>{freshnessState.detail}</small></div>
        <div className="trust-grid">
          <div><strong>{number(trust.records)}</strong><span>Twin records</span></div>
          <div><strong>{number(trust.scanCount)}</strong><span>Scans run</span></div>
          <div><strong>{trust.evidenceAttached}/{trust.findingCount}</strong><span>Findings evidenced</span></div>
          <div><strong>{trust.modelF1 == null ? '—' : `${trust.modelF1}%`}</strong><span>Detector F1</span></div>
        </div>
        <p>Live scan time, source evidence, and detector quality are shown together so reviewers can judge the board before acting.</p>
      </article>
    </div>
  </section>
}

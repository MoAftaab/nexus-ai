import { BadgeCheck, CalendarRange, FileCheck2, HandCoins, ShieldCheck, Sparkles, Timer, TrendingUp, UserX, UserCheck } from 'lucide-react'
import { currency, timeAgo } from '../utils'

const dayInLife = {
  without: [
    'Friday: weekly reconciliation spreadsheet flags a stock mismatch — the error is already 6 days old.',
    'An analyst spends ~4 hours pivoting between ERP, WMS and count sheets to find which number is wrong.',
    'Meanwhile: freight billed on a wrong weight, two short-picks, one truck loaded past its legal limit.',
    'Root cause is never written down — the same defect returns next quarter.',
  ],
  with: [
    'Within minutes of the data diverging, the finding appears — ranked by euro impact, root cause attached.',
    'The cascade map shows exactly what it will hit, when, and with what probability.',
    'One human approves the recommended control; the source records are corrected at the origin.',
    'The incident report and audit trail write themselves; a rescan proves the defect is gone.',
  ],
}

export function Outcomes({ outcomes, onSelectAnomaly }) {
  const summary = outcomes?.summary
  const roi = outcomes?.roi
  const items = outcomes?.items || []
  return <div className="page outcomes-page">
    <section className="page-lead"><div><span className="eyebrow"><HandCoins size={14} /> Value ledger</span><h2>What Warehouse Control Tower AI has saved you.</h2><p>Every human-approved control and every ingested document lands here with its measurable effect, so the value of each decision stays visible and auditable.</p></div>
      <div className="leaderboard-total"><span>Value protected</span><strong>{currency(summary?.value_protected || 0)}</strong></div></section>
    <section className="outcome-stats">
      <div className="outcome-stat card-surface"><ShieldCheck size={17} /><div><strong>{summary?.anomalies_resolved ?? 0}</strong><span>Cascades resolved</span></div></div>
      <div className="outcome-stat card-surface"><BadgeCheck size={17} /><div><strong>{summary?.fixes_applied ?? 0}</strong><span>Controls applied</span></div></div>
      <div className="outcome-stat card-surface"><FileCheck2 size={17} /><div><strong>{summary?.documents_ingested ?? 0}</strong><span>Documents ingested</span></div></div>
      <div className="outcome-stat card-surface"><TrendingUp size={17} /><div><strong>{currency(summary?.value_protected || 0)}</strong><span>Exposure removed</span></div></div>
    </section>
    {roi && <section className="roi-band card-surface">
      <div className="roi-cell"><CalendarRange size={16} /><div><strong>{currency(roi.annualized_value)}</strong><span>Annual run-rate if this shift is typical ({roi.shifts_per_year.toLocaleString()} shifts/yr)</span></div></div>
      <div className="roi-cell"><Timer size={16} /><div><strong>~{roi.detection_minutes} min vs {roi.manual_cadence_days} days</strong><span>Detection latency vs weekly manual reconciliation</span></div></div>
      <div className="roi-cell"><TrendingUp size={16} /><div><strong>{currency(roi.still_actionable)}</strong><span>Still actionable on the board right now</span></div></div>
      <p className="roi-note">{roi.note}</p>
    </section>}
    <section className="day-in-life">
      <article className="card-surface life-card without"><div className="life-head"><UserX size={16} /><h3>The same error, without Control Tower</h3></div><ol>{dayInLife.without.map((line, index) => <li key={index}>{line}</li>)}</ol></article>
      <article className="card-surface life-card with"><div className="life-head"><UserCheck size={16} /><h3>With Warehouse Control Tower watching</h3></div><ol>{dayInLife.with.map((line, index) => <li key={index}>{line}</li>)}</ol></article>
    </section>
    {items.length === 0
      ? <section className="card-surface empty-state"><Sparkles size={22} /><h3>No outcomes recorded yet</h3><p>Approve a recommended control from any finding, or ingest a document — the result and its value will appear here.</p></section>
      : <section className="card-surface outcome-ledger">
        {items.map((item) => <button key={item.id} className="outcome-row" onClick={() => item.anomaly_id && onSelectAnomaly?.({ id: item.anomaly_id })} disabled={!item.anomaly_id}>
          <span className={`outcome-kind ${item.kind}`}>{item.kind === 'fix' ? <ShieldCheck size={15} /> : <FileCheck2 size={15} />}</span>
          <div className="outcome-copy"><strong>{item.title}</strong><small>{item.detail}</small></div>
          <div className="outcome-meta">{item.saved > 0 && <b>{currency(item.saved)} protected</b>}<time>{timeAgo(item.at)}</time></div>
        </button>)}
      </section>}
  </div>
}

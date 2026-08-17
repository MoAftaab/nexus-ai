import { useMemo } from 'react'
import { ArrowUpRight, Clock3, Coins, Network, ShieldCheck } from 'lucide-react'
import { currency } from '../utils'
import { buildValueSignals } from '../utils/dashboardKpis'

export function ValueSignalRibbon({ workflow, anomalies, onOpenLedger }) {
  const signals = useMemo(() => buildValueSignals(workflow, anomalies), [workflow, anomalies])

  return <section className="value-signal-ribbon card-surface" aria-label="Operational value signals">
    <div className="value-signal intro">
      <span className="value-signal-icon"><ShieldCheck size={15} /></span>
      <div><small>Verified value protected</small><strong>{currency(signals.verifiedValue)}</strong><p>Approved and evidenced</p></div>
    </div>
    <div className="value-signal pending">
      <span className="value-signal-icon"><Coins size={15} /></span>
      <div><small>Value awaiting approval</small><strong>{currency(signals.awaitingValue)}</strong><p>Human decision required</p></div>
    </div>
    <div className="value-signal conversion">
      <span className="value-ring" style={{ '--value-rate': `${signals.protectionRate * 3.6}deg` }}><b>{signals.protectionRate}%</b></span>
      <div><small>Value secured</small><strong>{signals.protectionRate}%</strong><p>Of measurable decision value</p></div>
    </div>
    <div className="value-signal window">
      <span className="value-signal-icon"><Clock3 size={15} /></span>
      <div><small>Nearest impact window</small><strong>{signals.nearestWindow}</strong><p><Network size={11} /> {signals.systemsAtRisk} systems · {signals.openFindings} findings</p></div>
    </div>
    <button className="value-ledger-link" onClick={onOpenLedger}>Open value ledger <ArrowUpRight size={14} /></button>
  </section>
}

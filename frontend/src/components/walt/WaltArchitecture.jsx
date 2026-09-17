import { Activity, BrainCircuit, Database, Network, ShieldCheck, Sparkles } from 'lucide-react'

const fallbackTiers = [
  { id: 'ingestion', label: 'Ingestion Agent', status: 'connected', detail: '6 SAP sheets loaded & unified' },
  { id: 'data_quality', label: 'Data-Quality Agent', status: 'ready', detail: 'Master data catalog checks (A1–A6)' },
  { id: 'anomaly', label: 'Anomaly Agent', status: 'ready', detail: 'Inventory & process anomalies (B1–F2)' },
  { id: 'correlation', label: 'Correlation / Root-Cause Agent', status: 'ready', detail: 'Cross-system root cause & cascade (X1–X2)' },
  { id: 'impact', label: 'Impact Agent', status: 'ready', detail: 'Exposure scoring & priority worklist' },
  { id: 'remediation', label: 'Action / Remediation Agent', status: 'ready', detail: 'Human-approved change control & fixes' },
  { id: 'orchestrator', label: 'Orchestrator (WALT)', status: 'ready', detail: 'Flow planning, specialist handoffs & audit' },
]

const tierIcons = {
  source: Database,
  ingestion: Database,
  data_quality: ShieldCheck,
  anomaly: Activity,
  correlation: Network,
  impact: BrainCircuit,
  remediation: ShieldCheck,
  orchestrator: Sparkles,
  specialists: BrainCircuit,
  governance: ShieldCheck,
}

export function WaltArchitecture({ architecture, compact = false }) {
  const tiers = architecture?.tiers?.length ? architecture.tiers : fallbackTiers
  const dataset = architecture?.dataset
  const provider = architecture?.provider_label || 'Evidence mode'
  const model = architecture?.model || 'nexus_deterministic'
  const connected = dataset?.status === 'connected'

  return <section className={`walt-architecture ${compact ? 'is-compact' : ''}`} aria-label="WALT multi-tier architecture">
    <header className="walt-architecture__head">
      <div className="walt-architecture__title"><Network size={13} /><span><b>Tiered reasoning</b><small>{provider} · {model}</small></span></div>
      <span className="walt-architecture__signal" aria-label="Live agent handoff animation"><i /><i /><i /></span>
      <span className={`walt-architecture__status ${connected ? 'is-connected' : ''}`}><i />{connected ? 'Dataset linked' : 'Evidence mode'}</span>
    </header>
    <div className="walt-architecture__tiers">
      {tiers.map((tier, index) => {
        const Icon = tierIcons[tier.id] || Activity
        const isLive = tier.status === 'connected' || tier.status === 'ready' || tier.status === 'enforced'
        return <div className="walt-architecture__step" key={tier.id}>
          <article className={`walt-architecture__tier ${isLive ? 'is-live' : ''}`} data-tier={tier.id} style={{ '--architecture-delay': `${index * 140}ms` }}>
            <span className="walt-architecture__icon"><Icon size={12} /></span>
            <span className="walt-architecture__copy"><b>{tier.label}</b><small>{tier.detail}</small></span>
            {!compact && <em>{tier.status}</em>}
          </article>
          {index < tiers.length - 1 && <span className="walt-architecture__connector" aria-hidden="true"><i /></span>}
        </div>
      })}
    </div>
    {!compact && <footer className="walt-architecture__footer"><span><Database size={10} />{dataset?.records?.toLocaleString?.() || '—'} records</span><span><Activity size={10} />{dataset?.active_findings ?? '—'} active findings</span><span><ShieldCheck size={10} />Human approval required</span></footer>}
  </section>
}

import { useMemo } from 'react'
import { Boxes, Radio } from 'lucide-react'
import { currency } from '../utils'
import { buildSystemExposure } from '../utils/dashboardKpis'

export function SystemExposureVisual({ anomalies = [] }) {
  const systems = useMemo(() => buildSystemExposure(anomalies), [anomalies])
  const total = systems.reduce((sum, item) => sum + item.exposure, 0)

  return <article className="system-exposure-card card-surface">
    <div className="section-title">
      <div><span className="eyebrow"><Boxes size={14} /> System concentration</span><h2>Where exposure is accumulating</h2></div>
      <span className="live-visual-badge"><Radio size={11} /> Live allocation</span>
    </div>
    {systems.length > 0 ? <>
      <div className="system-exposure-total"><span>Open exposure represented</span><strong>{currency(total)}</strong></div>
      <div className="system-share-band" aria-label="Exposure share by system">
        {systems.map((item) => <i key={item.system} style={{ width: `${Math.max(item.share, 2)}%`, background: item.color }} title={`${item.system}: ${item.share}%`} />)}
      </div>
      <div className="system-exposure-list">
        {systems.map((item) => <div className="system-exposure-row" key={item.system}>
          <span className="system-swatch" style={{ background: item.color }} />
          <strong>{item.system}</strong>
          <small>{item.findings} {item.findings === 1 ? 'finding' : 'findings'}</small>
          <b>{currency(item.exposure)}</b>
          <em>{item.share}%</em>
        </div>)}
      </div>
      <p>Shared anomaly exposure is split evenly across affected systems to avoid double counting.</p>
    </> : <div className="system-exposure-empty"><strong>No open exposure</strong><span>All monitored systems are currently contained.</span></div>}
  </article>
}

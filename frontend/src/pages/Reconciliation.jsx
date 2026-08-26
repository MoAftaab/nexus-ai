import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, DatabaseZap, Search, Sparkles } from 'lucide-react'

export function Reconciliation({ data, onSelectAnomaly }) {
  const [selected, setSelected] = useState(data?.rows?.[0]?.id)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!selected && data?.rows?.[0]?.id) setSelected(data.rows[0].id)
  }, [data, selected])

  const active = data?.rows?.find((row) => row.id === selected) || data?.rows?.[0]
  const controlId = data?.summary?.anomaly_id
  const scale = active ? Math.max(active.wms, active.erp, active.tms, active.physical, 1) : 1
  const bar = (value) => `${Math.min(100, (value / scale) * 100)}%`

  // Every source measured against the physical count — the only balance that is
  // ground truth. The deltas are what an operator actually reads off this panel.
  const sources = useMemo(() => (active ? [
    { label: 'WMS', value: active.wms, delta: active.wms - active.physical },
    { label: 'ERP', value: active.erp, delta: active.erp - active.physical },
    { label: 'TMS', value: active.tms, delta: active.tms - active.physical },
    { label: 'Count', value: active.physical, delta: 0 },
  ] : []), [active])
  const agreeing = sources.filter((source) => source.delta === 0).length

  const filteredRows = (data?.rows || []).filter(
    (r) =>
      !filter ||
      r.sku?.toLowerCase().includes(filter.toLowerCase()) ||
      r.description?.toLowerCase().includes(filter.toLowerCase()) ||
      r.bin?.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="page reconciliation-page">
      <div className="recon-viewport-grid">
        {/* Left Column (50%): Balance table on top, Divergence Timeline below */}
        <div className="recon-left-col">
          {/* Top: Balance comparison table */}
          <article className="reconcile-table card-surface">
            <div className="reconcile-toolbar">
              <div>
                <h3>Balance comparison</h3>
                <span>Last physical count: {data?.summary?.last_count || 'Today'}</span>
              </div>
              <div className="reconcile-toolbar-right">
                <span className="recon-variance-chip">
                  {data?.summary?.review_items || 0} to review · {data?.summary?.total_variance || 0} units adrift
                </span>
                <label className="table-search">
                  <Search size={14} />
                  <input
                    placeholder="Filter inventory..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  />
                </label>
              </div>
            </div>

            <div className="inventory-head">
              <span>Part & location</span>
              <span>WMS</span>
              <span>ERP</span>
              <span>TMS</span>
              <span>Physical</span>
              <span>Variance</span>
              <span />
            </div>

            {/* Fixed at 8 rows by the API, so they share the height instead of scrolling. */}
            <div className="inventory-rows-scroll">
              {filteredRows.map((row) => (
                <button
                  className={`inventory-row ${selected === row.id ? 'selected' : ''}`}
                  key={row.id}
                  onClick={() => setSelected(row.id)}
                >
                  <span>
                    <strong>{row.sku}</strong>
                    <small>{row.description} · {row.bin}</small>
                  </span>
                  <b>{row.wms}</b>
                  <b>{row.erp}</b>
                  <b>{row.tms}</b>
                  <b>{row.physical}</b>
                  <em className={row.risk}>
                    {row.variance === 0 ? 'Balanced' : `${row.variance > 0 ? '+' : ''}${row.variance}`}
                  </em>
                </button>
              ))}
              {filteredRows.length === 0 && (
                <p className="recon-empty">No part matches “{filter}”.</p>
              )}
            </div>
          </article>

          {/* Full-width Divergence Timeline directly under Balance comparison table */}
          <section className="audit-timeline card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><CheckCircle2 size={12} /> Transaction archaeology</span>
                <h3>Divergence timeline {active ? `· ${active.sku}` : ''}</h3>
              </div>
            </div>
            <div className="timeline-row">
              {active ? (() => {
                const events = []
                const hasDrift = active.variance !== 0
                // WMS event
                events.push({
                  time: 'WMS',
                  event: hasDrift && active.wms !== active.physical
                    ? `WMS reports ${active.wms} units — ${active.wms > active.physical ? '+' : ''}${active.wms - active.physical} vs physical`
                    : `WMS reports ${active.wms} units — matches physical`,
                  system: 'WMS',
                  state: active.wms !== active.physical ? 'critical' : 'good',
                })
                // ERP event
                events.push({
                  time: 'ERP',
                  event: hasDrift && active.erp !== active.physical
                    ? `ERP balance shows ${active.erp} units — ${active.erp > active.physical ? '+' : ''}${active.erp - active.physical} divergence`
                    : `ERP balance ${active.erp} units — synchronized`,
                  system: 'ERP',
                  state: active.erp !== active.physical ? 'critical' : 'good',
                })
                // TMS event
                events.push({
                  time: 'TMS',
                  event: hasDrift && active.tms !== active.physical
                    ? `TMS inherited ${active.tms} units — ${active.tms > active.physical ? '+' : ''}${active.tms - active.physical} gap`
                    : `TMS shows ${active.tms} units — aligned`,
                  system: 'TMS',
                  state: active.tms !== active.physical ? 'watch' : 'good',
                })
                // Physical count event
                events.push({
                  time: 'Count',
                  event: `Physical count verified at ${active.physical} units`,
                  system: 'Physical',
                  state: 'good',
                })
                return events.map((event) => (
                  <div className={`timeline-event ${event.state}`} key={event.time}>
                    <i />
                    <span>{event.time}</span>
                    <strong>{event.event}</strong>
                    <small>{event.system}</small>
                  </div>
                ))
              })() : (
                <p className="recon-empty">Select a row to see its divergence timeline.</p>
              )}
            </div>
          </section>
        </div>

        {/* Right Column (50%): Reconciliation Agent on top, SAP ERP Storage Truth below */}
        <div className="recon-right-col">
          {/* Top: Reconciliation Agent Workbench */}
          <aside className="reconcile-detail card-surface">
            {active ? (
              <>
                <div className="recon-detail-head">
                  <div className="recon-detail-title-row">
                    <div>
                      <span className="eyebrow"><Sparkles size={13} /> Reconciliation agent</span>
                      <h3>{active.sku}: source of truth</h3>
                    </div>
                    <small className="recon-sku-bin">{active.description} · {active.bin}</small>
                  </div>
                </div>

                <div className="truth-value">
                  <strong>{active.physical}</strong>
                  <span>verified units</span>
                  <em className={active.risk}>
                    {active.variance === 0 ? 'In balance' : `${active.variance > 0 ? '+' : ''}${active.variance} drift`}
                  </em>
                </div>

                <p className="root-cause-text">{active.root}</p>

                <div className="balance-bars">
                  <div className="balance-bars-head">
                    <span>Source</span>
                    <span>Balance</span>
                    <span>Δ count</span>
                  </div>
                  {sources.map((source) => (
                    <div className={source.delta === 0 ? 'agrees' : 'drifts'} key={source.label}>
                      <span>{source.label}</span>
                      <i><b style={{ width: bar(source.value) }} /></i>
                      <strong>{source.value}</strong>
                      <em>{source.delta === 0 ? '—' : `${source.delta > 0 ? '+' : ''}${source.delta}`}</em>
                    </div>
                  ))}
                </div>

                <div className="recon-action-row">
                  <div className="recon-verdict">
                    <span>Source agreement</span>
                    <strong className={agreeing === sources.length ? 'sap-ok' : 'sap-alert'}>
                      {agreeing} of {sources.length} match the count
                    </strong>
                  </div>
                  {controlId && (
                    <button
                      className="primary-button recon-action-btn"
                      onClick={() => onSelectAnomaly?.({ id: controlId })}
                    >
                      Open reconciliation control
                    </button>
                  )}
                </div>
              </>
            ) : null}
          </aside>

          {/* Bottom: SAP ERP Storage-Location Truth & Warehouse Controls */}
          <section className="sap-workbench card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><DatabaseZap size={12} /> SAP ERP / MARD</span>
                <h3>Storage-location truth & controls</h3>
              </div>
              <span className="sap-plant">Plant {active?.plant || '1400'} · {active?.warehouse || 'WH-01'}</span>
            </div>

            <div className="sap-matrix">
              {/* Row 1: Primary Metrics (3 items) */}
              <div className="sap-matrix-row sap-row-top">
                <div className="sap-cell">
                  <span>Storage location</span>
                  <strong>{active?.storagelocation || active?.bin || 'F6M1'}</strong>
                </div>
                <div className="sap-cell">
                  <span>Fiscal period</span>
                  <strong className={active?.fiscalyearofcurrentperiod && active.fiscalyearofcurrentperiod < 2026 ? 'sap-alert' : ''}>
                    FY{active?.fiscalyearofcurrentperiod || '2026'} / {active?.currentperiod || '08'}
                  </strong>
                </div>
                <div className="sap-cell">
                  <span>Blocked stock</span>
                  <strong className={active?.blockedstock > 0 ? 'sap-warn' : 'sap-ok'}>
                    {active?.blockedstock || 0} ST
                  </strong>
                </div>
              </div>

              {/* Row 2: Status & Synchronization Verification (2 items) */}
              <div className="sap-matrix-row sap-row-bottom">
                <div className="sap-cell">
                  <span>Stock integrity</span>
                  <strong className={active?.deletionflag === 'X' ? 'sap-alert' : 'sap-ok'}>
                    {active?.deletionflag === 'X' ? 'Flagged for Deletion' : 'Normal / Unblocked'}
                  </strong>
                </div>
                <div className="sap-cell">
                  <span>Physical count sync</span>
                  <strong className={active?.dateoflastpostedcount === '00000000' ? 'sap-alert' : 'sap-ok'}>
                    {active?.dateoflastpostedcount && active.dateoflastpostedcount !== '00000000' ? `Posted ${active.dateoflastpostedcount}` : 'Synchronized'}
                  </strong>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

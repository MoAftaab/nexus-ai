import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, CheckCircle2, DatabaseZap, Search, Sparkles } from 'lucide-react'

export function Reconciliation({ data, onSelectAnomaly }) {
  const [selected, setSelected] = useState(data?.rows?.[0]?.id)
  const [filter, setFilter] = useState('')
  const isHackathon = data?.summary?.source === 'SAP Hackathon · Inventory_Stock'
  const sourceRows = useMemo(() => (isHackathon ? (data?.rows || []) : []), [data?.rows, isHackathon])

  useEffect(() => {
    if (sourceRows[0]?.id && !sourceRows.some((row) => row.id === selected)) setSelected(sourceRows[0].id)
  }, [sourceRows, selected])

  const active = sourceRows.find((row) => row.id === selected) || sourceRows[0]
  const controlId = active?.related_anomaly_id || data?.summary?.anomaly_id
  const scale = active ? Math.max(active.on_hand, active.blocked, active.in_transit, active.available, active.reorder_point, 1) : 1
  const bar = (value) => `${Math.min(100, (value / scale) * 100)}%`

  // These are the actual fields in the Hackathon Inventory_Stock sheet. The
  // available/reorder comparison is the operational signal shown as variance.
  const sources = useMemo(() => (active ? [
    { label: 'On hand', value: active.on_hand, delta: active.on_hand - active.reorder_point },
    { label: 'Available', value: active.available, delta: active.variance },
    { label: 'In transit', value: active.in_transit, delta: active.in_transit },
    { label: 'Reorder', value: active.reorder_point, delta: 0 },
  ] : []), [active])
  const agreeing = sources.filter((source) => source.delta === 0).length

  const filteredRows = sourceRows.filter(
    (r) =>
      !filter ||
      r.material?.toLowerCase().includes(filter.toLowerCase()) ||
      r.description?.toLowerCase().includes(filter.toLowerCase()) ||
      r.bin?.toLowerCase().includes(filter.toLowerCase()) ||
      r.storage_location?.toLowerCase().includes(filter.toLowerCase()) ||
      r.source_record_id?.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="page reconciliation-page">
      {data?.rows?.length > 0 && !isHackathon && (
        <div className="recon-data-warning" role="alert">
          This backend is returning the legacy synthetic reconciliation shape. Refresh after the Hackathon backend deployment completes.
        </div>
      )}
      <div className="recon-viewport-grid">
        {/* Left Column (50%): Balance table on top, Divergence Timeline below */}
        <div className="recon-left-col">
          {/* Top: Balance comparison table */}
          <article className="reconcile-table card-surface">
            <div className="reconcile-toolbar">
              <div>
                <h3>Balance comparison</h3>
                <span>{data?.summary?.source || 'SAP Inventory_Stock'} · last movement: {data?.summary?.last_count || 'Unknown'}</span>
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
              <span>Material & location</span>
              <span>On hand</span>
              <span>Blocked</span>
              <span>In transit</span>
              <span>Available</span>
              <span>Signal</span>
              <span />
            </div>

            {/* Fixed at 8 rows by the API, so they share the height instead of scrolling. */}
            <div className="inventory-rows-scroll">
              {isHackathon && filteredRows.map((row) => (
                <button
                  className={`inventory-row ${selected === row.id ? 'selected' : ''}`}
                  key={row.id}
                  onClick={() => setSelected(row.id)}
                  aria-label={`Open source record ${row.source_record_id}`}
                >
                  <span>
                    <strong>{row.material}</strong>
                    <small>{row.description} · Plant {row.plant} · {row.storage_location}</small>
                  </span>
                  <b>{row.on_hand}</b>
                  <b>{row.blocked}</b>
                  <b>{row.in_transit}</b>
                  <b>{row.available}</b>
                  <em className={row.risk}>
                    {row.risk === 'healthy' ? 'Healthy' : row.variance < 0 ? `${row.variance} vs reorder` : 'Watch'}
                  </em>
                  <ArrowUpRight size={14} />
                </button>
              ))}
              {isHackathon && filteredRows.length === 0 && (
                <p className="recon-empty">No material matches “{filter}”.</p>
              )}
              {!isHackathon && (
                <p className="recon-empty">Waiting for the official Hackathon Inventory_Stock feed.</p>
              )}
            </div>
          </article>

          {/* Full-width Divergence Timeline directly under Balance comparison table */}
          <section className="audit-timeline card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><CheckCircle2 size={12} /> Transaction archaeology</span>
                <h3>Inventory signal timeline {active ? `· ${active.material}` : ''}</h3>
              </div>
            </div>
            <div className="timeline-row">
              {active ? (() => {
                const events = []
                const hasDrift = active.variance < 0
                events.push({
                  time: 'Stock',
                  event: `Inventory_Stock reports ${active.on_hand} ${active.uom} on hand at ${active.storage_location}`,
                  system: 'SAP Inventory_Stock',
                  state: active.on_hand < 0 ? 'critical' : 'good',
                })
                events.push({
                  time: 'MRP',
                  event: hasDrift
                    ? `Available stock is ${Math.abs(active.variance)} ${active.uom} below the ${active.reorder_point} reorder point`
                    : `Available stock is at or above the ${active.reorder_point} reorder point`,
                  system: 'SAP Material Master',
                  state: hasDrift ? 'critical' : 'good',
                })
                events.push({
                  time: 'Status',
                  event: `${active.blocked} ${active.uom} blocked · ${active.in_transit} ${active.uom} in transit`,
                  system: 'SAP Stock Status',
                  state: active.blocked > 0 ? 'watch' : 'good',
                })
                events.push({
                  time: 'Source',
                  event: `Exact source record selected: ${active.source_record_id}`,
                  system: 'Hackathon workbook',
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
                      <h3>{active.material}: source record</h3>
                    </div>
                    <small className="recon-sku-bin">{active.description} · Plant {active.plant} · {active.storage_location}</small>
                  </div>
                </div>

                <div className="truth-value">
                  <strong>{active.available}</strong>
                  <span>available {active.uom}</span>
                  <em className={active.risk}>
                    {active.variance < 0 ? `${active.variance} vs reorder` : 'At reorder target'}
                  </em>
                </div>

                <p className="root-cause-text">{active.related_anomaly_title || 'Inventory position selected from the official Hackathon workbook.'}</p>

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
                      Open linked finding
                    </button>
                  )}
                </div>
                <div className="recon-source-record">
                  <span>Exact source record</span>
                  <code>{active.source_table} · {active.source_record_id}</code>
                </div>
              </>
            ) : null}
          </aside>

          {/* Bottom: SAP ERP Storage-Location Truth & Warehouse Controls */}
          <section className="sap-workbench card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><DatabaseZap size={12} /> Hackathon SAP source</span>
                <h3>Inventory_Stock record</h3>
              </div>
              <span className="sap-plant">Plant {active?.plant || '—'} · {active?.storage_location || '—'}</span>
            </div>

            <div className="sap-matrix">
              {/* Row 1: Primary Metrics (3 items) */}
              <div className="sap-matrix-row sap-row-top">
                <div className="sap-cell">
                  <span>Storage location</span>
                  <strong>{active?.storage_location || '—'}</strong>
                </div>
                <div className="sap-cell">
                  <span>Batch / unit</span>
                  <strong>{active?.source_record?.batch || 'No batch'} · {active?.uom || '—'}</strong>
                </div>
                <div className="sap-cell">
                  <span>Blocked quantity</span>
                  <strong className={active?.blocked > 0 ? 'sap-warn' : 'sap-ok'}>
                    {active?.blocked || 0} {active?.uom || 'EA'}
                  </strong>
                </div>
              </div>

              {/* Row 2: Status & Synchronization Verification (2 items) */}
              <div className="sap-matrix-row sap-row-bottom">
                <div className="sap-cell">
                  <span>Last movement</span>
                  <strong className="sap-ok">
                    {active?.source_record?.last_movement_date || 'Not recorded'}
                  </strong>
                </div>
                <div className="sap-cell">
                  <span>Reorder point</span>
                  <strong className={active?.variance < 0 ? 'sap-alert' : 'sap-ok'}>
                    {active?.reorder_point || 0} {active?.uom || 'EA'}
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

import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDownUp, ChevronLeft, ChevronRight, Filter, Search, SlidersHorizontal } from 'lucide-react'
import { currency, severityLabel } from '../utils'

// The table never scrolls: rows are sized to the space that exists and the
// remainder is paged. 54px is the shortest a row can be and stay readable,
// so it doubles as the divisor when working out how many fit.
const MIN_ROW_HEIGHT = 54

/** Builds a compact page list — 1 2 3 4 5 … 12 — around the current page. */
function pageWindow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  const anchors = [...new Set([1, current - 1, current, current + 1, total])]
    .filter((page) => page >= 1 && page <= total)
    .sort((a, b) => a - b)
  return anchors.flatMap((page, index) =>
    index > 0 && page - anchors[index - 1] > 1 ? ['gap', page] : [page]
  )
}

export function RiskIntelligence({ anomalies, onSelectAnomaly }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(8)
  const bodyRef = useRef(null)

  const visible = useMemo(() => (anomalies || []).filter((item) => {
    const matchesQuery = `${item.title} ${item.sku} ${item.system}`.toLowerCase().includes(query.toLowerCase())
    // The decision queue holds open work; contained findings live behind their own filter.
    if (filter === 'contained') return item.status === 'resolved' && matchesQuery
    if (item.status === 'resolved') return false
    return (filter === 'all' || item.severity === filter) && matchesQuery
  }), [anomalies, filter, query])
  const containedCount = useMemo(() => (anomalies || []).filter((item) => item.status === 'resolved').length, [anomalies])

  // The body is flex:1 inside a fixed-height card, so its height never depends
  // on how many rows we render — measuring it here cannot feed back on itself.
  useEffect(() => {
    const element = bodyRef.current
    if (!element || typeof ResizeObserver === 'undefined') return undefined
    const measure = () => {
      const fits = Math.max(4, Math.floor(element.clientHeight / MIN_ROW_HEIGHT))
      setRowsPerPage((current) => (current === fits ? current : fits))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const totalPages = Math.max(1, Math.ceil(visible.length / rowsPerPage))
  // Clamped rather than reset in an effect, so a shrinking result set or a
  // shorter viewport can never leave the pager pointing past the last page.
  const currentPage = Math.min(page, totalPages)
  const startIndex = (currentPage - 1) * rowsPerPage
  const rows = visible.slice(startIndex, startIndex + rowsPerPage)
  const totalExposure = useMemo(() => visible.reduce((total, item) => total + item.impact, 0), [visible])

  const applyFilter = (next) => { setFilter(next); setPage(1) }

  return <div className="page intelligence-page">
    <section className="toolbar card-surface intel-toolbar">
      <label className="table-search">
        <Search size={17} />
        <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Find part, system or anomaly…" />
      </label>
      <div className="filter-set" role="group" aria-label="Filter by severity">
        {['all', 'critical', 'high', 'medium', 'low'].map((item) => (
          <button className={filter === item ? 'active' : ''} key={item} onClick={() => applyFilter(item)}>
            {item === 'all' ? 'All findings' : severityLabel(item)}
          </button>
        ))}
        <button className={filter === 'contained' ? 'active contained-filter' : 'contained-filter'} onClick={() => applyFilter('contained')}>
          Contained{containedCount > 0 ? ` · ${containedCount}` : ''}
        </button>
      </div>
      <div className="intel-total">
        <span>{filter === 'contained' ? 'Exposure removed' : 'Open exposure'}</span>
        <strong>{currency(totalExposure)}</strong>
      </div>
      <button className="soft-button"><SlidersHorizontal size={16} />Filters</button>
    </section>

    <section className="risk-table card-surface">
      <div className="risk-table-head">
        <span>Finding</span>
        <span>Systems</span>
        <span>Time to impact</span>
        <span>Exposure <ArrowDownUp size={13} /></span>
        <span>Control</span>
      </div>
      <div className="risk-table-body" ref={bodyRef}>
        {rows.map((item, index) => (
          <button
            className={`risk-row ${item.status === 'resolved' ? 'contained-row' : ''}`}
            key={item.id}
            onClick={() => onSelectAnomaly(item)}
          >
            <span className="risk-title">
              <i>{String(startIndex + index + 1).padStart(2, '0')}</i>
              <span className={`severity-mark ${item.status === 'resolved' ? 'resolved' : item.severity}`} />
              <span>
                <strong>{item.title}</strong>
                <small>{item.id} · {item.sku} · {item.zone}</small>
              </span>
            </span>
            <span className="system-tags">{item.system.split(' · ').map((system) => <em key={system}>{system}</em>)}</span>
            <span className="deadline">{item.status === 'resolved' ? 'Contained' : item.time_to_impact}</span>
            <strong className="impact-number">{currency(item.impact)}</strong>
            <span className="control-preview">
              <b>{item.status === 'resolved' ? '✓ resolved' : item.actions[0] ? `${item.actions[0].confidence}%` : '—'}</b>
              <small>{item.actions[0]?.title || 'Escalate for manual review'}</small>
            </span>
          </button>
        ))}
        {visible.length === 0 && (
          <div className="empty-state">
            <Filter size={24} />
            {filter === 'contained'
              ? <><h3>Nothing contained yet</h3><p>Approve every control on a finding and it moves here with its value.</p></>
              : <><h3>No open risks match this view</h3><p>The board is clear — change a filter, run a scan, or check Contained.</p></>}
          </div>
        )}
      </div>
      <footer className="risk-pager">
        <span className="risk-pager-count">
          {visible.length
            ? <>Showing <b>{startIndex + 1}–{Math.min(startIndex + rowsPerPage, visible.length)}</b> of {visible.length} findings</>
            : 'No findings in view'}
        </span>
        <div className="risk-pager-pages">
          <button
            className="risk-pager-step"
            disabled={currentPage <= 1}
            onClick={() => setPage(currentPage - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft size={13} />
          </button>
          {pageWindow(currentPage, totalPages).map((entry, index) => entry === 'gap'
            ? <span className="risk-pager-gap" key={`gap-${index}`}>…</span>
            : <button
                className={entry === currentPage ? 'active' : ''}
                key={entry}
                onClick={() => setPage(entry)}
                aria-current={entry === currentPage ? 'page' : undefined}
              >
                {entry}
              </button>)}
          <button
            className="risk-pager-step"
            disabled={currentPage >= totalPages}
            onClick={() => setPage(currentPage + 1)}
            aria-label="Next page"
          >
            <ChevronRight size={13} />
          </button>
        </div>
      </footer>
    </section>
  </div>
}

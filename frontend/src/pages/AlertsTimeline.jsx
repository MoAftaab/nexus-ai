import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Clock3, Filter, ShieldAlert, Sparkles } from 'lucide-react'
import { currency, severityLabel } from '../utils'

const PAGE_SIZE = 4

export function AlertsTimeline({ alerts, onSelectAnomaly }) {
  const [active, setActive] = useState('all')
  const [page, setPage] = useState(1)

  const visible = useMemo(
    () => (active === 'all' ? alerts : alerts?.filter((alert) => alert.severity === active)) || [],
    [alerts, active]
  )

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const paginated = useMemo(
    () => visible.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [visible, currentPage]
  )

  const handleFilter = (item) => {
    setActive(item)
    setPage(1)
  }

  const criticalCount = alerts?.filter((a) => a.severity === 'critical').length || 0

  return (
    <div className="page alerts-page">
      {/* Top Filter Bar */}
      <div className="alerts-topbar">
        <section className="alert-filter">
          <span><Filter size={13} /> Filter</span>
          {['all', 'critical', 'high', 'medium', 'low'].map((item) => {
            const count = item === 'all' ? alerts?.length || 0 : alerts?.filter((a) => a.severity === item).length || 0
            return (
              <button
                className={active === item ? 'active' : ''}
                key={item}
                onClick={() => handleFilter(item)}
              >
                {item === 'all' ? 'All alerts' : severityLabel(item)}
                <span className="filter-count">({count})</span>
              </button>
            )
          })}
        </section>

        <div className="alerts-header-stat">
          <Clock3 size={13} />
          <span>{criticalCount} critical deadlines active</span>
        </div>
      </div>

      {/* Main Alert Timeline Card */}
      <section className="alert-timeline card-surface">
        <div className="timeline-title-row">
          <div>
            <span className="eyebrow"><Sparkles size={13} /> Predicted deadline</span>
            <h3>Operational runway & risk alerts</h3>
          </div>
          <span className="alerts-page-indicator">
            Page {currentPage} of {totalPages} ({visible.length} total alerts)
          </span>
        </div>

        {/* List of 4 paginated cards */}
        <div className="alerts-list">
          {paginated.map((alert) => (
            <button
              className="alert-card"
              key={alert.id}
              onClick={() => onSelectAnomaly?.({ id: alert.id })}
            >
              <div className={`alert-clock ${alert.severity}`}>
                <Clock3 size={16} />
                <strong>{alert.when}</strong>
              </div>

              <div className="alert-copy">
                <div className="alert-copy-head">
                  <span className={`severity-pill ${alert.severity}`}>{severityLabel(alert.severity)}</span>
                  <small>Owner: {alert.owner}</small>
                </div>
                <h3>{alert.title}</h3>
                <p>{alert.detail}</p>
              </div>

              <div className="alert-impact">
                <span>Preventable exposure</span>
                <strong>{currency(alert.impact)}</strong>
                <ChevronRight size={18} />
              </div>
            </button>
          ))}

          {paginated.length === 0 && (
            <div className="alerts-empty-state">
              <ShieldAlert size={28} />
              <h4>No alerts for this filter</h4>
              <p>All clear in the {active} severity bracket.</p>
            </div>
          )}
        </div>

        {/* Bottom Pagination Control with 1 2 3 Buttons */}
        <div className="alerts-pagination-toolbar">
          <div className="pagination-info">
            Showing {visible.length > 0 ? (currentPage - 1) * PAGE_SIZE + 1 : 0}–{Math.min(currentPage * PAGE_SIZE, visible.length)} of {visible.length}
          </div>

          <div className="pagination-controls">
            <button
              className="pager-btn"
              disabled={currentPage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              title="Previous Page"
            >
              <ChevronLeft size={14} />
              <span>Prev</span>
            </button>

            {/* Page number buttons: 1, 2, 3... */}
            <div className="page-numbers">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <button
                  className={`page-num-btn ${currentPage === p ? 'active' : ''}`}
                  key={p}
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              ))}
            </div>

            <button
              className="pager-btn"
              disabled={currentPage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              title="Next Page"
            >
              <span>Next</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}


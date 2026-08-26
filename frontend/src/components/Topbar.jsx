import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, Bell, BellRing, CircleHelp, FileSearch, LayoutDashboard, LogOut, Menu, Moon, Radar, Scale, ScanLine, Search, Sparkles, Sun, X } from 'lucide-react'

export function Topbar({
  title,
  subtitle,
  theme = 'light',
  onToggleTheme,
  onMenu,
  onTour,
  onBell,
  onNotifications,
  onScan,
  scanning = false,
  escalationCount = 0,
  notificationCount = 0,
  principal = null,
  onSignOut = null,
  // Search props
  anomalies = [],
  alerts = [],
  reconciliation = null,
  onSelectAnomaly,
  onNavigate,
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)

  const userInitials = principal?.display_name
    ? principal.display_name.split(' ').map((w) => w[0]).slice(0, 2).join('')
    : principal?.email ? principal.email.slice(0, 2).toUpperCase() : 'OP'

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // ⌘K / Ctrl+K shortcut to focus search
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
      if (e.key === 'Escape') { setOpen(false); inputRef.current?.blur() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Pages searchable
  const pages = [
    { id: 'command', label: 'Command center', icon: LayoutDashboard, keywords: 'dashboard home overview kpi' },
    { id: 'intelligence', label: 'Risk intelligence', icon: Radar, keywords: 'anomaly risk findings agent' },
    { id: 'reconcile', label: 'Reconciliation', icon: Scale, keywords: 'inventory balance wms erp tms physical count' },
    { id: 'documents', label: 'Document control', icon: FileSearch, keywords: 'upload inspect ppap vda batch' },
    { id: 'alerts', label: 'Alert timeline', icon: Activity, keywords: 'deadline critical high medium low alert' },
  ]

  const buildResults = useCallback(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    const results = []

    // Search pages
    pages.forEach((p) => {
      if (p.label.toLowerCase().includes(q) || p.keywords.includes(q)) {
        results.push({ type: 'page', id: p.id, label: p.label, detail: 'Navigate to page', icon: '📄' })
      }
    })

    // Search anomalies
    anomalies.forEach((a) => {
      if (a.title?.toLowerCase().includes(q) || a.summary?.toLowerCase().includes(q) || a.id?.toLowerCase().includes(q) || a.type?.toLowerCase().includes(q)) {
        results.push({ type: 'anomaly', id: a.id, label: a.title, detail: `${a.severity?.toUpperCase()} · ${a.type || 'Anomaly'}`, icon: '⚠️', data: a })
      }
    })

    // Search alerts
    alerts.forEach((a) => {
      if (a.title?.toLowerCase().includes(q) || a.detail?.toLowerCase().includes(q) || a.owner?.toLowerCase().includes(q)) {
        results.push({ type: 'alert', id: a.id, label: a.title, detail: `${a.severity?.toUpperCase()} · ${a.owner || ''}`, icon: '🔔', data: a })
      }
    })

    // Search reconciliation rows
    reconciliation?.rows?.forEach((r) => {
      if (r.sku?.toLowerCase().includes(q) || r.description?.toLowerCase().includes(q) || r.bin?.toLowerCase().includes(q)) {
        results.push({ type: 'recon', id: r.id, label: r.sku, detail: `${r.description} · ${r.bin}`, icon: '📦' })
      }
    })

    return results.slice(0, 12) // cap at 12 results
  }, [query, anomalies, alerts, reconciliation])

  const results = open ? buildResults() : []

  const handleSelect = (result) => {
    setOpen(false)
    setQuery('')
    if (result.type === 'page') {
      onNavigate?.(result.id)
    } else if (result.type === 'anomaly') {
      onSelectAnomaly?.(result.data)
    } else if (result.type === 'alert') {
      onSelectAnomaly?.(result.data)
    } else if (result.type === 'recon') {
      onNavigate?.('reconcile')
    }
  }

  const categoryLabel = (type) => {
    switch (type) {
      case 'page': return 'Pages'
      case 'anomaly': return 'Anomalies'
      case 'alert': return 'Alerts'
      case 'recon': return 'Inventory'
      default: return 'Results'
    }
  }

  // Group results by type
  const grouped = results.reduce((acc, r) => {
    if (!acc[r.type]) acc[r.type] = []
    acc[r.type].push(r)
    return acc
  }, {})

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={18} /></button>
      <div className="page-ident">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <div className="global-search-wrap" ref={wrapRef}>
          <label className="global-search">
            <Search size={14} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
              onFocus={() => { if (query.trim()) setOpen(true) }}
              placeholder="Search anomalies, parts…"
            />
            {query ? (
              <button className="search-clear" onClick={() => { setQuery(''); setOpen(false); inputRef.current?.focus() }} aria-label="Clear search"><X size={12} /></button>
            ) : (
              <kbd>⌘ K</kbd>
            )}
          </label>

          {open && query.trim() && (
            <div className="search-dropdown">
              {results.length === 0 ? (
                <div className="search-empty">
                  <span>No results for "{query}"</span>
                  <small>Search anomalies, alerts, parts, SKUs, or pages</small>
                </div>
              ) : (
                Object.entries(grouped).map(([type, items]) => (
                  <div className="search-group" key={type}>
                    <div className="search-group-label">{categoryLabel(type)}</div>
                    {items.map((result) => (
                      <button
                        className="search-result"
                        key={`${result.type}-${result.id}`}
                        onClick={() => handleSelect(result)}
                      >
                        <span className="search-result-icon">{result.icon}</span>
                        <div className="search-result-text">
                          <strong>{result.label}</strong>
                          <small>{result.detail}</small>
                        </div>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <button
          className="topbar-scan-button primary-button"
          onClick={onScan}
          disabled={scanning}
          aria-label={scanning ? 'Scanning intelligence mesh' : 'Run intelligence scan'}
          title={scanning ? 'Scanning intelligence mesh' : 'Run intelligence scan'}
        >
          <ScanLine size={13} />
          <span>{scanning ? 'Scanning…' : 'Scan'}</span>
        </button>
        <button
          className={`theme-toggle-btn ${theme === 'dark' ? 'is-dark' : ''}`}
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
          <span className="theme-toggle-text">{theme === 'dark' ? 'Light' : 'Dark'}</span>
        </button>
        <button className="icon-button notification" onClick={onBell} aria-label="Escalation previews" title="Shift-manager escalations">
          <Bell size={14} />
          {escalationCount > 0 && <i />}
        </button>
        <button className="icon-button notification" onClick={onNotifications} aria-label="Open workflow notifications" title="Workflow notifications">
          <BellRing size={14} />
          {notificationCount > 0 && <i />}
        </button>

        {principal && onSignOut && (
          <button
            className="topbar-user-btn"
            onClick={onSignOut}
            aria-label="Sign out"
            title={`Signed in as ${principal.display_name || principal.email} · Click to sign out`}
          >
            <span className="topbar-avatar">{userInitials}</span>
            <LogOut size={13} className="topbar-logout-icon" />
            <span className="topbar-logout-label">Logout</span>
          </button>
        )}
      </div>
    </header>
  )
}

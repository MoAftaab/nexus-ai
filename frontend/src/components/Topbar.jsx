import { Bell, BellRing, CircleHelp, LogOut, Menu, Moon, ScanLine, Search, Sparkles, Sun } from 'lucide-react'

export function Topbar({
  title,
  subtitle,
  theme = 'light',
  onToggleTheme,
  onSearch,
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
}) {
  const userInitials = principal?.display_name
    ? principal.display_name.split(' ').map((w) => w[0]).slice(0, 2).join('')
    : principal?.email ? principal.email.slice(0, 2).toUpperCase() : 'OP'

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={18} /></button>
      <div className="page-ident">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <label className="global-search">
          <Search size={14} />
          <input onChange={(event) => onSearch?.(event.target.value)} placeholder="Search anomalies, parts…" />
          <kbd>⌘ K</kbd>
        </label>
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
        <button className="icon-button help-icon-btn" onClick={onTour} aria-label="Open demo tour" title="Demo tour">
          <CircleHelp size={14} />
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

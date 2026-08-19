import { Bell, BellRing, CircleHelp, Menu, Moon, ScanLine, Search, Sparkles, Sun } from 'lucide-react'

export function Topbar({ title, subtitle, theme = 'light', onToggleTheme, onSearch, onMenu, onTour, onBell, onNotifications, onScan, scanning = false, escalationCount = 0, notificationCount = 0 }) {
  return <header className="topbar">
    <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu /></button>
    <div className="page-ident"><h1>{title}</h1><p>{subtitle}</p></div>
    <div className="topbar-actions">
      <label className="global-search"><Search size={15} /><input onChange={(event) => onSearch?.(event.target.value)} placeholder="Search anomalies, parts, zones…" /><kbd>⌘ K</kbd></label>
      <button className="topbar-scan-button primary-button" onClick={onScan} disabled={scanning} aria-label={scanning ? 'Scanning intelligence mesh' : 'Run intelligence scan'} title={scanning ? 'Scanning intelligence mesh' : 'Run intelligence scan'}>
        <ScanLine size={14} /><span>{scanning ? 'Scanning…' : 'Run intelligence'}</span>
      </button>
      <button
        className={`theme-toggle-btn ${theme === 'dark' ? 'is-dark' : ''}`}
        onClick={onToggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      >
        {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
        <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
      </button>
      <button className="icon-button" aria-label="AI status"><Sparkles size={15} /></button>
      <button className="icon-button notification" onClick={onBell} aria-label="Escalation previews" title="Shift-manager escalations"><Bell size={15} />{escalationCount > 0 && <i />}</button>
      <button className="icon-button notification" onClick={onNotifications} aria-label="Open workflow notifications" title="Workflow notifications"><BellRing size={15} />{notificationCount > 0 && <i />}</button>
      <button className="icon-button help" onClick={onTour} aria-label="Open demo tour" title="Demo tour"><CircleHelp size={15} /></button>
    </div>
  </header>
}

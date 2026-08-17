import { Bell, BellRing, CircleHelp, Menu, Moon, Search, Sparkles, Sun } from 'lucide-react'

export function Topbar({ title, subtitle, theme = 'light', onToggleTheme, onSearch, onMenu, onTour, onBell, onNotifications, escalationCount = 0, notificationCount = 0 }) {
  return <header className="topbar">
    <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu /></button>
    <div className="page-ident"><h1>{title}</h1><p>{subtitle}</p></div>
    <div className="topbar-actions">
      <label className="global-search"><Search size={17} /><input onChange={(event) => onSearch?.(event.target.value)} placeholder="Search anomalies, parts, zones…" /><kbd>⌘ K</kbd></label>
      <button
        className={`theme-toggle-btn ${theme === 'dark' ? 'is-dark' : ''}`}
        onClick={onToggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      >
        {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
      </button>
      <button className="icon-button" aria-label="AI status"><Sparkles size={18} /></button>
      <button className="icon-button notification" onClick={onBell} aria-label="Escalation previews" title="Shift-manager escalations"><Bell size={18} />{escalationCount > 0 && <i />}</button>
      <button className="icon-button notification" onClick={onNotifications} aria-label="Open workflow notifications" title="Workflow notifications"><BellRing size={18} />{notificationCount > 0 && <i />}</button>
      <button className="icon-button help" onClick={onTour} aria-label="Open demo tour" title="Demo tour"><CircleHelp size={18} /></button>
    </div>
  </header>
}

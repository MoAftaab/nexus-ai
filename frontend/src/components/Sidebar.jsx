import { Activity, FileClock, FileSearch, GitPullRequest, KeyRound, LayoutDashboard, LogOut, Radar, Scale, ShieldCheck, X } from 'lucide-react'
import { VwLogo } from './VwLogo'

const operationsNav = [
  { id: 'command', label: 'Command center', icon: LayoutDashboard },
  { id: 'intelligence', label: 'Risk intelligence', icon: Radar },
  { id: 'reconcile', label: 'Reconciliation', icon: Scale },
  { id: 'documents', label: 'Document control', icon: FileSearch },
  { id: 'alerts', label: 'Alert timeline', icon: Activity },
  { id: 'changes', label: 'Change control', icon: GitPullRequest },
]

export function Sidebar({ activePage, onNavigate, alertCount = 0, onClose, principal, onSignOut }) {
  return <aside className="sidebar">
    <button className="sidebar-close" onClick={onClose} aria-label="Close navigation"><X size={19} /></button>
    <button className="brand" onClick={() => onNavigate('home')} aria-label="Go to landing page">
      <VwLogo size={30} className="brand-vw-logo" />
      <span><strong>Warehouse Control Tower AI</strong><em>Enterprise</em></span>
    </button>
    <div className="workspace-switcher">
      <span className="workspace-dot" />
      <div className="workspace-info">
        <strong>{principal?.permitted_sites?.length === 1 ? principal.permitted_sites[0] : 'Multi-site'}</strong>
        <small>Active workspace</small>
      </div>
      <span className="switcher-chevron">⌄</span>
    </div>

    <nav className="main-nav" aria-label="Primary navigation">
      <div className="nav-group">
        <p className="nav-label">Operations</p>
        {operationsNav.map(({ id, label, icon: Icon }) => (
          <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => onNavigate(id)}>
            <span className="nav-icon"><Icon size={17} strokeWidth={1.8} /></span>
            <span>{label}</span>
            {id === 'alerts' && alertCount > 0 && <b className="nav-badge-alert">{alertCount}</b>}
          </button>
        ))}
      </div>

      {(principal?.role === 'auditor' || principal?.role === 'admin') && (
        <div className="nav-group">
          <p className="nav-label">Governance</p>
          {principal?.role === 'auditor' && (
            <button className={`nav-item ${activePage === 'archive' ? 'active' : ''}`} onClick={() => onNavigate('archive')}>
              <span className="nav-icon"><FileClock size={17} strokeWidth={1.8} /></span>
              <span>Audit archive</span>
            </button>
          )}
          {principal?.role === 'admin' && (
            <button className={`nav-item ${activePage === 'policy' ? 'active' : ''}`} onClick={() => onNavigate('policy')}>
              <span className="nav-icon"><KeyRound size={17} strokeWidth={1.8} /></span>
              <span>Access & policy</span>
            </button>
          )}
        </div>
      )}
    </nav>

    <div className="sidebar-bottom">
      <div className="system-pill">
        <ShieldCheck size={15} />
        <span>Governed AI · Multi-site secure</span>
      </div>
      <div className="operator">
        <div className="avatar">{principal?.display_name?.split(' ').map((word) => word[0]).slice(0, 2).join('') || 'CT'}</div>
        <div className="operator-details">
          <strong>{principal?.display_name || 'Control Tower operator'}</strong>
          <span>{principal?.role?.replaceAll('_', ' ') || 'Workspace user'}</span>
        </div>
        <button className="signout-btn" aria-label="Sign out" title="Sign out" onClick={onSignOut}>
          <LogOut size={15} />
        </button>
      </div>
    </div>
  </aside>
}

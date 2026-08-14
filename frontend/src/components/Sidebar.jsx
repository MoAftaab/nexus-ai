import { Activity, BookOpen, Bot, Cpu, FileClock, FileSearch, GitFork, GitPullRequest, HandCoins, KeyRound, LayoutDashboard, LogOut, Radar, Scale, ShieldCheck, X } from 'lucide-react'
import { VwLogo } from './VwLogo'

const navigation = [
  { id: 'command', label: 'Command center', icon: LayoutDashboard },
  { id: 'cascade', label: 'Cascade map', icon: GitFork },
  { id: 'intelligence', label: 'Risk intelligence', icon: Radar },
  { id: 'reconcile', label: 'Reconciliation', icon: Scale },
  { id: 'agents', label: 'Agent workspace', icon: Bot },
  { id: 'documents', label: 'Document control', icon: FileSearch },
  { id: 'alerts', label: 'Alert timeline', icon: Activity },
  { id: 'outcomes', label: 'Outcomes', icon: HandCoins },
  { id: 'system', label: 'System health', icon: Cpu },
  { id: 'terms', label: 'Key terms', icon: BookOpen },
  { id: 'changes', label: 'Change control', icon: GitPullRequest },
  { id: 'archive', label: 'Audit archive', icon: FileClock },
]

export function Sidebar({ activePage, onNavigate, alertCount = 0, onClose, principal, onSignOut }) {
  return <aside className="sidebar">
    <button className="sidebar-close" onClick={onClose} aria-label="Close navigation"><X size={19} /></button>
    <button className="brand" onClick={() => onNavigate('home')} aria-label="Go to landing page">
      <VwLogo size={30} className="brand-vw-logo" />
      <span><strong>Warehouse Control Tower</strong><em>AI</em></span>
    </button>
    <div className="workspace-switcher"><span className="workspace-dot" />{principal?.permitted_sites?.length === 1 ? principal.permitted_sites[0] : 'Multi-site'} workspace <span className="switcher-chevron">⌄</span></div>
    <nav className="main-nav" aria-label="Primary navigation">
      <p className="nav-label">Operations</p>
      {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => onNavigate(id)}>
        <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{id === 'alerts' && alertCount > 0 && <b>{alertCount}</b>}
      </button>)}
      {principal?.role === 'admin' && <button className={`nav-item ${activePage === 'policy' ? 'active' : ''}`} onClick={() => onNavigate('policy')}><KeyRound size={18} strokeWidth={1.8} /><span>Access & policy</span></button>}
    </nav>
    <div className="sidebar-bottom">
      <div className="system-pill"><ShieldCheck size={16} /><span>Secure workspace</span></div>
      <div className="operator"><div className="avatar">{principal?.display_name?.split(' ').map((word) => word[0]).slice(0, 2).join('') || 'CT'}</div><div><strong>{principal?.display_name || 'Control Tower operator'}</strong><span>{principal?.role?.replaceAll('_', ' ') || 'Workspace user'}</span></div><button aria-label="Sign out" onClick={onSignOut}><LogOut size={15} /></button></div>
    </div>
  </aside>
}

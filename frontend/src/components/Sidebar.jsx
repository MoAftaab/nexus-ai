import { Activity, BookOpen, Bot, Cpu, FileSearch, GitFork, HandCoins, LayoutDashboard, Radar, Scale, ShieldCheck, X } from 'lucide-react'

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
]

export function Sidebar({ activePage, onNavigate, alertCount = 0, onClose }) {
  return <aside className="sidebar">
    <button className="sidebar-close" onClick={onClose} aria-label="Close navigation"><X size={19} /></button>
    <button className="brand" onClick={() => onNavigate('home')} aria-label="Go to landing page">
      <span className="brand-mark"><span /><span /><span /></span>
      <span><strong>Nexus</strong><em>AI</em></span>
    </button>
    <div className="workspace-switcher"><span className="workspace-dot" />VW · Wolfsburg DC <span className="switcher-chevron">⌄</span></div>
    <nav className="main-nav" aria-label="Primary navigation">
      <p className="nav-label">Operations</p>
      {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => onNavigate(id)}>
        <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{id === 'alerts' && alertCount > 0 && <b>{alertCount}</b>}
      </button>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="system-pill"><ShieldCheck size={16} /><span>Secure workspace</span></div>
      <div className="operator"><div className="avatar">AM</div><div><strong>Alex Morgan</strong><span>Operations lead</span></div><button aria-label="Open profile">•••</button></div>
    </div>
  </aside>
}


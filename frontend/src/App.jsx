import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, LoaderCircle, RefreshCw, Wifi } from 'lucide-react'
import { api, clearSession, session } from './api'
import { AnomalyDrawer } from './components/AnomalyDrawer'
import { ApprovalHierarchy } from './components/ApprovalHierarchy'
import { AgentLauncher } from './components/AgentLauncher'
import { DemoTour } from './components/DemoTour'
import { EscalationPanel } from './components/EscalationPanel'
import { NotificationPanel } from './components/NotificationPanel'
import { Sidebar } from './components/Sidebar'
import { Toast } from './components/Toast'
import { Topbar } from './components/Topbar'
import { AgentWorkspace } from './pages/AgentWorkspace'
import { AlertsTimeline } from './pages/AlertsTimeline'
import { CommandCenter } from './pages/CommandCenter'
import { Documents } from './pages/Documents'
import { KeyTerms } from './pages/KeyTerms'
import { Landing } from './pages/Landing'
import { Outcomes } from './pages/Outcomes'
import { Reconciliation } from './pages/Reconciliation'
import { RiskIntelligence } from './pages/RiskIntelligence'
import { SystemHealth } from './pages/SystemHealth'
import { SignIn } from './pages/SignIn'
import { ChangeControl } from './pages/ChangeControl'
import { AuditArchive } from './pages/AuditArchive'
import { AccessPolicyConsole } from './pages/AccessPolicyConsole'
import { nextTheme, normalizeTheme } from './utils/theme'

const pageInfo = {
  command: ['Command center', 'Operational intelligence, one shift ahead'],
  intelligence: ['Risk intelligence', 'Prioritize the controls that protect the line'],
  reconcile: ['Reconciliation', 'Find the transaction where inventory drift began'],
  agents: ['Agent workspace', 'Evidence-led multi-agent operations reasoning'],
  documents: ['Document control', 'Extract, cross-check and release with confidence'],
  alerts: ['Alert timeline', 'The deadlines that matter before they arrive'],
  outcomes: ['Outcomes', 'Every approved control and its measured value'],
  system: ['System health', 'Models, endpoints and runtime, measured live'],
  terms: ['Key terms', 'The domain, explained the way you’d say it out loud'],
}

pageInfo.changes = ['Change control', 'The approval chain, snapshots, and verified execution']
pageInfo.archive = ['Audit archive', 'Immutable evidence for every governed decision']
pageInfo.policy = ['Access & policy', 'Seeded identities, site scopes, and routing rules']

export default function App() {
  const [page, setPage] = useState(() => window.location.hash.slice(1) || 'home')
  const [principal, setPrincipal] = useState(() => session()?.user || null)
  const [theme, setTheme] = useState(() => {
    try { return normalizeTheme(window.localStorage.getItem('nexusai.theme'), window.matchMedia('(prefers-color-scheme: dark)').matches) } catch { return 'light' }
  })
  const [dashboard, setDashboard] = useState(null); const [anomalies, setAnomalies] = useState([])
  const [agentData, setAgentData] = useState(null); const [reconciliation, setReconciliation] = useState(null); const [documentData, setDocumentData] = useState(null); const [alerts, setAlerts] = useState([]); const [outcomeData, setOutcomeData] = useState(null)
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [drawer, setDrawer] = useState(null); const [applying, setApplying] = useState(false); const [scanning, setScanning] = useState(false); const [toast, setToast] = useState(''); const [sidebarOpen, setSidebarOpen] = useState(false); const [pulse, setPulse] = useState(null); const [tourOpen, setTourOpen] = useState(false); const [bellOpen, setBellOpen] = useState(false); const [notificationOpen, setNotificationOpen] = useState(false); const [workflowData, setWorkflowData] = useState(null); const [changeRequests, setChangeRequests] = useState([]); const [notifications, setNotifications] = useState([]); const [changeFocus, setChangeFocus] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { window.localStorage.setItem('nexusai.theme', theme) } catch { /* ignore */ }
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((curr) => nextTheme(curr))
  }, [])

  const loadCore = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [nextDashboard, nextAnomalies, nextAgents, nextReconciliation, nextDocuments, nextAlerts, nextOutcomes, nextWorkflow, nextChanges, nextNotifications] = await Promise.all([api.dashboard(), api.anomalies(), api.agents(), api.reconciliation(), api.documents(), api.alerts(), api.outcomes(), principal ? api.workflowSummary().catch(() => null) : Promise.resolve(null), principal ? api.changes().catch(() => ({ items: [] })) : Promise.resolve({ items: [] }), principal ? api.notifications().catch(() => ({ items: [] })) : Promise.resolve({ items: [] })])
      setDashboard(nextDashboard); setAnomalies(nextAnomalies.items); setAgentData(nextAgents); setReconciliation(nextReconciliation); setDocumentData(nextDocuments); setAlerts(nextAlerts.items); setOutcomeData(nextOutcomes); setWorkflowData(nextWorkflow); setChangeRequests(nextChanges.items || []); setNotifications(nextNotifications.items || [])
    } catch (cause) { setError(`Warehouse Control Tower AI could not reach its operations API. ${cause.message}`) } finally { setLoading(false) }
  }, [principal])
  const refreshFromEvent = useCallback(async (message) => {
    if (!['action_applied', 'scan_complete', 'document_ingested', 'approval_decided', 'change_applied', 'change_verified', 'approval_stage_activated', 'change_submitted', 'change_rejected', 'change_returned', 'change_rollback', 'change_cancelled', 'reminder_confirmed', 'escalation_confirmed'].includes(message.type)) return
    try {
      const [nextDashboard, nextAnomalies, nextDocuments, nextAlerts, nextOutcomes, nextChanges, nextNotifications] = await Promise.all([api.dashboard(), api.anomalies(), api.documents(), api.alerts(), api.outcomes(), principal ? api.changes().catch(() => ({ items: [] })) : Promise.resolve({ items: [] }), principal ? api.notifications().catch(() => ({ items: [] })) : Promise.resolve({ items: [] })])
      setDashboard(nextDashboard); setAnomalies(nextAnomalies.items); setDocumentData(nextDocuments); setAlerts(nextAlerts.items); setOutcomeData(nextOutcomes); setChangeRequests(nextChanges.items || []); setNotifications(nextNotifications.items || []); if (principal) setWorkflowData(await api.workflowSummary().catch(() => null))
      const label = message.type === 'scan_complete' ? 'Live scan completed' : message.type === 'document_ingested' ? 'Document indexed and added to context' : 'Control application recorded'
      setToast(label)
    } catch { /* A later heartbeat or manual refresh will retry transient failures. */ }
  }, [principal])
  useEffect(() => {
    if (!principal) return undefined
    const timer = window.setInterval(() => { api.notifications().then((response) => setNotifications(response.items || [])).catch(() => null) }, 10000)
    return () => window.clearInterval(timer)
  }, [principal])
  useEffect(() => { loadCore() }, [loadCore])
  useEffect(() => { const onHash = () => setPage(window.location.hash.slice(1) || 'home'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash) }, [])
  // Mobile sidebar: close on Escape and lock body scroll while open.
  useEffect(() => {
    if (!sidebarOpen) return
    const onKey = (event) => { if (event.key === 'Escape') setSidebarOpen(false) }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [sidebarOpen])
  // Ctrl+Shift+X: inject a live incident into the twin (presenter shortcut).
  // Not Ctrl+Shift+I — Chrome claims that for DevTools. Disabled on the landing
  // page, where no Toast is mounted to confirm the injection.
  useEffect(() => {
    const onKey = async (event) => {
      if (!(event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'x')) return
      if ((window.location.hash.slice(1) || 'home') === 'home') return
      event.preventDefault()
      try {
        const result = await api.injectIncident()
        setToast(result.injected ? `Live incident: ${result.incident.story}` : result.detail)
      } catch (cause) { setToast(cause.message) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => {
    if (!principal) return undefined
    let socket; let retry; let disposed = false
    const connect = () => {
      // When the API lives on another origin (deployed split), derive the WS
      // endpoint from VITE_API_URL; locally the Vite proxy forwards /ws.
      const apiBase = import.meta.env.VITE_API_URL
      const wsBase = apiBase ? apiBase.replace(/^http/, 'ws') : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
      const token = session()?.session_token
      socket = new WebSocket(`${wsBase}/ws/operations${token ? `?token=${encodeURIComponent(token)}` : ''}`)
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          // Only heartbeats carry active_findings; action/document events would
          // render "undefined active signals" in the indicator.
          if (message.type === 'pulse') setPulse(message)
          void refreshFromEvent(message)
        } catch { /* Ignore malformed live events. */ }
      }
      socket.onclose = () => { if (!disposed) retry = window.setTimeout(connect, 2500) }
    }
    connect()
    return () => { disposed = true; window.clearTimeout(retry); socket?.close() }
  }, [principal, refreshFromEvent])
  const navigate = (next) => { window.location.hash = next; setPage(next); setSidebarOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const selectAnomaly = async (candidate) => { const id = candidate?.id; if (!id) return; try { const full = candidate?.actions ? candidate : await api.anomaly(id); setDrawer(full) } catch (cause) { setToast(cause.message) } }
  const applyAction = async (anomalyId, actionId) => { setApplying(true); try { const preview = await api.changePreview({ anomaly_id: anomalyId, action_id: actionId }); const draft = await api.createChange(preview); const request = await api.submitChange(draft.request_id); setChangeRequests((current) => [request, ...current.filter((item) => item.request_id !== request.request_id)]); setChangeFocus(request.request_id); setToast(`${request.request_id} sent to ${request.current_owner?.label || 'the next approver'}`); setDrawer(null); navigate('changes') } catch (cause) { setToast(cause.message) } finally { setApplying(false) } }
  const runScan = async () => { setScanning(true); try { const result = await api.scan(); setToast(`${result.scan_id} completed — ${result.findings} active findings reviewed.`); setDashboard(await api.dashboard()) } catch (cause) { setToast(cause.message) } finally { setScanning(false) } }
  const inspectDocument = useCallback(async (file) => { const result = await api.inspectDocument(file); setDocumentData(await api.documents()); return result }, [])
  const visiblePage = page === 'cascade' || (page === 'archive' && principal?.role !== 'auditor') ? 'command' : page
  const content = useMemo(() => {
    const props = { anomalies, onNavigate: navigate, onSelectAnomaly: selectAnomaly }
    if (visiblePage === 'intelligence') return <RiskIntelligence anomalies={anomalies} onSelectAnomaly={selectAnomaly} />
    if (visiblePage === 'reconcile') return <Reconciliation data={reconciliation} onSelectAnomaly={selectAnomaly} />
    if (visiblePage === 'agents') return <AgentWorkspace agents={agentData?.agents} communication={agentData?.communication} onChatStream={api.chatStream} onSelectAnomaly={selectAnomaly} />
    if (visiblePage === 'documents') return <Documents onInspect={inspectDocument} documentData={documentData} />
    if (visiblePage === 'alerts') return <AlertsTimeline alerts={alerts} onSelectAnomaly={selectAnomaly} />
    if (visiblePage === 'outcomes') return <Outcomes outcomes={outcomeData} onSelectAnomaly={selectAnomaly} />
    if (visiblePage === 'system') return <SystemHealth />
    if (visiblePage === 'terms') return <KeyTerms />
    if (visiblePage === 'changes') return <ChangeControl principal={principal} focusRequestId={changeFocus} onWorkflowChanged={loadCore} />
    if (visiblePage === 'archive') return <AuditArchive />
    if (visiblePage === 'policy') return <AccessPolicyConsole />
    return <CommandCenter {...props} dashboard={dashboard} workflow={workflowData} onScan={runScan} scanning={scanning} />
  }, [visiblePage, anomalies, dashboard, reconciliation, documentData, agentData, alerts, outcomeData, workflowData, inspectDocument, scanning, principal, changeFocus, loadCore])
  const [title, subtitle] = pageInfo[visiblePage] || pageInfo.command
  const openAlerts = anomalies.filter((item) => item.status !== 'resolved')
  const escalationCount = openAlerts.filter((item) => ['critical', 'high'].includes(item.severity)).length
  const currentRequest = changeRequests.find((item) => String(item.status).startsWith('awaiting_')) || changeRequests[0]
  const fallbackWorkflowPreview = !currentRequest && openAlerts[0] ? { severity: openAlerts[0].severity, impact_euros: openAlerts[0].impact, title: openAlerts[0].title } : null
  // The landing page owns the full viewport — no sidebar, topbar or drawers.
  if (page === 'home') return <Landing onEnter={() => navigate(principal ? 'command' : 'signin')} theme={theme} onToggleTheme={toggleTheme} />
  if (page === 'signin' || !principal) return <SignIn onSignedIn={(user) => { setPrincipal(user); navigate(page === 'signin' ? 'command' : page) }} />
  return <div className="app-shell">
    {sidebarOpen && <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />}
    <div className={`sidebar-wrap ${sidebarOpen ? 'open' : ''}`}><Sidebar activePage={visiblePage} onNavigate={navigate} alertCount={openAlerts.length} onClose={() => setSidebarOpen(false)} principal={principal} onSignOut={async () => { await api.signOut().catch(() => null); clearSession(); setPrincipal(null); navigate('signin') }} /></div>
    <main className="main-shell"><Topbar title={title} subtitle={subtitle} theme={theme} onToggleTheme={toggleTheme} onMenu={() => setSidebarOpen((open) => !open)} onTour={() => setTourOpen(true)} onBell={() => setBellOpen((open) => !open)} onNotifications={() => setNotificationOpen((open) => !open)} escalationCount={escalationCount} notificationCount={notifications.filter((item) => !item.read).length} />{pulse && <div className="realtime-indicator"><Wifi size={13} />Mesh live · {pulse.active_findings} active signals</div>}<div className="global-approval-flow"><ApprovalHierarchy compact request={currentRequest} preview={fallbackWorkflowPreview} onOpenLedger={() => navigate('changes')} /></div>
      {loading ? <div className="app-loading"><div className="loading-orbit"><LoaderCircle className="spin" size={31} /></div><h2>Warming the operational twin</h2><p>Loading specialist-agent context and synthetic logistics signals…</p></div> : error ? <div className="connection-error"><AlertTriangle size={25} /><h2>Operations API unavailable</h2><p>{error}</p><button className="primary-button" onClick={loadCore}><RefreshCw size={16} />Try again</button></div> : content}
    </main>
    <AnomalyDrawer anomaly={drawer} onClose={() => setDrawer(null)} onApply={applyAction} applying={applying} />
    <DemoTour open={tourOpen} onClose={() => setTourOpen(false)} onNavigate={navigate} onReset={loadCore} />
    <EscalationPanel open={bellOpen} onClose={() => setBellOpen(false)} onSelectAnomaly={selectAnomaly} />
    <NotificationPanel open={notificationOpen} onClose={() => setNotificationOpen(false)} notifications={notifications} onRead={async (item) => { if (!item.read) { await api.markNotificationRead(item.notification_id).catch(() => null); setNotifications((current) => current.map((entry) => entry.notification_id === item.notification_id ? { ...entry, read: true } : entry)) } }} onOpenChange={(requestId) => { setChangeFocus(requestId); navigate('changes') }} />
    <AgentLauncher
      anomalies={anomalies}
      capabilities={workflowData?.assistant_capabilities}
      currentPage={visiblePage}
      dashboard={dashboard}
      onChatStream={api.chatStream}
      onWaltResolve={api.waltResolve}
      onWaltConfirm={api.confirmWaltAction}
      onWaltFeedback={api.waltFeedback}
      requestId={currentRequest?.request_id}
      requestActions={currentRequest?.allowed_actions || []}
      riskCount={escalationCount}
    />
    <Toast message={toast} onClose={() => setToast('')} />
  </div>
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, LoaderCircle, RefreshCw, Wifi } from 'lucide-react'
import { api } from './api'
import { AnomalyDrawer } from './components/AnomalyDrawer'
import { DemoTour } from './components/DemoTour'
import { EscalationPanel } from './components/EscalationPanel'
import { Sidebar } from './components/Sidebar'
import { Toast } from './components/Toast'
import { Topbar } from './components/Topbar'
import { AgentWorkspace } from './pages/AgentWorkspace'
import { AlertsTimeline } from './pages/AlertsTimeline'
import { CascadeMap } from './pages/CascadeMap'
import { CommandCenter } from './pages/CommandCenter'
import { Documents } from './pages/Documents'
import { KeyTerms } from './pages/KeyTerms'
import { Landing } from './pages/Landing'
import { Outcomes } from './pages/Outcomes'
import { Reconciliation } from './pages/Reconciliation'
import { RiskIntelligence } from './pages/RiskIntelligence'
import { SystemHealth } from './pages/SystemHealth'

const pageInfo = {
  command: ['Command center', 'Operational intelligence, one shift ahead'],
  cascade: ['Cascade map', 'Dependency graph and outcome simulation'],
  intelligence: ['Risk intelligence', 'Prioritize the controls that protect the line'],
  reconcile: ['Reconciliation', 'Find the transaction where inventory drift began'],
  agents: ['Agent workspace', 'Evidence-led multi-agent operations reasoning'],
  documents: ['Document control', 'Extract, cross-check and release with confidence'],
  alerts: ['Alert timeline', 'The deadlines that matter before they arrive'],
  outcomes: ['Outcomes', 'Every approved control and its measured value'],
  system: ['System health', 'Models, endpoints and runtime, measured live'],
  terms: ['Key terms', 'The domain, explained the way you’d say it out loud'],
}

export default function App() {
  const [page, setPage] = useState(() => window.location.hash.slice(1) || 'home')
  const [dashboard, setDashboard] = useState(null); const [anomalies, setAnomalies] = useState([]); const [graph, setGraph] = useState(null)
  const [agentData, setAgentData] = useState(null); const [reconciliation, setReconciliation] = useState(null); const [documentData, setDocumentData] = useState(null); const [alerts, setAlerts] = useState([]); const [outcomeData, setOutcomeData] = useState(null)
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [drawer, setDrawer] = useState(null); const [applying, setApplying] = useState(false); const [scanning, setScanning] = useState(false); const [toast, setToast] = useState(''); const [sidebarOpen, setSidebarOpen] = useState(false); const [pulse, setPulse] = useState(null); const [tourOpen, setTourOpen] = useState(false); const [bellOpen, setBellOpen] = useState(false)

  const loadCore = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [nextDashboard, nextAnomalies, nextGraph, nextAgents, nextReconciliation, nextDocuments, nextAlerts, nextOutcomes] = await Promise.all([api.dashboard(), api.anomalies(), api.graph(), api.agents(), api.reconciliation(), api.documents(), api.alerts(), api.outcomes()])
      setDashboard(nextDashboard); setAnomalies(nextAnomalies.items); setGraph(nextGraph); setAgentData(nextAgents); setReconciliation(nextReconciliation); setDocumentData(nextDocuments); setAlerts(nextAlerts.items); setOutcomeData(nextOutcomes)
    } catch (cause) { setError(`NexusAI could not reach its operations API. ${cause.message}`) } finally { setLoading(false) }
  }, [])
  const refreshFromEvent = useCallback(async (message) => {
    if (!['action_applied', 'scan_complete', 'document_ingested'].includes(message.type)) return
    try {
      const [nextDashboard, nextAnomalies, nextDocuments, nextAlerts, nextOutcomes, nextGraph] = await Promise.all([api.dashboard(), api.anomalies(), api.documents(), api.alerts(), api.outcomes(), api.graph()])
      setDashboard(nextDashboard); setAnomalies(nextAnomalies.items); setDocumentData(nextDocuments); setAlerts(nextAlerts.items); setOutcomeData(nextOutcomes); setGraph(nextGraph)
      const label = message.type === 'scan_complete' ? 'Live scan completed' : message.type === 'document_ingested' ? 'Document indexed and added to context' : 'Control application recorded'
      setToast(label)
    } catch { /* A later heartbeat or manual refresh will retry transient failures. */ }
  }, [])
  useEffect(() => { loadCore() }, [loadCore])
  useEffect(() => { const onHash = () => setPage(window.location.hash.slice(1) || 'home'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash) }, [])
  // Ctrl+Shift+I: inject a live incident into the twin (presenter shortcut).
  useEffect(() => {
    const onKey = async (event) => {
      if (!(event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'i')) return
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
    let socket; let retry; let disposed = false
    const connect = () => {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/operations`)
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data); setPulse(message); void refreshFromEvent(message)
        } catch { /* Ignore malformed live events. */ }
      }
      socket.onclose = () => { if (!disposed) retry = window.setTimeout(connect, 2500) }
    }
    connect()
    return () => { disposed = true; window.clearTimeout(retry); socket?.close() }
  }, [refreshFromEvent])
  const navigate = (next) => { window.location.hash = next; setPage(next); setSidebarOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const loadGraph = useCallback(async (anomalyId) => { try { setGraph(await api.graph(anomalyId)) } catch (cause) { setToast(cause.message) } }, [])
  const selectAnomaly = async (candidate) => { const id = candidate?.id; if (!id) return; try { const full = candidate?.actions ? candidate : await api.anomaly(id); setDrawer(full) } catch (cause) { setToast(cause.message) } }
  const applyAction = async (anomalyId, actionId) => { setApplying(true); try { const result = await api.applyAction(anomalyId, actionId); setDrawer(result.anomaly); setToast(result.message); const [freshDashboard, freshAnomalies, freshOutcomes, freshGraph] = await Promise.all([api.dashboard(), api.anomalies(), api.outcomes(), api.graph()]); setDashboard(freshDashboard); setAnomalies(freshAnomalies.items); setOutcomeData(freshOutcomes); setGraph(freshGraph) } catch (cause) { setToast(cause.message) } finally { setApplying(false) } }
  const runScan = async () => { setScanning(true); try { const result = await api.scan(); setToast(`${result.scan_id} completed — ${result.findings} active findings reviewed.`); setDashboard(await api.dashboard()) } catch (cause) { setToast(cause.message) } finally { setScanning(false) } }
  const inspectDocument = useCallback(async (file) => { const result = await api.inspectDocument(file); setDocumentData(await api.documents()); return result }, [])
  const content = useMemo(() => {
    const props = { anomalies, graph, onNavigate: navigate, onSelectAnomaly: selectAnomaly }
    if (page === 'cascade') return <CascadeMap {...props} onLoadGraph={loadGraph} />
    if (page === 'intelligence') return <RiskIntelligence anomalies={anomalies} onSelectAnomaly={selectAnomaly} />
    if (page === 'reconcile') return <Reconciliation data={reconciliation} onSelectAnomaly={selectAnomaly} />
    if (page === 'agents') return <AgentWorkspace agents={agentData?.agents} communication={agentData?.communication} onChatStream={api.chatStream} />
    if (page === 'documents') return <Documents onInspect={inspectDocument} documentData={documentData} />
    if (page === 'alerts') return <AlertsTimeline alerts={alerts} onSelectAnomaly={selectAnomaly} />
    if (page === 'outcomes') return <Outcomes outcomes={outcomeData} onSelectAnomaly={selectAnomaly} />
    if (page === 'system') return <SystemHealth />
    if (page === 'terms') return <KeyTerms />
    return <CommandCenter {...props} dashboard={dashboard} onScan={runScan} scanning={scanning} />
  }, [page, anomalies, graph, dashboard, reconciliation, documentData, agentData, alerts, outcomeData, loadGraph, inspectDocument, scanning])
  const [title, subtitle] = pageInfo[page] || pageInfo.command
  const openAlerts = anomalies.filter((item) => item.status !== 'resolved')
  const escalationCount = openAlerts.filter((item) => ['critical', 'high'].includes(item.severity)).length
  // The landing page owns the full viewport — no sidebar, topbar or drawers.
  if (page === 'home') return <Landing onEnter={() => navigate('command')} />
  return <div className="app-shell">
    <div className={`sidebar-wrap ${sidebarOpen ? 'open' : ''}`}><Sidebar activePage={page} onNavigate={navigate} alertCount={openAlerts.length} /></div>
    <main className="main-shell"><Topbar title={title} subtitle={subtitle} onMenu={() => setSidebarOpen((open) => !open)} onTour={() => setTourOpen(true)} onBell={() => setBellOpen((open) => !open)} escalationCount={escalationCount} />{pulse && <div className="realtime-indicator"><Wifi size={13} />Mesh live · {pulse.active_findings} active signals</div>}
      {loading ? <div className="app-loading"><div className="loading-orbit"><LoaderCircle className="spin" size={31} /></div><h2>Warming the operational twin</h2><p>Loading specialist-agent context and synthetic logistics signals…</p></div> : error ? <div className="connection-error"><AlertTriangle size={25} /><h2>Operations API unavailable</h2><p>{error}</p><button className="primary-button" onClick={loadCore}><RefreshCw size={16} />Try again</button></div> : content}
    </main>
    <AnomalyDrawer anomaly={drawer} onClose={() => setDrawer(null)} onApply={applyAction} applying={applying} />
    <DemoTour open={tourOpen} onClose={() => setTourOpen(false)} onNavigate={navigate} onReset={loadCore} />
    <EscalationPanel open={bellOpen} onClose={() => setBellOpen(false)} onSelectAnomaly={selectAnomaly} />
    <Toast message={toast} onClose={() => setToast('')} />
  </div>
}

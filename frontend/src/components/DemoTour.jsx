import { useEffect, useState } from 'react'
import { Check, ChevronRight, CloudLightning, LoaderCircle, Presentation, RotateCcw, X, Zap } from 'lucide-react'
import { api } from '../api'

const script = [
  { page: 'command', title: 'Open on the money', line: '"NexusAI is watching a 72,900-record warehouse twin. Right now it sees €2.9M of exposure across 11 verified findings — before a single customer notices."' },
  { page: 'cascade', title: 'Show one cascade', line: '"This single fitment conflict is €1.2M. Every edge is a modeled probability — 93% it corrupts the sequence build, 76% it reaches the line. Watch the Monte-Carlo ribbon."' },
  { page: 'cascade', title: 'Run the counterfactual', line: 'Open Scenario controls: "If we apply this control, expected exposure collapses — we quantify the fix before we commit to it." Then hit Explain this cascade for the narrated version.' },
  { page: 'agents', title: 'Ask the mesh', line: 'Ask "What needs attention first?" — five specialists cite finding IDs, then the orchestrator gives one decision. Open the handoff trace to prove it is grounded.' },
  { page: 'intelligence', title: 'Approve as the human', line: 'Open the top finding, apply its controls. "The AI recommends; a human approves. The source data is genuinely corrected — this is not a status flag."' },
  { page: 'command', title: 'Show the drop', line: 'Back on the dashboard: exposure fell by the exact impact, containment ticked up. Run a scan — the finding does not come back, because the data is clean now.' },
  { page: 'outcomes', title: 'Close on value', line: '"Every decision lands in the ledger: €1.2M protected this shift — a €1.3B annual run-rate if this shift is typical, caught in minutes instead of a weekly reconciliation."' },
]

export function DemoTour({ open, onClose, onNavigate, onReset }) {
  const [step, setStep] = useState(0)
  const [injecting, setInjecting] = useState(false)
  const [lastIncident, setLastIncident] = useState('')
  const [confirmReset, setConfirmReset] = useState(false)
  // The component stays mounted while closed; a Reset left armed must not
  // survive into the next open, or one stray click wipes the demo.
  useEffect(() => { if (!open) { setConfirmReset(false); setLastIncident('') } }, [open])
  if (!open) return null
  const current = script[step]
  const inject = async () => {
    setInjecting(true); setLastIncident(''); setConfirmReset(false)
    try { const result = await api.injectIncident(); setLastIncident(result.injected ? result.incident.story : result.detail) }
    catch (cause) { setLastIncident(cause.message) }
    finally { setInjecting(false) }
  }
  const storm = async () => {
    setInjecting(true); setLastIncident(''); setConfirmReset(false)
    try {
      const result = await api.injectStorm()
      setLastIncident(result.injected ? `Storm: ${result.incidents.length} simultaneous incidents — ${result.incidents.map((item) => item.type).join(', ')}. Watch the queue re-rank by impact.` : result.detail)
    }
    catch (cause) { setLastIncident(cause.message) }
    finally { setInjecting(false) }
  }
  const reset = async () => {
    if (!confirmReset) { setConfirmReset(true); setLastIncident('Reset regenerates the whole twin and clears the value ledger. Click again to confirm.'); return }
    setConfirmReset(false); setInjecting(true); setLastIncident('')
    try {
      const result = await api.resetDemo()
      setLastIncident(`Fresh board: ${result.findings} findings rediscovered on a new twin (seed ${result.seed}).`)
      setStep(0)
      onReset?.()
    }
    catch (cause) { setLastIncident(cause.message) }
    finally { setInjecting(false) }
  }
  return <div className="tour-shell" role="dialog" aria-label="Demo tour">
    <div className="tour-card card-surface">
      <div className="tour-head"><span className="eyebrow"><Presentation size={13} /> 90-second demo script</span><button className="icon-button" onClick={onClose} aria-label="Close tour"><X size={14} /></button></div>
      <div className="tour-steps">{script.map((item, index) => <button key={index} className={`tour-step ${index === step ? 'active' : ''} ${index < step ? 'done' : ''}`} onClick={() => { setStep(index); onNavigate(item.page) }}>
        <span>{index < step ? <Check size={11} /> : index + 1}</span>{item.title}
      </button>)}</div>
      <p className="tour-line">{current.line}</p>
      {lastIncident && <p className="tour-incident"><Zap size={12} /> {lastIncident}</p>}
      <div className="tour-actions">
        <div className="tour-inject-group">
          <button className="soft-button" onClick={inject} disabled={injecting} title="Also on Ctrl+Shift+X">{injecting ? <LoaderCircle size={13} className="spin" /> : <Zap size={13} />}Incident</button>
          <button className="soft-button" onClick={storm} disabled={injecting} title="Inject 3 incidents at once">{injecting ? <LoaderCircle size={13} className="spin" /> : <CloudLightning size={13} />}Storm</button>
          <button className={`soft-button ${confirmReset ? 'reset-armed' : ''}`} onClick={reset} disabled={injecting} title="Regenerate the twin and clear all stats">{injecting ? <LoaderCircle size={13} className="spin" /> : <RotateCcw size={13} />}{confirmReset ? 'Confirm?' : 'Reset'}</button>
        </div>
        {step < script.length - 1
          ? <button className="primary-button" onClick={() => { const next = step + 1; setStep(next); onNavigate(script[next].page) }}>Next beat <ChevronRight size={14} /></button>
          : <button className="primary-button" onClick={() => { setStep(0); onClose() }}>Finish — you have this <Check size={14} /></button>}
      </div>
    </div>
  </div>
}

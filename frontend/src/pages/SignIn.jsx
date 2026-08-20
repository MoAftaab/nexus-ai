import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, LockKeyhole, ShieldCheck, Sparkles } from 'lucide-react'
import { api } from '../api'
import { VwLogo } from '../components/VwLogo'

const accounts = [
  ['operator1@nexusai.demo', 'Operations operator', 'Wolfsburg'], ['operator2@nexusai.demo', 'Operations operator', 'Bratislava'], ['operator3@nexusai.demo', 'Operations operator', 'Pune'],
  ['lead1@nexusai.demo', 'Operations lead', 'Wolfsburg'], ['lead2@nexusai.demo', 'Operations lead', 'Bratislava'], ['lead3@nexusai.demo', 'Operations lead', 'Pune'],
  ['manager1@nexusai.demo', 'Operations manager', 'Wolfsburg'], ['manager2@nexusai.demo', 'Operations manager', 'Bratislava'], ['manager3@nexusai.demo', 'Operations manager', 'Pune'],
  ['quality1@nexusai.demo', 'Quality & compliance', 'Wolfsburg'], ['quality2@nexusai.demo', 'Quality & compliance', 'Bratislava'], ['quality3@nexusai.demo', 'Quality & compliance', 'Pune'],
  ['director@nexusai.demo', 'Supply chain director', 'All sites'], ['auditor@nexusai.demo', 'Auditor', 'All sites'], ['admin@nexusai.demo', 'System administrator', 'All sites'],
]

export function SignIn({ onSignedIn }) {
  const [email, setEmail] = useState(accounts[0][0]); const [password, setPassword] = useState('nexusai2026'); const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const account = useMemo(() => accounts.find((item) => item[0] === email) || accounts[0], [email])
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('')
    try { const result = await api.signIn({ email, password }); window.localStorage.setItem('nexusai.session', JSON.stringify(result)); onSignedIn(result.user) } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  return <main className="auth-screen"><div className="auth-orbit" aria-hidden="true" /><section className="auth-panel">
    <button className="auth-back" onClick={() => { window.location.hash = '#home' }} type="button"><ArrowLeft size={18} /> Back</button>
    <div className="auth-brand"><VwLogo size={32} className="auth-vw-logo" /><span><strong>Warehouse Control Tower</strong><em>AI</em></span></div>
    <span className="eyebrow"><Sparkles size={14} /> Governed operations workspace</span><h1>Sign in to the decision layer.</h1><p className="auth-copy">Choose a seeded role to enter a site-scoped workspace. Every change stays visible from finding to verified outcome.</p>
    <form onSubmit={submit} className="auth-form"><label>Demo account<select value={email} onChange={(event) => setEmail(event.target.value)}>{accounts.map(([value, role, site]) => <option value={value} key={value}>{value} · {role} · {site}</option>)}</select></label><div className="account-card"><ShieldCheck size={18} /><div><strong>{account[1]}</strong><span>{account[2]} scope</span></div><b>{account[0].split('@')[0]}</b></div><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>{error && <p className="form-error">{error}</p>}<button className="primary-button auth-submit" disabled={busy}>{busy ? 'Opening workspace…' : 'Enter workspace'}<ArrowRight size={16} /></button></form>
    <p className="auth-foot"><LockKeyhole size={14} /> Demo sessions expire after 12 hours. Password for seeded accounts: <code>nexusai2026</code></p>
  </section></main>
}

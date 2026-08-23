import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Moon, ShieldCheck, Sparkles, Sun } from 'lucide-react'
import { api } from '../api'
import { currency } from '../utils'
import { VwLogo } from '../components/VwLogo'

// Keep the landing page usable while the optional WebGL layer loads. If an
// embedded browser cannot load Three.js, the static VW instrument remains.
const VwTwinScene = lazy(() => import('../components/landing/VwTwinScene')
  .then((module) => ({ default: module.VwTwinScene }))
  .catch(() => ({ default: () => null })))

const ACCOUNTS = [
  ['operator1@nexusai.demo', 'Operations operator', 'Wolfsburg'],
  ['operator2@nexusai.demo', 'Operations operator', 'Bratislava'],
  ['operator3@nexusai.demo', 'Operations operator', 'Pune'],
  ['lead1@nexusai.demo', 'Operations lead', 'Wolfsburg'],
  ['lead2@nexusai.demo', 'Operations lead', 'Bratislava'],
  ['lead3@nexusai.demo', 'Operations lead', 'Pune'],
  ['manager1@nexusai.demo', 'Operations manager', 'Wolfsburg'],
  ['manager2@nexusai.demo', 'Operations manager', 'Bratislava'],
  ['manager3@nexusai.demo', 'Operations manager', 'Pune'],
  ['quality1@nexusai.demo', 'Quality & compliance', 'Wolfsburg'],
  ['quality2@nexusai.demo', 'Quality & compliance', 'Bratislava'],
  ['quality3@nexusai.demo', 'Quality & compliance', 'Pune'],
  ['director@nexusai.demo', 'Supply chain director', 'All sites'],
  ['auditor@nexusai.demo', 'Auditor', 'All sites'],
  ['admin@nexusai.demo', 'System administrator', 'All sites'],
]

/** Scroll-reveal without framer-motion (its installed build is broken):
 *  adds .revealed when the element enters the viewport; CSS does the rest. */
function Reveal({ as: Tag = 'div', className = '', delay = 0, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (typeof IntersectionObserver !== 'function') { element.classList.add('revealed'); return }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { element.classList.add('revealed'); observer.disconnect() }
    }, { rootMargin: '-60px' })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return <Tag ref={ref} className={`reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>{children}</Tag>
}

/* ------------------------------------------------------------------------ */
/* 3D cascade network — perspective-projected canvas, no external library.  */
/* Nodes live on a slowly rotating sphere; signal pulses travel the edges,  */
/* echoing how one bad record propagates through the operation.             */
/* ------------------------------------------------------------------------ */

const PALETTE_DEFAULT = ['#008C82', '#64A844', '#8CBEE6', '#C882BE', '#FAAA3C']
const PALETTE_VW = ['#008C82', '#64A844', '#8CBEE6', '#FAAA3C', '#C882BE']

function CascadeField() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!context) return undefined
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame; let width; let height
    const pointer = { x: 0, y: 0 }
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
    const activePalette = isDark ? PALETTE_VW : PALETTE_DEFAULT

    const nodes = Array.from({ length: 110 }, (_, index) => {
      // Fibonacci sphere gives an even, organic distribution.
      const golden = Math.PI * (3 - Math.sqrt(5))
      const y = 1 - (index / 109) * 2
      const radiusAt = Math.sqrt(1 - y * y)
      const theta = golden * index
      const radius = 235 + (index % 7) * 9
      return {
        x: Math.cos(theta) * radiusAt * radius,
        y: y * radius * 0.86,
        z: Math.sin(theta) * radiusAt * radius,
        size: 1.1 + (index % 5) * 0.55,
        color: activePalette[index % activePalette.length],
      }
    })
    const edges = []
    for (let a = 0; a < nodes.length; a += 1) {
      for (let b = a + 1; b < nodes.length; b += 1) {
        const dx = nodes[a].x - nodes[b].x; const dy = nodes[a].y - nodes[b].y; const dz = nodes[a].z - nodes[b].z
        if (Math.sqrt(dx * dx + dy * dy + dz * dz) < 118) edges.push([a, b])
      }
    }
    const pulses = Array.from({ length: 9 }, () => ({
      edge: Math.floor(Math.random() * edges.length),
      t: Math.random(),
      speed: 0.005 + Math.random() * 0.008,
    }))

    // Automotive JIS sequencing conveyor packets that glide across coordinates
    const jisPackets = Array.from({ length: 6 }, (_, index) => ({
      progress: index / 6,
      speed: 0.0018 + (index % 3) * 0.0006,
      trackY: 0.25 + (index % 4) * 0.18,
      amplitude: 28 + (index % 3) * 15,
      frequency: 2 + (index % 2),
      color: index % 2 === 0 ? '#008C82' : '#64A844',
    }))

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth; height = canvas.clientHeight
      canvas.width = width * ratio; canvas.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }
    const onPointer = (event) => {
      const rect = canvas.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2
      pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2
    }
    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onPointer)

    let angle = 0
    let tick = 0
    const FOCAL = 560
    const project = (node, sin, cos, tilt) => {
      const x = node.x * cos - node.z * sin
      const z = node.x * sin + node.z * cos
      const y = node.y * Math.cos(tilt) - z * 0.14 * Math.sin(tilt)
      const scale = FOCAL / (FOCAL + z + 320)
      return { sx: width / 2 + x * scale, sy: height / 2 + y * scale, scale, z }
    }

    const draw = () => {
      tick += 1
      angle += reduced ? 0 : 0.0016 + pointer.x * 0.0011
      const tilt = 0.35 + pointer.y * 0.1
      const sin = Math.sin(angle); const cos = Math.cos(angle)
      context.clearRect(0, 0, width, height)

      // 1. JIS Flow-Line Conveyor Tracks (Automotive Logistics Telemetry)
      for (const packet of jisPackets) {
        packet.progress = (packet.progress + (reduced ? 0 : packet.speed)) % 1
        const py = height * packet.trackY + Math.sin(packet.progress * Math.PI * 2 * packet.frequency + tick * 0.02) * packet.amplitude
        const px = packet.progress * (width + 100) - 50
        
        // Track line
        context.strokeStyle = isDark ? 'rgba(0, 140, 130, 0.08)' : 'rgba(0, 39, 51, 0.06)'
        context.lineWidth = 1
        context.beginPath()
        context.moveTo(0, height * packet.trackY)
        context.quadraticCurveTo(width * 0.5, height * packet.trackY + packet.amplitude, width, height * packet.trackY)
        context.stroke()

        // Glowing packet pip
        const pGlow = context.createRadialGradient(px, py, 0, px, py, 12)
        pGlow.addColorStop(0, packet.color)
        pGlow.addColorStop(0.3, isDark ? 'rgba(140, 190, 230, 0.38)' : 'rgba(0, 140, 130, 0.28)')
        pGlow.addColorStop(1, 'rgba(0, 0, 0, 0)')
        context.fillStyle = pGlow
        context.beginPath()
        context.arc(px, py, 12, 0, Math.PI * 2)
        context.fill()
        context.fillStyle = '#ffffff'
        context.beginPath()
        context.arc(px, py, 1.8, 0, Math.PI * 2)
        context.fill()
      }

      // 2. 3D Twin Network Sphere
      const projected = nodes.map((node) => project(node, sin, cos, tilt))
      for (const [a, b] of edges) {
        const pa = projected[a]; const pb = projected[b]
        const depth = Math.min(pa.scale, pb.scale)
        context.strokeStyle = isDark
          ? `rgba(0, 140, 130, ${0.08 + depth * 0.14})`
          : `rgba(238, 213, 147, ${0.05 + depth * 0.1})`
        context.lineWidth = depth * 0.9
        context.beginPath(); context.moveTo(pa.sx, pa.sy); context.lineTo(pb.sx, pb.sy); context.stroke()
      }
      for (const pulse of pulses) {
        pulse.t += reduced ? 0 : pulse.speed
        if (pulse.t >= 1) { pulse.t = 0; pulse.edge = Math.floor(Math.random() * edges.length) }
        const [a, b] = edges[pulse.edge]
        const pa = projected[a]; const pb = projected[b]
        const px = pa.sx + (pb.sx - pa.sx) * pulse.t
        const py = pa.sy + (pb.sy - pa.sy) * pulse.t
        const glow = context.createRadialGradient(px, py, 0, px, py, 8)
        glow.addColorStop(0, isDark ? 'rgba(140, 190, 230, 0.9)' : 'rgba(0, 140, 130, 0.82)')
        glow.addColorStop(1, 'rgba(0, 0, 0, 0)')
        context.fillStyle = glow
        context.beginPath(); context.arc(px, py, 8, 0, Math.PI * 2); context.fill()
      }
      for (let index = 0; index < nodes.length; index += 1) {
        const point = projected[index]
        context.globalAlpha = 0.25 + point.scale * 0.65
        context.fillStyle = nodes[index].color
        context.beginPath(); context.arc(point.sx, point.sy, nodes[index].size * point.scale, 0, Math.PI * 2); context.fill()
      }
      context.globalAlpha = 1
      frame = window.requestAnimationFrame(draw)
    }
    draw()
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('resize', resize); window.removeEventListener('pointermove', onPointer) }
  }, [])
  return <canvas ref={canvasRef} className="landing-canvas" aria-hidden="true" />
}

export function Landing({ onEnter, onSignedIn, principal, theme = 'light', onToggleTheme }) {
  const [exposure, setExposure] = useState(null)
  const [email, setEmail] = useState(ACCOUNTS[0][0])
  const [password, setPassword] = useState('nexusai2026')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const account = useMemo(() => ACCOUNTS.find((item) => item[0] === email) || ACCOUNTS[0], [email])

  const handleSignIn = async (event) => {
    if (event) event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api.signIn({ email, password })
      window.localStorage.setItem('nexusai.session', JSON.stringify(result))
      onSignedIn?.(result.user)
    } catch (cause) {
      setError(cause.message || 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    api.dashboard().then((dashboard) => { if (!cancelled) setExposure(dashboard.metrics?.[0]?.value ?? null) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  return (
    <div className="landing">
      <nav className="landing-nav">
        <span className="brand landing-brand">
          <VwLogo size={32} className="landing-vw-logo" />
          <span><strong>Warehouse Control Tower</strong><em>AI</em></span>
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className={`theme-toggle-btn ${theme === 'dark' ? 'is-dark' : ''}`}
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>
          <button className="soft-button" onClick={onEnter}>Enter dashboard <ArrowRight size={14} /></button>
        </div>
      </nav>

      <header className="landing-hero">
        <CascadeField />
        <div className="landing-hero-grid">
          <div className="landing-hero-copy">
            <Reveal className="landing-hero-auth" delay={80}>
              {principal ? (
                <>
                  <div className="landing-auth-header">
                    <span className="live-chip"><Sparkles size={12} /> Governed Session Active</span>
                    <h2>Welcome back, <em>{principal.name || principal.email?.split('@')[0]}</em></h2>
                    <p>Connected to site-scoped decision layer. Ready to monitor the live twin.</p>
                  </div>
                  <div className="account-card">
                    <ShieldCheck size={18} />
                    <div>
                      <strong>{principal.role_label || principal.role}</strong>
                      <span>{principal.site || 'All sites'} scope</span>
                    </div>
                    <b>{principal.email?.split('@')[0]}</b>
                  </div>
                  <div className="landing-cta" style={{ marginTop: '16px' }}>
                    <button className="primary-button landing-primary" style={{ width: '100%' }} onClick={onEnter}>
                      Enter the command center <ArrowRight size={16} />
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="landing-auth-header">
                    <span className="live-chip"><Sparkles size={12} /> Governed operations workspace</span>
                    <h2>Sign in to the <em>Command Center</em></h2>
                    <p>Choose a seeded role to enter the decision layer and monitor the live twin.</p>
                  </div>
                  <form onSubmit={handleSignIn} className="auth-form landing-auth-form">
                    <label>
                      Demo account
                      <select value={email} onChange={(event) => setEmail(event.target.value)}>
                        {ACCOUNTS.map(([val, role, site]) => (
                          <option value={val} key={val}>{val} · {role} · {site}</option>
                        ))}
                      </select>
                    </label>
                    <div className="account-card">
                      <ShieldCheck size={18} />
                      <div>
                        <strong>{account[1]}</strong>
                        <span>{account[2]} scope</span>
                      </div>
                      <b>{account[0].split('@')[0]}</b>
                    </div>
                    <label>
                      Password
                      <input
                        type="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        autoComplete="current-password"
                      />
                    </label>
                    {error && <p className="form-error">{error}</p>}
                    <button className="primary-button landing-primary auth-submit" disabled={busy} type="submit">
                      {busy ? 'Opening workspace…' : 'Enter the command center'}
                      <ArrowRight size={16} />
                    </button>
                  </form>
                </>
              )}
              {exposure !== null && (
                <span className="landing-live" style={{ marginTop: '14px', display: 'flex' }}>
                  <i className="pulse-dot" />{currency(exposure)} at risk on the live twin right now
                </span>
              )}
            </Reveal>
            <Reveal className="landing-hero-meta" delay={200}>
              <span><i /> ERP / WMS / TMS</span>
              <span><i /> 5 + 1 AI roles</span>
              <span><i /> Human-approved actions</span>
            </Reveal>
          </div>

          <Reveal className="landing-twin-panel" delay={140}>
            <Suspense fallback={<div className="landing-twin-loading" aria-hidden="true" />}>
              <VwTwinScene theme={theme} />
            </Suspense>
            <div className="landing-twin-hud-header">
              <div className="landing-twin-brand-pill">
                <VwLogo size={22} animated={false} className="landing-twin-hud-logo" />
                <div>
                  <strong>VW OPERATIONAL TWIN</strong>
                  <span>WOLFSBURG DC · DECISION TELEMETRY</span>
                </div>
              </div>
              <div className="landing-twin-hud-status">
                <i className="pulse-dot" />
                <span>LIVE MESH SIGNAL</span>
              </div>
            </div>
            <div className="landing-twin-readout landing-twin-readout-left"><strong>72,900</strong><span>records watched</span></div>
            <div className="landing-twin-readout landing-twin-readout-right"><strong>38</strong><span>live findings</span></div>
            <div className="landing-twin-route"><span>detect</span><i /><span>trace</span><i /><span>approve</span></div>
          </Reveal>
        </div>
      </header>
    </div>
  )
}

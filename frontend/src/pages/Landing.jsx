import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Bot, Euro, FileSearch, GitFork, Radar, ShieldCheck, Sparkles, Waypoints } from 'lucide-react'
import { api } from '../api'
import { currency } from '../utils'

/** Scroll-reveal without framer-motion (its installed build is broken):
 *  adds .revealed when the element enters the viewport; CSS does the rest. */
function Reveal({ as: Tag = 'div', className = '', delay = 0, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
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

const PALETTE = ['#eed593', '#eed593', '#eed593', '#df9cc2', '#7fc7ad', '#9d94c9']

function CascadeField() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame; let width; let height
    const pointer = { x: 0, y: 0 }

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
        color: PALETTE[index % PALETTE.length],
      }
    })
    const edges = []
    for (let a = 0; a < nodes.length; a += 1) {
      for (let b = a + 1; b < nodes.length; b += 1) {
        const dx = nodes[a].x - nodes[b].x; const dy = nodes[a].y - nodes[b].y; const dz = nodes[a].z - nodes[b].z
        if (Math.sqrt(dx * dx + dy * dy + dz * dz) < 118) edges.push([a, b])
      }
    }
    const pulses = Array.from({ length: 7 }, () => ({ edge: Math.floor(Math.random() * edges.length), t: Math.random(), speed: 0.004 + Math.random() * 0.007 }))

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
    const FOCAL = 560
    const project = (node, sin, cos, tilt) => {
      const x = node.x * cos - node.z * sin
      const z = node.x * sin + node.z * cos
      const y = node.y * Math.cos(tilt) - z * 0.14 * Math.sin(tilt)
      const scale = FOCAL / (FOCAL + z + 320)
      return { sx: width / 2 + x * scale, sy: height / 2 + y * scale, scale, z }
    }

    const draw = () => {
      angle += reduced ? 0 : 0.0016 + pointer.x * 0.0011
      const tilt = 0.35 + pointer.y * 0.1
      const sin = Math.sin(angle); const cos = Math.cos(angle)
      context.clearRect(0, 0, width, height)
      const projected = nodes.map((node) => project(node, sin, cos, tilt))
      for (const [a, b] of edges) {
        const pa = projected[a]; const pb = projected[b]
        const depth = Math.min(pa.scale, pb.scale)
        context.strokeStyle = `rgba(238, 213, 147, ${0.05 + depth * 0.1})`
        context.lineWidth = depth * 0.8
        context.beginPath(); context.moveTo(pa.sx, pa.sy); context.lineTo(pb.sx, pb.sy); context.stroke()
      }
      for (const pulse of pulses) {
        pulse.t += reduced ? 0 : pulse.speed
        if (pulse.t >= 1) { pulse.t = 0; pulse.edge = Math.floor(Math.random() * edges.length) }
        const [a, b] = edges[pulse.edge]
        const pa = projected[a]; const pb = projected[b]
        const px = pa.sx + (pb.sx - pa.sx) * pulse.t
        const py = pa.sy + (pb.sy - pa.sy) * pulse.t
        const glow = context.createRadialGradient(px, py, 0, px, py, 7)
        glow.addColorStop(0, 'rgba(255, 236, 189, .9)'); glow.addColorStop(1, 'rgba(255, 236, 189, 0)')
        context.fillStyle = glow
        context.beginPath(); context.arc(px, py, 7, 0, Math.PI * 2); context.fill()
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

/* ------------------------------------------------------------------------ */

/* ------------------------------------------------------------------------ */
/* 3D agent mesh — five specialists orbit the Nexus orchestrator, streaming */
/* handoff pulses inward; the center emits a decision wave when they land.  */
/* ------------------------------------------------------------------------ */

const SPECIALIST_ORBS = [
  { name: 'Sentinel', role: 'Detection', temp: 0.2, color: '#8ae0d5' },
  { name: 'Correlator', role: 'Linkage', temp: 0.4, color: '#9d94c9' },
  { name: 'Cascade', role: 'Simulation', temp: 0.4, color: '#df9cc2' },
  { name: 'Impact', role: 'Quantification', temp: 0.2, color: '#eed593' },
  { name: 'Fix', role: 'Control design', temp: 0.35, color: '#7fc7ad' },
]

function AgentMeshField() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame; let width; let height
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth; height = canvas.clientHeight
      canvas.width = width * ratio; canvas.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)
    let tick = 0
    const FOCAL = 520; const RING = 205; const TILT = 0.42
    const draw = () => {
      tick += reduced ? 0 : 1
      const angle = tick * 0.0035
      context.clearRect(0, 0, width, height)
      const cx = width / 2; const cy = height / 2 + 4
      const orbs = SPECIALIST_ORBS.map((orb, index) => {
        const theta = angle + (index / SPECIALIST_ORBS.length) * Math.PI * 2
        const x = Math.cos(theta) * RING
        const z = Math.sin(theta) * RING
        const scale = FOCAL / (FOCAL + z + 240)
        return { ...orb, sx: cx + x * scale, sy: cy + z * TILT * scale * 0.9 - 8, scale, z }
      }).sort((a, b) => b.z - a.z)
      // Decision wave rippling out of the orchestrator.
      const wave = (tick % 260) / 260
      context.strokeStyle = `rgba(238, 213, 147, ${(1 - wave) * 0.3})`
      context.lineWidth = 1.4
      context.beginPath(); context.ellipse(cx, cy - 8, wave * 190, wave * 190 * TILT, 0, 0, Math.PI * 2); context.stroke()
      for (const orb of orbs) {
        // Handoff lane and traveling pulse (staggered per specialist).
        context.strokeStyle = `rgba(238, 213, 147, ${0.07 + orb.scale * 0.08})`
        context.lineWidth = orb.scale
        context.beginPath(); context.moveTo(orb.sx, orb.sy); context.lineTo(cx, cy - 8); context.stroke()
        const t = ((tick * 0.006) + SPECIALIST_ORBS.findIndex((s) => s.name === orb.name) * 0.2) % 1
        const px = orb.sx + (cx - orb.sx) * t; const py = orb.sy + (cy - 8 - orb.sy) * t
        const glow = context.createRadialGradient(px, py, 0, px, py, 6)
        glow.addColorStop(0, 'rgba(255, 240, 200, .95)'); glow.addColorStop(1, 'rgba(255, 240, 200, 0)')
        context.fillStyle = glow
        context.beginPath(); context.arc(px, py, 6, 0, Math.PI * 2); context.fill()
        // Specialist orb + label.
        const radius = 8.5 * orb.scale
        const orbGlow = context.createRadialGradient(orb.sx, orb.sy, 0, orb.sx, orb.sy, radius * 2.6)
        orbGlow.addColorStop(0, orb.color); orbGlow.addColorStop(1, 'rgba(0,0,0,0)')
        context.globalAlpha = 0.35 * orb.scale; context.fillStyle = orbGlow
        context.beginPath(); context.arc(orb.sx, orb.sy, radius * 2.6, 0, Math.PI * 2); context.fill()
        context.globalAlpha = 0.45 + orb.scale * 0.55; context.fillStyle = orb.color
        context.beginPath(); context.arc(orb.sx, orb.sy, radius, 0, Math.PI * 2); context.fill()
        context.globalAlpha = 0.5 + orb.scale * 0.5
        context.font = `700 ${Math.round(10 * orb.scale)}px "DM Mono", monospace`
        context.textAlign = 'center'; context.fillStyle = '#e8e2d0'
        context.fillText(orb.name, orb.sx, orb.sy + radius + 14 * orb.scale)
        context.font = `500 ${Math.round(8 * orb.scale)}px "DM Mono", monospace`
        context.fillStyle = '#93896f'
        context.fillText(orb.role, orb.sx, orb.sy + radius + 25 * orb.scale)
        context.globalAlpha = 1
      }
      // Orchestrator core.
      const pulse = 15 + Math.sin(tick * 0.045) * 2.2
      const core = context.createRadialGradient(cx, cy - 8, 0, cx, cy - 8, pulse * 2.6)
      core.addColorStop(0, 'rgba(255, 238, 190, .95)'); core.addColorStop(0.45, 'rgba(238, 213, 147, .5)'); core.addColorStop(1, 'rgba(238, 213, 147, 0)')
      context.fillStyle = core
      context.beginPath(); context.arc(cx, cy - 8, pulse * 2.6, 0, Math.PI * 2); context.fill()
      context.fillStyle = '#f7ecc9'
      context.beginPath(); context.arc(cx, cy - 8, pulse * 0.55, 0, Math.PI * 2); context.fill()
      context.font = '700 11px "DM Mono", monospace'; context.textAlign = 'center'
      context.fillStyle = '#f2e7c2'; context.fillText('NEXUS', cx, cy + 34)
      context.font = '500 8px "DM Mono", monospace'; context.fillStyle = '#93896f'
      context.fillText('orchestrator · synthesis', cx, cy + 45)
      frame = window.requestAnimationFrame(draw)
    }
    draw()
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('resize', resize) }
  }, [])
  return <canvas ref={canvasRef} className="mesh-canvas" aria-hidden="true" />
}

/* ------------------------------------------------------------------------ */
/* Haystack — ~15,000 scored positions as a shimmering field; one glows.    */
/* ------------------------------------------------------------------------ */

function HaystackField({ flagged = 1 }) {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame; let width; let height; let dots = []
    let hotIndex = 0
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth; height = canvas.clientHeight
      canvas.width = width * ratio; canvas.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      const cols = Math.floor(width / 13); const rows = Math.floor(height / 13)
      dots = []
      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
          dots.push({ x: 8 + col * 13 + (Math.sin(row * 7 + col) * 2), y: 10 + row * 13 + (Math.cos(col * 5) * 2), phase: (row * cols + col) % 97 })
        }
      }
      hotIndex = Math.floor(dots.length * 0.62)
    }
    resize()
    window.addEventListener('resize', resize)
    let tick = 0
    const draw = () => {
      tick += reduced ? 0 : 1
      context.clearRect(0, 0, width, height)
      for (let index = 0; index < dots.length; index += 1) {
        const dot = dots[index]
        if (index === hotIndex) continue
        context.globalAlpha = 0.1 + 0.08 * Math.sin(tick * 0.02 + dot.phase)
        context.fillStyle = '#8d8468'
        context.beginPath(); context.arc(dot.x, dot.y, 1.4, 0, Math.PI * 2); context.fill()
      }
      const hot = dots[hotIndex]
      if (hot) {
        const radius = 4 + Math.sin(tick * 0.07) * 1.4
        const glow = context.createRadialGradient(hot.x, hot.y, 0, hot.x, hot.y, radius * 5)
        glow.addColorStop(0, 'rgba(255, 176, 122, .95)'); glow.addColorStop(1, 'rgba(255, 176, 122, 0)')
        context.globalAlpha = 1; context.fillStyle = glow
        context.beginPath(); context.arc(hot.x, hot.y, radius * 5, 0, Math.PI * 2); context.fill()
        context.fillStyle = '#ffd9b8'
        context.beginPath(); context.arc(hot.x, hot.y, radius * 0.6, 0, Math.PI * 2); context.fill()
        context.font = '700 9px "DM Mono", monospace'; context.textAlign = 'center'
        context.fillStyle = '#ffcf9e'
        context.fillText(`score ${flagged >= 1 ? '0.99' : '—'}`, hot.x, hot.y - 14)
      }
      context.globalAlpha = 1
      frame = window.requestAnimationFrame(draw)
    }
    draw()
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('resize', resize) }
  }, [flagged])
  return <canvas ref={canvasRef} className="haystack-canvas" aria-hidden="true" />
}

/** Number that counts up from zero when it scrolls into view. */
function CountUp({ value, decimals = 1, suffix = '%' }) {
  const ref = useRef(null)
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      observer.disconnect()
      const start = performance.now()
      const step = (now) => {
        const progress = Math.min(1, (now - start) / 1100)
        setDisplay(value * (1 - Math.pow(1 - progress, 3)))
        if (progress < 1) window.requestAnimationFrame(step)
      }
      window.requestAnimationFrame(step)
    }, { rootMargin: '-40px' })
    observer.observe(element)
    return () => observer.disconnect()
  }, [value])
  return <strong ref={ref}>{display.toFixed(decimals)}{suffix}</strong>
}

const FALLBACK_CANDIDATES = [
  { name: 'random_forest', f1: 1, accuracy: 1, precision: 1, recall: 1, selected: true },
  { name: 'extra_trees', f1: 1, accuracy: 1, precision: 1, recall: 1, selected: false },
  { name: 'hist_gradient_boosting', f1: 0.99, accuracy: 0.99, precision: 0.99, recall: 0.99, selected: false },
]

const FEATURES = [
  { icon: Radar, title: 'Autonomous detection', text: '20+ statistical, rule-based and ML checks sweep ERP, WMS, TMS and count data — nothing is tagged by hand, the mesh finds the drift itself.' },
  { icon: GitFork, title: 'Cascade prediction', text: 'A dependency twin traces every finding downstream: which sequence, which dock, which line — with a modeled probability on every hop.' },
  { icon: Euro, title: 'Impact in euros', text: '1,000 Monte-Carlo trials price each cascade — expected exposure, P90 tail risk, and the counterfactual value of every proposed control.' },
  { icon: Bot, title: 'Five-specialist reasoning', text: 'Sentinel, Correlator, Cascade, Impact and Fix each argue from evidence; an orchestrator merges their handoffs into one operator decision.' },
  { icon: FileSearch, title: 'Document intelligence', text: 'Invoices, ASNs, PPAP packets and count sheets are parsed and cross-checked against the operation — missing release evidence blocks the batch.' },
  { icon: ShieldCheck, title: 'Human-approved fixes', text: 'The AI recommends; a person approves. Source records are corrected at the origin, a rescan proves the defect is gone, and the value lands in an auditable ledger.' },
]

const PIPELINE = ['Detect', 'Trace', 'Quantify', 'Approve', 'Prove']

export function Landing({ onEnter }) {
  const [exposure, setExposure] = useState(null)
  const [mlModel, setMlModel] = useState(null)
  useEffect(() => {
    let cancelled = false
    api.dashboard().then((dashboard) => { if (!cancelled) setExposure(dashboard.metrics?.[0]?.value ?? null) }).catch(() => {})
    api.system().then((system) => { if (!cancelled) setMlModel(system.model) }).catch(() => {})
    return () => { cancelled = true }
  }, [])
  const candidates = mlModel?.candidates?.length ? mlModel.candidates : FALLBACK_CANDIDATES
  const selected = candidates.find((candidate) => candidate.selected) || candidates[0]
  return <div className="landing">
    <nav className="landing-nav">
      <span className="brand landing-brand"><span className="brand-mark"><span /><span /><span /></span><span><strong>Nexus</strong><em>AI</em></span></span>
      <button className="soft-button" onClick={onEnter}>Enter dashboard <ArrowRight size={14} /></button>
    </nav>

    <header className="landing-hero">
      <CascadeField />
      <div className="landing-hero-copy">
        <Reveal as="span" className="live-chip"><Sparkles size={12} /> Multi-agent supply-chain intelligence</Reveal>
        <Reveal as="h1" delay={80}>One wrong number can stop an <em>assembly line.</em><br />Nexus finds it first.</Reveal>
        <Reveal as="p" delay={160}>
          NexusAI watches a 72,900-record warehouse twin across ERP, WMS and TMS, detects the data drift no human would catch in time,
          traces the cascade to its euro consequence — and fixes the source, with a person approving every change.
        </Reveal>
        <Reveal className="landing-cta" delay={240}>
          <button className="primary-button landing-primary" onClick={onEnter}>Enter the command center <ArrowRight size={16} /></button>
          {exposure !== null && <span className="landing-live"><i className="pulse-dot" />{currency(exposure)} at risk on the live twin right now</span>}
        </Reveal>
      </div>
    </header>

    <Reveal as="section" className="landing-stats">
      {[['72,900', 'twin records watched'], ['5 + 1', 'specialist agents & orchestrator'], ['20+', 'autonomous checks'], ['1,000', 'Monte-Carlo trials per cascade'], ['< 5 min', 'from drift to detection']].map(([value, label]) => (
        <div key={label}><strong>{value}</strong><span>{label}</span></div>
      ))}
    </Reveal>

    <section className="landing-features">
      <Reveal className="landing-section-head">
        <span className="eyebrow"><Waypoints size={13} /> What the mesh does</span>
        <h2>From a silent data error to a <em>signed, priced, audited</em> fix.</h2>
      </Reveal>
      <div className="landing-feature-grid">
        {FEATURES.map(({ icon: Icon, title, text }, index) => (
          <Reveal as="article" key={title} className="card-surface landing-feature" delay={(index % 3) * 80}>
            <span className="landing-feature-icon"><Icon size={17} /></span>
            <h3>{title}</h3><p>{text}</p>
          </Reveal>
        ))}
      </div>
    </section>

    <Reveal as="section" className="landing-pipeline">
      {PIPELINE.map((step, index) => (
        <div key={step} className="landing-step">
          <span className="landing-step-index">{index + 1}</span><strong>{step}</strong>
          {index < PIPELINE.length - 1 && <ArrowRight size={14} className="landing-step-arrow" />}
        </div>
      ))}
    </Reveal>

    <section className="landing-mesh">
      <Reveal className="landing-section-head centered">
        <span className="eyebrow"><Bot size={13} /> Multi-LLM architecture</span>
        <h2>Five specialists <em>argue from evidence.</em> One orchestrator decides.</h2>
        <p>Each GPT-5.4 mini specialist runs with its own persona, curated context and calibrated temperature — precise for evidence roles, warmer for reasoning roles. Their structured handoffs stream into the Nexus orchestrator, which synthesizes one grounded operator decision. Every claim must cite a finding ID; unsourced claims are a system failure.</p>
      </Reveal>
      <Reveal className="mesh-stage" delay={120}><AgentMeshField /></Reveal>
      <Reveal className="mesh-facts" delay={200}>
        {SPECIALIST_ORBS.map((orb) => (
          <div key={orb.name} className="mesh-fact"><i style={{ background: orb.color, boxShadow: `0 0 9px ${orb.color}` }} /><div><strong>{orb.name}</strong><span>{orb.role} · temp {orb.temp}</span></div></div>
        ))}
      </Reveal>
    </section>

    <section className="landing-ml">
      <Reveal className="landing-section-head centered">
        <span className="eyebrow"><Radar size={13} /> Measured machine learning</span>
        <h2>Three models compete. The best <em>F1</em> goes live.</h2>
        <p>Extra trees, random forest and gradient boosting train on the same temporal holdout; the winner scores all {(mlModel?.scored_positions ?? 15000).toLocaleString()} inventory positions. F1 wins over raw accuracy because faults are rare — a model that calls everything “normal” would score 99% accuracy and catch nothing.</p>
      </Reveal>
      <div className="ml-grid">
        <Reveal className="card-surface ml-benchmark" delay={80}>
          <span className="ml-card-label">Live benchmark · {mlModel ? 'from the running system' : 'connecting…'}</span>
          {candidates.map((candidate) => (
            <div key={candidate.name} className={`ml-bar-row ${candidate.selected ? 'winner' : ''}`}>
              <span className="ml-bar-name">{candidate.name.replaceAll('_', ' ')}{candidate.selected && <em>live</em>}</span>
              <div className="ml-bar-track"><i style={{ width: `${candidate.f1 * 100}%` }} /></div>
              <b>F1 {(candidate.f1 * 100).toFixed(1)}%</b>
            </div>
          ))}
          <div className="ml-metric-row">
            <div><CountUp value={(selected?.accuracy ?? 1) * 100} /><span>accuracy</span></div>
            <div><CountUp value={(selected?.precision ?? 1) * 100} /><span>precision</span></div>
            <div><CountUp value={(selected?.recall ?? 1) * 100} /><span>recall</span></div>
            <div><CountUp value={1500} decimals={0} suffix="" /><span>labeled records</span></div>
          </div>
        </Reveal>
        <Reveal className="card-surface ml-haystack" delay={160}>
          <span className="ml-card-label">The needle, live</span>
          <HaystackField flagged={mlModel?.flagged_over_50 ?? 1} />
          <p>{(mlModel?.scored_positions ?? 15000).toLocaleString()} positions scored — {mlModel?.flagged_over_50 ?? 1} crosses the alarm line. Statistical noise never pages an operator: a finding needs a real quantity spread <b>and</b> a model score ≥ .5.</p>
        </Reveal>
      </div>
    </section>

    <Reveal as="section" className="landing-closing">
      <h2>The demo is live. The data is <em>really</em> dirty.</h2>
      <p>Every finding on the board was discovered, not scripted — inject a fresh incident yourself and watch the mesh catch it.</p>
      <button className="primary-button landing-primary" onClick={onEnter}>Open NexusAI <ArrowRight size={16} /></button>
      <footer><span>NexusAI · VW Wolfsburg DC operational twin · human-approved operations</span></footer>
    </Reveal>
  </div>
}

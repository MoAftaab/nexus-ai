import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  calculateWaltPopupPosition,
  clampWaltPosition,
  findWaltRoamPosition,
  isDragGesture,
  isWaltPositionClear,
  parseStoredWaltPosition,
  WALT_STORAGE_KEY,
} from '../../utils/waltPosition'
import { WaltMascot } from './WaltMascot'
import { WaltPanel } from './WaltPanel'
import { useWaltChat } from './useWaltChat'
import { buildWaltContextCards, isReviewContext } from './waltModel'
import './walt.css'

const SLEEP_AFTER_MS = 45000
const WALT_OBSTACLES = '.sidebar-wrap, nav, form, button, input, textarea, select, [role="alert"], .topbar, .global-approval-flow, .metric-card, .value-signal-ribbon, .priority-queue, .toast, .anomaly-drawer, .notification-panel, .escalation-panel, [data-walt-obstacle]'
const WALT_GREETING_COPY = [
  { lead: 'Hi! I’m', name: 'WALT', trail: '' },
  { lead: '', name: 'WALT', trail: ' here — monitoring the flow.' },
  { lead: 'Still on watch —', name: 'WALT', trail: ' is ready.' },
]

function viewportBounds() {
  return {
    width: Math.round(window.visualViewport?.width || window.innerWidth),
    height: Math.round(window.visualViewport?.height || window.innerHeight),
  }
}

function initialPosition() {
  const viewport = viewportBounds()
  const fallback = { x: Math.max(12, viewport.width - 194), y: Math.max(12, viewport.height - 136) }
  try { return parseStoredWaltPosition(window.localStorage.getItem(WALT_STORAGE_KEY)) || fallback } catch { return fallback }
}

export function WaltAssistant({
  anomalies = [],
  capabilities,
  currentPage = 'command',
  dashboard,
  onChatStream,
  onWaltConfirm,
  onWaltResolve,
  requestId,
  requestActions = [],
  riskCount = 0,
}) {
  const [open, setOpen] = useState(false)
  const [panelMounted, setPanelMounted] = useState(false)
  const [panelClosing, setPanelClosing] = useState(false)
  const [inputFocused, setInputFocused] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [roaming, setRoaming] = useState(false)
  const [dragState, setDragState] = useState('dragging')
  const [restingState, setRestingState] = useState('greeting')
  const [showGreeting, setShowGreeting] = useState(true)
  const [greetingCopy, setGreetingCopy] = useState(WALT_GREETING_COPY[0])
  const [position, setPosition] = useState(initialPosition)
  const [edge, setEdge] = useState(() => position.x < window.innerWidth / 2 ? 'left' : 'right')
  const shellRef = useRef(null)
  const triggerRef = useRef(null)
  const positionRef = useRef(position)
  const manualPositionRef = useRef(position)
  const dragRef = useRef(null)
  const suppressClickRef = useRef(false)
  const sleepTimerRef = useRef(null)
  const transientTimerRef = useRef(null)
  const greetingTimerRef = useRef(null)
  const personalityTimerRef = useRef(null)
  const greetingIndexRef = useRef(0)
  const panelTimerRef = useRef(null)
  const roamTimerRef = useRef(null)
  const roamFinishRef = useRef(null)
  const openRef = useRef(open)
  const chat = useWaltChat(onChatStream, onWaltResolve, onWaltConfirm, open, requestId)
  const contextCards = useMemo(() => buildWaltContextCards(dashboard, anomalies), [dashboard, anomalies])

  useEffect(() => { openRef.current = open }, [open])
  useEffect(() => { positionRef.current = position }, [position])

  const showTransient = useCallback((state, duration = 1600) => {
    window.clearTimeout(transientTimerRef.current)
    setRestingState(state)
    transientTimerRef.current = window.setTimeout(() => setRestingState('waiting'), duration)
  }, [])

  const greet = useCallback((periodic = false) => {
    window.clearTimeout(greetingTimerRef.current)
    if (periodic) greetingIndexRef.current = (greetingIndexRef.current + 1) % WALT_GREETING_COPY.length
    else greetingIndexRef.current = 0
    setGreetingCopy(WALT_GREETING_COPY[greetingIndexRef.current])
    setShowGreeting(true)
    greetingTimerRef.current = window.setTimeout(() => setShowGreeting(false), periodic ? 3400 : 2800)
  }, [])

  const markActive = useCallback(() => {
    window.clearTimeout(sleepTimerRef.current)
    setRestingState((state) => state === 'sleeping' ? 'waking' : state)
    sleepTimerRef.current = window.setTimeout(() => {
      if (!openRef.current) setRestingState('sleeping')
    }, SLEEP_AFTER_MS)
  }, [])

  const getMascotSize = useCallback(() => {
    const bounds = triggerRef.current?.getBoundingClientRect()
    return {
      width: Math.max(94, Math.round(bounds?.width || 174)),
      height: Math.max(102, Math.round(bounds?.height || 124)),
    }
  }, [])

  const collectObstacles = useCallback(() => [...document.querySelectorAll(WALT_OBSTACLES)]
    .filter((element) => !element.closest('.walt-assistant-shell') && window.getComputedStyle(element).display !== 'none')
    .map((element) => element.getBoundingClientRect())
    .filter((bounds) => bounds.width > 0 && bounds.height > 0)
    .map(({ left, right, top, bottom }) => ({ left, right, top, bottom })), [])

  const keepPositionVisible = useCallback((desired, persist = true) => {
    const next = clampWaltPosition(
      desired,
      viewportBounds(),
      getMascotSize(),
    )
    positionRef.current = next
    setPosition(next)
    setEdge(next.x < window.innerWidth / 2 ? 'left' : 'right')
    if (persist) {
      manualPositionRef.current = next
      try { window.localStorage.setItem(WALT_STORAGE_KEY, JSON.stringify(next)) } catch { /* storage can be disabled */ }
    }
  }, [getMascotSize])

  const closePanel = useCallback(() => {
    window.clearTimeout(panelTimerRef.current)
    setOpen(false)
    setPanelClosing(true)
    panelTimerRef.current = window.setTimeout(() => {
      setPanelMounted(false)
      setPanelClosing(false)
    }, 210)
    markActive()
  }, [markActive])

  const openPanel = useCallback(() => {
    window.clearTimeout(panelTimerRef.current)
    window.clearTimeout(roamFinishRef.current)
    setRoaming(false)
    setPanelClosing(false)
    setPanelMounted(true)
    setOpen(true)
    greet()
    showTransient('greeting', 1600)
    markActive()
  }, [greet, markActive, showTransient])

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => keepPositionVisible(manualPositionRef.current, false))
    const onResize = () => keepPositionVisible(manualPositionRef.current, false)
    window.addEventListener('resize', onResize)
    window.visualViewport?.addEventListener('resize', onResize)
    markActive()
    greet()
    showTransient('greeting', 2200)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('resize', onResize)
      window.visualViewport?.removeEventListener('resize', onResize)
      window.clearTimeout(sleepTimerRef.current)
      window.clearTimeout(transientTimerRef.current)
      window.clearTimeout(greetingTimerRef.current)
      window.clearTimeout(personalityTimerRef.current)
      window.clearTimeout(panelTimerRef.current)
      window.clearTimeout(roamTimerRef.current)
      window.clearTimeout(roamFinishRef.current)
    }
  }, [greet, keepPositionVisible, markActive, showTransient])

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (reducedMotion.matches) return undefined
    let disposed = false
    const schedule = (delay = 7200) => {
      window.clearTimeout(personalityTimerRef.current)
      personalityTimerRef.current = window.setTimeout(() => {
        if (disposed) return
        const busy = openRef.current || chat.loading || dragRef.current || shellRef.current?.classList.contains('is-roaming')
        if (!busy && !document.hidden) {
          markActive()
          greet(true)
          showTransient('greeting', 2600)
        }
        schedule(14500 + Math.round(Math.random() * 5500))
      }, delay)
    }
    const wakeOnReturn = () => {
      if (!document.hidden && !openRef.current) {
        markActive()
        greet(true)
        showTransient('waking', 1500)
      }
    }
    schedule()
    document.addEventListener('visibilitychange', wakeOnReturn)
    return () => {
      disposed = true
      window.clearTimeout(personalityTimerRef.current)
      document.removeEventListener('visibilitychange', wakeOnReturn)
    }
  }, [chat.loading, greet, markActive, showTransient])

  useEffect(() => {
    if (riskCount > 0) showTransient('warning', 1900)
  }, [riskCount, showTransient])

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (reducedMotion.matches) return undefined
    let disposed = false
    const schedule = () => {
      window.clearTimeout(roamTimerRef.current)
      roamTimerRef.current = window.setTimeout(() => {
        if (disposed) return
        if (!openRef.current && !document.hidden && !dragRef.current) {
          const origin = positionRef.current
          const target = findWaltRoamPosition(
            origin,
            viewportBounds(),
            getMascotSize(),
            collectObstacles(),
          )
          if (target.x !== origin.x || target.y !== origin.y) {
            positionRef.current = target
            setDragState(target.x < origin.x ? 'walking-left' : 'walking-right')
            setRoaming(true)
            setPosition(target)
            setEdge(target.x < window.innerWidth / 2 ? 'left' : 'right')
            roamFinishRef.current = window.setTimeout(() => {
              setRoaming(false)
              setDragState('dragging')
            }, 1200)
          }
        }
        schedule()
      }, 22000 + Math.round(Math.random() * 9000))
    }
    schedule()
    return () => {
      disposed = true
      window.clearTimeout(roamTimerRef.current)
      window.clearTimeout(roamFinishRef.current)
    }
  }, [collectObstacles, getMascotSize])

  useEffect(() => {
    if (isReviewContext(currentPage)) showTransient('review', 2400)
  }, [currentPage, showTransient])

  // A saved manual position remains authoritative until a page change or an
  // asynchronous render places a control underneath it. In that case WALT
  // makes a temporary, non-persisted safety move and keeps the saved anchor.
  useEffect(() => {
    let frame = null
    let settleTimer = null
    const revalidate = () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(settleTimer)
      frame = window.requestAnimationFrame(() => {
        settleTimer = window.setTimeout(() => {
          if (openRef.current || dragRef.current) return
          const size = getMascotSize()
          const obstacles = collectObstacles()
          const origin = positionRef.current
          if (isWaltPositionClear(origin, size, obstacles)) return
          const safe = findWaltRoamPosition(origin, viewportBounds(), size, obstacles, 220)
          if (safe.x === origin.x && safe.y === origin.y) return
          positionRef.current = safe
          setDragState(safe.x < origin.x ? 'walking-left' : 'walking-right')
          setRoaming(true)
          setPosition(safe)
          setEdge(safe.x < window.innerWidth / 2 ? 'left' : 'right')
          roamFinishRef.current = window.setTimeout(() => { setRoaming(false); setDragState('dragging') }, 1200)
        }, 80)
      })
    }
    const content = document.querySelector('.main-shell')
    const observer = content ? new MutationObserver(revalidate) : null
    observer?.observe(content, { childList: true, subtree: true })
    window.addEventListener('resize', revalidate)
    window.visualViewport?.addEventListener('resize', revalidate)
    revalidate()
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', revalidate)
      window.visualViewport?.removeEventListener('resize', revalidate)
      window.cancelAnimationFrame(frame)
      window.clearTimeout(settleTimer)
    }
  }, [collectObstacles, currentPage, getMascotSize])

  useEffect(() => {
    if (chat.activityState === 'success') showTransient('success', 1900)
    if (chat.activityState === 'error') setRestingState('error')
  }, [chat.activityState, showTransient])

  useEffect(() => {
    if (!open) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') closePanel() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [closePanel, open])

  const state = dragging
    ? dragState
    : roaming
      ? dragState
      : chat.loading
        ? chat.activityState
        : (inputFocused || chat.input.trim())
          ? 'listening'
          : ['success', 'error'].includes(chat.activityState)
            ? chat.activityState
            : restingState

  const onPointerDown = (event) => {
    if (event.button !== 0) return
    window.clearTimeout(roamFinishRef.current)
    if (roaming) {
      const bounds = shellRef.current?.getBoundingClientRect()
      const captured = bounds ? { x: bounds.left, y: bounds.top } : positionRef.current
      positionRef.current = captured
      setPosition(captured)
      setRoaming(false)
    }
    markActive()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      pointerId: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
      previousX: event.clientX,
      origin: positionRef.current,
      dragged: false,
    }
  }

  const onPointerMove = (event) => {
    const active = dragRef.current
    if (!active || active.pointerId !== event.pointerId) return
    const current = { x: event.clientX, y: event.clientY }
    if (!active.dragged && isDragGesture(active.start, current)) {
      active.dragged = true
      setDragging(true)
      setOpen(false)
      setPanelMounted(false)
      setPanelClosing(false)
    }
    if (!active.dragged) return
    const horizontalDelta = current.x - active.previousX
    setDragState(Math.abs(horizontalDelta) < 1 ? 'dragging' : horizontalDelta < 0 ? 'walking-left' : 'walking-right')
    active.previousX = current.x
    const desired = {
      x: active.origin.x + current.x - active.start.x,
      y: active.origin.y + current.y - active.start.y,
    }
    const next = clampWaltPosition(desired, viewportBounds(), getMascotSize())
    positionRef.current = next
    setPosition(next)
    setEdge(next.x < window.innerWidth / 2 ? 'left' : 'right')
  }

  const finishPointer = (event) => {
    const active = dragRef.current
    if (!active || active.pointerId !== event.pointerId) return
    if (active.dragged) {
      const size = getMascotSize()
      const released = positionRef.current
      const validRelease = isWaltPositionClear(released, size, collectObstacles())
        ? released
        : findWaltRoamPosition(released, viewportBounds(), size, collectObstacles(), 110)
      keepPositionVisible(validRelease)
      suppressClickRef.current = true
      window.setTimeout(() => { suppressClickRef.current = false }, 0)
    }
    setDragging(false)
    setDragState('dragging')
    dragRef.current = null
  }

  const toggleOpen = () => {
    if (suppressClickRef.current) return
    if (open) closePanel()
    else openPanel()
  }

  const viewport = viewportBounds()
  const responsiveMascotSize = viewport.width <= 520
    ? { width: 126, height: 116 }
    : viewport.width <= 760
      ? { width: 150, height: 139 }
      : { width: 168, height: 152 }
  const popupPlacement = calculateWaltPopupPosition(
    { ...position, ...responsiveMascotSize },
    viewport,
    { width: 580, height: 680 },
  )
  return <div
    ref={shellRef}
    className={`walt-assistant-shell edge-${edge} popup-${popupPlacement.direction} ${open ? 'is-open' : ''} ${dragging ? 'is-dragging' : ''} ${roaming ? 'is-roaming' : ''}`}
    data-state={state}
    style={{ left: `${position.x}px`, top: `${position.y}px` }}
    onPointerEnter={() => {
      window.clearTimeout(roamFinishRef.current)
      if (roaming) {
        const bounds = shellRef.current?.getBoundingClientRect()
        if (bounds) {
          const captured = { x: bounds.left, y: bounds.top }
          positionRef.current = captured
          setPosition(captured)
        }
      }
      setRoaming(false)
      markActive()
      if (!open && restingState === 'sleeping') { greet(); showTransient('waking', 1300) }
    }}
  >
    {panelMounted && <WaltPanel
      capabilities={capabilities}
      closing={panelClosing}
      contextCards={contextCards}
      error={chat.error}
      input={chat.input}
      lastQuestion={chat.lastQuestion}
      loading={chat.loading}
      messages={chat.messages}
      onClearChat={chat.clearChat}
      onConfirmAction={chat.confirmAction}
      onDismissAction={chat.dismissAction}
      onClose={closePanel}
      onInput={(value) => { chat.setInput(value); markActive() }}
      onInputBlur={() => setInputFocused(false)}
      onInputFocus={() => { setInputFocused(true); markActive() }}
      onMinimize={closePanel}
      placement={popupPlacement}
      requestActions={requestActions}
      onRetry={chat.retry}
      onSend={chat.send}
      riskCount={riskCount}
      state={state}
    />}
    {!open && showGreeting && <span className="walt-hello" role="status">
      {greetingCopy.lead}{greetingCopy.lead ? ' ' : ''}<b>{greetingCopy.name}</b>{greetingCopy.trail}
    </span>}
    <button
      ref={triggerRef}
      className="walt-mascot-button"
      onClick={toggleOpen}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finishPointer}
      onPointerCancel={finishPointer}
      onLostPointerCapture={finishPointer}
      aria-expanded={open}
      aria-label={open ? 'Minimize WALT assistant' : 'Open WALT assistant'}
      title="Click to ask WALT · drag to reposition"
    >
      <span className="walt-hover-identity"><b>WALT</b><small>Warehouse Action &amp; Logistics Twin</small></span>
      <WaltMascot state={state} riskCount={riskCount} unread={chat.unread} />
    </button>
  </div>
}

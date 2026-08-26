import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  calculateWaltPopupPosition,
  clampWaltPosition,
  isDragGesture,
  parseStoredWaltPosition,
  WALT_DRAG_THRESHOLD,
  WALT_STORAGE_KEY,
} from '../../utils/waltPosition'
import { WaltMascot } from './WaltMascot'
import { WaltPanel } from './WaltPanel'
import { useWaltChat } from './useWaltChat'
import { buildWaltContextCards, isReviewContext } from './waltModel'
import './walt.css'

const SLEEP_AFTER_MS = 45000

function viewportBounds() {
  return {
    width: Math.round(window.visualViewport?.width || window.innerWidth),
    height: Math.round(window.visualViewport?.height || window.innerHeight),
  }
}

export function WaltAssistant({
  anomalies = [],
  capabilities,
  currentPage = 'command',
  dashboard,
  onChatStream,
  onWaltConfirm,
  onWaltFeedback,
  onWaltResolve,
  requestId,
  requestActions = [],
  riskCount = 0,
}) {
  const [open, setOpen] = useState(false)
  const [panelMounted, setPanelMounted] = useState(false)
  const [panelClosing, setPanelClosing] = useState(false)
  const [inputFocused, setInputFocused] = useState(false)
  const [restingState, setRestingState] = useState('greeting')
  const sleepTimerRef = useRef(null)
  const transientTimerRef = useRef(null)
  const panelTimerRef = useRef(null)
  const openRef = useRef(open)
  const shellRef = useRef(null)
  const dragRef = useRef(null)
  const suppressClickRef = useRef(false)

  const getMascotSize = useCallback(() => {
    const width = window.innerWidth
    if (width <= 520) return { width: 126, height: 116 }
    if (width <= 760) return { width: 150, height: 139 }
    return { width: 168, height: 152 }
  }, [])

  const [position, setPosition] = useState(() => {
    const stored = parseStoredWaltPosition(localStorage.getItem(WALT_STORAGE_KEY))
    const viewport = viewportBounds()
    const size = viewport.width <= 520 ? { width: 126, height: 116 } : viewport.width <= 760 ? { width: 150, height: 139 } : { width: 168, height: 152 }
    const defaultPos = {
      x: 24,
      y: Math.max(12, viewport.height - size.height - 18),
    }
    if (stored) {
      return clampWaltPosition(stored, viewport, size)
    }
    return defaultPos
  })
  const positionRef = useRef(position)
  const [dragging, setDragging] = useState(false)
  const [edge, setEdge] = useState(() => (position.x < (window.innerWidth / 2) ? 'left' : 'right'))

  const chat = useWaltChat(onChatStream, onWaltResolve, onWaltConfirm, onWaltFeedback, open, requestId)
  const contextCards = useMemo(() => buildWaltContextCards(dashboard, anomalies), [dashboard, anomalies])

  useEffect(() => { openRef.current = open }, [open])
  useEffect(() => { positionRef.current = position }, [position])

  useEffect(() => {
    if (open) {
      document.body.classList.add('walt-chat-active')
    } else {
      document.body.classList.remove('walt-chat-active')
    }
    return () => {
      document.body.classList.remove('walt-chat-active')
    }
  }, [open])

  const showTransient = useCallback((state, duration = 1600) => {
    window.clearTimeout(transientTimerRef.current)
    setRestingState(state)
    transientTimerRef.current = window.setTimeout(() => setRestingState('greeting'), duration)
  }, [])

  const markActive = useCallback(() => {
    window.clearTimeout(sleepTimerRef.current)
    setRestingState((state) => state === 'sleeping' ? 'greeting' : state)
    sleepTimerRef.current = window.setTimeout(() => {
      if (!openRef.current) setRestingState('sleeping')
    }, SLEEP_AFTER_MS)
  }, [])

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
    setPanelClosing(false)
    setPanelMounted(true)
    setOpen(true)
    showTransient('greeting', 1600)
    markActive()
  }, [markActive, showTransient])

  useEffect(() => {
    markActive()
    showTransient('greeting', 2200)
    return () => {
      window.clearTimeout(sleepTimerRef.current)
      window.clearTimeout(transientTimerRef.current)
      window.clearTimeout(panelTimerRef.current)
    }
  }, [markActive, showTransient])

  useEffect(() => {
    if (riskCount > 0) showTransient('warning', 1900)
  }, [riskCount, showTransient])

  useEffect(() => {
    if (isReviewContext(currentPage)) showTransient('review', 2400)
  }, [currentPage, showTransient])

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

  // Keep WALT within viewport on window resize
  useEffect(() => {
    const onResize = () => {
      const clamped = clampWaltPosition(positionRef.current, viewportBounds(), getMascotSize())
      positionRef.current = clamped
      setPosition(clamped)
      setEdge(clamped.x < (window.innerWidth / 2) ? 'left' : 'right')
    }
    window.addEventListener('resize', onResize)
    window.visualViewport?.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.visualViewport?.removeEventListener('resize', onResize)
    }
  }, [getMascotSize])

  const onPointerDown = (event) => {
    if (event.button !== 0) return
    markActive()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: positionRef.current.x,
      originY: positionRef.current.y,
      dragged: false,
    }
  }

  const onPointerMove = (event) => {
    const active = dragRef.current
    if (!active || active.pointerId !== event.pointerId) return
    const current = { x: event.clientX, y: event.clientY }
    const start = { x: active.startX, y: active.startY }

    if (!active.dragged) {
      if (!isDragGesture(start, current, WALT_DRAG_THRESHOLD)) return
      active.dragged = true
      setDragging(true)
    }

    const deltaX = current.x - start.x
    const deltaY = current.y - start.y
    const nextPos = clampWaltPosition(
      { x: active.originX + deltaX, y: active.originY + deltaY },
      viewportBounds(),
      getMascotSize(),
    )
    positionRef.current = nextPos
    setPosition(nextPos)
    setEdge(nextPos.x < (window.innerWidth / 2) ? 'left' : 'right')
  }

  const onPointerUp = (event) => {
    const active = dragRef.current
    if (!active || active.pointerId !== event.pointerId) return
    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
    } catch {
      // ignore pointer capture errors
    }
    dragRef.current = null
    setDragging(false)

    if (active.dragged) {
      const finalPos = clampWaltPosition(positionRef.current, viewportBounds(), getMascotSize())
      positionRef.current = finalPos
      setPosition(finalPos)
      try {
        localStorage.setItem(WALT_STORAGE_KEY, JSON.stringify(finalPos))
      } catch {
        // ignore storage errors
      }
      suppressClickRef.current = true
      window.setTimeout(() => {
        suppressClickRef.current = false
      }, 60)
    }
  }

  const state = dragging
    ? 'dragging'
    : chat.loading
      ? chat.activityState
      : (inputFocused || chat.input.trim())
        ? 'listening'
        : ['success', 'error'].includes(chat.activityState)
          ? chat.activityState
          : restingState

  const toggleOpen = () => {
    if (open) closePanel()
    else openPanel()
  }

  const viewport = viewportBounds()
  const responsiveMascotSize = getMascotSize()
  const popupPlacement = calculateWaltPopupPosition(
    {
      x: position.x,
      y: position.y,
      ...responsiveMascotSize,
    },
    viewport,
    { width: 580, height: 680 },
  )

  return (
    <>
      {panelMounted && (
        <div
          className={`walt-backdrop ${panelClosing ? 'is-closing' : ''}`}
          onClick={closePanel}
          aria-hidden="true"
        />
      )}
      <div
        ref={shellRef}
        className={`walt-assistant-shell edge-${edge} popup-${popupPlacement.direction} ${open ? 'is-open' : ''} ${dragging ? 'is-dragging' : ''}`}
        data-state={state}
        style={{ left: `${position.x}px`, top: `${position.y}px` }}
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
      onCancel={chat.cancel}
      onFeedback={chat.rateMessage}
      riskCount={riskCount}
      state={state}
    />}
    {!open && <span className="walt-hello" role="status">
      <span className="walt-hello-wave">👋</span>
      <span>Hi, I am <b>WALT</b>!</span>
    </span>}
    <button
      className="walt-mascot-button"
      onClick={() => {
        if (suppressClickRef.current) return
        toggleOpen()
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      aria-expanded={open}
      aria-label={open ? 'Minimize WALT assistant' : 'Open WALT assistant'}
      title="Drag WALT anywhere or click to ask"
    >
      <span className="walt-hover-identity"><b>WALT</b><small>Warehouse Action &amp; Logistics Twin</small></span>
      <WaltMascot state={state} riskCount={riskCount} unread={chat.unread} />
    </button>
  </div>
</>
  )
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { calculateWaltPopupPosition } from '../../utils/waltPosition'
import { WaltMascot } from './WaltMascot'
import { WaltPanel } from './WaltPanel'
import { useWaltChat } from './useWaltChat'
import { buildWaltContextCards, isReviewContext } from './waltModel'
import './walt.css'

const SLEEP_AFTER_MS = 45000
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
  const [showGreeting, setShowGreeting] = useState(true)
  const [greetingCopy, setGreetingCopy] = useState(WALT_GREETING_COPY[0])
  const sleepTimerRef = useRef(null)
  const transientTimerRef = useRef(null)
  const greetingTimerRef = useRef(null)
  const greetingIndexRef = useRef(0)
  const panelTimerRef = useRef(null)
  const openRef = useRef(open)
  const chat = useWaltChat(onChatStream, onWaltResolve, onWaltConfirm, onWaltFeedback, open, requestId)
  const contextCards = useMemo(() => buildWaltContextCards(dashboard, anomalies), [dashboard, anomalies])

  useEffect(() => { openRef.current = open }, [open])
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
    greet()
    showTransient('greeting', 1600)
    markActive()
  }, [greet, markActive, showTransient])

  useEffect(() => {
    markActive()
    greet()
    showTransient('greeting', 2200)
    return () => {
      window.clearTimeout(sleepTimerRef.current)
      window.clearTimeout(transientTimerRef.current)
      window.clearTimeout(greetingTimerRef.current)
      window.clearTimeout(panelTimerRef.current)
    }
  }, [greet, markActive, showTransient])

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

  const state = chat.loading
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
  const responsiveMascotSize = viewport.width <= 520
    ? { width: 126, height: 116 }
    : viewport.width <= 760
      ? { width: 150, height: 139 }
      : { width: 168, height: 152 }
  const popupPlacement = calculateWaltPopupPosition(
    {
      x: viewport.width - responsiveMascotSize.width - 18,
      y: viewport.height - responsiveMascotSize.height - 16,
      ...responsiveMascotSize,
    },
    viewport,
    { width: 580, height: 680 },
  )
  return <div
    className={`walt-assistant-shell walt-static edge-right popup-${popupPlacement.direction} ${open ? 'is-open' : ''}`}
    data-state={state}
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
    {!open && showGreeting && <span className="walt-hello" role="status">
      {greetingCopy.lead}{greetingCopy.lead ? ' ' : ''}<b>{greetingCopy.name}</b>{greetingCopy.trail}
    </span>}
    <button
      className="walt-mascot-button"
      onClick={toggleOpen}
      aria-expanded={open}
      aria-label={open ? 'Minimize WALT assistant' : 'Open WALT assistant'}
      title="Click to ask WALT"
    >
      <span className="walt-hover-identity"><b>WALT</b><small>Warehouse Action &amp; Logistics Twin</small></span>
      <WaltMascot state={state} riskCount={riskCount} unread={chat.unread} />
    </button>
  </div>
}

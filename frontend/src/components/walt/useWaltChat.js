import { useEffect, useRef, useState } from 'react'

const initialMessage = {
  role: 'assistant',
  content: 'Ask about live risks, your manager, your role and site scope, an approval owner, or tell me to prepare a reminder or escalation.',
  source: 'operational_evidence',
}

const REQUEST_TIMEOUT_MS = 30000

export function useWaltChat(onChatStream, onResolve, onConfirm, onFeedback, open, requestId) {
  const [messages, setMessages] = useState([initialMessage])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activityState, setActivityState] = useState('waiting')
  const [error, setError] = useState('')
  const [unread, setUnread] = useState(false)
  const [lastQuestion, setLastQuestion] = useState('')
  const openRef = useRef(open)
  const loadingRef = useRef(false)
  const requestRef = useRef(requestId)
  const conversationVersionRef = useRef(0)
  const successTimerRef = useRef(null)
  const requestControllerRef = useRef(null)
  const timeoutRef = useRef(null)

  useEffect(() => {
    openRef.current = open
    if (open) setUnread(false)
  }, [open])

  useEffect(() => () => {
    requestControllerRef.current?.abort()
    window.clearTimeout(successTimerRef.current)
    window.clearTimeout(timeoutRef.current)
  }, [])

  useEffect(() => {
    if (requestRef.current === requestId) return
    requestRef.current = requestId
    conversationVersionRef.current += 1
    requestControllerRef.current?.abort()
    window.clearTimeout(timeoutRef.current)
    loadingRef.current = false
    window.clearTimeout(successTimerRef.current)
    setMessages([initialMessage])
    setInput('')
    setLoading(false)
    setActivityState('waiting')
    setError('')
    setUnread(false)
    setLastQuestion('')
  }, [requestId])

  const clearChat = () => {
    if (loadingRef.current) return
    conversationVersionRef.current += 1
    window.clearTimeout(successTimerRef.current)
    setMessages([initialMessage])
    setInput('')
    setError('')
    setUnread(false)
    setLastQuestion('')
    setActivityState('waiting')
  }

  const send = async (prompt = input) => {
    const question = prompt.trim()
    if (!question || loadingRef.current) return
    loadingRef.current = true
    const conversationVersion = conversationVersionRef.current
    const selectedRequestId = requestRef.current
    const history = messages.filter((message) => message.content).map(({ role, content }) => ({ role, content }))
    const assistantId = `walt-${Date.now()}-${Math.random().toString(36).slice(2)}`
    setMessages((current) => [...current, { role: 'user', content: question }, { id: assistantId, role: 'assistant', content: '', source: 'streaming' }])
    setInput('')
    setLastQuestion(question)
    setError('')
    setLoading(true)
    window.clearTimeout(successTimerRef.current)
    setActivityState('thinking')
    const controller = new AbortController()
    requestControllerRef.current = controller
    timeoutRef.current = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      const resolution = onResolve ? await onResolve({ message: question, history, request_id: selectedRequestId || undefined }, controller.signal) : { handled: false }
      if (conversationVersion !== conversationVersionRef.current) return
      if (resolution.handled) {
        setMessages((current) => current.map((message) => message.id === assistantId ? {
          ...message,
          content: resolution.answer || 'The governed command was evaluated.',
          source: 'governance',
          action: resolution.action,
          choices: (resolution.choices || []).map((choice) => ({ ...choice, prompt: `${question} ${choice.request_id}` })),
          responseType: resolution.type,
        } : message))
        setLoading(false)
        loadingRef.current = false
        setActivityState(resolution.type === 'denied' || resolution.type === 'guardrail' ? 'warning' : resolution.type === 'action_preview' ? 'review' : 'success')
        successTimerRef.current = window.setTimeout(() => setActivityState('waiting'), 2200)
        if (!openRef.current) setUnread(true)
        return
      }
      await onChatStream({ message: question, history, request_id: selectedRequestId || undefined }, (event, payload) => {
        if (conversationVersion !== conversationVersionRef.current) return
        if (event === 'trace') setActivityState('analysing')
        if (event === 'delta' || event === 'reset') setActivityState('speaking')
        setMessages((current) => current.map((message) => {
          if (message.id !== assistantId) return message
          if (event === 'trace') return { ...message, trace: Array.isArray(payload) ? payload : [] }
          if (event === 'delta') return { ...message, content: message.content + payload.text }
          if (event === 'reset') return { ...message, content: payload.text || '', source: 'operational_evidence' }
          if (event === 'done') return {
            ...message,
            source: payload.source || 'operational_evidence',
            citedAnomalyIds: payload.cited_anomaly_ids || [],
            suggestions: payload.suggested_actions || [],
            confidence: payload.confidence || 'medium',
            sourceRefs: payload.source_refs || payload.cited_anomaly_ids || [],
          }
          return message
        }))
        if (event === 'done') {
          setLoading(false)
          setActivityState('success')
          successTimerRef.current = window.setTimeout(() => setActivityState('waiting'), 2200)
          if (!openRef.current) setUnread(true)
        }
      }, controller.signal)
    } catch (cause) {
      if (conversationVersion !== conversationVersionRef.current) return
      const cancelled = controller.signal.aborted
      setError(cancelled ? 'Request cancelled.' : `Live evidence request failed: ${cause.message}`)
      setMessages((current) => current.map((message) => message.id === assistantId
        ? { ...message, source: cancelled ? 'request_cancelled' : 'request_error', content: cancelled ? 'I stopped that request. Ask again whenever you’re ready.' : 'WALT could not complete the evidence request. Retry when the operations connection is available.' }
        : message))
      setActivityState(cancelled ? 'waiting' : 'error')
    } finally {
      window.clearTimeout(timeoutRef.current)
      if (requestControllerRef.current === controller) requestControllerRef.current = null
      if (conversationVersion === conversationVersionRef.current) {
        loadingRef.current = false
        setLoading(false)
      }
    }
  }

  const cancel = () => {
    if (!loadingRef.current) return
    requestControllerRef.current?.abort()
  }

  const rateMessage = async (messageId, rating) => {
    setMessages((current) => current.map((message) => message.id === messageId ? { ...message, feedback: rating } : message))
    const message = messages.find((item) => item.id === messageId)
    try { await onFeedback?.({ message_id: messageId, rating, question: lastQuestion, answer: message?.content || '' }) } catch { /* local feedback remains visible if the audit endpoint is unavailable */ }
  }

  const confirmAction = async (messageId, action) => {
    if (!action || loadingRef.current || !onConfirm) return
    loadingRef.current = true
    setLoading(true)
    setError('')
    setActivityState('thinking')
    setMessages((current) => current.map((message) => message.id === messageId
      ? { ...message, action: { ...action, status: 'confirming' } }
      : message))
    try {
      const receipt = await onConfirm(action)
      setMessages((current) => current.map((message) => message.id === messageId
        ? {
            ...message,
            action: { ...action, status: 'confirmed', confirmed_at: receipt.confirmed_at },
            content: `${message.content}\n\n**Notification sent.** ${action.recipient_name} received the ${action.kind} for ${action.request_id}. The delivery is recorded in the audit trail.`,
          }
        : message))
      setActivityState('success')
      successTimerRef.current = window.setTimeout(() => setActivityState('waiting'), 2200)
    } catch (cause) {
      setError(`Governed action failed: ${cause.message}`)
      setMessages((current) => current.map((message) => message.id === messageId
        ? { ...message, action: { ...action, status: 'failed', error: cause.message } }
        : message))
      setActivityState('error')
    } finally {
      loadingRef.current = false
      setLoading(false)
    }
  }

  const dismissAction = (messageId) => {
    if (loadingRef.current) return
    setMessages((current) => current.map((message) => message.id === messageId
      ? { ...message, action: { ...message.action, status: 'dismissed' } }
      : message))
  }

  return {
    activityState,
    cancel,
    clearChat,
    confirmAction,
    dismissAction,
    error,
    input,
    lastQuestion,
    loading,
    messages,
    retry: () => send(lastQuestion),
    rateMessage,
    send,
    setInput,
    unread,
  }
}

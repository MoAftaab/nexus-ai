import { CheckCircle2, X } from 'lucide-react'

export function Toast({ message, onClose }) {
  if (!message) return null
  return <div className="toast" role="status"><CheckCircle2 size={19} /><span>{message}</span><button onClick={onClose} aria-label="Dismiss"><X size={16} /></button></div>
}


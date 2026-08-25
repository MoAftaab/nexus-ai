export const currency = (value, compact = false) => {
  const num = Number(value) || 0
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: compact || num >= 1_000_000 ? 1 : 0,
    notation: compact || num >= 1_000_000 ? 'compact' : 'standard',
  }).format(num)
}

export const compactCurrency = (value) => {
  const num = Number(value) || 0
  if (num === 0) return '€0'
  if (num < 1000) return `€${Math.round(num)}`
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: num >= 1_000_000 ? 1 : 0,
    notation: 'compact',
  }).format(num)
}
export const number = (value) => new Intl.NumberFormat('en-US').format(value)
export const timeAgo = (iso) => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000))
  return minutes < 1 ? 'now' : minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes / 60)}h ago`
}
export const severityLabel = (value) => value === 'critical' ? 'Critical' : value.charAt(0).toUpperCase() + value.slice(1)


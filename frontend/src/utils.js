export const currency = (value) => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0, notation: value >= 1_000_000 ? 'compact' : 'standard' }).format(value)
export const number = (value) => new Intl.NumberFormat('en-US').format(value)
export const timeAgo = (iso) => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000))
  return minutes < 1 ? 'now' : minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes / 60)}h ago`
}
export const severityLabel = (value) => value === 'critical' ? 'Critical' : value.charAt(0).toUpperCase() + value.slice(1)


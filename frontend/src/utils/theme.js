export function normalizeTheme(value, prefersDark = false) {
  if (value === 'dark' || value === 'vw') return 'dark'
  if (value === 'light' || value === 'default') return 'light'
  return prefersDark ? 'dark' : 'light'
}

export function nextTheme(current) {
  return current === 'dark' ? 'light' : 'dark'
}

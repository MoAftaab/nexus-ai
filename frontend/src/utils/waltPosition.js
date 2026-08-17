export const WALT_DRAG_THRESHOLD = 7
export const WALT_STORAGE_KEY = 'nexusai.walt.position.v1'

const clamp = (value, minimum, maximum) => Math.min(Math.max(value, minimum), maximum)

export function isDragGesture(start, current, threshold = WALT_DRAG_THRESHOLD) {
  if (!start || !current) return false
  return Math.hypot(current.x - start.x, current.y - start.y) >= threshold
}

export function clampWaltPosition(position, viewport, size, margin = 12) {
  const maximumX = Math.max(margin, viewport.width - size.width - margin)
  const maximumY = Math.max(margin, viewport.height - size.height - margin)
  return {
    x: clamp(Number(position?.x) || 0, margin, maximumX),
    y: clamp(Number(position?.y) || 0, margin, maximumY),
  }
}

function overlaps(candidate, size, obstacle, padding) {
  const left = candidate.x - padding
  const right = candidate.x + size.width + padding
  const top = candidate.y - padding
  const bottom = candidate.y + size.height + padding
  return left < obstacle.right && right > obstacle.left && top < obstacle.bottom && bottom > obstacle.top
}

export function isWaltPositionClear(position, size, obstacles = [], padding = 8) {
  return !obstacles.some((obstacle) => overlaps(position, size, obstacle, padding))
}

export function calculateWaltPopupPosition(mascot, viewport, preferredSize, gap = 12, margin = 12) {
  const maximumWidth = Math.max(1, viewport.width - (margin * 2))
  const maximumHeight = Math.max(1, viewport.height - (margin * 2))
  const desiredWidth = Math.min(preferredSize.width, maximumWidth)
  const desiredHeight = Math.min(preferredSize.height, maximumHeight)
  const spaces = {
    left: mascot.x - margin - gap,
    right: viewport.width - (mascot.x + mascot.width) - margin - gap,
    above: mascot.y - margin - gap,
    below: viewport.height - (mascot.y + mascot.height) - margin - gap,
  }
  const horizontalMinimum = Math.min(360, maximumWidth)
  const verticalMinimum = Math.min(240, maximumHeight)
  const candidates = [
    { direction: 'left', available: spaces.left, horizontal: true },
    { direction: 'right', available: spaces.right, horizontal: true },
    { direction: 'above', available: spaces.above, horizontal: false },
    { direction: 'below', available: spaces.below, horizontal: false },
  ].map((candidate) => {
    const target = candidate.horizontal ? desiredWidth : desiredHeight
    const minimum = candidate.horizontal ? horizontalMinimum : verticalMinimum
    const usable = Math.min(target, Math.max(0, candidate.available))
    return {
      ...candidate,
      usable,
      valid: usable >= minimum,
      score: (usable / target) + (usable >= target ? 2 : 0) + (candidate.horizontal ? .25 : 0),
    }
  }).sort((left, right) => (Number(right.valid) - Number(left.valid)) || right.score - left.score)

  const choice = candidates[0]
  const width = choice.horizontal ? choice.usable : desiredWidth
  const height = choice.horizontal ? desiredHeight : choice.usable
  let x
  let y
  if (choice.direction === 'left') {
    x = mascot.x - gap - width
    y = mascot.y + (mascot.height / 2) - (height / 2)
  } else if (choice.direction === 'right') {
    x = mascot.x + mascot.width + gap
    y = mascot.y + (mascot.height / 2) - (height / 2)
  } else if (choice.direction === 'above') {
    x = mascot.x + (mascot.width / 2) - (width / 2)
    y = mascot.y - gap - height
  } else {
    x = mascot.x + (mascot.width / 2) - (width / 2)
    y = mascot.y + mascot.height + gap
  }

  return {
    direction: choice.direction,
    height,
    width,
    x: clamp(x, margin, Math.max(margin, viewport.width - width - margin)),
    y: clamp(y, margin, Math.max(margin, viewport.height - height - margin)),
  }
}

export function findWaltRoamPosition(position, viewport, size, obstacles = [], distance = 72) {
  const offsets = [
    { x: distance, y: 0 },
    { x: -distance, y: 0 },
    { x: 0, y: -distance * .65 },
    { x: 0, y: distance * .65 },
    { x: distance * .7, y: -distance * .45 },
    { x: -distance * .7, y: -distance * .45 },
  ]
  for (const offset of offsets) {
    const candidate = clampWaltPosition({ x: position.x + offset.x, y: position.y + offset.y }, viewport, size)
    if (isWaltPositionClear(candidate, size, obstacles)) return candidate
  }
  const origin = clampWaltPosition(position, viewport, size)
  if (isWaltPositionClear(origin, size, obstacles)) return origin

  // A page may render a large control group underneath a persisted position
  // after WALT mounts. If every local nudge is occupied, search the viewport
  // for the nearest clear resting place instead of leaving an action covered.
  const margin = 12
  const maximumX = Math.max(margin, viewport.width - size.width - margin)
  const maximumY = Math.max(margin, viewport.height - size.height - margin)
  const stepX = Math.max(56, Math.round(size.width * .55))
  const stepY = Math.max(48, Math.round(size.height * .5))
  const xs = [margin, maximumX]
  const ys = [margin, maximumY]
  for (let x = margin; x <= maximumX; x += stepX) xs.push(Math.min(x, maximumX))
  for (let y = margin; y <= maximumY; y += stepY) ys.push(Math.min(y, maximumY))
  const candidates = [...new Map(xs.flatMap((x) => ys.map((y) => {
    const candidate = { x, y }
    return [`${x}:${y}`, candidate]
  }))).values()]
    .sort((first, second) => Math.hypot(first.x - origin.x, first.y - origin.y) - Math.hypot(second.x - origin.x, second.y - origin.y))
  return candidates.find((candidate) => isWaltPositionClear(candidate, size, obstacles)) || origin
}

export function parseStoredWaltPosition(raw) {
  try {
    const parsed = JSON.parse(raw)
    if (!Number.isFinite(parsed?.x) || !Number.isFinite(parsed?.y)) return null
    return { x: parsed.x, y: parsed.y }
  } catch {
    return null
  }
}

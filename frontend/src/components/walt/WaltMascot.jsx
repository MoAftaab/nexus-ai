import { getAtlasAnimation } from './waltModel'

export function WaltMascot({ state = 'idle', compact = false, riskCount = 0, unread = false }) {
  const animation = getAtlasAnimation(state)
  const style = {
    '--walt-atlas-row': `${animation.row * 12.5}%`,
    '--walt-frame-end': `${(animation.frames / 7) * 100}%`,
    '--walt-cycle': `${animation.frames / animation.fps}s`,
    '--walt-frame-steps': `steps(${animation.frames})`,
  }

  return <span
    className={`walt-atlas-mascot ${compact ? 'is-compact' : ''}`}
    data-state={state}
    data-atlas-state={animation.id}
    data-has-risk={riskCount > 0}
    style={style}
    aria-hidden="true"
  >
    <span className="walt-atlas-frame" />
    {(state === 'analysing' || state === 'review') && <span className="walt-data-projection"><i /><i /><i /><b /></span>}
    {state === 'speaking' && <span className="walt-speaking-bars"><i /><i /><i /></span>}
    {state === 'warning' && <span className="walt-risk-pulse" />}
    {unread && <span className="walt-unread-dot" />}
  </span>
}

export function VwLogo({ size = 26, className = '', animated = true }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`vw-roundel-logo ${animated ? 'is-animated' : ''} ${className}`}
      aria-label="Volkswagen Logo"
    >
      {/* Outer circular ring */}
      <circle
        className="vw-stroke-circle"
        cx="100"
        cy="100"
        r="86.5"
        stroke="currentColor"
        strokeWidth="7.5"
      />
      {/* Upper 'V' */}
      <polyline
        className="vw-stroke-v"
        points="73.3,17.7 100,92 126.7,17.7"
        stroke="currentColor"
        strokeWidth="7.5"
        strokeLinecap="round"
        strokeLinejoin="miter"
      />
      {/* Lower 'W' */}
      <polyline
        className="vw-stroke-w"
        points="32.3,46.4 75.8,183 100,108 124.2,183 167.7,46.4"
        stroke="currentColor"
        strokeWidth="7.5"
        strokeLinecap="round"
        strokeLinejoin="miter"
      />
    </svg>
  )
}

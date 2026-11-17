// Favor 标志：日出渐变底 + 白色心形（关怀）+ 海军蓝心电线（健康）+ 右上角四芒星（AI）。
// 48×48 网格绘制，16px favicon 下仍可辨认。animated 时心电线描出、心形轻跳、星芒闪烁。
import { useId } from 'react'

const HEART = 'M24 38.5C24 38.5 10.5 30.6 10.5 20.6C10.5 15.6 14.3 12 18.8 12C21.3 12 23 13.3 24 15.1C25 13.3 26.7 12 29.2 12C33.7 12 37.5 15.6 37.5 20.6C37.5 30.6 24 38.5 24 38.5Z'
const PULSE = 'M12.5 24H18.6L21.2 18.6L25 30L27.8 21.6L29.8 24H35.5'
const SPARK = 'M38.6 5.6C39.1 8.9 40.1 9.9 43.4 10.4C40.1 10.9 39.1 11.9 38.6 15.2C38.1 11.9 37.1 10.9 33.8 10.4C37.1 9.9 38.1 8.9 38.6 5.6Z'

export function LogoMark({ size = 36, animated = false, className = '' }: { size?: number; animated?: boolean; className?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg className={`logo-mark ${animated ? 'is-animated' : ''} ${className}`} width={size} height={size} viewBox="0 0 48 48"
      role="img" aria-label="Favor">
      <defs>
        <linearGradient id={`${id}-bg`} x1="4" y1="2" x2="44" y2="46" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FF5A2A" />
          <stop offset=".55" stopColor="#FF7E3F" />
          <stop offset="1" stopColor="#FFB547" />
        </linearGradient>
        <radialGradient id={`${id}-shine`} cx="12" cy="8" r="30" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" stopOpacity=".38" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-heart`} x1="24" y1="12" x2="24" y2="38.5" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" />
          <stop offset="1" stopColor="#FFF1E6" />
        </linearGradient>
        <filter id={`${id}-shadow`} x="-20%" y="-20%" width="140%" height="150%">
          <feDropShadow dx="0" dy="1.6" stdDeviation="1.4" floodColor="#B83A0E" floodOpacity=".32" />
        </filter>
      </defs>
      <rect width="48" height="48" rx="14" fill={`url(#${id}-bg)`} />
      <rect width="48" height="48" rx="14" fill={`url(#${id}-shine)`} />
      <g className="logo-heart" filter={`url(#${id}-shadow)`}>
        <path d={HEART} fill={`url(#${id}-heart)`} />
      </g>
      <path className="logo-pulse" d={PULSE} fill="none" stroke="#2E4057" strokeWidth="2.7" strokeLinecap="round"
        strokeLinejoin="round" pathLength={1} />
      <path className="logo-spark" d={SPARK} fill="#fff" />
    </svg>
  )
}

/** 标志 + 字标。tone="light" 用于深色底（侧栏、登录页左栏）。 */
export default function Logo({ size = 36, animated = false, tone = 'dark', subtitle }:
  { size?: number; animated?: boolean; tone?: 'dark' | 'light'; subtitle?: string }) {
  return (
    <span className={`logo-lockup ${tone}`}>
      <LogoMark size={size} animated={animated} />
      <span className="logo-text">
        <span className="logo-word" style={{ fontSize: Math.round(size * 0.52) }}>Fav<span className="logo-o">o</span>r</span>
        {subtitle && <span className="logo-sub">{subtitle}</span>}
      </span>
    </span>
  )
}

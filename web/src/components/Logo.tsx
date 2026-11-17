// Favor 标志：日出渐变底 + 白色小锅（做饭）+ 两缕热气（刚出锅）+ 右上角四芒星（AI）。
// 第 4 期由「心形 + 心电线」改来：产品核心从健康记录回到「冰箱里有什么，今晚做什么」。
// 48×48 网格绘制，16px favicon 下仍可辨认。animated 时热气描出并飘动、锅轻轻一颠、星芒闪烁。
import { useId } from 'react'

// 锅身 + 两侧把手 + 锅盖（一条圆头横线）+ 盖钮
const POT = 'M11 26.2H37V30.4C37 35.1 33.2 38.9 28.5 38.9H19.5C14.8 38.9 11 35.1 11 30.4V26.2Z'
const HANDLES = 'M8 27.4H11M37 27.4H40'
const LID = 'M10.4 23.2H37.6'
const KNOB = 'M21.6 23.2V21.9C21.6 20.6 22.7 19.6 24 19.6C25.3 19.6 26.4 20.6 26.4 21.9V23.2'
const STEAM = 'M19.2 17.8C17.4 15.8 21 13.8 19.2 11.8C18.1 10.6 18.8 9.3 19.6 8.5M28.8 17.8C27 15.8 30.6 13.8 28.8 11.8C27.7 10.6 28.4 9.3 29.2 8.5'
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
        <linearGradient id={`${id}-pot`} x1="24" y1="19" x2="24" y2="39" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" />
          <stop offset="1" stopColor="#FFF1E6" />
        </linearGradient>
        <filter id={`${id}-shadow`} x="-20%" y="-20%" width="140%" height="150%">
          <feDropShadow dx="0" dy="1.6" stdDeviation="1.4" floodColor="#B83A0E" floodOpacity=".32" />
        </filter>
      </defs>
      <rect width="48" height="48" rx="14" fill={`url(#${id}-bg)`} />
      <rect width="48" height="48" rx="14" fill={`url(#${id}-shine)`} />
      <g className="logo-pot" filter={`url(#${id}-shadow)`}>
        <path d={POT} fill={`url(#${id}-pot)`} />
        <path d={HANDLES} stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
        <path d={KNOB} fill="#fff" />
        <path d={LID} stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      </g>
      {/* 热气用半透明白色细长曲线：深色短线放在锅盖上方会像一双眼睛 */}
      <path className="logo-steam" d={STEAM} fill="none" stroke="#fff" strokeOpacity=".92" strokeWidth="2.2" strokeLinecap="round"
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

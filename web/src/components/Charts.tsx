// 轻量 SVG 图表：单序列柱状图（可带目标线）与折线图。单序列不需要图例，标题即名称。
import { useEffect, useRef, useState } from 'react'

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

export interface Point { day: string; value: number | null }

const H = 180
const PAD = { top: 16, right: 8, bottom: 24, left: 36 }

function niceMax(v: number) {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p
}

const fmtDay = (d: string) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`

function xLabels(points: Point[]) {
  const step = Math.ceil(points.length / 7)
  return points.map((p, i) => ((points.length - 1 - i) % step === 0 ? fmtDay(p.day) : ''))
}

export function BarChart({ points, color, unit, target, format = (v: number) => String(v) }:
  { points: Point[]; color: string; unit: string; target?: number; format?: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const max = niceMax(Math.max(target ?? 0, ...points.map(p => p.value ?? 0)) * 1.08)
  const slot = innerW / points.length
  const barW = Math.max(2, Math.min(22, slot - 2))  // 相邻柱之间至少 2px 间隙
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const labels = xLabels(points)
  const r = Math.min(4, barW / 2)

  return (
    <div className="chart-box" ref={ref} onMouseLeave={() => setHover(null)}>
      <svg height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`柱状图，单位 ${unit}`}>
        {[0, 0.5, 1].map(f => (
          <g key={f}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(max * f)} y2={y(max * f)} stroke="var(--line)" strokeDasharray={f ? '3 4' : undefined} />
            <text x={PAD.left - 6} y={y(max * f) + 3.5} textAnchor="end" className="axis-text num">{format(max * f)}</text>
          </g>
        ))}
        {points.map((p, i) => {
          const x = PAD.left + slot * i + (slot - barW) / 2
          const v = p.value ?? 0
          const top = y(v)
          const h = PAD.top + innerH - top
          return (
            <g key={p.day}>
              {v > 0 && (
                <path fill={color} opacity={hover === null || hover === i ? 1 : 0.45} className="bar-grow"
                  style={{ animationDelay: `${Math.min(i * 25, 600)}ms`, transition: 'opacity .2s' }}
                  d={`M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + h} Z`} />
              )}
              <rect x={PAD.left + slot * i} y={PAD.top} width={slot} height={innerH} fill="transparent"
                onMouseEnter={() => setHover(i)} onTouchStart={() => setHover(i)} />
              {labels[i] && <text x={x + barW / 2} y={H - 6} textAnchor="middle" className="axis-text num">{labels[i]}</text>}
            </g>
          )
        })}
        {target !== undefined && target > 0 && (
          <g pointerEvents="none">
            <line x1={PAD.left} x2={width - PAD.right} y1={y(target)} y2={y(target)} stroke="var(--ink-2)" strokeWidth={1.5} strokeDasharray="5 4" />
            <text x={width - PAD.right} y={y(target) - 5} textAnchor="end" className="axis-text"
              stroke="var(--surface)" strokeWidth={4} strokeLinejoin="round" paintOrder="stroke"
              style={{ fill: 'var(--ink-2)' }}>目标 {format(target)}</text>
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="chart-tip" style={{ left: PAD.left + slot * hover + slot / 2, top: y(points[hover].value ?? 0) - 6 }}>
          {fmtDay(points[hover].day)} · <b className="num">{points[hover].value ? format(points[hover].value!) : '无记录'}</b>{points[hover].value ? ` ${unit}` : ''}
        </div>
      )}
    </div>
  )
}

export function LineChart({ points, color, unit }: { points: Point[]; color: string; unit: string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const values = points.map(p => p.value).filter((v): v is number => v !== null)
  const lo = values.length ? Math.floor(Math.min(...values) - 1) : 0
  const hi = values.length ? Math.ceil(Math.max(...values) + 1) : 1
  const x = (i: number) => PAD.left + (points.length === 1 ? innerW / 2 : (innerW * i) / (points.length - 1))
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo || 1)) * innerH
  const labels = xLabels(points)
  // 只连接有数据的点（跳过空日）
  const known = points.map((p, i) => ({ i, v: p.value })).filter(p => p.v !== null) as { i: number; v: number }[]
  const path = known.map((p, k) => `${k ? 'L' : 'M'}${x(p.i)},${y(p.v)}`).join(' ')
  const nearest = (mx: number) => known.reduce((best, p) => (Math.abs(x(p.i) - mx) < Math.abs(x(best.i) - mx) ? p : best), known[0])

  return (
    <div className="chart-box" ref={ref} onMouseLeave={() => setHover(null)}
      onMouseMove={e => {
        if (!known.length) return
        const rect = e.currentTarget.getBoundingClientRect()
        setHover(nearest(e.clientX - rect.left).i)
      }}>
      <svg height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`折线图，单位 ${unit}`}>
        {[0, 0.5, 1].map(f => {
          const v = lo + (hi - lo) * f
          return (
            <g key={f}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={f ? '3 4' : undefined} />
              <text x={PAD.left - 6} y={y(v) + 3.5} textAnchor="end" className="axis-text num">{v.toFixed(hi - lo < 4 ? 1 : 0)}</text>
            </g>
          )
        })}
        {labels.map((l, i) => l && <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="axis-text num">{l}</text>)}
        {path && <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
          pathLength={1} className="line-draw" />}
        {known.map((p, k) => (
          <circle key={p.i} cx={x(p.i)} cy={y(p.v)} r={hover === p.i ? 5 : 3.5} fill={color} stroke="var(--surface)" strokeWidth={2}
            className="dot-pop" style={{ animationDelay: `${300 + (k / Math.max(1, known.length)) * 1100}ms` }} />
        ))}
        {hover !== null && points[hover].value !== null && (
          <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--line-strong)" pointerEvents="none" />
        )}
      </svg>
      {hover !== null && points[hover].value !== null && (
        <div className="chart-tip" style={{ left: x(hover), top: y(points[hover].value!) - 10 }}>
          {fmtDay(points[hover].day)} · <b className="num">{points[hover].value}</b> {unit}
        </div>
      )}
      {!known.length && <div className="empty" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>还没有数据</div>}
    </div>
  )
}

/** 迷你趋势线：KPI 卡片里用，无坐标轴，面积渐变 + 描线动画。 */
export function Sparkline({ values, color, width = 120, height = 40 }:
  { values: (number | null)[]; color: string; width?: number; height?: number }) {
  const pts = values.map((v, i) => ({ i, v })).filter(p => p.v !== null && p.v > 0) as { i: number; v: number }[]
  if (pts.length < 2) return <svg width={width} height={height} aria-hidden />
  const lo = Math.min(...pts.map(p => p.v)), hi = Math.max(...pts.map(p => p.v))
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (width - 4) + 2
  const y = (v: number) => height - 4 - ((v - lo) / (hi - lo || 1)) * (height - 10)
  const line = pts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
  const area = `${line} L${x(pts[pts.length - 1].i)},${height} L${x(pts[0].i)},${height} Z`
  const id = `spark-${color.replace(/[^a-z]/gi, '')}`
  const last = pts[pts.length - 1]
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".22" /><stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} style={{ animation: 'fade 1s .4s both' }} />
      <path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" pathLength={1} className="line-draw" />
      <circle cx={x(last.i)} cy={y(last.v)} r={3.5} fill={color} stroke="#fff" strokeWidth={2} className="dot-pop" style={{ animationDelay: '1.1s' }} />
    </svg>
  )
}

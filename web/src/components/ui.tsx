import { createContext, useCallback, useContext, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { CircleCheck, X } from 'lucide-react'
import type { Kind } from '../lib/api'
import { KIND_META } from '../lib/metrics'
import { useCountUp } from '../lib/motion'

// ---------------------------------------------------------- Toast
const ToastContext = createContext<(msg: string) => void>(() => undefined)
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<{ text: string; id: number } | null>(null)
  const timer = useRef<number>()
  const show = useCallback((text: string) => {
    setMsg({ text, id: Date.now() })
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMsg(null), 2600)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      {msg && <div className="toast" role="status" key={msg.id}><CircleCheck size={15} />{msg.text}</div>}
    </ToastContext.Provider>
  )
}

// ---------------------------------------------------------- 数字滚动
export function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const shown = useCountUp(value, 900, decimals)
  return <>{decimals ? shown.toFixed(decimals) : Math.round(shown)}</>
}

// ---------------------------------------------------------- 指标图标
export function MetricIcon({ kind, size = 'md' }: { kind: Kind; size?: 'sm' | 'md' }) {
  const meta = KIND_META[kind]
  const Icon = meta.icon
  return (
    <span className={`metric-icon ${size === 'sm' ? 'sm' : ''}`} style={{ '--c': meta.color } as CSSProperties}>
      <Icon size={size === 'sm' ? 14 : 17} strokeWidth={2} />
    </span>
  )
}

export function ProgressBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="bar" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${value}%`, '--c': color } as CSSProperties} />
    </div>
  )
}

// ---------------------------------------------------------- 环形进度（挂载时从 0 画到目标）
export function Ring({ value, size = 176, stroke = 15, color, children }:
  { value: number; size?: number; stroke?: number; color?: string; children?: ReactNode }) {
  const [drawn, setDrawn] = useState(0)
  useEffect(() => {
    const raf = requestAnimationFrame(() => setDrawn(value))
    return () => cancelAnimationFrame(raf)
  }, [value])
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const over = value > 100
  const shown = Math.min(100, drawn)
  const gid = `ring-${size}-${stroke}`
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ff6b35" /><stop offset="100%" stopColor="#ffb547" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={over ? 'var(--danger)' : color ?? `url(#${gid})`}
          strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - shown / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(.2,.7,.2,1)' }} />
      </svg>
      <div className="center">{children}</div>
    </div>
  )
}

// ---------------------------------------------------------- 弹窗
export function Modal({ title, onClose, children, footer }:
  { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭"><X size={18} /></button>
        </div>
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

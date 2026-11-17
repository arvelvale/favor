// 动效与跨组件刷新工具。所有动画都尊重系统“减少动态效果”设置。
import { useEffect, useRef, useState } from 'react'

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** 数字从上一次的值滚动到新值（easeOutCubic）。 */
export function useCountUp(target: number, duration = 900, decimals = 0) {
  const [value, setValue] = useState(prefersReducedMotion() ? target : 0)
  const from = useRef(prefersReducedMotion() ? target : 0)
  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(target)) { setValue(target); from.current = target; return }
    const start = performance.now()
    const begin = from.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(begin + (target - begin) * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); from.current = target }
  }, [target, duration])
  const factor = Math.pow(10, decimals)
  return Math.round(value * factor) / factor
}

/** 进入视口时给元素加 .in（只触发一次），配合 CSS .reveal 使用。 */
export function useReveal<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return
    const targets = root.matches('.reveal') ? [root] : Array.from(root.querySelectorAll<HTMLElement>('.reveal'))
    if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
      targets.forEach(el => el.classList.add('in'))
      return
    }
    const io = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target) }
      }
    }, { threshold, rootMargin: '0px 0px -40px 0px' })
    targets.forEach(el => io.observe(el))
    return () => io.disconnect()
  }, [threshold])
  return ref
}

/** 元素首次可见后返回 true，用于让图表在可见时才播放生长动画。 */
export function useInView<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    if (!('IntersectionObserver' in window)) { setSeen(true); return }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect() } }, { threshold: 0.2 })
    io.observe(el)
    return () => io.disconnect()
  }, [seen])
  return [ref, seen] as const
}

// ---------------------------------------------------------- 数据变更广播
// Agent 在侧栏记录了数据后，工作台上的面板需要立即刷新。
const EVENT = 'favor:data-changed'

export function emitDataChanged() {
  window.dispatchEvent(new Event(EVENT))
}

export function useDataChanged(callback: () => void) {
  const cb = useRef(callback)
  cb.current = callback
  useEffect(() => {
    const handler = () => cb.current()
    window.addEventListener(EVENT, handler)
    return () => window.removeEventListener(EVENT, handler)
  }, [])
}

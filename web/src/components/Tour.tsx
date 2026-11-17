import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, HeartPulse, Sparkles, X } from 'lucide-react'
import { updateOnboarding, useOnboarding, type TourStep } from '../lib/onboarding'
import { useAuth } from '../App'

/**
 * 聚焦式新手引导：每一步只高亮一个要操作的区域，其余变暗且点不到；
 * 靠用户完成真实操作推进（进度由服务端从真实数据推导），任何一步都能跳过。
 * 目标元素用 data-tour 标记；当前页面找不到目标时，退成一个「带我去」的小提示条。
 */

interface Target { sel: string; title: string; text: string; photoText?: string }
const STEPS: Record<TourStep, { n: number; targets: Target[]; elsewhere: string; route: string }> = {
  pantry: {
    n: 1, route: '/app', elsewhere: '先告诉 Favor 冰箱里有什么',
    targets: [{ sel: '[data-tour="pantry"]', title: '先告诉 Favor 冰箱里有什么',
      text: '勾几样常见的，或者直接说一句话，比如「有鸡蛋、番茄、半颗洋葱」。放够 3 样就行，数量和保质期都不用填。',
      // 配了识图时换成这句（见下方 textFor）
      photoText: '勾几样常见的、说一句话，或者点「拍一张」直接拍冰箱。放够 3 样就行，数量和保质期都不用填。' }],
  },
  recommend: {
    n: 2, route: '/app', elsewhere: '让 Favor 推荐几道菜',
    targets: [{ sel: '[data-tour="recommend"]', title: '让 Favor 想想今天吃什么',
      text: '点这里，Favor 会用冰箱里的食材推荐 3 道菜，现在就能做的排在前面。' }],
  },
  open: {
    n: 2, route: '/app', elsewhere: '打开一道推荐的菜',
    targets: [{ sel: '[data-tour="first-recipe"]', title: '看懂推荐卡',
      text: '「现在就能做」表示不用再买东西；用到快过期的会标出来，缺什么也会写清楚。点开第一道看看做法。' }],
  },
  cook: {
    n: 3, route: '/app', elsewhere: '打开一道菜，做好或收藏它',
    targets: [
      { sel: '[data-tour="cook-actions"]', title: '跟着步骤做',
        text: '点「开始做菜」一步一步来，做完点「做好了」，用掉的食材会自动从冰箱扣掉。今天不做的话，先收藏也行。' },
      { sel: '[data-tour="first-recipe"]', title: '打开一道菜',
        text: '点开一道菜，跟着步骤做，或者先收藏起来。' },
    ],
  },
}
const TOTAL = 4
const PAD = 8

function findTarget(targets: Target[]) {
  for (const t of targets) {
    const el = document.querySelector<HTMLElement>(t.sel)
    if (el && el.getClientRects().length) return { el, t }
  }
  return null
}

export default function Tour() {
  const ob = useOnboarding()
  const { visionEnabled } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [found, setFound] = useState<Target | null>(null)
  const [blocked, setBlocked] = useState(false)
  const scrolledFor = useRef<{ key: string; at: number; retried: boolean }>({ key: '', at: 0, retried: false })
  const bubbleRef = useRef<HTMLDivElement>(null)
  const [bubbleH, setBubbleH] = useState(170)

  const active = ob?.tour === 'active' && ob.current !== null
  const step = active ? STEPS[ob!.current!] : null

  // 跟踪目标位置：页面内容异步加载、滚动、窗口变化都会让目标移动
  useEffect(() => {
    if (ob?.tour !== 'active') { setRect(null); setFound(null); return }
    let raf = 0
    const measure = () => {
      raf = 0
      // 做菜模式、确认弹窗等全屏层打开时让开，不叠在上面。
      // 没有当前步骤（等完成提示）时也要持续检查：否则「做好了」弹窗关掉后这个标记会一直停在 true，完成提示永远不出来
      const modal = !!document.querySelector('[aria-modal="true"]')
      setBlocked(modal)
      if (!step) { setFound(null); setRect(null); return }
      const hit = modal ? null : findTarget(step.targets)
      setFound(prev => (prev?.sel === hit?.t.sel ? prev : hit?.t ?? null))
      setRect(prev => {
        const r = hit?.el.getBoundingClientRect() ?? null
        if (!r || !prev) return r
        return Math.abs(r.top - prev.top) + Math.abs(r.left - prev.left) + Math.abs(r.width - prev.width) + Math.abs(r.height - prev.height) < 1 ? prev : r
      })
      // 新的一步：目标不在视野里就滚过去。先平滑滚动；0.8 秒后还没到位（平滑滚动被打断、或页面在后台不跑动画），
      // 再直接跳过去一次。只对「顶部被挡」做判断，太高的目标（录入区）对齐顶部即可
      if (hit) {
        const key = `${ob?.current}:${hit.t.sel}`
        const r = hit.el.getBoundingClientRect()
        const tall = r.height > window.innerHeight * 0.6
        const outOfView = r.top < 60 || (!tall && r.bottom > window.innerHeight - 90)
        const block = tall ? 'start' : 'center'
        const s = scrolledFor.current
        if (s.key !== key) {
          scrolledFor.current = { key, at: Date.now(), retried: false }
          if (outOfView) hit.el.scrollIntoView({ block, behavior: 'smooth' })
        } else if (!s.retried && outOfView && Date.now() - s.at > 800) {
          scrolledFor.current = { ...s, retried: true }
          hit.el.scrollIntoView({ block })
        }
      }
    }
    const schedule = () => { if (!raf) raf = requestAnimationFrame(measure) }
    measure()
    // 轮询直接测量，不走 requestAnimationFrame：后台/隐藏的页面里 rAF 会暂停，引导就一直找不到目标
    const timer = window.setInterval(measure, 250)
    window.addEventListener('scroll', schedule, true)
    window.addEventListener('resize', schedule)
    return () => {
      window.clearInterval(timer); cancelAnimationFrame(raf)
      window.removeEventListener('scroll', schedule, true); window.removeEventListener('resize', schedule)
    }
  }, [step, ob?.current, ob?.tour, pathname])

  // 只量完整气泡的高度来决定位置；缩成一行时不量，否则会在「放得下/放不下」之间来回跳
  useLayoutEffect(() => {
    const el = bubbleRef.current
    if (el && !el.classList.contains('compact')) setBubbleH(el.offsetHeight)
  }, [found, rect?.width])

  if (!ob || ob.tour !== 'active') return null
  const skip = () => updateOnboarding({ tour: 'skipped' })

  // 4 步都完成：完成提示（不遮挡，不强推健康）
  if (ob.current === null) {
    if (blocked) return null
    return (
      <div className="tour-finish" role="status">
        <span className="tour-finish-ico"><Sparkles size={18} /></span>
        <div className="grow">
          <b>上手完成</b>
          <p>{ob.cooked
            ? '刚才用掉的食材已经从冰箱扣掉，这一餐也帮你记下了。以后就是三步：放食材 → 帮我想想 → 做好了。'
            : '收好了。想做的时候在「收藏」里打开它，做完点「做好了」，会自动扣掉用掉的食材、记下这一餐。'}</p>
          <div className="tour-finish-actions">
            <button className="btn btn-primary" onClick={() => updateOnboarding({ tour: 'done' })}><Check size={15} />知道了</button>
            {ob.cooked && <Link className="btn btn-ghost" to="/app/health" onClick={() => updateOnboarding({ tour: 'done' })}><HeartPulse size={15} />看看记下的这一餐</Link>}
          </div>
        </div>
      </div>
    )
  }

  if (!step || blocked) return null

  // 当前页面没有要操作的东西：一个不挡路的小提示条
  if (!found || !rect) {
    return (
      <div className="tour-pill" role="status">
        <span className="num">{step.n}/{TOTAL}</span>
        <b>{step.elsewhere}</b>
        {pathname !== step.route && <button className="btn btn-primary" onClick={() => navigate(step.route)}>带我去<ArrowRight size={14} /></button>}
        <button className="icon-btn" aria-label="跳过引导" title="跳过引导" onClick={skip}><X size={15} /></button>
      </div>
    )
  }

  const vw = window.innerWidth, vh = window.innerHeight
  const hole = { x1: Math.max(0, rect.left - PAD), y1: Math.max(0, rect.top - PAD), x2: Math.min(vw, rect.right + PAD), y2: Math.min(vh, rect.bottom + PAD) }
  const clip = `polygon(evenodd, 0 0, ${vw}px 0, ${vw}px ${vh}px, 0 ${vh}px, 0 0, ${hole.x1}px ${hole.y1}px, ${hole.x2}px ${hole.y1}px, ${hole.x2}px ${hole.y2}px, ${hole.x1}px ${hole.y2}px, ${hole.x1}px ${hole.y1}px)`
  const width = Math.min(340, vw - 32)
  const gap = 14
  const topClamp = Math.min(Math.max(16, hole.y1), vh - bubbleH - 16)
  let left = Math.min(Math.max(16, rect.left), vw - width - 16)
  let pos: CSSProperties
  let compact = false
  if (vh - hole.y2 >= bubbleH + gap + 16) pos = { top: hole.y2 + gap }
  else if (hole.y1 >= bubbleH + gap + 16) pos = { top: hole.y1 - gap - bubbleH }
  else if (vw - hole.x2 >= width + gap + 16) { left = hole.x2 + gap; pos = { top: topClamp } }
  else if (hole.x1 >= width + gap + 16) { left = hole.x1 - gap - width; pos = { top: topClamp } }
  else { pos = { bottom: 16 }; compact = true }  // 目标比屏幕还高（手机上的录入区）：气泡缩成一行放底部，少挡内容

  return (
    <>
      <div className="tour-dim" style={{ clipPath: clip }} aria-hidden="true" />
      <div className="tour-ring" aria-hidden="true"
        style={{ left: hole.x1, top: hole.y1, width: hole.x2 - hole.x1, height: hole.y2 - hole.y1 }} />
      <div ref={bubbleRef} className={`tour-bubble ${compact ? 'compact' : ''}`} role="dialog" aria-label={found.title} style={{ left, width, ...pos }}>
        <div className="tour-bubble-head">
          <span className="tour-step num">第 {step.n} 步 · 共 {TOTAL} 步</span>
          <button className="tour-skip" onClick={skip}>跳过引导</button>
        </div>
        <b>{found.title}</b>
        {!compact && <p>{visionEnabled && found.photoText ? found.photoText : found.text}</p>}
        <div className="tour-dots" aria-hidden="true">
          {Array.from({ length: TOTAL }, (_, i) => <i key={i} className={i + 1 < step.n ? 'done' : i + 1 === step.n ? 'now' : ''} />)}
        </div>
      </div>
    </>
  )
}

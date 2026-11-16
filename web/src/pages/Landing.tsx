import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, BellRing, Check, ChartNoAxesColumn, CircleCheck, Droplet, MessageCircleHeart, ShieldCheck,
  Sparkles, Sprout, Stethoscope, UtensilsCrossed,
} from 'lucide-react'
import { useAuth } from '../App'
import { AnimatedNumber, MetricIcon, Ring } from '../components/ui'
import Logo, { LogoMark } from '../components/Logo'
import { prefersReducedMotion, useInView, useReveal } from '../lib/motion'
import type { Kind } from '../lib/api'
import '../landing.css'

// ---------------------------------------------------------- 首屏演示脚本
interface Scene { user: string; cards: { kind: Kind; title: string }[]; reply: string }
const SCENES: Scene[] = [
  {
    user: '午饭吃了牛肉面加卤蛋，下午跑了 25 分钟',
    cards: [{ kind: 'meal', title: '午餐 · 牛肉面、卤蛋 · 625 kcal' }, { kind: 'exercise', title: '跑步 25 分钟 · 约 125 kcal' }],
    reply: '都记好了。今天还可以吃约 **830 kcal**，晚餐来份清蒸鱼配青菜正合适。',
  },
  {
    user: '昨晚一点多才睡，只睡了 6 个小时',
    cards: [{ kind: 'sleep', title: '睡眠 6 小时 · 质量 2/5' }],
    reply: '这周已经三次少于 7 小时了。要不要一起定个小目标：**23:30 前放下手机**？',
  },
  {
    user: '早上称了一下 62.4 公斤',
    cards: [{ kind: 'weight', title: '体重 62.4 kg' }],
    reply: '比上周轻了 **0.6 kg**，节奏很健康，保持每周 0.5 kg 左右就好。',
  },
]

type Phase = 'typing' | 'thinking' | 'cards' | 'reply' | 'hold'

function useDemo() {
  const reduced = prefersReducedMotion()
  const [scene, setScene] = useState(0)
  const [phase, setPhase] = useState<Phase>(reduced ? 'hold' : 'typing')
  const [typed, setTyped] = useState(reduced ? SCENES[0].user.length : 0)
  const [cards, setCards] = useState(reduced ? SCENES[0].cards.length : 0)
  const [replied, setReplied] = useState(reduced ? SCENES[0].reply.length : 0)
  const s = SCENES[scene]

  useEffect(() => {
    if (reduced) return
    let t: number
    if (phase === 'typing') {
      t = window.setTimeout(() => (typed < s.user.length ? setTyped(typed + 1) : setPhase('thinking')), typed < s.user.length ? 55 : 350)
    } else if (phase === 'thinking') {
      t = window.setTimeout(() => setPhase('cards'), 900)
    } else if (phase === 'cards') {
      t = window.setTimeout(() => (cards < s.cards.length ? setCards(cards + 1) : setPhase('reply')), 520)
    } else if (phase === 'reply') {
      t = window.setTimeout(() => (replied < s.reply.length ? setReplied(replied + 2) : setPhase('hold')), 28)
    } else {
      t = window.setTimeout(() => {
        setScene((scene + 1) % SCENES.length); setTyped(0); setCards(0); setReplied(0); setPhase('typing')
      }, 3200)
    }
    return () => window.clearTimeout(t)
  }, [phase, typed, cards, replied, scene, s, reduced])

  return { s, phase, typed, cards, replied }
}

function renderBold(text: string) {
  // 演示里只有 **加粗** 一种标记；流式截断时未闭合的部分按普通文本显示
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part.replace(/\*/g, '')}</span>)
}

function Demo() {
  const { s, phase, typed, cards, replied } = useDemo()
  const showUser = phase !== 'typing'
  return (
    <div className="demo">
      <div className="demo-window">
        <div className="demo-bar"><i /><i /><i /><span><span className="live-dot" />Favor 在线</span></div>
        <div className="demo-body compact" key={s.user}>
          {showUser && <div className="msg user"><div className="bubble-user">{s.user}</div></div>}
          {showUser && (
            <div className="msg">
              <LogoMark size={30} className="bot-mark" />
              <div className="bot-body">
                {phase === 'thinking' && <span className="typing"><i /><i /><i /></span>}
                {cards > 0 && (
                  <div className="tool-cards">
                    {s.cards.slice(0, cards).map(c => (
                      <div className="tool-card" key={c.title}>
                        <MetricIcon kind={c.kind} size="sm" />
                        <div className="t"><b>{c.title}</b><span>已记录</span></div>
                        <CircleCheck size={16} className="ok" />
                      </div>
                    ))}
                  </div>
                )}
                {replied > 0 && <div className="md"><p>{renderBold(s.reply.slice(0, replied))}{phase === 'reply' && <span className="caret" />}</p></div>}
              </div>
            </div>
          )}
        </div>
        <div className="demo-input">
          {phase === 'typing' ? <span style={{ color: 'var(--ink)' }}>{s.user.slice(0, typed)}<span className="caret" /></span> : '和 Favor 说说今天…'}
          <span className="send-btn"><ArrowRight size={16} /></span>
        </div>
      </div>

      <div className="float-card f1">
        <Ring value={62} size={58} stroke={7}><b style={{ fontSize: 13 }}>62%</b></Ring>
        <div><small>今日热量</small><b className="num"><AnimatedNumber value={830} /></b> <small style={{ display: 'inline' }}>kcal 剩余</small></div>
      </div>
      <div className="float-card f2">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <MetricIcon kind="water" size="sm" /><small style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>饮水</small>
          <b className="num" style={{ marginLeft: 'auto', fontSize: 14 }}>1500<small style={{ display: 'inline' }}> / 2150</small></b>
        </div>
        <div className="bar"><i style={{ width: '70%', '--c': 'var(--water)' } as CSSProperties} /></div>
      </div>
      <div className="float-card f3">
        <span className="habit-check on"><Check size={14} strokeWidth={3} /></span>
        <span>23:30 前放下手机</span><span className="tag brand">连续 4 天</span>
      </div>
    </div>
  )
}

/** 滚动到可见时才开始滚动计数。 */
function CountOnView({ value }: { value: number }) {
  const [ref, seen] = useInView<HTMLSpanElement>()
  return <span ref={ref}><AnimatedNumber value={seen ? value : 0} /></span>
}

// ---------------------------------------------------------- 页面
const PHRASES: [string, Kind][] = [
  ['早饭两个包子一杯豆浆', 'meal'], ['今天称了 62.4 kg', 'weight'], ['昨晚只睡了 5 小时', 'sleep'], ['下午游泳 40 分钟', 'exercise'],
  ['刚喝了一大杯水', 'water'], ['今天有点焦虑，胃也胀', 'mood'], ['帮我配一份 500 kcal 的晚餐', 'meal'], ['这周我吃得怎么样？', 'meal'],
  ['奶茶去冰三分糖', 'meal'], ['爬楼梯 15 分钟', 'exercise'], ['午睡了 20 分钟', 'sleep'], ['想养成早睡的习惯', 'sleep'],
]

export default function LandingPage() {
  const { user } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const pageRef = useReveal<HTMLDivElement>()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const cta = user
    ? <Link className="btn btn-primary btn-lg" to="/app">进入工作台<ArrowRight size={17} /></Link>
    : <Link className="btn btn-primary btn-lg" to="/register">免费开始<ArrowRight size={17} /></Link>
  const half = PHRASES.length / 2

  return (
    <div className="lp" ref={pageRef}>
      <nav className={`lp-nav ${scrolled ? 'scrolled' : ''}`}>
        <div className="lp-wrap">
          <Link to="/" className="lp-logo"><Logo size={38} animated /></Link>
          <div className="lp-links">
            <a href="#features">功能</a><a href="#how">怎么用</a><a href="#safety">安全边界</a>
          </div>
          <div className="actions">
            {user ? <Link className="btn btn-primary" to="/app">进入工作台</Link> : <>
              <Link className="btn btn-ghost" to="/login">登录</Link>
              <Link className="btn btn-primary" to="/register">免费开始</Link>
            </>}
          </div>
        </div>
      </nav>

      <header className="lp-hero">
        <div className="lp-bg"><div className="blob b1" /><div className="blob b2" /><div className="blob b3" /><div className="grid" /></div>
        <div className="lp-wrap">
          <div className="hero-in">
            <span className="pill"><span className="tag">新</span>AI 健康管家 · 对话即记录</span>
            <h1>说一句话，<br />健康就<span className="grad-text">记好了</span>。</h1>
            <p className="lead">不用翻食物库、不用填表格。像跟朋友聊天一样告诉 Favor 今天吃了什么、睡得怎样，它会估算营养、记进工作台，再给你一条刚刚好的建议。</p>
            <div className="lp-cta">
              {cta}
              <a className="btn btn-lg" href="#how">看看怎么用</a>
            </div>
            <div className="lp-facts">
              <div><b className="num">14</b>个 Agent 工具</div>
              <div><b className="num">6</b>类健康数据</div>
              <div><b className="num">0</b>张要填的表</div>
            </div>
          </div>
          <Demo />
        </div>
      </header>

      <div className="marquee" aria-hidden>
        {[PHRASES.slice(0, half), PHRASES.slice(half)].map((row, r) => (
          <div className={`marquee-row ${r ? 'rev' : ''}`} key={r}>
            {[...row, ...row].map(([text, kind], i) => (
              <span className="marquee-item" key={i} style={{ '--c': `var(--${kind})` } as CSSProperties}><i />{text}</span>
            ))}
          </div>
        ))}
      </div>

      <section className="lp-section" id="features">
        <div className="lp-wrap">
          <div className="lp-head reveal">
            <span className="lp-eyebrow">FEATURES</span>
            <h2>记录、分析、建议，<br />一个工作台全搞定</h2>
            <p>Favor 把聊天和数据面板放在一起：你说，它记；你看，它提醒。</p>
          </div>
          <div className="bento">
            <div className="card wide reveal">
              <MetricIcon kind="meal" />
              <h3>对话即记录</h3>
              <p>一句话里有吃饭、运动、喝水，Favor 会拆开分别记录，营养按常见份量自动估算。</p>
              <div className="visual mini-chat">
                <div className="bubble-user">早饭两个肉包一杯豆浆，还走了 6000 步</div>
                <div className="tool-card"><MetricIcon kind="meal" size="sm" /><div className="t"><b>早餐 · 肉包、豆浆 · 510 kcal</b><span>蛋白质 23g · 碳水 68g · 脂肪 16g</span></div><CircleCheck size={16} className="ok" /></div>
                <div className="tool-card"><MetricIcon kind="exercise" size="sm" /><div className="t"><b>快走 50 分钟 · 约 190 kcal</b><span>已记录</span></div><CircleCheck size={16} className="ok" /></div>
              </div>
            </div>
            <div className="card reveal d1">
              <span className="metric-icon" style={{ '--c': 'var(--brand)' } as CSSProperties}><UtensilsCrossed size={17} /></span>
              <h3>今天还能吃多少</h3>
              <p>按身高体重、活动量和目标算出每日预算，运动消耗自动加回。</p>
              <div className="visual" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <Ring value={68} size={104} stroke={11}><b style={{ fontSize: 20 }}>520</b><span>kcal 剩余</span></Ring>
                <div style={{ flex: 1, display: 'grid', gap: 10 }}>
                  {[['蛋白质', 72, 'var(--meal)'], ['碳水', 55, 'var(--weight)'], ['脂肪', 40, 'var(--mood)']].map(([l, v, c]) => (
                    <div key={l as string}><div className="macro-row"><span>{l}</span><span>{v}%</span></div>
                      <div className="bar"><i style={{ width: `${v}%`, '--c': c } as CSSProperties} /></div></div>
                  ))}
                </div>
              </div>
            </div>
            <div className="card reveal">
              <span className="metric-icon" style={{ '--c': 'var(--water)' } as CSSProperties}><ChartNoAxesColumn size={17} /></span>
              <h3>趋势一目了然</h3>
              <p>体重、睡眠、热量、饮水，7 到 90 天的变化一眼看清。</p>
              <div className="visual mini-bars">
                {[62, 78, 54, 88, 70, 95, 66].map((h, i) => (
                  <i key={i} style={{ height: `${h}%`, '--c': 'var(--sleep)', transitionDelay: `${i * 70}ms` } as CSSProperties} />
                ))}
              </div>
            </div>
            <div className="card reveal d1">
              <span className="metric-icon" style={{ '--c': 'var(--exercise)' } as CSSProperties}><Sprout size={17} /></span>
              <h3>小习惯，慢慢养</h3>
              <p>想早睡、想多喝水？Favor 帮你拆成每天能打卡的一小步。</p>
              <div className="visual" style={{ display: 'grid', gap: 2 }}>
                {[['晚上 11:30 前放下手机', true], ['每天两份蔬菜', true], ['饭后散步 15 分钟', false]].map(([n, d]) => (
                  <div className="habit" key={n as string}>
                    <span className={`habit-check ${d ? 'on' : ''}`}>{d && <Check size={14} strokeWidth={3} />}</span>
                    <span className={`name ${d ? 'done' : ''}`}>{n}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card navy reveal d2" id="safety">
              <span className="metric-icon" style={{ '--c': '#ffb08a', background: 'rgba(255,255,255,.1)' } as CSSProperties}><ShieldCheck size={17} /></span>
              <h3>懂分寸的建议</h3>
              <p>Favor 是生活方式助手，不是医生。</p>
              <div className="visual shield-list">
                <div><Stethoscope size={15} />不做诊断，不给用药建议</div>
                <div><BellRing size={15} />胸痛、呼吸困难等危险信号，第一时间提醒就医</div>
                <div><ShieldCheck size={15} />热量目标设有安全下限，不鼓励极端节食</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section alt" id="how">
        <div className="lp-wrap">
          <div className="lp-head reveal">
            <span className="lp-eyebrow">HOW IT WORKS</span>
            <h2>三步，把照顾自己变简单</h2>
          </div>
          <div className="steps reveal">
            <div className="step"><div className="n">1</div><h3>随口说一句</h3><p>在工作台右侧的 Favor 面板里，用最自然的话描述你的一天。</p><span className="example">“晚饭吃了半碗米饭和番茄炒蛋”</span></div>
            <div className="step"><div className="n">2</div><h3>Favor 记录并估算</h3><p>它会调用工具记下数据、估算热量和营养，并告诉你还差多少。</p><span className="example">晚餐 · 420 kcal · 已记录</span></div>
            <div className="step"><div className="n">3</div><h3>看趋势，拿建议</h3><p>工作台汇总每天的进度和长期趋势，Favor 给出下一步的小建议。</p><span className="example">这周睡眠平均 6.4 小时</span></div>
          </div>
        </div>
      </section>

      <section className="band">
        <div className="orb a" /><div className="orb b" />
        <div className="lp-wrap band-grid reveal">
          <div><b className="num"><CountOnView value={14} /><em>个</em></b><span>Agent 可调用的健康工具</span></div>
          <div><b className="num"><CountOnView value={6} /><em>类</em></b><span>饮食、饮水、运动、睡眠、体重、心情</span></div>
          <div><b className="num"><CountOnView value={90} /><em>天</em></b><span>趋势回看范围</span></div>
          <div><b className="num"><CountOnView value={1} /><em>句话</em></b><span>就能完成一次记录</span></div>
        </div>
      </section>

      <section className="final">
        <div className="lp-wrap">
          <div className="final-box reveal">
            <Sparkles size={28} />
            <h2>从今天的第一杯水开始</h2>
            <p>注册只需要一个用户名。你的数据只属于你，可以随时查看和删除。</p>
            <Link className="btn btn-lg" to={user ? '/app' : '/register'}>{user ? '进入工作台' : '免费创建账号'}<ArrowRight size={17} /></Link>
          </div>
        </div>
      </section>

      <footer className="lp-foot">
        <div className="lp-wrap">
          <span className="lp-logo"><Logo size={30} subtitle="AI 健康管家" /></span>
          <span><MessageCircleHeart size={13} style={{ verticalAlign: -2 }} /> Favor 提供生活方式建议，不能替代专业医疗诊断。<Droplet size={13} style={{ verticalAlign: -2, marginLeft: 8 }} /> © 2026 Favor</span>
        </div>
      </footer>
    </div>
  )
}

import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, Camera, Carrot, Check, ChefHat, CircleCheck, Clock, Drumstick, Egg, Flame, HeartPulse, Leaf, LeafyGreen,
  ListChecks, MessageSquareText, Milk, Refrigerator, ScanLine, ShieldCheck, ShoppingBasket, SlidersHorizontal, Sparkles,
  UtensilsCrossed, type LucideIcon,
} from 'lucide-react'
import { useAuth } from '../App'
import { AnimatedNumber, Ring } from '../components/ui'
import Logo, { LogoMark } from '../components/Logo'
import { prefersReducedMotion, useInView, useReveal } from '../lib/motion'
import '../landing.css'

// ---------------------------------------------------------- 首屏演示：拍冰箱 → 认出食材 → 3 道推荐 → 做好了 → 自动记一餐
const STAGES = [
  { key: 'snap', label: '拍冰箱', icon: Camera },
  { key: 'found', label: '认出食材', icon: ScanLine },
  { key: 'recipes', label: '3 道推荐', icon: ChefHat },
  { key: 'cooked', label: '做好了', icon: Check },
  { key: 'logged', label: '记一餐', icon: HeartPulse },
] as const
const STAGE_MS = [2600, 3000, 3200, 2800, 3000]

const SHELF: { icon: LucideIcon; c: string; x: number; y: number }[] = [
  { icon: Egg, c: '#f0a43a', x: 16, y: 16 }, { icon: Milk, c: '#2f7cf6', x: 62, y: 12 },
  { icon: LeafyGreen, c: '#1e9e5e', x: 22, y: 48 }, { icon: Carrot, c: '#f08a24', x: 58, y: 50 },
  { icon: Drumstick, c: '#e5484d', x: 38, y: 78 },
]
const FOUND = [
  { name: '鸡蛋', meta: '6 个', icon: Egg, c: '#f0a43a' },
  { name: '番茄', meta: '3 个', icon: Carrot, c: '#e5484d' },
  { name: '菠菜', meta: '还剩 1 天', icon: LeafyGreen, c: '#1e9e5e', warn: true },
  { name: '牛奶', meta: '1 盒', icon: Milk, c: '#2f7cf6' },
  { name: '鸡腿', meta: '2 只', icon: Drumstick, c: '#d9480f' },
]
const RECIPES = [
  { title: '菠菜蛋花汤', tag: '现在就能做', note: '顺手用掉菠菜', min: 10, ok: true },
  { title: '番茄炒蛋', tag: '现在就能做', note: '12 分钟出锅', min: 12, ok: true },
  { title: '照烧鸡腿', tag: '还缺 1 样', note: '缺：照烧汁', min: 25, ok: false },
]

function useStage() {
  const reduced = prefersReducedMotion()
  const [stage, setStage] = useState(reduced ? 2 : 0)
  useEffect(() => {
    if (reduced) return
    const t = window.setTimeout(() => setStage((stage + 1) % STAGES.length), STAGE_MS[stage])
    return () => window.clearTimeout(t)
  }, [stage, reduced])
  return [stage, setStage] as const
}

function Demo() {
  const [stage, setStage] = useStage()
  const key = STAGES[stage].key
  return (
    <div className="demo">
      <div className="demo-window">
        <div className="demo-bar"><i /><i /><i /><span><span className="live-dot" />今天吃什么</span></div>
        <ol className="demo-steps" aria-label="Favor 的流程">
          {STAGES.map((s, i) => (
            <li key={s.key} className={i < stage ? 'done' : i === stage ? 'now' : ''}>
              <button type="button" onClick={() => setStage(i)} aria-label={s.label}><s.icon size={13} /><span>{s.label}</span></button>
            </li>
          ))}
        </ol>
        <div className="demo-stage" key={key}>
          {key === 'snap' && (
            <div className="fridge">
              <div className="fridge-door">
                {SHELF.map(({ icon: Icon, c, x, y }, i) => (
                  <span key={i} className="fridge-item" style={{ left: `${x}%`, top: `${y}%`, '--c': c, '--i': i } as CSSProperties}><Icon size={22} /></span>
                ))}
                <i className="shelf s1" /><i className="shelf s2" />
                <span className="scan" />
              </div>
              <span className="shutter"><Camera size={18} /></span>
            </div>
          )}
          {key === 'found' && (
            <div className="found">
              <p className="stage-title"><ScanLine size={15} />认出 5 样，确认一下就放进冰箱</p>
              {FOUND.map((f, i) => (
                <div className="found-row" key={f.name} style={{ '--i': i, '--c': f.c } as CSSProperties}>
                  <span className="ck"><Check size={12} strokeWidth={3} /></span>
                  <span className="dot"><f.icon size={15} /></span>
                  <b>{f.name}</b><span className={`meta ${f.warn ? 'warn' : ''}`}>{f.meta}</span>
                </div>
              ))}
              <span className="fake-btn" style={{ '--i': 6 } as CSSProperties}><Check size={14} />放进冰箱 5 样</span>
            </div>
          )}
          {key === 'recipes' && (
            <div className="recs">
              <p className="stage-title"><Sparkles size={15} />现在就能做的排前面</p>
              {RECIPES.map((r, i) => (
                <div className="rec" key={r.title} style={{ '--i': i } as CSSProperties}>
                  <span className={`rtag ${r.ok ? 'ok' : 'miss'}`}>{r.ok ? <Check size={11} strokeWidth={3} /> : <ShoppingBasket size={11} />}{r.tag}</span>
                  <b>{r.title}</b>
                  <span className="rmeta"><Clock size={12} />{r.min} 分钟 · {r.note}</span>
                </div>
              ))}
            </div>
          )}
          {key === 'cooked' && (
            <div className="cooked">
              <span className="big-check"><Check size={30} strokeWidth={3} /></span>
              <b>番茄炒蛋，做好了</b>
              <div className="used">
                <span style={{ '--i': 0 } as CSSProperties}>番茄 · 用完了</span>
                <span style={{ '--i': 1 } as CSSProperties}>鸡蛋 · 还剩 3 个</span>
              </div>
              <small>冰箱已经自动更新</small>
            </div>
          )}
          {key === 'logged' && (
            <div className="logged">
              <div className="meal-card">
                <span className="dot"><UtensilsCrossed size={16} /></span>
                <div><b>晚餐 · 番茄炒蛋</b><span>做菜后自动记录 · 约 380 kcal</span></div>
                <CircleCheck size={18} className="ok" />
              </div>
              <div className="kcal">
                <Ring value={58} size={86} stroke={9}><b style={{ fontSize: 16 }}>820</b><span>kcal</span></Ring>
                <p>今天还能吃约 820 kcal。<br /><span>不用另外记，做菜顺手就记好了。</span></p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="float-card f1">
        <span className="fc-ico" style={{ '--c': '#1e9e5e' } as CSSProperties}><Leaf size={18} /></span>
        <div><small>快过期</small><b>菠菜 · 还剩 1 天</b></div>
      </div>
      <div className="float-card f2">
        <small>按你的情况推荐</small>
        <div className="fc-chips"><span>1 人份</span><span>15 分钟内</span><span>只有小电锅</span><span>不吃香菜</span></div>
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
const PHRASES: [string, string][] = [
  ['冰箱里有半颗洋葱和三个鸡蛋', '#f08a24'], ['鸡胸肉明天就过期了', '#e5484d'], ['15 分钟能做什么', '#2f7cf6'],
  ['两个人吃，不要辣', '#8b5cf6'], ['只有一个小电锅', '#1e9e5e'], ['家里有老人，做软一点', '#d9480f'],
  ['番茄快坏了怎么用掉', '#e5484d'], ['不吃香菜', '#1e9e5e'], ['想吃点清淡的', '#2f7cf6'],
  ['冻了一斤排骨', '#8b5cf6'], ['剩米饭能做什么', '#f08a24'], ['帮我凑一顿两菜一汤', '#d9480f'],
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
            <a href="#features">功能</a><a href="#how">怎么用</a><a href="#trust">放心用</a>
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
            <span className="pill"><span className="tag">新</span>AI 厨房搭子 · 拍一张冰箱就能开始</span>
            <h1>冰箱里有什么，<br />今晚就<span className="grad-text">做什么</span>。</h1>
            <p className="lead">拍一张冰箱、勾几样，或者随口说一句。Favor 记住你有什么、哪些快过期了，推荐现在就能做的菜；做完点一下，冰箱和这一餐都自动记好。</p>
            <div className="lp-cta">
              {cta}
              <a className="btn btn-lg" href="#how">看看怎么用</a>
            </div>
            <div className="lp-facts">
              <div><b className="num">3</b>种录入方式</div>
              <div><b className="num">3</b>道菜每次推荐</div>
              <div><b className="num">0</b>个保质期要你记</div>
            </div>
          </div>
          <Demo />
        </div>
      </header>

      <div className="marquee" aria-hidden>
        {[PHRASES.slice(0, half), PHRASES.slice(half)].map((row, r) => (
          <div className={`marquee-row ${r ? 'rev' : ''}`} key={r}>
            {[...row, ...row].map(([text, c], i) => (
              <span className="marquee-item" key={i} style={{ '--c': c } as CSSProperties}><i />{text}</span>
            ))}
          </div>
        ))}
      </div>

      <section className="lp-section" id="features">
        <div className="lp-wrap">
          <div className="lp-head reveal">
            <span className="lp-eyebrow">FEATURES</span>
            <h2>剩下的食材，<br />不再放到坏</h2>
            <p>通用聊天 AI 记不住你冰箱里有什么。Favor 记得，还会先帮你用掉快过期的。</p>
          </div>
          <div className="bento">
            <div className="card wide reveal">
              <span className="metric-icon" style={{ '--c': '#2f7cf6' } as CSSProperties}><Camera size={17} /></span>
              <h3>拍一张，冰箱就进来了</h3>
              <p>打开冰箱拍一张，认出来的食材先给你确认；拿不准的默认不勾，不会把认错的东西放进去。也可以勾选常见食材，或者说一句「有鸡蛋、番茄、半颗洋葱」。</p>
              <div className="visual lp-found">
                {[['鸡蛋', '6 个', true], ['番茄', '3 个', true], ['菠菜', '1 把', true], ['可能是豆腐', '不太确定', false]].map(([n, m, on]) => (
                  <div className={`lp-found-row ${on ? 'on' : ''}`} key={n as string}>
                    <span className="ck">{on && <Check size={12} strokeWidth={3} />}</span><b>{n}</b><span>{m}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card reveal d1">
              <span className="metric-icon" style={{ '--c': '#1e9e5e' } as CSSProperties}><Leaf size={17} /></span>
              <h3>快过期的先用掉</h3>
              <p>保质期不用记，按食材和存放位置自动估算；快过期的会排在推荐前面。</p>
              <div className="visual lp-expiry">
                {[['菠菜', '约还剩 1 天', 'urgent'], ['番茄', '约还剩 4 天', 'soon'], ['鸡蛋', '约还剩 30 天', 'ok']].map(([n, t, tone]) => (
                  <div key={n}><b>{n}</b><span className={`exp-pill ${tone}`}>{t}</span></div>
                ))}
              </div>
            </div>
            <div className="card reveal">
              <span className="metric-icon" style={{ '--c': '#ff6b35' } as CSSProperties}><ChefHat size={17} /></span>
              <h3>推荐看得懂</h3>
              <p>「现在就能做」排前面；缺什么、用掉了哪些快过期的，卡片上写清楚。</p>
              <div className="visual lp-mini-recs">
                <span className="rtag ok"><Check size={11} strokeWidth={3} />现在就能做</span>
                <span className="rtag save"><Leaf size={11} />用掉快过期的</span>
                <span className="rtag miss"><ShoppingBasket size={11} />还缺 1 样</span>
              </div>
            </div>
            <div className="card reveal d1">
              <span className="metric-icon" style={{ '--c': '#8b5cf6' } as CSSProperties}><SlidersHorizontal size={17} /></span>
              <h3>照你的情况来</h3>
              <p>一分钟问卷：几个人吃、会不会做、有哪些厨具。没有烤箱就不推烤菜，过敏的由程序检查、一律排除。</p>
              <div className="visual fc-chips big"><span>两菜一汤</span><span>新手模式</span><span>只有小电锅</span><span>花生过敏</span></div>
            </div>
            <div className="card navy reveal d2" id="trust">
              <span className="metric-icon" style={{ '--c': '#ffb08a', background: 'rgba(255,255,255,.1)' } as CSSProperties}><ShieldCheck size={17} /></span>
              <h3>做完点一下，就闭环了</h3>
              <p>不用另外记账，健康数据是顺手留下的。</p>
              <div className="visual shield-list">
                <div><Refrigerator size={15} />用掉的食材自动从冰箱扣掉</div>
                <div><Flame size={15} />这一餐按份数记下，热量为估算</div>
                <div><Camera size={15} />照片只用来识别，不会保存</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section alt" id="how">
        <div className="lp-wrap">
          <div className="lp-head reveal">
            <span className="lp-eyebrow">HOW IT WORKS</span>
            <h2>三步，从冰箱到饭桌</h2>
          </div>
          <div className="steps reveal">
            <div className="step"><div className="n">1</div><h3>放进冰箱</h3><p>拍一张、勾几样，或者说一句话。数量和保质期都可以不填。</p><span className="example"><Camera size={13} /> <ListChecks size={13} /> <MessageSquareText size={13} /> 三种方式随便选</span></div>
            <div className="step"><div className="n">2</div><h3>帮我想想</h3><p>Favor 用现有食材推荐 3 道菜，现在就能做的排前面，顺手用掉快过期的。</p><span className="example">菠菜蛋花汤 · 10 分钟 · 不用买东西</span></div>
            <div className="step"><div className="n">3</div><h3>做好了</h3><p>跟着步骤做，做完点一下：冰箱自动更新，这一餐也记好了。</p><span className="example">番茄 用完了 · 鸡蛋 还剩 3 个</span></div>
          </div>
        </div>
      </section>

      <section className="band">
        <div className="orb a" /><div className="orb b" />
        <div className="lp-wrap band-grid reveal">
          <div><b className="num"><CountOnView value={3} /><em>种</em></b><span>录入方式：拍照、勾选、说一句</span></div>
          <div><b className="num"><CountOnView value={2} /><em>天</em></b><span>内要过期的，优先用掉</span></div>
          <div><b className="num"><CountOnView value={8} /><em>题</em></b><span>问卷最多这么多，每题都会改变推荐</span></div>
          <div><b className="num"><CountOnView value={1} /><em>步</em></b><span>做好了：扣库存、记一餐一起完成</span></div>
        </div>
      </section>

      <section className="final">
        <div className="lp-wrap">
          <div className="final-box reveal">
            <LogoMark size={44} animated />
            <h2>今晚，先打开冰箱看看</h2>
            <p>注册只需要一个用户名。你的数据只属于你，可以随时查看和删除。</p>
            <Link className="btn btn-lg" to={user ? '/app' : '/register'}>{user ? '进入工作台' : '免费创建账号'}<ArrowRight size={17} /></Link>
          </div>
        </div>
      </section>

      <footer className="lp-foot">
        <div className="lp-wrap">
          <span className="lp-logo"><Logo size={30} subtitle="AI 厨房搭子" /></span>
          <span>菜谱由 AI 生成，热量与营养为估算，不能替代专业医疗或营养建议。 © 2026 Favor</span>
        </div>
      </footer>
    </div>
  )
}

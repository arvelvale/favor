import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bookmark, ChefHat, ExternalLink, HeartPulse, LogOut, MessageCircleHeart, MessageSquarePlus,
  PanelLeftClose, PanelLeftOpen, PanelRightClose, Plus, Refrigerator, UserRound, X,
} from 'lucide-react'
import { useAuth } from '../App'
import { emitDataChanged } from '../lib/motion'
import { usePrefs } from '../lib/prefs'
import ChatView, { type AskRequest } from './ChatView'
import Logo, { LogoMark } from './Logo'
import RecordModal from './RecordModal'
import Tour from './Tour'

// 主导航围绕「冰箱 → 做菜」。健康默认是次要入口（在「我的」旁边）；
// 问卷里选了「想吃得健康」的用户，健康进主导航（手机底栏里替换「对话」，对话仍可从右下角按钮进入）
const NAV = [
  { to: '/app', label: '今天吃什么', short: '今天', icon: ChefHat, end: true },
  { to: '/app/fridge', label: '冰箱', short: '冰箱', icon: Refrigerator },
  { to: '/app/recipes', label: '收藏', short: '收藏', icon: Bookmark },
  { to: '/app/chat', label: '对话', short: '对话', icon: MessageCircleHeart },
]
const HEALTH_ROUTES = ['/app/health', '/app/trends', '/app/records', '/app/profile']
const HEALTH_TABS: [string, string][] = [['/app/health', '总览'], ['/app/trends', '趋势'], ['/app/records', '记录'], ['/app/profile', '档案']]

const TITLES: Record<string, [string, string]> = {
  '/app': ['今天吃什么', ''],
  '/app/fridge': ['冰箱', '有什么、放在哪、还能放几天'],
  '/app/recipes': ['收藏', '喜欢的菜和做过的菜'],
  '/app/recipe': ['菜谱', '按步骤来，做完点「做好了」'],
  '/app/chat': ['对话', '冰箱、做菜、饮食，都可以问 Favor'],
  '/app/health': ['健康', '做完菜会自动记一餐，这里看看整体情况'],
  '/app/trends': ['健康 · 趋势', '看看最近的变化'],
  '/app/records': ['健康 · 记录', '你和 Favor 记下的每一条'],
  '/app/profile': ['健康 · 档案', '过敏和饮食偏好也会用在菜谱推荐里'],
  '/app/me': ['我的', '口味、厨具和身体档案'],
}

// 本机偏好（侧栏折叠、停靠栏开关、停靠栏当前对话）：读写失败时退回默认值
const store = {
  get(key: string) { try { return localStorage.getItem(key) } catch { return null } },
  set(key: string, value: string | null) {
    try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value) } catch { /* 忽略 */ }
  },
}

const ASK_EVENT = 'favor:ask'
/** 任意页面调用：打开右侧 Favor 面板并发送一句话。 */
export function askFavor(text: string) {
  window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: text }))
}

function greeting() {
  const h = new Date().getHours()
  return h < 5 ? '夜深了' : h < 11 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
}

export default function Workbench() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const inHealth = HEALTH_ROUTES.some(r => pathname === r || pathname.startsWith(r + '/'))
  const wide = () => window.innerWidth > 1280
  const [collapsed, setCollapsed] = useState(store.get('favor.side') === 'collapsed')
  const [dockOpen, setDockOpen] = useState(() => wide() && store.get('favor.dock') !== 'closed')
  const [dockConv, setDockConv] = useState<number | null>(() => Number(store.get('favor.dock.conv')) || null)
  const [ask, setAsk] = useState<AskRequest | null>(null)
  const [recording, setRecording] = useState(false)
  const onChatPage = pathname.startsWith('/app/chat')
  const showDock = dockOpen && !onChatPage
  const name = user?.nickname || user?.username || ''
  const healthMain = !!usePrefs()?.health_in_nav
  const healthLink = (
    <NavLink to="/app/health" title="健康" className={inHealth ? 'active' : ''}>
      <HeartPulse size={healthMain ? 19 : 18} strokeWidth={1.9} /><span>健康</span>
    </NavLink>
  )

  const toggleDock = (open: boolean) => {
    setDockOpen(open)
    if (wide()) store.set('favor.dock', open ? 'open' : 'closed')
  }

  useEffect(() => {
    const onAsk = (e: Event) => {
      setDockOpen(true)
      setAsk({ text: (e as CustomEvent<string>).detail, nonce: Date.now() })
    }
    window.addEventListener(ASK_EVENT, onAsk)
    return () => window.removeEventListener(ASK_EVENT, onAsk)
  }, [])

  // 窄屏上切换页面时收起抽屉式停靠栏
  useEffect(() => { if (!wide()) setDockOpen(false) }, [pathname])

  const onDockCreated = useCallback((id: number) => { setDockConv(id); store.set('favor.dock.conv', String(id)) }, [])
  const newDockChat = useCallback(() => { setDockConv(null); store.set('favor.dock.conv', null) }, [])

  const key = Object.keys(TITLES).filter(k => pathname === k || pathname.startsWith(k + '/')).sort((a, b) => b.length - a.length)[0] ?? '/app'
  const [title, subtitle] = TITLES[key]
  const today = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })

  return (
    <div className={`wb ${collapsed ? 'collapsed' : ''}`}>
      <aside className="wb-side">
        <Link to="/" className="wb-brand" title="返回首页">
          <Logo size={38} tone="light" subtitle="AI 厨房搭子" animated />
        </Link>
        <div className="wb-label">厨房</div>
        <nav className="wb-nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} title={label}>
              <Icon size={19} strokeWidth={1.9} /><span>{label}</span>
              {to === '/app/chat' && <span className="badge">AI</span>}
            </NavLink>
          ))}
          {healthMain && healthLink}
        </nav>
        <div className="wb-label">更多</div>
        <nav className="wb-nav secondary">
          <NavLink to="/app/me" title="我的"><UserRound size={18} strokeWidth={1.9} /><span>我的</span></NavLink>
          {!healthMain && healthLink}
        </nav>
        <div className="wb-side-foot">
          <div className="wb-user">
            <div className="avatar">{name.slice(0, 1).toUpperCase()}</div>
            <div className="who"><b>{name}</b><span>@{user?.username}</span></div>
            <button className="icon-btn" title="退出登录" aria-label="退出登录" onClick={logout}><LogOut size={16} /></button>
          </div>
          <button className="wb-collapse" onClick={() => { setCollapsed(!collapsed); store.set('favor.side', collapsed ? null : 'collapsed') }}>
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}<span>收起侧栏</span>
          </button>
        </div>
      </aside>

      <div className="wb-main">
        <header className="wb-top">
          <div className="title">
            <h1>{key === '/app' ? `${greeting()}，${name}` : title}</h1>
            <p>{key === '/app' ? today : subtitle}</p>
          </div>
          <div className="tools">
            {inHealth ? <>
              <button className="btn btn-primary hide-sm" onClick={() => setRecording(true)}><Plus size={16} />记一笔</button>
              <button className="icon-btn mobile-only" aria-label="记一笔" onClick={() => setRecording(true)}><Plus size={19} /></button>
            </> : <>
              <button className="btn btn-primary hide-sm" onClick={() => navigate('/app/fridge?add=1')}><Plus size={16} />加食材</button>
              <button className="icon-btn mobile-only" aria-label="加食材" onClick={() => navigate('/app/fridge?add=1')}><Plus size={19} /></button>
            </>}
            {!onChatPage && (
              <button className={`btn ${showDock ? 'btn-ghost' : ''} dock-toggle hide-sm`} onClick={() => toggleDock(!dockOpen)}>
                {showDock ? <PanelRightClose size={16} /> : <MessageCircleHeart size={16} />}
                {showDock ? '收起 Favor' : '问 Favor'}
                {!showDock && <span className="dot" />}
              </button>
            )}
          </div>
        </header>
        <div className="wb-content">
          {inHealth && (
            <nav className="sub-tabs" aria-label="健康">
              {HEALTH_TABS.map(([to, label]) => <NavLink key={to} to={to} end>{label}</NavLink>)}
            </nav>
          )}
          <Outlet />
        </div>
      </div>

      {showDock && <>
        <div className="dock-scrim" onClick={() => setDockOpen(false)} />
        <aside className="wb-dock" aria-label="Favor 助手">
          <div className="dock-head">
            <LogoMark size={34} animated />
            <div className="grow"><b>Favor</b><span><span className="live-dot" />在线 · 问问今天吃什么</span></div>
            <button className="icon-btn" title="新对话" aria-label="新对话" onClick={newDockChat}><MessageSquarePlus size={17} /></button>
            {dockConv && <Link className="icon-btn" title="在对话页打开" aria-label="在对话页打开" to={`/app/chat/${dockConv}`}><ExternalLink size={16} /></Link>}
            <button className="icon-btn" title="收起" aria-label="收起" onClick={() => toggleDock(false)}><X size={17} /></button>
          </div>
          <div className="dock-body">
            <ChatView compact conversationId={dockConv} onCreated={onDockCreated} onMissing={newDockChat} ask={ask} />
          </div>
        </aside>
      </>}

      {!showDock && !onChatPage && (
        <button className="fab" aria-label="问 Favor" onClick={() => setDockOpen(true)}><MessageCircleHeart size={24} /></button>
      )}

      <nav className="tabbar">
        {NAV.filter(n => !(healthMain && n.to === '/app/chat')).map(({ to, short, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}><Icon size={21} strokeWidth={1.8} />{short}</NavLink>
        ))}
        {healthMain && <NavLink to="/app/health" className={inHealth ? 'active' : ''}><HeartPulse size={21} strokeWidth={1.8} />健康</NavLink>}
        <NavLink to="/app/me" className={!healthMain && inHealth ? 'active' : ''}><UserRound size={21} strokeWidth={1.8} />我的</NavLink>
      </nav>

      <Tour />

      {recording && <RecordModal onClose={() => setRecording(false)} onSaved={() => emitDataChanged()} />}
    </div>
  )
}

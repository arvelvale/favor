import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ChartNoAxesColumn, ExternalLink, LayoutDashboard, ListChecks, LogOut, MessageCircleHeart, MessageSquarePlus,
  PanelLeftClose, PanelLeftOpen, PanelRightClose, Plus, UserRound, X,
} from 'lucide-react'
import { useAuth } from '../App'
import { emitDataChanged } from '../lib/motion'
import ChatView, { type AskRequest } from './ChatView'
import Logo, { LogoMark } from './Logo'
import RecordModal from './RecordModal'

const NAV = [
  { to: '/app', label: '总览', icon: LayoutDashboard, end: true },
  { to: '/app/chat', label: '对话', icon: MessageCircleHeart },
  { to: '/app/trends', label: '趋势', icon: ChartNoAxesColumn },
  { to: '/app/records', label: '记录', icon: ListChecks },
  { to: '/app/profile', label: '档案', icon: UserRound },
]

const TITLES: Record<string, [string, string]> = {
  '/app': ['总览', ''],
  '/app/chat': ['对话', '和 Favor 聊聊你的一天'],
  '/app/trends': ['趋势', '看看最近的变化'],
  '/app/records': ['记录', '你和 Favor 记下的每一条'],
  '/app/profile': ['健康档案', '用来计算每日目标，也让建议更贴合你'],
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
  const wide = () => window.innerWidth > 1280
  const [collapsed, setCollapsed] = useState(store.get('favor.side') === 'collapsed')
  const [dockOpen, setDockOpen] = useState(() => wide() && store.get('favor.dock') !== 'closed')
  const [dockConv, setDockConv] = useState<number | null>(() => Number(store.get('favor.dock.conv')) || null)
  const [ask, setAsk] = useState<AskRequest | null>(null)
  const [recording, setRecording] = useState(false)
  const onChatPage = pathname.startsWith('/app/chat')
  const showDock = dockOpen && !onChatPage
  const name = user?.nickname || user?.username || ''

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
          <Logo size={38} tone="light" subtitle="AI 健康管家" animated />
        </Link>
        <div className="wb-label">工作台</div>
        <nav className="wb-nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} title={label}>
              <Icon size={19} strokeWidth={1.9} /><span>{label}</span>
              {to === '/app/chat' && <span className="badge">AI</span>}
            </NavLink>
          ))}
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
            <button className="btn btn-primary hide-sm" onClick={() => setRecording(true)}><Plus size={16} />记一笔</button>
            <button className="icon-btn mobile-only" aria-label="记一笔" onClick={() => setRecording(true)}><Plus size={19} /></button>
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
          <Outlet />
        </div>
      </div>

      {showDock && <>
        <div className="dock-scrim" onClick={() => setDockOpen(false)} />
        <aside className="wb-dock" aria-label="Favor 助手">
          <div className="dock-head">
            <LogoMark size={34} animated />
            <div className="grow"><b>Favor</b><span><span className="live-dot" />在线 · 说一句就能记录</span></div>
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
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}><Icon size={21} strokeWidth={1.8} />{label}</NavLink>
        ))}
      </nav>

      {recording && <RecordModal onClose={() => setRecording(false)} onSaved={() => emitDataChanged()} />}
    </div>
  )
}

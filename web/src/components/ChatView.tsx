import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowUp, ChartNoAxesColumn, ChefHat, CircleAlert, CircleCheck, Image as ImageIcon, ImageOff, Loader2, Moon, Sparkles,
  Sprout, Square, UserRound,
  UtensilsCrossed, type LucideIcon,
} from 'lucide-react'
import { api, ApiError, streamChat, type Card, type ChatMessage, type Conversation, type ImageMeta } from '../lib/api'
import { emitDataChanged } from '../lib/motion'
import { useAuth } from '../App'
import { MetricIcon } from './ui'
import { LogoMark } from './Logo'

const STARTERS: { icon: LucideIcon; color: string; title: string; text: string }[] = [
  { icon: UtensilsCrossed, color: 'var(--meal)', title: '记一顿饭', text: '午饭吃了一碗牛肉面，加了个卤蛋，还喝了杯奶茶' },
  { icon: ChefHat, color: 'var(--exercise)', title: '晚餐吃什么', text: '冰箱里有鸡胸肉、西兰花和鸡蛋，帮我配一份晚餐，控制在剩余热量内' },
  { icon: ChartNoAxesColumn, color: 'var(--water)', title: '看看这周', text: '帮我总结一下最近 7 天的饮食、睡眠和运动情况' },
  { icon: Moon, color: 'var(--sleep)', title: '想睡得更好', text: '我最近总是一点多才睡，帮我定几个能坚持的小习惯' },
]

interface LiveMessage extends ChatMessage { pending?: boolean; tool?: string | null; gap?: boolean; error?: string }

export interface AskRequest { text: string; nonce: number }

export default function ChatView({ conversationId, onCreated, onMissing, onTurnDone, compact = false, ask }: {
  conversationId: number | null
  onCreated: (id: number) => void
  onMissing?: () => void
  onTurnDone?: () => void
  compact?: boolean
  ask?: AskRequest | null
}) {
  const { llmEnabled } = useAuth()
  const [messages, setMessages] = useState<LiveMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState('')
  // 历史消息加载完成前不处理外部 ask，避免加载结果覆盖正在流式输出的内容
  const [ready, setReady] = useState(conversationId === null)
  const created = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const convRef = useRef(conversationId)
  convRef.current = conversationId

  useEffect(() => {
    setLoadError('')
    if (conversationId === null) { setMessages([]); setReady(true); return }
    // 本组件刚创建的对话：消息已在本地，不要用服务端的空列表覆盖正在流式输出的内容
    if (created.current === conversationId) { created.current = null; return }
    let alive = true
    setReady(false)
    api.get<{ messages: ChatMessage[] }>(`/api/conversations/${conversationId}/messages`)
      .then(r => { if (alive) setMessages(r.messages) })
      .catch(e => {
        if (!alive) return
        if (e instanceof ApiError && e.status === 404 && onMissing) onMissing()  // 对话已被删除：回到新对话
        else setLoadError(e instanceof ApiError ? e.message : '加载失败')
      })
      .finally(() => { if (alive) setReady(true) })
    return () => { alive = false }
  }, [conversationId, onMissing])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  useEffect(() => () => abortRef.current?.abort(), [])

  const patchLast = (fn: (m: LiveMessage) => LiveMessage) =>
    setMessages(list => list.map((m, i) => (i === list.length - 1 ? fn(m) : m)))

  const send = useCallback(async (raw: string) => {
    const text = raw.trim()
    if (!text || busy || !llmEnabled) return
    setBusy(true)
    setInput('')
    if (taRef.current) taRef.current.style.height = 'auto'
    let target = convRef.current
    try {
      if (target === null) {
        const r = await api.post<{ conversation: Conversation }>('/api/conversations')
        target = r.conversation.id
        created.current = target
        onCreated(target)
      }
    } catch (e) {
      setBusy(false)
      setLoadError(e instanceof ApiError ? e.message : '创建对话失败')
      return
    }
    setMessages(list => [...list,
      { id: `u${Date.now()}`, role: 'user', content: text, cards: [] },
      { id: `a${Date.now()}`, role: 'assistant', content: '', cards: [], pending: true, tool: null }])

    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await streamChat(target, text, ev => {
        // 工具调用把一次回复分成多段：新一段文字前补一个空行，和历史回放的拼接方式一致
        if (ev.type === 'delta') patchLast(m => ({
          ...m, tool: null, gap: false, content: m.content + (m.gap && m.content ? '\n\n' : '') + ev.content,
        }))
        else if (ev.type === 'tool') patchLast(m => ({ ...m, tool: ev.label, gap: true }))
        else if (ev.type === 'card') {
          patchLast(m => ({ ...m, cards: [...m.cards, ev.card] }))
          emitDataChanged()  // 工作台上的面板立即刷新
        }
        else if (ev.type === 'error') patchLast(m => ({ ...m, error: ev.message }))
      }, ctrl.signal)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        patchLast(m => ({ ...m, error: e instanceof ApiError ? e.message : '连接中断了，请重试' }))
      }
    } finally {
      patchLast(m => ({ ...m, pending: false, tool: null }))
      setBusy(false)
      abortRef.current = null
      onTurnDone?.()
    }
  }, [busy, llmEnabled, onCreated, onTurnDone])

  // 外部（如工作台“今日建议”）请求发送一句话
  const lastAsk = useRef(0)
  useEffect(() => {
    if (ask && ask.nonce !== lastAsk.current && !busy && ready) {
      lastAsk.current = ask.nonce
      send(ask.text)
    }
  }, [ask, busy, ready, send])

  return (
    <div className={`chat-view ${compact ? 'compact' : ''}`}>
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-inner">
          {!llmEnabled && (
            <div className="notice warn"><CircleAlert size={16} style={{ flexShrink: 0, marginTop: 2 }} />
              服务端还没有配置模型密钥（LLM_API_KEY），对话暂不可用；手动记录、趋势和档案功能可以正常使用。</div>
          )}
          {loadError && <div className="notice warn"><CircleAlert size={16} style={{ flexShrink: 0, marginTop: 2 }} />{loadError}</div>}
          {messages.length === 0 && (
            <div className="welcome">
              <h2>今天过得怎么样？</h2>
              <p>像和朋友聊天一样告诉我，我来记录和分析。</p>
              <div className="starter-grid">
                {STARTERS.map(s => (
                  <button key={s.title} className="starter" onClick={() => send(s.text)} disabled={!llmEnabled || busy}>
                    <span className="metric-icon sm" style={{ '--c': s.color } as CSSProperties}><s.icon size={14} /></span>
                    <div><b>{s.title}</b><span>{s.text}</span></div>
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map(m => m.role === 'user'
            ? <div className="msg user" key={m.id}><div className="bubble-user">{m.content}</div></div>
            : <AssistantMessage key={m.id} m={m} />)}
        </div>
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea ref={taRef} rows={1} value={input} disabled={!llmEnabled}
            placeholder={compact ? '和 Favor 说说今天…' : '例如：早饭吃了两个肉包和一杯豆浆'}
            onChange={e => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(160, e.target.scrollHeight)}px`
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input) }
            }} />
          {busy
            ? <button className="send-btn" aria-label="停止" onClick={() => abortRef.current?.abort()}><Square size={13} fill="currentColor" /></button>
            : <button className="send-btn" aria-label="发送" disabled={!input.trim() || !llmEnabled} onClick={() => send(input)}><ArrowUp size={18} /></button>}
        </div>
        {!compact && <p className="composer-hint">Favor 提供的是生活方式建议，不能替代医生的诊断。身体有明显不适请及时就医。</p>}
      </div>
    </div>
  )
}

function AssistantMessage({ m }: { m: LiveMessage }) {
  const waiting = m.pending && !m.content && !m.tool && !m.cards.length
  return (
    <div className="msg">
      <LogoMark size={30} className="bot-mark" />
      <div className="bot-body">
        {m.cards.length > 0 && <div className="tool-cards">{m.cards.map((c, i) => <ToolCard key={i} card={c} />)}</div>}
        {m.tool && <span className="tool-running"><Loader2 size={14} className="spin" />{m.tool}…</span>}
        {waiting && <span className="typing"><i /><i /><i /></span>}
        {m.content && <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>}
        {m.error && <div className="notice warn"><CircleAlert size={15} style={{ flexShrink: 0, marginTop: 3 }} />{m.error}</div>}
      </div>
    </div>
  )
}

/** 菜品配图：后台生成，轮询状态；生成中显示流光占位，完成后淡入，点击看原图。 */
function ImageCard({ id, title }: { id: number; title: string }) {
  const [meta, setMeta] = useState<ImageMeta | null>(null)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    let alive = true
    let timer = 0
    let tries = 0
    const poll = () => {
      api.get<{ image: ImageMeta }>(`/api/images/${id}`).then(r => {
        if (!alive) return
        setMeta(r.image)
        // 先 2 秒一次，30 秒后放慢到 5 秒；3 分钟还没好就停止并提示
        if (r.image.status === 'pending' && ++tries < 60) timer = window.setTimeout(poll, tries < 15 ? 2000 : 5000)
        else if (r.image.status === 'pending') setMeta({ ...r.image, status: 'failed', error: '生成时间太久了，稍后再试' })
      }).catch(() => { if (alive) setMeta({ id, title, status: 'failed', error: '图片加载失败' }) })
    }
    poll()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [id, title])

  const status = meta?.status ?? 'pending'
  const src = `/api/images/${id}/file`
  return (
    <div className={`image-card ${status}`}>
      {status === 'ready' ? (
        <a href={src} target="_blank" rel="noreferrer" className="image-frame" title="查看原图">
          <img src={src} alt={title} onLoad={() => setLoaded(true)} className={loaded ? 'in' : ''} />
        </a>
      ) : status === 'pending' ? (
        <div className="image-frame skeleton"><span><ImageIcon size={18} />正在生成「{title}」…</span></div>
      ) : (
        <div className="image-frame failed"><span><ImageOff size={18} />{meta?.error ?? '图片生成失败了'}</span></div>
      )}
      <div className="image-cap"><Sparkles size={12} />{title}<em>AI 生成示意图</em></div>
    </div>
  )
}

function ToolCard({ card }: { card: Card }) {
  if (card.type === 'image') return <ImageCard id={card.image_id} title={card.title} />
  if (card.type === 'record') {
    return (
      <div className={`tool-card ${card.action}`}>
        <MetricIcon kind={card.kind} size="sm" />
        <div className="t"><b>{card.title}</b><span>{card.action === 'deleted' ? '已删除' : `已记录 · ${card.at.slice(11, 16)}`}</span></div>
        {card.action !== 'deleted' && <CircleCheck size={16} className="ok" />}
      </div>
    )
  }
  if (card.type === 'profile') {
    return (
      <Link to="/app/profile" className="tool-card">
        <span className="metric-icon sm" style={{ '--c': 'var(--brand)' } as CSSProperties}><UserRound size={14} /></span>
        <div className="t"><b>{card.title}</b><span>每日目标 {card.calories} kcal · 饮水 {card.water_ml} ml</span></div>
      </Link>
    )
  }
  if (card.type === 'habit') {
    const label = { created: '新习惯', checked: '已打卡', unchecked: '已取消打卡' }[card.action]
    return (
      <Link to="/app" className="tool-card">
        <span className="metric-icon sm" style={{ '--c': 'var(--exercise)' } as CSSProperties}><Sprout size={14} /></span>
        <div className="t"><b>{card.title}</b><span>{label}</span></div>
      </Link>
    )
  }
  return (
    <Link to="/app/trends" className="tool-card">
      <span className="metric-icon sm" style={{ '--c': 'var(--water)' } as CSSProperties}><ChartNoAxesColumn size={14} /></span>
      <div className="t"><b>分析了最近 {card.days} 天的数据</b><span>查看趋势图</span></div>
    </Link>
  )
}

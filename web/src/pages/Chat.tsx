import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { MessageSquarePlus, Trash2 } from 'lucide-react'
import { api, type Conversation } from '../lib/api'
import ChatView from '../components/ChatView'
import { useToast } from '../components/ui'

export default function ChatPage() {
  const { id } = useParams()
  const convId = id ? Number(id) : null
  const navigate = useNavigate()
  const toast = useToast()
  const [convs, setConvs] = useState<Conversation[]>([])

  const loadConvs = useCallback(() => {
    api.get<{ conversations: Conversation[] }>('/api/conversations').then(r => setConvs(r.conversations)).catch(() => undefined)
  }, [])
  useEffect(loadConvs, [loadConvs])

  const onCreated = useCallback((newId: number) => {
    navigate(`/app/chat/${newId}`, { replace: true })
    loadConvs()
  }, [navigate, loadConvs])
  const onMissing = useCallback(() => { toast('这个对话已经不存在了'); navigate('/app/chat', { replace: true }) }, [navigate, toast])

  async function removeConv(c: Conversation) {
    if (!confirm(`删除对话「${c.title}」？已记录的健康数据不受影响。`)) return
    await api.del(`/api/conversations/${c.id}`).catch(e => toast(e.message))
    loadConvs()
    if (c.id === convId) navigate('/app/chat')
  }

  return (
    <div className="wb-page full">
      <div className="chat-page">
        <aside className="conv-list">
          <button className="btn btn-primary btn-block" style={{ marginBottom: 14 }} onClick={() => navigate('/app/chat')}>
            <MessageSquarePlus size={16} />新对话
          </button>
          {convs.map(c => (
            <div key={c.id} className={`conv-item ${c.id === convId ? 'active' : ''}`} onClick={() => navigate(`/app/chat/${c.id}`)}>
              <span className="t">{c.title}</span>
              <button className="icon-btn danger" aria-label="删除对话" onClick={e => { e.stopPropagation(); removeConv(c) }}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {!convs.length && <p className="muted" style={{ fontSize: 12.5, padding: '4px 10px' }}>聊过的内容会出现在这里</p>}
        </aside>
        <ChatView conversationId={convId} onCreated={onCreated} onMissing={onMissing} onTurnDone={loadConvs} />
      </div>
    </div>
  )
}

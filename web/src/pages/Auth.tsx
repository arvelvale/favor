import { useState, type CSSProperties, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChartNoAxesColumn, MessageCircleHeart, Sprout } from 'lucide-react'
import Logo from '../components/Logo'
import { api, ApiError, type User } from '../lib/api'
import { useAuth } from '../App'
import { clearPrefsCache } from '../lib/prefs'

const FEATS = [
  { icon: MessageCircleHeart, color: '#ff9a6b', title: '说一句就记好', text: '“午饭一碗牛肉面”——热量和营养自动估算' },
  { icon: ChartNoAxesColumn, color: '#7fb6ff', title: '看懂自己的趋势', text: '体重、睡眠、饮食与运动，一眼看清变化' },
  { icon: Sprout, color: '#6fdc9f', title: '小习惯慢慢养', text: '把目标拆成每天能打卡的一小步' },
]

export default function AuthPage({ initialMode = 'login' }: { initialMode?: 'login' | 'register' }) {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState(initialMode)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const url = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const res = await api.post<{ user: User }>(url, { username, password, nickname })
      clearPrefsCache()
      setUser(res.user)
      navigate('/app', { replace: true })
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : '出了点问题，请稍后再试')
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    const next = mode === 'login' ? 'register' : 'login'
    setMode(next)
    setErr('')
    navigate(`/${next}`, { replace: true })
  }

  return (
    <div className="auth">
      <section className="auth-side">
        <div className="orb a" /><div className="orb b" />
        <div>
          <Link to="/" className="wb-brand" style={{ padding: 0 }}>
            <Logo size={42} tone="light" subtitle="AI 厨房搭子" animated />
          </Link>
          <h1>照顾好自己，<br />从<span className="grad-text">记下今天</span>开始。</h1>
          <p className="lead">Favor 是一位懂营养学的 AI 朋友。你只管像聊天一样告诉它，记录、分析和建议交给它。</p>
        </div>
        <div className="auth-feats">
          {FEATS.map(f => (
            <div className="auth-feat" key={f.title}>
              <span className="metric-icon" style={{ '--c': f.color } as CSSProperties}><f.icon size={17} /></span>
              <div><b>{f.title}</b><span>{f.text}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section className="auth-main">
        <Link to="/" className="btn btn-ghost btn-sm auth-back"><ArrowLeft size={15} />返回首页</Link>
        <form className="auth-form" onSubmit={submit} key={mode}>
          <h2>{mode === 'login' ? '欢迎回来' : '创建账号'}</h2>
          <p className="sub">{mode === 'login' ? '登录后看看今天吃什么' : '只需要一个用户名和密码'}</p>
          <div className="stack">
            <label className="field"><span>用户名</span>
              <input className="input" autoComplete="username" value={username} required
                onChange={e => setUsername(e.target.value)} placeholder="3–20 位字母或数字" /></label>
            {mode === 'register' && (
              <label className="field"><span>怎么称呼你（可选）</span>
                <input className="input" value={nickname} onChange={e => setNickname(e.target.value)} placeholder="例如 小林" /></label>
            )}
            <label className="field"><span>密码</span>
              <input className="input" type="password" required value={password}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                onChange={e => setPassword(e.target.value)} placeholder={mode === 'register' ? '至少 8 位' : ''} /></label>
            {err && <p className="error-text">{err}</p>}
            <button className="btn btn-primary btn-block" disabled={busy} style={{ height: 44, marginTop: 4 }}>
              {busy ? '请稍候…' : mode === 'login' ? '登录' : '注册并进入工作台'}
            </button>
          </div>
          <p className="auth-switch">
            {mode === 'login' ? '还没有账号？' : '已经有账号了？'}
            <button type="button" onClick={switchMode}>{mode === 'login' ? '注册一个' : '去登录'}</button>
          </p>
        </form>
      </section>
    </div>
  )
}

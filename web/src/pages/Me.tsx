import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, HeartPulse, IdCard, LogOut, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useAuth } from '../App'
import { adjustments, usePrefs } from '../lib/prefs'

export default function MePage() {
  const { user, logout } = useAuth()
  const state = usePrefs()
  const name = user?.nickname || user?.username || ''

  return (
    <div className="wb-page">
      <div className="me-grid stagger">
        <section className="card me-head">
          <div className="avatar lg">{name.slice(0, 1).toUpperCase()}</div>
          <div className="grow"><b>{name}</b><span>@{user?.username}</span></div>
          <button className="btn btn-ghost" onClick={logout}><LogOut size={16} />退出登录</button>
        </section>

        <section className="card me-prefs">
          <div className="card-title">
            <h2><SlidersHorizontal size={16} />厨房偏好</h2>
            <Link to="/welcome?redo=1" className="hint"><RotateCcw size={12} style={{ verticalAlign: -1 }} /> 重新做一遍问卷</Link>
          </div>
          <p className="muted me-lead">
            {state?.status === 'skipped' ? '你跳过了问卷，下面是默认设置。' : '这些设置决定了 Favor 给你推荐什么。'}
            点任意一条单独修改。
          </p>
          {state ? (
            <ul className="adjust-list">
              {adjustments(state).map(a => (
                <li key={a.q}>
                  <Link to={`/welcome?q=${a.q}`} style={{ '--c': a.color } as CSSProperties}>
                    <span className="adj-ico"><a.icon size={17} /></span>
                    <span className="adj-text">{a.text}{a.defaulted && <em>默认</em>}</span>
                    <ChevronRight size={16} className="adj-go" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <div className="skeleton" style={{ height: 300 }} />}
        </section>

        <section className="card me-links">
          <div className="card-title"><h2><HeartPulse size={16} />健康</h2></div>
          <Link to="/app/health" className="me-link" style={{ '--c': '#e5484d' } as CSSProperties}>
            <span className="adj-ico"><HeartPulse size={17} /></span>
            <span className="grow"><b>健康记录</b><small>做完菜会自动记一餐，在这里看热量和趋势</small></span>
            <ChevronRight size={16} />
          </Link>
          <Link to="/app/profile" className="me-link" style={{ '--c': '#2f7cf6' } as CSSProperties}>
            <span className="adj-ico"><IdCard size={17} /></span>
            <span className="grow"><b>身体档案</b><small>身高体重、目标、过敏</small></span>
            <ChevronRight size={16} />
          </Link>
        </section>
      </div>
    </div>
  )
}

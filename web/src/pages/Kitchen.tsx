import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ChefHat, CircleAlert, Leaf, Loader2, RefreshCw, Refrigerator, Sparkles } from 'lucide-react'
import { api, ApiError, type PantryItem, type RecipeBatch } from '../lib/api'
import { isExpiring, STORAGE_META, STORAGES } from '../lib/kitchen'
import { useDataChanged } from '../lib/motion'
import { useAuth } from '../App'
import { useToast } from '../components/ui'
import { CatDot, ExpiryPill, PantryAdder, RecipeCard, RecipeSkeletons } from '../components/Kitchen'

const THINKING = ['正在翻冰箱…', '看看哪些快过期了…', '挑几道现在就能做的…', '快好了…']

export default function KitchenPage() {
  const toast = useToast()
  const { llmEnabled } = useAuth()
  const [pantry, setPantry] = useState<PantryItem[] | null>(null)
  const [batch, setBatch] = useState<RecipeBatch | null>(null)
  const [note, setNote] = useState('')
  const [thinking, setThinking] = useState(false)
  const [tick, setTick] = useState(0)
  const [failed, setFailed] = useState('')

  const load = useCallback(() => {
    api.get<{ items: PantryItem[] }>('/api/pantry').then(r => setPantry(r.items)).catch(e => toast(e.message))
    api.get<RecipeBatch>('/api/recipes/latest').then(setBatch).catch(() => undefined)
  }, [toast])
  useEffect(load, [load])
  useDataChanged(load)

  useEffect(() => {
    if (!thinking) return
    const t = window.setInterval(() => setTick(x => x + 1), 2200)
    return () => window.clearInterval(t)
  }, [thinking])

  async function recommend() {
    setThinking(true); setFailed(''); setTick(0)
    try {
      const res = await api.post<RecipeBatch>('/api/recipes/recommend', { note: note.trim() })
      setBatch({ ...res, stale: false })
      if (res.dropped?.length) toast(`已排除 ${res.dropped.length} 道含过敏原的菜`)
    } catch (e) { setFailed(e instanceof ApiError ? e.message : '这次没想出来，再试一次吧') }
    finally { setThinking(false) }
  }

  if (pantry === null) {
    return <div className="wb-page"><div className="ov"><div className="skeleton span-8" style={{ height: 260 }} /><div className="skeleton span-4" style={{ height: 260 }} /></div></div>
  }

  const expiring = pantry.filter(p => isExpiring(p.days_left))
  const hasRecipes = !!batch?.recipes.length

  // 冰箱是空的：首页就是录入，别让用户先去找入口
  if (!pantry.length) {
    return (
      <div className="wb-page">
        <section className="card kitchen-hero empty-hero stagger">
          <div className="hero-copy">
            <span className="hero-kicker"><Refrigerator size={14} />第一步</span>
            <h2>先告诉 Favor，冰箱里有什么</h2>
            <p>选几样常见的，或者直接说一句话。不用填数量，也不用记保质期。</p>
          </div>
          <PantryAdder existing={pantry} onAdded={load} />
        </section>
      </div>
    )
  }

  return (
    <div className="wb-page">
      <div className="ov stagger">
        <section className="card kitchen-hero span-8">
          <div className="hero-copy">
            <span className="hero-kicker"><ChefHat size={14} />今天吃什么</span>
            <h2>{expiring.length ? `有 ${expiring.length} 样快过期了，先用掉它们？` : '冰箱里的东西，够做好几顿了'}</h2>
            <p>冰箱里有 {pantry.length} 样食材。Favor 会优先推荐现在就能做的菜，顺手用掉快过期的。</p>
          </div>
          <div className="ask-row">
            <input className="input" value={note} maxLength={100} disabled={thinking}
              placeholder="有什么要求？比如：想吃辣的、两个人吃、15 分钟内"
              onChange={e => setNote(e.target.value)} onKeyDown={e => e.key === 'Enter' && !thinking && llmEnabled && recommend()} />
            <button className="btn btn-primary btn-lg" onClick={recommend} disabled={thinking || !llmEnabled}>
              {thinking ? <Loader2 size={17} className="spin" /> : hasRecipes ? <RefreshCw size={17} /> : <Sparkles size={17} />}
              {thinking ? THINKING[tick % THINKING.length] : hasRecipes ? '换一批' : '帮我想想'}
            </button>
          </div>
          {!llmEnabled && <p className="hero-note"><CircleAlert size={14} />服务端还没配置模型密钥，暂时不能推荐菜谱。</p>}
          {failed && <p className="hero-note warn"><CircleAlert size={14} />{failed}</p>}
          {batch?.stale && !thinking && hasRecipes && (
            <p className="hero-note"><RefreshCw size={14} />冰箱有变化，下面的推荐可能不是最新的，可以换一批。</p>
          )}
        </section>

        <section className="card span-4 expiring-card">
          <div className="card-title"><h2><Leaf size={16} color="#1e9e5e" />快过期的</h2><Link to="/app/fridge" className="hint">去冰箱</Link></div>
          {expiring.length ? (
            <div className="mini-list">
              {expiring.slice(0, 5).map(p => (
                <div className="mini-row" key={p.id}><CatDot category={p.category} size={26} /><b>{p.name}</b><ExpiryPill daysLeft={p.days_left} estimated={p.expires_estimated} /></div>
              ))}
              {expiring.length > 5 && <Link to="/app/fridge" className="muted" style={{ fontSize: 12.5 }}>还有 {expiring.length - 5} 样</Link>}
            </div>
          ) : <p className="muted" style={{ fontSize: 13 }}>两天内没有要过期的，放心慢慢吃。</p>}
          <div className="storage-sum">
            {STORAGES.map(s => {
              const Icon = STORAGE_META[s].icon
              const n = pantry.filter(p => p.storage === s).length
              return <Link to="/app/fridge" key={s} style={{ '--c': STORAGE_META[s].color } as CSSProperties}><Icon size={14} /><b className="num">{n}</b><span>{STORAGE_META[s].label}</span></Link>
            })}
          </div>
        </section>

        <section className="span-12 recipes-section">
          <div className="section-head">
            <h2>{thinking ? 'Favor 正在想…' : hasRecipes ? '推荐给你' : '还没有推荐'}</h2>
            {hasRecipes && !thinking && <span className="muted">点开看用料和步骤，做完点「做好了」会自动更新冰箱</span>}
          </div>
          {thinking ? <RecipeSkeletons /> : hasRecipes ? (
            <div className="recipe-grid">{batch!.recipes.map((r, i) => <RecipeCard key={r.id} r={r} index={i} />)}</div>
          ) : (
            <div className="card empty-recipes">
              <ChefHat size={36} />
              <p>点上面的「帮我想想」，Favor 会根据冰箱里的 {pantry.length} 样食材推荐 3 道菜。</p>
            </div>
          )}
        </section>

        <section className="card span-12 quick-add">
          <div className="card-title"><h2><Refrigerator size={16} />顺手补几样</h2><Link to="/app/fridge" className="hint">管理冰箱 <ArrowRight size={12} style={{ verticalAlign: -1 }} /></Link></div>
          <PantryAdder existing={pantry} onAdded={load} />
        </section>
      </div>
    </div>
  )
}

import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ChefHat, CircleAlert, ClipboardCheck, Leaf, Loader2, RefreshCw, Refrigerator, Sparkles } from 'lucide-react'
import { api, ApiError, type DislikeReason, type PantryItem, type RecipeBatch, type RecipeBrief } from '../lib/api'
import { isExpiring, STORAGE_META, STORAGES } from '../lib/kitchen'
import { emitDataChanged, useDataChanged } from '../lib/motion'
import { OnboardingChecklist, TipBanner } from '../components/Onboarding'
import { usePrefs } from '../lib/prefs'
import { useAuth } from '../App'
import { useToast } from '../components/ui'
import { CatDot, ExpiryPill, PantryAdder, RecipeCard, RecipeSkeletons } from '../components/Kitchen'

const THINKING = ['正在翻冰箱…', '看看哪些快过期了…', '挑几道现在就能做的…', '快好了…']

export default function KitchenPage() {
  const toast = useToast()
  const { llmEnabled, visionEnabled } = useAuth()
  const prefs = usePrefs()
  // 问卷 Q7 选了「食材总放坏」：快过期的放在首页最前面
  const wasteFirst = !!prefs?.prefs.goals.includes('waste')
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
      emitDataChanged()  // 引导进度、上手清单跟着刷新
      if (res.dropped?.length) {
        const why = [...new Set(res.dropped.map(d => d.reason))].slice(0, 2).join('，')
        toast(`按你的设置去掉了 ${res.dropped.length} 道菜（${why}）`)
      }
    } catch (e) { setFailed(e instanceof ApiError ? e.message : '这次没想出来，再试一次吧') }
    finally { setThinking(false) }
  }

  async function dislike(r: RecipeBrief, reason: DislikeReason) {
    try {
      await api.post(`/api/recipes/${r.id}/dislike`, { reason })
      setBatch(b => b && { ...b, recipes: b.recipes.map(x => (x.id === r.id ? { ...x, disliked: reason } : x)) })
      toast(reason === 'not_like' ? `好的，以后不再推荐「${r.title}」` : reason === 'too_hard' ? '记下了，以后多推省事的' : `好的，这几天先不推「${r.title}」`)
    } catch (e) { toast(e instanceof ApiError ? e.message : '没记上，再试一次') }
  }

  if (pantry === null) {
    return <div className="wb-page"><div className="ov"><div className="skeleton span-8" style={{ height: 260 }} /><div className="skeleton span-4" style={{ height: 260 }} /></div></div>
  }

  // 过期的（多半是按类别估算的日期）不进「快过期」，单独让用户清点；推荐时服务端也不会用它们
  const expired = pantry.filter(p => p.days_left !== null && p.days_left < 0)
  const expiring = pantry.filter(p => isExpiring(p.days_left) && !(p.days_left !== null && p.days_left < 0))
  // 说过「不想吃」的不再展示（刷新后也一样）
  const shown = (batch?.recipes ?? []).filter(r => !r.disliked)
  const hasRecipes = shown.length > 0

  // 冰箱是空的：首页就是录入，别让用户先去找入口
  if (!pantry.length) {
    return (
      <div className="wb-page">
        <section className="card kitchen-hero empty-hero stagger">
          <div className="hero-copy">
            <span className="hero-kicker"><Refrigerator size={14} />第一步</span>
            <h2>先告诉 Favor，冰箱里有什么</h2>
            <p>{visionEnabled ? '拍一张冰箱、选几样常见的，或者直接说一句话。不用填数量，也不用记保质期。' : '选几样常见的，或者直接说一句话。不用填数量，也不用记保质期。'}</p>
          </div>
          <div data-tour="pantry"><PantryAdder existing={pantry} onAdded={load} /></div>
        </section>
        <div className="ov" style={{ marginTop: 18 }}><TipBanner page="home" /><OnboardingChecklist /></div>
      </div>
    )
  }

  return (
    <div className="wb-page">
      <div className={`ov stagger ${wasteFirst ? 'waste-first' : ''}`}>
        {expired.length > 0 && <ReviewCard items={expired} onDone={load} />}
        <TipBanner page="home" />
        <OnboardingChecklist />
        <section className="card kitchen-hero span-8">
          <div className="hero-copy">
            <span className="hero-kicker"><ChefHat size={14} />今天吃什么</span>
            <h2>{expiring.length ? `有 ${expiring.length} 样快过期了，先用掉它们？` : '冰箱里的东西，够做好几顿了'}</h2>
            <p>冰箱里有 {pantry.length} 样食材。Favor 会优先推荐现在就能做的菜，顺手用掉快过期的。
              {prefs && <>按<Link to="/app/me" className="hero-link">{prefs.servings} 人份{prefs.prefs.minutes ? `、${prefs.prefs.minutes} 分钟内` : ''}</Link>来推荐。</>}</p>
          </div>
          <div className="ask-row">
            <input className="input" value={note} maxLength={100} disabled={thinking}
              placeholder="有什么要求？比如：想吃辣的、两个人吃、15 分钟内"
              onChange={e => setNote(e.target.value)} onKeyDown={e => e.key === 'Enter' && !thinking && llmEnabled && recommend()} />
            <button className="btn btn-primary btn-lg" data-tour="recommend" onClick={recommend} disabled={thinking || !llmEnabled}>
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
            <div className="recipe-grid">{shown.map((r, i) => <RecipeCard key={r.id} r={r} index={i} tour={i === 0 ? 'first-recipe' : undefined} onDislike={dislike} />)}</div>
          ) : (
            <div className="card empty-recipes">
              <ChefHat size={36} />
              <p>点上面的「帮我想想」，Favor 会根据冰箱里的 {pantry.length} 样食材推荐 3 道菜。</p>
            </div>
          )}
        </section>

        <section className="card span-12 quick-add">
          <div className="card-title"><h2><Refrigerator size={16} />顺手补几样</h2><Link to="/app/fridge" className="hint">管理冰箱 <ArrowRight size={12} style={{ verticalAlign: -1 }} /></Link></div>
          <div data-tour="pantry"><PantryAdder existing={pantry} onAdded={load} /></div>
        </section>
      </div>
    </div>
  )
}

/** 清点过期食材：按估算已经过期的，问一句「还在吗」。还在的改成 2 天后到期（当快过期优先用掉），用完/扔了的移出冰箱。 */
function ReviewCard({ items, onDone }: { items: PantryItem[]; onDone: () => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [confirmAll, setConfirmAll] = useState(false)
  async function review(decisions: { id: number; action: 'keep' | 'used' | 'discarded' }[], msg: string) {
    setBusy(true)
    try {
      await api.post('/api/pantry/review', { items: decisions })
      toast(msg)
      emitDataChanged()
      onDone()
    } catch (e) { toast(e instanceof ApiError ? e.message : '没改成，再试一次') }
    finally { setBusy(false); setConfirmAll(false) }
  }
  return (
    <section className="card span-12 review-card">
      <div className="card-title">
        <h2><ClipboardCheck size={16} color="#d9480f" />这几样按估算已经过期了，还在吗？</h2>
      </div>
      <p className="muted review-lead">过期的不会用在推荐里。点「还在」的会当成快过期的，优先帮你用掉。</p>
      <div className="review-list">
        {items.map(p => (
          <div className="review-row" key={p.id}>
            <CatDot category={p.category} size={28} />
            <b>{p.name}</b>
            <ExpiryPill daysLeft={p.days_left} estimated={p.expires_estimated} />
            <div className="review-actions">
              <button className="btn btn-sm" disabled={busy} onClick={() => review([{ id: p.id, action: 'keep' }], `${p.name}还在，先用掉它`)}>还在</button>
              <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => review([{ id: p.id, action: 'used' }], `${p.name}用完了`)}>用完了</button>
              <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => review([{ id: p.id, action: 'discarded' }], `${p.name}扔掉了`)}>扔了</button>
            </div>
          </div>
        ))}
      </div>
      {items.length > 1 && (
        <div className="review-foot">
          {confirmAll
            ? <><span className="muted">把这 {items.length} 样都移出冰箱？</span>
                <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setConfirmAll(false)}>算了</button>
                <button className="btn btn-sm" disabled={busy} onClick={() => review(items.map(p => ({ id: p.id, action: 'discarded' as const })), `清掉了 ${items.length} 样`)}>都扔了</button></>
            : <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setConfirmAll(true)}>都不在了，一键清掉</button>}
        </div>
      )}
    </section>
  )
}

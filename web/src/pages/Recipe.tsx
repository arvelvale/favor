import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, Bookmark, BookmarkCheck, Check, ChefHat, ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Clock, Flame,
  Leaf, Lightbulb, Loader2, Minus, Pause, Play, Plus, RotateCcw, ShoppingBasket, Timer, Users, X,
} from 'lucide-react'
import { api, ApiError, type CookPreview, type CookResult, type Recipe } from '../lib/api'
import { DIFFICULTY, formatQty, MEAL_SLOTS } from '../lib/kitchen'
import { emitDataChanged } from '../lib/motion'
import { useToast } from '../components/ui'

export default function RecipePage() {
  const { id } = useParams()
  const toast = useToast()
  const navigate = useNavigate()
  const [recipe, setRecipe] = useState<Recipe | null>(null)
  const [missing, setMissing] = useState(false)
  const [cooking, setCooking] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [done, setDone] = useState<CookResult | null>(null)

  const load = useCallback(() => {
    api.get<{ recipe: Recipe }>(`/api/recipes/${id}`).then(r => setRecipe(r.recipe))
      .catch(e => { if (e instanceof ApiError && e.status === 404) setMissing(true); else toast(e.message) })
  }, [id, toast])
  useEffect(load, [load])

  async function toggleSave() {
    if (!recipe) return
    try {
      await api.post(`/api/recipes/${recipe.id}/save`, { saved: !recipe.saved })
      setRecipe({ ...recipe, saved: !recipe.saved })
      toast(recipe.saved ? '已取消收藏' : '收藏好了，在「收藏」里能找到')
    } catch (e) { toast(e instanceof ApiError ? e.message : '操作失败') }
  }

  if (missing) {
    return <div className="wb-page"><div className="card empty"><ChefHat size={36} /><p>这道菜找不到了。</p><Link className="btn btn-sm" style={{ marginTop: 10 }} to="/app">回到今天吃什么</Link></div></div>
  }
  if (!recipe) return <div className="wb-page"><div className="skeleton" style={{ height: 420 }} /></div>

  const have = recipe.ingredients.filter(i => i.status === 'have')
  const ready = recipe.missing.length === 0

  return (
    <div className="wb-page recipe-page">
      <button className="btn btn-ghost btn-sm back-btn" onClick={() => navigate(-1)}><ArrowLeft size={15} />返回</button>

      {done ? <CookDone result={done} /> : (
        <>
          <section className="card recipe-head">
            <div className="grow">
              <div className="recipe-top">
                <span className={`ready-tag ${ready ? 'ok' : 'miss'}`}>
                  {ready ? <><Check size={12} strokeWidth={3} />现在就能做</> : <><ShoppingBasket size={12} />还缺 {recipe.missing.length} 样</>}
                </span>
                {recipe.uses_expiring.length > 0 && <span className="save-tag"><Leaf size={12} />用掉 {recipe.uses_expiring.join('、')}</span>}
                {recipe.cooked_count > 0 && <span className="tag">做过 {recipe.cooked_count} 次</span>}
              </div>
              <h2>{recipe.title}</h2>
              {recipe.summary && <p className="muted">{recipe.summary}</p>}
              <div className="recipe-meta big">
                <span><Clock size={15} />{recipe.minutes} 分钟</span>
                <span><ChefHat size={15} />{DIFFICULTY[recipe.difficulty] ?? '简单'}</span>
                <span><Users size={15} />{recipe.servings} 人份</span>
                {recipe.kcal_per_serving ? <span><Flame size={15} />每份约 {recipe.kcal_per_serving} kcal</span> : null}
              </div>
            </div>
            <div className="head-actions">
              <button className="btn" onClick={toggleSave}>
                {recipe.saved ? <><BookmarkCheck size={16} color="var(--brand)" />已收藏</> : <><Bookmark size={16} />收藏</>}
              </button>
              <button className="btn btn-primary btn-lg" onClick={() => setCooking(true)}><Play size={16} />开始做菜</button>
            </div>
          </section>

          <div className="recipe-body">
            <section className="card">
              <div className="card-title"><h2>用料</h2><span className="hint">冰箱里有 {have.length} 样</span></div>
              <ul className="ing-list">
                {recipe.ingredients.map((ing, i) => (
                  <li key={i} className={ing.status}>
                    <span className="ing-mark">
                      {ing.status === 'have' ? <Check size={13} strokeWidth={3} /> : ing.status === 'missing' ? <ShoppingBasket size={13} /> : <span className="dot" />}
                    </span>
                    <b>{ing.name}</b>
                    <span className="amt">{ing.amount}</span>
                    <span className="ing-tag">{ing.status === 'have' ? '冰箱有' : ing.status === 'staple' ? '常备' : ing.optional ? '可省略' : '要买'}</span>
                  </li>
                ))}
              </ul>
              {!ready && <p className="notice warn" style={{ marginTop: 12 }}><CircleAlert size={15} style={{ flexShrink: 0, marginTop: 2 }} />还缺 {recipe.missing.join('、')}。可以先去买，或者回去换一批。</p>}
            </section>

            <section className="card">
              <div className="card-title"><h2>步骤</h2><span className="hint">{recipe.steps.length} 步</span></div>
              <ol className="step-list">{recipe.steps.map((s, i) => <li key={i}><span className="step-n num">{i + 1}</span><p>{s}</p></li>)}</ol>
              {recipe.tips && <p className="tip"><Lightbulb size={15} />{recipe.tips}</p>}
            </section>
          </div>
        </>
      )}

      {cooking && <CookMode recipe={recipe} onClose={() => setCooking(false)} onFinish={() => { setCooking(false); setFinishing(true) }} />}
      {finishing && <CookConfirm recipeId={recipe.id} onClose={() => setFinishing(false)}
        onDone={r => { setFinishing(false); setDone(r); emitDataChanged() }} />}
    </div>
  )
}

// ---------------------------------------------------------- 做菜模式：一步一屏，提到「N 分钟」的步骤可以直接计时
function stepMinutes(text: string): number | null {
  const m = /(\d+(?:\.\d+)?)\s*(?:-|~|～|到)?\s*(?:\d+)?\s*分钟/.exec(text)
  return m ? Math.min(180, parseFloat(m[1])) : null
}

function CookMode({ recipe, onClose, onFinish }: { recipe: Recipe; onClose: () => void; onFinish: () => void }) {
  const [i, setI] = useState(0)
  const last = i === recipe.steps.length - 1
  const step = recipe.steps[i]
  const minutes = useMemo(() => stepMinutes(step), [step])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight' && !last) setI(x => x + 1)
      if (e.key === 'ArrowLeft' && i > 0) setI(x => x - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [i, last, onClose])

  return (
    <div className="cook-mode" role="dialog" aria-modal="true" aria-label={`做 ${recipe.title}`}>
      <div className="cook-top">
        <b>{recipe.title}</b>
        <span className="num">第 {i + 1} / {recipe.steps.length} 步</span>
        <button className="icon-btn" aria-label="退出做菜模式" onClick={onClose}><X size={20} /></button>
      </div>
      <div className="cook-progress"><i style={{ width: `${((i + 1) / recipe.steps.length) * 100}%` }} /></div>
      <div className="cook-stage" key={i}>
        <span className="cook-n num">{i + 1}</span>
        <p>{step}</p>
        {minutes && <StepTimer key={i} minutes={minutes} />}
      </div>
      <div className="cook-nav">
        <button className="btn btn-lg" disabled={i === 0} onClick={() => setI(i - 1)}><ChevronLeft size={18} />上一步</button>
        {last
          ? <button className="btn btn-primary btn-lg" onClick={onFinish}><CircleCheck size={18} />做好了</button>
          : <button className="btn btn-navy btn-lg" onClick={() => setI(i + 1)}>下一步<ChevronRight size={18} /></button>}
      </div>
    </div>
  )
}

function StepTimer({ minutes }: { minutes: number }) {
  const total = Math.round(minutes * 60)
  const [left, setLeft] = useState(total)
  const [running, setRunning] = useState(false)
  const timer = useRef<number>()
  useEffect(() => {
    if (!running) return
    timer.current = window.setInterval(() => setLeft(l => {
      if (l <= 1) { window.clearInterval(timer.current); setRunning(false); return 0 }
      return l - 1
    }), 1000)
    return () => window.clearInterval(timer.current)
  }, [running])
  const mm = String(Math.floor(left / 60)).padStart(2, '0')
  const ss = String(left % 60).padStart(2, '0')
  return (
    <div className={`step-timer ${left === 0 ? 'done' : ''}`}>
      <Timer size={18} />
      <b className="num">{left === 0 ? '时间到' : `${mm}:${ss}`}</b>
      {left > 0 && <button className="btn btn-sm" onClick={() => setRunning(!running)}>{running ? <><Pause size={14} />暂停</> : <><Play size={14} />计时 {minutes} 分钟</>}</button>}
      {left !== total && <button className="icon-btn" aria-label="重新计时" onClick={() => { setRunning(false); setLeft(total) }}><RotateCcw size={15} /></button>}
    </div>
  )
}

// ---------------------------------------------------------- 做好了：确认扣库存与记一餐
function CookConfirm({ recipeId, onClose, onDone }: { recipeId: number; onClose: () => void; onDone: (r: CookResult) => void }) {
  const toast = useToast()
  const [preview, setPreview] = useState<CookPreview | null>(null)
  const [usedUp, setUsedUp] = useState<Record<number, boolean>>({})
  const [eaten, setEaten] = useState(1)
  const [meal, setMeal] = useState('dinner')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get<CookPreview>(`/api/recipes/${recipeId}/cook`).then(p => {
      setPreview(p)
      setUsedUp(Object.fromEntries(p.usage.map(u => [u.item_id, u.used_up])))
      setMeal(p.meal_type)
      setEaten(p.eaten_servings)
    }).catch(e => { toast(e.message); onClose() })
  }, [recipeId, toast, onClose])

  async function submit() {
    setBusy(true)
    try {
      const res = await api.post<CookResult>(`/api/recipes/${recipeId}/cook`, {
        usage: Object.entries(usedUp).map(([id, v]) => ({ item_id: Number(id), used_up: v })),
        eaten_servings: eaten, meal_type: meal,
      })
      onDone(res)
    } catch (e) { toast(e instanceof ApiError ? e.message : '没保存上，再试一次') }
    finally { setBusy(false) }
  }

  const kcal = preview?.recipe.kcal_per_serving
  return (
    <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal cook-confirm" role="dialog" aria-modal="true" aria-label="做好了">
        <div className="modal-head"><h3>做好了，更新一下冰箱</h3><button className="icon-btn" onClick={onClose} aria-label="关闭"><X size={18} /></button></div>
        {!preview ? <div className="skeleton" style={{ height: 180 }} /> : (
          <>
            <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>这些食材用完了吗？Favor 先帮你猜了一下，不对就点一下改。</p>
            {preview.usage.length ? (
              <div className="usage-list">
                {preview.usage.map(u => {
                  const up = usedUp[u.item_id]
                  return (
                    <div className="usage-row" key={u.item_id}>
                      <div className="grow"><b>{u.name}</b><span>这道菜用 {u.amount || '适量'}
                        {u.quantity !== null && ` · 冰箱里 ${formatQty(u.quantity, u.unit)}`}</span></div>
                      <div className="segmented">
                        <button className={up ? 'on' : ''} onClick={() => setUsedUp({ ...usedUp, [u.item_id]: true })}>用完了</button>
                        <button className={!up ? 'on' : ''} onClick={() => setUsedUp({ ...usedUp, [u.item_id]: false })}>
                          {u.remaining !== null && u.remaining > 0 ? `还剩 ${formatQty(u.remaining, u.unit)}` : '还有剩'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : <p className="muted" style={{ fontSize: 13 }}>这道菜没用到冰箱里记录的食材。</p>}

            <div className="eat-row">
              <div><b>你吃了几份？</b><span>{kcal ? `每份约 ${kcal} kcal，会记进今天的饮食` : '会记进今天的饮食（热量按估算）'}</span></div>
              <div className="stepper">
                <button className="icon-btn" aria-label="少一份" disabled={eaten <= 0} onClick={() => setEaten(Math.max(0, eaten - 0.5))}><Minus size={15} /></button>
                <b className="num">{eaten}</b>
                <button className="icon-btn" aria-label="多一份" disabled={eaten >= 8} onClick={() => setEaten(Math.min(8, eaten + 0.5))}><Plus size={15} /></button>
              </div>
            </div>
            {eaten > 0 && (
              <div className="segmented meal-seg">
                {MEAL_SLOTS.map(([k, v]) => <button key={k} className={meal === k ? 'on' : ''} onClick={() => setMeal(k)}>{v}</button>)}
              </div>
            )}
            <div className="modal-foot">
              <button className="btn btn-ghost" onClick={onClose}>再等等</button>
              <button className="btn btn-primary" disabled={busy} onClick={submit}>
                {busy ? <Loader2 size={16} className="spin" /> : <Check size={16} />}确认
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function CookDone({ result }: { result: CookResult }) {
  return (
    <section className="card cook-done">
      <span className="done-mark"><CircleCheck size={34} /></span>
      <h2>{result.title}，做好了</h2>
      <p className="muted">冰箱已经更新{result.record ? '，这一餐也帮你记下了' : ''}。</p>
      <ul className="done-list">
        {result.used.map(u => <li key={u.name}><b>{u.name}</b><span>{u.result}</span></li>)}
        {result.record && <li className="meal"><b>饮食记录</b><span>{result.record.text}</span></li>}
      </ul>
      <div className="done-actions">
        <Link to="/app" className="btn btn-primary">回到今天吃什么</Link>
        <Link to="/app/fridge" className="btn">看看冰箱</Link>
        {result.record && <Link to="/app/health" className="btn btn-ghost">查看健康记录</Link>}
      </div>
    </section>
  )
}

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  Check, CircleAlert, Clock, Flame, Leaf, ListChecks, Loader2, MessageSquareText, Plus, ShoppingBasket, Sparkles, X,
} from 'lucide-react'
import { api, ApiError, type CatalogGroup, type PantryItem, type ParsedItem, type RecipeBrief } from '../lib/api'
import { catMeta, DIFFICULTY, expiryInfo, formatQty } from '../lib/kitchen'
import { emitDataChanged } from '../lib/motion'
import { useToast } from './ui'

// ---------------------------------------------------------- 到期提示
export function ExpiryPill({ daysLeft, estimated }: { daysLeft: number | null; estimated?: boolean }) {
  const { text, tone } = expiryInfo(daysLeft, estimated)
  return <span className={`exp-pill ${tone}`} title={estimated ? '按食材类型估算，可以在冰箱里修改' : undefined}>{text}</span>
}

export function CatDot({ category, size = 30 }: { category: string; size?: number }) {
  const meta = catMeta(category)
  const Icon = meta.icon
  return (
    <span className="cat-dot" style={{ '--c': meta.color, width: size, height: size } as CSSProperties} title={meta.label}>
      <Icon size={Math.round(size * 0.5)} strokeWidth={2} />
    </span>
  )
}

// ---------------------------------------------------------- 加食材：勾选常见 / 说一句话
export function PantryAdder({ existing, onAdded, autoFocus = false }: {
  existing: PantryItem[]; onAdded?: (items: PantryItem[]) => void; autoFocus?: boolean
}) {
  const toast = useToast()
  const [mode, setMode] = useState<'pick' | 'say'>('pick')
  const [groups, setGroups] = useState<CatalogGroup[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<ParsedItem[] | null>(null)
  const [busy, setBusy] = useState(false)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const have = useMemo(() => new Set(existing.map(i => i.name)), [existing])

  useEffect(() => {
    api.get<{ groups: CatalogGroup[] }>('/api/pantry/catalog').then(r => setGroups(r.groups)).catch(() => undefined)
  }, [])
  useEffect(() => { if (autoFocus && mode === 'say') taRef.current?.focus() }, [autoFocus, mode])

  async function add(items: Record<string, unknown>[], source: string) {
    setBusy(true)
    try {
      const res = await api.post<{ items: PantryItem[] }>('/api/pantry', { items, source })
      toast(`放进冰箱了：${res.items.map(i => i.name).join('、')}`)
      setPicked([]); setText(''); setParsed(null)
      emitDataChanged()
      onAdded?.(res.items)
    } catch (e) { toast(e instanceof ApiError ? e.message : '没加上，再试一次') }
    finally { setBusy(false) }
  }

  async function parse() {
    if (!text.trim()) return
    setBusy(true)
    try {
      const res = await api.post<{ items: ParsedItem[] }>('/api/pantry/parse', { text })
      if (!res.items.length) toast('没认出食材，换个说法试试，比如「鸡蛋、番茄、半颗洋葱」')
      setParsed(res.items)
    } catch (e) { toast(e instanceof ApiError ? e.message : '识别失败') }
    finally { setBusy(false) }
  }

  const toggle = (name: string) => setPicked(p => (p.includes(name) ? p.filter(n => n !== name) : [...p, name]))

  return (
    <div className="adder">
      <div className="segmented adder-tabs">
        <button className={mode === 'pick' ? 'on' : ''} onClick={() => setMode('pick')}><ListChecks size={14} />勾选常见食材</button>
        <button className={mode === 'say' ? 'on' : ''} onClick={() => setMode('say')}><MessageSquareText size={14} />说一句话</button>
      </div>

      {mode === 'pick' && (
        <>
          <div className="pick-groups">
            {groups.map(g => (
              <div className="pick-group" key={g.category}>
                <span className="pick-label" style={{ '--c': catMeta(g.category).color } as CSSProperties}>{g.label}</span>
                <div className="pick-chips">
                  {g.items.map(name => {
                    const on = picked.includes(name)
                    const owned = have.has(name)
                    return (
                      <button key={name} className={`chip ${on ? 'on' : ''} ${owned ? 'owned' : ''}`} onClick={() => toggle(name)}
                        title={owned ? '冰箱里已经有了，再选会合并成一条' : undefined}>
                        {on && <Check size={12} strokeWidth={3} />}{name}{owned && !on && <span className="owned-dot" />}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
            {!groups.length && <div className="skeleton" style={{ height: 160 }} />}
          </div>
          <div className="adder-foot">
            <span className="muted">数量和保质期可以不填，Favor 会按常识估算。</span>
            <button className="btn btn-primary" disabled={!picked.length || busy}
              onClick={() => add(picked.map(name => ({ name })), 'pick')}>
              {busy ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}放进冰箱{picked.length ? ` ${picked.length} 样` : ''}
            </button>
          </div>
        </>
      )}

      {mode === 'say' && (
        <>
          {!parsed && (
            <>
              <textarea ref={taRef} className="textarea say-box" rows={3} value={text} maxLength={500}
                placeholder="比如：冰箱里有 6 个鸡蛋、两个番茄、半颗洋葱，冷冻还有一斤排骨"
                onChange={e => setText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) parse() }} />
              <div className="adder-foot">
                <span className="muted">说得随意一点也行，识别后你可以先确认再放进去。</span>
                <button className="btn btn-primary" disabled={!text.trim() || busy} onClick={parse}>
                  {busy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}识别食材
                </button>
              </div>
            </>
          )}
          {parsed && (
            <>
              <div className="parsed-list">
                {parsed.map((p, i) => (
                  <div className="parsed-row" key={`${p.name}-${i}`}>
                    <CatDot category={p.category} size={28} />
                    <div className="grow"><b>{p.name}</b>
                      <span>{[formatQty(p.quantity, p.unit), p.storage_label, p.category_label].filter(Boolean).join(' · ')}</span></div>
                    <ExpiryPill daysLeft={p.days_left} estimated={p.expires_estimated} />
                    <button className="icon-btn" aria-label={`去掉${p.name}`} onClick={() => setParsed(parsed.filter((_, j) => j !== i))}><X size={15} /></button>
                  </div>
                ))}
                {!parsed.length && <p className="muted" style={{ padding: 8 }}>没有可加入的食材了。</p>}
              </div>
              <div className="adder-foot">
                <button className="btn btn-ghost" onClick={() => setParsed(null)}>重新说</button>
                <button className="btn btn-primary" disabled={!parsed.length || busy}
                  onClick={() => add(parsed.map(p => ({ name: p.name, quantity: p.quantity, unit: p.unit, storage: p.storage, category: p.category })), 'text')}>
                  {busy ? <Loader2 size={16} className="spin" /> : <Check size={16} />}确认放进冰箱 {parsed.length} 样
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------- 菜谱卡片
export function RecipeCard({ r, index = 0, tour }: { r: RecipeBrief; index?: number; tour?: string }) {
  const ready = r.missing.length === 0
  return (
    <Link to={`/app/recipe/${r.id}`} className="card lift recipe-card" data-tour={tour} style={{ '--i': index } as CSSProperties}>
      <div className="recipe-top">
        <span className={`ready-tag ${ready ? 'ok' : 'miss'}`}>
          {ready ? <><Check size={12} strokeWidth={3} />现在就能做</> : <><ShoppingBasket size={12} />还缺 {r.missing.length} 样</>}
        </span>
        {r.uses_expiring.length > 0 && <span className="save-tag"><Leaf size={12} />用掉快过期的</span>}
      </div>
      <h3>{r.title}</h3>
      {r.summary && <p className="recipe-sum">{r.summary}</p>}
      <div className="recipe-meta">
        <span><Clock size={13} />{r.minutes} 分钟</span>
        <span>{DIFFICULTY[r.difficulty] ?? '简单'}</span>
        {r.kcal_per_serving ? <span><Flame size={13} />约 {r.kcal_per_serving} kcal</span> : null}
      </div>
      {!ready && <p className="recipe-miss"><CircleAlert size={13} />缺：{r.missing.join('、')}</p>}
      {ready && r.uses_expiring.length > 0 && <p className="recipe-save"><Leaf size={13} />顺手用掉：{r.uses_expiring.join('、')}</p>}
      {r.fit?.map(f => <p className="recipe-fit" key={f}><Clock size={13} />{f}</p>)}
      {r.stripped?.length ? <p className="recipe-stripped"><Check size={13} />已去掉你不吃的{r.stripped.join('、')}</p> : null}
    </Link>
  )
}

export function RecipeSkeletons() {
  return (
    <div className="recipe-grid">
      {[0, 1, 2].map(i => <div key={i} className="skeleton recipe-skel" />)}
    </div>
  )
}

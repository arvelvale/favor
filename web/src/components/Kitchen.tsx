import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  Camera, Check, CircleAlert, Clock, Flame, ImageIcon, Info, Leaf, ListChecks, Loader2, MessageSquareText, Plus,
  ShoppingBasket, Sparkles, ThumbsDown, X,
} from 'lucide-react'
import { api, ApiError, type CatalogGroup, type DislikeReason, type PantryItem, type ParsedItem, type RecipeBrief } from '../lib/api'
import { catMeta, DIFFICULTY, expiryInfo, formatQty } from '../lib/kitchen'
import { emitDataChanged } from '../lib/motion'
import { useToast } from './ui'
import { compressImage } from '../lib/image'
import { useAuth } from '../App'

type PhotoItem = ParsedItem & { sure: boolean }

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

// ---------------------------------------------------------- 加食材：勾选常见 / 说一句话 / 拍一张
export function PantryAdder({ existing, onAdded, autoFocus = false }: {
  existing: PantryItem[]; onAdded?: (items: PantryItem[]) => void; autoFocus?: boolean
}) {
  const toast = useToast()
  const { visionEnabled } = useAuth()
  const [mode, setMode] = useState<'pick' | 'say' | 'photo'>('pick')
  // 拍一张：照片只在浏览器里压缩后发去识别，服务端不保存；识别结果先确认再入库
  const camRef = useRef<HTMLInputElement>(null)
  const albumRef = useRef<HTMLInputElement>(null)
  const [photoUrl, setPhotoUrl] = useState<string | null>(null)
  const [shot, setShot] = useState<{ items: PhotoItem[]; note: string } | null>(null)
  const [checked, setChecked] = useState<Set<number>>(new Set())
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
      setPicked([]); setText(''); setParsed(null); setShot(null); setPhotoUrl(null)
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

  async function onPhoto(file: File | undefined) {
    if (!file) return
    setBusy(true); setShot(null)
    try {
      const url = await compressImage(file)
      setPhotoUrl(url)
      const res = await api.post<{ items: PhotoItem[]; note: string }>('/api/pantry/photo', { image: url })
      setShot(res)
      // 确定的默认勾上，不太确定的默认不勾：宁可少放，也别把认错的东西放进冰箱
      setChecked(new Set(res.items.flatMap((it, i) => (it.sure ? [i] : []))))
    } catch (e) {
      setPhotoUrl(null)
      toast(e instanceof ApiError || e instanceof Error ? e.message : '没认出来，再试一次')
    } finally { setBusy(false) }
  }
  const retake = () => { setShot(null); setPhotoUrl(null); camRef.current?.click() }
  const flip = (i: number) => setChecked(c => { const n = new Set(c); if (n.has(i)) n.delete(i); else n.add(i); return n })

  const toggle = (name: string) => setPicked(p => (p.includes(name) ? p.filter(n => n !== name) : [...p, name]))

  return (
    <div className="adder">
      <div className="segmented adder-tabs">
        <button className={mode === 'pick' ? 'on' : ''} onClick={() => setMode('pick')}><ListChecks size={14} />勾选常见食材</button>
        <button className={mode === 'say' ? 'on' : ''} onClick={() => setMode('say')}><MessageSquareText size={14} />说一句话</button>
        {visionEnabled && (
          // 点这个标签就直接打开相机：拍照 → 确认放进冰箱，一共 3 次点击
          <button className={mode === 'photo' ? 'on' : ''}
            onClick={() => { setMode('photo'); if (!shot && !busy) camRef.current?.click() }}><Camera size={14} />拍一张</button>
        )}
      </div>
      {visionEnabled && <>
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden
          onChange={e => { void onPhoto(e.target.files?.[0]); e.target.value = '' }} />
        <input ref={albumRef} type="file" accept="image/*" hidden
          onChange={e => { void onPhoto(e.target.files?.[0]); e.target.value = '' }} />
      </>}

      {mode === 'photo' && !shot && (
        <div className={`photo-drop ${busy ? 'busy' : ''}`}>
          {photoUrl ? <img src={photoUrl} alt="刚拍的照片" /> : <span className="photo-ico"><Camera size={26} /></span>}
          {busy ? <p className="photo-wait"><Loader2 size={16} className="spin" />正在认照片里的食材…</p> : <>
            <p>打开冰箱拍一张，Favor 帮你认出里面有什么</p>
            <div className="photo-actions">
              <button className="btn btn-primary" onClick={() => camRef.current?.click()}><Camera size={16} />拍一张</button>
              <button className="btn btn-ghost" onClick={() => albumRef.current?.click()}><ImageIcon size={16} />从相册选</button>
            </div>
            <small>照片只用来识别，不会保存。认出来的会先给你确认。</small>
          </>}
        </div>
      )}
      {mode === 'photo' && shot && (
        <>
          <div className="photo-head">
            {photoUrl && <img className="photo-thumb" src={photoUrl} alt="刚拍的照片" />}
            <div className="grow">
              <b>{shot.items.length ? `认出 ${shot.items.length} 样` : '没认出食材'}</b>
              <span>{shot.items.length ? (shot.note || '不太确定的没勾上，看一眼再放进去') : (shot.note || '换个角度、离近一点再拍一张试试')}</span>
            </div>
          </div>
          {shot.items.length > 0 && (
            <div className="parsed-list">
              {shot.items.map((p, i) => (
                <label className={`parsed-row pickable ${checked.has(i) ? 'on' : ''}`} key={`${p.name}-${i}`}>
                  <input type="checkbox" checked={checked.has(i)} onChange={() => flip(i)} />
                  <CatDot category={p.category} size={28} />
                  <div className="grow"><b>{p.name}{!p.sure && <em className="unsure">不太确定</em>}</b>
                    <span>{[formatQty(p.quantity, p.unit), p.storage_label, p.category_label].filter(Boolean).join(' · ')}</span></div>
                  <ExpiryPill daysLeft={p.days_left} estimated={p.expires_estimated} />
                </label>
              ))}
            </div>
          )}
          <div className="adder-foot">
            <button className="btn btn-ghost" onClick={retake} disabled={busy}><Camera size={15} />重拍</button>
            <button className="btn btn-primary" disabled={!checked.size || busy}
              onClick={() => add(shot.items.filter((_, i) => checked.has(i)).map(p => ({ name: p.name, quantity: p.quantity, unit: p.unit, storage: p.storage, category: p.category })), 'photo')}>
              {busy ? <Loader2 size={16} className="spin" /> : <Check size={16} />}放进冰箱 {checked.size} 样
            </button>
          </div>
        </>
      )}

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
const DISLIKE_REASONS: [DislikeReason, string, string][] = [
  ['not_like', '不爱吃', '以后不再推荐这道'],
  ['too_hard', '太麻烦', '排后面，多推省事的'],
  ['recent', '最近吃过', '这几天先不推'],
]

/** 「不想吃」：选一个原因，Favor 记下来调整以后的推荐（第 5 期）。 */
export function DislikeMenu({ onPick, compact = false }: { onPick: (reason: DislikeReason) => void; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  return (
    <div className={`dislike ${compact ? 'compact' : ''}`} ref={ref}>
      <button type="button" className={compact ? 'icon-btn dislike-btn' : 'btn btn-ghost'} aria-label="不想吃这道" title="不想吃这道"
        aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ThumbsDown size={compact ? 15 : 16} />{!compact && '不想吃'}
      </button>
      {open && (
        <div className="dislike-menu" role="menu">
          <span className="dislike-q">为什么不想吃？</span>
          {DISLIKE_REASONS.map(([k, label, hint]) => (
            <button type="button" role="menuitem" key={k} onClick={() => { setOpen(false); onPick(k) }}>
              <b>{label}</b><small>{hint}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function RecipeCard({ r, index = 0, tour, onDislike }: {
  r: RecipeBrief; index?: number; tour?: string; onDislike?: (r: RecipeBrief, reason: DislikeReason) => void
}) {
  const ready = r.missing.length === 0
  return (
    // 「不想吃」按钮放在链接外面（链接里不能再嵌按钮），用定位叠在卡片右上角
    <div className="recipe-card-wrap" style={{ '--i': index } as CSSProperties}>
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
        {r.fit?.map(f => <p className="recipe-fit" key={f}><Info size={13} />{f}</p>)}
        {r.stripped?.length ? <p className="recipe-stripped"><Check size={13} />已去掉你不吃的{r.stripped.join('、')}</p> : null}
      </Link>
      {onDislike && <DislikeMenu compact onPick={reason => onDislike(r, reason)} />}
    </div>
  )
}

export function RecipeSkeletons() {
  return (
    <div className="recipe-grid">
      {[0, 1, 2].map(i => <div key={i} className="skeleton recipe-skel" />)}
    </div>
  )
}

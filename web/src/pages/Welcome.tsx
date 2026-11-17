import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, ChevronRight, Loader2, Minus, Plus, Sparkles, X } from 'lucide-react'
import { api, ApiError, type ProfilePayload } from '../lib/api'
import {
  adjustments, ALLERGIES, DEFAULT_PREFS, DIET, DISLIKES, EQUIPMENT, FAMILY_FLAGS, GOALS, HOUSEHOLD, MINUTES,
  QUESTION_META, setPrefsCache, SKILL, SPICE, STAPLES, type Option, type Prefs, type PrefsState, type QuestionKey,
} from '../lib/prefs'
import { useAuth } from '../App'
import { useToast } from '../components/ui'
import Logo from '../components/Logo'

const ORDER: QuestionKey[] = ['household', 'skill', 'minutes', 'equipment', 'staples', 'taste', 'goals', 'body']
// 每题对应的偏好字段：跳过这题时把这些字段恢复成默认值
const FIELDS: Record<QuestionKey, (keyof Prefs)[]> = {
  household: ['household', 'family_size', 'family_flags'], skill: ['skill'], minutes: ['minutes'],
  equipment: ['equipment'], staples: ['staples'], taste: ['spice', 'diet', 'dislikes'], goals: ['goals'], body: [],
}

type Body = { sex: string; birth_year: string; height_cm: string; weight_kg: string; activity_level: string; goal: string }
const EMPTY_BODY: Body = { sex: '', birth_year: '', height_cm: '', weight_kg: '', activity_level: '', goal: '' }

function OptionCard<T>({ o, on, onClick, multi }: { o: Option<T>; on: boolean; onClick: () => void; multi?: boolean }) {
  const Icon = o.icon
  return (
    <button type="button" className={`q-option ${on ? 'on' : ''}`} aria-pressed={on} onClick={onClick}
      style={{ '--c': o.color ?? 'var(--brand)' } as CSSProperties}>
      {Icon && <span className="q-ico"><Icon size={20} strokeWidth={1.9} /></span>}
      <span className="q-text"><b>{o.label}</b>{o.sub && <small>{o.sub}</small>}</span>
      <span className={`q-tick ${multi ? 'square' : ''}`}>{on && <Check size={13} strokeWidth={3} />}</span>
    </button>
  )
}

function Chips({ options, selected, onToggle, tone, custom }: {
  options: string[]; selected: string[]; onToggle: (v: string) => void; tone?: 'danger'; custom?: string
}) {
  const [text, setText] = useState('')
  const all = [...options, ...selected.filter(s => !options.includes(s))]
  const add = () => {
    const v = text.trim().slice(0, 10)
    if (v && !selected.includes(v)) onToggle(v)
    setText('')
  }
  return (
    <div className={`q-chips ${tone ?? ''}`}>
      {all.map(v => (
        <button type="button" key={v} className={`q-chip ${selected.includes(v) ? 'on' : ''}`} aria-pressed={selected.includes(v)} onClick={() => onToggle(v)}>
          {selected.includes(v) && <Check size={12} strokeWidth={3} />}{v}
        </button>
      ))}
      {custom && (
        <span className="q-chip-add">
          <input value={text} maxLength={10} placeholder={custom} onChange={e => setText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); add() } }} />
          <button type="button" aria-label="添加" onClick={add} disabled={!text.trim()}><Plus size={14} /></button>
        </span>
      )}
    </div>
  )
}

const toggle = (list: string[], v: string) => list.includes(v) ? list.filter(x => x !== v) : [...list, v]

export default function WelcomePage() {
  const { user, setUser } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const editKey = (ORDER as string[]).includes(params.get('q') ?? '') ? params.get('q') as QuestionKey : null

  const [ready, setReady] = useState(false)
  const [p, setP] = useState<Prefs>(DEFAULT_PREFS)
  const [allergies, setAllergies] = useState<string[]>([])
  const [body, setBody] = useState<Body>(EMPTY_BODY)
  const [options, setOptions] = useState<ProfilePayload['options'] | null>(null)
  const [skipped, setSkipped] = useState<QuestionKey[]>([])
  const [step, setStep] = useState(0)
  const [fromSummary, setFromSummary] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState<PrefsState | null>(null)

  const flow = useMemo(() => ORDER.filter(q => q !== 'body' || p.goals.includes('healthy')), [p.goals])
  const q: QuestionKey | null = editKey ?? flow[step] ?? null   // null = 总结页

  useEffect(() => {
    Promise.all([api.get<PrefsState>('/api/preferences'), api.get<ProfilePayload>('/api/profile')]).then(([s, pr]) => {
      setP(s.prefs); setAllergies(s.allergies); setSkipped(s.status === 'new' ? [] : s.skipped)
      setOptions(pr.options)
      const b = { ...EMPTY_BODY }
      for (const k of Object.keys(b) as (keyof Body)[]) b[k] = pr.profile[k] == null ? '' : String(pr.profile[k])
      setBody(b)
      setReady(true)
    }).catch(e => toast(e.message))
  }, [toast])

  const update = (changes: Partial<Prefs>, key: QuestionKey) => {
    setP(prev => ({ ...prev, ...changes }))
    setSkipped(prev => prev.filter(x => x !== key))
  }

  function bodyPayload(b: Body) {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(b)) if (v !== '') out[k] = ['birth_year', 'height_cm', 'weight_kg'].includes(k) ? Number(v) : v
    return out
  }

  type Snapshot = { p: Prefs; allergies: string[]; skipped: QuestionKey[]; body: Body }

  // 传入快照而不是读 state：「跳过这题」会在同一次点击里改值并保存，state 还没更新
  async function save(status?: 'done' | 'skipped', s: Snapshot = { p, allergies, skipped, body }) {
    setSaving(true); setErr('')
    try {
      const payload: Record<string, unknown> = { prefs: s.p, allergies: s.allergies, skipped: s.skipped }
      if (status) payload.status = status
      if (s.p.goals.includes('healthy') && !s.skipped.includes('body')) payload.profile = bodyPayload(s.body)
      const res = await api.put<PrefsState>('/api/preferences', payload)
      setPrefsCache(res)
      if (user && user.prefs_status !== res.status) setUser({ ...user, prefs_status: res.status })
      return res
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : '保存失败，再试一次吧')
      return null
    } finally { setSaving(false) }
  }

  async function next(s?: Snapshot) {
    if (editKey) {
      if (await save(undefined, s)) { toast('已更新，下次推荐就会按新的来'); navigate('/app/me') }
      return
    }
    const steps = s ? ORDER.filter(k => k !== 'body' || s.p.goals.includes('healthy')) : flow
    if (fromSummary || step >= steps.length - 1) {
      const res = await save('done', s)
      if (res) { setResult(res); setFromSummary(false); setStep(steps.length) }
      return
    }
    setStep(step + 1)
  }

  /** 跳过这题：这题的字段恢复默认值，记为「跳过」（之后在合适的时机再问）。 */
  function skipThis() {
    if (!q) return
    const reset: Partial<Prefs> = {}
    for (const f of FIELDS[q]) (reset as Record<string, unknown>)[f] = DEFAULT_PREFS[f]
    const snap: Snapshot = {
      p: { ...p, ...reset }, allergies: q === 'taste' ? [] : allergies,
      skipped: skipped.includes(q) ? skipped : [...skipped, q], body: q === 'body' ? EMPTY_BODY : body,
    }
    setP(snap.p); setAllergies(snap.allergies); setSkipped(snap.skipped); setBody(snap.body)
    void next(snap)
  }

  async function skipAll() {
    setSaving(true)
    try {
      const res = await api.put<PrefsState>('/api/preferences', { status: 'skipped', skipped: ORDER })
      setPrefsCache(res)
      if (user) setUser({ ...user, prefs_status: 'skipped' })
      toast('先按默认来，随时可以在「我的」里改')
      navigate('/app', { replace: true })
    } catch (e) { toast(e instanceof ApiError ? e.message : '没跳过去，再试一次吧') }
    finally { setSaving(false) }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (e.key === 'Enter' && q && !saving && tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'BUTTON') void next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!ready) return <div className="loading-screen">正在加载…</div>

  const meta = q ? QUESTION_META[q] : null
  const index = q ? flow.indexOf(q) : flow.length

  let content: ReactNode = null
  if (q === 'household') {
    content = <>
      <div className="q-options">
        {HOUSEHOLD.map(o => <OptionCard key={o.value} o={o} on={p.household === o.value} onClick={() => update({ household: o.value }, q)} />)}
      </div>
      {p.household === 'family' && (
        <div className="q-sub">
          <div className="q-row">
            <span>家里几口人</span>
            <div className="stepper">
              <button type="button" aria-label="少一个" onClick={() => update({ family_size: Math.max(2, p.family_size - 1) }, q)}><Minus size={15} /></button>
              <b className="num">{p.family_size}</b>
              <button type="button" aria-label="多一个" onClick={() => update({ family_size: Math.min(10, p.family_size + 1) }, q)}><Plus size={15} /></button>
            </div>
          </div>
          <div className="q-row">
            <span>需要照顾的</span>
            <div className="q-chips">
              {FAMILY_FLAGS.map(f => (
                <button type="button" key={f.value} className={`q-chip ${p.family_flags.includes(f.value) ? 'on' : ''}`}
                  aria-pressed={p.family_flags.includes(f.value)} onClick={() => update({ family_flags: toggle(p.family_flags, f.value) }, q)}>
                  {p.family_flags.includes(f.value) && <Check size={12} strokeWidth={3} />}{f.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  } else if (q === 'skill') {
    content = <div className="q-options">{SKILL.map(o => <OptionCard key={o.value} o={o} on={p.skill === o.value} onClick={() => update({ skill: o.value }, q)} />)}</div>
  } else if (q === 'minutes') {
    content = <div className="q-options">{MINUTES.map(o => <OptionCard key={o.value} o={o} on={p.minutes === o.value} onClick={() => update({ minutes: o.value }, q)} />)}</div>
  } else if (q === 'equipment') {
    const pick = (v: string) => {
      // 「只有一个小电锅」和其他厨具互斥
      let eq = v === 'mini_pot' ? ['mini_pot'] : toggle(p.equipment.filter(e => e !== 'mini_pot'), v)
      if (!eq.length) eq = [v]
      update({ equipment: eq }, q)
    }
    content = <div className="q-options grid2">{EQUIPMENT.map(o => <OptionCard key={o.value} o={o} multi on={p.equipment.includes(o.value)} onClick={() => pick(o.value)} />)}</div>
  } else if (q === 'staples') {
    content = <Chips options={STAPLES} selected={p.staples} custom="其他调料" onToggle={v => update({ staples: toggle(p.staples, v) }, q)} />
  } else if (q === 'taste') {
    content = <div className="q-taste">
      <div className="q-group"><h3>辣度</h3>
        <div className="segmented wide">
          {SPICE.map(o => <button type="button" key={o.value} className={p.spice === o.value ? 'on' : ''} onClick={() => update({ spice: o.value }, q)}>{o.label}</button>)}
        </div>
      </div>
      <div className="q-group"><h3>饮食方式</h3>
        <div className="q-chips">
          {DIET.map(o => (
            <button type="button" key={o.value} className={`q-chip ${p.diet === o.value ? 'on' : ''}`} aria-pressed={p.diet === o.value} onClick={() => update({ diet: o.value }, q)}>
              {p.diet === o.value && <Check size={12} strokeWidth={3} />}{o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="q-group"><h3>不吃的 <small>可省略的会直接去掉，必需的整道菜不推</small></h3>
        <Chips options={DISLIKES} selected={p.dislikes} custom="其他" onToggle={v => update({ dislikes: toggle(p.dislikes, v) }, q)} />
      </div>
      <div className="q-group"><h3 className="danger">过敏 <small>含这些的菜一律不推，由程序检查，不只靠 AI</small></h3>
        <Chips tone="danger" options={ALLERGIES} selected={allergies} custom="其他过敏原"
          onToggle={v => { setAllergies(toggle(allergies, v)); setSkipped(s => s.filter(x => x !== 'taste')) }} />
      </div>
    </div>
  } else if (q === 'goals') {
    content = <div className="q-options grid2">{GOALS.map(o => <OptionCard key={o.value} o={o} multi on={p.goals.includes(o.value)}
      onClick={() => update({ goals: toggle(p.goals, o.value).length ? toggle(p.goals, o.value) : [o.value] }, q)} />)}</div>
  } else if (q === 'body' && options) {
    const set = (k: keyof Body) => (e: { target: { value: string } }) => { setBody({ ...body, [k]: e.target.value }); setSkipped(s => s.filter(x => x !== 'body')) }
    content = <div className="q-body">
      <div className="q-group"><h3>目标</h3>
        <div className="segmented wide">
          {(['lose', 'maintain', 'gain'] as const).map(g => <button type="button" key={g} className={body.goal === g ? 'on' : ''}
            onClick={() => set('goal')({ target: { value: g } })}>{options.goals[g]}</button>)}
        </div>
      </div>
      <div className="q-body-grid">
        <label className="field"><span>性别</span>
          <select className="select" value={body.sex} onChange={set('sex')}><option value="">不填</option><option value="male">男</option><option value="female">女</option></select>
        </label>
        <label className="field"><span>出生年份</span><input className="input" inputMode="numeric" value={body.birth_year} onChange={set('birth_year')} placeholder="如 2003" /></label>
        <label className="field"><span>身高 cm</span><input className="input" inputMode="decimal" value={body.height_cm} onChange={set('height_cm')} placeholder="如 170" /></label>
        <label className="field"><span>体重 kg</span><input className="input" inputMode="decimal" value={body.weight_kg} onChange={set('weight_kg')} placeholder="如 60" /></label>
        <label className="field span2"><span>平时活动量</span>
          <select className="select" value={body.activity_level} onChange={set('activity_level')}>
            <option value="">不填</option>
            {Object.entries(options.activity_levels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <p className="q-note">都可以不填。填全了才能算出每天的热量目标，以后也能在「健康 · 档案」里改。</p>
    </div>
  }

  return (
    <div className="welcome">
      <header className="welcome-top">
        <Logo size={34} subtitle="AI 厨房搭子" />
        {editKey ? (
          <button className="btn btn-ghost" onClick={() => navigate('/app/me')}><X size={16} />不改了</button>
        ) : q && (
          <button className="btn btn-ghost" onClick={skipAll} disabled={saving}>跳过问卷，先用默认</button>
        )}
      </header>

      {!editKey && q && (
        <div className="q-progress" aria-label={`第 ${index + 1} 题，共 ${flow.length} 题`}>
          {flow.map((k, i) => <span key={k} className={i < index ? 'done' : i === index ? 'now' : ''} />)}
        </div>
      )}

      <main className="welcome-main">
        {q && meta ? (
          <section className="q-card" key={q}>
            <div className="q-head" style={{ '--c': meta.color } as CSSProperties}>
              <span className="q-badge"><meta.icon size={18} strokeWidth={2} /></span>
              {!editKey && <span className="q-count num">{index + 1} / {flow.length}</span>}
            </div>
            <h1>{meta.title}</h1>
            <p className="q-hint">{meta.hint}</p>
            <div className="q-content">{content}</div>
            {err && <p className="q-err">{err}</p>}
            <footer className="q-foot">
              {!editKey && index > 0 && !fromSummary
                ? <button className="btn btn-ghost" onClick={() => setStep(step - 1)} disabled={saving}><ArrowLeft size={16} />上一题</button>
                : <span />}
              <div className="q-foot-right">
                {!editKey && <button className="btn btn-ghost" onClick={skipThis} disabled={saving}>跳过这题</button>}
                <button className="btn btn-primary btn-lg" onClick={() => next()} disabled={saving}>
                  {saving ? <Loader2 size={17} className="spin" /> : null}
                  {editKey ? '保存' : fromSummary || index === flow.length - 1 ? '完成' : '下一题'}
                  {!saving && !editKey && <ArrowRight size={17} />}
                </button>
              </div>
            </footer>
          </section>
        ) : result && (
          <section className="q-card q-summary">
            <div className="q-head" style={{ '--c': 'var(--brand)' } as CSSProperties}>
              <span className="q-badge"><Sparkles size={18} /></span>
            </div>
            <h1>根据你的回答，我们已经……</h1>
            <p className="q-hint">点任意一条可以改。以后在「我的」里也能随时改。</p>
            <ul className="adjust-list">
              {adjustments(result, true).map(a => (
                <li key={a.q}>
                  <button type="button" onClick={() => { setFromSummary(true); setStep(flow.indexOf(a.q)) }} style={{ '--c': a.color } as CSSProperties}>
                    <span className="adj-ico"><a.icon size={17} /></span>
                    <span className="adj-text">{a.text}{a.defaulted && <em>默认</em>}</span>
                    <ChevronRight size={16} className="adj-go" />
                  </button>
                </li>
              ))}
            </ul>
            <footer className="q-foot">
              <span />
              <button className="btn btn-primary btn-lg" onClick={() => navigate('/app', { replace: true })}>去看看冰箱<ArrowRight size={17} /></button>
            </footer>
          </section>
        )}
      </main>
    </div>
  )
}

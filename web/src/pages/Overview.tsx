import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  Beef, Check, ChevronLeft, ChevronRight, ClipboardList, Droplets, Dumbbell, Flame, Lightbulb, Sparkles, Target, Trash2, Wheat,
} from 'lucide-react'
import { api, ApiError, type DayPoint, type HealthRecord, type Kind, type ProfilePayload, type Summary } from '../lib/api'
import { dayLabel, KIND_META, pct, shiftDay, todayISO } from '../lib/metrics'
import { useDataChanged } from '../lib/motion'
import { buildInsights } from '../lib/insights'
import { AnimatedNumber, MetricIcon, ProgressBar, Ring, useToast } from '../components/ui'
import { BarChart, Sparkline, type Point } from '../components/Charts'
import RecordModal from '../components/RecordModal'
import RecordItem from '../components/RecordItem'
import { askFavor } from '../components/Workbench'

type WeekMetric = 'calories_in' | 'water_ml' | 'sleep_hours' | 'exercise_min'
const WEEK_METRICS: { key: WeekMetric; label: string; kind: Kind; unit: string; target: keyof Summary['targets'] }[] = [
  { key: 'calories_in', label: '热量', kind: 'meal', unit: 'kcal', target: 'calories' },
  { key: 'water_ml', label: '饮水', kind: 'water', unit: 'ml', target: 'water_ml' },
  { key: 'sleep_hours', label: '睡眠', kind: 'sleep', unit: '小时', target: 'sleep_hours' },
  { key: 'exercise_min', label: '运动', kind: 'exercise', unit: '分钟', target: 'exercise_min' },
]

export default function OverviewPage() {
  const toast = useToast()
  const [day, setDay] = useState(todayISO())
  const [data, setData] = useState<Summary | null>(null)
  const [month, setMonth] = useState<DayPoint[]>([])
  const [profile, setProfile] = useState<ProfilePayload | null>(null)
  const [modal, setModal] = useState<Kind | null>(null)
  const [habitName, setHabitName] = useState('')
  const [metric, setMetric] = useState<WeekMetric>('calories_in')
  const isToday = day === todayISO()

  const load = useCallback(() => {
    api.get<Summary>(`/api/summary?day=${day}`).then(setData).catch(e => toast(e.message))
    api.get<{ series: DayPoint[] }>('/api/trends?days=30').then(r => setMonth(r.series)).catch(() => undefined)
    api.get<ProfilePayload>('/api/profile').then(setProfile).catch(() => undefined)
  }, [day, toast])
  useEffect(load, [load])
  useDataChanged(load)

  const week = useMemo(() => month.slice(-7), [month])
  const insights = useMemo(() => (data && isToday ? buildInsights(data, week) : []), [data, week, isToday])

  async function quickLog(kind: Kind, payload: Record<string, unknown>) {
    try {
      const res = await api.post<{ record: HealthRecord }>('/api/records', { kind, data: payload, at: isToday ? undefined : `${day}T12:00` })
      toast(`已记录：${res.record.text}`)
      load()
    } catch (e) { toast(e instanceof ApiError ? e.message : '记录失败') }
  }
  async function remove(r: HealthRecord) {
    if (!confirm(`删除「${r.text}」？`)) return
    await api.del(`/api/records/${r.id}`).then(() => { toast('已删除'); load() }).catch(e => toast(e.message))
  }
  async function toggleHabit(id: number, done: boolean) {
    await api.post(`/api/habits/${id}/check`, { day, done }).then(load).catch(e => toast(e.message))
  }
  async function addHabit() {
    if (!habitName.trim()) return
    await api.post('/api/habits', { name: habitName.trim() }).then(() => { setHabitName(''); load() }).catch(e => toast(e.message))
  }
  async function archiveHabit(id: number, name: string) {
    if (!confirm(`不再追踪「${name}」？打卡历史会保留。`)) return
    await api.del(`/api/habits/${id}`).then(load).catch(e => toast(e.message))
  }

  if (!data) {
    return (
      <div className="wb-page">
        <div className="ov">
          <div className="skeleton span-7" style={{ height: 240 }} /><div className="skeleton span-5" style={{ height: 240 }} />
          {[0, 1, 2, 3].map(i => <div key={i} className="skeleton span-3" style={{ height: 150 }} />)}
        </div>
      </div>
    )
  }

  const { totals: t, targets: g } = data
  const budget = g.calories + t.exercise_kcal
  const remaining = data.remaining_calories
  const proteinTarget = g.protein_g ?? Math.round(g.calories * 0.2 / 4)
  const carbsTarget = Math.round(g.calories * 0.5 / 4)
  const fatTarget = Math.round(g.calories * 0.275 / 9)
  const weight = t.weight_kg ?? t.last_weight?.kg ?? null
  const spark = (key: keyof DayPoint) => week.map(d => (d[key] as number) || null)
  const wm = WEEK_METRICS.find(m => m.key === metric)!
  const weekPoints: Point[] = week.map(d => ({ day: d.day, value: (d[metric] as number) || null }))

  // 体重目标进度：30 天内第一次记录 → 当前 → 目标
  const weights = month.map(d => d.weight_kg).filter((v): v is number => !!v)
  const startW = weights[0] ?? weight
  const targetW = profile?.profile.target_weight_kg ?? null
  const goalPct = startW && weight && targetW && startW !== targetW
    ? Math.max(0, Math.min(100, ((startW - weight) / (startW - targetW)) * 100)) : 0

  return (
    <div className="wb-page">
      <div className="toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button className="icon-btn" aria-label="前一天" onClick={() => setDay(shiftDay(day, -1))}><ChevronLeft size={17} /></button>
          <b style={{ minWidth: 92, textAlign: 'center', fontWeight: 500 }}>{dayLabel(day)}</b>
          <button className="icon-btn" aria-label="后一天" disabled={isToday} onClick={() => setDay(shiftDay(day, 1))}><ChevronRight size={17} /></button>
          {!isToday && <button className="btn btn-sm btn-ghost" onClick={() => setDay(todayISO())}>回到今天</button>}
        </div>
        {!g.complete && (
          <Link to="/app/profile" className="tag brand" style={{ padding: '6px 12px' }}>
            <Target size={13} />补充{g.missing.join('、')}，目标会更准
          </Link>
        )}
      </div>

      <div className="ov stagger">
        <section className="card hero-card span-7">
          <Ring value={pct(t.calories_in, budget)}>
            <span>{remaining >= 0 ? '还可摄入' : '已超出'}</span>
            <b className="num"><AnimatedNumber value={Math.abs(remaining)} /></b>
            <span>kcal</span>
          </Ring>
          <div>
            <div className="hero-stats">
              <div className="hero-stat"><span><Flame size={12} />已摄入</span><b className="num"><AnimatedNumber value={t.calories_in} /></b><small>kcal</small></div>
              <div className="hero-stat"><span><Dumbbell size={12} />运动消耗</span><b className="num"><AnimatedNumber value={t.exercise_kcal} /></b><small>kcal</small></div>
              <div className="hero-stat"><span><Target size={12} />每日目标</span><b className="num"><AnimatedNumber value={g.calories} /></b><small>kcal</small></div>
            </div>
            <div className="macro">
              {[
                { label: '蛋白质', icon: Beef, v: t.protein, goal: proteinTarget, c: 'var(--meal)' },
                { label: '碳水', icon: Wheat, v: t.carbs, goal: carbsTarget, c: 'var(--weight)' },
                { label: '脂肪', icon: Droplets, v: t.fat, goal: fatTarget, c: 'var(--mood)' },
              ].map(m => (
                <div key={m.label}>
                  <div className="macro-row"><span><m.icon size={12} style={{ verticalAlign: -1, marginRight: 4, color: m.c }} />{m.label}</span><span className="num">{Math.round(m.v)} / {m.goal} g</span></div>
                  <ProgressBar value={pct(m.v, m.goal)} color={m.c} />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="card insight-card span-5">
          <div className="card-title"><h2><Sparkles size={16} color="#ffb08a" />Favor 今日建议</h2><span className="hint">根据你的数据</span></div>
          <div className="insight-list">
            {!isToday && <div className="insight"><Lightbulb size={16} /><span>正在查看{dayLabel(day)}的数据，建议只针对今天生成。</span></div>}
            {isToday && insights.length === 0 && (
              <div className="insight"><Lightbulb size={16} color="#ffb08a" /><div><b>今天节奏不错</b><span>继续记录，Favor 会在发现问题时提醒你。</span></div></div>
            )}
            {insights.map(i => {
              const content = <>
                <span className="metric-icon sm" style={{ '--c': i.tone === 'good' ? '#5fd18b' : i.tone === 'warn' ? '#ff9a6b' : '#ffc94d' } as CSSProperties}>
                  {(() => { const I = KIND_META[i.kind].icon; return <I size={14} /> })()}
                </span>
                <div style={{ minWidth: 0 }}><b>{i.title}</b><span>{i.text}</span></div>
                {i.ask && <ChevronRight size={16} className="go" />}
              </>
              return i.ask
                ? <button key={i.title} className="insight" onClick={() => askFavor(i.ask)} title="交给 Favor">{content}</button>
                : <div key={i.title} className="insight">{content}</div>
            })}
          </div>
        </section>

        <Kpi kind="water" value={t.water_ml} target={g.water_ml} unit="ml" spark={spark('water_ml')}
          sub={t.water_ml >= g.water_ml ? '今天喝够了' : `还差 ${g.water_ml - t.water_ml} ml`}
          quick={[['+250', () => quickLog('water', { ml: 250 })], ['+500', () => quickLog('water', { ml: 500 })]]} />
        <Kpi kind="exercise" value={t.exercise_min} target={g.exercise_min} unit="分钟" spark={spark('exercise_min')}
          sub={`消耗约 ${t.exercise_kcal} kcal`} quick={[['记录运动', () => setModal('exercise')]]} />
        <Kpi kind="sleep" value={t.sleep_hours} target={g.sleep_hours} unit="小时" decimals={1} spark={spark('sleep_hours')}
          sub={t.sleep_hours ? (t.sleep_hours >= 7 ? '睡得挺充足' : '比建议的少一些') : `建议 ${g.sleep_hours} 小时`}
          quick={[['记录睡眠', () => setModal('sleep')]]} />
        <Kpi kind="weight" value={weight ?? 0} unit="kg" decimals={1} spark={spark('weight_kg')} empty={weight === null}
          sub={t.weight_kg ? '今天已称重' : t.last_weight ? `${dayLabel(t.last_weight.day)}的记录` : '还没有体重记录'}
          quick={[['记录体重', () => setModal('weight')]]} />

        <section className="card span-8">
          <div className="card-title">
            <h2><MetricIcon kind={wm.kind} size="sm" />近 7 天{wm.label}</h2>
            <div className="segmented">
              {WEEK_METRICS.map(m => <button key={m.key} className={metric === m.key ? 'on' : ''} onClick={() => setMetric(m.key)}>{m.label}</button>)}
            </div>
          </div>
          <BarChart key={metric} points={weekPoints} color={KIND_META[wm.kind].color} unit={wm.unit}
            target={g[wm.target] as number} format={v => (metric === 'sleep_hours' ? v.toFixed(1) : v.toFixed(0))} />
        </section>

        <section className="card span-4">
          <div className="card-title"><h2>每日习惯</h2><span className="hint">近 7 天打卡</span></div>
          {data.habits.map(h => (
            <div className="habit" key={h.id}>
              <button className={`habit-check ${h.done ? 'on' : ''}`} aria-label={h.done ? '取消打卡' : '打卡'}
                onClick={() => toggleHabit(h.id, !h.done)}>{h.done && <Check size={14} strokeWidth={3} />}</button>
              <span className={`name ${h.done ? 'done' : ''}`}>{h.name}</span>
              <span className="week-count num">{h.week_count}/7</span>
              <button className="icon-btn danger" aria-label="删除习惯" onClick={() => archiveHabit(h.id, h.name)}><Trash2 size={14} /></button>
            </div>
          ))}
          {!data.habits.length && <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>从一个小习惯开始，比如“晚上 11 点前放下手机”。也可以让 Favor 帮你定。</p>}
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input className="input" style={{ height: 36 }} placeholder="新习惯" value={habitName}
              onChange={e => setHabitName(e.target.value)} onKeyDown={e => e.key === 'Enter' && addHabit()} />
            <button className="btn btn-sm" onClick={addHabit} disabled={!habitName.trim()}>添加</button>
          </div>
        </section>

        <section className="card span-8">
          <div className="card-title"><h2>{isToday ? '今天的记录' : '当天记录'}</h2><span className="hint">{data.records.length} 条</span></div>
          {data.records.length ? (
            <div className="timeline">{data.records.map(r => <RecordItem key={r.id} record={r} onDelete={remove} />)}</div>
          ) : (
            <div className="empty"><ClipboardList size={36} /><p>还没有记录。试试在右侧对 Favor 说“早饭吃了两个包子一杯豆浆”。</p></div>
          )}
        </section>

        <section className="card span-4">
          <div className="card-title"><h2><MetricIcon kind="weight" size="sm" />体重目标</h2>
            {data && profile?.bmi && <span className="tag">BMI {profile.bmi}</span>}</div>
          {targetW && weight ? <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <b className="num" style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-.02em' }}><AnimatedNumber value={weight} decimals={1} /></b>
              <span className="muted">kg · 目标 {targetW} kg</span>
            </div>
            <div className="goal-track"><i style={{ width: `${goalPct}%` }} /></div>
            <div className="goal-ends"><span>起点 {startW} kg</span><span>完成 {Math.round(goalPct)}%</span></div>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
              {Math.abs(weight - targetW) < 0.3 ? '已经到达目标体重，接下来以保持为主。' : `距离目标还有 ${Math.abs(weight - targetW).toFixed(1)} kg，每周 0.5 kg 左右的节奏最稳。`}
            </p>
          </> : (
            <div className="empty" style={{ padding: '18px 8px' }}>
              <Target size={32} />
              <p>{weight ? '设置一个目标体重，这里会显示进度。' : '先记录一次体重吧。'}</p>
              <Link to="/app/profile" className="btn btn-sm" style={{ marginTop: 10 }}>去设置</Link>
            </div>
          )}
        </section>
      </div>

      {modal && <RecordModal initialKind={modal} onClose={() => setModal(null)} onSaved={load} />}
    </div>
  )
}

function Kpi({ kind, value, target, unit, sub, quick, spark, decimals = 0, empty = false }: {
  kind: Kind; value: number; target?: number; unit: string; sub: string; quick: [string, () => void][]
  spark: (number | null)[]; decimals?: number; empty?: boolean
}) {
  const color = KIND_META[kind].color
  return (
    <section className="card kpi lift span-3" style={{ '--c': color } as CSSProperties}>
      <div className="top"><span className="label">{KIND_META[kind].label}</span><MetricIcon kind={kind} size="sm" /></div>
      <div className="row">
        <div>
          <div className="value num">{empty ? '—' : <AnimatedNumber value={value} decimals={decimals} />}
            <small>{empty ? '' : unit}{target ? ` / ${target}` : ''}</small></div>
          <div className="sub">{sub}</div>
        </div>
        <Sparkline values={spark} color={color} width={92} height={38} />
      </div>
      {target !== undefined && <ProgressBar value={pct(value, target)} color={color} />}
      <div className="quick">{quick.map(([label, fn]) => <button key={label} onClick={fn}>{label}</button>)}</div>
    </section>
  )
}

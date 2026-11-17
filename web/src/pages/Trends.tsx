import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, type DayPoint, type Kind, type Targets } from '../lib/api'
import { KIND_META } from '../lib/metrics'
import { useDataChanged } from '../lib/motion'
import { BarChart, LineChart, type Point } from '../components/Charts'
import { MetricIcon, useToast } from '../components/ui'

const RANGES = [7, 30, 90]

export default function TrendsPage() {
  const toast = useToast()
  const [days, setDays] = useState(30)
  const [series, setSeries] = useState<DayPoint[]>([])
  const [targets, setTargets] = useState<Targets | null>(null)

  const load = useCallback(() => {
    api.get<{ series: DayPoint[]; targets: Targets }>(`/api/trends?days=${days}`)
      .then(r => { setSeries(r.series); setTargets(r.targets) })
      .catch(e => toast(e.message))
  }, [days, toast])
  useEffect(load, [load])
  useDataChanged(load)

  const stats = useMemo(() => {
    const logged = (key: keyof DayPoint) => series.map(d => d[key] as number | null).filter((v): v is number => !!v)
    const avg = (key: keyof DayPoint) => {
      const v = logged(key)
      return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
    }
    const weights = logged('weight_kg')
    return {
      calories: avg('calories_in'), water: avg('water_ml'), exercise: avg('exercise_min'), sleep: avg('sleep_hours'),
      weightNow: weights.at(-1) ?? null,
      weightDelta: weights.length >= 2 ? weights.at(-1)! - weights[0] : null,
      activeDays: series.filter(d => d.count > 0).length,
      exerciseDays: series.filter(d => d.exercise_min > 0).length,
    }
  }, [series])

  const pts = (key: keyof DayPoint): Point[] => series.map(d => ({ day: d.day, value: (d[key] as number) || null }))

  return (
    <div className="wb-page">
      <div className="toolbar">
        <p>最近 {days} 天，有记录的 {stats.activeDays} 天。平均值只统计有记录的日子。</p>
        <div className="segmented">
          {RANGES.map(r => <button key={r} className={days === r ? 'on' : ''} onClick={() => setDays(r)}>{r} 天</button>)}
        </div>
      </div>

      <div className="stat-row stagger">
        <Stat kind="weight" label="当前体重" value={stats.weightNow?.toFixed(1)} unit="kg"
          foot={stats.weightDelta === null ? '记录两次以上可看变化' : `${stats.weightDelta > 0 ? '上升' : stats.weightDelta < 0 ? '下降' : '持平'} ${Math.abs(stats.weightDelta).toFixed(1)} kg`} />
        <Stat kind="meal" label="日均摄入" value={stats.calories?.toFixed(0)} unit="kcal" foot={targets ? `目标 ${targets.calories} kcal` : ''} />
        <Stat kind="sleep" label="平均睡眠" value={stats.sleep?.toFixed(1)} unit="小时" foot={targets ? `建议 ${targets.sleep_hours} 小时` : ''} />
        <Stat kind="exercise" label="运动天数" value={String(stats.exerciseDays)} unit={`/ ${days} 天`}
          foot={stats.exercise ? `运动日平均 ${stats.exercise.toFixed(0)} 分钟` : '每周 150 分钟是个好目标'} />
      </div>

      <div className="charts stagger" key={days}>
        <ChartCard kind="weight" title="体重" value={stats.weightNow?.toFixed(1)} unit="kg">
          <LineChart points={pts('weight_kg')} color={KIND_META.weight.color} unit="kg" />
        </ChartCard>
        <ChartCard kind="meal" title="热量摄入" value={stats.calories?.toFixed(0)} unit="kcal 日均">
          <BarChart points={pts('calories_in')} color={KIND_META.meal.color} unit="kcal" target={targets?.calories} format={v => v.toFixed(0)} />
        </ChartCard>
        <ChartCard kind="sleep" title="睡眠时长" value={stats.sleep?.toFixed(1)} unit="小时 平均">
          <BarChart points={pts('sleep_hours')} color={KIND_META.sleep.color} unit="小时" target={targets?.sleep_hours} format={v => v.toFixed(1)} />
        </ChartCard>
        <ChartCard kind="water" title="饮水" value={stats.water?.toFixed(0)} unit="ml 日均">
          <BarChart points={pts('water_ml')} color={KIND_META.water.color} unit="ml" target={targets?.water_ml} format={v => v.toFixed(0)} />
        </ChartCard>
        <ChartCard kind="exercise" title="运动时长" value={stats.exercise?.toFixed(0)} unit="分钟 运动日平均">
          <BarChart points={pts('exercise_min')} color={KIND_META.exercise.color} unit="分钟" target={targets?.exercise_min} format={v => v.toFixed(0)} />
        </ChartCard>
        <ChartCard kind="mood" title="心情" value={undefined} unit="1 很糟 · 5 很好">
          <BarChart points={pts('mood')} color={KIND_META.mood.color} unit="/ 5" format={v => v.toFixed(1)} />
        </ChartCard>
      </div>
    </div>
  )
}

function Stat({ kind, label, value, unit, foot }: { kind: Kind; label: string; value?: string; unit: string; foot: string }) {
  return (
    <div className="card stat">
      <div className="label"><MetricIcon kind={kind} size="sm" />{label}</div>
      <div className="value num">{value ?? '—'}{value && <small>{unit}</small>}</div>
      <div className="foot">{foot}</div>
    </div>
  )
}

function ChartCard({ kind, title, value, unit, children }:
  { kind: Kind; title: string; value?: string; unit: string; children: ReactNode }) {
  return (
    <div className="card">
      <div className="chart-head">
        <h2 style={{ fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}><MetricIcon kind={kind} size="sm" />{title}</h2>
        <span className="big num">{value ?? ''}<small>{unit}</small></span>
      </div>
      {children}
    </div>
  )
}

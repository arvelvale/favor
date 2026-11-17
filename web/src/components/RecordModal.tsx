import { useState, type CSSProperties } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api, ApiError, type HealthRecord, type Kind } from '../lib/api'
import { INTENSITIES, KIND_META, KINDS, MEAL_TYPES, MOODS } from '../lib/metrics'
import { Modal, useToast } from './ui'

function nowLocal() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

function defaultMeal() {
  const h = new Date().getHours()
  return h < 10 ? 'breakfast' : h < 15 ? 'lunch' : h < 21 ? 'dinner' : 'snack'
}

export default function RecordModal({ initialKind = 'meal', onClose, onSaved }:
  { initialKind?: Kind; onClose: () => void; onSaved: (r: HealthRecord) => void }) {
  const toast = useToast()
  const [kind, setKind] = useState<Kind>(initialKind)
  const [at, setAt] = useState(nowLocal())
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const [mealType, setMealType] = useState(defaultMeal())
  const [foods, setFoods] = useState([{ name: '', calories: '' }])
  const [ml, setMl] = useState('250')
  const [activity, setActivity] = useState('')
  const [minutes, setMinutes] = useState('30')
  const [intensity, setIntensity] = useState('moderate')
  const [hours, setHours] = useState('7.5')
  const [quality, setQuality] = useState(3)
  const [kg, setKg] = useState('')
  const [score, setScore] = useState(4)
  const [symptoms, setSymptoms] = useState('')
  const [note, setNote] = useState('')

  function payload() {
    switch (kind) {
      case 'meal': return {
        meal_type: mealType, note,
        items: foods.filter(f => f.name.trim()).map(f => ({ name: f.name.trim(), calories: Number(f.calories) || 0 })),
      }
      case 'water': return { ml: Number(ml) }
      case 'exercise': return { activity, minutes: Number(minutes), intensity, note }
      case 'sleep': return { hours: Number(hours), quality, note }
      case 'weight': return { kg: Number(kg) }
      case 'mood': return { score, note, symptoms: symptoms.split(/[,，、\s]+/).filter(Boolean) }
    }
  }

  async function save() {
    setErr('')
    setSaving(true)
    try {
      const res = await api.post<{ record: HealthRecord }>('/api/records', { kind, data: payload(), at })
      toast(`已记录：${res.record.text}`)
      onSaved(res.record)
      onClose()
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="添加记录" onClose={onClose} footer={<>
      <button className="btn btn-ghost" onClick={onClose}>取消</button>
      <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? '保存中…' : '保存'}</button>
    </>}>
      <div className="kind-grid">
        {KINDS.map(k => {
          const M = KIND_META[k]
          return (
            <button key={k} className={`kind-btn ${kind === k ? 'on' : ''}`} style={{ '--c': M.color } as CSSProperties}
              onClick={() => { setKind(k); setErr('') }}>
              <M.icon size={18} color={M.color} />{M.label}
            </button>
          )
        })}
      </div>

      <div className="stack">
        {kind === 'meal' && <>
          <div className="segmented" style={{ alignSelf: 'flex-start' }}>
            {Object.entries(MEAL_TYPES).map(([k, v]) =>
              <button key={k} className={mealType === k ? 'on' : ''} onClick={() => setMealType(k)}>{v}</button>)}
          </div>
          <div className="field">
            <span>吃了什么</span>
            <div className="stack" style={{ gap: 8 }}>
              {foods.map((f, i) => (
                <div className="food-row" key={i}>
                  <input className="input" placeholder="例如 番茄炒蛋" value={f.name}
                    onChange={e => setFoods(foods.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                  <input className="input num" placeholder="热量 kcal" inputMode="numeric" value={f.calories}
                    onChange={e => setFoods(foods.map((x, j) => j === i ? { ...x, calories: e.target.value } : x))} />
                  <button className="icon-btn danger" aria-label="删除这一项" disabled={foods.length === 1}
                    onClick={() => setFoods(foods.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
                </div>
              ))}
              <button className="btn btn-sm btn-ghost" style={{ alignSelf: 'flex-start' }}
                onClick={() => setFoods([...foods, { name: '', calories: '' }])}><Plus size={14} />再加一项</button>
            </div>
            <small>不知道热量？直接告诉 Favor 吃了什么，它会帮你估算。</small>
          </div>
        </>}

        {kind === 'water' && <div className="field">
          <span>喝了多少（ml）</span>
          <div className="quick" style={{ marginBottom: 4 }}>
            {[150, 250, 350, 500].map(v => <button key={v} onClick={() => setMl(String(v))}>{v} ml</button>)}
          </div>
          <input className="input num" inputMode="numeric" value={ml} onChange={e => setMl(e.target.value)} />
        </div>}

        {kind === 'exercise' && <>
          <label className="field"><span>运动项目</span>
            <input className="input" placeholder="跑步、瑜伽、快走…" value={activity} onChange={e => setActivity(e.target.value)} /></label>
          <div className="grid-2">
            <label className="field"><span>时长（分钟）</span>
              <input className="input num" inputMode="numeric" value={minutes} onChange={e => setMinutes(e.target.value)} /></label>
            <div className="field"><span>强度</span>
              <div className="segmented">
                {Object.entries(INTENSITIES).map(([k, v]) =>
                  <button key={k} className={intensity === k ? 'on' : ''} onClick={() => setIntensity(k)}>{v}</button>)}
              </div></div>
          </div>
        </>}

        {kind === 'sleep' && <>
          <label className="field"><span>睡了多久（小时）</span>
            <input className="input num" inputMode="decimal" value={hours} onChange={e => setHours(e.target.value)} /></label>
          <div className="field"><span>睡得怎么样</span>
            <div className="segmented">
              {[1, 2, 3, 4, 5].map(v => <button key={v} className={quality === v ? 'on' : ''} onClick={() => setQuality(v)}>{v}</button>)}
            </div><small>1 很差 · 5 很好</small></div>
        </>}

        {kind === 'weight' && <label className="field"><span>体重（kg）</span>
          <input className="input num" inputMode="decimal" placeholder="例如 62.5" value={kg} onChange={e => setKg(e.target.value)} />
          <small>称重建议固定在早上起床、如厕后。</small></label>}

        {kind === 'mood' && <>
          <div className="field"><span>今天感觉</span>
            <div className="segmented">
              {MOODS.map((m, i) => <button key={m} className={score === i + 1 ? 'on' : ''} onClick={() => setScore(i + 1)}>{m}</button>)}
            </div></div>
          <label className="field"><span>身体不适（可选）</span>
            <input className="input" placeholder="头痛、胃胀…用逗号分隔" value={symptoms} onChange={e => setSymptoms(e.target.value)} /></label>
        </>}

        {['meal', 'exercise', 'sleep', 'mood'].includes(kind) &&
          <label className="field"><span>备注（可选）</span>
            <input className="input" value={note} onChange={e => setNote(e.target.value)} /></label>}

        <label className="field"><span>时间</span>
          <input className="input" type="datetime-local" value={at} max={nowLocal()} onChange={e => setAt(e.target.value)} /></label>
        {err && <p className="error-text">{err}</p>}
      </div>
    </Modal>
  )
}

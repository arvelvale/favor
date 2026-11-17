import { useEffect, useState, type CSSProperties } from 'react'
import { Beef, Flame, LogOut } from 'lucide-react'
import { api, ApiError, type Profile, type ProfilePayload } from '../lib/api'
import { useAuth } from '../App'
import { MetricIcon, useToast } from '../components/ui'

type Form = Record<keyof Profile, string> & { nickname: string }

function toForm(p: Profile, nickname: string): Form {
  const f = {} as Form
  for (const [k, v] of Object.entries(p)) (f as any)[k] = v === null || v === undefined ? '' : String(v)
  f.nickname = nickname
  return f
}

function bmiLabel(bmi: number) {
  // 中国成人标准：<18.5 偏瘦，18.5–23.9 正常，24–27.9 超重，≥28 肥胖
  if (bmi < 18.5) return '偏瘦'
  if (bmi < 24) return '正常范围'
  if (bmi < 28) return '超重'
  return '肥胖'
}

export default function ProfilePage() {
  const { user, setUser, logout } = useAuth()
  const toast = useToast()
  const [data, setData] = useState<ProfilePayload | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get<ProfilePayload>('/api/profile').then(r => { setData(r); setForm(toForm(r.profile, user?.nickname ?? '')) })
      .catch(e => toast(e.message))
  }, [toast, user?.nickname])

  if (!data || !form) return <div className="wb-page"><div className="profile-grid stagger"><div className="skeleton" style={{ height: 520 }} /><div className="skeleton" style={{ height: 320 }} /></div></div>

  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  async function save() {
    setErr('')
    setSaving(true)
    try {
      const payload: Record<string, unknown> = { ...form }
      for (const k of ['birth_year', 'height_cm', 'weight_kg', 'target_weight_kg']) payload[k] = form![k as keyof Form] || null
      const r = await api.put<ProfilePayload>('/api/profile', payload)
      setData(r)
      if (user && form!.nickname.trim()) setUser({ ...user, nickname: form!.nickname.trim() })
      toast('档案已保存，每日目标已更新')
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const t = data.targets
  const { options } = data

  return (
    <div className="wb-page">
      <div className="toolbar">
        <p>Favor 会根据这些信息计算你的每日目标，并在对话里参考你的偏好和忌口。</p>
        <button className="btn btn-ghost mobile-only" onClick={logout}><LogOut size={16} />退出登录</button>
      </div>

      <div className="profile-grid stagger">
        <div className="card stack">
          <p className="section-label">基本信息</p>
          <div className="grid-2">
            <label className="field"><span>昵称</span><input className="input" value={form.nickname} onChange={set('nickname')} /></label>
            <div className="field"><span>性别</span>
              <div className="segmented">
                {[['female', '女'], ['male', '男']].map(([k, v]) =>
                  <button key={k} className={form.sex === k ? 'on' : ''} onClick={() => setForm({ ...form, sex: k })}>{v}</button>)}
              </div></div>
            <label className="field"><span>出生年份</span><input className="input num" inputMode="numeric" placeholder="例如 2003" value={form.birth_year} onChange={set('birth_year')} /></label>
            <label className="field"><span>身高（cm）</span><input className="input num" inputMode="decimal" value={form.height_cm} onChange={set('height_cm')} /></label>
            <label className="field"><span>体重（kg）</span><input className="input num" inputMode="decimal" value={form.weight_kg} onChange={set('weight_kg')} />
              <small>记录体重时会自动同步</small></label>
            <label className="field"><span>目标体重（kg，可选）</span><input className="input num" inputMode="decimal" value={form.target_weight_kg} onChange={set('target_weight_kg')} /></label>
          </div>

          <p className="section-label">生活与目标</p>
          <label className="field"><span>日常活动水平</span>
            <select className="select" value={form.activity_level} onChange={set('activity_level')}>
              <option value="">请选择</option>
              {Object.entries(options.activity_levels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></label>
          <div className="field"><span>当前目标</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {Object.entries(options.goals).map(([k, v]) =>
                <button key={k} className={`chip ${form.goal === k ? 'on' : ''}`} onClick={() => setForm({ ...form, goal: k })}>{v}</button>)}
            </div></div>

          <p className="section-label">饮食与健康</p>
          <label className="field"><span>饮食偏好</span><input className="input" placeholder="例如 不吃辣、偏爱面食、素食" value={form.diet_preferences} onChange={set('diet_preferences')} /></label>
          <label className="field"><span>过敏或忌口</span><input className="input" placeholder="例如 花生、乳糖不耐" value={form.allergies} onChange={set('allergies')} /></label>
          <label className="field"><span>已知健康状况（可选）</span>
            <textarea className="textarea" placeholder="例如 胃不太好、血压偏高。Favor 会在建议时注意，但不会替代医生。" value={form.conditions} onChange={set('conditions')} /></label>

          {err && <p className="error-text">{err}</p>}
          <div><button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? '保存中…' : '保存档案'}</button></div>
        </div>

        <div className="card">
          <div className="card-title"><h2>每日目标</h2>{data.bmi && <span className="tag">BMI {data.bmi} · {bmiLabel(data.bmi)}</span>}</div>
          <div className="target-list">
            <Target icon={<MetricIcon kind="meal" />} label="热量" value={`${t.calories} kcal`} />
            {t.protein_g && <Target icon={<span className="metric-icon" style={{ '--c': 'var(--mood)' } as CSSProperties}><Beef size={17} /></span>} label="蛋白质" value={`${t.protein_g} g`} />}
            <Target icon={<MetricIcon kind="water" />} label="饮水" value={`${t.water_ml} ml`} />
            <Target icon={<MetricIcon kind="exercise" />} label="运动" value={`${t.exercise_min} 分钟`} />
            <Target icon={<MetricIcon kind="sleep" />} label="睡眠" value={`${t.sleep_hours} 小时`} />
          </div>
          {t.complete ? (
            <p className="formula">
              <Flame size={12} style={{ verticalAlign: -1 }} /> 基础代谢 {t.bmr} kcal（Mifflin-St Jeor 公式）× 活动系数 = 日常消耗 {t.tdee} kcal，
              再按目标调整：减脂少吃 15%，增肌多吃 10%。热量目标不会低于基础代谢，也不低于 {form.sex === 'male' ? 1500 : 1200} kcal。
              饮水按 33 ml/kg 估算。这些是通用估算，有慢性病或特殊情况请遵医嘱。
            </p>
          ) : (
            <p className="formula">还缺 {t.missing.join('、')}，目前显示的是通用默认值。也可以直接告诉 Favor，它会帮你填好。</p>
          )}
        </div>
      </div>
    </div>
  )
}

function Target({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="target-item">{icon}<span className="grow">{label}</span><b className="num">{value}</b></div>
  )
}

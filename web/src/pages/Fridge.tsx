import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Check, Pencil, Plus, Refrigerator, Trash2, X } from 'lucide-react'
import { api, ApiError, type PantryItem, type Storage } from '../lib/api'
import { CATEGORY_META, formatQty, isExpiring, STORAGE_META, STORAGES } from '../lib/kitchen'
import { emitDataChanged, useDataChanged } from '../lib/motion'
import { Modal, useToast } from '../components/ui'
import { CatDot, ExpiryPill, PantryAdder } from '../components/Kitchen'
import { TipBanner } from '../components/Onboarding'
import { useAuth } from '../App'

export default function FridgePage() {
  const toast = useToast()
  const { visionEnabled } = useAuth()
  const [params, setParams] = useSearchParams()
  const [items, setItems] = useState<PantryItem[] | null>(null)
  const [adding, setAdding] = useState(params.get('add') === '1')
  const [editing, setEditing] = useState<PantryItem | null>(null)
  const [filter, setFilter] = useState<'all' | Storage>('all')

  const load = useCallback(() => {
    api.get<{ items: PantryItem[] }>('/api/pantry').then(r => setItems(r.items)).catch(e => toast(e.message))
  }, [toast])
  useEffect(load, [load])
  useDataChanged(load)
  useEffect(() => {
    if (params.get('add') === '1') { setAdding(true); setParams({}, { replace: true }) }
  }, [params, setParams])

  async function remove(item: PantryItem, reason: 'used' | 'discarded') {
    try {
      await api.post(`/api/pantry/${item.id}/remove`, { reason })
      toast(reason === 'used' ? `${item.name} 用完了` : `${item.name} 已移出冰箱`)
      emitDataChanged()
    } catch (e) { toast(e instanceof ApiError ? e.message : '操作失败') }
  }

  if (items === null) return <div className="wb-page"><div className="skeleton" style={{ height: 320 }} /></div>

  const shown = filter === 'all' ? items : items.filter(i => i.storage === filter)
  const expiringCount = items.filter(i => isExpiring(i.days_left)).length

  return (
    <div className="wb-page">
      <div className="ov fridge-tip"><TipBanner page="fridge" /></div>
      <div className="toolbar">
        <div className="segmented">
          <button className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>全部 {items.length}</button>
          {STORAGES.map(s => (
            <button key={s} className={filter === s ? 'on' : ''} onClick={() => setFilter(s)}>
              {STORAGE_META[s].label} {items.filter(i => i.storage === s).length}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {expiringCount > 0 && <span className="exp-pill urgent">{expiringCount} 样快过期</span>}
          <button className={`btn ${adding ? 'btn-ghost' : 'btn-primary'}`} onClick={() => setAdding(!adding)}>
            {adding ? <><X size={16} />收起</> : <><Plus size={16} />加食材</>}
          </button>
        </div>
      </div>

      {adding && (
        <section className="card adder-card" data-tour="pantry">
          <PantryAdder existing={items} autoFocus onAdded={load} />
        </section>
      )}

      {!items.length ? (
        <div className="card empty" style={{ padding: '48px 16px' }}>
          <Refrigerator size={40} />
          <p>{visionEnabled ? '冰箱还是空的。点右上角「加食材」，拍一张冰箱、选几样或者说一句话就行。' : '冰箱还是空的。点右上角「加食材」，选几样或者说一句话就行。'}</p>
        </div>
      ) : (
        <div className="fridge-cols stagger">
          {STORAGES.filter(s => filter === 'all' || filter === s).map(s => {
            const list = shown.filter(i => i.storage === s)
            if (filter === 'all' && !list.length) return null
            const Icon = STORAGE_META[s].icon
            return (
              <section className="card fridge-col" key={s} style={{ '--c': STORAGE_META[s].color } as CSSProperties}>
                <div className="card-title"><h2><span className="store-ico"><Icon size={15} /></span>{STORAGE_META[s].label}</h2><span className="hint">{list.length} 样</span></div>
                {list.length ? list.map(item => (
                  <div className={`pantry-row ${isExpiring(item.days_left) ? 'hot' : ''}`} key={item.id}>
                    <CatDot category={item.category} />
                    <div className="grow">
                      <b>{item.name}</b>
                      <span>{[formatQty(item.quantity, item.unit), item.category_label].filter(Boolean).join(' · ')}</span>
                    </div>
                    <ExpiryPill daysLeft={item.days_left} estimated={item.expires_estimated} />
                    <div className="row-actions">
                      <button className="icon-btn" title="修改" aria-label={`修改${item.name}`} onClick={() => setEditing(item)}><Pencil size={14} /></button>
                      <button className="icon-btn good" title="用完了" aria-label={`${item.name}用完了`} onClick={() => remove(item, 'used')}><Check size={15} /></button>
                      <button className="icon-btn danger" title="扔掉了" aria-label={`扔掉${item.name}`} onClick={() => remove(item, 'discarded')}><Trash2 size={14} /></button>
                    </div>
                  </div>
                )) : <p className="muted" style={{ fontSize: 13 }}>这里没有东西。</p>}
              </section>
            )
          })}
        </div>
      )}

      {editing && <EditItem item={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); emitDataChanged() }} />}
    </div>
  )
}

function EditItem({ item, onClose, onSaved }: { item: PantryItem; onClose: () => void; onSaved: () => void }) {
  const toast = useToast()
  const [form, setForm] = useState({
    name: item.name, quantity: item.quantity === null ? '' : String(item.quantity), unit: item.unit,
    storage: item.storage, category: item.category, expires_on: item.expires_estimated ? '' : item.expires_on ?? '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof form, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function save() {
    setBusy(true)
    const changes: Record<string, unknown> = {
      name: form.name, quantity: form.quantity === '' ? null : Number(form.quantity), unit: form.unit,
      storage: form.storage, category: form.category,
    }
    // 只有用户填了日期才发送；没填且原本是估算值时，换存放位置会自动重新估算
    if (form.expires_on) changes.expires_on = form.expires_on
    else if (!item.expires_estimated) changes.expires_on = null
    try {
      await api.patch(`/api/pantry/${item.id}`, changes)
      toast('改好了')
      onSaved()
    } catch (e) { toast(e instanceof ApiError ? e.message : '保存失败') }
    finally { setBusy(false) }
  }

  return (
    <Modal title={`修改 ${item.name}`} onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>取消</button><button className="btn btn-primary" disabled={busy || !form.name.trim()} onClick={save}>保存</button></>}>
      <div className="form-grid">
        <label className="field"><span>名称</span><input className="input" value={form.name} maxLength={30} onChange={e => set('name', e.target.value)} /></label>
        <div className="grid-2">
          <label className="field"><span>数量（可不填）</span><input className="input" inputMode="decimal" value={form.quantity} onChange={e => set('quantity', e.target.value.replace(/[^\d.]/g, ''))} /></label>
          <label className="field"><span>单位</span><input className="input" value={form.unit} maxLength={8} placeholder="个 / 斤 / g" onChange={e => set('unit', e.target.value)} /></label>
        </div>
        <label className="field"><span>放在哪</span>
          <div className="segmented">{STORAGES.map(s => <button key={s} type="button" className={form.storage === s ? 'on' : ''} onClick={() => set('storage', s)}>{STORAGE_META[s].label}</button>)}</div>
        </label>
        <label className="field"><span>分类</span>
          <select className="select" value={form.category} onChange={e => set('category', e.target.value)}>
            {Object.entries(CATEGORY_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <label className="field"><span>到期日（不填就按常识估算）</span>
          <input className="input" type="date" value={form.expires_on} onChange={e => set('expires_on', e.target.value)} />
        </label>
      </div>
    </Modal>
  )
}

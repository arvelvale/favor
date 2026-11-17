import { useCallback, useEffect, useMemo, useState } from 'react'
import { ClipboardList, Plus } from 'lucide-react'
import { api, type HealthRecord, type Kind } from '../lib/api'
import { dayLabel, KIND_META, KINDS, shiftDay, todayISO } from '../lib/metrics'
import { useDataChanged } from '../lib/motion'
import RecordItem from '../components/RecordItem'
import RecordModal from '../components/RecordModal'
import { useToast } from '../components/ui'

export default function RecordsPage() {
  const toast = useToast()
  const [kind, setKind] = useState<Kind | ''>('')
  const [span, setSpan] = useState(7)
  const [records, setRecords] = useState<HealthRecord[] | null>(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    const to = todayISO()
    const from = shiftDay(to, -(span - 1))
    api.get<{ records: HealthRecord[] }>(`/api/records?from=${from}&to=${to}${kind ? `&kind=${kind}` : ''}`)
      .then(r => setRecords(r.records)).catch(e => toast(e.message))
  }, [kind, span, toast])
  useEffect(load, [load])
  useDataChanged(load)

  const groups = useMemo(() => {
    const map = new Map<string, HealthRecord[]>()
    for (const r of records ?? []) map.set(r.day, [...(map.get(r.day) ?? []), r])
    return [...map.entries()]
  }, [records])

  async function remove(r: HealthRecord) {
    if (!confirm(`删除「${r.text}」？`)) return
    await api.del(`/api/records/${r.id}`).then(() => { toast('已删除'); load() }).catch(e => toast(e.message))
  }

  return (
    <div className="wb-page">
      <div className="filters">
        <button className="btn btn-sm btn-navy" onClick={() => setAdding(true)}><Plus size={15} />添加记录</button>
        <span style={{ width: 4 }} />
        <button className={`chip ${kind === '' ? 'on' : ''}`} onClick={() => setKind('')}>全部</button>
        {KINDS.map(k => {
          const M = KIND_META[k]
          return (
            <button key={k} className={`chip ${kind === k ? 'on' : ''}`} onClick={() => setKind(k)}>
              <M.icon size={14} color={M.color} />{M.label}
            </button>
          )
        })}
        <span style={{ flex: 1 }} />
        <div className="segmented">
          {[7, 30, 90].map(d => <button key={d} className={span === d ? 'on' : ''} onClick={() => setSpan(d)}>近 {d} 天</button>)}
        </div>
      </div>

      <div className="card">
        {records === null ? <div className="empty">正在加载…</div>
          : groups.length === 0 ? (
            <div className="empty"><ClipboardList size={36} /><p>这段时间还没有{kind ? KIND_META[kind].label : ''}记录。</p></div>
          ) : groups.map(([day, items]) => (
            <div className="day-group" key={day}>
              <div className="day-label">{dayLabel(day)}</div>
              <div className="timeline">{items.map(r => <RecordItem key={r.id} record={r} onDelete={remove} />)}</div>
            </div>
          ))}
      </div>

      {adding && <RecordModal initialKind={kind || 'meal'} onClose={() => setAdding(false)} onSaved={load} />}
    </div>
  )
}

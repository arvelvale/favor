import { Sparkles, Trash2 } from 'lucide-react'
import type { HealthRecord } from '../lib/api'
import { KIND_META } from '../lib/metrics'
import { MetricIcon } from './ui'

export default function RecordItem({ record, onDelete }: { record: HealthRecord; onDelete?: (r: HealthRecord) => void }) {
  const d = record.data
  let detail = ''
  if (record.kind === 'meal') {
    // 没有营养素数据时（如旧菜谱做完自动记的一餐）不显示「0g」，以免误以为真的是 0
    detail = d.protein || d.carbs || d.fat ? `蛋白质 ${d.protein}g · 碳水 ${d.carbs}g · 脂肪 ${d.fat}g` : (d.note || '')
  } else if (record.kind === 'mood' && d.note) {
    detail = d.note
  } else if (d.note) {
    detail = d.note
  }
  return (
    <div className="tl-item">
      <MetricIcon kind={record.kind} />
      <div className="body">
        <b>{record.text}</b>
        <span className="num">
          {record.at.slice(11, 16)} · {KIND_META[record.kind].label}
          {detail && ` · ${detail}`}
          {record.source === 'agent' && <> · <span className="src-tag"><Sparkles size={11} />Favor 记录</span></>}
        </span>
      </div>
      {onDelete && (
        <div className="actions">
          <button className="icon-btn danger" aria-label="删除记录" title="删除" onClick={() => onDelete(record)}>
            <Trash2 size={15} />
          </button>
        </div>
      )}
    </div>
  )
}

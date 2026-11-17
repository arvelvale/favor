import { Droplet, Dumbbell, Moon, Scale, Smile, UtensilsCrossed, type LucideIcon } from 'lucide-react'
import type { Kind } from './api'

export const KIND_META: Record<Kind, { label: string; color: string; icon: LucideIcon; unit: string }> = {
  meal: { label: '饮食', color: 'var(--meal)', icon: UtensilsCrossed, unit: 'kcal' },
  water: { label: '饮水', color: 'var(--water)', icon: Droplet, unit: 'ml' },
  exercise: { label: '运动', color: 'var(--exercise)', icon: Dumbbell, unit: '分钟' },
  sleep: { label: '睡眠', color: 'var(--sleep)', icon: Moon, unit: '小时' },
  weight: { label: '体重', color: 'var(--weight)', icon: Scale, unit: 'kg' },
  mood: { label: '心情', color: 'var(--mood)', icon: Smile, unit: '/5' },
}

export const KINDS = Object.keys(KIND_META) as Kind[]

export const MEAL_TYPES: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }
export const INTENSITIES: Record<string, string> = { low: '轻松', moderate: '中等', high: '高强度' }
export const MOODS = ['很糟', '不太好', '一般', '不错', '很好']

export function pct(value: number, target: number) {
  if (!target) return 0
  return Math.max(0, Math.min(100, (value / target) * 100))
}

export function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function shiftDay(iso: string, delta: number) {
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d + delta)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const WEEK = '日一二三四五六'
export function dayLabel(iso: string) {
  const today = todayISO()
  if (iso === today) return '今天'
  if (iso === shiftDay(today, -1)) return '昨天'
  const [y, m, d] = iso.split('-').map(Number)
  const w = new Date(y, m - 1, d).getDay()
  return `${m}月${d}日 周${WEEK[w]}`
}

export function greeting() {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

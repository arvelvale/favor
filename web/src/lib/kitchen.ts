import {
  Apple, Beef, Carrot, Croissant, Egg, Fish, Package, Salad, Snowflake, Sun, Thermometer, type LucideIcon,
} from 'lucide-react'
import type { Storage } from './api'

/** 食材分类：颜色给有含义的地方（白底为主，多搭颜色）。 */
export const CATEGORY_META: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  veg: { label: '蔬菜', color: '#1e9e5e', icon: Carrot },
  fruit: { label: '水果', color: '#e04f86', icon: Apple },
  meat: { label: '肉禽', color: '#e5484d', icon: Beef },
  seafood: { label: '水产', color: '#2e86de', icon: Fish },
  egg_dairy: { label: '蛋奶', color: '#e0a100', icon: Egg },
  tofu: { label: '豆制品', color: '#b07d3a', icon: Salad },
  staple: { label: '主食', color: '#c4451a', icon: Croissant },
  condiment: { label: '调料', color: '#7b8aa0', icon: Package },
  other: { label: '其他', color: '#7b5ce6', icon: Package },
}

export const catMeta = (c: string) => CATEGORY_META[c] ?? CATEGORY_META.other

export const STORAGE_META: Record<Storage, { label: string; icon: LucideIcon; color: string }> = {
  fridge: { label: '冷藏', icon: Thermometer, color: '#2e86de' },
  freezer: { label: '冷冻', icon: Snowflake, color: '#7b5ce6' },
  pantry: { label: '常温', icon: Sun, color: '#e0a100' },
}

export const STORAGES = Object.keys(STORAGE_META) as Storage[]

/** 剩余天数 → 文案与色调。estimated 时加「约」，提醒这是估算值。 */
export function expiryInfo(daysLeft: number | null, estimated = false): { text: string; tone: 'over' | 'urgent' | 'soon' | 'ok' | 'none' } {
  if (daysLeft === null) return { text: '不易坏', tone: 'none' }
  const about = estimated ? '约' : ''
  if (daysLeft < 0) return { text: `已过期 ${-daysLeft} 天`, tone: 'over' }
  if (daysLeft === 0) return { text: '今天到期', tone: 'urgent' }
  if (daysLeft <= 2) return { text: `${about}还剩 ${daysLeft} 天`, tone: 'urgent' }
  if (daysLeft <= 5) return { text: `${about}还剩 ${daysLeft} 天`, tone: 'soon' }
  return { text: `${about}还剩 ${daysLeft} 天`, tone: 'ok' }
}

export const isExpiring = (daysLeft: number | null) => daysLeft !== null && daysLeft <= 2

export function formatQty(quantity: number | null, unit: string) {
  if (quantity === null) return ''
  return `${Number.isInteger(quantity) ? quantity : quantity.toFixed(1).replace(/\.0$/, '')}${unit}`
}

export const DIFFICULTY = ['', '简单', '一般', '稍难']

export const MEAL_SLOTS: [string, string][] = [['breakfast', '早餐'], ['lunch', '午餐'], ['dinner', '晚餐'], ['snack', '加餐']]

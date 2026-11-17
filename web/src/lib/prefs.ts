import { useEffect, useState } from 'react'
import {
  AirVent, Baby, Coffee, CookingPot, Flame, GraduationCap, HeartPulse, Heater, House, Leaf, Microwave,
  PiggyBank, Salad, ShieldAlert, Soup, Sprout, Timer, User, Users, Utensils, Zap, CircleHelp, type LucideIcon,
} from 'lucide-react'
import { api } from './api'

export type QuestionKey = 'household' | 'skill' | 'minutes' | 'equipment' | 'staples' | 'taste' | 'goals' | 'body'

export interface Prefs {
  household: 'solo' | 'two' | 'family'
  family_size: number
  family_flags: string[]
  skill: 'beginner' | 'home' | 'skilled'
  minutes: 15 | 30 | 0
  equipment: string[]
  staples: string[]
  spice: 'none' | 'mild' | 'medium' | 'hot'
  dislikes: string[]
  diet: 'none' | 'vegetarian' | 'vegan' | 'halal' | 'no_beef'
  goals: string[]
}

export interface PrefsState {
  status: 'new' | 'done' | 'skipped'
  prefs: Prefs
  skipped: QuestionKey[]
  allergies: string[]
  servings: number
  health_in_nav: boolean
}

export interface Option<T = string> { value: T; label: string; sub?: string; icon?: LucideIcon; color?: string }

export const HOUSEHOLD: Option<Prefs['household']>[] = [
  { value: 'solo', label: '只有我', sub: '一人份，一锅出、少剩菜', icon: User, color: '#2f7cf6' },
  { value: 'two', label: '两个人', sub: '两人份', icon: Users, color: '#8b5cf6' },
  { value: 'family', label: '一家人', sub: '两菜一汤，凑成一顿饭', icon: House, color: '#f08a24' },
]
export const FAMILY_FLAGS: Option[] = [
  { value: 'elderly', label: '有老人', icon: Heater },
  { value: 'kids', label: '有小孩', icon: Baby },
]
export const SKILL: Option<Prefs['skill']>[] = [
  { value: 'beginner', label: '几乎不会', sub: '只推简单的，步骤会解释术语', icon: Sprout, color: '#1e9e5e' },
  { value: 'home', label: '会做家常菜', sub: '家常难度为主', icon: CookingPot, color: '#2f7cf6' },
  { value: 'skilled', label: '挺熟练', sub: '可以来点有技术含量的', icon: Flame, color: '#e5484d' },
]
export const MINUTES: Option<Prefs['minutes']>[] = [
  { value: 15, label: '15 分钟内', sub: '下班只想快点吃上', icon: Zap, color: '#f08a24' },
  { value: 30, label: '30 分钟左右', sub: '正常做一顿', icon: Timer, color: '#2f7cf6' },
  { value: 0, label: '不赶时间', sub: '慢慢做也行', icon: Coffee, color: '#8b5cf6' },
]
export const EQUIPMENT: Option[] = [
  { value: 'wok', label: '炒锅', icon: CookingPot, color: '#e5484d' },
  { value: 'rice_cooker', label: '电饭煲', icon: Soup, color: '#f08a24' },
  { value: 'microwave', label: '微波炉', icon: Microwave, color: '#2f7cf6' },
  { value: 'air_fryer', label: '空气炸锅', icon: AirVent, color: '#8b5cf6' },
  { value: 'oven', label: '烤箱', icon: Heater, color: '#d9480f' },
  { value: 'mini_pot', label: '只有一个小电锅', sub: '宿舍党', icon: Utensils, color: '#1e9e5e' },
]
export const EQUIPMENT_LABEL: Record<string, string> = Object.fromEntries(EQUIPMENT.map(e => [e.value, e.label === '只有一个小电锅' ? '小电锅' : e.label]))
export const STAPLES = ['盐', '油', '酱油', '醋', '糖', '蚝油', '料酒', '淀粉', '豆瓣酱', '胡椒粉', '香油', '鸡精']
export const SPICE: Option<Prefs['spice']>[] = [
  { value: 'none', label: '不吃辣' }, { value: 'mild', label: '微辣' },
  { value: 'medium', label: '中辣' }, { value: 'hot', label: '很能吃辣' },
]
export const DIET: Option<Prefs['diet']>[] = [
  { value: 'none', label: '没有限制' }, { value: 'vegetarian', label: '素食（蛋奶素）' }, { value: 'vegan', label: '纯素' },
  { value: 'halal', label: '清真' }, { value: 'no_beef', label: '不吃牛肉' },
]
export const DISLIKES = ['香菜', '葱', '姜', '蒜', '芹菜', '内脏', '羊肉', '海鲜', '茄子', '苦瓜']
export const ALLERGIES = ['花生', '坚果', '海鲜', '牛奶', '鸡蛋', '大豆', '小麦']
export const GOALS: Option[] = [
  { value: 'what_to_cook', label: '不知道做什么', sub: '打开就有 3 道能做的', icon: CircleHelp, color: '#2f7cf6' },
  { value: 'waste', label: '食材总放坏', sub: '快过期的优先用掉', icon: Leaf, color: '#1e9e5e' },
  { value: 'save_money', label: '想省钱', sub: '尽量不用额外买', icon: PiggyBank, color: '#f08a24' },
  { value: 'healthy', label: '想吃得健康', sub: '看热量，健康进主导航', icon: HeartPulse, color: '#e5484d' },
  { value: 'learn', label: '想学做饭', sub: '每次学一个新手法', icon: GraduationCap, color: '#8b5cf6' },
]

export const QUESTION_META: Record<QuestionKey, { title: string; hint: string; icon: LucideIcon; color: string }> = {
  household: { title: '你平时给几个人做饭？', hint: '决定默认份量，以及推荐一人食还是两菜一汤', icon: Users, color: '#2f7cf6' },
  skill: { title: '你的做饭水平？', hint: '决定推荐的难度，新手会把步骤讲得更细', icon: Sprout, color: '#1e9e5e' },
  minutes: { title: '工作日愿意花多久做饭？', hint: '超过这个时间的菜会排后面，并标出来', icon: Timer, color: '#f08a24' },
  equipment: { title: '你有哪些厨具？', hint: '没有的厨具，相关的菜一律不推', icon: CookingPot, color: '#e5484d' },
  staples: { title: '家里常备哪些调料？', hint: '勾上的不算「缺料」，不会每道菜都提醒你买', icon: Salad, color: '#8b5cf6' },
  taste: { title: '口味和忌口', hint: '过敏和饮食方式会严格排除，口味只影响偏好', icon: ShieldAlert, color: '#d9480f' },
  goals: { title: '你最想解决什么？', hint: '决定推荐的排序和首页先看什么，可以多选', icon: CircleHelp, color: '#2f7cf6' },
  body: { title: '你的目标和身体数据', hint: '用来算每天的热量，推荐时会看今天还能吃多少', icon: HeartPulse, color: '#e5484d' },
}

export const DEFAULT_PREFS: Prefs = {
  household: 'solo', family_size: 3, family_flags: [], skill: 'home', minutes: 30,
  equipment: ['wok', 'rice_cooker', 'microwave'], staples: ['盐', '油', '酱油', '醋', '糖'],
  spice: 'mild', dislikes: [], diet: 'none', goals: ['what_to_cook'],
}

const label = <T,>(opts: Option<T>[], v: T) => opts.find(o => o.value === v)?.label ?? ''

export interface Adjustment { q: QuestionKey; icon: LucideIcon; color: string; text: string; defaulted: boolean }

/** 「根据你的回答，我们已经……」：每一题对应一条看得见的调整。 */
export function adjustments(s: Pick<PrefsState, 'prefs' | 'skipped' | 'allergies'>, includeBody = false): Adjustment[] {
  const p = s.prefs
  const out: Adjustment[] = []
  const add = (q: QuestionKey, text: string) =>
    out.push({ q, icon: QUESTION_META[q].icon, color: QUESTION_META[q].color, text, defaulted: s.skipped.includes(q) })

  const n = p.household === 'solo' ? 1 : p.household === 'two' ? 2 : p.family_size
  let household = p.household === 'solo' ? '推荐按 1 人份，优先一锅出、少剩菜的菜'
    : p.household === 'two' ? '推荐按 2 人份' : `推荐按 ${n} 人份，3 道菜搭成两菜一汤`
  if (p.family_flags.includes('elderly')) household += '；照顾老人，少盐、做得软烂'
  if (p.family_flags.includes('kids')) household += '；照顾小孩，不辣、去刺去骨'
  add('household', household)

  add('skill', p.skill === 'beginner' ? '只推简单的菜，步骤里会解释焯水、勾芡这些说法'
    : p.skill === 'home' ? '以家常难度为主，太难的排后面' : '会推荐一些有技术含量的菜')
  add('minutes', p.minutes ? `超过 ${p.minutes} 分钟的菜排后面，并标出要多久` : '不限时间，按食材来')

  if (p.equipment.length === 1 && p.equipment[0] === 'mini_pot') {
    add('equipment', '只推一个小电锅能做的菜：煮、焖、蒸')
  } else {
    const lacking = ['oven', 'air_fryer', 'microwave', 'wok'].filter(e => !p.equipment.includes(e)).map(e => EQUIPMENT_LABEL[e])
    add('equipment', lacking.length ? `不推需要${lacking.join('、')}的菜` : '你的厨具很全，什么菜都可以推')
  }
  add('staples', p.staples.length ? `${p.staples.join('、')}不算缺料，不会每道菜都提醒你买` : '调料也会算进缺料里')

  const taste = [label(SPICE, p.spice)]
  if (p.diet !== 'none') taste.push(`只推${label(DIET, p.diet)}的菜`)
  if (p.dislikes.length) taste.push(`去掉${p.dislikes.join('、')}`)
  if (s.allergies.length) taste.push(`含${s.allergies.join('、')}的菜一律不推`)
  add('taste', taste.join('；'))

  const goals: string[] = []
  if (p.goals.includes('waste')) goals.push('快过期的放在首页最前面，推荐时优先用掉')
  if (p.goals.includes('save_money')) goals.push('缺料少的菜排前面')
  if (p.goals.includes('learn')) goals.push('每次推荐安排一道能学到新手法的')
  if (p.goals.includes('healthy')) goals.push('「健康」放进主导航，推荐会看今天还能吃多少热量')
  if (!goals.length) goals.push('打开首页就推荐 3 道现在就能做的菜')
  add('goals', goals.join('；'))
  if (includeBody && p.goals.includes('healthy')) add('body', '按你的身体数据算每天的热量目标')
  return out
}

// ------------------------------------------------------------ 共享状态：工作台导航、首页、我的页都要读

let cache: PrefsState | null = null
const listeners = new Set<(s: PrefsState) => void>()

export function setPrefsCache(s: PrefsState) {
  cache = s
  listeners.forEach(fn => fn(s))
}

export function usePrefs(): PrefsState | null {
  const [state, setState] = useState<PrefsState | null>(cache)
  useEffect(() => {
    listeners.add(setState)
    if (!cache) api.get<PrefsState>('/api/preferences').then(setPrefsCache).catch(() => undefined)
    return () => { listeners.delete(setState) }
  }, [])
  return state
}

export function clearPrefsCache() { cache = null }

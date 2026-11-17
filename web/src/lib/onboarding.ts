import { useEffect, useState } from 'react'
import { api } from './api'
import { useDataChanged } from './motion'

export type TourStep = 'pantry' | 'recommend' | 'open' | 'cook'
export type TipId = 'expiring' | 'expiry_dates' | 'health' | `ask_${string}`

export interface OnboardingState {
  tour: 'active' | 'skipped' | 'done'
  steps: Record<TourStep, boolean>
  current: TourStep | null
  cooked: boolean
  checklist: { key: string; label: string; done: boolean }[]
  checklist_done: number
  checklist_dismissed: boolean
  tips: TipId[]
  prefs_status: 'new' | 'done' | 'skipped'
}

// 共享状态：引导层（工作台）、首页清单和提示、菜谱页都要读；数据变化（加食材、推荐、做菜）后自动刷新
let cache: OnboardingState | null = null
const listeners = new Set<(s: OnboardingState) => void>()

function publish(s: OnboardingState) {
  cache = s
  listeners.forEach(fn => fn(s))
}

// 多个组件同时监听数据变化：合并成一个请求；请求途中又有变化，就在结束后再拉一次
let inflight: Promise<void> | null = null
let again = false

export function refreshOnboarding(): Promise<void> {
  if (inflight) { again = true; return inflight }
  inflight = api.get<OnboardingState>('/api/onboarding').then(publish).catch(() => undefined).finally(() => {
    inflight = null
    if (again) { again = false; void refreshOnboarding() }
  })
  return inflight
}

export async function updateOnboarding(changes: Record<string, unknown>) {
  try { publish(await api.post<OnboardingState>('/api/onboarding', changes)) } catch { /* 引导状态写失败不影响主流程 */ }
}

export function clearOnboardingCache() { cache = null }

export function useOnboarding(): OnboardingState | null {
  const [state, setState] = useState<OnboardingState | null>(cache)
  useEffect(() => {
    listeners.add(setState)
    if (!cache) refreshOnboarding()
    return () => { listeners.delete(setState) }
  }, [])
  useDataChanged(refreshOnboarding)
  return state
}

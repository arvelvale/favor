// 与 Flask 后端通信。所有请求带上本地时区偏移，后端据此计算“今天”。
export type Kind = 'meal' | 'water' | 'exercise' | 'sleep' | 'weight' | 'mood'

export interface User { id: number; username: string; nickname: string; prefs_status?: 'new' | 'done' | 'skipped' }

export interface FoodItem { name: string; amount?: string; calories: number; protein?: number; carbs?: number; fat?: number }

export interface HealthRecord {
  id: number
  kind: Kind
  day: string
  at: string
  source: 'manual' | 'agent'
  text: string
  data: Record<string, any>
}

export interface Targets {
  calories: number
  water_ml: number
  exercise_min: number
  sleep_hours: number
  protein_g: number | null
  bmr: number | null
  tdee: number | null
  complete: boolean
  missing: string[]
}

export interface Totals {
  calories_in: number; protein: number; carbs: number; fat: number; water_ml: number
  exercise_min: number; exercise_kcal: number; sleep_hours: number; weight_kg: number | null; mood: number | null
  last_weight?: { kg: number; day: string } | null
}

export interface Habit { id: number; name: string; note: string; done: boolean; week_count: number }

export interface Summary {
  day: string; totals: Totals; targets: Targets; remaining_calories: number; records: HealthRecord[]; habits: Habit[]
}

export interface DayPoint extends Totals { day: string; count: number }

export interface Profile {
  sex: 'male' | 'female' | null; birth_year: number | null; height_cm: number | null; weight_kg: number | null
  target_weight_kg: number | null; activity_level: string | null; goal: string | null
  diet_preferences: string; allergies: string; conditions: string
}

export interface ProfilePayload {
  profile: Profile; bmi: number | null; targets: Targets
  options: { activity_levels: Record<string, string>; goals: Record<string, string> }
}

export interface Conversation { id: number; title: string; updated_at: string }

/** 一条营养资料引用：编号、出处、证据等级、摘要等，字段与后端 sources_payload 对齐。 */
export interface NutritionSource {
  citation: number
  title: string
  heading?: string
  publisher: string
  published: string
  url: string
  snippet: string
  score?: number
  evidence_level: string
  evidence_class: 'guide' | 'gov' | 'paper' | 'popular' | string
  evidence_label: string
  audience?: string
}

// ---------------------------------------------------------- 冰箱与菜谱

export type Storage = 'fridge' | 'freezer' | 'pantry'

export interface PantryItem {
  id: number
  name: string
  category: string
  category_label: string
  quantity: number | null
  unit: string
  storage: Storage
  storage_label: string
  expires_on: string | null
  expires_estimated: boolean
  days_left: number | null
}

/** 一句话录入的解析预览：还没入库，没有 id。 */
export type ParsedItem = Omit<PantryItem, 'id'>

export interface CatalogGroup { category: string; label: string; items: string[] }

export interface Ingredient {
  name: string
  amount: string
  optional: boolean
  status?: 'have' | 'staple' | 'missing'
  pantry_id?: number
}

export interface Recipe {
  id: number
  title: string
  summary: string
  minutes: number
  difficulty: number
  servings: number
  kcal_per_serving: number | null
  ingredients: Ingredient[]
  steps: string[]
  tips: string
  missing: string[]
  uses_expiring: string[]
  uses_count: number
  /** 不符合问卷设置的地方（超时、太难、超热量），排序时排后面 */
  fit?: string[]
  /** 因忌口/饮食方式去掉的可省略用料 */
  stripped?: string[]
  saved: boolean
  cooked_count: number
  created_at: string
}

export interface RecipeBatch { batch: string | null; recipes: Recipe[]; stale: boolean; dropped?: { title: string; reason: string }[] }

export interface CookUsage {
  item_id: number
  name: string
  amount: string
  quantity: number | null
  unit: string
  remaining: number | null
  used_up: boolean
}

export interface CookPreview { recipe: Recipe; usage: CookUsage[]; meal_type: string; eaten_servings: number }
export interface CookResult { title: string; used: { name: string; result: string }[]; record: { id: number; text: string } | null }
export interface CookLog { id: number; title: string; cooked_at: string; servings: number; recipe_id: number | null; used: { name: string; result: string }[] }

export type RecipeBrief = Pick<Recipe, 'id' | 'title' | 'minutes' | 'difficulty' | 'kcal_per_serving' | 'missing' | 'uses_expiring' | 'summary' | 'fit' | 'stripped'>

export type Card =
  | { type: 'record'; action: 'logged' | 'deleted'; kind: Kind; record_id: number; title: string; at: string }
  | { type: 'pantry'; action: 'added' | 'removed'; names: string[] }
  | { type: 'recipes'; recipes: RecipeBrief[] }
  | { type: 'profile'; title: string; fields: string[]; calories: number; water_ml: number }
  | { type: 'habit'; action: 'created' | 'checked' | 'unchecked'; title: string }
  | { type: 'trend'; days: number }
  | { type: 'image'; image_id: number; title: string }
  | {
      type: 'sources'
      sources: NutritionSource[]
      no_evidence: boolean
      risk_terms: string[]
      risk_notice: string
      disclaimer: string
    }

/** 引用事后自检结果：核对回答里的 [n] 是否都能在本次资料中找到出处。 */
export interface CitationAudit {
  cited: number[]
  valid: number[]
  invalid: number[]
  uncited: number[]
  ok: boolean
  level?: 'ok' | 'warn' | 'error'
  notice: string
}

export interface ImageMeta { id: number; title: string; status: 'pending' | 'ready' | 'failed'; error: string | null }

export interface ChatMessage {
  id: number | string
  role: 'user' | 'assistant'
  content: string
  cards: Card[]
  citation_audit?: CitationAudit | null
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

function headers(json: boolean): HeadersInit {
  const h: Record<string, string> = { 'X-TZ-Offset': String(new Date().getTimezoneOffset()) }
  if (json) h['Content-Type'] = 'application/json'
  return h
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn }

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method, credentials: 'same-origin', headers: headers(body !== undefined),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('网络连接失败，检查一下服务是否在运行', 0)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401 && !url.startsWith('/api/auth/')) onUnauthorized?.()
    throw new ApiError(data.error || `请求失败（${res.status}）`, res.status)
  }
  return data as T
}

export const api = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body: unknown = {}) => request<T>('POST', url, body),
  put: <T>(url: string, body: unknown) => request<T>('PUT', url, body),
  patch: <T>(url: string, body: unknown) => request<T>('PATCH', url, body),
  del: <T>(url: string) => request<T>('DELETE', url),
}

export type StreamEvent =
  | { type: 'delta'; content: string }
  | { type: 'tool'; name: string; label: string; status: 'running' }
  | { type: 'card'; card: Card }
  | { type: 'citation_audit'; audit: CitationAudit }
  | { type: 'done'; title: string }
  | { type: 'error'; message: string }

/** POST 后读取 SSE 流（EventSource 不支持 POST，这里手动解析 data: 行）。 */
export async function streamChat(conversationId: number, message: string,
  onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}/chat`, {
    method: 'POST', credentials: 'same-origin', headers: headers(true),
    body: JSON.stringify({ message }), signal,
  })
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}))
    throw new ApiError(data.error || `请求失败（${res.status}）`, res.status)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try { onEvent(JSON.parse(line.slice(6))) } catch { /* 忽略残缺行 */ }
        }
      }
    }
  }
}

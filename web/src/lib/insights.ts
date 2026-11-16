// 工作台“今日建议”：基于数据的规则提示，不依赖模型，没配置密钥时也能用。
import type { DayPoint, Kind, Summary } from './api'

export interface Insight { kind: Kind; tone: 'good' | 'tip' | 'warn'; title: string; text: string; ask: string }

export function buildInsights(s: Summary, week: DayPoint[]): Insight[] {
  const out: Insight[] = []
  const t = s.totals, g = s.targets
  const hour = new Date().getHours()
  const past = week.slice(0, -1).filter(d => d.count > 0)

  // 饮水：按时间进度判断是否落后（8 点到 22 点线性分配目标）
  const expected = g.water_ml * Math.min(1, Math.max(0, (hour - 8) / 14))
  if (t.water_ml < expected - 300) {
    out.push({ kind: 'water', tone: 'tip', title: '喝水有点落后了',
      text: `按现在的时间，今天应该喝到约 ${Math.round(expected / 50) * 50} ml，目前 ${t.water_ml} ml。`,
      ask: '我今天水喝得不够，有什么容易坚持的补水办法？' })
  } else if (t.water_ml >= g.water_ml) {
    out.push({ kind: 'water', tone: 'good', title: '今天的水喝够了', text: `已经喝了 ${t.water_ml} ml，保持住。`, ask: '' })
  }

  // 蛋白质：午后仍不到目标的 40%
  if (g.protein_g && hour >= 14 && t.protein < g.protein_g * 0.4) {
    out.push({ kind: 'meal', tone: 'tip', title: '蛋白质偏少',
      text: `目前 ${Math.round(t.protein)} g，目标 ${g.protein_g} g。晚餐可以加一份鱼虾、豆腐或鸡胸肉。`,
      ask: `帮我推荐一份高蛋白晚餐，热量控制在 ${Math.max(300, s.remaining_calories)} kcal 以内` })
  }

  // 热量：超出预算
  if (s.remaining_calories < -150) {
    out.push({ kind: 'meal', tone: 'warn', title: '今天吃得有点多',
      text: `超出约 ${-s.remaining_calories} kcal。不用节食补偿，明天正常吃、多走走就好。`,
      ask: '今天热量超了，明天的饮食怎么安排比较合理？' })
  }

  // 睡眠：近几天平均
  const sleeps = past.map(d => d.sleep_hours).filter(Boolean)
  if (sleeps.length >= 3) {
    const avg = sleeps.reduce((a, b) => a + b, 0) / sleeps.length
    if (avg < 7) out.push({ kind: 'sleep', tone: 'warn', title: `最近平均只睡了 ${avg.toFixed(1)} 小时`,
      text: '连续睡眠不足会影响食欲和情绪，今晚试着提前 30 分钟上床。', ask: '我最近睡得太少了，帮我定一个循序渐进的早睡计划' })
    else out.push({ kind: 'sleep', tone: 'good', title: '睡眠很规律', text: `最近平均 ${avg.toFixed(1)} 小时，继续保持。`, ask: '' })
  }

  // 运动：近一周运动天数
  const activeDays = week.filter(d => d.exercise_min > 0).length
  if (week.length >= 7 && activeDays <= 2) {
    out.push({ kind: 'exercise', tone: 'tip', title: `这周只运动了 ${activeDays} 天`,
      text: '不用一下子练很多，饭后快走 20 分钟就很好。', ask: '我平时很忙，帮我安排一个每天 20 分钟的运动计划' })
  } else if (activeDays >= 4) {
    out.push({ kind: 'exercise', tone: 'good', title: `这周已运动 ${activeDays} 天`, text: '运动习惯正在形成。', ask: '' })
  }

  if (!s.records.length) {
    out.unshift({ kind: 'meal', tone: 'tip', title: '今天还没有记录',
      text: '从早餐开始吧，直接跟 Favor 说一句就行。', ask: '早饭吃了两个包子和一杯豆浆' })
  }

  const rank = { warn: 0, tip: 1, good: 2 }
  return out.sort((a, b) => rank[a.tone] - rank[b.tone]).slice(0, 4)
}

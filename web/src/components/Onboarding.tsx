import type { CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CalendarClock, Check, HeartPulse, Leaf, Lightbulb, SlidersHorizontal, X } from 'lucide-react'
import { updateOnboarding, useOnboarding, type OnboardingState, type TipId } from '../lib/onboarding'
import { QUESTION_META, type QuestionKey } from '../lib/prefs'

function scrollToTour(sel: string) {
  const el = document.querySelector<HTMLElement>(sel)
  if (!el) return false
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  el.classList.add('flash')
  window.setTimeout(() => el.classList.remove('flash'), 1400)
  return true
}

/** 首页「上手进度 x/5」清单：引导跳过或完成后才出现；全部完成或手动关闭后消失。 */
const checklistVisible = (ob: OnboardingState) =>
  ob.tour !== 'active' && !ob.checklist_dismissed && ob.checklist_done < ob.checklist.length

export function OnboardingChecklist() {
  const ob = useOnboarding()
  const navigate = useNavigate()
  if (!ob || !checklistVisible(ob)) return null

  const go = (key: string) => {
    if (key === 'prefs') navigate('/welcome?redo=1')
    else if (key === 'pantry') navigate('/app/fridge?add=1')
    else if (key === 'recommend') scrollToTour('[data-tour="recommend"]') || scrollToTour('[data-tour="pantry"]')
    else scrollToTour('[data-tour="first-recipe"]') || scrollToTour('[data-tour="recommend"]')
  }
  const total = ob.checklist.length
  const next = ob.checklist.find(c => !c.done)

  return (
    <section className="card span-12 checklist-card">
      <div className="checklist-head">
        <div>
          <h2>上手进度 <span className="num">{ob.checklist_done}/{total}</span></h2>
          <div className="checklist-bar"><i style={{ width: `${(ob.checklist_done / total) * 100}%` }} /></div>
        </div>
        <button className="icon-btn" aria-label="不再显示上手进度" title="不再显示" onClick={() => updateOnboarding({ checklist_dismissed: true })}><X size={16} /></button>
      </div>
      <ol className="checklist">
        {ob.checklist.map((c, i) => (
          <li key={c.key} className={c.done ? 'done' : c === next ? 'next' : ''}>
            <button type="button" onClick={() => !c.done && go(c.key)} disabled={c.done}>
              <span className="ck">{c.done ? <Check size={13} strokeWidth={3} /> : <span className="num">{i + 1}</span>}</span>
              <span className="lbl">{c.label}</span>
              {c === next && <ArrowRight size={14} className="go" />}
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}

const HOME_TIPS = (id: TipId) => id === 'expiring' || id === 'health' || id.startsWith('ask_')

/** 情境提示：每条只出现一次，一次只出一条。首页和冰箱页各显示属于自己的那几种。 */
export function TipBanner({ page }: { page: 'home' | 'fridge' }) {
  const ob = useOnboarding()
  const navigate = useNavigate()
  // 上手清单还在、且「告诉 Favor 你的口味」没做时，清单已经在提醒补问卷，就不再单独弹「补一下」提示，免得重复
  const checklistAsks = !!ob && checklistVisible(ob) && !ob.checklist.find(c => c.key === 'prefs')?.done
  const tip = ob?.tips.find(t => (page === 'home' ? HOME_TIPS(t) && !(checklistAsks && t.startsWith('ask_')) : t === 'expiry_dates'))
  if (!tip) return null
  // 整份问卷都跳过的人：所有「补一下」合成一条，点「不用了」一起记为看过，不连着追问 7 次
  const askAll = tip.startsWith('ask_') && ob!.prefs_status === 'skipped'
  const seen = () => updateOnboarding({ seen_tip: askAll ? ob!.tips.filter(t => t.startsWith('ask_')) : tip })

  let icon = <Lightbulb size={17} />, color = '#2f7cf6', text = '', action: { label: string; run: () => void } | null = null
  if (tip === 'expiring') {
    icon = <Leaf size={17} />; color = '#1e9e5e'
    text = '有食材快过期了。推荐时会把用得上它们的菜排在前面，帮你先用掉。'
  } else if (tip === 'expiry_dates') {
    icon = <CalendarClock size={17} />; color = '#f08a24'
    text = '现在的到期日都是按类别估的。点一样食材，改成包装上的日期，快过期提醒会更准。'
  } else if (tip === 'health') {
    icon = <HeartPulse size={17} />; color = '#e5484d'
    text = '你做的每顿饭都自动记在「健康」里了，想看看热量和趋势随时可以去。'
    action = { label: '去看看', run: () => { seen(); navigate('/app/health') } }
  } else if (askAll) {
    icon = <SlidersHorizontal size={17} />
    text = '你跳过了问卷，现在的推荐是按默认来的（1 人份、30 分钟、炒锅电饭煲微波炉）。花一分钟做完，推荐会更合你的情况。'
    action = { label: '去做问卷', run: () => { seen(); navigate('/welcome?redo=1') } }
  } else {
    const q = tip.slice(4) as QuestionKey
    icon = <SlidersHorizontal size={17} />; color = QUESTION_META[q]?.color ?? color
    text = `问卷里你跳过了「${QUESTION_META[q]?.title ?? q}」，推荐暂时按默认来。补一下，推荐会更合你的情况。`
    action = { label: '补一下', run: () => { seen(); navigate(`/welcome?q=${q}`) } }
  }

  return (
    <div className="tip-banner span-12" style={{ '--c': color } as CSSProperties} role="status">
      <span className="tip-ico">{icon}</span>
      <p>{text}</p>
      <div className="tip-actions">
        {action && <button className="btn btn-primary" onClick={action.run}>{action.label}</button>}
        <button className="btn btn-ghost" onClick={seen}>{action ? '不用了' : '知道了'}</button>
      </div>
    </div>
  )
}


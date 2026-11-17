import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bookmark, CookingPot } from 'lucide-react'
import { api, type CookLog, type Recipe } from '../lib/api'
import { useDataChanged } from '../lib/motion'
import { useToast } from '../components/ui'
import { RecipeCard } from '../components/Kitchen'

export default function SavedPage() {
  const toast = useToast()
  const [data, setData] = useState<{ saved: Recipe[]; cooked: CookLog[] } | null>(null)
  const load = useCallback(() => {
    api.get<{ saved: Recipe[]; cooked: CookLog[] }>('/api/recipes').then(setData).catch(e => toast(e.message))
  }, [toast])
  useEffect(load, [load])
  useDataChanged(load)

  if (!data) return <div className="wb-page"><div className="skeleton" style={{ height: 300 }} /></div>

  return (
    <div className="wb-page">
      <section className="recipes-section">
        <div className="section-head"><h2><Bookmark size={17} />收藏的菜</h2><span className="muted">{data.saved.length} 道</span></div>
        {data.saved.length ? (
          <div className="recipe-grid">{data.saved.map((r, i) => <RecipeCard key={r.id} r={r} index={i} />)}</div>
        ) : (
          <div className="card empty"><Bookmark size={34} /><p>喜欢的菜点「收藏」，下次想做直接来这里找。缺不缺料会按当时的冰箱重新算。</p></div>
        )}
      </section>

      <section className="card" style={{ marginTop: 22 }}>
        <div className="card-title"><h2><CookingPot size={16} />做过的菜</h2><span className="hint">最近 30 次</span></div>
        {data.cooked.length ? (
          <div className="cook-log">
            {data.cooked.map(l => (
              <div className="cook-log-row" key={l.id}>
                <div className="when num">{l.cooked_at.slice(5, 10).replace('-', '/')}<span>{l.cooked_at.slice(11, 16)}</span></div>
                <div className="grow">
                  {l.recipe_id ? <Link to={`/app/recipe/${l.recipe_id}`}><b>{l.title}</b></Link> : <b>{l.title}</b>}
                  <span>{l.used.length ? l.used.map(u => `${u.name}${u.result === '用完了' ? '用完' : u.result.replace('还', '')}`).join(' · ') : '没用到冰箱里的食材'}</span>
                </div>
                {l.servings > 0 && <span className="tag">吃了 {l.servings} 份</span>}
              </div>
            ))}
          </div>
        ) : <div className="empty"><CookingPot size={34} /><p>还没有做过菜。做完一道点「做好了」，这里就会记下来。</p></div>}
      </section>
    </div>
  )
}

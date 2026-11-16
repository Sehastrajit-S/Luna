import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { P } from '../palette'
import { Corners } from '../shared/Corners'
import { asArray, fetchLuna, fetchLunaCached } from '../lunaDashboardApi'

interface NewsItem { source: string; title: string; link: string; image?: string }
interface ArticleData { title: string; body: string; image?: string; url: string }

function ArticleReader({ article, onClose }: { article: ArticleData; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.18 }}
      style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div onClick={e => e.stopPropagation()} style={{ width: '72vw', maxWidth: 820, maxHeight: '82vh', background: 'rgba(10,10,18,0.97)', border: `1px solid ${P.borderBright}`, borderRadius: 8, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <Corners />
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${P.border}`, display: 'flex', alignItems: 'flex-start', gap: 10, flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.15em', marginBottom: 6 }}>ARTICLE</div>
            <div style={{ fontSize: 13, color: P.text, lineHeight: 1.4, fontWeight: 500 }}>{article.title || 'Article'}</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
            <button
              onClick={() => (window as any).electronAPI?.openUrl?.(article.url) ?? window.open(article.url, '_blank')}
              style={{ background: 'none', border: `1px solid ${P.border}`, borderRadius: 4, padding: '3px 8px', cursor: 'pointer', color: P.textDim, fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.08em' }}
            >OPEN</button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: P.textDim, display: 'flex', padding: 2 }}><X size={14} /></button>
          </div>
        </div>
        {article.image && (
          <div style={{ width: '100%', height: 200, flexShrink: 0, overflow: 'hidden', background: '#0a0a12' }}>
            <img src={article.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', opacity: 0.9 }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
          </div>
        )}
        <div style={{ overflowY: 'auto', padding: '14px 18px', scrollbarWidth: 'none', flex: 1 }}>
          {article.body.split('\n\n').map((para, i) => (
            <p key={i} style={{ fontSize: 12, color: 'rgba(226,232,240,0.82)', lineHeight: 1.7, marginBottom: 12 }}>{para}</p>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

export function NewsList({ limit }: { limit?: number }) {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [article, setArticle] = useState<ArticleData | null>(null)
  const [fetching, setFetching] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<unknown>('/api/luna/news', 4 * 60_000)
        setItems(asArray<NewsItem>(d))
      } catch (e) {
        console.warn('[luna] news unavailable', e)
        setItems([])
      }
      setLoading(false)
    }
    load()
    const t = setInterval(load, 4 * 60_000)
    return () => clearInterval(t)
  }, [])

  const openArticle = async (item: NewsItem) => {
    if (!item.link || fetching) return
    setFetching(item.link)
    try {
      const d = await fetchLuna<ArticleData>(`/api/luna/article?url=${encodeURIComponent(item.link)}`)
      setArticle(d)
    } catch {
      setArticle({ title: item.title, body: 'Could not load article content.', url: item.link })
    }
    setFetching(null)
  }

  const list = limit ? items.slice(0, limit) : items

  if (loading) return <div style={{ padding: 14, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>loading...</div>
  if (!list.length) return <div style={{ padding: 14, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>no feed</div>

  return (
    <>
      <AnimatePresence>
        {article && <ArticleReader article={article} onClose={() => setArticle(null)} />}
      </AnimatePresence>
      <div style={{ overflowY: 'auto', height: '100%', scrollbarWidth: 'none' }}>
        {list.map((item, i) => (
          <div key={i} role="button" tabIndex={0}
            onClick={() => openArticle(item)}
            style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '7px 10px', background: fetching === item.link ? 'rgba(139,92,246,0.11)' : 'transparent', borderBottom: `1px solid rgba(139,92,246,0.07)`, cursor: 'pointer', transition: 'background 0.12s' }}
            onMouseEnter={e => { if (fetching !== item.link) (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.07)' }}
            onMouseLeave={e => { if (fetching !== item.link) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            {item.image && (
              <img src={item.image} alt="" style={{ width: 52, height: 38, objectFit: 'cover', borderRadius: 3, flexShrink: 0, opacity: 0.88 }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, color: P.textDim, fontFamily: 'monospace', marginBottom: 3, letterSpacing: '0.1em' }}>
                {item.source.toUpperCase()}{fetching === item.link ? ' — LOADING...' : ''}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.72)', lineHeight: 1.45 }}>{item.title}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

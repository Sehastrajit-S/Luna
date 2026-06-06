import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Brain, Search, Trash2, Zap, Sparkles, Loader2, Network, List } from 'lucide-react'
import { useStore } from '../../store'
import { api } from '../../api/client'
import { Fact } from '../../types'
import { BrainMemoryCanvas } from './BrainMemoryCanvas'

const CATEGORY_COLORS: Record<string, string> = {
  personal:     'bg-violet-500/20 text-violet-300 border-violet-500/30',
  preference:   'bg-blue-500/20 text-blue-300 border-blue-500/30',
  relationship: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  event:        'bg-amber-500/20 text-amber-300 border-amber-500/30',
  goal:         'bg-green-500/20 text-green-300 border-green-500/30',
  health:       'bg-red-500/20 text-red-300 border-red-500/30',
}

const MOOD_DESCRIPTIONS: Record<string, string> = {
  happy: 'Bright and optimistic',
  playful: 'Lighthearted and witty',
  thoughtful: 'Reflective and deep',
  excited: 'Energetic and enthusiastic',
  concerned: 'Attentive and caring',
  warm: 'Cozy and connected',
  neutral: 'Calm and present',
  curious: 'Inquisitive and engaged',
  melancholic: 'Introspective and gentle',
}

function PersonalityCard() {
  const { personality } = useStore()
  if (!personality) return null

  const bars: { label: string; key: keyof typeof personality }[] = [
    { label: 'Verbosity', key: 'verbosity' },
    { label: 'Humor', key: 'humor' },
    { label: 'Depth', key: 'depth' },
    { label: 'Emotional support', key: 'emotional_support' },
    { label: 'Formality', key: 'formality' },
  ]

  return (
    <div className="bg-luna-card border border-luna-border rounded-2xl p-5 mb-4">
      <div className="flex items-center gap-2 mb-4">
        <Zap size={14} className="text-luna-primary" />
        <h3 className="text-sm font-semibold text-luna-text">Personality State</h3>
        <span className="ml-auto text-xs text-luna-muted capitalize">
          {personality.current_mood} · {Math.round(personality.mood_intensity * 100)}% intensity
        </span>
      </div>
      <p className="text-xs text-luna-dim mb-4 italic">
        {MOOD_DESCRIPTIONS[personality.current_mood] ?? 'Adapting…'}
      </p>
      <div className="space-y-2.5">
        {bars.map(({ label, key }) => {
          const val = personality[key] as number
          return (
            <div key={key}>
              <div className="flex justify-between text-[11px] text-luna-dim mb-1">
                <span>{label}</span>
                <span>{Math.round(val * 100)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-luna-border overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${val * 100}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-[10px] text-luna-dim mt-3 text-center">
        Adapted from {personality.total_interactions} interactions · energy {Math.round(personality.energy_level * 100)}%
      </p>
    </div>
  )
}

export function MemoryPanel() {
  const { facts, setFacts, personality, setPersonality } = useStore()
  const [view, setView] = useState<'list' | 'graph'>('list')
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [searchResults, setSearchResults] = useState<string[]>([])
  const [searching, setSearching] = useState(false)
  const [compacting, setCompacting] = useState(false)
  const [compactResult, setCompactResult] = useState<number | null>(null)

  useEffect(() => {
    api.getFacts().then(setFacts).catch(() => {})
    api.getPersonality().then(setPersonality).catch(() => {})
  }, [setFacts, setPersonality])

  const handleSearch = async () => {
    if (!search.trim()) { setSearchResults([]); return }
    setSearching(true)
    const res = await api.searchMemory(search)
    setSearchResults(res.results ?? [])
    setSearching(false)
  }

  const deleteFact = async (id: number) => {
    await api.deleteFact(id)
    setFacts(facts.filter(f => f.id !== id))
  }

  const filtered = facts.filter(f =>
    (!activeCategory || f.category === activeCategory) &&
    (!search || f.content.toLowerCase().includes(search.toLowerCase()))
  )

  const categories = [...new Set(facts.map(f => f.category))]

  const handleCompact = async () => {
    setCompacting(true)
    setCompactResult(null)
    try {
      const res = await api.compactMemory()
      setCompactResult(res.removed)
      if (res.removed > 0) {
        api.getFacts().then(setFacts).catch(() => {})
      }
    } catch {
      setCompactResult(0)
    } finally {
      setCompacting(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 pt-6 pb-4 flex-shrink-0">
        <Brain size={20} className="text-luna-primary" />
        <h2 className="text-lg font-semibold text-luna-text">Luna's Memory</h2>
        <span className="text-xs text-luna-dim">{facts.length} facts stored</span>
        {compactResult !== null && (
          <span className="text-[10px] text-luna-dim">
            {compactResult > 0 ? `−${compactResult} merged` : 'already compact'}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {view === 'list' && (
            <button
              onClick={handleCompact}
              disabled={compacting}
              title="Merge duplicate facts"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs bg-luna-card border border-luna-border text-luna-muted hover:text-luna-text hover:border-luna-primary/40 transition-all disabled:opacity-50"
            >
              {compacting ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
              Compact
            </button>
          )}
          <button
            onClick={() => setView(v => v === 'list' ? 'graph' : 'list')}
            title={view === 'list' ? 'Show brain graph' : 'Show list'}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs border transition-all ${
              view === 'graph'
                ? 'bg-luna-primary/20 border-luna-primary/40 text-luna-accent'
                : 'bg-luna-card border-luna-border text-luna-muted hover:text-luna-text hover:border-luna-primary/40'
            }`}
          >
            {view === 'list' ? <Network size={12} /> : <List size={12} />}
            {view === 'list' ? 'Graph' : 'List'}
          </button>
        </div>
      </div>

      {/* Brain graph view */}
      {view === 'graph' && (
        <div className="flex-1 min-h-0 px-6 pb-6">
          <BrainMemoryCanvas />
        </div>
      )}

      {/* List view */}
      {view === 'list' && <div className="flex-1 overflow-y-auto px-6 pb-6">

      <PersonalityCard />

      {/* Search */}
      <div className="flex gap-2 mb-4">
        <div className="flex-1 relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-luna-dim" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Search memories…"
            className="w-full bg-luna-card border border-luna-border rounded-xl pl-9 pr-4 py-2 text-sm text-luna-text placeholder-luna-dim outline-none focus:border-luna-primary/50 transition-all"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={searching}
          className="px-4 py-2 bg-luna-primary/20 hover:bg-luna-primary/30 border border-luna-primary/30 text-luna-accent rounded-xl text-sm transition-all"
        >
          Search
        </button>
      </div>

      {/* Semantic search results */}
      {searchResults.length > 0 && (
        <div className="mb-4 bg-luna-card border border-luna-border rounded-2xl p-4">
          <p className="text-xs text-luna-primary font-medium mb-2">Semantic matches</p>
          {searchResults.map((r, i) => (
            <p key={i} className="text-xs text-luna-muted py-1 border-b border-luna-border/50 last:border-0">{r}</p>
          ))}
        </div>
      )}

      {/* Category filter */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setActiveCategory(null)}
          className={`text-xs px-3 py-1 rounded-full border transition-all ${!activeCategory ? 'bg-luna-primary/20 border-luna-primary/30 text-luna-accent' : 'border-luna-border text-luna-dim hover:border-luna-primary/30'}`}
        >
          All
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat === activeCategory ? null : cat)}
            className={`text-xs px-3 py-1 rounded-full border transition-all capitalize ${
              activeCategory === cat
                ? 'bg-luna-primary/20 border-luna-primary/30 text-luna-accent'
                : 'border-luna-border text-luna-dim hover:border-luna-primary/30'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Facts grid */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-luna-dim text-sm">
            {facts.length === 0
              ? "Luna hasn't learned anything yet. Start chatting!"
              : "No facts match this filter."}
          </div>
        ) : (
          filtered.map(fact => (
            <motion.div
              key={fact.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 bg-luna-card border border-luna-border rounded-xl px-4 py-3 group hover:border-luna-primary/30 transition-all"
            >
              <div className="flex flex-col gap-1 flex-shrink-0 mt-0.5 items-end">
                <span className={`text-[10px] px-2 py-0.5 rounded-full border capitalize ${CATEGORY_COLORS[fact.category] ?? 'bg-luna-surface text-luna-dim border-luna-border'}`}>
                  {fact.category}
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border text-center ${
                  fact.memory_type === 'persistent'
                    ? 'bg-orange-500/15 text-orange-300 border-orange-500/30'
                    : fact.memory_type === 'short'
                    ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                    : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                }`}>
                  {fact.memory_type ?? 'long'}
                </span>
                {fact.expires_at && fact.memory_type !== 'long' && (() => {
                  const days = Math.ceil((new Date(fact.expires_at).getTime() - Date.now()) / 86400000)
                  return days > 0 ? (
                    <span className="text-[9px] text-luna-dim">{days}d left</span>
                  ) : null
                })()}
              </div>
              <p className="text-sm text-luna-text flex-1 leading-relaxed">{fact.content}</p>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-[10px] text-luna-dim opacity-0 group-hover:opacity-100">
                  {Math.round(fact.confidence * 100)}%
                </span>
                <button
                  onClick={() => deleteFact(fact.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:text-red-400"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>}
    </div>
  )
}

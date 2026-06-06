import { motion } from 'framer-motion'
import { MessageCircle, Brain, Calendar, Activity, Plus, Trash2, Clock, Dna, Moon, FlaskConical, ShieldCheck } from 'lucide-react'
import { useStore } from '../../store'
import { useChat } from '../../hooks/useChat'
import { View } from '../../types'
import { format } from 'date-fns'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'

const MOOD_EMOJI: Record<string, string> = {
  happy: '😊', playful: '😄', thoughtful: '🤔', excited: '✨',
  concerned: '💙', warm: '🌙', neutral: '😌', curious: '🔍', melancholic: '🌧',
}

const NAV: { id: View; icon: typeof MessageCircle; label: string }[] = [
  { id: 'chat',       icon: MessageCircle, label: 'Chat' },
  { id: 'memory',     icon: Brain,         label: 'Memory' },
  { id: 'calendar',   icon: Calendar,      label: 'Calendar' },
  { id: 'activities', icon: Activity,      label: 'Activities' },
  { id: 'agent',      icon: ShieldCheck,   label: 'Agent' },
  { id: 'sleep',      icon: Moon,          label: 'Sleep' },
  { id: 'train',      icon: Dna,           label: 'Train' },
  { id: 'extract',    icon: FlaskConical,  label: 'Extract' },
]

export function Sidebar() {
  const { activeView, setView, conversations, setConversations, activeConversationId, personality, ollamaOnline } = useStore()
  const { loadConversation, newConversation } = useChat()
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    api.listConversations().then(setConversations).catch(() => {})
  }, [setConversations])

  const deleteConv = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    await api.deleteConversation(id)
    setConversations(conversations.filter(c => c.id !== id))
    if (activeConversationId === id) newConversation()
  }

  const mood = personality?.current_mood ?? 'neutral'

  return (
    <div className="w-60 h-full flex flex-col bg-luna-surface border-r border-luna-border">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-luna-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-luna-card border border-luna-border flex items-center justify-center shadow-glow">
            <img src={`${import.meta.env.BASE_URL}images/logo.svg`} alt="" className="w-7 h-7" draggable={false} />
          </div>
          <div>
            <h1 className="text-luna-text font-semibold text-sm">Luna</h1>
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${ollamaOnline ? 'bg-green-400' : 'bg-red-400'}`} />
              <span className="text-luna-dim text-[10px]">
                {ollamaOnline ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Mood & time */}
      {personality && (
        <div className="px-4 py-3 border-b border-luna-border/50">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-luna-dim flex items-center gap-1">
              <span>{MOOD_EMOJI[mood]}</span>
              <span className="capitalize">{mood}</span>
            </span>
            <span className="text-[11px] text-luna-dim flex items-center gap-1">
              <Clock size={10} />
              {format(now, 'h:mm a')}
            </span>
          </div>
          <div className="mt-1.5 h-1 rounded-full bg-luna-border overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-1000"
              style={{ width: `${(personality.energy_level * 100).toFixed(0)}%` }}
            />
          </div>
          <p className="text-[9px] text-luna-dim mt-0.5">energy {Math.round(personality.energy_level * 100)}%</p>
        </div>
      )}

      {/* Navigation */}
      <nav className="px-3 py-3 space-y-1">
        {NAV.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setView(id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all ${
              activeView === id
                ? 'bg-luna-primary/20 text-luna-accent border border-luna-primary/30'
                : 'text-luna-muted hover:bg-luna-card hover:text-luna-text'
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>

      {/* New conversation */}
      <div className="px-3 mb-2">
        <button
          onClick={newConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-luna-dim hover:text-luna-text hover:bg-luna-card transition-all border border-dashed border-luna-border/60 hover:border-luna-primary/40"
        >
          <Plus size={13} />
          New conversation
        </button>
      </div>

      {/* Conversation history */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5">
        {conversations.slice(0, 20).map((conv) => (
          <motion.button
            key={conv.id}
            onClick={() => { loadConversation(conv.id); setView('chat') }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className={`w-full text-left px-3 py-2 rounded-xl group transition-all flex items-start justify-between gap-2 ${
              activeConversationId === conv.id
                ? 'bg-luna-card border border-luna-border text-luna-text'
                : 'text-luna-dim hover:bg-luna-card hover:text-luna-text'
            }`}
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs truncate">
                {conv.title ?? format(new Date(conv.started_at), 'MMM d, h:mm a')}
              </p>
              <p className="text-[10px] text-luna-dim mt-0.5">{conv.message_count} messages</p>
            </div>
            <button
              onClick={(e) => deleteConv(e, conv.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:text-red-400 flex-shrink-0"
            >
              <Trash2 size={11} />
            </button>
          </motion.button>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-luna-border">
        <p className="text-[10px] text-luna-dim text-center">
          {personality?.total_interactions ?? 0} total interactions
        </p>
      </div>
    </div>
  )
}

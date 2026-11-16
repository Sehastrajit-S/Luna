import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Moon, Sun, Clock, TrendingUp, Bed } from 'lucide-react'
import { authHeaders } from '../../api/client'
import { format, parseISO, differenceInMinutes } from 'date-fns'

interface SleepLog {
  id: number
  sleep_start: string
  sleep_end: string | null
  duration_minutes: number | null
  label: string
}

interface Stats {
  total_nights: number
  avg_duration_minutes: number | null
  longest_minutes: number | null
  shortest_minutes: number | null
  recent_logs: SleepLog[]
}

function fmtDuration(mins: number | null) {
  if (!mins) return '—'
  const h = Math.floor(mins / 60)
  const m = Math.round(mins % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  return format(parseISO(iso), 'h:mm a')
}

function qualityColor(mins: number | null) {
  if (!mins) return 'text-luna-dim'
  if (mins >= 420) return 'text-green-400'   // 7+ hours
  if (mins >= 360) return 'text-amber-400'   // 6+ hours
  return 'text-red-400'                      // < 6 hours
}

function SleepBar({ log }: { log: SleepLog }) {
  const start = parseISO(log.sleep_start)
  const end   = log.sleep_end ? parseISO(log.sleep_end) : null
  const dur   = log.duration_minutes
  const isOpen = !end

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-4 py-3 border-b border-luna-border/40 last:border-0"
    >
      {/* Date */}
      <div className="w-24 shrink-0">
        <p className="text-xs text-luna-text font-mono">{format(start, 'EEE, MMM d')}</p>
        <p className="text-[10px] text-luna-dim/60 capitalize">{log.label}</p>
      </div>

      {/* Sleep/wake times */}
      <div className="flex items-center gap-2 flex-1">
        <div className="flex items-center gap-1">
          <Moon size={10} className="text-indigo-400" />
          <span className="text-xs font-mono text-luna-dim">{fmtTime(log.sleep_start)}</span>
        </div>
        <span className="text-luna-dim/30 text-xs">→</span>
        <div className="flex items-center gap-1">
          <Sun size={10} className={isOpen ? 'text-luna-dim/30' : 'text-amber-400'} />
          <span className={`text-xs font-mono ${isOpen ? 'text-luna-dim/40' : 'text-luna-dim'}`}>
            {isOpen ? 'ongoing' : fmtTime(log.sleep_end)}
          </span>
        </div>
      </div>

      {/* Duration */}
      <div className="shrink-0 text-right">
        <span className={`text-sm font-mono font-light ${qualityColor(dur)}`}>
          {fmtDuration(dur)}
        </span>
      </div>
    </motion.div>
  )
}

export function SleepView() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [allLogs, setAllLogs] = useState<SleepLog[]>([])
  const [loading, setLoading] = useState(true)
  const base = window.electronAPI?.apiBase ?? ''

  useEffect(() => {
    const headers = authHeaders()
    Promise.all([
      fetch(`${base}/api/sleep/stats`, { headers }).then(r => r.json()),
      fetch(`${base}/api/sleep/logs?days=30`, { headers }).then(r => r.json()),
    ]).then(([s, l]) => {
      setStats(s)
      setAllLogs(l.logs ?? [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [base])

  if (loading) return (
    <div className="h-full flex items-center justify-center text-luna-dim text-sm">Loading...</div>
  )

  const bedtimeLogs = allLogs.filter(l => l.label === 'bedtime')

  return (
    <div className="h-full overflow-y-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Moon size={16} className="text-indigo-400" />
        <h2 className="text-sm font-semibold text-luna-text">Sleep Tracking</h2>
        <span className="text-[10px] text-luna-dim bg-luna-surface px-2 py-0.5 rounded-full border border-luna-border">
          last 30 days
        </span>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Avg sleep', value: fmtDuration(stats.avg_duration_minutes), icon: Clock, color: 'text-violet-400' },
            { label: 'Longest',   value: fmtDuration(stats.longest_minutes),       icon: TrendingUp, color: 'text-green-400' },
            { label: 'Nights',    value: stats.total_nights.toString(),             icon: Bed, color: 'text-indigo-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-luna-card border border-luna-border rounded-xl p-3.5">
              <div className="flex items-center gap-1.5 mb-1">
                <Icon size={11} className={color} />
                <span className="text-[10px] text-luna-dim uppercase tracking-wider">{label}</span>
              </div>
              <p className={`text-xl font-light font-mono ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Sleep quality hint */}
      {stats?.avg_duration_minutes && (
        <div className={`text-xs px-3 py-2 rounded-lg border ${
          stats.avg_duration_minutes >= 420
            ? 'bg-green-500/8 border-green-500/20 text-green-400/80'
            : stats.avg_duration_minutes >= 360
              ? 'bg-amber-500/8 border-amber-500/20 text-amber-400/80'
              : 'bg-red-500/8 border-red-500/20 text-red-400/80'
        }`}>
          {stats.avg_duration_minutes >= 420
            ? 'Averaging 7+ hours — solid sleep.'
            : stats.avg_duration_minutes >= 360
              ? 'Averaging 6-7 hours — a bit short.'
              : 'Averaging under 6 hours — try to get more rest.'}
        </div>
      )}

      {/* Log */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-luna-dim/60 mb-3">Sleep log</p>
        {bedtimeLogs.length === 0 ? (
          <div className="text-center py-10">
            <Moon size={28} className="text-luna-dim/20 mx-auto mb-3" />
            <p className="text-luna-dim text-sm">No sleep recorded yet.</p>
            <p className="text-luna-dim/50 text-xs mt-1">Say "going to bed" or "good night" and Luna will start tracking.</p>
          </div>
        ) : (
          <div className="bg-luna-card border border-luna-border rounded-xl px-4 py-1">
            {bedtimeLogs.map(log => <SleepBar key={log.id} log={log} />)}
          </div>
        )}
      </div>

      {/* Away sessions (non-bedtime) */}
      {allLogs.filter(l => l.label !== 'bedtime').length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-luna-dim/60 mb-3">Away sessions</p>
          <div className="bg-luna-card border border-luna-border rounded-xl px-4 py-1">
            {allLogs.filter(l => l.label !== 'bedtime').map(log => <SleepBar key={log.id} log={log} />)}
          </div>
        </div>
      )}
    </div>
  )
}

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, CheckCircle, Clock, Pause, XCircle } from 'lucide-react'
import { useStore } from '../../store'
import { api } from '../../api/client'
import { format, parseISO, formatDistanceToNow } from 'date-fns'
import { Activity as ActivityType } from '../../types'

const STATUS_ICONS: Record<string, React.ReactNode> = {
  in_progress: <Clock size={14} className="text-amber-400" />,
  done:        <CheckCircle size={14} className="text-green-400" />,
  paused:      <Pause size={14} className="text-blue-400" />,
  abandoned:   <XCircle size={14} className="text-luna-dim" />,
}

const CATEGORY_COLORS: Record<string, string> = {
  work:          'bg-violet-500/20 text-violet-300',
  study:         'bg-blue-500/20 text-blue-300',
  personal:      'bg-pink-500/20 text-pink-300',
  creative:      'bg-amber-500/20 text-amber-300',
  health:        'bg-green-500/20 text-green-300',
  social:        'bg-cyan-500/20 text-cyan-300',
  errands:       'bg-orange-500/20 text-orange-300',
  entertainment: 'bg-red-500/20 text-red-300',
}

function ActivityCard({ activity }: { activity: ActivityType }) {
  const started = activity.started_at ? parseISO(activity.started_at) : null
  const elapsed = started ? formatDistanceToNow(started, { addSuffix: false }) : null
  const notes = activity.progress_notes ?? []

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-luna-card border rounded-2xl p-4 ${
        activity.status === 'in_progress' ? 'border-amber-500/30' : 'border-luna-border'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{STATUS_ICONS[activity.status]}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-medium text-luna-text">{activity.title}</h3>
            {activity.category && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full capitalize ${CATEGORY_COLORS[activity.category] ?? 'bg-luna-surface text-luna-dim'}`}>
                {activity.category}
              </span>
            )}
            <span className="ml-auto text-[10px] text-luna-dim capitalize">{activity.status.replace('_', ' ')}</span>
          </div>
          {activity.description && (
            <p className="text-xs text-luna-dim mt-1">{activity.description}</p>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-luna-dim">
            {elapsed && <span>Started {elapsed} ago</span>}
            {activity.status === 'done' && activity.completed_at && (
              <span>Completed {format(parseISO(activity.completed_at), 'h:mm a')}</span>
            )}
          </div>

          {/* Progress notes */}
          {notes.length > 0 && (
            <div className="mt-3 space-y-1.5 border-t border-luna-border/50 pt-2">
              {notes.slice(-3).map((note, i) => (
                <div key={i} className="flex gap-2">
                  <div className="w-1 h-1 rounded-full bg-luna-primary mt-1.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-luna-muted">{note.note}</p>
                    <p className="text-[10px] text-luna-dim">
                      {formatDistanceToNow(parseISO(note.ts), { addSuffix: true })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export function ActivitiesView() {
  const { activities, setActivities } = useStore()

  useEffect(() => {
    api.getActivities().then(setActivities).catch(() => {})
  }, [setActivities])

  const active = activities.filter(a => a.status === 'in_progress')
  const completed = activities.filter(a => a.status === 'done')
  const other = activities.filter(a => a.status !== 'in_progress' && a.status !== 'done')

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Activity size={20} className="text-luna-primary" />
        <h2 className="text-lg font-semibold text-luna-text">Activities</h2>
        <span className="ml-auto text-xs text-luna-dim">{active.length} in progress</span>
      </div>

      {active.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-amber-400 mb-2">In Progress</p>
          <div className="space-y-3">
            {active.map(a => <ActivityCard key={a.id} activity={a} />)}
          </div>
        </div>
      )}

      {completed.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-green-400 mb-2">Completed</p>
          <div className="space-y-3">
            {completed.slice(0, 10).map(a => <ActivityCard key={a.id} activity={a} />)}
          </div>
        </div>
      )}

      {other.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-luna-dim mb-2">Paused / Abandoned</p>
          <div className="space-y-3">
            {other.map(a => <ActivityCard key={a.id} activity={a} />)}
          </div>
        </div>
      )}

      {activities.length === 0 && (
        <div className="text-center py-16 text-luna-dim">
          <Activity size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No activities tracked yet.</p>
          <p className="text-xs mt-1">Tell Luna what you're working on — she'll track it.</p>
        </div>
      )}
    </div>
  )
}

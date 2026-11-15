import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Calendar, CheckCircle2, Circle, Trash2, Plus, Clock, MapPin, Repeat, ChevronRight } from 'lucide-react'
import { useStore } from '../../store'
import { api } from '../../api/client'
import { format, isToday, isTomorrow, isPast, isThisWeek, parseISO, formatDistanceToNow, differenceInMinutes, isAfter } from 'date-fns'
import { Task, CalendarEvent } from '../../types'

const PRIORITY_COLORS: Record<string, string> = {
  low:    'text-blue-400 bg-blue-500/10 border-blue-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  high:   'text-red-400 bg-red-500/10 border-red-500/20',
}

const PRIORITY_BAR: Record<string, string> = {
  low: 'bg-blue-500/40', medium: 'bg-amber-500/60', high: 'bg-red-500/70',
}

function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-2xl font-light font-mono tabular-nums text-luna-text">
        {format(now, 'h:mm')}
        <span className="text-luna-dim text-lg">{format(now, ':ss')}</span>
      </span>
      <span className="text-xs text-luna-dim font-mono">{format(now, 'a')}</span>
    </div>
  )
}

function EventCard({ event, onDelete }: { event: CalendarEvent; onDelete: (id: number) => void }) {
  const start = parseISO(event.start_datetime)
  const end   = event.end_datetime ? parseISO(event.end_datetime) : null
  const now   = new Date()
  const isNow = end ? isAfter(now, start) && isAfter(end, now) : false
  const upcoming = isAfter(start, now) && differenceInMinutes(start, now) <= 120

  let dateLabel = ''
  if (isToday(start))       dateLabel = 'Today'
  else if (isTomorrow(start)) dateLabel = 'Tomorrow'
  else                        dateLabel = format(start, 'EEE, MMM d')

  const duration = end ? differenceInMinutes(end, start) : null
  const durationLabel = duration
    ? duration < 60 ? `${duration}m` : `${Math.floor(duration / 60)}h${duration % 60 ? ` ${duration % 60}m` : ''}`
    : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative flex gap-3 p-4 rounded-xl border transition-all group ${
        isNow
          ? 'border-violet-500/40 bg-violet-500/8'
          : 'border-luna-border bg-luna-card hover:border-luna-primary/30'
      }`}
    >
      {/* Time bar accent */}
      <div className={`w-0.5 rounded-full self-stretch flex-shrink-0 ${isNow ? 'bg-violet-500' : 'bg-luna-border'}`} />

      <div className="flex-1 min-w-0">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-luna-text leading-snug">{event.title}</p>
          <button
            onClick={() => onDelete(event.id)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:text-red-400 flex-shrink-0 -mt-0.5"
          >
            <Trash2 size={11} />
          </button>
        </div>

        {event.description && (
          <p className="text-xs text-luna-dim mt-0.5 line-clamp-2">{event.description}</p>
        )}

        {/* Time row */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
          <div className="flex items-center gap-1 text-xs font-mono">
            <Clock size={10} className={isNow ? 'text-violet-400' : 'text-luna-dim'} />
            <span className={isNow ? 'text-violet-300' : 'text-luna-accent'}>
              {format(start, 'h:mm a')}
            </span>
            {end && (
              <span className="text-luna-dim">
                <ChevronRight size={9} className="inline" />
                {format(end, 'h:mm a')}
              </span>
            )}
          </div>

          {durationLabel && (
            <span className="text-[10px] text-luna-dim bg-luna-surface px-1.5 py-0.5 rounded-full border border-luna-border">
              {durationLabel}
            </span>
          )}

          <span className="text-[10px] text-luna-dim">{dateLabel}</span>

          {isNow && (
            <span className="text-[10px] text-violet-400 bg-violet-500/15 px-1.5 py-0.5 rounded-full border border-violet-500/25 font-mono">
              now
            </span>
          )}
          {upcoming && !isNow && (
            <span className="text-[10px] text-amber-400/70">
              in {formatDistanceToNow(start)}
            </span>
          )}
        </div>

        {/* Location / recurrence */}
        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          {event.location && (
            <span className="flex items-center gap-1 text-[10px] text-luna-dim">
              <MapPin size={9} /> {event.location}
            </span>
          )}
          {event.recurring && (
            <span className="flex items-center gap-1 text-[10px] text-luna-accent bg-luna-primary/10 px-1.5 py-0.5 rounded-full capitalize">
              <Repeat size={9} /> {event.recurring}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function groupEventsByDate(events: CalendarEvent[]) {
  const groups: { label: string; events: CalendarEvent[] }[] = []
  const map = new Map<string, CalendarEvent[]>()

  for (const e of events) {
    const d = parseISO(e.start_datetime)
    const key = isToday(d) ? '__today__' : isTomorrow(d) ? '__tomorrow__' : format(d, 'yyyy-MM-dd')
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(e)
  }

  // Sort keys: today first, then tomorrow, then by date
  const keys = Array.from(map.keys()).sort((a, b) => {
    if (a === '__today__') return -1
    if (b === '__today__') return 1
    if (a === '__tomorrow__') return -1
    if (b === '__tomorrow__') return 1
    return a.localeCompare(b)
  })

  for (const key of keys) {
    const label =
      key === '__today__'    ? 'Today' :
      key === '__tomorrow__' ? 'Tomorrow' :
      format(parseISO(key), 'EEEE, MMMM d')
    groups.push({ label, events: map.get(key)! })
  }
  return groups
}

function TaskItem({ task, onComplete, onDelete }: { task: Task; onComplete: (id: number) => void; onDelete: (id: number) => void }) {
  const due = task.due_date ? parseISO(task.due_date) : null
  const overdue = due && isPast(due) && !task.completed

  let dueLabel = ''
  let dueDetail = ''
  if (due) {
    if (isToday(due))       { dueLabel = 'Today';    dueDetail = format(due, 'h:mm a') }
    else if (isTomorrow(due)) { dueLabel = 'Tomorrow'; dueDetail = format(due, 'h:mm a') }
    else                      { dueLabel = format(due, 'MMM d'); dueDetail = format(due, 'h:mm a') }
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all group ${
        task.completed
          ? 'opacity-40 border-luna-border/40 bg-luna-card'
          : overdue
            ? 'border-red-500/30 bg-red-500/5'
            : 'border-luna-border bg-luna-card hover:border-luna-primary/30'
      }`}
    >
      {/* Priority bar */}
      {!task.completed && (
        <div className={`w-0.5 self-stretch rounded-full flex-shrink-0 ${PRIORITY_BAR[task.priority] ?? 'bg-luna-border'}`} />
      )}

      <button onClick={() => onComplete(task.id)} className="flex-shrink-0 mt-0.5">
        {task.completed
          ? <CheckCircle2 size={15} className="text-green-400" />
          : <Circle size={15} className="text-luna-dim hover:text-luna-primary transition-colors" />
        }
      </button>

      <div className="flex-1 min-w-0">
        <p className={`text-sm leading-snug ${task.completed ? 'line-through text-luna-dim' : 'text-luna-text'}`}>
          {task.title}
        </p>
        {task.description && (
          <p className="text-xs text-luna-dim mt-0.5 line-clamp-2">{task.description}</p>
        )}
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          {dueLabel && (
            <span className={`flex items-center gap-1 text-[10px] font-mono ${overdue ? 'text-red-400' : 'text-luna-dim'}`}>
              <Clock size={9} />
              {dueLabel}
              {dueDetail && <span className="opacity-60">· {dueDetail}</span>}
            </span>
          )}
          <span className={`text-[10px] capitalize px-1.5 py-0.5 rounded-full border ${PRIORITY_COLORS[task.priority]}`}>
            {task.priority}
          </span>
          {overdue && (
            <span className="text-[10px] text-red-400/70">overdue</span>
          )}
        </div>
      </div>

      <button
        onClick={() => onDelete(task.id)}
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:text-red-400 flex-shrink-0 mt-0.5"
      >
        <Trash2 size={11} />
      </button>
    </motion.div>
  )
}

export function CalendarView() {
  const { tasks, events, setTasks, setEvents } = useStore()
  const [newTask, setNewTask] = useState('')
  const [activeTab, setActiveTab] = useState<'tasks' | 'events'>('tasks')

  useEffect(() => {
    api.getTasks().then(setTasks).catch(() => {})
    api.getEvents().then(setEvents).catch(() => {})
  }, [setTasks, setEvents])

  const addTask = async () => {
    if (!newTask.trim()) return
    const t = await api.createTask({ title: newTask.trim() })
    setTasks([t, ...tasks])
    setNewTask('')
  }

  const completeTask = async (id: number) => {
    await api.completeTask(id)
    setTasks(tasks.map(t => t.id === id ? { ...t, completed: true } : t))
  }

  const deleteTask = async (id: number) => {
    await api.deleteTask(id)
    setTasks(tasks.filter(t => t.id !== id))
  }

  const deleteEvent = async (id: number) => {
    await api.deleteEvent(id)
    setEvents(events.filter(e => e.id !== id))
  }

  const pending  = tasks.filter(t => !t.completed)
  const done     = tasks.filter(t => t.completed)
  const overdue  = pending.filter(t => t.due_date && isPast(parseISO(t.due_date)))
  const dueToday = pending.filter(t => t.due_date && isToday(parseISO(t.due_date)))
  const eventGroups = groupEventsByDate(
    [...events].sort((a, b) => parseISO(a.start_datetime).getTime() - parseISO(b.start_datetime).getTime())
  )
  const todayEvents = events.filter(e => isToday(parseISO(e.start_datetime)))

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-luna-border shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Calendar size={15} className="text-luna-primary" />
              <span className="text-xs text-luna-dim font-mono uppercase tracking-widest">
                {format(new Date(), 'EEEE, MMMM d')}
              </span>
            </div>
            <LiveClock />
          </div>
          {/* Today summary chips */}
          <div className="flex flex-col items-end gap-1">
            {todayEvents.length > 0 && (
              <span className="text-[10px] text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded-full">
                {todayEvents.length} event{todayEvents.length > 1 ? 's' : ''} today
              </span>
            )}
            {overdue.length > 0 && (
              <span className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
                {overdue.length} overdue
              </span>
            )}
            {dueToday.length > 0 && (
              <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                {dueToday.length} due today
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="px-6 py-4">
        {/* Tabs */}
        <div className="flex gap-1 mb-5 bg-luna-surface rounded-xl p-1">
          {(['tasks', 'events'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                activeTab === tab ? 'bg-luna-card text-luna-text shadow' : 'text-luna-dim hover:text-luna-text'
              }`}
            >
              {tab === 'tasks' ? `Tasks (${pending.length})` : `Events (${events.length})`}
            </button>
          ))}
        </div>

        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <input
                value={newTask}
                onChange={e => setNewTask(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addTask()}
                placeholder="Add a task…"
                className="flex-1 bg-luna-card border border-luna-border rounded-xl px-4 py-2.5 text-sm text-luna-text placeholder-luna-dim outline-none focus:border-luna-primary/50 transition-all"
              />
              <button
                onClick={addTask}
                className="px-4 py-2.5 bg-luna-primary/20 hover:bg-luna-primary/30 border border-luna-primary/30 text-luna-accent rounded-xl transition-all"
              >
                <Plus size={16} />
              </button>
            </div>

            {/* Overdue section */}
            {overdue.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-red-400/70 mb-2">Overdue</p>
                <div className="space-y-2">
                  {overdue.map(t => (
                    <TaskItem key={t.id} task={t} onComplete={completeTask} onDelete={deleteTask} />
                  ))}
                </div>
              </div>
            )}

            {/* Pending section */}
            <div>
              {overdue.length > 0 && pending.length > overdue.length && (
                <p className="text-[10px] uppercase tracking-wider text-luna-dim/60 mb-2">Upcoming</p>
              )}
              <div className="space-y-2">
                {pending.filter(t => !overdue.includes(t)).length === 0 && overdue.length === 0 ? (
                  <p className="text-center py-8 text-luna-dim text-sm">All clear.</p>
                ) : (
                  pending.filter(t => !overdue.includes(t)).map(t => (
                    <TaskItem key={t.id} task={t} onComplete={completeTask} onDelete={deleteTask} />
                  ))
                )}
              </div>
            </div>

            {/* Completed */}
            {done.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-luna-dim/60 mb-2 mt-2">
                  Completed ({done.length})
                </p>
                <div className="space-y-2">
                  {done.slice(0, 5).map(t => (
                    <TaskItem key={t.id} task={t} onComplete={completeTask} onDelete={deleteTask} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'events' && (
          <div className="space-y-5">
            {eventGroups.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-luna-dim text-sm">No events scheduled.</p>
                <p className="text-luna-dim/50 text-xs mt-1">Ask Luna to add events for you.</p>
              </div>
            ) : (
              eventGroups.map(group => (
                <div key={group.label}>
                  <p className={`text-[10px] uppercase tracking-wider mb-2 ${
                    group.label === 'Today' ? 'text-violet-400/80' : 'text-luna-dim/60'
                  }`}>
                    {group.label}
                  </p>
                  <div className="space-y-2">
                    {group.events.map(e => (
                      <EventCard key={e.id} event={e} onDelete={deleteEvent} />
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { format, parseISO } from 'date-fns'
import {
  Target, Play, Pause, Check, LifeBuoy, SkipForward, Mic, MicOff, Inbox, ListChecks,
  Timer, TrendingUp, ScrollText, Trash2, Plus, X,
} from 'lucide-react'
import { useMomentum } from '../../store/momentum'
import { useNextStep, useDoneToday, useFocusRemaining, useSpeech } from './hooks'
import { splitBrainDump, fmtClock, isToday, Energy } from './logic'

const TIME_CHIPS = [5, 10, 25, 60]
const ENERGY_CHIPS: Energy[] = ['low', 'medium', 'high']
const FOCUS_PRESETS = [5, 10, 25]

function Card({ icon: Icon, title, right, children, className = '' }: {
  icon: typeof Target; title: string; right?: React.ReactNode; children: React.ReactNode; className?: string
}) {
  return (
    <div className={`bg-luna-card border border-luna-border rounded-xl p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <Icon size={12} className="text-luna-accent" />
          <span className="text-[10px] uppercase tracking-wider text-luna-dim">{title}</span>
        </div>
        {right}
      </div>
      {children}
    </div>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-full text-[11px] border transition-all ${
        active
          ? 'bg-luna-primary/20 text-luna-accent border-luna-primary/30'
          : 'text-luna-dim border-luna-border hover:text-luna-text'
      }`}
    >
      {children}
    </button>
  )
}

export function MomentumView() {
  const m = useMomentum()
  const next = useNextStep()
  const doneToday = useDoneToday()
  const remaining = useFocusRemaining()

  const [dump, setDump] = useState('')
  const [picked, setPicked] = useState<Record<number, boolean>>({})
  const [newTask, setNewTask] = useState('')
  const [confirmClear, setConfirmClear] = useState(false)
  const [focusMinutes, setFocusMinutes] = useState(10)
  const speech = useSpeech(setDump)

  const focusStep = m.focus ? m.steps.find(s => s.id === m.focus!.stepId) : null
  const currentTask = focusStep
    ? m.tasks.find(t => t.id === focusStep.taskId)
    : next?.task
  const currentSteps = currentTask
    ? m.steps.filter(s => s.taskId === currentTask.id).sort((a, b) => a.order - b.order)
    : []

  const week = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date()
      d.setDate(d.getDate() - (6 - i))
      return d
    })
    return days.map(d => ({
      label: format(d, 'EEEEE'),
      count: m.steps.filter(s => s.done && s.doneAt && new Date(s.doneAt).toDateString() === d.toDateString()).length,
    }))
  }, [m.steps])
  const weekMax = Math.max(1, ...week.map(w => w.count))
  const focusToday = m.sessions.filter(s => isToday(s.endedAt)).reduce((n, s) => n + s.minutes, 0)
  const openTasks = m.tasks.filter(t => !t.done)

  const capture = () => {
    const items = splitBrainDump(dump)
    if (!items.length) return
    if (speech.listening) speech.toggle()
    m.captureBrainDump(items)
    setDump('')
    setPicked({})
  }

  const saveInbox = () => {
    const keep = m.inbox.filter((_, i) => picked[i] !== false)
    if (keep.length) m.acceptInbox(keep)
    else m.discardInbox()
    setPicked({})
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Target size={16} className="text-luna-accent" />
        <h2 className="text-sm font-semibold text-luna-text">Momentum</h2>
        <span className="text-[10px] text-luna-dim bg-luna-surface px-2 py-0.5 rounded-full border border-luna-border">
          Stop overthinking. Start with one step.
        </span>
      </div>

      {/* Time + energy */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-luna-dim mr-1">I have</span>
          {TIME_CHIPS.map(t => (
            <Chip key={t} active={m.availableMinutes === t} onClick={() => m.setAvailableMinutes(t)}>
              {t === 60 ? '1h+' : `${t} min`}
            </Chip>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-luna-dim mr-1">Energy</span>
          {ENERGY_CHIPS.map(e => (
            <Chip key={e} active={m.energy === e} onClick={() => m.setEnergy(e)}>{e}</Chip>
          ))}
        </div>
      </div>

      {/* Today's focus + timer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card icon={Target} title="Today's focus" className="lg:col-span-2">
          {focusStep && m.focus ? (
            <div className="space-y-3">
              <p className="text-[11px] text-luna-dim">{currentTask?.title}</p>
              <p className="text-lg text-luna-text font-light">{focusStep.text}</p>
              <div className="flex items-center gap-4">
                <span className={`text-3xl font-mono font-light ${remaining === 0 ? 'text-green-400' : 'text-luna-accent'}`}>
                  {fmtClock(remaining ?? 0)}
                </span>
                <div className="h-1.5 flex-1 rounded-full bg-luna-border overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-1000"
                    style={{ width: `${100 - ((remaining ?? 0) / m.focus.durationMs) * 100}%` }}
                  />
                </div>
              </div>
              {remaining === 0 && <p className="text-xs text-green-400">Time's up. Did you finish it?</p>}
              <div className="flex gap-2">
                {m.focus.endsAt
                  ? <ActionBtn onClick={m.pauseFocus} icon={Pause}>Pause</ActionBtn>
                  : <ActionBtn onClick={m.resumeFocus} icon={Play}>Resume</ActionBtn>}
                <ActionBtn primary onClick={() => m.endFocus(true)} icon={Check}>Done</ActionBtn>
                <ActionBtn onClick={() => m.endFocus(false)} icon={X}>Stop</ActionBtn>
              </div>
            </div>
          ) : next ? (
            <div className="space-y-3">
              <p className="text-[11px] text-luna-dim">{next.task.title}</p>
              <p className="text-lg text-luna-text font-light">{next.step.text}</p>
              <p className="text-xs text-luna-dim">
                About {next.step.minutes} min
                {next.step.minutes <= m.availableMinutes ? ' · fits your time' : ' · a bit longer than you have'}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <ActionBtn primary onClick={() => m.startFocus(next.step.id, focusMinutes)} icon={Play}>
                  Start {focusMinutes} min
                </ActionBtn>
                <ActionBtn onClick={() => m.completeStep(next.step.id)} icon={Check}>Already done</ActionBtn>
                <ActionBtn onClick={() => m.getUnstuck(next.step.id)} icon={LifeBuoy}>I'm stuck</ActionBtn>
                <ActionBtn onClick={() => m.skipStep(next.step.id)} icon={SkipForward}>Not now</ActionBtn>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center">
              <Target size={26} className="text-luna-dim/20 mx-auto mb-3" />
              <p className="text-sm text-luna-dim">What's on your mind?</p>
              <p className="text-xs text-luna-dim/50 mt-1">Dump everything below. Luna will pick one small step.</p>
            </div>
          )}
        </Card>

        <Card icon={Timer} title="Focus session">
          <div className="space-y-3">
            <div className="flex gap-1.5">
              {FOCUS_PRESETS.map(p => (
                <Chip key={p} active={focusMinutes === p} onClick={() => setFocusMinutes(p)}>{p} min</Chip>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Focus today" value={`${focusToday}m`} />
              <Stat label="Sessions" value={String(m.sessions.filter(s => isToday(s.endedAt)).length)} />
            </div>
          </div>
        </Card>
      </div>

      {/* Brain dump + inbox */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          icon={Mic}
          title="Brain dump"
          right={speech.supported && (
            <button
              onClick={speech.toggle}
              className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${
                speech.listening ? 'text-red-400 border-red-400/40' : 'text-luna-dim border-luna-border hover:text-luna-text'
              }`}
            >
              {speech.listening ? <><MicOff size={10} /> Stop</> : <><Mic size={10} /> Speak</>}
            </button>
          )}
        >
          <textarea
            value={dump}
            onChange={e => setDump(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) capture() }}
            placeholder="finish my essay due today, clean my room, email Sam..."
            rows={4}
            className="w-full bg-luna-surface border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text placeholder:text-luna-dim/50 resize-none focus:outline-none focus:border-luna-primary/40"
          />
          <div className="flex justify-end mt-2">
            <ActionBtn primary onClick={capture} icon={Inbox}>Capture</ActionBtn>
          </div>
        </Card>

        <Card icon={Inbox} title="Review" right={m.inbox.length > 0 && <span className="text-[10px] text-luna-accent">{m.inbox.length} new</span>}>
          {m.inbox.length === 0 ? (
            <p className="text-xs text-luna-dim py-4 text-center">Nothing to review.</p>
          ) : (
            <div className="space-y-2">
              {m.inbox.map((item, i) => (
                <label key={i} className="flex items-center gap-2 text-sm text-luna-text cursor-pointer">
                  <input
                    type="checkbox"
                    checked={picked[i] !== false}
                    onChange={e => setPicked(p => ({ ...p, [i]: e.target.checked }))}
                    className="accent-violet-500"
                  />
                  {item}
                </label>
              ))}
              <div className="flex justify-end gap-2 pt-2">
                <ActionBtn onClick={m.discardInbox} icon={X}>Discard</ActionBtn>
                <ActionBtn primary onClick={saveInbox} icon={Check}>Save & break down</ActionBtn>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Tiny steps + tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card icon={ListChecks} title={currentTask ? `Tiny steps · ${currentTask.title}` : 'Tiny steps'}>
          {currentSteps.length === 0 ? (
            <p className="text-xs text-luna-dim py-4 text-center">Steps show up here once you add a task.</p>
          ) : (
            <div className="space-y-1">
              {currentSteps.map(s => (
                <motion.button
                  key={s.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  onClick={() => !s.done && m.completeStep(s.id)}
                  className="w-full flex items-center gap-2 py-1.5 text-left group"
                >
                  <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                    s.done ? 'bg-green-500/20 border-green-500/40' : 'border-luna-border group-hover:border-luna-primary/40'
                  }`}>
                    {s.done && <Check size={10} className="text-green-400" />}
                  </span>
                  <span className={`text-sm flex-1 ${s.done ? 'text-luna-dim line-through' : 'text-luna-text'}`}>{s.text}</span>
                  <span className="text-[10px] font-mono text-luna-dim">{s.minutes}m</span>
                </motion.button>
              ))}
            </div>
          )}
        </Card>

        <Card icon={ListChecks} title="All tasks" right={<span className="text-[10px] text-luna-dim">{openTasks.length} open</span>}>
          <form
            onSubmit={e => { e.preventDefault(); if (newTask.trim()) { m.addTask(newTask.trim()); setNewTask('') } }}
            className="flex gap-2 mb-3"
          >
            <input
              value={newTask}
              onChange={e => setNewTask(e.target.value)}
              placeholder="Add one task"
              className="flex-1 bg-luna-surface border border-luna-border rounded-lg px-3 py-1.5 text-sm text-luna-text placeholder:text-luna-dim/50 focus:outline-none focus:border-luna-primary/40"
            />
            <button type="submit" className="p-2 rounded-lg border border-luna-border text-luna-dim hover:text-luna-text"><Plus size={13} /></button>
          </form>
          <div className="space-y-1 max-h-56 overflow-y-auto">
            {m.tasks.map(t => {
              const ts = m.steps.filter(s => s.taskId === t.id)
              const done = ts.filter(s => s.done).length
              return (
                <div key={t.id} className="flex items-center gap-2 py-1.5 group">
                  <span className={`text-sm flex-1 truncate ${t.done ? 'text-luna-dim line-through' : 'text-luna-text'}`}>{t.title}</span>
                  {t.urgency === 3 && !t.done && <span className="text-[9px] px-1.5 rounded-full bg-amber-500/15 text-amber-400">today</span>}
                  <span className="text-[10px] font-mono text-luna-dim">{done}/{ts.length}</span>
                  <button
                    onClick={() => m.deleteTask(t.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-luna-dim hover:text-red-400"
                    title="Delete task"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* Progress + log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card icon={TrendingUp} title="Progress">
          <div className="grid grid-cols-3 gap-2 mb-4">
            <Stat label="Steps today" value={String(doneToday)} />
            <Stat label="This week" value={String(week.reduce((n, w) => n + w.count, 0))} />
            <Stat label="Tasks done" value={String(m.tasks.filter(t => t.done).length)} />
          </div>
          <div className="flex items-end gap-2 h-20">
            {week.map((w, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex-1 flex items-end">
                  <div
                    className="w-full rounded-t bg-gradient-to-t from-violet-500/60 to-indigo-400/60"
                    style={{ height: `${(w.count / weekMax) * 100}%`, minHeight: w.count ? 3 : 0 }}
                    title={`${w.count} steps`}
                  />
                </div>
                <span className="text-[9px] text-luna-dim">{w.label}</span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-luna-dim/60 mt-2">Every step counts. No streaks to lose.</p>
        </Card>

        <Card
          icon={ScrollText}
          title="Activity log"
          right={confirmClear ? (
            <span className="flex items-center gap-1.5 text-[10px]">
              <span className="text-red-400">Delete all?</span>
              <button onClick={() => { m.clearData(); setConfirmClear(false) }} className="text-red-400 hover:underline">Yes</button>
              <button onClick={() => setConfirmClear(false)} className="text-luna-dim hover:underline">No</button>
            </span>
          ) : (
            <button onClick={() => setConfirmClear(true)} className="text-[10px] text-luna-dim hover:text-red-400">Clear data</button>
          )}
        >
          {m.log.length === 0 ? (
            <p className="text-xs text-luna-dim py-4 text-center">No actions yet.</p>
          ) : (
            <div className="space-y-1 max-h-52 overflow-y-auto font-mono">
              {m.log.slice(0, 40).map((l, i) => (
                <div key={i} className="flex gap-2 text-[11px]">
                  <span className="text-luna-dim/60 shrink-0">{format(parseISO(l.ts), 'HH:mm')}</span>
                  <span className="text-luna-accent shrink-0">{l.action}</span>
                  <span className="text-luna-dim truncate">{l.detail}</span>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-luna-dim/50 mt-2">Saved only on this device.</p>
        </Card>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-luna-surface border border-luna-border rounded-lg px-3 py-2">
      <p className="text-[9px] uppercase tracking-wider text-luna-dim">{label}</p>
      <p className="text-lg font-mono font-light text-luna-text">{value}</p>
    </div>
  )
}

function ActionBtn({ onClick, icon: Icon, children, primary }: {
  onClick: () => void; icon: typeof Target; children: React.ReactNode; primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-all ${
        primary
          ? 'bg-luna-primary/20 text-luna-accent border-luna-primary/30 hover:bg-luna-primary/30'
          : 'text-luna-dim border-luna-border hover:text-luna-text hover:bg-luna-surface'
      }`}
    >
      <Icon size={12} />
      {children}
    </button>
  )
}

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { MTask, MStep, Energy, uid, guessUrgency, breakDown, shrinkStep } from '../components/Momentum/logic'

export interface FocusSession {
  stepId: string
  durationMs: number
  endsAt: number | null      // null while paused
  remainingMs: number        // valid while paused
  startedAt: string
}

export interface LogEntry {
  ts: string
  action: string
  detail: string
}

export interface CompletedSession {
  stepId: string
  minutes: number
  endedAt: string
}

interface MomentumState {
  tasks: MTask[]
  steps: MStep[]
  inbox: string[]            // brain-dump items not yet reviewed
  availableMinutes: number
  energy: Energy
  skipped: string[]          // step ids skipped for now
  focus: FocusSession | null
  sessions: CompletedSession[]
  log: LogEntry[]

  captureBrainDump: (items: string[]) => void
  acceptInbox: (items: string[]) => void
  discardInbox: () => void
  addTask: (title: string) => void
  deleteTask: (id: string) => void
  completeStep: (id: string) => void
  skipStep: (id: string) => void
  getUnstuck: (id: string) => void
  setAvailableMinutes: (m: number) => void
  setEnergy: (e: Energy) => void
  startFocus: (stepId: string, minutes: number) => void
  pauseFocus: () => void
  resumeFocus: () => void
  endFocus: (completed: boolean) => void
  clearData: () => void
}

const EMPTY = {
  tasks: [], steps: [], inbox: [], skipped: [], focus: null, sessions: [], log: [],
  availableMinutes: 10, energy: 'medium' as Energy,
}

const entry = (action: string, detail: string): LogEntry => ({ ts: new Date().toISOString(), action, detail })
const withLog = (log: LogEntry[], action: string, detail: string) => [entry(action, detail), ...log].slice(0, 100)

function makeTask(title: string): { task: MTask; steps: MStep[] } {
  const task: MTask = { id: uid(), title, urgency: guessUrgency(title), createdAt: new Date().toISOString(), done: false }
  return { task, steps: breakDown(task) }
}

export const useMomentum = create<MomentumState>()(persist((set, get) => ({
  ...EMPTY,

  captureBrainDump: (items) => set(s => ({
    inbox: [...s.inbox, ...items],
    log: withLog(s.log, 'capture_tasks', `${items.length} item(s)`),
  })),

  acceptInbox: (items) => set(s => {
    const made = items.map(makeTask)
    return {
      inbox: [],
      tasks: [...s.tasks, ...made.map(m => m.task)],
      steps: [...s.steps, ...made.flatMap(m => m.steps)],
      log: withLog(s.log, 'save_tasks', `${made.length} task(s), ${made.reduce((n, m) => n + m.steps.length, 0)} steps`),
    }
  }),

  discardInbox: () => set(s => ({ inbox: [], log: withLog(s.log, 'discard_inbox', `${s.inbox.length} item(s)`) })),

  addTask: (title) => set(s => {
    const { task, steps } = makeTask(title)
    return { tasks: [...s.tasks, task], steps: [...s.steps, ...steps], log: withLog(s.log, 'break_down_task', title) }
  }),

  deleteTask: (id) => set(s => {
    const task = s.tasks.find(t => t.id === id)
    const stepIds = new Set(s.steps.filter(st => st.taskId === id).map(st => st.id))
    return {
      tasks: s.tasks.filter(t => t.id !== id),
      steps: s.steps.filter(st => st.taskId !== id),
      focus: s.focus && stepIds.has(s.focus.stepId) ? null : s.focus,
      log: withLog(s.log, 'delete_task', task?.title ?? id),
    }
  }),

  completeStep: (id) => set(s => {
    const now = new Date().toISOString()
    const steps = s.steps.map(st => st.id === id ? { ...st, done: true, doneAt: now } : st)
    const step = steps.find(st => st.id === id)
    const tasks = s.tasks.map(t =>
      t.id === step?.taskId && steps.filter(st => st.taskId === t.id).every(st => st.done) ? { ...t, done: true } : t)
    return {
      steps, tasks,
      skipped: s.skipped.filter(x => x !== id),
      log: withLog(s.log, 'complete_step', step?.text ?? id),
    }
  }),

  skipStep: (id) => set(s => ({ skipped: [...s.skipped, id], log: withLog(s.log, 'skip_step', id) })),

  getUnstuck: (id) => set(s => {
    const step = s.steps.find(st => st.id === id)
    if (!step) return {}
    const smaller: MStep = { ...step, ...shrinkStep(step), id: uid(), order: step.order - 0.5, done: false, doneAt: null }
    return { steps: [...s.steps, smaller], log: withLog(s.log, 'get_unstuck', smaller.text) }
  }),

  setAvailableMinutes: (availableMinutes) => set({ availableMinutes, skipped: [] }),
  setEnergy: (energy) => set({ energy, skipped: [] }),

  startFocus: (stepId, minutes) => set(s => ({
    focus: {
      stepId, durationMs: minutes * 60_000, endsAt: Date.now() + minutes * 60_000,
      remainingMs: minutes * 60_000, startedAt: new Date().toISOString(),
    },
    log: withLog(s.log, 'start_focus_session', `${minutes} min`),
  })),

  pauseFocus: () => set(s => s.focus?.endsAt
    ? { focus: { ...s.focus, endsAt: null, remainingMs: Math.max(0, s.focus.endsAt - Date.now()) } }
    : {}),

  resumeFocus: () => set(s => s.focus && s.focus.endsAt === null
    ? { focus: { ...s.focus, endsAt: Date.now() + s.focus.remainingMs } }
    : {}),

  endFocus: (completed) => {
    const f = get().focus
    if (!f) return
    const left = f.endsAt ? Math.max(0, f.endsAt - Date.now()) : f.remainingMs
    const minutes = Math.max(1, Math.round((f.durationMs - left) / 60_000))
    set(s => ({
      focus: null,
      sessions: [{ stepId: f.stepId, minutes, endedAt: new Date().toISOString() }, ...s.sessions].slice(0, 200),
      log: withLog(s.log, 'update_focus_session', completed ? `done after ${minutes} min` : `stopped after ${minutes} min`),
    }))
    if (completed) get().completeStep(f.stepId)
  },

  clearData: () => set({ ...EMPTY, log: [entry('clear_data', 'all local data removed')] }),
}), { name: 'luna_momentum' }))

// Rule-based helpers for the Momentum dashboard. Next-step choice is deterministic;
// nothing here calls an LLM.

export type Energy = 'low' | 'medium' | 'high'

export interface MTask {
  id: string
  title: string
  urgency: number // 1 = someday, 2 = soon, 3 = today
  createdAt: string
  done: boolean
}

export interface MStep {
  id: string
  taskId: string
  text: string
  minutes: number
  order: number
  done: boolean
  doneAt: string | null
}

export const uid = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

const URGENT = /\b(today|tonight|now|asap|urgent|due|deadline)\b/i
const SOON = /\b(tomorrow|this week|soon)\b/i

export function guessUrgency(text: string): number {
  if (URGENT.test(text)) return 3
  if (SOON.test(text)) return 2
  return 1
}

/** Split a brain dump ("email Sam, clean my room and finish essay") into task titles. */
export function splitBrainDump(raw: string): string[] {
  return raw
    .split(/\n|;|,|\.\s|\band then\b|\bthen\b|\balso\b|\band\b/i)
    .map(s => s
      .replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '')
      .replace(/^(?:i\s+)?(?:need|have|got|should|must|want)\s+to\s+/i, '')
      .replace(/^to\s+/i, '')
      .trim())
    .filter(s => s.length > 2)
    .map(s => s.charAt(0).toUpperCase() + s.slice(1))
}

type Template = { match: RegExp; steps: [string, number][] }

const TEMPLATES: Template[] = [
  {
    match: /\b(clean|tidy|organi[sz]e|declutter)\b/i,
    steps: [
      ['Grab a bag and pick up any trash', 3],
      ['Put dirty clothes in one pile', 3],
      ['Clear one surface completely', 5],
      ['Put 10 things back where they belong', 5],
      ['Quick wipe or vacuum of the floor', 10],
    ],
  },
  {
    match: /\b(assignment|essay|paper|report|write|writing|homework|thesis)\b/i,
    steps: [
      ['Open the document', 2],
      ['Write the title and three headings', 5],
      ['Write just the first sentence', 3],
      ['Write messy notes under the first heading', 10],
      ['Read it once and fix one thing', 5],
    ],
  },
  {
    match: /\b(study|revise|exam|test|quiz|learn|read)\b/i,
    steps: [
      ['Open your notes or the book', 2],
      ['Pick one topic only', 2],
      ['Read for 10 minutes', 10],
      ['Write three things you remember', 5],
    ],
  },
  {
    match: /\b(email|reply|message|text|slack)\b/i,
    steps: [
      ['Open the email or chat', 2],
      ['Write one rough line', 3],
      ['Finish the reply and send it', 5],
    ],
  },
  {
    match: /\b(call|phone|book|appointment|schedule)\b/i,
    steps: [
      ['Find the number or booking link', 2],
      ['Write what you want to say in one line', 2],
      ['Make the call or booking', 5],
    ],
  },
  {
    match: /\b(laundry|dishes|wash)\b/i,
    steps: [
      ['Gather everything in one place', 3],
      ['Start the machine or the sink', 3],
      ['Set a timer and do one load', 10],
    ],
  },
]

/** Break a vague task into 2-10 minute steps. */
export function breakDown(task: MTask): MStep[] {
  const t = TEMPLATES.find(tpl => tpl.match.test(task.title))
  const raw: [string, number][] = t?.steps ?? [
    [`Get what you need for "${task.title}"`, 2],
    [`Do the very first part of "${task.title}"`, 5],
    [`Keep going for 10 minutes`, 10],
    [`Wrap up and note where you stopped`, 3],
  ]
  return raw.map(([text, minutes], i) => ({
    id: uid(), taskId: task.id, text, minutes, order: i, done: false, doneAt: null,
  }))
}

function energyFit(minutes: number, energy: Energy): number {
  if (energy === 'low') return minutes <= 5 ? 1 : 0
  if (energy === 'medium') return minutes <= 10 ? 1 : 0
  return 1
}

/**
 * score = urgency*3 + fits_time*4 + energy_fit*2 - minutes/5
 * Only the first open step of each task is a candidate, so steps stay in order.
 */
export function pickNextStep(
  tasks: MTask[], steps: MStep[], availableMinutes: number, energy: Energy, skip: string[] = [],
): { step: MStep; task: MTask } | null {
  let best: { step: MStep; task: MTask; score: number } | null = null
  for (const task of tasks) {
    if (task.done) continue
    const step = steps
      .filter(s => s.taskId === task.id && !s.done && !skip.includes(s.id))
      .sort((a, b) => a.order - b.order)[0]
    if (!step) continue
    const fits = step.minutes <= availableMinutes ? 1 : 0
    const score = task.urgency * 3 + fits * 4 + energyFit(step.minutes, energy) * 2 - step.minutes / 5
    if (!best || score > best.score) best = { step, task, score }
  }
  return best ? { step: best.step, task: best.task } : null
}

/** "I'm stuck": a smaller first move for the given step. */
export function shrinkStep(step: MStep): Pick<MStep, 'text' | 'minutes'> {
  if (step.minutes > 2) return { text: `Just get set up for: ${step.text.toLowerCase()}`, minutes: 2 }
  return { text: `Take one breath, then only look at it: ${step.text.toLowerCase()}`, minutes: 1 }
}

export function isToday(iso: string | null): boolean {
  if (!iso) return false
  return new Date(iso).toDateString() === new Date().toDateString()
}

export function fmtClock(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

import { Target, Play, Pause, Check, LifeBuoy, Mic, CheckCircle2 } from 'lucide-react'
import { useStore } from '../../store'
import { useMomentum } from '../../store/momentum'
import { useNextStep, useDoneToday, useFocusRemaining } from './hooks'
import { fmtClock } from './logic'

/** Compact "one look" card shown in the sidebar above recent chats. */
export function MomentumCard() {
  const setView = useStore(s => s.setView)
  const { focus, steps, inbox, startFocus, pauseFocus, resumeFocus, endFocus, getUnstuck } = useMomentum()
  const next = useNextStep()
  const doneToday = useDoneToday()
  const remaining = useFocusRemaining()
  const focusStep = focus ? steps.find(s => s.id === focus.stepId) : null

  const open = () => setView('focus')

  return (
    <div className="px-3 mb-2">
      <div className="rounded-xl bg-luna-card border border-luna-border p-3 space-y-2">
        <button onClick={open} className="w-full flex items-center justify-between text-[10px] uppercase tracking-wider text-luna-dim hover:text-luna-text">
          <span className="flex items-center gap-1.5"><Target size={11} className="text-luna-accent" /> Today's focus</span>
          <span className="flex items-center gap-1"><CheckCircle2 size={10} className="text-green-400" />{doneToday}</span>
        </button>

        {focus && focusStep ? (
          <div className="space-y-1.5">
            <p className="text-xs text-luna-text leading-snug line-clamp-2">{focusStep.text}</p>
            <div className="flex items-center justify-between">
              <span className={`font-mono text-sm ${remaining === 0 ? 'text-green-400' : 'text-luna-accent'}`}>
                {remaining === 0 ? "Time's up" : fmtClock(remaining ?? 0)}
              </span>
              <div className="flex gap-1">
                {focus.endsAt
                  ? <IconBtn title="Pause" onClick={pauseFocus}><Pause size={11} /></IconBtn>
                  : <IconBtn title="Resume" onClick={resumeFocus}><Play size={11} /></IconBtn>}
                <IconBtn title="Done" onClick={() => endFocus(true)}><Check size={11} /></IconBtn>
              </div>
            </div>
          </div>
        ) : next ? (
          <div className="space-y-1.5">
            <p className="text-xs text-luna-text leading-snug line-clamp-2">{next.step.text}</p>
            <p className="text-[10px] text-luna-dim truncate">{next.step.minutes} min · {next.task.title}</p>
            <div className="flex gap-1">
              <button
                onClick={() => startFocus(next.step.id, Math.max(next.step.minutes, 2))}
                className="flex-1 flex items-center justify-center gap-1 py-1 rounded-lg text-[11px] bg-luna-primary/20 text-luna-accent border border-luna-primary/30 hover:bg-luna-primary/30"
              >
                <Play size={10} /> Start
              </button>
              <button
                onClick={() => getUnstuck(next.step.id)}
                className="flex items-center justify-center gap-1 px-2 py-1 rounded-lg text-[11px] text-luna-dim border border-luna-border hover:text-luna-text"
                title="Give me a smaller step"
              >
                <LifeBuoy size={10} /> Stuck
              </button>
            </div>
          </div>
        ) : (
          <button onClick={open} className="w-full text-left text-xs text-luna-dim hover:text-luna-text">
            What's on your mind?
          </button>
        )}

        <button
          onClick={open}
          className="w-full flex items-center justify-between text-[11px] text-luna-dim hover:text-luna-text pt-1 border-t border-luna-border/50"
        >
          <span className="flex items-center gap-1.5"><Mic size={10} /> Brain dump</span>
          {inbox.length > 0 && <span className="text-[10px] px-1.5 rounded-full bg-luna-primary/20 text-luna-accent">{inbox.length} new</span>}
        </button>
      </div>
    </div>
  )
}

function IconBtn({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button title={title} onClick={onClick} className="p-1 rounded-md border border-luna-border text-luna-dim hover:text-luna-text hover:bg-luna-surface">
      {children}
    </button>
  )
}

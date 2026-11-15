import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',   label: 'Overview' },
  { id: 'states',     label: 'User states' },
  { id: 'policies',   label: 'Response policies' },
  { id: 'update',     label: 'update()' },
  { id: 'infer',      label: 'infer_passive()' },
  { id: 'classify',   label: 'Classification logic' },
  { id: 'context',    label: 'build_state_context()' },
  { id: 'patterns',   label: 'Pattern learning' },
  { id: 'singleton',  label: 'The state_engine singleton' },
];

export default function StateEngineService() {
  return (
    <DocsLayout
      title="State Engine"
      description="Rule-based user state classifier that infers sleep, focus, relaxation, and more from voice signals, PC activity, time of day, and learned habits."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>StateEngine</code> classifies the user into one of 9 states. Each state
          has a response policy that the chat pipeline uses to adjust Luna's tone and
          proactive behaviour — shorter in focus mode, warmer when tired, silent when
          sleeping.
        </p>
        <p>
          Classification uses a priority waterfall: explicit voice signals first,
          then time-of-day heuristics, then PC activity, then learned patterns from
          historical <code>StateEvent</code> rows.
        </p>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>state_engine/states.py</code></td><td><code>UserState</code> enum, <code>STATE_POLICIES</code>, focus-app and work-word sets.</td></tr>
            <tr><td><code>state_engine/pc.py</code></td><td><code>get_pc_idle_seconds()</code>, <code>get_active_app()</code>.</td></tr>
            <tr><td><code>state_engine/engine.py</code></td><td><code>StateEngine</code> class + <code>state_engine</code> singleton.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="states">User states</h2>
        <table>
          <thead><tr><th>State</th><th>When inferred</th></tr></thead>
          <tbody>
            <tr><td><code>SLEEPING</code></td><td>01:00–07:00 + no PC activity for &gt; 30 min</td></tr>
            <tr><td><code>JUST_WOKE_UP</code></td><td>05:00–10:00, PC just became active, prior state was SLEEPING</td></tr>
            <tr><td><code>AWAY</code></td><td>Personal variant only — gone &gt; 20 min, PC now active (just returned)</td></tr>
            <tr><td><code>BACK_FROM_WORK</code></td><td>16:00–21:00, message contains "back", "home", "tired", "done", etc.</td></tr>
            <tr><td><code>FOCUS_MODE</code></td><td>Active app is an IDE/editor; or late evening with very low mic volume</td></tr>
            <tr><td><code>RELAXING</code></td><td>20:00–23:00, non-focus app active</td></tr>
            <tr><td><code>STAYING_UP</code></td><td>23:00–02:00, PC active</td></tr>
            <tr><td><code>LOW_ENERGY</code></td><td>Voice emotion is sad/angry, or slow speech (&lt; 90 WPM) + low volume</td></tr>
            <tr><td><code>NORMAL</code></td><td>Fallback — nothing else matched</td></tr>
          </tbody>
        </table>

        <h3>Focus apps</h3>
        <p>These executable names trigger <code>FOCUS_MODE</code>:</p>
        <CodeFile label="state_engine/states.py">
          <pre><code>{`_FOCUS_APPS = frozenset({
    "code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe",
    "devenv.exe", "vim.exe", "nvim.exe", "sublime_text.exe",
    "rider64.exe", "clion64.exe", "fleet.exe",
})`}</code></pre>
        </CodeFile>
        <Callout type="note">
          Add entries to <code>_FOCUS_APPS</code> in <code>state_engine/states.py</code>
          to recognise additional editors or terminals.
        </Callout>
      </section>

      <section>
        <h2 id="policies">Response policies</h2>
        <p>
          Each state has a <code>tone</code>, a <code>behavior</code> instruction, and
          a <code>prompt_note</code> that is injected into the system prompt when that
          state is active.
        </p>
        <table>
          <thead><tr><th>State</th><th>Tone</th><th>Behavior</th></tr></thead>
          <tbody>
            <tr><td><code>SLEEPING</code></td><td>Silent</td><td>Don't speak unless explicitly addressed.</td></tr>
            <tr><td><code>JUST_WOKE_UP</code></td><td>Calm, brief</td><td>Short morning summary — schedule and top tasks.</td></tr>
            <tr><td><code>AWAY</code></td><td>Welcoming</td><td>Warm welcome back; brief summary if useful.</td></tr>
            <tr><td><code>BACK_FROM_WORK</code></td><td>Warm, low-energy</td><td>Don't push tasks; keep it easy and low-key.</td></tr>
            <tr><td><code>FOCUS_MODE</code></td><td>Minimal</td><td>One or two sentences only. No proactive interruptions.</td></tr>
            <tr><td><code>RELAXING</code></td><td>Casual, playful</td><td>Fun and conversational; not task-oriented.</td></tr>
            <tr><td><code>STAYING_UP</code></td><td>Gentle, practical</td><td>Acknowledge the hour once; don't nag.</td></tr>
            <tr><td><code>LOW_ENERGY</code></td><td>Soft, caring</td><td>Short sentences, warm tone, no agenda.</td></tr>
            <tr><td><code>NORMAL</code></td><td>Normal</td><td>Standard conversational companion mode.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="update">update()</h2>
        <p>
          Call this after every voice-input turn. Reads PC idle time and active app,
          classifies the state, logs a <code>StateEvent</code> row, and returns the
          new <code>UserState</code>.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def update(
    db: Session,
    transcript: str = "",
    emotion: str = "neutral",    # from voice emotion classifier
    volume: float | None = None, # RMS 0–1000
    speech_speed: float | None = None,  # words per minute
    speech_duration: float | None = None,
) -> UserState`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.state_engine import state_engine
from backend.models.database import SessionLocal

db = SessionLocal()
state = state_engine.update(
    db,
    transcript="I just got home",
    emotion="calm",
    volume=320.0,
    speech_speed=120.0,
)
print(state)  # UserState.BACK_FROM_WORK
db.close()`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="infer">infer_passive()</h2>
        <p>
          Classifies state without a voice turn — uses only time-of-day, PC idle
          seconds, and active app. Used by the scheduler's <code>state_aware_proactive()</code>
          to check state between conversations.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def infer_passive(db: Session) -> UserState`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`state = state_engine.infer_passive(db)
if state == UserState.FOCUS_MODE:
    print("User is in deep work — skip proactive messages")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="classify">Classification logic</h2>
        <p>The <code>_classify()</code> method applies rules in priority order:</p>
        <ol>
          <li><strong>SLEEPING</strong> — 01:00–07:00 + PC idle &gt; 30 min → immediate return.</li>
          <li><strong>JUST_WOKE_UP</strong> — 05:00–10:00, PC just active, prior state was SLEEPING.</li>
          <li><strong>AWAY</strong> — personal variant, last-seen gap &gt; 20 min, PC now active.</li>
          <li><strong>BACK_FROM_WORK</strong> — 16:00–21:00, transcript contains work-return words.</li>
          <li><strong>STAYING_UP</strong> — 23:00–02:00, PC active.</li>
          <li><strong>LOW_ENERGY</strong> — voice emotion is sad/angry, or slow + quiet speech.</li>
          <li><strong>FOCUS_MODE</strong> — active app is in the focus-apps set; or late evening + very low volume.</li>
          <li><strong>RELAXING</strong> — 20:00–23:00, non-focus app.</li>
          <li><strong>Learned pattern</strong> — most common state at this hour from <code>StateEvent</code> history.</li>
          <li><strong>NORMAL</strong> — fallback.</li>
        </ol>
      </section>

      <section>
        <h2 id="context">build_state_context()</h2>
        <p>
          Returns a short markdown string suitable for injection into the system prompt.
          Empty string for <code>NORMAL</code> state (no extra context needed).
        </p>
        <CodeFile label="signature">
          <pre><code>{`def build_state_context(state: UserState | None = None) -> str`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`ctx = state_engine.build_state_context()
# "## User state: FOCUS_MODE (for ~18 min)\n
#  The user is in deep-work / focus mode. Answer only what is directly asked..."

full_system = ctx + "\\n\\n" + personality_prompt + "\\n\\n" + memory_context`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="patterns">Pattern learning</h2>
        <p>
          Every call to <code>update()</code> logs a <code>StateEvent</code> row with
          hour, day of week, emotions, volume, speech speed, PC activity, and inferred
          state. Over time this builds a habit model:
        </p>
        <CodeFile label="example.py">
          <pre><code>{`# Get the most common state at a given hour
state_at_9am = state_engine.common_state_by_hour(db, hour=9)
print(state_at_9am)   # "JUST_WOKE_UP"

# Human-readable pattern summary
print(state_engine.narrative_summary(db))
# Learned habits:
#   Mon 09:00 — just waking up (14×)
#   Mon 14:00 — in deep-work mode (22×)
#   Fri 23:00 — staying up late (8×)`}</code></pre>
        </CodeFile>
        <p>
          Patterns are surfaced by <code>mine_behavioral_patterns()</code> in the
          scheduler (runs daily at 04:00) and stored as <code>behavior</code> facts
          in the memory manager.
        </p>
      </section>

      <section>
        <h2 id="singleton">The state_engine singleton</h2>
        <p>
          A single <code>StateEngine()</code> instance — <code>state_engine</code> — is
          created at module import. Import it anywhere in the backend:
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.state_engine import state_engine, UserState

# Check current state without a DB call
print(state_engine.current_state)    # UserState.NORMAL
print(state_engine.state_since)      # datetime of last transition

# Get the response policy dict
policy = state_engine.get_response_policy()
print(policy["tone"])                # "normal"`}</code></pre>
        </CodeFile>
        <Callout type="note">
          <code>current_state</code> reflects the last <em>update()</em> or
          <em>infer_passive()</em> call. If the server just restarted it returns
          <code>NORMAL</code> until the first inference.
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/services/scheduler',   label: 'Service', title: 'Scheduler', desc: 'state_aware_proactive() reads the state engine every 10 minutes.' },
        { href: '/services/personality', label: 'Service', title: 'Personality Engine', desc: 'State context is combined with the personality prompt.' },
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'Behavioral facts are stored by mine_behavioral_patterns().' },
      ]} />
    </DocsLayout>
  );
}

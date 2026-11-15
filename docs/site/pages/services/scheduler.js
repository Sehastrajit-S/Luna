import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',      label: 'Overview' },
  { id: 'jobs',          label: 'Scheduled jobs' },
  { id: 'events',        label: 'check_upcoming_events()' },
  { id: 'tasks',         label: 'check_overdue_tasks()' },
  { id: 'compaction',    label: 'daily_memory_compaction()' },
  { id: 'decay',         label: 'daily_personality_decay()' },
  { id: 'confidence',    label: 'confidence_decay()' },
  { id: 'patterns',      label: 'mine_behavioral_patterns()' },
  { id: 'companion',     label: 'companion_check_in()' },
  { id: 'commitment',    label: 'proactive_commitment_followup()' },
  { id: 'state-proactive', label: 'state_aware_proactive()' },
  { id: 'proactive-queue', label: 'Proactive queue' },
  { id: 'custom',        label: 'Adding custom jobs' },
];

export default function SchedulerService() {
  return (
    <DocsLayout
      title="Scheduler"
      description="APScheduler-based background job runner for proactive notifications, memory maintenance, personality decay, and behavioral pattern mining."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>LunaScheduler</code> wraps APScheduler's <code>BackgroundScheduler</code>
          and registers all periodic jobs at startup. It runs in-process alongside the
          FastAPI server — no separate worker process required.
        </p>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>scheduler/service.py</code></td><td><code>LunaScheduler</code> class + <code>luna_scheduler</code> singleton.</td></tr>
            <tr><td><code>scheduler/jobs.py</code></td><td>All job functions (events, tasks, memory, personality, patterns).</td></tr>
            <tr><td><code>scheduler/notifications.py</code></td><td><code>send_windows_notification()</code>, shared <code>proactive_queue</code>.</td></tr>
          </tbody>
        </table>

        <h3>Start / stop</h3>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.scheduler import luna_scheduler

luna_scheduler.start()   # called by FastAPI lifespan on startup
luna_scheduler.stop()    # called on shutdown`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          <code>start()</code> is idempotent — calling it a second time is a no-op.
          All jobs self-throttle with recent-log checks; running them manually during
          development is safe.
        </Callout>
      </section>

      <section>
        <h2 id="jobs">Scheduled jobs</h2>
        <table>
          <thead>
            <tr><th>Function</th><th>Schedule</th><th>Purpose</th></tr>
          </thead>
          <tbody>
            <tr><td><code>check_upcoming_events</code></td><td>Every 15 min</td><td>Windows notification for events starting within 1 hour.</td></tr>
            <tr><td><code>check_overdue_tasks</code></td><td>Daily 08:00</td><td>Notification for past-due tasks.</td></tr>
            <tr><td><code>morning_greeting</code></td><td>Daily 08:00</td><td>Good-morning push + proactive queue entry.</td></tr>
            <tr><td><code>daily_memory_compaction</code></td><td>Daily 03:00</td><td>LLM-based dedup of the facts table.</td></tr>
            <tr><td><code>daily_personality_decay</code></td><td>Daily 00:00</td><td>Pulls style preferences back toward 0.5.</td></tr>
            <tr><td><code>confidence_decay</code></td><td>Weekly Sun 02:00</td><td>Reduces confidence on stale preference/goal facts.</td></tr>
            <tr><td><code>mine_behavioral_patterns</code></td><td>Daily 04:00</td><td>Detects recurring habits and stores as behavioral facts.</td></tr>
            <tr><td><code>companion_check_in</code></td><td>Every 10 min</td><td>LLM-generated check-in after 25–180 quiet minutes.</td></tr>
            <tr><td><code>state_aware_proactive</code></td><td>Every 10 min</td><td>State-contextual proactive message (STAYING_UP, JUST_WOKE_UP, etc.).</td></tr>
            <tr><td><code>proactive_commitment_followup</code></td><td>Daily 12:00</td><td>Follows up on past commitments mentioned 1–6 days ago.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="events">check_upcoming_events()</h2>
        <p>
          Queries <code>CalendarEvent</code> records starting within the next 60 minutes
          and fires a Windows desktop notification for each one. The message is also
          appended to <code>proactive_queue</code> so the chat frontend can surface it.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.scheduler.jobs import check_upcoming_events

check_upcoming_events()   # run manually for testing`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="tasks">check_overdue_tasks()</h2>
        <p>
          Finds incomplete tasks whose <code>due_date</code> is in the past and fires
          a single notification listing up to 3 task names (with "+N more" if there are more).
        </p>
      </section>

      <section>
        <h2 id="compaction">daily_memory_compaction()</h2>
        <p>
          Calls <code>MemoryManager.compact_facts()</code> which performs an LLM pass
          to identify redundant or contradicted facts and deactivates them. Runs at
          3:00 AM daily in a fresh event loop (safe to call from a thread).
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.scheduler.jobs import daily_memory_compaction

daily_memory_compaction()   # blocks until compaction completes`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="decay">daily_personality_decay()</h2>
        <p>
          Calls <code>PersonalityEngine.daily_decay()</code> to nudge all six style
          preference axes slightly toward 0.5. Prevents the personality from polarising
          based on short-run conversation patterns.
        </p>
      </section>

      <section>
        <h2 id="confidence">confidence_decay()</h2>
        <p>
          Reduces the <code>confidence</code> column by 0.04 for every
          <code>preference</code> or <code>goal</code> fact that hasn't been updated
          in more than 30 days. The floor is 0.3 — facts are never deleted, just
          de-prioritised in retrieval scoring.
        </p>
        <p>Runs weekly (Sunday 02:00). Example decay path for a fact untouched for 6 months:</p>
        <table>
          <thead><tr><th>Week</th><th>Confidence</th></tr></thead>
          <tbody>
            <tr><td>0 (stored)</td><td>0.85</td></tr>
            <tr><td>5 weeks</td><td>0.65</td></tr>
            <tr><td>10 weeks</td><td>0.45</td></tr>
            <tr><td>15+ weeks</td><td>0.30 (floor)</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="patterns">mine_behavioral_patterns()</h2>
        <p>
          Scans the <code>StateEvent</code> table for the last 30 days and derives
          three types of behavioral patterns, which are stored as long-term
          <code>behavior</code> facts in the memory manager:
        </p>
        <ul>
          <li><strong>Peak activity hour</strong> — hour with the most state events.</li>
          <li><strong>Emotional days</strong> — days where &gt; 50% of events show a
              negative emotion (sad / angry / stressed).</li>
          <li><strong>Late-night tendency</strong> — if &gt; 30% of events occur between
              23:00–04:00.</li>
        </ul>
        <p>
          Patterns are only stored if they don't already exist (dedup check on the first
          35 characters). Requires at least 20 state events in the window.
        </p>
        <CodeFile label="stored facts example">
          <pre><code>{`"User is most active around 10pm"
"User often feels stressed on Mondays"
"User is frequently active late at night"`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="companion">companion_check_in()</h2>
        <p>
          Generates an LLM-written unprompted message from Luna if the user has been
          quiet for 25–180 minutes within the same calendar day. The message is seeded
          from the last 6 conversation turns so it's never a generic filler line.
        </p>
        <h3>Throttle rules</h3>
        <ul>
          <li>Only fires when last user message was 25–180 minutes ago (same day).</li>
          <li>No second check-in within 90 minutes of the previous one.</li>
          <li>Skipped if the last message was on a prior calendar day.</li>
        </ul>
        <CodeFile label="LLM prompt (abbreviated)">
          <pre><code>{`"The conversation ended 42 minutes ago.

Recent exchange:
User: just got back from the gym
Luna: Nice, how'd it go?

Generate a single short unprompted message from Luna...
Rules: max 2 sentences, no questions asking how they are,
not clingy, could be a random thought or observation."`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="commitment">proactive_commitment_followup()</h2>
        <p>
          Scans user messages from 20 hours to 6 days ago for future-tense commitments
          (interviews, exams, appointments, flights, etc.) and generates a one-sentence
          follow-up if the event has likely passed.
        </p>
        <p>Trigger keywords detected by regex:</p>
        <CodeFile label="commitment keywords">
          <pre><code>{`tomorrow | next week | next monday/tuesday/... | this friday/...
tonight | later today | in a few days
interview | presentation | exam | test | deadline | surgery | appointment | flight`}</code></pre>
        </CodeFile>
        <p>Throttled to one follow-up per 24 hours. Only fires once per scheduler run (the first matching message).</p>
      </section>

      <section>
        <h2 id="state-proactive">state_aware_proactive()</h2>
        <p>
          Checks the current inferred <code>UserState</code> every 10 minutes and
          queues a state-specific proactive message when warranted. Messages for
          three states:
        </p>
        <table>
          <thead><tr><th>State</th><th>Message style</th></tr></thead>
          <tbody>
            <tr><td><code>STAYING_UP</code></td><td>Acknowledges late hour, offers focus mode or sleep reminder.</td></tr>
            <tr><td><code>JUST_WOKE_UP</code></td><td>Morning brief with today's events and open tasks.</td></tr>
            <tr><td><code>BACK_FROM_WORK</code></td><td>Warm welcome back, asks if they want a summary.</td></tr>
          </tbody>
        </table>
        <p>Throttled: no repeat of any of these three reasons within 60 minutes.</p>
      </section>

      <section>
        <h2 id="proactive-queue">Proactive queue</h2>
        <p>
          <code>proactive_queue</code> is a plain Python <code>list[str]</code> shared
          between the scheduler jobs and the chat router. When the frontend polls
          <code>GET /api/chat/proactive</code>, the router drains the queue and returns
          any pending messages as SSE events.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.scheduler.notifications import proactive_queue

# Add a custom proactive message
proactive_queue.append("Your 2 PM meeting is in 10 minutes.")

# Read + drain (done by the chat router)
while proactive_queue:
    msg = proactive_queue.pop(0)
    print(msg)`}</code></pre>
        </CodeFile>
        <Callout type="note">
          The queue is in-process memory. If the server restarts, any pending messages
          are lost. For durable delivery use the <code>ProactiveLog</code> database table.
        </Callout>
      </section>

      <section>
        <h2 id="custom">Adding custom jobs</h2>
        <p>
          Each process module in <code>backend/processes/</code> can register its own
          APScheduler jobs by exposing a <code>register_scheduler(scheduler)</code>
          function. The scheduler calls it at startup via the process registry.
        </p>
        <CodeFile label="backend/processes/my_process.py">
          <pre><code>{`from apscheduler.schedulers.background import BackgroundScheduler

def register_scheduler(scheduler: BackgroundScheduler):
    scheduler.add_job(
        my_job_function,
        trigger="interval",
        minutes=30,
        id="my_custom_job",
        replace_existing=True,
    )

def my_job_function():
    print("custom job running")`}</code></pre>
        </CodeFile>
        <p>
          Any module placed in <code>backend/processes/</code> is auto-discovered by
          <code>iter_processes()</code> — no manual registration needed.
        </p>
      </section>

      <NextSteps items={[
        { href: '/services/state-engine', label: 'Service', title: 'State Engine', desc: 'UserState inference that drives state_aware_proactive().' },
        { href: '/services/personality',  label: 'Service', title: 'Personality Engine', desc: 'daily_decay() is called by the scheduler.' },
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'compact_facts() is called by the scheduler.' },
      ]} />
    </DocsLayout>
  );
}

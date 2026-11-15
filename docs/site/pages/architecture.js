import DocsLayout from '../components/DocsLayout';
import { Callout, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'layers',       label: 'Three layers' },
  { id: 'message-flow', label: 'Message lifecycle' },
  { id: 'sse',          label: 'SSE event protocol' },
  { id: 'tools',        label: 'Tool execution model' },
  { id: 'memory-arch',  label: 'Memory architecture' },
  { id: 'processes',    label: 'Background processes' },
  { id: 'boundaries',   label: 'Contribution boundaries' },
];

export default function Architecture() {
  return (
    <DocsLayout
      title="Architecture"
      description="How the Electron shell, React frontend, and FastAPI backend fit together — and how a message flows from input to streamed response."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna is built from three cooperating layers that communicate over HTTP and SSE.
          All three can run on a single machine; only the Electron shell requires a native OS environment.
        </p>

        <figure className="doc-figure">
          <img src="/images/architecture.svg" alt="L.U.N.A. system architecture" />
          <figcaption>System layers: Electron shell, React/Vite frontend, and FastAPI backend with service modules.</figcaption>
        </figure>
      </section>

      <section>
        <h2 id="layers">Three layers</h2>

        <h3>Electron shell</h3>
        <p>
          <code>electron/main.js</code> is the desktop process owner. It starts the FastAPI backend as a
          child process, manages the health-check loop (exponential backoff restart on crash), creates the
          browser window, and wires up tray and IPC. The preload script (<code>electron/preload.js</code>)
          exposes <code>electronAPI.apiBase</code> and <code>electronAPI.isElectron</code> to the renderer
          without leaking Node.js APIs.
        </p>

        <h3>React / Vite frontend</h3>
        <p>
          <code>frontend/src/App.tsx</code> is the root. The app renders in one of three view modes —
          <code>dev</code> (sidebar + content), <code>user</code> (voice-focused), and <code>luna</code>
          (full-screen HUD). State is managed by a single Zustand store at <code>frontend/src/store/index.ts</code>.
          Feature components live in <code>frontend/src/components/</code> grouped by domain.
        </p>

        <h3>FastAPI backend</h3>
        <p>
          <code>backend/main.py</code> bootstraps the FastAPI app, registers CORS middleware, mounts all
          routers, and starts background processes. Routers in <code>backend/routers/</code> are intentionally
          thin — they validate requests and delegate all logic to <code>backend/services/</code>.
        </p>
      </section>

      <section>
        <h2 id="message-flow">Message lifecycle</h2>
        <p>Here is what happens from the moment you send a message to the moment the response is complete:</p>

        <ol>
          <li><strong>User input</strong> — text typed in <code>InputBar</code>, voice processed by the voice route, or a scheduled proactive trigger fires.</li>
          <li><strong>Fast-path check</strong> — the backend checks a small set of intent patterns that should not hit the LLM (e.g. explicit app-launch commands).</li>
          <li><strong>Context assembly</strong> — <code>memory_manager.py</code> fetches relevant facts from ChromaDB using semantic search, then appends personality state, recent calendar tasks, active activities, vision observations, and the last N conversation turns.</li>
          <li><strong>LLM call</strong> — the assembled prompt is sent to the configured provider (Ollama or OpenAI-compatible) with <code>num_ctx: 8192</code> and <code>num_predict: 1024</code>. The response streams as tokens.</li>
          <li><strong>Stream parsing</strong> — as tokens arrive, the backend scans for bracket commands (<code>[WIDGET:...]</code>, <code>[WEB_SEARCH:...]</code>, <code>[MAP:...]</code>) and JSON tool calls. Commands are stripped from the displayed text and emitted as separate SSE events.</li>
          <li><strong>Tool execution</strong> — detected tools run concurrently where possible. Results (search snippets, Spotify state, widget data) may be appended to the stream as additional content.</li>
          <li><strong>Memory update</strong> — after the <code>done</code> event, background coroutines extract new facts, update personality scores, and compact long conversations into summaries.</li>
        </ol>
      </section>

      <section>
        <h2 id="sse">SSE event protocol</h2>
        <p>
          The chat stream endpoint is <code>POST /api/chat/stream</code>. It returns <code>text/event-stream</code>.
          Each event has a <code>type</code> field:
        </p>

        <table>
          <thead><tr><th>Type</th><th>Payload</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>metadata</code></td><td><code>conversationId, model</code></td><td>First event — identifies the conversation and model being used.</td></tr>
            <tr><td><code>token</code></td><td><code>content: string</code></td><td>A streamed text chunk from the LLM. Append to the current message bubble.</td></tr>
            <tr><td><code>command</code></td><td><code>action, payload</code></td><td>A parsed tool call — widget open, web search result, map display, Spotify action, 3D scene, etc.</td></tr>
            <tr><td><code>confirmation</code></td><td><code>tool, description, id</code></td><td>Luna wants to execute a tool but needs user approval first (confirm-mode tool).</td></tr>
            <tr><td><code>done</code></td><td><code>conversationId</code></td><td>Stream complete. Memory extraction runs after this event.</td></tr>
            <tr><td><code>error</code></td><td><code>message</code></td><td>Unrecoverable stream error. The frontend shows an error state.</td></tr>
          </tbody>
        </table>

        <Callout type="info" title="Handling the stream in the frontend">
          <p><code>frontend/src/api/chat.ts</code> wraps the SSE connection. The Zustand store dispatches
          each event type to the correct reducer — tokens go to <code>streamMessage</code>, commands open
          widgets via <code>setDynamicWidget</code>, and confirmation events set <code>pendingConfirmation</code>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="tools">Tool execution model</h2>
        <p>Luna supports two command syntaxes that can appear in LLM output:</p>

        <h3>Bracket tags</h3>
        <p>Simple inline commands parsed from the token stream by regex:</p>
        <pre><code>{`[WEB_SEARCH:query here]
[WIDGET:{"type":"steps","data":[...]}]
[MAP:{"lat":40.7,"lon":-74.0}]
[SPOTIFY:{"action":"play","query":"artist name"}]
[SCENE:{"prompt":"rotating cube"}]`}</code></pre>

        <h3>JSON tool calls</h3>
        <p>Structured tool calls in the model's native tool-use format. These go through <code>tool_registry.py</code>
        where each tool is registered with a name, schema, and permission mode.</p>

        <h3>Permission modes</h3>
        <p>Every tool has one of three permission modes set per user in <code>data/permissions.json</code>:</p>
        <table>
          <thead><tr><th>Mode</th><th>Behaviour</th></tr></thead>
          <tbody>
            <tr><td><code>allow</code></td><td>Executes immediately without prompting the user.</td></tr>
            <tr><td><code>confirm</code></td><td>Emits a <code>confirmation</code> SSE event. The tool waits until the user approves or rejects via the UI banner.</td></tr>
            <tr><td><code>block</code></td><td>The tool call is silently dropped and Luna is told the tool is unavailable.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="memory-arch">Memory architecture</h2>
        <p>Luna's memory system has three tiers:</p>

        <h3>Structured facts — SQLite</h3>
        <p>
          Explicit facts about you (<em>"user prefers dark mode"</em>, <em>"user's dog is named Max"</em>)
          are stored as rows in the <code>Fact</code> table in <code>data/luna.db</code>. Each fact has a
          source (conversation ID), confidence score, and creation timestamp.
        </p>

        <h3>Semantic search — ChromaDB</h3>
        <p>
          All facts are also embedded with <code>nomic-embed-text</code> via Ollama and stored in
          <code>data/chroma/</code>. When assembling context for a new message, the backend runs a
          semantic search against the user's query to surface the most relevant facts — not just the
          most recent ones.
        </p>

        <h3>Personality engine</h3>
        <p>
          <code>backend/services/personality.py</code> maintains a floating-point state vector with dimensions
          for mood, energy level, formality preference, humor level, and emotional support need.
          These values drift based on conversation sentiment and update Luna's system-prompt tone in real time.
        </p>

        <Callout type="note" title="Privacy">
          <p>All memory is stored locally. Nothing is sent to external servers. The ChromaDB collection
          and SQLite database live in <code>data/</code> and are gitignored.</p>
        </Callout>
      </section>

      <section>
        <h2 id="processes">Background processes</h2>
        <p>
          The backend registers long-running coroutines via <code>backend/processes/registry.py</code>.
          Each process runs on its own schedule:
        </p>

        <table>
          <thead><tr><th>Process</th><th>Schedule</th><th>Responsibility</th></tr></thead>
          <tbody>
            <tr><td><code>memory_maintenance</code></td><td>Every 5 min</td><td>Extracts facts from recent conversations, compacts long threads into summaries, prunes low-confidence facts.</td></tr>
            <tr><td><code>proactive_followups</code></td><td>Every 20 s</td><td>Checks whether Luna should send an unsolicited message (reminders, observations, check-ins) and emits it to the frontend.</td></tr>
            <tr><td><code>calendar_reminders</code></td><td>Every 60 s</td><td>Scans upcoming tasks and calendar events and fires reminder notifications.</td></tr>
            <tr><td><code>voice_runtime</code></td><td>Continuous</td><td>Runs the wake-word detection loop and pipes audio to the STT model.</td></tr>
          </tbody>
        </table>

        <p>List all registered processes at runtime:</p>
        <pre><code>npm run luna -- processes</code></pre>
      </section>

      <section>
        <h2 id="boundaries">Contribution boundaries</h2>
        <p>Keep changes scoped to one layer when possible. Crossing layers in a single PR makes review harder:</p>

        <table>
          <thead><tr><th>What you're changing</th><th>Where it lives</th></tr></thead>
          <tbody>
            <tr><td>API endpoint logic</td><td><code>backend/services/</code> — not in routers</td></tr>
            <tr><td>New background job</td><td><code>backend/processes/</code> — registered in <code>registry.py</code></td></tr>
            <tr><td>UI component or view</td><td><code>frontend/src/components/&lt;Feature&gt;/</code></td></tr>
            <tr><td>Global client state</td><td><code>frontend/src/store/index.ts</code></td></tr>
            <tr><td>Desktop/native behaviour</td><td><code>electron/main.js</code> or <code>electron/preload.js</code></td></tr>
            <tr><td>New tool or skill</td><td><code>backend/services/tool_registry.py</code> + <code>skills/</code></td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/workflow',        label: 'Deep dive', title: 'Full workflow',     desc: 'Six-stage request lifecycle visualised — from input to privacy.' },
        { href: '/memory',          label: 'Feature',   title: 'Memory system',    desc: 'Fact extraction, ChromaDB embeddings, personality, and compaction explained.' },
        { href: '/agent',           label: 'Feature',   title: 'Agent & Skills',   desc: 'How to write a skill, set permission modes, and use the workspace.' },
        { href: '/project-structure', label: 'Platform', title: 'Project structure', desc: 'File-level ownership map for the full monorepo.' },
      ]} />
    </DocsLayout>
  );
}

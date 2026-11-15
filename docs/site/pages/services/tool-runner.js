import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',   label: 'Overview' },
  { id: 'parse',      label: 'parse_tool_call_json()' },
  { id: 'execute',    label: 'execute_tool_call()' },
  { id: 'verify',     label: 'verify_tool_result()' },
  { id: 'tools',      label: 'Available tools' },
  { id: 'system',     label: 'System controls' },
  { id: 'workspace',  label: 'Workspace tools' },
  { id: 'browser',    label: 'Browser tools' },
  { id: 'screen',     label: 'Screen tools' },
  { id: 'calendar',   label: 'Calendar & tasks' },
];

export default function ToolRunnerService() {
  return (
    <DocsLayout
      title="Tool Runner"
      description="JSON tool call parser and async dispatcher for the coding agent — launches apps, controls Spotify, manages the workspace, and calls web tools."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          The tool runner is used by the coding agent (and general chat agent) to parse
          structured JSON tool calls embedded in the LLM's output and execute them
          asynchronously. It is separate from the bracket command parser — tool calls
          use structured JSON, bracket commands use inline text syntax.
        </p>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>tool_runner/parser.py</code></td><td><code>parse_tool_call_json()</code>, <code>strip_tool_call_json()</code>, <code>_scan_json_object()</code>.</td></tr>
            <tr><td><code>tool_runner/executor.py</code></td><td><code>execute_tool_call()</code> — dispatches 30+ tools.</td></tr>
            <tr><td><code>tool_runner/verifier.py</code></td><td><code>verify_tool_result()</code> — validates tool output.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="parse">parse_tool_call_json()</h2>
        <p>
          Scans a raw LLM response string for the first valid JSON object containing a
          <code>"tool"</code> key and returns it as a dict. Handles partial JSON,
          markdown code fences, and embedded noise.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def parse_tool_call_json(text: str) -> dict | None`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.tool_runner import parse_tool_call_json, strip_tool_call_json

raw = 'Let me check that. {"tool": "web_search", "args": {"query": "Python 3.13 features"}}'
tc = parse_tool_call_json(raw)
# {"tool": "web_search", "args": {"query": "Python 3.13 features"}}

# Remove the JSON blob from the display text
display_text = strip_tool_call_json(raw)
# "Let me check that."  `}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="execute">execute_tool_call()</h2>
        <p>
          Async dispatcher — takes a parsed tool call dict and returns a result string.
          The result is fed back into the LLM as a tool-result message for the next
          reasoning step.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def execute_tool_call(
    tc: dict,          # {"tool": "...", "args": {...}}
    db: Session,
    conversation_id: int,
) -> str               # short result string, max ~4000 chars`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`import asyncio
from backend.services.tool_runner import execute_tool_call
from backend.models.database import SessionLocal

db = SessionLocal()
result = asyncio.run(execute_tool_call(
    {"tool": "web_search", "args": {"query": "FastAPI streaming"}},
    db=db,
    conversation_id=1,
))
print(result)   # search results string
db.close()`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="verify">verify_tool_result()</h2>
        <p>
          Validates a tool result string — checks it's non-empty, not an obvious error
          message, and within size limits. Returns <code>True</code> if the result is
          usable for the next LLM turn.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def verify_tool_result(result: str) -> bool`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="tools">Available tools</h2>
        <p>All tools available to the LLM via the tool runner:</p>
        <table>
          <thead><tr><th>Tool name</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>launch_app</code></td><td>Launch a desktop application by name.</td></tr>
            <tr><td><code>list_apps</code></td><td>Return a list of known launchable apps.</td></tr>
            <tr><td><code>spotify_play</code></td><td>Play a track or playlist by search query.</td></tr>
            <tr><td><code>spotify_pause</code></td><td>Pause playback.</td></tr>
            <tr><td><code>spotify_next</code></td><td>Skip to next track.</td></tr>
            <tr><td><code>spotify_prev</code></td><td>Go to previous track.</td></tr>
            <tr><td><code>spotify_queue</code></td><td>Queue a track by search query.</td></tr>
            <tr><td><code>switch_audio</code></td><td>Switch default audio output device by name.</td></tr>
            <tr><td><code>browse_url</code></td><td>Open a URL in the default browser.</td></tr>
            <tr><td><code>create_task</code></td><td>Create a task with optional due date and priority.</td></tr>
            <tr><td><code>create_event</code></td><td>Create a calendar event with datetime and duration.</td></tr>
            <tr><td><code>web_search</code></td><td>Web search — returns text results.</td></tr>
            <tr><td><code>web_research</code></td><td>Deep research query — structured result with sources.</td></tr>
            <tr><td><code>dataset_search</code></td><td>Find public datasets matching a query.</td></tr>
            <tr><td><code>web_fetch</code></td><td>Fetch and return the text content of a URL.</td></tr>
            <tr><td><code>web_download_file</code></td><td>Download a file from URL to a local path.</td></tr>
            <tr><td><code>browser_open</code></td><td>Open a URL in a controlled browser session.</td></tr>
            <tr><td><code>browser_read</code></td><td>Fetch the rendered DOM text of a URL.</td></tr>
            <tr><td><code>workspace_read</code></td><td>Read a file from the workspace directory.</td></tr>
            <tr><td><code>workspace_read_base64</code></td><td>Read a binary file as base64.</td></tr>
            <tr><td><code>workspace_write</code></td><td>Write text content to a workspace file.</td></tr>
            <tr><td><code>workspace_write_base64</code></td><td>Write binary content (base64) to a workspace file.</td></tr>
            <tr><td><code>list_skills</code></td><td>List all available skill definitions.</td></tr>
            <tr><td><code>create_agent_task</code></td><td>Create a delegated agent task with a description.</td></tr>
            <tr><td><code>take_screenshot</code></td><td>Capture a screenshot.</td></tr>
            <tr><td><code>get_active_window</code></td><td>Get the name of the currently focused window.</td></tr>
            <tr><td><code>find_text_on_screen</code></td><td>OCR — find text at screen coordinates.</td></tr>
            <tr><td><code>click_at</code></td><td>Simulate a mouse click at x, y.</td></tr>
            <tr><td><code>type_text</code></td><td>Type text via keyboard simulation.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="system">System controls</h2>
        <p>The following tools map to <code>backend/services/system_controls.py</code>:</p>
        <table>
          <thead><tr><th>Tool</th><th>Args</th></tr></thead>
          <tbody>
            <tr><td><code>get_volume</code></td><td>none</td></tr>
            <tr><td><code>set_volume</code></td><td><code>level: int</code> (0–100)</td></tr>
            <tr><td><code>mute_audio</code></td><td>none</td></tr>
            <tr><td><code>unmute_audio</code></td><td>none</td></tr>
            <tr><td><code>get_brightness</code></td><td>none</td></tr>
            <tr><td><code>set_brightness</code></td><td><code>level: int</code> (0–100)</td></tr>
            <tr><td><code>lock_screen</code></td><td>none</td></tr>
            <tr><td><code>turn_off_display</code></td><td>none</td></tr>
            <tr><td><code>sleep_system</code></td><td>none</td></tr>
            <tr><td><code>get_clipboard</code></td><td>none</td></tr>
            <tr><td><code>set_clipboard</code></td><td><code>text: str</code></td></tr>
            <tr><td><code>get_system_info</code></td><td>none</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="workspace">Workspace tools</h2>
        <p>
          All workspace operations are scoped to the configured workspace root
          (<code>WORKSPACE_ROOT</code> in <code>.env</code>). Paths outside the root
          are rejected.
        </p>
        <CodeFile label="tool call examples">
          <pre><code>{`{"tool": "workspace_read",  "args": {"path": "src/main.py"}}
{"tool": "workspace_write", "args": {"path": "output.txt", "content": "hello world"}}
{"tool": "workspace_read_base64",  "args": {"path": "assets/logo.png"}}
{"tool": "workspace_write_base64", "args": {"path": "export.png", "content_base64": "iVBOR..."}}`}</code></pre>
        </CodeFile>
        <Callout type="note">
          All workspace tool calls are written to the audit log
          (<code>AuditLog</code> table) with the tool name, args, and result length.
        </Callout>
      </section>

      <section>
        <h2 id="browser">Browser tools</h2>
        <p>
          <code>browser_open</code> opens a URL in a managed headless browser session.
          <code>browser_read</code> fetches and returns rendered page text (DOM
          extraction, not raw HTML). Both calls are audited.
        </p>
        <CodeFile label="tool call example">
          <pre><code>{`{"tool": "browser_read", "args": {"url": "https://docs.python.org/3/library/asyncio.html"}}
// Returns up to 4000 chars of the rendered page text`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="screen">Screen tools</h2>
        <p>
          Screen tools use the <code>screen_perception</code> service for screenshot,
          OCR, and UI automation. Results are truncated to 200 characters and
          JSON-encoded.
        </p>
        <CodeFile label="tool call example">
          <pre><code>{`{"tool": "take_screenshot",       "args": {}}
{"tool": "get_active_window",     "args": {}}
{"tool": "find_text_on_screen",   "args": {"text": "Submit"}}
{"tool": "click_at",              "args": {"x": 540, "y": 320}}
{"tool": "type_text",             "args": {"text": "Hello world"}}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="calendar">Calendar and tasks</h2>
        <CodeFile label="tool call examples">
          <pre><code>{`{"tool": "create_task", "args": {
    "title": "Review pull request",
    "due": "2025-06-15T09:00:00",
    "priority": "high"
}}

{"tool": "create_event", "args": {
    "title": "Team standup",
    "datetime": "2025-06-10T09:30:00",
    "duration": 15
}}`}</code></pre>
        </CodeFile>
        <p>
          Both tools write to the SQLite <code>tasks</code> and <code>calendar_events</code>
          tables and are automatically surfaced by the scheduler's
          <code>check_upcoming_events()</code> and <code>check_overdue_tasks()</code>.
        </p>
      </section>

      <NextSteps items={[
        { href: '/services/command-parser', label: 'Service', title: 'Command Parser', desc: 'Bracket commands — an alternative to structured tool calls.' },
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'The LLM output is used to extract and store facts after tool runs.' },
        { href: '/api-reference', label: 'Reference', title: 'API Reference', desc: 'The coding endpoint streams tool_call and tool_result SSE events.' },
      ]} />
    </DocsLayout>
  );
}

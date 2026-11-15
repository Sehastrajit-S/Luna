import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',   label: 'Overview' },
  { id: 'parse',      label: 'parse_commands()' },
  { id: 'execute',    label: 'execute_commands()' },
  { id: 'brackets',   label: 'Bracket syntax reference' },
  { id: 'away',       label: 'Away detection' },
  { id: 'intents',    label: 'Intent parsing' },
  { id: 'research',   label: 'Research query extraction' },
  { id: 'coding',     label: 'Coding request detection' },
];

export default function CommandParserService() {
  return (
    <DocsLayout
      title="Command Parser"
      description="Extracts and executes embedded bracket actions from Luna's responses, plus intent parsing helpers for launch, map, Spotify, and research requests."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          When Luna produces a response it may embed action commands inside square
          brackets — <code>[LAUNCH:chrome]</code>, <code>[BROWSE:https://...]</code>,
          <code>[TASK:Buy milk|2025-06-01|low]</code>, etc. The command parser extracts
          these, and the executor carries them out.
        </p>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>command_parser/commands.py</code></td><td><code>parse_commands()</code>, <code>execute_commands()</code>.</td></tr>
            <tr><td><code>command_parser/away.py</code></td><td><code>user_is_leaving()</code>, <code>response_is_farewell()</code>.</td></tr>
            <tr><td><code>command_parser/intents.py</code></td><td><code>parse_user_launch_request()</code>, <code>parse_user_map_request()</code>, <code>parse_user_spotify_request()</code>.</td></tr>
            <tr><td><code>command_parser/research.py</code></td><td><code>extract_direct_research_query()</code>, <code>extract_direct_dataset_query()</code>.</td></tr>
            <tr><td><code>command_parser/coding.py</code></td><td><code>is_coding_request()</code>.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="parse">parse_commands()</h2>
        <p>
          Scans Luna's response text for embedded bracket commands and returns a list
          of parsed command dicts. Does <em>not</em> execute them.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def parse_commands(
    response: str,
    user_message: str = "",
) -> list[dict]`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.command_parser import parse_commands

response = "Sure! [LAUNCH:spotify] [TASK:Buy milk|2025-06-01|low]"
cmds = parse_commands(response)
# [
#   {"type": "launch", "app": "spotify"},
#   {"type": "task", "title": "Buy milk", "due": "2025-06-01", "priority": "low"},
# ]`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="execute">execute_commands()</h2>
        <p>
          Takes the list returned by <code>parse_commands()</code> and executes each
          command. Side effects: launching apps, opening URLs, writing to the database,
          calling Spotify, setting away state.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def execute_commands(
    commands: list[dict],
    db: Session,
    conversation_id: int,
) -> None`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.command_parser import parse_commands, execute_commands
from backend.models.database import SessionLocal

db = SessionLocal()
cmds = parse_commands(luna_response, user_message)
execute_commands(cmds, db, conversation_id=42)
db.close()`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          All errors inside <code>execute_commands()</code> are silently swallowed per
          command — one failing command doesn't block the others. Check logs if an
          action doesn't seem to execute.
        </Callout>
      </section>

      <section>
        <h2 id="brackets">Bracket syntax reference</h2>
        <p>Luna's system prompt teaches it to embed these brackets. Each is parsed by <code>parse_commands()</code>:</p>
        <table>
          <thead><tr><th>Bracket</th><th>Command type</th><th>Fields</th></tr></thead>
          <tbody>
            <tr>
              <td><code>[AWAY]</code></td>
              <td><code>away</code></td>
              <td><code>action: "on"</code>, <code>label: "away"|"bedtime"</code></td>
            </tr>
            <tr>
              <td><code>[BROWSE:https://...]</code></td>
              <td><code>browse</code></td>
              <td><code>url</code> — blocked for weather/finance/crypto sites</td>
            </tr>
            <tr>
              <td><code>[MAP:search:query]</code></td>
              <td><code>map</code></td>
              <td><code>action: "search"</code>, <code>query</code></td>
            </tr>
            <tr>
              <td><code>[MAP:route:destination]</code></td>
              <td><code>map</code></td>
              <td><code>action: "route"</code>, <code>query</code></td>
            </tr>
            <tr>
              <td><code>[MAP:close]</code></td>
              <td><code>map</code></td>
              <td><code>action: "close"</code></td>
            </tr>
            <tr>
              <td><code>[SPOTIFY:query]</code></td>
              <td><code>spotify</code></td>
              <td><code>query</code></td>
            </tr>
            <tr>
              <td><code>[SPOTIFY:queue query]</code></td>
              <td><code>spotify_queue</code></td>
              <td><code>query</code></td>
            </tr>
            <tr>
              <td><code>[LAUNCH:app name]</code></td>
              <td><code>launch</code></td>
              <td><code>app</code></td>
            </tr>
            <tr>
              <td><code>[WIDGET:kind|title|body]</code></td>
              <td><code>widget</code></td>
              <td><code>kind</code>, <code>title</code>, <code>body</code></td>
            </tr>
            <tr>
              <td><code>[TASK:title|due?|priority?]</code></td>
              <td><code>task</code></td>
              <td><code>title</code>, <code>due</code> (ISO date, optional), <code>priority</code> (default: medium)</td>
            </tr>
            <tr>
              <td><code>[EVENT:title|datetime|duration?]</code></td>
              <td><code>event</code></td>
              <td><code>title</code>, <code>datetime</code> (ISO), <code>duration</code> (minutes, default: 60)</td>
            </tr>
          </tbody>
        </table>

        <h3>Browse blocklist</h3>
        <p>
          URLs matching weather, finance, or crypto domains are blocked from the
          <code>[BROWSE]</code> command (Luna is not supposed to open live data pages
          automatically). Affected domains include <code>weather.com</code>,
          <code>finance.yahoo.com</code>, <code>coinmarketcap.com</code>, and others.
        </p>
      </section>

      <section>
        <h2 id="away">Away detection</h2>
        <p>
          The <code>away.py</code> module provides two helper predicates used by
          <code>parse_commands()</code> and the chat pipeline:
        </p>
        <CodeFile label="signatures">
          <pre><code>{`def user_is_leaving(message: str) -> bool
def response_is_farewell(response: str) -> bool`}</code></pre>
        </CodeFile>
        <p>
          If the user's message contains farewell phrases (<em>"going to bed"</em>,
          <em>"see you later"</em>, <em>"taking a break"</em>, …) or Luna's response
          is itself a farewell, an <code>[AWAY]</code> command is emitted with label
          <code>"bedtime"</code> when bed-related words are present, otherwise <code>"away"</code>.
        </p>
        <Callout type="note">
          Away detection only runs in the <code>personal</code> variant
          (<code>LUNA_VARIANT=personal</code>).
        </Callout>
      </section>

      <section>
        <h2 id="intents">Intent parsing</h2>
        <p>These helpers are used by the chat router before sending messages to the LLM,
          to decide whether to route to a specialised handler:</p>
        <CodeFile label="signatures">
          <pre><code>{`def parse_user_launch_request(message: str) -> str | None
# Returns the app name to launch, or None

def parse_user_map_request(message: str) -> dict | None
# Returns {"action": "search"|"route", "query": str} or None

def parse_user_spotify_request(message: str) -> dict | None
# Returns {"action": "play"|"pause"|"next"|"prev", "query": str | None} or None`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.command_parser import (
    parse_user_launch_request,
    parse_user_map_request,
    parse_user_spotify_request,
)

parse_user_launch_request("open notepad")        # "notepad"
parse_user_map_request("directions to the gym")  # {"action": "route", "query": "the gym"}
parse_user_spotify_request("play some jazz")     # {"action": "play", "query": "jazz"}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="research">Research query extraction</h2>
        <CodeFile label="signatures">
          <pre><code>{`def extract_direct_research_query(message: str) -> str | None
# Detects explicit research requests ("research X", "look up X", "find info on X")

def extract_direct_dataset_query(message: str) -> str | None
# Detects dataset requests ("find a dataset of X", "get CSV data about X")`}</code></pre>
        </CodeFile>
        <p>
          These are used by the chat router to bypass the main LLM and call the
          research skill directly when the user's intent is unambiguous.
        </p>
      </section>

      <section>
        <h2 id="coding">Coding request detection</h2>
        <CodeFile label="signature">
          <pre><code>{`def is_coding_request(message: str) -> bool`}</code></pre>
        </CodeFile>
        <p>
          Returns <code>True</code> when the message is clearly a code-writing, debugging,
          or technical explanation request. Used by the chat router to redirect to the
          coding agent rather than the general chat pipeline.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.command_parser import is_coding_request

is_coding_request("write a Python function to parse JSON")  # True
is_coding_request("what should I have for lunch?")          # False`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/services/tool-runner', label: 'Service', title: 'Tool Runner', desc: 'Structured JSON tool calls executed by the coding agent.' },
        { href: '/services/state-engine', label: 'Service', title: 'State Engine', desc: 'State is checked before deciding whether to execute away commands.' },
        { href: '/api-reference', label: 'Reference', title: 'API Reference', desc: 'Chat endpoints that invoke the command parser.' },
      ]} />
    </DocsLayout>
  );
}

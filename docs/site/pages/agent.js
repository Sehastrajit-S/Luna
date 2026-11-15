import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'skills',       label: 'Skills' },
  { id: 'create-skill', label: 'Create a skill' },
  { id: 'permissions',  label: 'Permission modes' },
  { id: 'workspace',    label: 'Workspace' },
  { id: 'browser',      label: 'Browser automation' },
  { id: 'tasks',        label: 'Agent tasks' },
  { id: 'audit',        label: 'Audit log' },
];

export default function Agent() {
  return (
    <DocsLayout
      title="Agent & Skills"
      description="Skills, permission modes, the agent workspace, browser automation, multi-step tasks, and the audit log."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna's agent layer is built on an OpenClaw-style permission model. Every action Luna can take
          — searching the web, launching an app, reading a file — is a registered <em>tool</em>.
          Tools are grouped into <em>skills</em> and each has an individually-configurable permission mode.
        </p>

        <p>The Agent page in the Luna sidebar shows all installed skills, current permissions, workspace
        files, browser status, active tasks, and the live audit stream.</p>
      </section>

      <section>
        <h2 id="skills">Skills</h2>
        <p>
          A skill is a package that extends Luna with new capabilities. Skills live in two locations:
        </p>
        <ul>
          <li><code>skills/</code> — skills shipped with the repo (version-controlled).</li>
          <li><code>data/workspace/skills/</code> — user-created or agent-created skills (gitignored).</li>
        </ul>

        <p>Each skill directory contains two files:</p>

        <table>
          <thead><tr><th>File</th><th>Purpose</th></tr></thead>
          <tbody>
            <tr><td><code>skill.json</code></td><td>Machine-readable manifest — name, description, version, and registered commands.</td></tr>
            <tr><td><code>SKILL.md</code></td><td>Human-readable description. Luna reads this to understand what the skill does and when to use it.</td></tr>
          </tbody>
        </table>

        <p>List all installed skills via the API:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl http://localhost:8899/api/agent/skills`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="create-skill">Create a skill</h2>
        <p>Skills follow a simple two-file structure. Here is a minimal example:</p>

        <CodeFile label="skills/my-skill/skill.json">
          <pre><code>{`{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "A short description of what this skill does.",
  "commands": [
    {
      "name": "do_thing",
      "description": "Does the thing with the given input.",
      "parameters": {
        "input": { "type": "string", "description": "What to process." }
      }
    }
  ]
}`}</code></pre>
        </CodeFile>

        <CodeFile label="skills/my-skill/SKILL.md">
          <pre><code>{`# My Skill

This skill enables Luna to do the thing.

## When to use
Call \`do_thing\` when the user asks to process something.

## Examples
- "Do the thing with this text"
- "Can you process X for me?"`}</code></pre>
        </CodeFile>

        <Callout type="note" title="Command implementation">
          <p>Commands declared in <code>skill.json</code> must be registered in
          <code>backend/services/tool_registry.py</code> with matching names and handler functions.
          The manifest describes the schema; the registry provides the implementation.</p>
        </Callout>

        <p>After adding a skill, restart the backend. Luna will load it on startup and make it available
        to the LLM as a tool call option.</p>
      </section>

      <section>
        <h2 id="permissions">Permission modes</h2>
        <p>
          Every registered tool has a permission mode. Modes are stored per-user in
          <code>data/permissions.json</code> and are configurable from the Agent page in the UI.
        </p>

        <table>
          <thead><tr><th>Mode</th><th>Behaviour</th><th>Suitable for</th></tr></thead>
          <tbody>
            <tr>
              <td><code>allow</code></td>
              <td>Tool executes immediately without any user prompt.</td>
              <td>Safe, idempotent tools — web search, reading files, weather lookup.</td>
            </tr>
            <tr>
              <td><code>confirm</code></td>
              <td>Luna pauses and shows a confirmation banner in the UI. You must approve or reject before execution continues.</td>
              <td>Destructive or irreversible actions — writing files, launching apps, Spotify control.</td>
            </tr>
            <tr>
              <td><code>block</code></td>
              <td>The tool call is silently dropped. Luna is told the tool is unavailable.</td>
              <td>Tools you want to disable entirely — e.g. camera, browser automation.</td>
            </tr>
          </tbody>
        </table>

        <p>Update a tool's permission via the API:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl -X POST http://localhost:8899/api/agent/permissions/web_search \
  -H "Content-Type: application/json" \
  -d '{"mode": "allow"}'`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="workspace">Workspace</h2>
        <p>
          Agent-created files are restricted to <code>data/workspace/</code>. This acts as a sandbox — Luna
          can read and write files within the workspace but cannot access the rest of your filesystem without
          explicit OS-level permission escalation.
        </p>

        <p>Read and write workspace files via the API:</p>
        <CodeFile label="terminal">
          <pre><code>{`# List workspace contents
GET /api/agent/workspace

# Read a file
GET /api/agent/workspace/read?path=notes/ideas.md

# Write a file
POST /api/agent/workspace/write
{"path": "notes/ideas.md", "content": "..."}`}</code></pre>
        </CodeFile>

        <Callout type="info" title="Gitignored">
          <p><code>data/workspace/</code> is gitignored. Files created by Luna live here and are never
          committed to the repository.</p>
        </Callout>
      </section>

      <section>
        <h2 id="browser">Browser automation</h2>
        <p>
          Luna's default browser layer uses HTTP requests via <code>httpx</code> — it can fetch and parse
          public web pages without a real browser. This is fast and lightweight.
        </p>

        <p>For pages that require JavaScript rendering, Luna supports optional <strong>Playwright</strong>
        integration. Install it separately if needed:</p>

        <CodeFile label="terminal">
          <pre><code>{`pip install playwright
playwright install chromium`}</code></pre>
        </CodeFile>

        <p>Browser automation routes:</p>
        <CodeFile label="terminal">
          <pre><code>{`# Check browser status
GET /api/agent/browser/status

# Open a URL (Playwright required for JS-rendered pages)
POST /api/agent/browser/open
{"url": "https://example.com"}

# Read page content
POST /api/agent/browser/read
{"url": "https://example.com"}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="tasks">Agent tasks</h2>
        <p>
          Luna supports multi-step agent tasks — goals that require multiple tool calls planned and
          executed over time. Tasks are created, planned, and tracked in the database.
        </p>

        <CodeFile label="terminal">
          <pre><code>{`# List all tasks
GET /api/agent/tasks

# Create a new task
POST /api/agent/tasks
{"title": "Research competitors", "description": "..."}`}</code></pre>
        </CodeFile>

        <p>From the chat UI, tell Luna to start a task:</p>
        <pre><code>{`"Start a research task: find the top 5 competitors to Notion and summarise their pricing."`}</code></pre>

        <p>Luna will break this into steps, plan an execution sequence, and work through it — asking for
        confirmation at each confirm-mode tool call.</p>
      </section>

      <section>
        <h2 id="audit">Audit log</h2>
        <p>
          Every tool call Luna executes is appended to <code>data/audit.log</code> with a timestamp, tool
          name, input parameters, and outcome. This gives you full visibility into what Luna has done.
        </p>

        <CodeFile label="terminal">
          <pre><code>{`# Stream the live audit log via the API
GET /api/agent/audit`}</code></pre>
        </CodeFile>

        <p>The Agent page in the sidebar shows the audit stream in real time. Each entry shows the tool,
        whether it was auto-allowed or user-confirmed, and the result summary.</p>

        <Callout type="tip" title="Reviewing past actions">
          <p>Open <code>data/audit.log</code> directly to review the full history. Entries are newline-delimited
          JSON objects, easy to parse or grep.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/architecture', label: 'Deep dive', title: 'Architecture',   desc: 'How tool calls flow through the SSE stream and permission system.' },
        { href: '/contributing', label: 'Community', title: 'Contributing',   desc: 'How to write and submit a new skill or tool for the repo.' },
        { href: '/api-reference', label: 'Platform',  title: 'API reference',  desc: 'Full agent API endpoint documentation.' },
      ]} />
    </DocsLayout>
  );
}

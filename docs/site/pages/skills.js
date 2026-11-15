import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',      label: 'Overview' },
  { id: 'how-skills-work', label: 'How skills work' },
  { id: 'built-in',      label: 'Built-in skills' },
  { id: 'coding-agent',  label: 'coding-agent' },
  { id: 'research',      label: 'research' },
  { id: 'desktop-agent', label: 'desktop-agent' },
  { id: 'workspace-suite', label: 'workspace-suite' },
  { id: 'file-builder',  label: 'file-builder' },
  { id: 'document-drafter', label: 'document-drafter' },
  { id: 'dataset-builder', label: 'dataset-builder' },
  { id: 'resume-checker', label: 'resume-checker' },
  { id: 'job-application', label: 'job-application-assistant' },
  { id: 'list-api',      label: 'list_skills API' },
];

export default function SkillsPage() {
  return (
    <DocsLayout
      title="Skills"
      description="Luna's skill system — what built-in skills are available, how they're loaded, and how they shape model behavior."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          A <strong>skill</strong> is a markdown file (<code>SKILL.md</code>) that lives
          in a named folder under <code>skills/</code>. When Luna detects that a user's
          request matches a skill's purpose, the skill's instructions are injected into
          the system prompt — no code changes, no redeployment.
        </p>
        <p>
          Skills add context, workflow rules, and tool guidance without hardcoding
          behaviour in the backend. They're the primary extension point for giving
          Luna specialised capabilities.
        </p>
      </section>

      <section>
        <h2 id="how-skills-work">How skills work</h2>
        <ol>
          <li>The skill manager scans <code>skills/*/SKILL.md</code> on startup and caches all skill definitions.</li>
          <li>On each chat turn, the chat router calls <code>list_skills()</code> to expose skill names and descriptions to the LLM.</li>
          <li>The LLM decides whether to invoke a skill tool call based on the user's request.</li>
          <li>When invoked, the skill's <code>SKILL.md</code> content is injected as additional system context for that turn.</li>
          <li>Skills that have a dedicated endpoint (e.g. the coding agent) can also be called directly via their own route.</li>
        </ol>
        <CodeFile label="skills/ directory layout">
          <pre><code>{`skills/
  coding-agent/
    SKILL.md          ← workflow rules + tool list
  research/
    SKILL.md
  desktop-agent/
    SKILL.md
  workspace-suite/
    SKILL.md
  file-builder/
    SKILL.md
  document-drafter/
    SKILL.md
  dataset-builder/
    SKILL.md
  resume-checker/
    SKILL.md
  job-application-assistant/
    SKILL.md`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="built-in">Built-in skills</h2>
        <p>Luna ships nine built-in skills covering code, research, desktop automation, cloud productivity, and documents.</p>
      </section>

      <section>
        <h2 id="coding-agent">coding-agent</h2>
        <p>
          Activated for code-writing, debugging, editing, review, and technical explanation
          requests. Uses a dedicated Ollama model (<code>CODING_MODEL</code> in <code>.env</code>,
          default: <code>qwen2.5-coder:7b</code>).
        </p>
        <p>Has its own streaming endpoint: <code>POST /api/coding/stream</code>.</p>
        <h3>Tools</h3>
        <table>
          <thead><tr><th>Tool</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>code_read_file(path)</code></td><td>Read a workspace file (max 100 KB).</td></tr>
            <tr><td><code>code_edit_file(path, old_string, new_string)</code></td><td>Exact-string replacement. Fails if string not found or ambiguous.</td></tr>
            <tr><td><code>code_write_file(path, content)</code></td><td>Write or overwrite a workspace file.</td></tr>
            <tr><td><code>code_list_files(path)</code></td><td>List a workspace directory.</td></tr>
            <tr><td><code>code_search(pattern, path)</code></td><td>Regex search across workspace files (up to 50 matches).</td></tr>
            <tr><td><code>code_run_shell(command)</code></td><td>Run a shell command (read-only by default; confirms before destructive ops).</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="research">research</h2>
        <p>
          Activated for current-information questions, comparisons, source-backed answers,
          and website research.
        </p>
        <p>Workflow: search → fetch relevant pages → compare sources → summarise with citations. Always includes a <strong>References</strong> section for web-backed answers.</p>
        <p>Uses <code>web_search</code> for quick lookups and <code>web_research</code> for deep, cited context.</p>
      </section>

      <section>
        <h2 id="desktop-agent">desktop-agent</h2>
        <p>Multi-step desktop automation. Asks for confirmation before clicks, typing, shell commands, destructive file operations, or sending external messages. Records meaningful actions to the audit log and verifies results before declaring completion.</p>
      </section>

      <section>
        <h2 id="workspace-suite">workspace-suite</h2>
        <p>Google Workspace and Microsoft 365 integration. Automatically routes requests to the correct provider (Gmail/Outlook, Google Calendar/Microsoft Calendar, Drive/OneDrive, Sheets/Excel, Tasks/To Do). Requires OAuth tokens in <code>.env</code>.</p>
        <Callout type="note">
          If a workspace tool returns an auth error, Luna tells the user which OAuth token
          is missing rather than silently failing.
        </Callout>
      </section>

      <section>
        <h2 id="file-builder">file-builder</h2>
        <p>Creates, organises, and manages files in the workspace sandbox. Handles text, code, CSV, JSON, markdown, and other file types. Keeps all output inside <code>data/workspace/</code>.</p>
      </section>

      <section>
        <h2 id="document-drafter">document-drafter</h2>
        <p>Drafts structured documents — reports, emails, summaries, memos, meeting notes, technical specs. Applies formatting and structure appropriate to the document type. Can export to Google Docs or Markdown.</p>
      </section>

      <section>
        <h2 id="dataset-builder">dataset-builder</h2>
        <p>Assembles datasets from web sources, APIs, and uploaded files. Searches dataset portals (Kaggle, Hugging Face, UCI, data.gov, NOAA, World Bank), downloads CSVs, and organises output in the workspace.</p>
      </section>

      <section>
        <h2 id="resume-checker">resume-checker</h2>
        <p>Reviews resume content, structure, phrasing, and ATS keyword density against a job description. Highlights gaps and suggests specific improvements. Works with uploaded PDF or plain-text resumes.</p>
      </section>

      <section>
        <h2 id="job-application">job-application-assistant</h2>
        <p>End-to-end job application workflow: tailors the resume to a job description, drafts a cover letter, prepares talking points for common interview questions, and tracks application status. Saves output to the workspace.</p>
      </section>

      <section>
        <h2 id="list-api">list_skills API</h2>
        <p>
          The backend exposes the skill registry via a tool call and via HTTP:
        </p>
        <CodeFile label="HTTP">
          <pre><code>{`GET /api/skills
# Returns JSON array of { name, description, has_dedicated_endpoint }`}</code></pre>
        </CodeFile>
        <CodeFile label="Python">
          <pre><code>{`from backend.services.skill_manager import list_skills

skills = list_skills()
for s in skills:
    print(s["name"], "—", s["description"])`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/skills-authoring', label: 'Guide',   title: 'Authoring Skills', desc: 'Build your own skill — SKILL.md format, tools, and contribution guide.' },
        { href: '/services/tool-runner', label: 'Service', title: 'Tool Runner', desc: 'Tools available to skills at runtime.' },
        { href: '/api-reference',    label: 'Reference', title: 'API Reference', desc: 'The coding agent endpoint and skill endpoints.' },
      ]} />
    </DocsLayout>
  );
}

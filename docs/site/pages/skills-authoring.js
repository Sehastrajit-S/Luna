import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',      label: 'Overview' },
  { id: 'structure',     label: 'File structure' },
  { id: 'skill-md',      label: 'SKILL.md format' },
  { id: 'tools',         label: 'Declaring tools' },
  { id: 'endpoint',      label: 'Dedicated endpoint (optional)' },
  { id: 'example',       label: 'Full example' },
  { id: 'loading',       label: 'How skills are loaded' },
  { id: 'best-practices', label: 'Best practices' },
];

export default function SkillsAuthoringPage() {
  return (
    <DocsLayout
      title="Authoring Skills"
      description="How to create a new Luna skill — SKILL.md format, tool declarations, endpoint wiring, and contribution guidelines."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          A skill is a folder under <code>skills/</code> containing a single
          <code>SKILL.md</code> file. No Python code is required for a basic skill —
          just a markdown file that tells the LLM how to behave when the skill is active.
          For skills that need a dedicated HTTP endpoint or custom logic, a Python
          backend module can be added.
        </p>
      </section>

      <section>
        <h2 id="structure">File structure</h2>
        <CodeFile label="skills/my-skill/">
          <pre><code>{`skills/
  my-skill/
    SKILL.md            ← required: instructions for the LLM
    handler.py          ← optional: custom Python endpoint
    SKILL_ICON.svg      ← optional: icon for the skill UI card`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="skill-md">SKILL.md format</h2>
        <p>
          <code>SKILL.md</code> is plain markdown. It should contain three things:
        </p>
        <ol>
          <li><strong>Heading</strong> — <code># Skill Name</code> — used as the display name.</li>
          <li><strong>Trigger description</strong> — one or two sentences describing when to use this skill. Luna reads this to decide whether to invoke the skill for a given request.</li>
          <li><strong>Workflow rules</strong> — numbered steps the model should follow when the skill is active.</li>
        </ol>
        <CodeFile label="skills/my-skill/SKILL.md — minimal">
          <pre><code>{`# My Skill

Use this skill when the user asks to do X or Y.

Workflow:

1. Do the first thing.
2. Confirm before doing anything destructive.
3. Summarise what changed.`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          Write the trigger description to be unambiguous. If it overlaps too broadly
          with other skills, the LLM may invoke it when it shouldn't. Test with a few
          sample messages to verify the matching feels right.
        </Callout>
      </section>

      <section>
        <h2 id="tools">Declaring tools</h2>
        <p>
          Tools don't need to be declared in <code>SKILL.md</code> — all tools registered
          in the <code>ToolRegistry</code> are available to every skill. Document the tools
          your skill uses in a <strong>Tools</strong> section for the LLM's benefit:
        </p>
        <CodeFile label="SKILL.md — Tools section example">
          <pre><code>{`## Tools

- \`web_search(query)\` — Search the web for current information.
- \`web_fetch(url)\` — Fetch a URL and return its readable content.
- \`workspace_write(path, content)\` — Save output to a workspace file.`}</code></pre>
        </CodeFile>
        <p>
          Listing tools explicitly helps the model know which tools are relevant without
          scanning through all 30+ registered tools each turn.
        </p>

        <h3>Adding a new tool to the registry</h3>
        <p>
          If your skill needs a tool that doesn't exist yet, register it in
          <code>backend/services/tool_registry.py</code>:
        </p>
        <CodeFile label="backend/services/tool_registry.py">
          <pre><code>{`{
    "name": "my_tool",
    "description": "Does something useful. Args: query (str).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The query to run"}
        },
        "required": ["query"]
    }
}`}</code></pre>
        </CodeFile>
        <p>
          Then handle it in <code>backend/services/tool_runner/executor.py</code> under
          the <code>execute_tool_call()</code> dispatcher.
        </p>
      </section>

      <section>
        <h2 id="endpoint">Dedicated endpoint (optional)</h2>
        <p>
          Most skills only need a <code>SKILL.md</code> file — they run through the
          standard chat pipeline. If your skill benefits from a separate streaming
          endpoint (e.g. the coding agent at <code>/api/coding/stream</code>), add
          a FastAPI router in the backend:
        </p>
        <CodeFile label="backend/routers/my_skill.py">
          <pre><code>{`from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.models.database import get_db

router = APIRouter()

@router.post("/api/my-skill/stream")
async def my_skill_stream(payload: dict, db: Session = Depends(get_db)):
    async def generate():
        # your streaming logic here
        yield 'data: {"type":"token","content":"hello"}\\n\\n'
        yield 'data: {"type":"done"}\\n\\n'
    return StreamingResponse(generate(), media_type="text/event-stream")`}</code></pre>
        </CodeFile>
        <CodeFile label="backend/main.py — register the router">
          <pre><code>{`from backend.routers.my_skill import router as my_skill_router
app.include_router(my_skill_router)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="example">Full example — price-tracker skill</h2>
        <CodeFile label="skills/price-tracker/SKILL.md">
          <pre><code>{`# Price Tracker

Use this skill when the user asks to track, monitor, or compare prices for products,
flights, hotels, or other purchasable items.

Workflow:

1. Identify the item and any comparison criteria (store, date range, region).
2. Use \`web_search\` to find current pricing from multiple sources.
3. Use \`web_fetch\` to read individual product pages if snippets are insufficient.
4. Compare at least three sources before giving a recommendation.
5. Save a summary table to the workspace if the user wants to revisit it later.
6. Include source URLs in the response.

## Tools

- \`web_search(query)\` — Search for current prices.
- \`web_fetch(url)\` — Read a product or retailer page.
- \`workspace_write(path, content)\` — Save comparison table to workspace.`}</code></pre>
        </CodeFile>
        <p>
          That's it — no Python code needed. The skill manager picks it up automatically
          on the next server start.
        </p>
      </section>

      <section>
        <h2 id="loading">How skills are loaded</h2>
        <p>
          At startup, <code>backend/services/skill_manager.py</code> walks
          <code>skills/*/SKILL.md</code> and builds an in-memory registry. The registry
          is exposed to the LLM as a <code>list_skills</code> tool call result on the
          first turn of each conversation.
        </p>
        <p>
          Skills are hot-reloaded on each server restart — no cache invalidation needed.
          During development, restart the backend after editing a <code>SKILL.md</code>.
        </p>
        <CodeFile label="Python — access the registry directly">
          <pre><code>{`from backend.services.skill_manager import list_skills, get_skill

skills = list_skills()         # all skills as dicts
skill  = get_skill("research") # a single skill by folder name
print(skill["instructions"])   # full SKILL.md content`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="best-practices">Best practices</h2>
        <ul>
          <li>
            <strong>One responsibility per skill.</strong> If a skill's trigger
            description covers two unrelated domains, split it into two skills.
          </li>
          <li>
            <strong>Include a confirmation step for destructive actions.</strong>
            Any tool call that sends, deletes, uploads, or overwrites should be gated
            behind a user confirmation in the workflow rules.
          </li>
          <li>
            <strong>Document error cases.</strong> Tell the model how to handle the
            most common failures — missing credentials, tool errors, empty results.
          </li>
          <li>
            <strong>Keep the trigger description unambiguous.</strong> It's read by
            the LLM to match intent. Vague descriptions lead to false positives.
          </li>
          <li>
            <strong>List the tools you use.</strong> A short Tools section prevents
            the model from guessing or trying tools that aren't relevant.
          </li>
          <li>
            <strong>Test against real messages.</strong> Run a few sample user messages
            through the chat API and check whether the skill is invoked when it should
            be — and not when it shouldn't.
          </li>
        </ul>
      </section>

      <NextSteps items={[
        { href: '/skills',            label: 'Guide',   title: 'Skills Overview', desc: 'Browse all built-in skills and how the skill system works.' },
        { href: '/services/tool-runner', label: 'Service', title: 'Tool Runner', desc: 'Add new tools to the registry for your skill to use.' },
        { href: '/api-reference',     label: 'Reference', title: 'API Reference', desc: 'Wire your skill to a dedicated streaming endpoint.' },
      ]} />
    </DocsLayout>
  );
}

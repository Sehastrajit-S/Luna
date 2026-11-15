import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'what-is-luna-sdk',  label: 'What is the Luna SDK?' },
  { id: 'two-modes',         label: 'Two integration modes' },
  { id: 'providers',         label: 'LLM provider compatibility' },
  { id: 'http-quickstart',   label: 'HTTP API quick start' },
  { id: 'python-quickstart', label: 'Python import quick start' },
  { id: 'service-map',       label: 'Service map' },
  { id: 'next',              label: 'Next steps' },
];

const providers = [
  {
    name: 'Ollama',
    logo: '/images/providers/ollama.svg',
    env: 'LLM_PROVIDER=ollama',
    note: 'Local inference — zero API cost, full privacy.',
    models: 'qwen2.5, llama3, mistral, phi3, …',
    status: 'default',
  },
  {
    name: 'OpenAI',
    logo: '/images/providers/openai.svg',
    env: 'LLM_PROVIDER=openai-compatible',
    note: 'GPT-4o, GPT-4-turbo, GPT-3.5-turbo and any OpenAI-compatible endpoint (OpenRouter, Jan.ai, llama.cpp, LM Studio).',
    models: 'gpt-4o, gpt-4o-mini, gpt-4-turbo',
    status: 'supported',
  },
  {
    name: 'Anthropic',
    logo: '/images/providers/anthropic.svg',
    env: 'LLM_PROVIDER=anthropic',
    note: 'Native Claude Messages API with SSE streaming.',
    models: 'claude-opus-4, claude-sonnet-4-6, claude-haiku-4-5',
    status: 'supported',
  },
  {
    name: 'Google Gemini',
    logo: '/images/providers/google.svg',
    env: 'LLM_PROVIDER=google',
    note: 'Native Gemini REST API with streaming.',
    models: 'gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash',
    status: 'supported',
  },
  {
    name: 'Groq',
    logo: '/images/providers/groq.svg',
    env: 'LLM_PROVIDER=groq',
    note: 'Ultra-fast cloud inference — lowest latency of any hosted provider.',
    models: 'llama-3.3-70b-versatile, mixtral-8x7b',
    status: 'supported',
  },
  {
    name: 'Mistral AI',
    logo: '/images/providers/mistral.svg',
    env: 'LLM_PROVIDER=mistral',
    note: 'Native Mistral API.',
    models: 'mistral-large-latest, mistral-medium, mistral-small',
    status: 'supported',
  },
  {
    name: 'Cohere',
    logo: '/images/providers/cohere.svg',
    env: 'LLM_PROVIDER=cohere',
    note: 'Cohere Chat API v2 with streaming.',
    models: 'command-r-plus, command-r, command-light',
    status: 'supported',
  },
  {
    name: 'NVIDIA NIM',
    logo: '/images/providers/nvidia.svg',
    env: 'LLM_PROVIDER=nvidia-nim',
    note: 'OpenAI-compatible endpoint for NVIDIA-optimised models.',
    models: 'meta/llama-3.1-8b-instruct, nvidia/nemotron-4-340b',
    status: 'supported',
  },
  {
    name: 'LM Studio',
    logo: '/images/providers/lmstudio.svg',
    env: 'LLM_PROVIDER=openai-compatible',
    note: 'Point openai_base_url at your LM Studio local server.',
    models: 'any model loaded in LM Studio',
    status: 'compatible',
  },
];

const services = [
  { name: 'LLM Service',       href: '/services/llm',            desc: 'Multi-provider streaming + completion client.' },
  { name: 'Memory Manager',    href: '/services/memory-manager',  desc: 'Long-term facts, ChromaDB vectors, conversation context.' },
  { name: 'Personality Engine',href: '/services/personality',     desc: 'Mood state, RL-style style preferences, prompt building.' },
  { name: 'Scheduler',         href: '/services/scheduler',       desc: 'Background jobs, proactive messages, Windows notifications.' },
  { name: 'State Engine',      href: '/services/state-engine',    desc: 'Time-aware user state classification + response policies.' },
  { name: 'Command Parser',    href: '/services/command-parser',  desc: 'Intent detection, bracket commands, launch/Spotify/map parsing.' },
  { name: 'Tool Runner',       href: '/services/tool-runner',     desc: 'LLM tool call JSON parsing, execution, result summarisation.' },
  { name: 'Memory Graph',      href: '/services/memory-graph',    desc: 'Knowledge graph traversal + episodic memory.' },
  { name: 'MCP Servers',       href: '/mcp',                      desc: 'Model Context Protocol servers for Claude Desktop and agents.' },
];

export default function SDKOverview() {
  return (
    <DocsLayout
      title="Build with Luna — SDK Overview"
      description="Use Luna's AI engine in your own applications. Two integration paths, nine LLM providers, detailed service APIs."
      toc={toc}
    >

      {/* ── What is the Luna SDK ───────────────────────────────── */}
      <section>
        <h2 id="what-is-luna-sdk">What is the Luna SDK?</h2>
        <p>
          Luna is a full AI backend — not just a chat wrapper. When you run it, you get a FastAPI
          server at <code>http://localhost:8899</code> that exposes a rich set of services your
          application can call: streaming LLM inference, persistent memory, personality-driven
          prompts, proactive scheduling, state detection, tool execution, and more.
        </p>
        <p>
          You can integrate Luna into your own project in two ways:
        </p>
        <ul>
          <li><strong>HTTP API</strong> — call the REST endpoints from any language or framework.</li>
          <li><strong>Python import</strong> — import the service modules directly into your Python app.</li>
        </ul>
        <p>
          Either way, one <code>.env</code> file controls which LLM provider Luna talks to, and
          swapping providers is a one-line change.
        </p>
      </section>

      {/* ── Two integration modes ─────────────────────────────── */}
      <section>
        <h2 id="two-modes">Two integration modes</h2>

        <table>
          <thead>
            <tr>
              <th>Mode</th>
              <th>When to use</th>
              <th>Language</th>
              <th>Overhead</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>HTTP API</strong></td>
              <td>Any language, microservice architecture, Electron/web apps, mobile</td>
              <td>Any (REST + SSE)</td>
              <td>Network round-trip (~1 ms local)</td>
            </tr>
            <tr>
              <td><strong>Python import</strong></td>
              <td>Python monorepo, scripts, notebooks, agents in same process</td>
              <td>Python 3.10+</td>
              <td>None — in-process call</td>
            </tr>
          </tbody>
        </table>

        <Callout type="tip" title="Recommended for most apps">
          Use the HTTP API. It isolates your app from Luna's internals, survives Luna restarts
          independently, and works from any language. The Python import path is best when you're
          building a Python-first tool and want zero network overhead.
        </Callout>
      </section>

      {/* ── Provider compatibility ────────────────────────────── */}
      <section>
        <h2 id="providers">LLM provider compatibility</h2>
        <p>
          Luna's <code>LLMClient</code> is a unified interface that routes to any of the providers
          below. All providers expose the same <code>stream_chat()</code>, <code>complete()</code>,
          and <code>embed()</code> methods — your code doesn't change when you switch providers.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem', margin: '1.5rem 0' }}>
          {providers.map((p) => (
            <div key={p.name} style={{
              border: '1px solid var(--docs-border)',
              borderRadius: 10,
              padding: '1rem',
              background: 'var(--docs-surface)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <img src={p.logo} alt={p.name} width={40} height={40} style={{ borderRadius: 8, flexShrink: 0 }} />
                <div>
                  <strong style={{ fontSize: '0.95rem' }}>{p.name}</strong>
                  <span style={{
                    display: 'inline-block',
                    marginLeft: 8,
                    fontSize: '0.68rem',
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    padding: '2px 7px',
                    borderRadius: 99,
                    background: p.status === 'default' ? 'var(--docs-accent)' : p.status === 'compatible' ? 'var(--docs-border)' : 'color-mix(in srgb, var(--docs-accent) 20%, transparent)',
                    color: p.status === 'default' ? 'white' : 'var(--docs-text-muted)',
                  }}>
                    {p.status === 'default' ? 'default' : p.status}
                  </span>
                </div>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--docs-text-muted)', margin: 0 }}>{p.note}</p>
              <code style={{ fontSize: '0.75rem', background: 'var(--docs-code-bg)', padding: '3px 6px', borderRadius: 4 }}>{p.env}</code>
              <p style={{ fontSize: '0.78rem', color: 'var(--docs-text-muted)', margin: 0 }}>
                <em>Models: {p.models}</em>
              </p>
            </div>
          ))}
        </div>

        <h3>Switching providers</h3>
        <p>Edit <code>.env</code> and restart the backend. No code changes needed anywhere:</p>
        <CodeFile label=".env">
          <pre><code>{`# Local (default)
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b

# Groq — fastest hosted option
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# Any OpenAI-compatible endpoint (OpenRouter, LM Studio, llama.cpp)
LLM_PROVIDER=openai-compatible
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-...
OPENAI_MODEL=meta-llama/llama-3.3-70b-instruct`}</code></pre>
        </CodeFile>

        <h3>Separate coding model</h3>
        <p>
          The coding agent can use a different model from the chat LLM — useful if you want
          a specialist coder locally while routing conversation to a cloud provider:
        </p>
        <CodeFile label=".env">
          <pre><code>{`LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

# Override just the coding agent to a local coder
CODING_PROVIDER=ollama
CODING_MODEL=qwen2.5-coder:7b`}</code></pre>
        </CodeFile>
      </section>

      {/* ── HTTP API quick start ──────────────────────────────── */}
      <section>
        <h2 id="http-quickstart">HTTP API quick start</h2>

        <h3>1. Start the backend</h3>
        <pre><code>{`cd /path/to/Luna
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8899`}</code></pre>

        <p>The Swagger UI is available at <code>http://localhost:8899/docs</code> once running.</p>

        <h3>2. Stream a chat response (Python)</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`import httpx

with httpx.stream(
    "POST", "http://localhost:8899/api/chat/stream",
    json={"message": "Summarise my tasks for today", "conversation_id": None},
    timeout=60,
) as r:
    for line in r.iter_lines():
        if line.startswith("data: "):
            print(line[6:], end="", flush=True)`}</code></pre>
        </CodeFile>

        <h3>2b. Stream a chat response (JavaScript / Node)</h3>
        <CodeFile label="my_app.js">
          <pre><code>{`const response = await fetch('http://localhost:8899/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'What is on my calendar today?', conversation_id: null }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  for (const line of chunk.split('\\n')) {
    if (line.startsWith('data: ')) process.stdout.write(line.slice(6));
  }
}`}</code></pre>
        </CodeFile>

        <h3>2c. Non-streaming (single response)</h3>
        <pre><code>{`curl -s -X POST http://localhost:8899/api/chat \\
  -H 'Content-Type: application/json' \\
  -d '{"message": "What can you do?"}' | jq .response`}</code></pre>

        <h3>3. Run the coding agent</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`with httpx.stream(
    "POST", "http://localhost:8899/api/coding/stream",
    json={
        "message": "Create a FastAPI endpoint that returns a hello world JSON",
        "workspace_root": "/my/project",
    },
    timeout=120,
) as r:
    for line in r.iter_lines():
        if line.startswith("data: "):
            import json
            event = json.loads(line[6:])
            print(event["type"], "→", event.get("content", "")[:80])`}</code></pre>
        </CodeFile>

        <Callout type="note" title="SSE event types from the coding agent">
          <code>workspace_index</code> · <code>plan</code> · <code>tool_call</code> · <code>tool_result</code> · <code>token</code> · <code>done</code> · <code>error</code>
        </Callout>
      </section>

      {/* ── Python import quick start ─────────────────────────── */}
      <section>
        <h2 id="python-quickstart">Python import quick start</h2>
        <p>
          Install the backend dependencies once, then import any service directly.
          No server needed.
        </p>
        <pre><code>{`pip install -r /path/to/Luna/backend/requirements.txt`}</code></pre>

        <h3>LLM — streaming</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`import asyncio, sys
sys.path.insert(0, "/path/to/Luna")

from backend.services.llm import ollama

async def main():
    async for token in ollama.stream_chat(
        messages=[{"role": "user", "content": "Explain async/await in Python"}],
        system_prompt="You are a concise technical writer.",
    ):
        print(token, end="", flush=True)

asyncio.run(main())`}</code></pre>
        </CodeFile>

        <h3>LLM — one-shot completion</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`result = asyncio.run(
    ollama.complete("Extract the key topics from: " + my_text, temperature=0.2)
)
print(result)`}</code></pre>
        </CodeFile>

        <h3>Memory — store and retrieve facts</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`from backend.services.memory_manager import MemoryManager
from backend.models.database import SessionLocal

db = SessionLocal()
mm = MemoryManager(db)

# Store a fact
asyncio.run(mm.store_fact(
    "User prefers dark mode",
    category="preference",
    importance=0.8,
))

# Retrieve semantically relevant facts
facts = asyncio.run(mm.retrieve_relevant("what UI preferences does the user have?"))
for f in facts:
    print(f.content, f.confidence)

db.close()`}</code></pre>
        </CodeFile>

        <h3>Personality — build a system prompt</h3>
        <CodeFile label="my_app.py">
          <pre><code>{`from backend.services.personality import PersonalityEngine
from backend.models.database import SessionLocal

db = SessionLocal()
engine = PersonalityEngine(db)

# Update mood based on the user's last message
engine.update_mood("I'm so excited about this!")

# Get a personality-aware system prompt
prompt = engine.build_personality_prompt(user_name="Alex")
print(prompt[:300])
db.close()`}</code></pre>
        </CodeFile>
      </section>

      {/* ── Service map ───────────────────────────────────────── */}
      <section>
        <h2 id="service-map">Service map</h2>
        <p>Every Luna service lives in <code>backend/services/</code> and is documented on its own page.</p>
        <table>
          <thead>
            <tr><th>Service</th><th>What it does</th></tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <tr key={s.name}>
                <td><a href={s.href}><strong>{s.name}</strong></a></td>
                <td>{s.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ── Next steps ────────────────────────────────────────── */}
      <section>
        <h2 id="next">Next steps</h2>
        <NextSteps items={[
          { href: '/services/llm',            label: 'Service', title: 'LLM Service',        desc: 'Streaming, completion, embeddings across all providers.' },
          { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager',     desc: 'Store facts, run semantic search, compact conversations.' },
          { href: '/api-reference',           label: 'Reference', title: 'API Reference',    desc: 'Full HTTP endpoint and SSE event documentation.' },
          { href: '/mcp',                     label: 'MCP', title: 'MCP Servers',            desc: 'Connect Luna to Claude Desktop and agent frameworks.' },
        ]} />
      </section>

    </DocsLayout>
  );
}

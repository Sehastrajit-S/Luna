import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, PropTable, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',   label: 'Overview' },
  { id: 'config',     label: 'Configuration' },
  { id: 'stream',     label: 'stream_chat()' },
  { id: 'complete',   label: 'complete()' },
  { id: 'embed',      label: 'embed()' },
  { id: 'providers',  label: 'Provider notes' },
  { id: 'singleton',  label: 'The ollama singleton' },
  { id: 'http',       label: 'Via HTTP' },
];

export default function LLMService() {
  return (
    <DocsLayout
      title="LLM Service"
      description="Unified streaming and completion client supporting Ollama, OpenAI, Anthropic, Google, Groq, Cohere, Mistral, and NVIDIA NIM."
      toc={toc}
    >

      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>backend/services/llm/</code> is Luna's unified LLM abstraction layer. It exposes a
          single <code>LLMClient</code> class whose methods (<code>stream_chat</code>, <code>complete</code>,
          <code>embed</code>) route to whichever provider is configured in <code>.env</code> — your
          calling code never changes when you swap providers.
        </p>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>llm/providers.py</code></td><td>All per-provider streaming generators and non-streaming completions.</td></tr>
            <tr><td><code>llm/client.py</code></td><td><code>LLMClient</code> class + <code>ollama</code> singleton.</td></tr>
            <tr><td><code>llm/__init__.py</code></td><td>Public re-exports.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="config">Configuration</h2>
        <p>Set <code>LLM_PROVIDER</code> in <code>.env</code> and supply the matching key/model:</p>
        <CodeFile label=".env — provider options">
          <pre><code>{`# ── Ollama (local, default) ──────────────────────────────────────
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

# ── OpenAI or any OpenAI-compatible endpoint ─────────────────────
LLM_PROVIDER=openai-compatible
OPENAI_BASE_URL=https://api.openai.com/v1   # or LM Studio / Jan.ai / OpenRouter
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

# ── Anthropic Claude ─────────────────────────────────────────────
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# ── Google Gemini ─────────────────────────────────────────────────
LLM_PROVIDER=google
GOOGLE_API_KEY=AIza...
GOOGLE_MODEL=gemini-2.0-flash

# ── Groq ──────────────────────────────────────────────────────────
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# ── Cohere ────────────────────────────────────────────────────────
LLM_PROVIDER=cohere
COHERE_API_KEY=...
COHERE_MODEL=command-r-plus

# ── Mistral AI ────────────────────────────────────────────────────
LLM_PROVIDER=mistral
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-large-latest

# ── NVIDIA NIM ────────────────────────────────────────────────────
LLM_PROVIDER=nvidia-nim
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_API_KEY=nvapi-...
NVIDIA_NIM_MODEL=meta/llama-3.1-8b-instruct`}</code></pre>
        </CodeFile>

        <h3>Embeddings provider</h3>
        <p>
          Embeddings (used by the memory manager) can use a different provider from chat:
        </p>
        <CodeFile label=".env">
          <pre><code>{`# Use Ollama for chat but OpenAI for embeddings (higher quality vectors)
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=openai-compatible
OPENAI_API_KEY=sk-...
OPENAI_EMBED_MODEL=text-embedding-3-small`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="stream">stream_chat()</h2>
        <p>
          Returns an async generator that yields string tokens as they arrive from the model.
          This is the method used by every chat router, coding agent, and streaming response.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def stream_chat(
    messages: list[dict],      # [{"role": "user"|"assistant", "content": "..."}]
    system_prompt: str,
    *,
    num_ctx: int | None = None,    # Ollama only: context window override
    num_predict: int | None = None,# Ollama only: max new tokens override
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]`}</code></pre>
        </CodeFile>

        <h3>Usage</h3>
        <CodeFile label="example.py">
          <pre><code>{`import asyncio
from backend.services.llm import ollama

async def main():
    messages = [
        {"role": "user", "content": "Explain how transformers work."}
    ]
    async for token in ollama.stream_chat(messages, system_prompt="Be concise."):
        print(token, end="", flush=True)

asyncio.run(main())`}</code></pre>
        </CodeFile>

        <h3>Multi-turn conversation</h3>
        <CodeFile label="example.py">
          <pre><code>{`history = []
while True:
    user_input = input("You: ")
    history.append({"role": "user", "content": user_input})

    response = ""
    async for token in ollama.stream_chat(history, system_prompt="You are helpful."):
        print(token, end="", flush=True)
        response += token

    history.append({"role": "assistant", "content": response})
    print()`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="complete">complete()</h2>
        <p>
          Non-streaming, awaitable completion. Used internally by the memory manager for
          fact extraction and contradiction detection.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def complete(
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
) -> str`}</code></pre>
        </CodeFile>

        <h3>Usage</h3>
        <CodeFile label="example.py">
          <pre><code>{`import asyncio
from backend.services.llm import ollama

result = asyncio.run(
    ollama.complete(
        "Extract the main topics from this text: " + document,
        system="Return a JSON list of strings.",
        temperature=0.1,
    )
)
print(result)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="embed">embed()</h2>
        <p>
          Generates a float embedding vector for a piece of text. Used by the memory manager
          to store and retrieve facts via semantic similarity.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def embed(text: str) -> list[float]`}</code></pre>
        </CodeFile>

        <h3>Usage</h3>
        <CodeFile label="example.py">
          <pre><code>{`vector = asyncio.run(ollama.embed("the user prefers dark mode"))
print(len(vector))  # 768 for nomic-embed-text, 1536 for text-embedding-3-small`}</code></pre>
        </CodeFile>

        <Callout type="note">
          Returns an empty list if the embedding provider is not configured or unavailable.
          Always check <code>len(vector) {'>'} 0</code> before storing.
        </Callout>
      </section>

      <section>
        <h2 id="providers">Provider notes</h2>

        <h3>Ollama — adaptive context window</h3>
        <p>
          Luna automatically sizes the Ollama context window based on actual prompt length
          rather than always allocating the full 8 192-token KV cache. This reduces TTFT
          by 20–40% on short turns. Override with <code>num_ctx</code> if needed:
        </p>
        <pre><code>{`async for token in ollama.stream_chat(msgs, sys, num_ctx=4096, num_predict=512):
    ...`}</code></pre>

        <h3>OpenAI-compatible — any endpoint</h3>
        <p>
          Setting <code>LLM_PROVIDER=openai-compatible</code> works with OpenAI,
          OpenRouter, LM Studio, Jan.ai, llama.cpp, Ollama's OpenAI-compat endpoint,
          and any server that exposes <code>/chat/completions</code>.
        </p>

        <h3>Anthropic — max tokens</h3>
        <p>
          The Anthropic streaming handler hard-codes <code>max_tokens=8192</code> for
          <code>stream_chat</code> and <code>max_tokens=4096</code> for <code>complete</code>.
          Adjust in <code>llm/providers.py</code> if you need longer outputs.
        </p>

        <h3>Groq — rate limits</h3>
        <p>
          Groq free tier has per-minute token limits. If you hit them, catch
          <code>httpx.HTTPStatusError</code> (status 429) and back off.
        </p>
      </section>

      <section>
        <h2 id="singleton">The <code>ollama</code> singleton</h2>
        <p>
          <code>from backend.services.llm import ollama</code> gives you a pre-created
          <code>LLMClient()</code> instance. This is a convenience — it reads the provider
          from settings at <em>call time</em>, not at import time, so changing <code>.env</code>
          and restarting is all that's needed to swap providers.
        </p>
        <p>
          The name <code>ollama</code> is historical (Luna originally only supported Ollama).
          It is now a fully multi-provider client regardless of its name.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.llm import ollama, LLMClient

# Using the shared singleton (recommended)
await ollama.complete("Hello")

# Or create your own client with different settings
client = LLMClient()
print(client.provider)   # reads LLM_PROVIDER from .env
print(client.model)      # resolves to the correct model name`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="http">Via HTTP</h2>
        <p>The LLM service powers every chat endpoint. You don't call it directly over HTTP —
        you call the chat router which invokes it internally:</p>
        <table>
          <thead><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>/api/chat/stream</code></td><td>POST (SSE)</td><td>Streaming chat with memory + personality.</td></tr>
            <tr><td><code>/api/chat</code></td><td>POST</td><td>Non-streaming chat.</td></tr>
            <tr><td><code>/api/coding/stream</code></td><td>POST (SSE)</td><td>Coding agent with tool calls.</td></tr>
          </tbody>
        </table>
        <p>See <a href="/api-reference">API Reference</a> for full request/response shapes.</p>
      </section>

      <NextSteps items={[
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'Use the LLM output to extract and store long-term facts.' },
        { href: '/services/personality',   label: 'Service', title: 'Personality Engine', desc: 'Build mood-aware system prompts using LLMClient.' },
        { href: '/sdk-overview',           label: 'Guide',   title: 'SDK Overview', desc: 'See all integration paths and provider compatibility.' },
      ]} />

    </DocsLayout>
  );
}

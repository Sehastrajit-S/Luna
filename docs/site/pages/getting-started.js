import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'variants',     label: 'Choose a variant' },
  { id: 'oneliner',     label: 'One-liner setup' },
  { id: 'docker',       label: 'Docker (any device)' },
  { id: 'desktop',      label: 'Desktop install' },
  { id: 'providers',    label: 'LLM provider' },
  { id: 'verify',       label: 'Verify setup' },
  { id: 'next',         label: 'Next steps' },
];

export default function GettingStarted() {
  return (
    <DocsLayout
      title="Getting Started"
      description="Choose your variant, pick an LLM provider, and have Luna running in under 5 minutes — locally or via Docker."
      toc={toc}
    >

      {/* ── Variants ── */}
      <section>
        <h2 id="variants">Choose a variant</h2>
        <p>
          Luna ships in two flavours. Choose the one that matches your use case —
          the setup wizard will configure everything automatically.
        </p>

        <table>
          <thead>
            <tr><th>Variant</th><th>Best for</th><th>Key features</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Personal</strong></td>
              <td>Individual daily use</td>
              <td>Voice, vision, Spotify, maps, desktop automation. Casual tone. No auth required.</td>
            </tr>
            <tr>
              <td><strong>Business</strong></td>
              <td>Teams &amp; companies</td>
              <td>Professional tone, multi-user JWT auth, rate limiting, Slack/Telegram/Discord channels.</td>
            </tr>
          </tbody>
        </table>

        <Callout type="info" title="Switching later">
          <p>Change <code>luna_variant=personal</code> or <code>luna_variant=business</code> in
          your <code>.env</code> at any time and restart. No data is lost.</p>
        </Callout>
      </section>

      {/* ── One-liner ── */}
      <section>
        <h2 id="oneliner">One-liner setup</h2>
        <p>
          The fastest path — clones the repo, walks you through variant + provider selection,
          installs all dependencies, and pulls Ollama models automatically.
        </p>

        <CodeFile label="terminal">
          <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git
cd Luna
npm install
npm run luna -- setup`}</code></pre>
        </CodeFile>

        <p>The interactive setup prompt:</p>
        <CodeFile label="output">
          <pre><code>{`  Choose your variant

  1. Personal
     Voice, vision, desktop automation, Spotify, maps.
     Casual AI companion. Single user. No auth required.

  2. Business
     Professional team assistant. Multi-user JWT auth.
     Rate limiting, Slack/Telegram/Discord channels.

  Enter 1 or 2 (default: 1): _`}</code></pre>
        </CodeFile>

        <p>After setup completes:</p>
        <CodeFile label="terminal">
          <pre><code>{`# Personal — full desktop stack
luna dev

# Business — Docker with rate limiting and auth enforced
luna docker:business`}</code></pre>
        </CodeFile>
      </section>

      {/* ── Docker ── */}
      <section>
        <h2 id="docker">Docker (any device)</h2>
        <p>
          The easiest path for servers, NAS boxes, or any machine you don't want to
          install Python on. Requires Docker Desktop or Docker Engine.
        </p>

        <h3>Personal — local Ollama (CPU)</h3>
        <CodeFile label="terminal">
          <pre><code>{`cp .env.personal.example .env   # edit model / location
docker compose up -d
open http://localhost:8899`}</code></pre>
        </CodeFile>

        <h3>Personal — NVIDIA GPU</h3>
        <CodeFile label="terminal">
          <pre><code>{`docker compose -f compose.yml -f compose.gpu.yml up -d`}</code></pre>
        </CodeFile>

        <h3>Personal — cloud LLM (no Ollama)</h3>
        <CodeFile label="terminal">
          <pre><code>{`# Set llm_provider + API key in .env first
docker compose -f compose.cloud.yml up -d`}</code></pre>
        </CodeFile>

        <h3>Business variant</h3>
        <CodeFile label="terminal">
          <pre><code>{`cp .env.business.example .env
# Edit .env — set jwt_secret, business_name, llm_provider
docker compose -f compose.business.yml up -d`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="luna docker command">
          <p>After <code>npm install</code>, the CLI auto-detects the right compose file based
          on <code>luna_variant</code> and <code>llm_provider</code> in your <code>.env</code>:</p>
          <pre><code>{`npm run luna -- docker        # auto-detect
npm run luna -- docker:business  # force business
npm run luna -- docker:gpu    # force GPU`}</code></pre>
        </Callout>
      </section>

      {/* ── Desktop install ── */}
      <section>
        <h2 id="desktop">Desktop install</h2>
        <p>Required for voice, camera, screen vision, Electron window, and OS-level automation.</p>

        <table>
          <thead><tr><th>Tool</th><th>Version</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td>Node.js</td><td>18+</td><td>Required by Electron and Vite.</td></tr>
            <tr><td>Python</td><td>3.10+</td><td>Required by the FastAPI backend.</td></tr>
            <tr><td>Ollama</td><td>Latest</td><td>Only if using local LLM inference.</td></tr>
          </tbody>
        </table>

        <Steps>
          <Step num={1} title="Run the setup wizard">
            <CodeFile label="terminal">
              <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git
cd Luna && npm install && npm run luna -- setup`}</code></pre>
            </CodeFile>
            <p>This installs all Node and Python dependencies, creates <code>.env</code>, and pulls
            Ollama models. Takes about 2 minutes on a fast connection.</p>
          </Step>

          <Step num={2} title="Edit .env">
            <p>Open <code>.env</code> and confirm the model name, your location for weather, and
            optionally your name:</p>
            <CodeFile label=".env">
              <pre><code>{`user_name=your_name
weather_city=London
weather_lat=51.5074
weather_lon=-0.1278`}</code></pre>
            </CodeFile>
          </Step>

          <Step num={3} title="Start Luna">
            <CodeFile label="terminal">
              <pre><code>{`luna dev         # Electron + Vite + FastAPI
# or
luna backend     # FastAPI only (use the browser UI)
# or
luna web         # Backend + browser UI, no Electron`}</code></pre>
            </CodeFile>
          </Step>
        </Steps>
      </section>

      {/* ── LLM provider ── */}
      <section>
        <h2 id="providers">LLM provider</h2>
        <p>
          Luna works with 8 providers out of the box. Switch by setting <code>llm_provider</code> in
          <code>.env</code> — no code changes, no restart of anything else.
        </p>

        <table>
          <thead><tr><th>Provider</th><th><code>llm_provider</code></th><th>Key needed</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td>Ollama (default)</td><td><code>ollama</code></td><td>None</td><td>Fully local. Pull any model with <code>ollama pull</code>.</td></tr>
            <tr><td>OpenAI</td><td><code>openai-compatible</code></td><td><code>openai_api_key</code></td><td>Also covers LM Studio, OpenRouter, Jan.ai, llama.cpp.</td></tr>
            <tr><td>NVIDIA NIM</td><td><code>nvidia-nim</code></td><td><code>nvidia_nim_api_key</code></td><td>OpenAI-compatible NVIDIA-hosted or self-hosted NIM endpoint.</td></tr>
            <tr><td>Anthropic Claude</td><td><code>anthropic</code></td><td><code>anthropic_api_key</code></td><td>Native Messages API. Recommended for business.</td></tr>
            <tr><td>Google Gemini</td><td><code>google</code></td><td><code>google_api_key</code></td><td>Gemini 2.0 Flash by default. Long context, multimodal.</td></tr>
            <tr><td>Groq</td><td><code>groq</code></td><td><code>groq_api_key</code></td><td>~300 tok/s. Free tier. Fastest cloud option.</td></tr>
            <tr><td>Cohere</td><td><code>cohere</code></td><td><code>cohere_api_key</code></td><td>Command R+. Strong RAG performance.</td></tr>
            <tr><td>Mistral AI</td><td><code>mistral</code></td><td><code>mistral_api_key</code></td><td>Mistral Large. European-hosted, GDPR-friendly.</td></tr>
          </tbody>
        </table>

        <p>Example — switch to Anthropic:</p>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=anthropic
anthropic_api_key=sk-ant-...
anthropic_model=claude-sonnet-4-5`}</code></pre>
        </CodeFile>

        <p>Example — switch to Groq (free tier, fastest):</p>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=groq
groq_api_key=gsk_...
groq_model=llama-3.3-70b-versatile`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="OpenRouter — one key for everything">
          <p>Use <code>openai-compatible</code> with OpenRouter to access Claude, Gemini, GPT-4o,
          Mistral, and hundreds of other models through a single API key and pay-per-token pricing:</p>
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://openrouter.ai/api/v1
openai_api_key=sk-or-...
openai_model=anthropic/claude-opus-4`}</code></pre>
        </Callout>
      </section>

      {/* ── Verify ── */}
      <section>
        <h2 id="verify">Verify setup</h2>

        <CodeFile label="terminal">
          <pre><code>{`# Check all tools are installed
luna doctor

# Check the running backend is healthy
luna health

# Quick terminal chat (backend must be running)
luna chat`}</code></pre>
        </CodeFile>

        <CodeFile label="output (doctor)">
          <pre><code>{`  ✓ Node.js 20.x
  ✓ npm 10.x
  ✓ Python 3.11
  ✓ Ollama running
  ✓ Docker available`}</code></pre>
        </CodeFile>

        <Callout type="warn" title="Port 8899 already in use">
          <p>Kill any existing Luna process or change <code>port=8900</code> in <code>.env</code>.
          See <a href="/troubleshooting" style={{ color: '#7c3aed' }}>Troubleshooting</a> for more.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/environment',  label: 'Config',    title: 'Environment',      desc: 'Every .env key for all 8 LLM providers, channels, auth, and rate limiting.' },
        { href: '/integrations', label: 'Integrate', title: 'Integrations',     desc: 'All supported providers, apps, messaging channels, and platforms.' },
        { href: '/voice',        label: 'Feature',   title: 'Voice setup',      desc: 'Configure wake-word, STT model, TTS voice, and push-to-talk.' },
        { href: '/agent',        label: 'Agent',     title: 'Agent & Skills',   desc: 'Permission system, custom skills, and workspace.' },
      ]} />
    </DocsLayout>
  );
}

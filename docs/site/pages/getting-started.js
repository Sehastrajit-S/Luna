import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'quick',        label: 'Quick start' },
  { id: 'variants',     label: 'Choose a variant' },
  { id: 'oneliner',     label: 'Setup from source' },
  { id: 'docker',       label: 'Docker (any device)' },
  { id: 'desktop',      label: 'Desktop app' },
  { id: 'providers',    label: 'LLM provider' },
  { id: 'verify',       label: 'Verify setup' },
  { id: 'next',         label: 'Next steps' },
];

export default function GettingStarted() {
  return (
    <DocsLayout
      title="Getting Started"
      description="Have Luna running in a few minutes with Docker, the Windows app, or from source, then reach it from any device."
      toc={toc}
    >

      <section>
        <h2 id="quick">Quick start</h2>
        <CodeFile label="any OS with Docker">
          <pre><code>{`docker run -d --name luna --restart unless-stopped \\
  -p 127.0.0.1:8899:8899 -v luna_data:/app/data \\
  ghcr.io/sehastrajit-s/luna:latest`}</code></pre>
        </CodeFile>
        <p>
          Open <strong>http://localhost:8899</strong> and choose a model in Settings. Prefer an app? Get the Windows
          installer from <Link href="/downloads">Downloads</Link>. Want it on your phone? See
          <Link href="/setup#remote"> Setup: Remote over Tailscale</Link>.
        </p>
      </section>

      {/* ── Variants ── */}
      <section>
        <h2 id="variants">Choose a variant</h2>
        <p>
          Luna ships in two flavours. The setup wizard configures whichever you pick.
        </p>

        <table>
          <thead>
            <tr><th>Variant</th><th>Best for</th><th>Key features</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Personal</strong></td>
              <td>Individual daily use</td>
              <td>Voice, meeting mode, news, store prices, Spotify, desktop automation. Casual tone. No auth required.</td>
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
        <h2 id="oneliner">Setup from source</h2>
        <p>
          Clones the repo, walks you through variant and provider selection, installs all dependencies,
          and pulls Ollama models. Needs Node.js 18+ and Python 3.10+.
        </p>

        <CodeFile label="terminal">
          <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git
cd Luna
npm install
npm run setup`}</code></pre>
        </CodeFile>

        <p>The interactive setup prompt:</p>
        <CodeFile label="output">
          <pre><code>{`  Choose your variant

  1. Personal
     Voice, desktop automation, Spotify, maps.
     Casual AI companion. Single user. No auth required.

  2. Business
     Professional team assistant. Multi-user JWT auth.
     Rate limiting, Slack/Telegram/Discord channels.

  Enter 1 or 2 (default: 1): _`}</code></pre>
        </CodeFile>

        <p>After setup completes:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run web                 # Luna at http://localhost:8899
npm run serve:tailscale     # same, shared to your devices over Tailscale
npm run luna -- docker:business   # business variant in Docker`}</code></pre>
        </CodeFile>
      </section>

      {/* ── Docker ── */}
      <section>
        <h2 id="docker">Docker (any device)</h2>
        <p>
          The easiest path for servers, NAS boxes, or any machine you don't want to install Python on.
          The image is <code>ghcr.io/sehastrajit-s/luna</code> (amd64 and arm64). From a clone of the repo:
        </p>
        <CodeFile label="terminal">
          <pre><code>{`docker compose -f deploy/compose.yml up -d                              # Luna + Ollama (CPU)
docker compose -f deploy/compose.yml -f deploy/compose.gpu.yml up -d    # NVIDIA GPU
docker compose -f deploy/compose.cloud.yml up -d                        # cloud model, no Ollama
docker compose -f deploy/compose.business.yml up -d                     # business variant`}</code></pre>
        </CodeFile>
        <p>A <code>.env</code> is optional: settings saved in the browser persist in the data volume. See <Link href="/docker">Docker</Link> for volumes and upgrades.</p>
      </section>

      {/* ── Desktop install ── */}
      <section>
        <h2 id="desktop">Desktop app</h2>
        <p>The desktop app adds push-to-talk (Alt+L), a tray icon, and desktop automation on Windows.</p>
        <Steps>
          <Step num={1} title="Install">
            <p>Run <code>Luna-Setup-&lt;version&gt;.exe</code> from <Link href="/downloads">Downloads</Link>, or build it yourself with <code>npm run build:desktop</code> (output in <code>dist/desktop</code>).</p>
          </Step>
          <Step num={2} title="Pick a server">
            <p>
              Settings → Server: <strong>This computer</strong> starts a local server with your Python
              (install <code>server/requirements.txt</code> once), or uses one already running on port 8899.
              <strong> Remote over Tailscale</strong> finds your Luna on another machine.
            </p>
          </Step>
          <Step num={3} title="Personalise">
            <p>Your name, weather location and model can be set in Settings or in <code>.env</code>:</p>
            <CodeFile label=".env">
              <pre><code>{`user_name=your_name
weather_city=London
weather_lat=51.5074
weather_lon=-0.1278`}</code></pre>
            </CodeFile>
          </Step>
        </Steps>
      </section>

      {/* ── LLM provider ── */}
      <section>
        <h2 id="providers">LLM provider</h2>
        <p>
          Luna works with 8 providers out of the box. Pick one in Settings → AI model, or set
          <code>llm_provider</code> in <code>.env</code>.
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

        <p>Example - switch to Anthropic:</p>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=anthropic
anthropic_api_key=sk-ant-...
anthropic_model=claude-sonnet-4-5`}</code></pre>
        </CodeFile>

        <p>Example - switch to Groq (free tier, fastest):</p>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=groq
groq_api_key=gsk_...
groq_model=llama-3.3-70b-versatile`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="OpenRouter - one key for everything">
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
npm run luna -- doctor

# Check the running server is healthy
npm run health

# Quick terminal chat (server must be running)
npm run chat`}</code></pre>
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
          See <Link href="/troubleshooting">Troubleshooting</Link> for more.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/setup',        label: 'Setup',     title: 'Local & Remote',   desc: 'Use Luna from your phone and other computers over Tailscale.' },
        { href: '/environment',  label: 'Config',    title: 'Environment',      desc: 'Every .env key for all 8 LLM providers, channels, auth, and rate limiting.' },
        { href: '/integrations', label: 'Integrate', title: 'Integrations',     desc: 'All supported providers, apps, messaging channels, and platforms.' },
        { href: '/voice',        label: 'Feature',   title: 'Voice setup',      desc: 'Configure wake-word, STT model, TTS voice, and push-to-talk.' },
        { href: '/agent',        label: 'Agent',     title: 'Agent & Skills',   desc: 'Permission system, custom skills, and workspace.' },
      ]} />
    </DocsLayout>
  );
}

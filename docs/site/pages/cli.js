import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'usage',    label: 'Usage' },
  { id: 'commands', label: 'Commands' },
  { id: 'docker',   label: 'Docker commands' },
  { id: 'global',   label: 'Global install' },
  { id: 'workflow', label: 'Developer workflow' },
];

export default function CLI() {
  return (
    <DocsLayout
      title="CLI"
      description="The Luna CLI wraps every developer and operations script into a single consistent interface. Set up, run, build, check, and debug the full stack from one command."
      toc={toc}
    >
      <section>
        <h2 id="usage">Usage</h2>
        <p>Install the CLI globally on macOS, Windows, or Linux:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm i -g luna-workspace`}</code></pre>
        </CodeFile>

        <p>Shortest first run without a permanent install:</p>

        <CodeFile label="terminal">
          <pre><code>{`npx luna-workspace setup`}</code></pre>
        </CodeFile>

        <p>If the npm package is not published yet, install directly from GitHub:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm i -g github:Sehastrajit-S/Luna`}</code></pre>
        </CodeFile>

        <p>Run the CLI from the repository root:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- <command>`}</code></pre>
        </CodeFile>

        <p>The double dash (<code>--</code>) is required by npm to pass arguments to the script.
        Everything after it is forwarded to <code>interfaces/cli/luna.mjs</code>.</p>

        <p>After running <code>npm link</code> (see <a href="#global">Global install</a>), you can
        drop the <code>npm run luna --</code> prefix and just use <code>luna</code>:</p>

        <CodeFile label="terminal">
          <pre><code>{`luna setup      # first-time wizard
luna dev        # start desktop stack
luna docker     # start via Docker (auto-detects mode)
luna help       # list all commands`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="commands">Commands</h2>

        <table>
          <thead><tr><th>Command</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>help</code></td><td>Print command list and usage.</td></tr>
            <tr><td><code>install:command</code></td><td>Print the one-line global CLI installer.</td></tr>
            <tr><td><code>setup</code></td><td>Interactive first-time wizard — selects variant, installs dependencies, creates <code>.env</code>, and pulls Ollama models.</td></tr>
            <tr><td><code>doctor</code></td><td>Verify Node.js, npm, Python, Ollama, and Docker are installed and at the right versions.</td></tr>
            <tr><td><code>health</code></td><td>Hit the running backend's <code>/api/system/health</code> endpoint and display the JSON response.</td></tr>
            <tr><td><code>chat</code></td><td>Start an interactive terminal chat session with a running Luna backend. Pass a message as an argument for a one-shot query.</td></tr>
            <tr><td><code>web</code></td><td>Start the server and open Luna in your browser at <code>http://localhost:8899</code>.</td></tr>
            <tr><td><code>web:lan</code></td><td>Same as <code>web</code>, reachable from phones and tablets on your network.</td></tr>
            <tr><td><code>dev</code> / <code>dev:lan</code></td><td>Aliases for <code>web</code> / <code>web:lan</code>.</td></tr>
            <tr><td><code>serve</code></td><td>Start the server. <code>--tailscale</code> also shares it with your tailnet over HTTPS port 8899; <code>--tailscale --off</code> stops sharing. See <Link href="/remote">Remote access</Link>.</td></tr>
            <tr><td><code>backend</code></td><td>Start only the FastAPI server on port 8899.</td></tr>
            <tr><td><code>frontend</code></td><td>Start only the Vite dev server for the mobile React UI.</td></tr>
            <tr><td><code>tunnel</code></td><td>Expose the Vite dev server through a Cloudflare tunnel.</td></tr>
            <tr><td><code>build</code></td><td>Build the React frontend.</td></tr>
            <tr><td><code>check</code></td><td>Run lightweight Python syntax checks on critical backend files.</td></tr>
            <tr><td><code>processes</code></td><td>Print all registered backend background processes as JSON.</td></tr>
            <tr><td><code>clean</code></td><td>Remove build artifacts and runtime data.</td></tr>
          </tbody>
        </table>

        <h3>npm scripts</h3>
        <p>From a clone, these npm scripts wrap the CLI and the build steps. In PowerShell, prefer them over <code>npm run luna -- …</code>, because PowerShell drops the <code>--</code>.</p>
        <table>
          <thead><tr><th>Script</th><th>Does</th></tr></thead>
          <tbody>
            <tr><td><code>npm run setup</code></td><td>First-time setup wizard.</td></tr>
            <tr><td><code>npm run web</code></td><td>Server + browser UI at <code>http://localhost:8899</code>.</td></tr>
            <tr><td><code>npm run serve:tailscale</code></td><td>Start the server and share it over Tailscale.</td></tr>
            <tr><td><code>npm run serve:tailscale:off</code></td><td>Stop sharing over Tailscale.</td></tr>
            <tr><td><code>npm run build:desktop</code></td><td>Windows installer in <code>dist/desktop/</code>.</td></tr>
            <tr><td><code>npm run build:mobile</code></td><td>Sync the web build into <code>interfaces/mobile</code> for Android Studio / Xcode.</td></tr>
            <tr><td><code>npm run docs</code></td><td>This docs site at <code>http://localhost:3000</code>.</td></tr>
          </tbody>
        </table>

        <h3>setup</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna setup`}</code></pre>
        </CodeFile>
        <p>The interactive wizard on first run:</p>
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
        <p>After variant selection, the wizard prompts for your LLM provider, installs all
        dependencies, and pulls Ollama models if needed. Takes about 2 minutes on a fast connection.</p>

        <h3>doctor</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna doctor`}</code></pre>
        </CodeFile>
        <CodeFile label="output">
          <pre><code>{`  ✓ Node.js 20.x
  ✓ npm 10.x
  ✓ Python 3.11
  ✓ Ollama running
  ✓ Docker available`}</code></pre>
        </CodeFile>

        <h3>health</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna health`}</code></pre>
        </CodeFile>
        <p>Requires the backend to be running. Returns the live system status from
        <code>/api/system/health</code> including LLM provider and active features.</p>

        <h3>chat</h3>
        <CodeFile label="terminal">
          <pre><code>{`# Interactive session
luna chat

# One-shot query
luna chat "what time is it?"

# Auto-approve or auto-deny confirmation prompts
luna chat --yes "create the requested workspace file"
luna chat --no "try this but deny risky actions"`}</code></pre>
        </CodeFile>
        <p>Inside the interactive session, use <code>/new</code> to start a fresh conversation and
        <code>/help</code> for terminal commands. Use <code>/exit</code> to quit.</p>
        <p>The terminal uses the same chat stream as web and Electron. It handles tool confirmations,
        plans, plan progress, proactive messages, command events, web research, workspace file tools,
        installed skills, agent tasks, and Google/Microsoft workspace tool calls.</p>

        <h3>tunnel</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna tunnel`}</code></pre>
        </CodeFile>
        <p>Starts ngrok pointing at the backend port. Requires ngrok to be installed and on
        <code>PATH</code>. Use the printed HTTPS URL as your webhook base when registering
        Telegram, Discord, or Slack integrations during development.</p>

        <h3>check</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna check`}</code></pre>
        </CodeFile>
        <p>Runs <code>python -m py_compile</code> on the critical backend entry points — a fast
        sanity check that catches import errors and syntax mistakes before opening a PR.</p>

        <h3>clean</h3>
        <CodeFile label="terminal">
          <pre><code>{`luna clean`}</code></pre>
        </CodeFile>
        <p>Deletes <code>interfaces/web/dist/</code>, <code>electron/dist/</code>, and any other gitignored
        build artefacts. Does <strong>not</strong> touch <code>data/</code> — your memory and runtime
        data are preserved.</p>

        <Callout type="warn" title="clean does not delete data/">
          <p>If you want to fully reset Luna's memory, personality, and conversation history, manually
          delete <code>data/luna.db</code> and <code>data/chroma/</code>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="docker">Docker commands</h2>
        <p>
          The Docker commands wrap <code>scripts/docker.mjs</code> and auto-detect the right
          compose file based on <code>luna_variant</code> and <code>llm_provider</code> in your
          <code>.env</code>.
        </p>

        <table>
          <thead><tr><th>Command</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>docker</code></td><td>Auto-detect mode from <code>.env</code> and start the appropriate compose stack. Business variant → <code>compose.business.yml</code>, cloud LLM → <code>compose.cloud.yml</code>, GPU detected → GPU overlay, otherwise CPU.</td></tr>
            <tr><td><code>docker:business</code></td><td>Force Business variant compose file regardless of <code>.env</code>.</td></tr>
            <tr><td><code>docker:gpu</code></td><td>Force GPU compose overlay (<code>compose.yml + compose.gpu.yml</code>).</td></tr>
            <tr><td><code>docker:cloud</code></td><td>Force cloud compose file — no Ollama container started.</td></tr>
            <tr><td><code>docker:down</code></td><td>Stop and remove all Luna containers across all compose files.</td></tr>
            <tr><td><code>docker:logs</code></td><td>Tail the Luna container logs in real time.</td></tr>
            <tr><td><code>docker:pull</code></td><td>Re-pull Ollama models into a running container (after changing <code>ollama_model</code> in <code>.env</code>).</td></tr>
          </tbody>
        </table>

        <h3>Auto-detection logic</h3>
        <CodeFile label="detection order">
          <pre><code>{`1. --business flag → compose.business.yml
2. luna_variant=business in .env → compose.business.yml
3. --cloud flag → compose.cloud.yml
4. llm_provider is a cloud provider → compose.cloud.yml
   (anthropic, google, groq, cohere, mistral, openai-compatible, nvidia-nim)
5. --gpu flag → compose.yml + compose.gpu.yml
6. NVIDIA GPU detected on host → GPU overlay
7. fallback → compose.yml (CPU)`}</code></pre>
        </CodeFile>

        <h3>Starting the Business variant</h3>
        <CodeFile label="terminal">
          <pre><code>{`cp deploy/.env.business.example .env
# Edit .env — set jwt_secret, business_name, llm_provider
luna docker:business

# → http://localhost:8899
# → Admin API: http://localhost:8899/api/admin/`}</code></pre>
        </CodeFile>

        <h3>Upgrading</h3>
        <CodeFile label="terminal">
          <pre><code>{`git pull
luna docker      # rebuilds containers with new image`}</code></pre>
        </CodeFile>

        <Callout type="info" title="luna docker vs docker compose">
          <p><code>luna docker</code> does preflight checks, builds containers, pulls Ollama models,
          and waits for the health endpoint before printing the success banner.
          Use raw <code>docker compose</code> commands when you want finer control.</p>
        </Callout>
      </section>

      <section>
        <h2 id="global">Global install</h2>
        <p>
          Link the CLI globally so you can run <code>luna</code> from anywhere instead of
          <code>npm run luna --</code>:
        </p>

        <CodeFile label="terminal">
          <pre><code>{`# From the repo root
npm link

# Now run from anywhere
luna setup
luna dev
luna doctor
luna docker`}</code></pre>
        </CodeFile>

        <p>To unlink later:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm unlink`}</code></pre>
        </CodeFile>

        <Callout type="info" title="Windows PATH">
          <p>On Windows, npm's global bin directory must be on your <code>PATH</code>. If{' '}
          <code>luna</code> isn't found after linking, run <code>npm config get prefix</code> and
          add that path's <code>\bin</code> subdirectory to your environment variables.</p>
        </Callout>
      </section>

      <section>
        <h2 id="workflow">Developer workflow</h2>
        <p>Typical flow for a feature PR:</p>

        <CodeFile label="terminal">
          <pre><code>{`# 1. First time — run setup wizard
luna setup

# 2. Verify dependencies any time
luna doctor

# 3. Start full stack for development
luna dev

# 4. Make your changes in interfaces/web/ or server/

# 5. Check backend syntax hasn't broken
luna check

# 6. Build frontend to catch TypeScript errors
cd frontend && npm run build && cd ..

# 7. Quick smoke test
luna health

# 8. Open PR`}</code></pre>
        </CodeFile>

        <p>If you only need the backend running (e.g. testing API changes with curl):</p>
        <CodeFile label="terminal">
          <pre><code>{`luna backend
# In another terminal:
curl http://localhost:8899/api/system/health`}</code></pre>
        </CodeFile>

        <p>Testing channel integrations locally:</p>
        <CodeFile label="terminal">
          <pre><code>{`luna backend
luna tunnel
# → https://abc123.ngrok-free.app
# Paste that URL into Telegram BotFather / Discord App / Slack App settings`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/contributing',      label: 'Community', title: 'Contributing',       desc: 'Branch conventions, PR checklist, and architecture rules.' },
        { href: '/project-structure', label: 'Platform',  title: 'Project structure',  desc: 'Where every file lives in the monorepo.' },
        { href: '/troubleshooting',   label: 'Support',   title: 'Troubleshooting',    desc: 'Fix common build, port, and backend issues.' },
      ]} />
    </DocsLayout>
  );
}

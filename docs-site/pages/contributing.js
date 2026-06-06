import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'setup',       label: 'Fork & setup' },
  { id: 'branches',    label: 'Branches' },
  { id: 'code-style',  label: 'Code standards' },
  { id: 'arch-rules',  label: 'Architecture rules' },
  { id: 'pr-process',  label: 'PR process' },
  { id: 'checklist',   label: 'PR checklist' },
  { id: 'privacy',     label: 'Privacy rules' },
];

export default function Contributing() {
  return (
    <DocsLayout
      title="Contributing"
      description="How to fork, develop, write a good PR, follow architecture rules, and get your changes merged into L.U.N.A."
      toc={toc}
    >
      <section>
        <h2 id="setup">Fork and set up</h2>
        <p>All contributions go through GitHub pull requests against the <code>main</code> branch.</p>

        <Steps>
          <Step num={1} title="Fork the repository">
            <p>Click <strong>Fork</strong> on <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed' }}>github.com/Sehastrajit/Luna</a>.
            This creates your own copy where you can push changes freely.</p>
          </Step>

          <Step num={2} title="Clone your fork">
            <CodeFile label="terminal">
              <pre><code>{`git clone https://github.com/<your-username>/Luna.git
cd Luna
git remote add upstream https://github.com/Sehastrajit/Luna.git`}</code></pre>
            </CodeFile>
          </Step>

          <Step num={3} title="Install dependencies">
            <CodeFile label="terminal">
              <pre><code>{`npm install
cd frontend && npm install && cd ..
pip install -r backend/requirements.txt`}</code></pre>
            </CodeFile>
          </Step>

          <Step num={4} title="Create your environment file">
            <CodeFile label="terminal">
              <pre><code>{`copy .env.example .env`}</code></pre>
            </CodeFile>
            <p>Set at minimum <code>user_name</code>, <code>ollama_model</code>, and <code>embedding_model</code>.
            See the <a href="/environment" style={{ color: '#7c3aed' }}>Environment</a> page for details.</p>
          </Step>

          <Step num={5} title="Verify everything works">
            <CodeFile label="terminal">
              <pre><code>{`npm run luna -- doctor
npm run luna -- dev`}</code></pre>
            </CodeFile>
          </Step>
        </Steps>
      </section>

      <section>
        <h2 id="branches">Branch naming</h2>
        <p>Use a consistent prefix so PRs are easy to filter:</p>

        <table>
          <thead><tr><th>Prefix</th><th>Use for</th><th>Example</th></tr></thead>
          <tbody>
            <tr><td><code>feature/</code></td><td>New capabilities</td><td><code>feature/spotify-queue-control</code></td></tr>
            <tr><td><code>fix/</code></td><td>Bug fixes</td><td><code>fix/voice-runtime-crash-on-resume</code></td></tr>
            <tr><td><code>docs/</code></td><td>Documentation only</td><td><code>docs/memory-api-reference</code></td></tr>
            <tr><td><code>refactor/</code></td><td>Internal restructuring, no behaviour change</td><td><code>refactor/split-tool-registry</code></td></tr>
            <tr><td><code>chore/</code></td><td>Dependency bumps, config changes</td><td><code>chore/upgrade-electron-32</code></td></tr>
          </tbody>
        </table>

        <CodeFile label="terminal">
          <pre><code>{`# Always branch from an up-to-date main
git fetch upstream
git checkout -b feature/my-feature upstream/main`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="code-style">Code standards</h2>

        <h3>Backend (Python)</h3>
        <ul>
          <li>Routers in <code>backend/routers/</code> must be <strong>thin</strong> — validate the request, call a service, return the result. No business logic in routers.</li>
          <li>All business logic goes in <code>backend/services/</code>. Service functions should be importable and testable in isolation.</li>
          <li>Background jobs belong in <code>backend/processes/</code> and must register themselves in <code>registry.py</code>.</li>
          <li>Use type hints on all function signatures.</li>
          <li>Never use <code>print()</code> for logging — use the Python <code>logging</code> module.</li>
          <li>Avoid non-ASCII characters in log messages — causes <code>UnicodeEncodeError</code> on Windows cp1252.</li>
        </ul>

        <h3>Frontend (TypeScript / React)</h3>
        <ul>
          <li>Components live in <code>frontend/src/components/&lt;Feature&gt;/</code> — group by domain, not by type.</li>
          <li>All backend communication goes through typed wrappers in <code>frontend/src/api/</code>. No raw <code>fetch</code> calls in components.</li>
          <li>Global state mutations go in <code>frontend/src/store/index.ts</code> via Zustand actions.</li>
          <li>New reusable hooks go in <code>frontend/src/hooks/</code>.</li>
          <li>Use TypeScript strictly — no <code>any</code> unless unavoidable, and document why.</li>
        </ul>

        <h3>Electron</h3>
        <ul>
          <li>All native/Node.js APIs must go through the <code>contextBridge</code> in <code>preload.js</code>. Never expose raw Node APIs to the renderer.</li>
          <li>Backend lifecycle management (start, restart, health check) lives in <code>electron/main.js</code> only.</li>
        </ul>
      </section>

      <section>
        <h2 id="arch-rules">Architecture rules</h2>

        <Callout type="warn" title="Read before large changes">
          <p>Read <code>docs/ARCHITECTURE.md</code> before making broad architectural changes.
          Read <code>docs/PROCESSES.md</code> before changing background job behaviour.</p>
        </Callout>

        <table>
          <thead><tr><th>Rule</th><th>Why</th></tr></thead>
          <tbody>
            <tr><td>Business logic in services, not routers</td><td>Routers are tested at the HTTP boundary. Services are testable in isolation and reusable across routes.</td></tr>
            <tr><td>One layer per PR where possible</td><td>Mixing backend + frontend + Electron changes makes review hard and widens blast radius.</td></tr>
            <tr><td>New tools require permission registration</td><td>Every new tool must have a default permission mode in <code>tool_registry.py</code> — defaulting to <code>confirm</code> is safest.</td></tr>
            <tr><td>Agent-created files only in data/workspace/</td><td>Prevents Luna from accidentally modifying source files or user documents outside the sandbox.</td></tr>
            <tr><td>No hardcoded model names in services</td><td>Models are user-configurable via <code>.env</code>. Services must read from <code>config.py</code>.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="pr-process">PR process</h2>
        <p>Here is the full flow from your branch to merged:</p>

        <Steps>
          <Step num={1} title="Run the checks locally">
            <CodeFile label="terminal">
              <pre><code>{`npm run luna -- check          # backend syntax
cd frontend && npm run build   # TypeScript compile`}</code></pre>
            </CodeFile>
            <p>Both must pass cleanly before opening a PR.</p>
          </Step>

          <Step num={2} title="Push and open the PR">
            <CodeFile label="terminal">
              <pre><code>{`git push origin feature/my-feature`}</code></pre>
            </CodeFile>
            <p>Open a PR on GitHub against <code>main</code>. Fill in:</p>
            <ul>
              <li><strong>What changed</strong> — clear one-paragraph summary.</li>
              <li><strong>Why</strong> — motivation, issue link if applicable.</li>
              <li><strong>How to test</strong> — steps the reviewer should follow.</li>
              <li><strong>Screenshots</strong> — for any UI change.</li>
            </ul>
          </Step>

          <Step num={3} title="Address review feedback">
            <p>Push new commits to your branch — don't force-push during review as it makes it harder
            to see what changed. Squash on merge is enabled.</p>
          </Step>

          <Step num={4} title="Merge">
            <p>Once approved, the PR will be squash-merged into <code>main</code>. Your branch is deleted
            automatically.</p>
          </Step>
        </Steps>
      </section>

      <section>
        <h2 id="checklist">PR checklist</h2>
        <p>Run through this before requesting review:</p>

        <ul>
          <li><code>npm run luna -- check</code> passes.</li>
          <li><code>cd frontend && npm run build</code> passes with no TypeScript errors.</li>
          <li>No <code>.env</code>, <code>data/</code>, <code>*.db</code>, or <code>chroma/</code> files staged.</li>
          <li>New backend logic is in <code>services/</code>, not in <code>routers/</code>.</li>
          <li>New tools are registered in <code>tool_registry.py</code> with a default permission mode.</li>
          <li>No hardcoded model names — config reads from <code>config.py</code>.</li>
          <li>No <code>print()</code> statements in backend code — use <code>logging</code>.</li>
          <li>No non-ASCII characters in backend log strings.</li>
          <li>PR description includes what changed, why, and how to test.</li>
          <li>Screenshots included for UI changes.</li>
        </ul>
      </section>

      <section>
        <h2 id="privacy">Privacy rules</h2>
        <ul>
          <li>Never commit <code>.env</code>, <code>data/</code>, <code>*.db</code>, <code>chroma/</code>, or log files.</li>
          <li>Do not submit conversation logs, memory exports, or personal data of any kind.</li>
          <li>API keys, tokens, and secrets are never acceptable in source code — use <code>.env</code> and <code>config.py</code>.</li>
          <li>If your contribution involves external service calls, document which data is sent and ensure users can opt out via configuration.</li>
        </ul>
      </section>

      <NextSteps items={[
        { href: '/architecture',     label: 'Deep dive', title: 'Architecture',       desc: 'Layer boundaries, SSE protocol, and contribution guidelines.' },
        { href: '/project-structure',label: 'Platform',  title: 'Project structure',  desc: 'Where every file lives — before you start editing.' },
        { href: '/cli',              label: 'Platform',  title: 'CLI reference',      desc: 'Build, check, and run the stack from the command line.' },
      ]} />
    </DocsLayout>
  );
}

import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'port',        label: 'Port 8899 conflict' },
  { id: 'ollama',      label: 'Ollama connection' },
  { id: 'chroma',      label: 'ChromaDB errors' },
  { id: 'unicode',     label: 'Windows encoding' },
  { id: 'voice',       label: 'Voice not working' },
  { id: 'frontend',    label: 'Frontend blank screen' },
  { id: 'electron',    label: 'Electron crashes' },
  { id: 'spotify',     label: 'Spotify auth' },
  { id: 'memory',      label: 'Memory not persisting' },
  { id: 'build',       label: 'Build failures' },
];

export default function Troubleshooting() {
  return (
    <DocsLayout
      title="Troubleshooting"
      description="Step-by-step fixes for the most common build, runtime, and integration issues with L.U.N.A."
      toc={toc}
    >
      <section>
        <h2 id="port">Port 8899 conflict</h2>

        <Callout type="warn" title="Symptom">
          <p>Backend fails to start: <code>ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8899)</code></p>
        </Callout>

        <p>Another process is already using port 8899. Find and stop it:</p>

        <CodeFile label="Windows (PowerShell)">
          <pre><code>{`# Find the process holding port 8899
netstat -ano | findstr :8899

# Kill it by PID (replace 12345 with the actual PID from the output above)
taskkill /PID 12345 /F`}</code></pre>
        </CodeFile>

        <CodeFile label="macOS / Linux">
          <pre><code>{`lsof -ti :8899 | xargs kill -9`}</code></pre>
        </CodeFile>

        <p>If you want to run Luna on a different port, set <code>backend_port=9000</code> in your
        <code>.env</code> and update the Vite proxy in <code>frontend/vite.config.ts</code> to match.</p>
      </section>

      <section>
        <h2 id="ollama">Ollama connection refused</h2>

        <Callout type="warn" title="Symptom">
          <p>Chat fails silently or returns: <code>httpx.ConnectError: All connection attempts failed</code>
          in the backend logs.</p>
        </Callout>

        <h3>1. Verify Ollama is running</h3>
        <CodeFile label="terminal">
          <pre><code>{`# Start Ollama (it runs as a background service)
ollama serve

# Confirm it's reachable
curl http://localhost:11434/api/tags`}</code></pre>
        </CodeFile>

        <h3>2. Verify your model is pulled</h3>
        <CodeFile label="terminal">
          <pre><code>{`ollama list

# If your configured model isn't listed, pull it
ollama pull qwen2.5:7b
ollama pull nomic-embed-text`}</code></pre>
        </CodeFile>

        <h3>3. Check config.py values</h3>
        <p>Confirm <code>ollama_model</code> in your <code>.env</code> exactly matches the model name
        shown in <code>ollama list</code> — including the tag (e.g. <code>qwen2.5:7b</code> not just
        <code>qwen2.5</code>).</p>

        <h3>4. Non-default Ollama host</h3>
        <p>If Ollama is running on a different machine or port, set:</p>
        <CodeFile label=".env">
          <pre><code>{`ollama_base_url=http://192.168.1.50:11434`}</code></pre>
        </CodeFile>

        <Callout type="info" title="OpenAI-compatible APIs">
          <p>If you're using OpenRouter, LM Studio, or another OpenAI-compatible API instead of Ollama,
          see the <a href="/environment" style={{color:'#7c3aed'}}>Environment</a> page — the config
          keys are different.</p>
        </Callout>
      </section>

      <section>
        <h2 id="chroma">ChromaDB errors</h2>

        <Callout type="warn" title="Symptom">
          <p>Backend starts but semantic search fails, or logs show:
          <code>chromadb.errors.InvalidCollectionException</code> or <code>sqlite3.DatabaseError: database disk image is malformed</code></p>
        </Callout>

        <h3>Reset the ChromaDB collection</h3>
        <p>The ChromaDB index can be rebuilt from the SQLite facts at any time. Deleting the folder
        triggers an automatic rebuild on next startup:</p>

        <CodeFile label="Windows (PowerShell)">
          <pre><code>{`# Stop the backend first, then:
Remove-Item -Recurse -Force data\chroma`}</code></pre>
        </CodeFile>

        <CodeFile label="macOS / Linux">
          <pre><code>{`rm -rf data/chroma`}</code></pre>
        </CodeFile>

        <p>The next time Luna starts it will re-embed all facts from <code>data/luna.db</code>. For large
        fact collections this may take a few seconds.</p>

        <h3>Embedding model not available</h3>
        <p>ChromaDB silently skips embedding if the embedding model request fails. Confirm the embedding
        model is pulled in Ollama:</p>
        <CodeFile label="terminal">
          <pre><code>{`ollama pull nomic-embed-text`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="unicode">Windows encoding errors (UnicodeEncodeError)</h2>

        <Callout type="warn" title="Symptom">
          <p>Backend crashes on Windows with:
          <code>UnicodeEncodeError: 'charmap' codec can't encode character '✓'</code></p>
        </Callout>

        <p>Windows uses the <code>cp1252</code> code page by default for console output, which cannot
        encode Unicode characters like <code>✓</code>, <code>→</code>, or emoji. Fix this two ways:</p>

        <h3>Option A — Set UTF-8 mode (recommended)</h3>
        <p>Set the environment variable before starting the backend:</p>

        <CodeFile label="Windows (PowerShell)">
          <pre><code>{`$env:PYTHONUTF8 = "1"
npm run luna -- dev`}</code></pre>
        </CodeFile>

        <p>Or add it permanently to your system environment variables via Settings → Advanced → Environment Variables.</p>

        <h3>Option B — Patch the backend code</h3>
        <p>If you're adding new code that logs output, avoid non-ASCII characters in log messages.
        See the <a href="/contributing#code-style" style={{color:'#7c3aed'}}>Contributing</a> page —
        this is an enforced code standard.</p>

        <CodeFile label="backend">
          <pre><code>{`# Bad — will crash on Windows cp1252
logger.info("✓ Memory loaded")

# Good
logger.info("Memory loaded successfully")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="voice">Voice not working</h2>

        <h3>Wake word not triggering</h3>
        <ul>
          <li>Confirm <code>wake_word_enabled=true</code> is set in <code>.env</code>.</li>
          <li>The wake word is case-insensitive. Default is <code>hey luna</code>. Make sure
          <code>wake_word</code> in <code>.env</code> matches what you're saying.</li>
          <li>Check that <code>voice_runtime</code> shows as <code>running</code> in
          <code>GET /api/system/processes</code>.</li>
          <li>Verify your default microphone is selected in OS audio settings.</li>
        </ul>

        <h3>Transcription is inaccurate</h3>
        <p>Switch to a larger Whisper model:</p>
        <CodeFile label=".env">
          <pre><code>{`whisper_model=small    # or medium for best accuracy`}</code></pre>
        </CodeFile>
        <p>Larger models use more RAM but transcribe more accurately. See the
        <a href="/voice#stt" style={{color:'#7c3aed'}}>Voice</a> page for the full tradeoff table.</p>

        <h3>TTS not speaking</h3>
        <ul>
          <li>Confirm your OS volume is not muted.</li>
          <li>List available voices and check the index:</li>
        </ul>
        <CodeFile label="Python">
          <pre><code>{`import pyttsx3
engine = pyttsx3.init()
for i, v in enumerate(engine.getProperty('voices')):
    print(i, v.name)`}</code></pre>
        </CodeFile>
        <p>Set <code>tts_voice_index</code> in <code>.env</code> to a valid index from the output above.</p>

        <h3>Microphone permission denied</h3>
        <p>On Windows, go to Settings → Privacy → Microphone and ensure Desktop apps are allowed to
        access the microphone. On macOS, go to System Settings → Privacy & Security → Microphone.</p>
      </section>

      <section>
        <h2 id="frontend">Frontend blank screen</h2>

        <Callout type="warn" title="Symptom">
          <p>The Vite dev server starts but the browser shows a blank page or a white screen with
          no error.</p>
        </Callout>

        <h3>1. Check the browser console</h3>
        <p>Open DevTools (F12) → Console. A React render error will be logged there with the exact
        component and line.</p>

        <h3>2. Verify the backend is running</h3>
        <p>The frontend makes an API call on mount. If the backend is down:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl http://localhost:8899/health
# Should return: {"status":"ok",...}`}</code></pre>
        </CodeFile>

        <h3>3. Check the proxy config</h3>
        <p>The Vite proxy at <code>frontend/vite.config.ts</code> forwards <code>/api</code> to
        <code>http://localhost:8899</code>. If your backend port differs, update the proxy target.</p>

        <h3>4. TypeScript errors blocking the build</h3>
        <CodeFile label="terminal">
          <pre><code>{`cd frontend
npm run build    # Shows all TypeScript errors`}</code></pre>
        </CodeFile>

        <h3>5. Clear Vite cache</h3>
        <CodeFile label="terminal">
          <pre><code>{`cd frontend
rm -rf node_modules/.vite
npm run dev`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="electron">Electron crashes or won't start</h2>

        <Callout type="warn" title="Symptom">
          <p>The Electron window opens and immediately closes, or shows an error dialog about
          the backend failing to start.</p>
        </Callout>

        <h3>Backend crash loop</h3>
        <p>Electron monitors the FastAPI backend and restarts it up to 3 times within 60 seconds.
        If all 3 attempts fail, it shows an error dialog and stops retrying.</p>

        <p>Run the backend manually to see the error directly:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- backend`}</code></pre>
        </CodeFile>

        <h3>Wrong Python in PATH</h3>
        <p>Electron spawns Python directly. If your virtual environment is not activated,
        it may pick up the wrong Python without the required packages:</p>
        <CodeFile label="terminal">
          <pre><code>{`# Activate your venv before launching
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # macOS / Linux

npm run luna -- dev`}</code></pre>
        </CodeFile>

        <h3>Electron port conflict</h3>
        <p>Electron uses port 5173 for the Vite dev server renderer and 8899 for the backend.
        Both must be free. See the <a href="#port">Port 8899 conflict</a> section above.</p>
      </section>

      <section>
        <h2 id="spotify">Spotify auth issues</h2>

        <Callout type="warn" title="Symptom">
          <p>Spotify routes return <code>401</code> or the login flow redirects but shows
          <em>"INVALID_CLIENT: Invalid redirect URI"</em>.</p>
        </Callout>

        <h3>Redirect URI mismatch</h3>
        <p>In your Spotify Developer dashboard, the redirect URI must be set to exactly:</p>
        <CodeFile label="Spotify app settings">
          <pre><code>{`http://localhost:8899/api/spotify/callback`}</code></pre>
        </CodeFile>
        <p>No trailing slash. No <code>https</code>. It must match character-for-character.</p>

        <h3>Token expiry</h3>
        <p>The Spotify token is stored at <code>data/spotify_token.json</code>. If it has expired
        and the refresh fails, delete the file and re-authenticate:</p>
        <CodeFile label="terminal">
          <pre><code>{`# Delete the stale token
del data\spotify_token.json

# Re-authenticate by visiting
curl http://localhost:8899/api/spotify/login`}</code></pre>
        </CodeFile>

        <h3>Missing credentials</h3>
        <p>Ensure both <code>spotify_client_id</code> and <code>spotify_client_secret</code> are set
        in <code>.env</code>. See the <a href="/environment#spotify" style={{color:'#7c3aed'}}>Environment</a> page.</p>
      </section>

      <section>
        <h2 id="memory">Memory not persisting between sessions</h2>

        <Callout type="warn" title="Symptom">
          <p>Luna doesn't remember facts from previous conversations after a restart.</p>
        </Callout>

        <h3>1. Verify fact extraction is running</h3>
        <p>Facts are extracted by the <code>memory_maintenance</code> background process, which runs
        every 5 minutes. Check it's active:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl http://localhost:8899/api/system/processes | python -m json.tool`}</code></pre>
        </CodeFile>
        <p>Look for <code>"name": "memory_maintenance"</code> with <code>"status": "running"</code>.</p>

        <h3>2. Check that data/ is not being deleted</h3>
        <p><code>data/luna.db</code> is where facts live. If you're running <code>npm run luna -- clean</code>
        frequently, that command does not touch <code>data/</code> — but manual deletion would.
        Confirm the file exists:</p>
        <CodeFile label="terminal">
          <pre><code>{`# Windows
dir data\luna.db

# macOS / Linux
ls -lh data/luna.db`}</code></pre>
        </CodeFile>

        <h3>3. Cold start period</h3>
        <p>On first run there are no facts. The extractor needs a few conversations before memory
        becomes useful. After 3–5 sessions, context quality improves noticeably.</p>
      </section>

      <section>
        <h2 id="build">Build failures</h2>

        <h3>Frontend TypeScript errors</h3>
        <CodeFile label="terminal">
          <pre><code>{`cd frontend && npm run build`}</code></pre>
        </CodeFile>
        <p>Read each error carefully — they always include the file path and line number. Common causes:</p>
        <ul>
          <li>Missing type imports after adding a new component.</li>
          <li><code>any</code> type added to bypass a type error — find and fix the root type.</li>
          <li>A new API response shape that doesn't match <code>frontend/src/types/index.ts</code>.</li>
        </ul>

        <h3>Backend syntax errors</h3>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- check`}</code></pre>
        </CodeFile>
        <p>Runs <code>python -m py_compile</code> on critical backend files. Catches import errors and
        obvious syntax mistakes immediately.</p>

        <h3>npm install fails</h3>
        <CodeFile label="terminal">
          <pre><code>{`# Clear npm cache and reinstall
npm cache clean --force
npm install`}</code></pre>
        </CodeFile>

        <h3>pip install fails</h3>
        <p>Ensure you're inside an activated virtual environment and that you have the required Python
        version (3.10+):</p>
        <CodeFile label="terminal">
          <pre><code>{`python --version           # Must be 3.10 or newer
pip install --upgrade pip  # Update pip first
pip install -r backend/requirements.txt`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="Still stuck?">
          <p>Run <code>npm run luna -- doctor</code> first — it checks Node.js, npm, and Python
          versions and tells you exactly what's wrong with your environment.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/getting-started', label: 'Start here', title: 'Getting started',  desc: 'Installation steps and first run — if you haven\'t set up Luna yet.' },
        { href: '/environment',     label: 'Config',     title: 'Environment',       desc: 'All .env keys and what they do.' },
        { href: '/cli',             label: 'Platform',   title: 'CLI reference',     desc: 'Build, check, and diagnose the stack from the command line.' },
      ]} />
    </DocsLayout>
  );
}

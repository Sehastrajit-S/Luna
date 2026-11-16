import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'how',     label: 'How Luna is set up' },
  { id: 'server',  label: '1. Run the server' },
  { id: 'model',   label: '2. Choose a model' },
  { id: 'local',   label: '3. Use it locally' },
  { id: 'remote',  label: '4. Use it remotely' },
  { id: 'tokens',  label: 'Who needs a token' },
  { id: 'update',  label: '5. Updating' },
];

export default function Setup() {
  return (
    <DocsLayout
      title="Setup: Local & Remote"
      description="Run Luna's server once, then use it on that computer or from your phone and other computers over Tailscale."
      toc={toc}
    >
      <section>
        <h2 id="how">How Luna is set up</h2>
        <p>
          Luna is a <strong>server</strong>, which does the thinking and keeps your chats, memory and files, plus
          <strong> apps</strong> that talk to it: the desktop app, any browser, and the phone app. You set up the
          server once on the computer that will run it. Then you use it from that computer (<strong>Local</strong>)
          or from your other devices (<strong>Remote</strong>, over Tailscale).
        </p>
      </section>

      <section>
        <h2 id="server">1. Run the server</h2>
        <table>
          <thead><tr><th>Option</th><th>Good for</th><th>You need</th></tr></thead>
          <tbody>
            <tr><td><strong>A. Docker</strong></td><td>Any OS, nothing else to install, easy upgrades</td><td>Docker Desktop, or Docker Engine on Linux</td></tr>
            <tr><td><strong>B. Windows app</strong></td><td>A Windows PC you use every day, with voice and desktop controls</td><td>Windows 10/11, plus Python 3.10+ for the built-in server</td></tr>
            <tr><td><strong>C. From source</strong></td><td>Developing Luna, or Linux/macOS without Docker</td><td>Node.js 18+ and Python 3.10+</td></tr>
          </tbody>
        </table>

        <h3>A. Docker</h3>
        <CodeFile label="terminal">
          <pre><code>{`docker run -d --name luna --restart unless-stopped \\
  -p 127.0.0.1:8899:8899 -v luna_data:/app/data \\
  ghcr.io/sehastrajit-s/luna:latest`}</code></pre>
        </CodeFile>
        <p>
          Open <strong>http://localhost:8899</strong>. Everything Luna stores, including settings you save in the
          browser, lives in the <code>luna_data</code> volume, so upgrading never loses anything. For Ollama in
          Compose, a GPU, or a cloud-only setup, see <Link href="/docker">Docker</Link>.
        </p>

        <h3>B. Windows app</h3>
        <Steps>
          <Step num="1" title="Install the app">
            <p>Download <code>Luna-Setup-&lt;version&gt;.exe</code> from <Link href="/downloads">Downloads</Link> and run it.</p>
          </Step>
          <Step num="2" title="Give it Python">
            <p>The app starts its own server with the Python on your PC. Install Python 3.10+, then Luna's packages, once:</p>
            <CodeFile label="PowerShell">
              <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git
pip install -r Luna\\server\\requirements.txt`}</code></pre>
            </CodeFile>
            <p>No Python? Run the server with Docker instead. When a Luna server is already running on port 8899, the app uses it.</p>
          </Step>
        </Steps>

        <h3>C. From source</h3>
        <CodeFile label="terminal">
          <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna
npm install
npm run setup     # picks a model, installs Python and Node packages, writes .env
npm run web       # Luna at http://localhost:8899`}</code></pre>
        </CodeFile>
        <p>Desktop app from source: <code>npm --prefix interfaces/desktop start</code>.</p>
      </section>

      <section>
        <h2 id="model">2. Choose a model</h2>
        <p>Open <strong>Settings → AI model</strong> in Luna, or set it in <code>.env</code>.</p>
        <ul>
          <li>
            <strong>Ollama (local, free, private):</strong> install <a href="https://ollama.com">Ollama</a> and pull a
            model, e.g. <code>ollama pull qwen2.5:7b</code>. Docker Compose includes Ollama.
          </li>
          <li><strong>A cloud model:</strong> pick a provider and paste its API key: Anthropic, Google, Groq, Mistral, Cohere, NVIDIA NIM, or any OpenAI-compatible service such as OpenRouter.</li>
        </ul>
        <p>Optional extras in <strong>Settings → Integrations</strong>: GitHub, Spotify, and a SerpApi key for live <Link href="/store-prices">store prices</Link>.</p>
      </section>

      <section>
        <h2 id="local">3. Use it on this computer (Local)</h2>
        <ul>
          <li><strong>Browser:</strong> http://localhost:8899</li>
          <li><strong>Desktop app:</strong> starts on <strong>This computer</strong> by default (Settings → Server).</li>
        </ul>
        <p>Nothing needs a token on the same computer.</p>
      </section>

      <section>
        <h2 id="remote">4. Use it from your other devices (Remote, over Tailscale)</h2>
        <p>
          <a href="https://tailscale.com">Tailscale</a> is a free private network between your devices. Luna stays off
          the public internet; only devices signed in to your tailnet can reach it.
        </p>
        <Steps>
          <Step num="1" title="On the computer running Luna">
            <p>Install Tailscale and sign in. Then share Luna:</p>
            <table>
              <thead><tr><th>Server type</th><th>Command</th></tr></thead>
              <tbody>
                <tr><td>From source</td><td><code>npm run serve:tailscale</code> (starts Luna and shares it)</td></tr>
                <tr><td>Windows app or Docker</td><td><code>tailscale serve --bg --https=8899 http://127.0.0.1:8899</code></td></tr>
              </tbody>
            </table>
            <p>Luna is now at <code>https://&lt;this-computer&gt;.&lt;your-tailnet&gt;.ts.net:8899</code>.</p>
          </Step>
          <Step num="2" title="On your other devices">
            <p>Install Tailscale on each one and sign in with the <strong>same account</strong>.</p>
            <ul>
              <li><strong>Desktop app on another computer:</strong> Settings → Server → <strong>Remote over Tailscale</strong>. Luna lists the servers it finds; pick yours and <strong>Save and restart</strong>.</li>
              <li><strong>Any browser, including phones:</strong> open the <code>ts.net</code> address. On a phone, "Add to Home Screen" makes it open like an app.</li>
              <li><strong>Android app:</strong> Settings → Server: enter the same address.</li>
            </ul>
          </Step>
        </Steps>
        <figure className="doc-figure">
          <img src="/screenshots/desktop-server.png" alt="Desktop app settings listing Luna servers found on a Tailscale network" />
          <figcaption>Settings → Server finds Luna servers on your tailnet. Ones that trust your account connect with one click.</figcaption>
        </figure>
      </section>

      <section>
        <h2 id="tokens">Who needs a token</h2>
        <ul>
          <li><strong>Your own devices</strong> (same Tailscale account): no token, when Luna runs from source or the desktop app.</li>
          <li>
            <strong>Docker:</strong> Luna can't confirm the Tailscale account through the container, so each remote
            device uses the access token once: <code>docker exec luna cat /app/data/local_api_token</code>. Open
            <code>…ts.net:8899/#token=&lt;token&gt;</code> once in each browser, or paste it in the desktop app's Server settings.
          </li>
          <li><strong>Other people on your tailnet</strong> always need the token. It gives full access to your Luna, so treat it like a password.</li>
        </ul>
        <Callout type="tip" title="More detail">
          <p>How access is checked, Funnel, and security notes: <Link href="/remote">Remote access</Link>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="update">5. Updating</h2>
        <table>
          <thead><tr><th>Setup</th><th>Update</th></tr></thead>
          <tbody>
            <tr><td>Docker</td><td><code>docker pull ghcr.io/sehastrajit-s/luna:latest</code>, then recreate the container. Data stays in the volume.</td></tr>
            <tr><td>Windows app</td><td>Download the new installer, quit Luna (including the tray icon), and run it. Settings and chats are kept.</td></tr>
            <tr><td>From source</td><td><code>git pull</code>, <code>npm install</code>, <code>pip install -r server/requirements.txt</code>, then restart the server.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/remote', label: 'Details', title: 'Remote access', desc: 'Tailscale, tokens and security.' },
        { href: '/docker', label: 'Containers', title: 'Docker', desc: 'Image, Compose files, volumes and upgrades.' },
        { href: '/troubleshooting', label: 'Help', title: 'Troubleshooting', desc: 'When something doesn\'t start or connect.' },
      ]} />
    </DocsLayout>
  );
}

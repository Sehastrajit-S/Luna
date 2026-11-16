import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'run',      label: 'Run the image' },
  { id: 'compose',  label: 'Compose files' },
  { id: 'data',     label: 'Data and settings' },
  { id: 'models',   label: 'Models' },
  { id: 'upgrade',  label: 'Upgrading' },
  { id: 'build',    label: 'Build it yourself' },
];

export default function Docker() {
  return (
    <DocsLayout
      title="Docker"
      description="Run Luna's server and web UI from a prebuilt image on any OS."
      toc={toc}
    >
      <section>
        <h2 id="run">Run the image</h2>
        <CodeFile label="terminal">
          <pre><code>{`docker run -d --name luna --restart unless-stopped \\
  -p 127.0.0.1:8899:8899 -v luna_data:/app/data \\
  ghcr.io/sehastrajit-s/luna:latest`}</code></pre>
        </CodeFile>
        <p>
          Open <strong>http://localhost:8899</strong> and pick a model in Settings. Images are published for
          <code> linux/amd64</code> and <code>linux/arm64</code> with every release, tagged <code>:&lt;version&gt;</code> and <code>:latest</code>.
        </p>
        <Callout type="warn" title="Keep the port on 127.0.0.1">
          <p>
            Publishing it on all interfaces (<code>-p 8899:8899</code>) puts Luna on your whole network. To use it
            from other devices, share it privately over <Link href="/remote">Tailscale</Link> instead.
          </p>
        </Callout>
      </section>

      <section>
        <h2 id="compose">Compose files</h2>
        <p>From a clone of the repo:</p>
        <table>
          <thead><tr><th>Command</th><th>Runs</th></tr></thead>
          <tbody>
            <tr><td><code>docker compose -f deploy/compose.yml up -d</code></td><td>Luna + Ollama on CPU</td></tr>
            <tr><td><code>docker compose -f deploy/compose.yml -f deploy/compose.gpu.yml up -d</code></td><td>Luna + Ollama on an NVIDIA GPU (needs the NVIDIA container toolkit)</td></tr>
            <tr><td><code>docker compose -f deploy/compose.cloud.yml up -d</code></td><td>Luna only, for a cloud model</td></tr>
            <tr><td><code>docker compose -f deploy/compose.business.yml up -d</code></td><td>Business mode: logins, rate limits, team channels. Opens the port on purpose; put it behind HTTPS.</td></tr>
          </tbody>
        </table>
        <p>
          The Compose files use the published image and fall back to building from your checkout.
          <code> docker compose … up --build</code> always builds locally. A <code>.env</code> in the repo root is optional and read if present.
        </p>
      </section>

      <section>
        <h2 id="data">Data and settings</h2>
        <p>Everything Luna writes lives in <code>/app/data</code>, so mount a volume there:</p>
        <ul>
          <li>the database, memory, uploads, meetings and Library files;</li>
          <li>settings saved from the Settings page, in <code>/app/data/luna.env</code>;</li>
          <li>downloaded speech-to-text models, in <code>/app/data/models</code>;</li>
          <li>the access token for remote devices, in <code>/app/data/local_api_token</code>.</li>
        </ul>
        <p>The container runs as a non-root user, and nothing from your machine's <code>.env</code> is baked into the image.</p>
      </section>

      <section>
        <h2 id="models">Models</h2>
        <CodeFile label="pull a model into the Compose Ollama">
          <pre><code>{`docker compose -f deploy/compose.yml exec ollama ollama pull qwen2.5:7b`}</code></pre>
        </CodeFile>
        <p>Or choose a cloud provider in Settings → AI model and paste its key.</p>
      </section>

      <section>
        <h2 id="upgrade">Upgrading</h2>
        <CodeFile label="terminal">
          <pre><code>{`docker pull ghcr.io/sehastrajit-s/luna:latest
docker rm -f luna
docker run -d --name luna --restart unless-stopped -p 127.0.0.1:8899:8899 -v luna_data:/app/data ghcr.io/sehastrajit-s/luna:latest

# Compose:
docker compose -f deploy/compose.yml pull && docker compose -f deploy/compose.yml up -d`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="build">Build it yourself</h2>
        <CodeFile label="terminal">
          <pre><code>{`docker build -t luna .
docker run -d -p 127.0.0.1:8899:8899 -v luna_data:/app/data luna`}</code></pre>
        </CodeFile>
        <p>Every pull request builds the image and checks that it starts, answers its health check and serves the web UI.</p>
      </section>

      <NextSteps items={[
        { href: '/remote', label: 'Anywhere', title: 'Remote access', desc: 'Reach your container from other devices.' },
        { href: '/releasing', label: 'Maintainers', title: 'Releasing', desc: 'How images and installers are published.' },
      ]} />
    </DocsLayout>
  );
}

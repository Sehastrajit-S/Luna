import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const repoUrl = 'https://github.com/Sehastrajit-S/Luna';
const releasesUrl = `${repoUrl}/releases/latest`;

const toc = [
  { id: 'desktop', label: 'Desktop' },
  { id: 'mobile', label: 'Mobile' },
  { id: 'web', label: 'Web and Docker' },
  { id: 'developer', label: 'Developer tools' },
  { id: 'source', label: 'Source install' },
];

const platforms = [
  {
    name: 'Windows',
    status: 'Packaged',
    device: 'Windows 10/11 x64',
    download: 'Luna setup installer or portable zip',
    href: releasesUrl,
    notes: 'The full desktop app: local or remote server, push-to-talk voice, meeting mode, tray and desktop automation.',
  },
  {
    name: 'macOS',
    status: 'Source',
    device: 'Apple Silicon or Intel',
    download: 'Docker or run from source',
    href: '#web',
    notes: 'Run the server in Docker and use Luna in your browser, or run from source. A signed DMG is not published yet.',
  },
  {
    name: 'Linux',
    status: 'Source',
    device: 'Ubuntu/Debian/Fedora and similar',
    download: 'Docker image or source',
    href: '#web',
    notes: 'The container image runs on amd64 and arm64, including a Raspberry Pi or NAS.',
  },
  {
    name: 'Android',
    status: 'APK',
    device: 'Android phones and tablets',
    download: 'Android debug APK',
    href: releasesUrl,
    notes: 'Sideload the APK from the release, then point it at your server over Tailscale. Or just open Luna in the phone browser.',
  },
  {
    name: 'iPhone / iPad',
    status: 'Build required',
    device: 'iOS and iPadOS',
    download: 'iOS simulator build or signed local build',
    href: '#mobile',
    notes: 'The repo can produce an iOS simulator package. Real devices require Apple signing.',
  },
  {
    name: 'Browser',
    status: 'Supported',
    device: 'Desktop, tablet, phone, LAN devices',
    download: 'Open your Luna address',
    href: '#web',
    notes: 'Any browser works, with a phone layout on small screens. Reach your server from anywhere over Tailscale.',
  },
  {
    name: 'VS Code',
    status: 'Extension',
    device: 'VS Code on desktop',
    download: 'VSIX extension',
    href: `${repoUrl}/tree/main/interfaces/vscode`,
    notes: 'Connects to the Luna server on the same computer and shares its conversation context.',
  },
];

function DownloadCard({ item }) {
  return (
    <a className="download-card" href={item.href}>
      <div className="download-card-top">
        <h3>{item.name}</h3>
        <span>{item.status}</span>
      </div>
      <p className="download-device">{item.device}</p>
      <p>{item.notes}</p>
      <strong>{item.download}</strong>
    </a>
  );
}

export default function Downloads() {
  return (
    <DocsLayout
      title="Downloads"
      description="Install Luna on Windows, Android, any browser, Docker, and VS Code."
      toc={toc}
    >
      <section>
        <p>
          Every release publishes a Windows installer, an Android APK, an iOS simulator build and a
          container image. Not sure which you need? Start with <Link href="/setup">Setup</Link>.
        </p>
        <p>
          <a className="docs-inline-button" href={releasesUrl} target="_blank" rel="noopener noreferrer">
            Open Latest Release
          </a>
          <a className="docs-inline-button secondary" href={repoUrl} target="_blank" rel="noopener noreferrer">
            View Repository
          </a>
        </p>
      </section>

      <section>
        <h2 id="desktop">Desktop</h2>
        <div className="download-grid">
          {platforms.slice(0, 3).map((item) => <DownloadCard key={item.name} item={item} />)}
        </div>

        <Callout type="info" title="Full desktop features">
          <p>
            Push-to-talk, tray controls and OS automation need the desktop app. It starts a local server
            for you, or connects to one on another computer over Tailscale. The installer isn't code-signed
            yet, so Windows SmartScreen asks once: More info → Run anyway.
          </p>
        </Callout>
      </section>

      <section>
        <h2 id="mobile">Mobile</h2>
        <div className="download-grid">
          {platforms.slice(3, 5).map((item) => <DownloadCard key={item.name} item={item} />)}
        </div>

        <CodeFile label="build mobile locally">
          <pre><code>{`npm install
npm run build:mobile       # builds the web UI and syncs it into interfaces/mobile
# then open interfaces/mobile/android in Android Studio, or interfaces/mobile/ios in Xcode`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="web">Web and Docker</h2>
        <div className="download-grid">
          <DownloadCard item={platforms[5]} />
        </div>

        <CodeFile label="browser UI">
          <pre><code>{`npm run web
# Open http://localhost:8899`}</code></pre>
        </CodeFile>

        <CodeFile label="Docker">
          <pre><code>{`docker run -d --name luna --restart unless-stopped \\
  -p 127.0.0.1:8899:8899 -v luna_data:/app/data \\
  ghcr.io/sehastrajit-s/luna:latest
# Open http://localhost:8899`}</code></pre>
        </CodeFile>
        <p>Compose files for Ollama, GPU, cloud-only and business setups are on <Link href="/docker">Docker</Link>. To open Luna on your phone, see <Link href="/setup#remote">Remote over Tailscale</Link>.</p>
      </section>

      <section>
        <h2 id="developer">Developer tools</h2>
        <div className="download-grid">
          <DownloadCard item={platforms[6]} />
        </div>

        <CodeFile label="Luna CLI">
          <pre><code>{`npm i -g luna-workspace
luna setup`}</code></pre>
        </CodeFile>

        <CodeFile label="Shortest first run">
          <pre><code>{`npx luna-workspace setup`}</code></pre>
        </CodeFile>

        <p>If the npm package is not published yet, install directly from GitHub:</p>

        <CodeFile label="GitHub fallback">
          <pre><code>{`npm i -g github:Sehastrajit-S/Luna
luna setup`}</code></pre>
        </CodeFile>

        <CodeFile label="VS Code extension">
          <pre><code>{`cd interfaces/vscode
npm install
npm run compile
npx vsce package`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="source">Source install</h2>
        <p>
          Source install is the universal fallback for Windows, macOS, and Linux.
          It is also the best path if you want to develop Luna or build your own packages.
        </p>

        <CodeFile label="terminal">
          <pre><code>{`git clone https://github.com/Sehastrajit-S/Luna.git
cd Luna
npm install
npm run setup
npm run web       # http://localhost:8899`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/setup', label: 'Setup', title: 'Local & Remote', desc: 'Set up the server and connect your devices.' },
        { href: '/environment', label: 'Config', title: 'Environment', desc: 'Set models, providers, auth, and integrations.' },
        { href: '/troubleshooting', label: 'Help', title: 'Troubleshooting', desc: 'Fix install, backend, and model issues.' },
      ]} />
    </DocsLayout>
  );
}

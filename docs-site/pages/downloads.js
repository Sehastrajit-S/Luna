import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const repoUrl = 'https://github.com/Sehastrajit/Luna';
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
    notes: 'Best option for the full desktop app, local backend, voice, vision, and OS automation.',
  },
  {
    name: 'macOS',
    status: 'Source',
    device: 'Apple Silicon or Intel',
    download: 'Run from source',
    href: '#source',
    notes: 'Supported as a development/source install. A signed DMG is not published yet.',
  },
  {
    name: 'Linux',
    status: 'Source',
    device: 'Ubuntu/Debian/Fedora and similar',
    download: 'Run from source or Docker',
    href: '#source',
    notes: 'Use source mode for desktop features, or Docker for a browser-accessible deployment.',
  },
  {
    name: 'Android',
    status: 'APK',
    device: 'Android phones and tablets',
    download: 'Android debug APK',
    href: releasesUrl,
    notes: 'Use the APK when published in releases, or build locally from the Capacitor project.',
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
    download: 'Run Luna web or Docker',
    href: '#web',
    notes: 'Use the browser UI when a local or LAN backend is running.',
  },
  {
    name: 'VS Code',
    status: 'Extension',
    device: 'VS Code on desktop',
    download: 'VSIX extension',
    href: `${repoUrl}/tree/main/integrations/vscode`,
    notes: 'Connects to the same local Luna backend and shared conversation context.',
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
      description="Install Luna on desktop, mobile, browser, Docker, and developer tools."
      toc={toc}
    >
      <section>
        <p>
          Download packaged builds from the Luna GitHub releases page when available.
          Source installs are available for every platform that can run Node.js, Python,
          and the required native desktop dependencies.
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
            Voice, camera, screen perception, tray controls, and OS automation work best
            through the desktop app because Electron can launch and manage the local backend.
          </p>
        </Callout>
      </section>

      <section>
        <h2 id="mobile">Mobile</h2>
        <div className="download-grid">
          {platforms.slice(3, 5).map((item) => <DownloadCard key={item.name} item={item} />)}
        </div>

        <CodeFile label="build mobile locally">
          <pre><code>{`cd frontend
npm install
npm run build
npx cap sync android
npx cap sync ios`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="web">Web and Docker</h2>
        <div className="download-grid">
          <DownloadCard item={platforms[5]} />
        </div>

        <CodeFile label="browser UI">
          <pre><code>{`npm run web
# Open http://localhost:5173`}</code></pre>
        </CodeFile>

        <CodeFile label="Docker">
          <pre><code>{`cp .env.personal.example .env
docker compose up -d
# Open http://localhost:8899`}</code></pre>
        </CodeFile>
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
          <pre><code>{`npm i -g github:Sehastrajit/Luna
luna setup`}</code></pre>
        </CodeFile>

        <CodeFile label="VS Code extension">
          <pre><code>{`cd integrations/vscode
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
          <pre><code>{`git clone https://github.com/Sehastrajit/Luna.git
cd Luna
npm install
npm run luna -- setup
npm run luna -- dev`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/getting-started', label: 'Setup', title: 'Getting Started', desc: 'Configure the app after download.' },
        { href: '/environment', label: 'Config', title: 'Environment', desc: 'Set models, providers, auth, and integrations.' },
        { href: '/troubleshooting', label: 'Help', title: 'Troubleshooting', desc: 'Fix install, backend, and model issues.' },
      ]} />
    </DocsLayout>
  );
}

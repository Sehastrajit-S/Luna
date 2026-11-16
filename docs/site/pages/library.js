import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { NextSteps } from '../components/Docs';

const toc = [
  { id: 'tabs',   label: 'Two tabs' },
  { id: 'phone',  label: 'On a phone' },
  { id: 'api',    label: 'API' },
];

export default function Library() {
  return (
    <DocsLayout
      title="Library"
      description="Everything you've uploaded and everything Luna has made, in one place."
      toc={toc}
    >
      <section>
        <h2 id="tabs">Two tabs</h2>
        <ul>
          <li><strong>Uploads:</strong> files you attached in chat, with a preview where possible.</li>
          <li><strong>Created:</strong> files Luna wrote in its workspace: documents, code, reports, and <Link href="/meeting-mode">meeting</Link> recordings, transcripts and minutes.</li>
        </ul>
        <p>Open <strong>Library</strong> from the sidebar. Click a file to preview it, or download it.</p>
        <figure className="doc-figure">
          <img src="/screenshots/desktop-library.png" alt="The Library with Uploads and Created tabs" />
        </figure>
      </section>

      <section>
        <h2 id="phone">On a phone</h2>
        <p>
          In a phone browser, Luna switches to a mobile layout automatically: the sidebar becomes a menu, and the
          Library opens full screen with the same two tabs.
        </p>
        <div className="doc-figure-row" style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <figure className="doc-figure" style={{ flex: '1 1 200px', maxWidth: 280 }}>
            <img src="/screenshots/mobile-chat.png" alt="Luna chat on a phone" />
            <figcaption>Chat</figcaption>
          </figure>
          <figure className="doc-figure" style={{ flex: '1 1 200px', maxWidth: 280 }}>
            <img src="/screenshots/mobile-library.png" alt="Luna Library on a phone" />
            <figcaption>Library</figcaption>
          </figure>
        </div>
      </section>

      <section>
        <h2 id="api">API</h2>
        <table>
          <thead><tr><th>Method</th><th>Path</th><th>Does</th></tr></thead>
          <tbody>
            <tr><td><code>GET</code></td><td><code>/api/library/uploads</code></td><td>List uploaded files</td></tr>
            <tr><td><code>GET</code></td><td><code>/api/library/created</code></td><td>List files in the workspace</td></tr>
            <tr><td><code>GET</code></td><td><code>/api/library/created/raw?path=…</code></td><td>Download one workspace file</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/meeting-mode', label: 'Feature', title: 'Meeting mode', desc: 'Record meetings and get minutes.' },
        { href: '/setup#remote', label: 'Setup', title: 'Use it on your phone', desc: 'Reach Luna over Tailscale.' },
      ]} />
    </DocsLayout>
  );
}

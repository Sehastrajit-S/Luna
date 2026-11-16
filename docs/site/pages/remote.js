import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'share',    label: 'Share the server' },
  { id: 'connect',  label: 'Connect a device' },
  { id: 'access',   label: 'How access is checked' },
  { id: 'docker',   label: 'With Docker' },
  { id: 'settings', label: 'Settings' },
  { id: 'limits',   label: 'Limits' },
];

export default function Remote() {
  return (
    <DocsLayout
      title="Remote access (Tailscale)"
      description="Use your Luna from your phone, laptop or browser anywhere, over your private Tailscale network."
      toc={toc}
    >
      <section>
        <p>
          Step-by-step setup for each kind of install is on <Link href="/setup#remote">Setup</Link>. This page
          explains what happens and how access is protected.
        </p>
      </section>

      <section>
        <h2 id="share">Share the server</h2>
        <CodeFile label="from a source checkout">
          <pre><code>{`npm run serve:tailscale        # or: luna serve --tailscale
npm run serve:tailscale:off    # stop sharing`}</code></pre>
        </CodeFile>
        <p>
          This starts Luna and runs <code>tailscale serve</code>, so it's reachable at
          <code> https://&lt;this-computer&gt;.&lt;your-tailnet&gt;.ts.net:8899</code> by devices on your tailnet only.
          It prints the address and Luna's access token.
        </p>
        <ul>
          <li>Luna keeps listening on <code>127.0.0.1</code>, and Tailscale forwards to it. Leave <code>host=127.0.0.1</code>.</li>
          <li>It uses HTTPS port 8899, so other <code>tailscale serve</code> mappings (Ollama on 443, say) are left alone. Pick another with <code>--https=&lt;port&gt;</code>.</li>
          <li>In PowerShell use <code>npm run serve:tailscale</code>, not <code>npm run luna -- serve --tailscale</code>: PowerShell drops the <code>--</code> and npm swallows the flag.</li>
        </ul>
      </section>

      <section>
        <h2 id="connect">Connect a device</h2>
        <table>
          <thead><tr><th>Client</th><th>How</th></tr></thead>
          <tbody>
            <tr><td>Desktop app</td><td>Settings → Server → <strong>Remote over Tailscale</strong>. Luna searches your tailnet and lists every shared Luna as <strong>Trusted</strong> or <strong>Needs token</strong>. If exactly one trusted server turns up, it's selected for you. <strong>Save and restart</strong>.</td></tr>
            <tr><td>Browser</td><td>Open the <code>ts.net</code> address. Your own devices get in directly; others enter the token once.</td></tr>
            <tr><td>Mobile app</td><td>Settings → Server: the address, plus the token if needed.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="access">How access is checked</h2>
        <p>Apps on the server's own computer call <code>http://127.0.0.1:8899</code> and need nothing. Requests through <code>tailscale serve</code> are let in when either:</p>
        <ol>
          <li>
            <strong>Tailscale identity:</strong> Tailscale adds <code>Tailscale-User-Login</code> for the signed-in
            user, and strips any copy a client sends. Luna trusts the account this computer is signed in to, plus
            any listed in <code>tailscale_trusted_logins</code>. It only believes the header when the connection
            arrived on loopback, meaning it came from tailscaled on this machine, and it's never Funnel traffic.
          </li>
          <li><strong>Access token:</strong> sent in the <code>X-Luna-Token</code> header, or as <code>?luna_token=</code> for event streams. The token is in <code>data/local_api_token</code>.</li>
        </ol>
        <p>
          <code>/api/remote/hello</code> is public: it tells a client "this is Luna, and you are or aren't authorized".
          The desktop app uses it for discovery. Health checks, the web UI's files, signed webhooks and OAuth
          callbacks also stay open. Everything else under <code>/api</code> needs one of the two. See
          <code> server/core/access.py</code>.
        </p>
        <Callout type="warn" title="Treat the token like a password">
          <p>It gives full access to that Luna. To rotate it, delete <code>data/local_api_token</code>, restart the server, and reconnect your devices.</p>
        </Callout>
      </section>

      <section>
        <h2 id="docker">With Docker</h2>
        <CodeFile label="on the Docker host">
          <pre><code>{`tailscale serve --bg --https=8899 http://127.0.0.1:8899
docker exec luna cat /app/data/local_api_token`}</code></pre>
        </CodeFile>
        <p>
          Tailscale's proxy reaches the container from outside it, so Luna can't confirm the account and every
          remote device uses the token once. Keep the container's port on <code>127.0.0.1</code>, the default in
          the Compose files, so nothing on your network can reach Luna except through Tailscale.
        </p>
      </section>

      <section>
        <h2 id="settings">Settings</h2>
        <table>
          <thead><tr><th>Setting</th><th>Default</th><th>What it does</th></tr></thead>
          <tbody>
            <tr><td><code>tailscale_trust_owner</code></td><td><code>true</code></td><td>Let in this computer's Tailscale account without a token.</td></tr>
            <tr><td><code>tailscale_trusted_logins</code></td><td>empty</td><td>More tailnet logins to trust, comma-separated.</td></tr>
            <tr><td><code>require_token_on_lan</code></td><td><code>false</code></td><td>Also require the token for direct network connections when <code>host=0.0.0.0</code>.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="limits">Limits</h2>
        <ul>
          <li><strong>Google Workspace add-on:</strong> it runs on Google's servers, which can't reach a tailnet address.</li>
          <li><strong>VS Code and Office add-ins</strong> have no token field yet, so they work with a server on the same computer.</li>
        </ul>
      </section>

      <NextSteps items={[
        { href: '/setup', label: 'Setup', title: 'Setup: Local & Remote', desc: 'The full step-by-step guide.' },
        { href: '/docker', label: 'Containers', title: 'Docker', desc: 'Run the server in a container.' },
      ]} />
    </DocsLayout>
  );
}

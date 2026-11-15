import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'comparison',   label: 'Feature comparison' },
  { id: 'personal',     label: 'Personal variant' },
  { id: 'business',     label: 'Business variant' },
  { id: 'auth',         label: 'Authentication (JWT)' },
  { id: 'rate-limiting', label: 'Rate limiting' },
  { id: 'persona',      label: 'Persona configuration' },
  { id: 'switching',    label: 'Switching variants' },
];

export default function VariantsPage() {
  return (
    <DocsLayout
      title="Personal vs Business"
      description="Luna ships in two variants — Personal for single-user companion use and Business for team deployments with JWT auth, rate limiting, and professional persona."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Set <code>LUNA_VARIANT</code> in <code>.env</code> to choose the deployment
          mode. The variant affects authentication, proactive behaviour, away-state
          logic, persona tone, and rate limiting.
        </p>
        <CodeFile label=".env">
          <pre><code>{`LUNA_VARIANT=personal   # default — single-user companion
# or
LUNA_VARIANT=business   # team deployment with JWT and rate limiting`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="comparison">Feature comparison</h2>
        <table>
          <thead>
            <tr>
              <th>Feature</th>
              <th>Personal</th>
              <th>Business</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Authentication</td><td>None (localhost-only)</td><td>JWT bearer tokens, configurable expiry</td></tr>
            <tr><td>Multi-user</td><td>Single user</td><td>Multiple users, per-user memory</td></tr>
            <tr><td>Rate limiting</td><td>Disabled</td><td>Configurable per-minute + burst limits</td></tr>
            <tr><td>Away detection</td><td>Enabled (farewell phrases)</td><td>Disabled</td></tr>
            <tr><td>Proactive messages</td><td>Companion check-ins, state alerts</td><td>Task/event notifications only</td></tr>
            <tr><td>Tone</td><td>Warm, casual, companion</td><td>Professional, configurable</td></tr>
            <tr><td>Voice pipeline</td><td>Full (desktop wake-word)</td><td>Configurable / optional</td></tr>
            <tr><td>Personality RL</td><td>Full (per-user drift)</td><td>Bounded (professional floor)</td></tr>
            <tr><td>Spotify / desktop</td><td>Enabled</td><td>Disabled by default</td></tr>
            <tr><td>Persona name</td><td><code>LUNA_NAME</code></td><td><code>LUNA_NAME</code> + <code>BUSINESS_NAME</code></td></tr>
            <tr><td>Database</td><td>SQLite (default)</td><td>PostgreSQL recommended</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="personal">Personal variant</h2>
        <p>
          Designed for single-user, always-on companion use on a personal desktop or
          laptop. Prioritises warmth, proactivity, and natural conversation flow.
        </p>
        <CodeFile label=".env — personal">
          <pre><code>{`LUNA_VARIANT=personal

# Persona
LUNA_NAME=Luna
USER_NAME=Alex               # Luna uses this name when addressing the user

# No auth required — backend binds to localhost only
HOST=127.0.0.1
PORT=8899`}</code></pre>
        </CodeFile>
        <h3>Personal-only features</h3>
        <ul>
          <li><strong>Away detection</strong> — farewell phrases trigger the away screen.</li>
          <li><strong>Companion check-in</strong> — LLM-generated messages after 25–180 quiet minutes.</li>
          <li><strong>State-aware proactive</strong> — morning brief, late-night nudge, back-from-work greeting.</li>
          <li><strong>Commitment follow-up</strong> — remembers interviews/exams and asks how they went.</li>
          <li><strong>Spotify control</strong> — play, pause, queue via voice or chat.</li>
          <li><strong>Desktop automation</strong> — launch apps, take screenshots, control volume/brightness.</li>
        </ul>
      </section>

      <section>
        <h2 id="business">Business variant</h2>
        <p>
          Designed for team deployments — multiple users sharing a Luna instance, with
          JWT authentication and a professional persona anchored to the organisation.
        </p>
        <CodeFile label=".env — business">
          <pre><code>{`LUNA_VARIANT=business

# Required for multi-user auth
JWT_SECRET=your-long-random-secret-here
JWT_EXPIRY_HOURS=720          # 30 days

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=20

# Organisation persona
BUSINESS_NAME=Acme Corp
BUSINESS_DESCRIPTION=a SaaS company building developer tools
BUSINESS_TONE=professional    # professional | friendly | technical | concise
LUNA_NAME=Luna

# Production database recommended
DB_URL=postgresql+psycopg2://user:pass@db.example.com:5432/luna
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Bind to all interfaces (behind a reverse proxy)
HOST=0.0.0.0
PORT=8899`}</code></pre>
        </CodeFile>
        <h3>Business-only features</h3>
        <ul>
          <li><strong>JWT authentication</strong> — every API request must carry a valid bearer token.</li>
          <li><strong>Per-user memory isolation</strong> — facts, personality state, and conversation history are scoped to the authenticated user.</li>
          <li><strong>Rate limiting</strong> — per-user per-minute limits with burst allowance.</li>
          <li><strong>Professional tone floor</strong> — personality RL drift is bounded so Luna never becomes overly casual.</li>
          <li><strong>Organisation context</strong> — system prompt includes business name, description, and tone.</li>
        </ul>
      </section>

      <section>
        <h2 id="auth">Authentication (JWT)</h2>
        <p>
          In the business variant, the backend generates JWT tokens signed with
          <code>JWT_SECRET</code>. All protected endpoints require:
        </p>
        <CodeFile label="request header">
          <pre><code>{`Authorization: Bearer <token>`}</code></pre>
        </CodeFile>
        <h3>Generate a token</h3>
        <CodeFile label="terminal">
          <pre><code>{`curl -X POST http://localhost:8899/api/auth/token \\
  -H "Content-Type: application/json" \\
  -d '{"username": "alice", "password": "..."}'

# Response:
{ "access_token": "eyJ0eXA...", "token_type": "bearer" }`}</code></pre>
        </CodeFile>
        <h3>Token configuration</h3>
        <table>
          <thead><tr><th>Env var</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>JWT_SECRET</code></td><td>(empty)</td><td>HMAC secret for signing tokens. Set a long random string in production.</td></tr>
            <tr><td><code>JWT_EXPIRY_HOURS</code></td><td>720</td><td>Token lifetime in hours (default: 30 days).</td></tr>
          </tbody>
        </table>
        <Callout type="note">
          If <code>JWT_SECRET</code> is empty in business variant, the backend will
          refuse to start — authentication without a secret is insecure.
        </Callout>
      </section>

      <section>
        <h2 id="rate-limiting">Rate limiting</h2>
        <p>
          Rate limiting uses a sliding-window algorithm per authenticated user.
          Requests over the limit receive <code>429 Too Many Requests</code>.
        </p>
        <table>
          <thead><tr><th>Env var</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>RATE_LIMIT_ENABLED</code></td><td>false</td><td>Enable/disable rate limiting.</td></tr>
            <tr><td><code>RATE_LIMIT_PER_MINUTE</code></td><td>60</td><td>Max requests per user per minute.</td></tr>
            <tr><td><code>RATE_LIMIT_BURST</code></td><td>20</td><td>Additional burst allowance above the per-minute limit.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="persona">Persona configuration</h2>
        <p>Both variants support persona customisation:</p>
        <table>
          <thead><tr><th>Env var</th><th>Personal default</th><th>Business default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>LUNA_NAME</code></td><td>L.U.N.A.</td><td>L.U.N.A.</td><td>The name Luna introduces herself as.</td></tr>
            <tr><td><code>USER_NAME</code></td><td>friend</td><td>user</td><td>How Luna addresses the user (personal only).</td></tr>
            <tr><td><code>BUSINESS_NAME</code></td><td>—</td><td>(empty)</td><td>Organisation name injected into the system prompt.</td></tr>
            <tr><td><code>BUSINESS_DESCRIPTION</code></td><td>—</td><td>(empty)</td><td>One-sentence org description for context.</td></tr>
            <tr><td><code>BUSINESS_TONE</code></td><td>—</td><td>professional</td><td><code>professional</code> | <code>friendly</code> | <code>technical</code> | <code>concise</code></td></tr>
          </tbody>
        </table>
        <CodeFile label="business persona example">
          <pre><code>{`LUNA_NAME=Aria
BUSINESS_NAME=Meridian Labs
BUSINESS_DESCRIPTION=a biotech company developing AI-assisted diagnostics
BUSINESS_TONE=technical`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="switching">Switching variants</h2>
        <ol>
          <li>
            Change <code>LUNA_VARIANT</code> in <code>.env</code>.
          </li>
          <li>
            If switching from personal → business, set <code>JWT_SECRET</code>
            and optionally add <code>.env.business</code> for variant-specific overrides.
          </li>
          <li>
            Restart the backend: <code>python -m backend.main</code>.
          </li>
          <li>
            Run <code>alembic upgrade head</code> if switching to a new database.
          </li>
        </ol>
        <Callout type="tip">
          Variant-specific env files (<code>.env.personal</code>, <code>.env.business</code>)
          are loaded on top of <code>.env</code> when the matching variant is active.
          Put variant-specific overrides there to avoid cluttering the base <code>.env</code>.
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/database',     label: 'Guide',     title: 'Database Integrations', desc: 'PostgreSQL is recommended for business deployments.' },
        { href: '/sdk-overview', label: 'Guide',     title: 'SDK Overview', desc: 'Integration modes — HTTP API and direct Python import.' },
        { href: '/mcp',          label: 'Reference', title: 'MCP Servers', desc: 'MCP works with both variants.' },
      ]} />
    </DocsLayout>
  );
}

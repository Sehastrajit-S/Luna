import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'variant',      label: 'Variant' },
  { id: 'llm',          label: 'LLM providers' },
  { id: 'embeddings',   label: 'Embeddings' },
  { id: 'auth',         label: 'Auth & rate limiting' },
  { id: 'channels',     label: 'Messaging channels' },
  { id: 'github',       label: 'GitHub' },
  { id: 'lan',          label: 'LAN / network' },
  { id: 'spotify',      label: 'Spotify' },
  { id: 'data',         label: 'Data services' },
  { id: 'reference',    label: 'Full reference' },
];

export default function Environment() {
  return (
    <DocsLayout
      title="Environment"
      description="Every .env key explained — variants, 8 LLM providers, messaging channels, auth, rate limiting, and live data services."
      toc={toc}
    >
      <section>
        <p>
          Create your local environment file from one of the variant templates, then edit as needed.
          The file is gitignored — never commit it.
        </p>
        <CodeFile label="terminal">
          <pre><code>{`# Personal variant
cp .env.personal.example .env

# Business variant
cp .env.business.example .env`}</code></pre>
        </CodeFile>
        <Callout type="warn" title="Never commit .env">
          <p><code>.env</code> may contain API keys, your name, and local paths. It is gitignored by default.</p>
        </Callout>
      </section>

      {/* ── Variant ── */}
      <section>
        <h2 id="variant">Variant</h2>
        <CodeFile label=".env">
          <pre><code>{`luna_variant=personal   # personal | business`}</code></pre>
        </CodeFile>

        <table>
          <thead><tr><th>Value</th><th>Behaviour</th></tr></thead>
          <tbody>
            <tr>
              <td><code>personal</code></td>
              <td>Casual companion. Voice, vision, Spotify, desktop automation. Single user. No auth required by default.</td>
            </tr>
            <tr>
              <td><code>business</code></td>
              <td>Professional team assistant. Multi-user JWT. Rate limiting. No personal features. Channels emphasised.</td>
            </tr>
          </tbody>
        </table>

        <p>Business-specific identity keys:</p>
        <CodeFile label=".env">
          <pre><code>{`business_name=Acme Corp
business_description=a SaaS company building developer tools
# professional | friendly | technical | concise
business_tone=professional`}</code></pre>
        </CodeFile>
      </section>

      {/* ── LLM ── */}
      <section>
        <h2 id="llm">LLM providers</h2>
        <p>
          Set <code>llm_provider</code> to one of the eight supported values, then fill in the
          matching key block. All providers stream tokens via the same interface — no other code changes needed.
        </p>

        <h3>Ollama (local, default)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b`}</code></pre>
        </CodeFile>
        <p>Any model in <code>ollama list</code> can be used. Tested with <code>qwen2.5:7b</code>,
        <code>qwen2.5:14b</code>, and <code>llama3.2:3b</code> on low-end hardware.</p>

        <h3>OpenAI / OpenAI-compatible</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://api.openai.com/v1
openai_api_key=sk-...
openai_model=gpt-4o-mini`}</code></pre>
        </CodeFile>
        <p>Works with any OpenAI-compatible endpoint: LM Studio, Jan.ai, llama.cpp server, vLLM, Together AI, and
        OpenRouter (which gives you access to every major model through one key).</p>

        <h3>NVIDIA NIM</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=nvidia-nim
nvidia_nim_base_url=https://integrate.api.nvidia.com/v1
nvidia_nim_api_key=nvapi-...
nvidia_nim_model=meta/llama-3.1-8b-instruct`}</code></pre>
        </CodeFile>
        <p>Uses NVIDIA NIM's OpenAI-compatible chat completions endpoint. Point the base URL at NVIDIA API Catalog or a self-hosted NIM.</p>

        <h3>Anthropic Claude (native)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=anthropic
anthropic_api_key=sk-ant-...
anthropic_model=claude-sonnet-4-5`}</code></pre>
        </CodeFile>
        <p>Uses the Anthropic Messages API directly — no proxy needed. Recommended for the business variant.</p>

        <h3>Google Gemini (native)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=google
google_api_key=AIza...
google_model=gemini-2.0-flash`}</code></pre>
        </CodeFile>
        <p>Uses the Gemini REST API. Flash is fast and cheap; Pro gives longer context and stronger reasoning.</p>

        <h3>Groq (native — fastest cloud)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=groq
groq_api_key=gsk_...
groq_model=llama-3.3-70b-versatile`}</code></pre>
        </CodeFile>
        <p>Groq runs inference on custom LPU chips at ~300 tokens/second. Free tier available.
        Best speed/quality ratio for cloud inference.</p>

        <h3>Cohere Command R (native)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=cohere
cohere_api_key=...
cohere_model=command-r-plus`}</code></pre>
        </CodeFile>

        <h3>Mistral AI (native)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=mistral
mistral_api_key=...
mistral_model=mistral-large-latest`}</code></pre>
        </CodeFile>
        <p>European-hosted. GDPR-compliant. Strong coding and reasoning performance.</p>

        <Callout type="info" title="OpenRouter — one key, every model">
          <p>Use <code>openai-compatible</code> with OpenRouter to access Claude, Gemini, GPT-4o,
          Mistral, Llama, and more through a single key and pay-per-token billing:</p>
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://openrouter.ai/api/v1
openai_api_key=sk-or-...
openai_model=anthropic/claude-opus-4`}</code></pre>
        </Callout>
      </section>

      {/* ── Embeddings ── */}
      <section>
        <h2 id="embeddings">Embeddings</h2>
        <p>Embeddings power memory search — finding semantically similar facts when building context.</p>
        <CodeFile label=".env">
          <pre><code>{`# Ollama (default — pull nomic-embed-text once)
embedding_provider=ollama
ollama_embed_model=nomic-embed-text

# OpenAI-compatible (uses same base_url and api_key as LLM)
embedding_provider=openai-compatible
openai_embed_model=text-embedding-3-small`}</code></pre>
        </CodeFile>
      </section>

      {/* ── Auth ── */}
      <section>
        <h2 id="auth">Auth &amp; rate limiting</h2>

        <h3>JWT (business / multi-user)</h3>
        <p>Set <code>jwt_secret</code> to enable per-user JWT tokens via the admin API.
        Admin requests must include <code>Authorization: Bearer &lt;jwt_secret&gt;</code>.</p>
        <CodeFile label=".env">
          <pre><code>{`# Generate: openssl rand -hex 32
jwt_secret=your-64-char-hex-string
jwt_expiry_hours=720`}</code></pre>
        </CodeFile>
        <CodeFile label="terminal">
          <pre><code>{`# Create a user and get a JWT
curl -X POST http://localhost:8899/api/admin/users \\
  -H "Authorization: Bearer YOUR_JWT_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{"username": "alice", "role": "user"}'

# → { "user_id": "...", "token": "eyJ..." }`}</code></pre>
        </CodeFile>

        <h3>Rate limiting</h3>
        <CodeFile label=".env">
          <pre><code>{`rate_limit_enabled=true
rate_limit_per_minute=60   # requests per user per window
rate_limit_burst=20        # extra burst allowance`}</code></pre>
        </CodeFile>
        <p>The sliding-window rate limiter runs in-memory (no Redis required). The business Docker
        compose file enables rate limiting automatically.</p>

        <Callout type="info" title="Admin API endpoints">
          <pre><code>{`GET    /api/admin/info                  System info + provider status
GET    /api/admin/users                 List users
POST   /api/admin/users                 Create user (returns JWT)
DELETE /api/admin/users/{id}            Revoke user
POST   /api/admin/users/{id}/rotate-token  Rotate JWT
GET    /api/admin/llm/providers         All configured providers`}</code></pre>
        </Callout>
      </section>

      {/* ── Channels ── */}
      <section>
        <h2 id="channels">Messaging channels</h2>
        <p>
          Luna can receive messages via Telegram, Discord, Slack, and a generic HTTP webhook.
          GitHub event notifications are covered in the <a href="#github" style={{color:'#7c3aed'}}>GitHub</a> section below.
          Each channel maintains isolated per-user conversation history.
          Desktop features (voice, Spotify, maps) are automatically stripped from channel replies.
        </p>

        <h3>Telegram</h3>
        <CodeFile label=".env">
          <pre><code>{`telegram_bot_token=123456:ABC-...`}</code></pre>
        </CodeFile>
        <p>Register the webhook after Luna is running at a public URL:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://YOUR_HOST/api/channels/telegram"`}</code></pre>
        </CodeFile>

        <h3>Discord</h3>
        <CodeFile label=".env">
          <pre><code>{`discord_bot_token=MTI...
discord_public_key=abc123...  # from Discord Developer Portal`}</code></pre>
        </CodeFile>
        <p>In the Discord Developer Portal, set the Interactions Endpoint URL to
        <code>https://YOUR_HOST/api/channels/discord</code>. Luna handles the Ed25519 ping verification automatically.</p>

        <h3>Slack</h3>
        <CodeFile label=".env">
          <pre><code>{`slack_bot_token=xoxb-...
slack_signing_secret=abc...`}</code></pre>
        </CodeFile>
        <p>In your Slack App config, set the Events API Request URL to
        <code>https://YOUR_HOST/api/channels/slack</code> and subscribe to
        <code>message.channels</code> and <code>app_mention</code>.</p>

        <h3>Generic webhook</h3>
        <p>Any system can post to Luna over HTTP:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl -X POST http://localhost:8899/api/channels/webhook \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "u1", "user_name": "Bob", "text": "summarise this week"}'

# → { "reply": "Here is this week's summary..." }`}</code></pre>
        </CodeFile>

        <CodeFile label=".env (status check)">
          <pre><code>{`# GET /api/channels/status returns which channels are configured
# { "telegram": true, "discord": false, "slack": true, "webhook": true }`}</code></pre>
        </CodeFile>
      </section>

      {/* ── GitHub ── */}
      <section>
        <h2 id="github">GitHub</h2>
        <p>
          Set <code>github_token</code> to enable GitHub tools in chat (list issues, create issues,
          comment on PRs). Set <code>github_webhook_secret</code> to receive push, PR, and issue
          events via the <code>/api/channels/github</code> endpoint.
        </p>
        <CodeFile label=".env">
          <pre><code>{`# Personal Access Token — needs repo, issues, pull_requests read/write
github_token=ghp_...

# Webhook — must match the secret set in GitHub repo/org settings
github_webhook_secret=strong-random-secret

# Default repo for tool calls (owner/repo format)
github_default_repo=myorg/myrepo

# Forward GitHub event summaries to a notification channel (optional)
github_notify_slack_channel=C0123ABCDEF    # Slack channel ID
github_notify_telegram_chat_id=123456789   # Telegram chat ID`}</code></pre>
        </CodeFile>
        <p>Register the webhook in GitHub under <strong>Settings → Webhooks → Add webhook</strong>:</p>
        <CodeFile label="GitHub webhook settings">
          <pre><code>{`Payload URL:   https://YOUR_HOST/api/channels/github
Content type:  application/json
Secret:        <same as github_webhook_secret>
Events:        push, pull_request, issues, issue_comment, release`}</code></pre>
        </CodeFile>
        <Callout type="tip" title="Token scopes">
          <p>A fine-grained PAT with <strong>Contents</strong> (read), <strong>Issues</strong> (read/write),
          and <strong>Pull requests</strong> (read) is sufficient. Classic tokens need the <code>repo</code> scope.</p>
        </Callout>
      </section>

      {/* ── LAN ── */}
      <section>
        <h2 id="lan">LAN / network mode</h2>
        <CodeFile label=".env">
          <pre><code>{`host=0.0.0.0`}</code></pre>
        </CodeFile>
        <p>Open <code>http://YOUR_LAN_IP:8899</code> on any device on your network.
        For the business variant, set <code>jwt_secret</code> to protect the admin API.</p>
      </section>

      {/* ── Spotify ── */}
      <section>
        <h2 id="spotify">Spotify (personal variant only)</h2>
        <p>Create a Spotify Developer app at <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed' }}>developer.spotify.com</a> and
        add <code>http://localhost:8899/api/spotify/callback</code> as a redirect URI.</p>
        <CodeFile label=".env">
          <pre><code>{`spotify_client_id=your_client_id
spotify_client_secret=your_client_secret`}</code></pre>
        </CodeFile>
      </section>

      {/* ── Data ── */}
      <section>
        <h2 id="data">Data services</h2>
        <table>
          <thead><tr><th>Key</th><th>Service</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td><code>the_news_api</code></td><td>TheNewsAPI</td><td>Live news headlines. Dashboard widget. Free tier available.</td></tr>
            <tr><td><code>alpha_vantage</code></td><td>Alpha Vantage</td><td>Extended market data. Falls back to Yahoo Finance without this.</td></tr>
            <tr><td><code>weather_lat/lon</code></td><td>Open-Meteo</td><td>Free, no key. Set your coordinates for accurate weather.</td></tr>
            <tr><td><code>weather_city</code></td><td>—</td><td>Display name for the weather widget.</td></tr>
            <tr><td><code>weather_timezone</code></td><td>—</td><td>IANA timezone string, e.g. <code>America/New_York</code>.</td></tr>
          </tbody>
        </table>
      </section>

      {/* ── Reference ── */}
      <section>
        <h2 id="reference">Full reference</h2>
        <table>
          <thead><tr><th>Key</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>luna_variant</code></td><td><code>personal</code></td><td><code>personal</code> or <code>business</code>.</td></tr>
            <tr><td><code>business_name</code></td><td>—</td><td>Company name injected into business system prompt.</td></tr>
            <tr><td><code>business_description</code></td><td>—</td><td>One-line description of the organisation.</td></tr>
            <tr><td><code>business_tone</code></td><td><code>professional</code></td><td><code>professional</code> | <code>friendly</code> | <code>technical</code> | <code>concise</code>.</td></tr>
            <tr><td><code>llm_provider</code></td><td><code>ollama</code></td><td><code>ollama</code> | <code>openai-compatible</code> | <code>nvidia-nim</code> | <code>anthropic</code> | <code>google</code> | <code>groq</code> | <code>cohere</code> | <code>mistral</code>.</td></tr>
            <tr><td><code>ollama_base_url</code></td><td><code>http://localhost:11434</code></td><td>Ollama server URL.</td></tr>
            <tr><td><code>ollama_model</code></td><td><code>qwen2.5:7b</code></td><td>Ollama chat model.</td></tr>
            <tr><td><code>ollama_embed_model</code></td><td><code>nomic-embed-text</code></td><td>Ollama embedding model.</td></tr>
            <tr><td><code>openai_base_url</code></td><td><code>https://api.openai.com/v1</code></td><td>OpenAI-compatible base URL.</td></tr>
            <tr><td><code>openai_api_key</code></td><td>—</td><td>API key for OpenAI-compatible provider.</td></tr>
            <tr><td><code>openai_model</code></td><td><code>gpt-4o-mini</code></td><td>Model name.</td></tr>
            <tr><td><code>nvidia_nim_base_url</code></td><td><code>https://integrate.api.nvidia.com/v1</code></td><td>NVIDIA NIM OpenAI-compatible base URL.</td></tr>
            <tr><td><code>nvidia_nim_api_key</code></td><td>—</td><td>NVIDIA API key.</td></tr>
            <tr><td><code>nvidia_nim_model</code></td><td><code>meta/llama-3.1-8b-instruct</code></td><td>NVIDIA NIM model ID.</td></tr>
            <tr><td><code>anthropic_api_key</code></td><td>—</td><td>Anthropic API key.</td></tr>
            <tr><td><code>anthropic_model</code></td><td><code>claude-sonnet-4-5</code></td><td>Anthropic model ID.</td></tr>
            <tr><td><code>google_api_key</code></td><td>—</td><td>Google AI Studio API key.</td></tr>
            <tr><td><code>google_model</code></td><td><code>gemini-2.0-flash</code></td><td>Gemini model ID.</td></tr>
            <tr><td><code>groq_api_key</code></td><td>—</td><td>Groq API key.</td></tr>
            <tr><td><code>groq_model</code></td><td><code>llama-3.3-70b-versatile</code></td><td>Groq model ID.</td></tr>
            <tr><td><code>cohere_api_key</code></td><td>—</td><td>Cohere API key.</td></tr>
            <tr><td><code>cohere_model</code></td><td><code>command-r-plus</code></td><td>Cohere model ID.</td></tr>
            <tr><td><code>mistral_api_key</code></td><td>—</td><td>Mistral AI API key.</td></tr>
            <tr><td><code>mistral_model</code></td><td><code>mistral-large-latest</code></td><td>Mistral model ID.</td></tr>
            <tr><td><code>embedding_provider</code></td><td><code>ollama</code></td><td><code>ollama</code> or <code>openai-compatible</code>.</td></tr>
            <tr><td><code>jwt_secret</code></td><td>—</td><td>Signs per-user JWT tokens. Admin API uses <code>Authorization: Bearer &lt;jwt_secret&gt;</code>.</td></tr>
            <tr><td><code>jwt_expiry_hours</code></td><td><code>720</code></td><td>JWT lifetime in hours (30 days default).</td></tr>
            <tr><td><code>rate_limit_enabled</code></td><td><code>false</code></td><td>Enable sliding-window rate limiting.</td></tr>
            <tr><td><code>rate_limit_per_minute</code></td><td><code>60</code></td><td>Max requests per user per 60-second window.</td></tr>
            <tr><td><code>rate_limit_burst</code></td><td><code>20</code></td><td>Extra burst allowance on top of the per-minute limit.</td></tr>
            <tr><td><code>telegram_bot_token</code></td><td>—</td><td>Telegram Bot API token from @BotFather.</td></tr>
            <tr><td><code>discord_bot_token</code></td><td>—</td><td>Discord bot token.</td></tr>
            <tr><td><code>discord_public_key</code></td><td>—</td><td>Discord app public key for interaction signature verification.</td></tr>
            <tr><td><code>slack_bot_token</code></td><td>—</td><td>Slack bot OAuth token (<code>xoxb-...</code>).</td></tr>
            <tr><td><code>slack_signing_secret</code></td><td>—</td><td>Slack app signing secret for request verification.</td></tr>
            <tr><td><code>github_token</code></td><td>—</td><td>GitHub Personal Access Token for API tools (list/create issues, PRs).</td></tr>
            <tr><td><code>github_webhook_secret</code></td><td>—</td><td>HMAC secret for verifying GitHub webhook payloads.</td></tr>
            <tr><td><code>github_default_repo</code></td><td>—</td><td>Default <code>owner/repo</code> for tool calls when no repo is specified.</td></tr>
            <tr><td><code>github_notify_slack_channel</code></td><td>—</td><td>Slack channel ID to forward GitHub event summaries to.</td></tr>
            <tr><td><code>github_notify_telegram_chat_id</code></td><td>—</td><td>Telegram chat ID to forward GitHub event summaries to.</td></tr>
            <tr><td><code>host</code></td><td><code>127.0.0.1</code></td><td>Backend bind address. <code>0.0.0.0</code> for LAN/Docker.</td></tr>
            <tr><td><code>port</code></td><td><code>8899</code></td><td>Backend HTTP port.</td></tr>
            <tr><td><code>user_name</code></td><td><code>friend</code></td><td>Your name — used in the personal variant system prompt.</td></tr>
            <tr><td><code>luna_name</code></td><td><code>L.U.N.A.</code></td><td>Assistant display name.</td></tr>
            <tr><td><code>spotify_client_id</code></td><td>—</td><td>Spotify Developer app client ID.</td></tr>
            <tr><td><code>spotify_client_secret</code></td><td>—</td><td>Spotify Developer app client secret.</td></tr>
            <tr><td><code>the_news_api</code></td><td>—</td><td>TheNewsAPI key for live news widget.</td></tr>
            <tr><td><code>alpha_vantage</code></td><td>—</td><td>Alpha Vantage key for extended market data.</td></tr>
            <tr><td><code>weather_lat</code></td><td><code>40.7128</code></td><td>Latitude for Open-Meteo weather.</td></tr>
            <tr><td><code>weather_lon</code></td><td><code>-74.0060</code></td><td>Longitude for Open-Meteo weather.</td></tr>
            <tr><td><code>weather_city</code></td><td><code>New York</code></td><td>Display name for the weather widget.</td></tr>
            <tr><td><code>weather_timezone</code></td><td><code>America/New_York</code></td><td>IANA timezone string.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/integrations', label: 'Integrate', title: 'Integrations',  desc: 'All supported providers, messaging channels, and platforms in one place.' },
        { href: '/voice',        label: 'Feature',   title: 'Voice setup',   desc: 'Voice-specific config: STT model, TTS voice, wake word.' },
        { href: '/troubleshooting', label: 'Support', title: 'Troubleshooting', desc: 'Common setup and connection issues with fixes.' },
      ]} />
    </DocsLayout>
  );
}

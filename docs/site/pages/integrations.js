import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'variants',  label: 'Variants' },
  { id: 'llm',       label: 'LLM providers' },
  { id: 'channels',  label: 'Messaging channels' },
  { id: 'github',    label: 'GitHub' },
  { id: 'voice',     label: 'Voice engines' },
  { id: 'apps',      label: 'Desktop apps' },
  { id: 'data',      label: 'Live data & APIs' },
  { id: 'health',    label: 'Health platforms' },
  { id: 'production',label: 'Production' },
  { id: 'platforms', label: 'Platforms' },
];

const Badge = ({ label, color = 'purple' }) => (
  <span className={`int-badge int-badge-${color}`}>{label}</span>
);

const Card = ({ icon, title, subtitle, badges = [], note }) => (
  <div className="int-card">
    <div className="int-icon">{icon}</div>
    <div className="int-card-body">
      <div className="int-card-head">
        <span className="int-title">{title}</span>
        {badges.map(b => <Badge key={b.label} label={b.label} color={b.color} />)}
      </div>
      {subtitle && <p className="int-subtitle">{subtitle}</p>}
      {note    && <p className="int-note">{note}</p>}
    </div>
  </div>
);

const Grid = ({ children }) => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
    {children}
  </div>
);

const PlatformCard = ({ icon, name, status, detail }) => (
  <div className="int-platform-card">
    <div className="int-platform-icon">{icon}</div>
    <div className="int-platform-name">{name}</div>
    <div className="int-platform-status"><Badge label={status} color={status === 'Full support' ? 'green' : status === 'Partial' ? 'blue' : 'gray'} /></div>
    <div className="int-detail">{detail}</div>
  </div>
);

export default function Integrations() {
  return (
    <DocsLayout
      title="Integrations"
      description="Every variant, LLM provider, messaging channel, voice engine, desktop app, data service, and platform that Luna works with."
      toc={toc}
    >

      <p>
        Luna is built to plug into what you already use. Every integration is configured in{' '}
        <code>.env</code> — no code changes needed. Local integrations require no API key;
        cloud ones are always opt-in.
      </p>

      {/* ── Variants ── */}
      <section>
        <h2 id="variants">Variants</h2>
        <p>
          Luna ships as two distinct deployment modes. Set <code>luna_variant</code> in{' '}
          <code>.env</code> to switch; no data is lost.
        </p>

        <Card
          icon="🏠"
          title="Personal"
          subtitle="Local-first AI companion for daily individual use. Casual conversational tone. Voice, vision, Spotify, maps, app launcher, and desktop automation all enabled. No authentication required."
          badges={[{ label: 'Default', color: 'purple' }, { label: 'Single user', color: 'green' }]}
          note="luna_variant=personal  ·  Start with: luna dev"
        />
        <Card
          icon="🏢"
          title="Business"
          subtitle="Professional team assistant. Multi-user JWT authentication, sliding-window rate limiting, Slack/Telegram/Discord messaging channels. No Spotify, no desktop launchers — focused on productivity and Q&A."
          badges={[{ label: 'Multi-user', color: 'blue' }, { label: 'Production-ready', color: 'purple' }]}
          note="luna_variant=business  ·  Start with: luna docker:business"
        />

        <Callout type="info" title="Switching variants">
          <p>Change the <code>luna_variant</code> key in <code>.env</code> and restart. Personal and
          Business mode share the same codebase — the variant controls which features are exposed,
          which system prompt is used, and whether auth is enforced.</p>
        </Callout>
      </section>

      {/* ── LLM Providers ── */}
      <section>
        <h2 id="llm">LLM Providers</h2>
        <p>
          Luna supports 8 providers natively. Switch by changing <code>llm_provider</code> in{' '}
          <code>.env</code> — no code changes, no restart of anything else.
        </p>

        <h3>Local inference</h3>

        <Card
          icon="🦙"
          title="Ollama"
          subtitle="Runs models locally on your machine. The default provider. No API key, no internet required. Supports GPU acceleration via CUDA or Metal."
          badges={[{ label: 'Local', color: 'green' }, { label: 'Default', color: 'purple' }]}
          note="llm_provider=ollama  ·  ollama_base_url=http://localhost:11434  ·  ollama_model=qwen2.5:7b"
        />
        <Card
          icon="🔬"
          title="LM Studio"
          subtitle="Local model server with a GUI. Exposes an OpenAI-compatible endpoint. Good for trying new GGUF models without configuring Ollama."
          badges={[{ label: 'Local', color: 'green' }]}
          note="llm_provider=openai-compatible  ·  openai_base_url=http://localhost:1234/v1"
        />
        <Card
          icon="🦾"
          title="llama.cpp server"
          subtitle="Minimal OpenAI-compatible server. Maximum control over quantization and hardware utilisation."
          badges={[{ label: 'Local', color: 'green' }]}
          note="llm_provider=openai-compatible  ·  openai_base_url=http://localhost:8080/v1"
        />
        <Card
          icon="🏠"
          title="Jan.ai"
          subtitle="Open-source local model manager with a desktop GUI. Exposes an OpenAI-compatible API on localhost."
          badges={[{ label: 'Local', color: 'green' }]}
          note="llm_provider=openai-compatible  ·  openai_base_url=http://localhost:1337/v1"
        />

        <h3>Cloud inference</h3>

        <Card
          icon="🧠"
          title="Anthropic Claude"
          subtitle="Native Anthropic Messages API. Claude Sonnet and Opus models. Recommended for the Business variant — strong instruction following, long context, and function calling."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Business rec.', color: 'purple' }]}
          note="llm_provider=anthropic  ·  anthropic_api_key=sk-ant-…  ·  anthropic_model=claude-sonnet-4-5"
        />
        <Card
          icon="✨"
          title="Google Gemini"
          subtitle="Native Google AI REST API. Gemini 2.0 Flash by default. Exceptional long-context performance (1M tokens) and multimodal support."
          badges={[{ label: 'Cloud', color: 'blue' }]}
          note="llm_provider=google  ·  google_api_key=AIza…  ·  google_model=gemini-2.0-flash"
        />
        <Card
          icon="⚡"
          title="Groq"
          subtitle="Purpose-built LPU inference — LLaMA 3.3 70B at ~300 tok/s. Free tier available. Best for low-latency chat where speed matters more than context length."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Fast', color: 'purple' }]}
          note="llm_provider=groq  ·  groq_api_key=gsk_…  ·  groq_model=llama-3.3-70b-versatile"
        />
        <Card
          icon="🪸"
          title="Cohere"
          subtitle="Command R+ with native RAG tooling. European data residency option. Strong at retrieval-augmented tasks and long structured outputs."
          badges={[{ label: 'Cloud', color: 'blue' }]}
          note="llm_provider=cohere  ·  cohere_api_key=…  ·  cohere_model=command-r-plus"
        />
        <Card
          icon="🌬"
          title="Mistral AI"
          subtitle="Mistral Large, European-hosted and GDPR-friendly. Strong at coding and multilingual tasks."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'GDPR', color: 'green' }]}
          note="llm_provider=mistral  ·  mistral_api_key=…  ·  mistral_model=mistral-large-latest"
        />
        <Card
          icon="🤖"
          title="NVIDIA NIM"
          subtitle="NVIDIA-hosted or self-hosted NIM endpoints using the OpenAI-compatible chat completions API."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'OpenAI-compatible', color: 'green' }]}
          note="llm_provider=nvidia-nim / nvidia_nim_base_url=https://integrate.api.nvidia.com/v1"
        />
        <Card
          icon="ðŸ¤–"
          title="OpenAI"
          subtitle="GPT-4o, GPT-4o mini, o1, and future models via the official OpenAI API."
          badges={[{ label: 'Cloud', color: 'blue' }]}
          note="llm_provider=openai-compatible  ·  openai_base_url=https://api.openai.com/v1  ·  openai_model=gpt-4o"
        />
        <Card
          icon="🌐"
          title="OpenRouter"
          subtitle="One API key for every major model: Claude, Gemini, GPT-4o, Mistral, Llama, Command R, and hundreds more. Pay-per-token, no subscriptions."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Any model', color: 'purple' }]}
          note="llm_provider=openai-compatible  ·  openai_base_url=https://openrouter.ai/api/v1"
        />

        <Callout type="tip" title="OpenRouter — one key for everything">
          <p>Use <code>openai-compatible</code> with OpenRouter to access Claude, Gemini, GPT-4o,
          Mistral, and hundreds of other models through a single API key:</p>
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://openrouter.ai/api/v1
openai_api_key=sk-or-...
openai_model=anthropic/claude-opus-4`}</code></pre>
        </Callout>

        <h3>Models known to work well</h3>
        <table>
          <thead><tr><th>Model</th><th>Provider</th><th>Good for</th></tr></thead>
          <tbody>
            <tr><td><code>qwen2.5:7b</code></td><td>Ollama (local)</td><td>Daily driver — fast, tool-calling, 8 GB VRAM</td></tr>
            <tr><td><code>qwen2.5:14b</code></td><td>Ollama (local)</td><td>Better reasoning, 12 GB VRAM</td></tr>
            <tr><td><code>llama3.2:3b</code></td><td>Ollama (local)</td><td>Low-end hardware, 4 GB VRAM</td></tr>
            <tr><td><code>claude-sonnet-4-5</code></td><td>Anthropic</td><td>Business variant — complex instructions, tools</td></tr>
            <tr><td><code>gemini-2.0-flash</code></td><td>Google</td><td>Long context, multimodal, fast</td></tr>
            <tr><td><code>llama-3.3-70b-versatile</code></td><td>Groq</td><td>Fastest cloud response times</td></tr>
            <tr><td><code>command-r-plus</code></td><td>Cohere</td><td>RAG and structured retrieval tasks</td></tr>
            <tr><td><code>mistral-large-latest</code></td><td>Mistral</td><td>GDPR workloads, multilingual, coding</td></tr>
            <tr><td><code>gpt-4o-mini</code></td><td>OpenAI</td><td>Budget cloud option</td></tr>
          </tbody>
        </table>
      </section>

      {/* ── Messaging channels ── */}
      <section>
        <h2 id="channels">Messaging Channels</h2>
        <p>
          The Business variant routes messages from Telegram, Discord, Slack, or a generic
          webhook into Luna's chat engine. Each channel user gets a persistent conversation
          thread. UI-only commands (widgets, maps, Spotify) are automatically stripped from
          channel replies.
        </p>

        <Card
          icon="✈️"
          title="Telegram"
          subtitle="Set up a bot via @BotFather, point the webhook at your Luna instance. Supports markdown replies and per-user conversation history."
          badges={[{ label: 'Business', color: 'purple' }, { label: 'Personal', color: 'green' }]}
          note="telegram_bot_token=…  ·  Endpoint: POST /api/channels/telegram"
        />
        <Card
          icon="🎮"
          title="Discord"
          subtitle="Register a Discord application and set the Interactions Endpoint URL. Ed25519 signature verification built-in. Replies are capped at Discord's 2000-character limit."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="discord_bot_token=…  ·  discord_public_key=…  ·  Endpoint: POST /api/channels/discord"
        />
        <Card
          icon="💼"
          title="Slack"
          subtitle="Subscribe to the message.channels event in a Slack app. HMAC-SHA256 request signature verified on every inbound message."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="slack_bot_token=xoxb-…  ·  slack_signing_secret=…  ·  Endpoint: POST /api/channels/slack"
        />
        <Card
          icon="🔗"
          title="Generic webhook"
          subtitle='Post any JSON payload with user_id, user_name, and text fields — Luna replies with a plain-text reply field. Integrate with any platform.'
          badges={[{ label: 'Any platform', color: 'blue' }]}
          note='POST /api/channels/webhook  ·  {"user_id":"…","user_name":"…","text":"…"}'
        />

        <h3>Quick setup</h3>

        <CodeFile label=".env">
          <pre><code>{`# Telegram
telegram_bot_token=7123456789:AAF...

# Discord
discord_bot_token=MTI3...
discord_public_key=a1b2c3...

# Slack
slack_bot_token=xoxb-...
slack_signing_secret=abc123...`}</code></pre>
        </CodeFile>

        <CodeFile label="terminal — check which channels are live">
          <pre><code>{`curl http://localhost:8899/api/channels/status`}</code></pre>
        </CodeFile>

        <Callout type="info" title="Registering webhooks">
          <p>Luna must be publicly reachable for Telegram, Discord, and Slack to deliver
          messages. Use <code>luna tunnel</code> (ngrok) for local testing:</p>
          <pre><code>{`luna tunnel
# → https://abc123.ngrok-free.app
# Set this as your webhook URL in the respective platform dashboard`}</code></pre>
        </Callout>
      </section>

      {/* ── GitHub ── */}
      <section>
        <h2 id="github">GitHub</h2>
        <p>
          GitHub integration has two parts: a <strong>webhook receiver</strong> that turns GitHub
          events into Slack or Telegram notifications, and a set of <strong>Luna tools</strong>
          that let the LLM interact with your repositories directly via natural language.
        </p>

        <h3>Webhook events</h3>
        <Card
          icon="🐙"
          title="GitHub webhook"
          subtitle="Receives push, pull request, issue, issue comment, and release events from any repo or organisation. HMAC-SHA256 signature verified on every request."
          badges={[{ label: 'Both variants', color: 'purple' }]}
          note="github_webhook_secret=…  ·  Endpoint: POST /api/channels/github"
        />

        <p>Point a GitHub webhook at <code>https://YOUR_HOST/api/channels/github</code> and
        set the secret to the value of <code>github_webhook_secret</code> in your <code>.env</code>.
        Luna acknowledges every event and optionally forwards a formatted summary to Slack or Telegram:</p>

        <CodeFile label=".env">
          <pre><code>{`github_token=ghp_...               # Personal Access Token (repo scope)
github_webhook_secret=strong-secret  # Must match the secret in GitHub webhook settings

# Forward event summaries to a notification channel (optional — pick one)
github_notify_slack_channel=C0123ABCDEF    # Slack channel ID
github_notify_telegram_chat_id=123456789   # Telegram chat ID`}</code></pre>
        </CodeFile>

        <CodeFile label="GitHub → Settings → Webhooks">
          <pre><code>{`Payload URL:   https://YOUR_HOST/api/channels/github
Content type:  application/json
Secret:        <same as github_webhook_secret in .env>
Events:        ✓ Pushes  ✓ Pull requests  ✓ Issues  ✓ Issue comments  ✓ Releases`}</code></pre>
        </CodeFile>

        <h3>GitHub tools (LLM actions)</h3>
        <p>
          Set <code>github_token</code> in <code>.env</code> and Luna can interact with GitHub
          directly from chat. Set <code>github_default_repo</code> to avoid typing the repo
          name every time.
        </p>

        <table>
          <thead><tr><th>Tool</th><th>What it does</th><th>Permission</th></tr></thead>
          <tbody>
            <tr><td><code>github_list_repos</code></td><td>List your repos sorted by last update</td><td>allow</td></tr>
            <tr><td><code>github_list_issues(repo)</code></td><td>List open issues in a repo</td><td>allow</td></tr>
            <tr><td><code>github_list_prs(repo)</code></td><td>List open pull requests in a repo</td><td>allow</td></tr>
            <tr><td><code>github_get_pr(repo, number)</code></td><td>Get diff stats and details for a PR</td><td>allow</td></tr>
            <tr><td><code>github_create_issue(repo, title, body)</code></td><td>Open a new issue</td><td>confirm</td></tr>
            <tr><td><code>github_comment(repo, number, body)</code></td><td>Post a comment on an issue or PR</td><td>confirm</td></tr>
          </tbody>
        </table>

        <CodeFile label="chat examples">
          <pre><code>{`"List open issues in myorg/myrepo"
"Open an issue in myorg/myrepo: Add dark mode support"
"What PRs are waiting for review in myrepo?"
"Comment on issue #42 in myrepo: This is fixed in v2.1"`}</code></pre>
        </CodeFile>

        <Callout type="note" title="Token scopes">
          <p>A fine-grained PAT with <strong>Contents</strong> (read), <strong>Issues</strong> (read/write),
          and <strong>Pull requests</strong> (read) is sufficient. Classic tokens need the <code>repo</code> scope.</p>
        </Callout>
      </section>

      {/* ── Voice engines ── */}
      <section>
        <h2 id="voice">Voice Engines</h2>
        <p>Voice runs entirely on your machine. No audio is sent to external servers unless you configure a cloud TTS.</p>

        <h3>Speech-to-text (STT)</h3>
        <Card
          icon="🎙"
          title="faster-whisper"
          subtitle="OpenAI Whisper reimplemented in CTranslate2. Runs locally, significantly faster than the original. Recommended."
          badges={[{ label: 'Local', color: 'green' }, { label: 'Default', color: 'purple' }]}
          note="whisper_model=base  (tiny / base / small / medium / large)"
        />
        <Card
          icon="🔊"
          title="Vosk"
          subtitle="Offline speech recognition toolkit. Very fast, low memory footprint, good for wake-word detection on low-end hardware."
          badges={[{ label: 'Local', color: 'green' }]}
          note="voice_runtime=vosk"
        />

        <h3>Text-to-speech (TTS)</h3>
        <Card
          icon="🔉"
          title="edge-tts"
          subtitle="Microsoft Edge neural TTS voices. High quality, 300+ voices and languages. Requires an internet connection — audio is synthesised by Microsoft's servers."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Default', color: 'purple' }]}
          note="tts_provider=edge-tts"
        />
        <Card
          icon="💬"
          title="pyttsx3"
          subtitle="Fully offline TTS using the OS voice engine (SAPI5 on Windows, NSSpeechSynthesizer on macOS, eSpeak on Linux). No internet required."
          badges={[{ label: 'Local', color: 'green' }]}
          note="tts_provider=pyttsx3  ·  tts_voice_index=0"
        />

        <p>
          For the full STT/TTS config options and model tradeoff table, see the{' '}
          <a href="/voice" style={{ color: '#7c3aed' }}>Voice</a> page.
          Voice is a Personal variant feature and is disabled in Business mode.
        </p>
      </section>

      {/* ── Desktop apps ── */}
      <section>
        <h2 id="apps">Desktop Apps &amp; Automation</h2>
        <p>
          Luna can launch and control apps through natural language on Windows, macOS, and Linux.
          Every action goes through the permission system — <code>allow</code>, <code>confirm</code>,
          or <code>block</code> per tool. Desktop features are available in the{' '}
          <strong>Personal</strong> variant only unless noted.
        </p>

        <h3>App launcher</h3>
        <Card
          icon="🖥"
          title="App launcher — 80+ app profiles"
          subtitle='Launch any app by name across Windows, macOS, and Linux. Say "open VS Code", "launch Figma", "open Discord". Discovery uses curated profiles, macOS Spotlight (mdfind), Linux .desktop files, Windows registry, and Start Menu — covering virtually any installed app.'
          badges={[{ label: 'Personal only', color: 'green' }, { label: 'Cross-platform', color: 'purple' }]}
          note='luna dev → "open <app name>" to launch. Covers all categories below.'
        />

        <table>
          <thead><tr><th>Category</th><th>Apps covered</th></tr></thead>
          <tbody>
            <tr><td>Browsers</td><td>Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi, Tor, Arc</td></tr>
            <tr><td>Terminals &amp; editors</td><td>VS Code, Cursor, Sublime Text, Vim, Emacs, Warp, Hyper, Xcode, Visual Studio</td></tr>
            <tr><td>IDEs</td><td>PyCharm, IntelliJ, WebStorm, Android Studio, Rider, CLion, DataGrip, GoLand, Eclipse, NetBeans</td></tr>
            <tr><td>Dev tools</td><td>Postman, Insomnia, DBeaver, TablePlus, Sequel Pro, GitHub Desktop, GitKraken, Sourcetree, Docker, Figma</td></tr>
            <tr><td>Communication</td><td>Slack, Zoom, Teams, Discord, Signal, WhatsApp, Telegram, Skype, Viber, Messages, FaceTime, Outlook, Thunderbird</td></tr>
            <tr><td>Office</td><td>Word, Excel, PowerPoint, LibreOffice, Pages, Numbers, Keynote, Notion, Obsidian</td></tr>
            <tr><td>Media &amp; creative</td><td>VLC, Spotify, Music, GIMP, Inkscape, Audacity, Blender, OBS, Kdenlive, DaVinci Resolve, HandBrake</td></tr>
            <tr><td>Cloud &amp; storage</td><td>Dropbox, OneDrive, Google Drive</td></tr>
            <tr><td>Gaming</td><td>Steam, Epic Games, Xbox</td></tr>
            <tr><td>Security</td><td>Bitwarden, 1Password, Windows Security</td></tr>
            <tr><td>System utilities</td><td>Task Manager, Activity Monitor, Event Viewer, Device Manager, Registry Editor, Disk Utility, Disk Management, Task Scheduler, Resource Monitor</td></tr>
            <tr><td>System settings</td><td>Settings, Display, Sound, Bluetooth, Network, Updates, Privacy, Accessibility (all platforms)</td></tr>
            <tr><td>macOS system apps</td><td>Safari, Mail, Messages, FaceTime, Music, Podcasts, Books, News, Contacts, Reminders, Calendar, Maps, Notes, Stickies, Console, Keychain Access, Disk Utility, Script Editor, Automator, Font Book, Preview, Voice Memos, Find My</td></tr>
            <tr><td>Linux (XDG)</td><td>Any app with a <code>.desktop</code> file — Flatpak, Snap, and natively installed apps all discovered automatically</td></tr>
          </tbody>
        </table>

        <h3>System controls</h3>
        <Card
          icon="🔊"
          title="Volume"
          subtitle='Get and set system volume (0–100), mute/unmute. Works on Windows (PowerShell/nircmd), macOS (osascript), and Linux (pactl/amixer). Say "set volume to 40", "mute", "unmute".'
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: GET/POST /api/system/volume  ·  POST /api/system/volume/mute|unmute"
        />
        <Card
          icon="☀️"
          title="Brightness"
          subtitle='Get and set display brightness (0–100). Windows uses WMI, macOS uses the brightness CLI (brew install brightness), Linux uses brightnessctl or xbacklight. Say "set brightness to 60".'
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: GET/POST /api/system/brightness"
        />
        <Card
          icon="🔒"
          title="Lock screen"
          subtitle='Instantly lock the workstation. Windows: rundll32 LockWorkStation. macOS: Command+Control+Q. Linux: loginctl lock-session or xdg-screensaver. Say "lock my screen".'
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: POST /api/system/lock"
        />
        <Card
          icon="💤"
          title="Sleep"
          subtitle='Put the system to sleep / suspend. Windows: SetSuspendState. macOS: pmset sleepnow. Linux: systemctl suspend. Requires confirm permission by default.'
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: POST /api/system/sleep  ·  Permission: confirm"
        />
        <Card
          icon="📋"
          title="Clipboard"
          subtitle={`Read and write the system clipboard. Windows: PowerShell Get/Set-Clipboard. macOS: pbpaste/pbcopy. Linux: xclip, xsel, or wl-paste/wl-copy. Say "copy this to clipboard" or "what's in my clipboard?"`}
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: GET/POST /api/system/clipboard"
        />
        <Card
          icon="🖥"
          title="Display off"
          subtitle="Turn off the display without sleeping the system. Windows: SendMessage. macOS: pmset displaysleepnow. Linux: xset dpms."
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: POST /api/system/display/off"
        />
        <Card
          icon="ℹ️"
          title="System info"
          subtitle="Report OS, RAM, battery percentage, and machine name. Cross-platform via WMI (Windows), sysctl (macOS), and /proc (Linux)."
          badges={[{ label: 'Cross-platform', color: 'purple' }]}
          note="API: GET /api/system/info"
        />

        <h3>Other personal features</h3>
        <Card
          icon="🎵"
          title="Spotify"
          subtitle='Playback control, queue management, search, and now-playing display. Trigger with phrases like "play something chill" or "skip this".'
          badges={[{ label: 'Personal only', color: 'green' }, { label: 'Opt-in', color: 'blue' }]}
          note="Requires spotify_client_id and spotify_client_secret in .env."
        />
        <Card
          icon="🌐"
          title="Web browser"
          subtitle="Open URLs and read public page content. Playwright can be enabled for full browser automation including JavaScript-rendered pages."
          badges={[{ label: 'Built-in', color: 'purple' }]}
          note="Playwright: pip install playwright && playwright install chromium"
        />
        <Card
          icon="📅"
          title="Calendar &amp; tasks"
          subtitle="Create, list, update, and complete tasks in Luna's local SQLite database. Proactive reminders fire when tasks are due."
          badges={[{ label: 'Both variants', color: 'purple' }]}
        />
        <Card
          icon="🔍"
          title="Web search"
          subtitle="DuckDuckGo HTML search — no API key required. Fires automatically when the LLM needs live information."
          badges={[{ label: 'Both variants', color: 'purple' }]}
        />
        <Card
          icon="🔈"
          title="Audio device switcher"
          subtitle="Switch the default Windows audio output device by name — headphones, speakers, virtual audio."
          badges={[{ label: 'Windows only', color: 'gray' }]}
          note="API: GET /api/system/audio-devices  ·  POST /api/system/audio-device"
        />
        <Card
          icon="🗺"
          title="Maps"
          subtitle="Open interactive MapLibre map overlays with a location query."
          badges={[{ label: 'Personal only', color: 'green' }]}
        />
      </section>

      {/* ── Live data ── */}
      <section>
        <h2 id="data">Live Data &amp; APIs</h2>
        <p>These feed the Luna dashboard and the LLM's context. All are opt-in except Open-Meteo.</p>

        <Card
          icon="⛅"
          title="Open-Meteo"
          subtitle="Free, no-key weather API. Returns current conditions and forecasts for any coordinates. Default weather provider."
          badges={[{ label: 'Free', color: 'green' }, { label: 'No key', color: 'green' }]}
          note="Set weather_lat, weather_lon, weather_city, weather_timezone in .env."
        />
        <Card
          icon="📰"
          title="TheNewsAPI"
          subtitle="Live top headlines and category-filtered news articles for the dashboard. Falls back to RSS when no key is configured."
          badges={[{ label: 'Opt-in', color: 'blue' }]}
          note="the_news_api=your-key"
        />
        <Card
          icon="📈"
          title="Yahoo Finance"
          subtitle="Stock quotes and market data. Used by default for equities in the dashboard — no API key required."
          badges={[{ label: 'No key', color: 'green' }]}
        />
        <Card
          icon="🪙"
          title="CoinGecko"
          subtitle="Cryptocurrency prices and market cap data. Used by default for crypto widgets — no API key required."
          badges={[{ label: 'No key', color: 'green' }]}
        />
        <Card
          icon="📊"
          title="Alpha Vantage"
          subtitle="Extended stock market data and technical indicators. Used as an alternative data source when configured."
          badges={[{ label: 'Opt-in', color: 'blue' }]}
          note="alpha_vantage=your-key"
        />
      </section>

      {/* ── Health ── */}
      <section>
        <h2 id="health">Health Platforms</h2>
        <p>
          Connect wearables and health apps to give Luna awareness of your fitness, sleep,
          heart rate, and body metrics. All data is stored locally — nothing is sent to any cloud.
        </p>

        <Card
          icon="⌚"
          title="Fitbit"
          subtitle="Full REST API coverage: steps, distance, calories, heart rate, HRV, all sleep stages, SpO2, breathing rate, skin temperature, and weight. OAuth2 setup takes about 2 minutes."
          badges={[{ label: 'OAuth2', color: 'blue' }, { label: 'Personal', color: 'green' }]}
          note="fitbit_client_id= · fitbit_client_secret= · GET /api/health/oauth/authorize/fitbit"
        />
        <Card
          icon="🏃"
          title="Google Fit"
          subtitle="Aggregates activity data from any Android wearable synced to Google Fit — Pixel Watch, Galaxy Watch, Wear OS devices, and more. Steps, calories, HR, weight, sleep via Google OAuth2."
          badges={[{ label: 'OAuth2', color: 'blue' }, { label: 'Android ecosystem', color: 'purple' }]}
          note="google_fit_client_id= · google_fit_client_secret= · GET /api/health/oauth/authorize/google_fit"
        />
        <Card
          icon="💍"
          title="Oura Ring"
          subtitle="Best-in-class sleep staging, HRV, resting heart rate, readiness score, stress levels, and respiratory rate. Simple personal access token auth — no OAuth flow."
          badges={[{ label: 'API token', color: 'purple' }, { label: 'Best HRV data', color: 'green' }]}
          note="oura_api_key= — cloud.ouraring.com/user/api-tokens"
        />
        <Card
          icon="⚖️"
          title="Withings"
          subtitle="Medical-grade smart scales (weight, BMI, body fat), blood pressure monitors, and sleep mats. The only platform that provides blood pressure readings."
          badges={[{ label: 'OAuth2', color: 'blue' }, { label: 'Blood pressure', color: 'purple' }]}
          note="withings_client_id= · withings_client_secret= · GET /api/health/oauth/authorize/withings"
        />
        <Card
          icon="🏔"
          title="Garmin Connect"
          subtitle="Detailed GPS workouts, VO2 Max, Body Battery (readiness), stress, sleep stages, and SpO2 via the garth library. Works with every Garmin wearable: Forerunner, Fenix, Venu, and more."
          badges={[{ label: 'Credentials', color: 'gray' }]}
          note="garmin_email= · garmin_password= · pip install garth"
        />
        <Card
          icon="🍎"
          title="Apple Health"
          subtitle="All HealthKit metrics from Apple Watch via webhook push. Apple has no public REST API, so Luna uses the free 'Health Auto Export' iOS app to push data on a schedule."
          badges={[{ label: 'Webhook', color: 'gray' }, { label: 'iOS app needed', color: 'blue' }]}
          note="Endpoint: POST /api/health/webhook/apple · health_webhook_secret= in .env"
        />
        <Card
          icon="📱"
          title="Samsung Health"
          subtitle="Galaxy Watch and Galaxy Fit data via a compatible Android exporter app. Supports the same Health Auto Export JSON format as Apple Health."
          badges={[{ label: 'Webhook', color: 'gray' }, { label: 'Android app needed', color: 'blue' }]}
          note="Endpoint: POST /api/health/webhook/samsung · health_webhook_secret= in .env"
        />

        <Callout type="tip" title="Full health documentation">
          <p>
            For setup guides, supported device lists, all 23 metric types, API reference,
            and chat examples, see the{' '}
            <a href="/health" style={{ color: '#7c3aed' }}>Health Platforms</a> page.
          </p>
        </Callout>
      </section>

      {/* ── Production ── */}
      <section>
        <h2 id="production">Production</h2>
        <p>
          The Business variant includes production-grade features for team deployments. All
          are configured in <code>.env</code>.
        </p>

        <Card
          icon="🔐"
          title="JWT Authentication"
          subtitle="HS256 JSON Web Tokens for multi-user access. Issue per-user tokens with expiry, rotate them without downtime, and list active users via the admin API."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="jwt_secret=…  ·  jwt_expiry_hours=720"
        />
        <Card
          icon="🚦"
          title="Rate limiting"
          subtitle="Sliding-window in-memory rate limiter. Configurable per-minute limit and burst allowance. Returns 429 with Retry-After header when exceeded. No Redis required."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="rate_limit_enabled=true  ·  rate_limit_per_minute=60  ·  rate_limit_burst=20"
        />
        <Card
          icon="👥"
          title="Admin user management API"
          subtitle="Create, list, rotate tokens, and delete users via REST API. User store is a flat JSON file — no database migration needed."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="GET/POST /api/admin/users  ·  DELETE /api/admin/users/{id}  ·  POST /api/admin/users/{id}/rotate-token"
        />
        <Card
          icon="🔒"
          title="HTTPS / reverse proxy"
          subtitle="compose.business.yml includes a commented nginx block for TLS termination. Point a domain at the container and uncomment to enable HTTPS."
          badges={[{ label: 'Business', color: 'purple' }]}
          note="See the commented nginx service in compose.business.yml"
        />

        <h3>Admin API quick reference</h3>
        <CodeFile label="terminal — create a user and get a token">
          <pre><code>{`curl -X POST http://localhost:8899/api/admin/users \\
  -H "Authorization: Bearer $JWT_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"alice","email":"alice@example.com"}'
# → {"id":"…","name":"alice","token":"eyJ…"}`}</code></pre>
        </CodeFile>

        <CodeFile label="terminal — list all providers and their status">
          <pre><code>{`curl http://localhost:8899/api/admin/llm/providers \\
  -H "Authorization: Bearer $JWT_SECRET"`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="Setting the admin token">
          <p>Generate a strong secret with <code>openssl rand -hex 32</code> and set it as <code>jwt_secret</code> in <code>.env</code>.
          Admin API calls use <code>Authorization: Bearer &lt;jwt_secret&gt;</code>.</p>
        </Callout>
      </section>

      {/* ── Platforms ── */}
      <section>
        <h2 id="platforms">Platforms</h2>
        <p>Where Luna runs and what works on each platform.</p>

        <Grid>
          <PlatformCard
            icon="🪟"
            name="Windows"
            status="Full support"
            detail="Electron desktop app, voice input/output, app launcher, audio switcher, Spotify, camera, screen vision. Primary development target."
          />
          <PlatformCard
            icon="🍎"
            name="macOS"
            status="Full support"
            detail="Electron desktop app, voice input/output, app launcher, Spotify. Audio switcher not available. Tested on Apple Silicon."
          />
          <PlatformCard
            icon="🐧"
            name="Linux"
            status="Full support"
            detail="Electron desktop app. Voice works with PortAudio. pyttsx3 uses eSpeak. Audio switcher not available. Best with Docker."
          />
          <PlatformCard
            icon="🐳"
            name="Docker"
            status="Partial"
            detail="Full chat, memory, tools, channels, admin API, and rate limiting. Voice, Electron shell, and OS-level automation are desktop-only. Any device with Docker installed."
          />
          <PlatformCard
            icon="📱"
            name="Phone / Tablet"
            status="Partial"
            detail="Browser access via local network (LAN mode) or via Telegram/Discord/Slack channels in the Business variant. Chat and dashboard work fully."
          />
          <PlatformCard
            icon="💻"
            name="Second computer"
            status="Partial"
            detail="Any machine on your LAN can connect to the same Luna backend via browser. Set host=0.0.0.0 in .env."
          />
        </Grid>

        <Callout type="info" title="LAN / multi-device access">
          <pre><code>{`# .env
host=0.0.0.0`}</code></pre>
          <p style={{ margin: '8px 0 0' }}>
            Then open <code>http://YOUR-LAN-IP:8899</code> on any device. For the business variant,
            set <code>jwt_secret</code> to protect the admin API.
          </p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/environment', label: 'Config',    title: 'Environment',    desc: 'Every .env key for all 8 LLM providers, channels, auth, and rate limiting.' },
        { href: '/voice',       label: 'Voice',     title: 'Voice',          desc: 'STT/TTS model details, wake word config, and tradeoff table.' },
        { href: '/agent',       label: 'Agent',     title: 'Agent & Skills', desc: 'Permission system, tool registry, and custom skills.' },
      ]} />
    </DocsLayout>
  );
}

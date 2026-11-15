import { useState } from 'react';
import DocsLayout from '../components/DocsLayout';
import { Callout, NextSteps } from '../components/Docs';

const toc = [
  { id: 'explorer', label: 'File explorer' },
  { id: 'entry',    label: 'Key entry points' },
];

// ── File type icon ────────────────────────────────────────────────────────────
function fileIcon(name) {
  if (!name) return '📄';
  if (name.endsWith('.py'))                             return '🐍';
  if (name.endsWith('.ts') || name.endsWith('.tsx'))   return '📘';
  if (name.endsWith('.js') || name.endsWith('.mjs') || name.endsWith('.jsx')) return '📜';
  if (name.endsWith('.json'))                           return '📋';
  if (name.endsWith('.md'))                             return '📝';
  if (name.endsWith('.css'))                            return '🎨';
  if (name.endsWith('.svg'))                            return '🖼';
  if (name.endsWith('.yml') || name.endsWith('.yaml')) return '⚙️';
  if (name.startsWith('.env'))                          return '🔑';
  if (name.endsWith('.db'))                             return '🗄';
  if (name.endsWith('.log'))                            return '📋';
  if (name.endsWith('.txt'))                            return '📄';
  return '📄';
}

// ── Tree data ─────────────────────────────────────────────────────────────────
// Each node: { name, type:'file'|'folder', desc, children? }
// Paths are added by addPaths() at load time.

const RAW_TREE = {
  name: 'Luna/', type: 'folder',
  desc: 'Repository root. Contains all workspace packages, config files, and Docker Compose definitions.',
  children: [
    {
      name: 'backend/', type: 'folder',
      desc: 'FastAPI Python backend — all server logic, LLM calls, services, routers, and background workers.',
      children: [
        { name: 'main.py', type: 'file', desc: 'FastAPI app bootstrap. Mounts all routers, adds the rate limiting middleware, sets up CORS, and starts background processes on startup. Add new routers here.' },
        { name: 'config.py', type: 'file', desc: 'Pydantic Settings class that reads every .env key and exposes them as typed attributes on the `settings` singleton. All backend code reads config here — never os.environ directly.' },
        {
          name: 'middleware/', type: 'folder',
          desc: 'ASGI middleware stack.',
          children: [
            { name: '__init__.py', type: 'file', desc: 'Empty package marker.' },
            { name: 'rate_limit.py', type: 'file', desc: 'Sliding-window in-memory rate limiter (BaseHTTPMiddleware). Tracks per-IP request timestamps in a deque. Returns 429 with Retry-After: 60 when the window is exceeded. Skips /api/system/health, /api/auth/check, and /api/channels/discord.' },
          ]
        },
        {
          name: 'routers/', type: 'folder',
          desc: 'FastAPI route handlers. One file per URL prefix. Routers are thin — they validate input and delegate to services.',
          children: [
            { name: 'admin.py', type: 'file', desc: 'Business-variant user and JWT token management. Endpoints: GET /api/admin/info, GET/POST /api/admin/users, DELETE /api/admin/users/{id}, POST /api/admin/users/{id}/rotate-token, GET /api/admin/llm/providers. All require Authorization: Bearer <jwt_secret>. Uses flat-file data/users.json. Signs HS256 JWTs via PyJWT, falls back to opaque tokens if PyJWT not installed.' },
            { name: 'channels.py', type: 'file', desc: 'Messaging channel webhooks. Telegram (Bot API), Discord (Ed25519 signature verification via PyNaCl), Slack (HMAC-SHA256), and generic HTTP webhook. Routes to channel_bridge.handle_channel_message(). Discord PING/type-1 verification returns immediately without calling the LLM.' },
            { name: 'chat.py', type: 'file', desc: 'Primary chat endpoint. POST /api/chat/stream returns an SSE stream. Assembles the system prompt (personal vs business variant), injects memory/personality/calendar/vision context, calls the LLM, executes tool commands, and updates memory post-stream.' },
            { name: 'luna.py', type: 'file', desc: 'Luna dashboard data. GET /api/luna/dashboard bundles weather, markets, and news into one call. Individual endpoints: /api/luna/weather, /api/luna/markets, /api/luna/news.' },
            { name: 'system.py', type: 'file', desc: 'System utilities. Health check (/api/system/health), background process status, proactive message queue, app launch, 3D scene generation, and app state persistence.' },
            { name: 'memory.py', type: 'file', desc: 'Memory CRUD. Fact list/add/delete, semantic search via ChromaDB, personality state get/update, and conversation compaction trigger.' },
            { name: 'voice.py', type: 'file', desc: 'Voice I/O. POST /api/voice/transcribe accepts a WAV blob and returns text. POST /api/voice/speak plays TTS audio. GET /api/voice/status returns current STT/TTS state. GET /api/voice/events is an SSE stream for voice state changes.' },
            { name: 'vision.py', type: 'file', desc: 'Computer vision. POST /api/vision/screen captures and describes the screen. POST /api/vision/camera captures a camera frame. POST /api/vision/frame receives a JPEG frame from the frontend camera hook. All require the vision permission to be allow or confirm.' },
            { name: 'agent.py', type: 'file', desc: 'Agent platform. Skills list, permission CRUD, workspace file read/write/list, multi-step task management, browser status, and audit log endpoints.' },
            { name: 'spotify.py', type: 'file', desc: 'Spotify OAuth flow and playback control. OAuth redirect at /api/spotify/login, callback at /api/spotify/callback. Playback: play, pause, next, prev, volume. Requires spotify_client_id and spotify_client_secret in .env.' },
            { name: 'calendar.py', type: 'file', desc: 'Tasks and calendar events CRUD. Full lifecycle for tasks (create, list, update, complete, delete) and events (create, list, update, delete). Both stored in SQLite.' },
            { name: 'state.py', type: 'file', desc: 'UI application state persistence. GET /api/state and PUT /api/state store the active conversation, sidebar view, and other preferences across sessions.' },
          ]
        },
        {
          name: 'services/', type: 'folder',
          desc: 'Business logic. All non-trivial code lives here; routers delegate to services.',
          children: [
            { name: 'llm.py', type: 'file', desc: 'Multi-provider LLM client. Implements streaming generators for all 8 providers (Ollama, NVIDIA NIM, Anthropic, Google, Groq, Cohere, Mistral, OpenAI-compatible) via raw httpx — no external SDKs. LLMClient.stream_chat() and complete() dispatch on settings.llm_provider. A singleton `ollama = LLMClient()` is exported for backward compatibility.' },
            { name: 'channel_bridge.py', type: 'file', desc: 'Messaging channel session management. Each {channel}:{user_id} key gets a ChannelSession with independent conversation history (capped at 40 turns). handle_channel_message() calls the LLM and strips UI commands ([LAUNCH:…], [WIDGET:…], [SPOTIFY:…], [MAP:…]) from replies before returning plain text.' },
            { name: 'memory_manager.py', type: 'file', desc: 'Persistent memory layer. CRUD for facts in SQLite, vector embedding into ChromaDB, and cosine-similarity semantic search. Manages fact confidence scoring and last-accessed timestamps.' },
            { name: 'personality.py', type: 'file', desc: 'Personality state machine. Tracks mood, energy, formality, humor, and emotional_support as floats in [0,1]. Updates based on conversation sentiment and user feedback signals.' },
            { name: 'fact_extractor.py', type: 'file', desc: 'Extracts new facts from conversation turns using an LLM pass after each assistant response. Deduplicates against existing facts before writing to SQLite.' },
            { name: 'tool_registry.py', type: 'file', desc: 'Tool registration and dispatch. Each tool is registered with a name, callable, and default permission mode (allow/confirm/block). dispatch() checks the permission before executing and writes to audit.log.' },
            { name: 'app_launcher.py', type: 'file', desc: 'Cross-platform app launcher. Platform-specific profiles for browsers, editors, terminals, file managers, notes, office, and more. Windows uses Start Menu, registry, and AppID discovery. Falls back to PATH.' },
            { name: 'web_tools.py', type: 'file', desc: 'Web search and page fetch. web_search() hits DuckDuckGo HTML search (no API key). web_fetch() retrieves a URL via httpx, optionally via Playwright for JS-rendered pages.' },
            { name: 'scheduler.py', type: 'file', desc: 'Background job orchestrator. Runs registered background processes on their configured schedules using asyncio. Exposes start/stop and status reporting to the system router.' },
            { name: 'vision.py', type: 'file', desc: 'Vision pipeline. screen_capture() takes a screenshot and sends it to the vision model. camera_capture() captures a frame from the default camera. Both produce natural-language descriptions without storing raw frames.' },
            { name: 'spotify.py', type: 'file', desc: 'Spotify API client. Manages access token refresh, wraps the Spotify Web API for playback control, queue management, and now-playing state.' },
            { name: 'workspace.py', type: 'file', desc: 'Agent workspace sandbox. All agent-created files live under data/workspace/. Provides safe read/write/list with path traversal protection.' },
            {
              name: 'dashboard/', type: 'folder',
              desc: 'Live data providers for the dashboard.',
              children: [
                { name: 'weather.py', type: 'file', desc: 'Fetches current conditions and forecast from Open-Meteo (free, no key). Reads weather_lat, weather_lon, weather_city, weather_timezone from config.' },
                { name: 'markets.py', type: 'file', desc: 'Fetches stock quotes from Yahoo Finance (no key) and Alpha Vantage (optional key). Fetches crypto prices from CoinGecko (no key).' },
                { name: 'news.py', type: 'file', desc: 'Fetches top headlines from TheNewsAPI (requires the_news_api key). Falls back to curated RSS feeds when no key is set.' },
                { name: 'articles.py', type: 'file', desc: 'SQLite storage for news articles shown in the dashboard. Deduplicates by URL and expires articles after 48 hours.' },
              ]
            },
          ]
        },
        {
          name: 'processes/', type: 'folder',
          desc: 'Long-running background workers registered with the scheduler.',
          children: [
            { name: 'registry.py', type: 'file', desc: 'Registers all background processes with the scheduler at startup. Add new background workers here.' },
            { name: 'memory_maintenance/', type: 'folder', desc: 'Periodic fact extraction from recent conversations, conversation compaction (summarising older turns into embeddings), and fact pruning (removing low-confidence facts).', children: [] },
            { name: 'proactive_followups/', type: 'folder', desc: 'Generates unsolicited Luna messages based on pending tasks, upcoming events, and user patterns. Pushes messages to the proactive queue polled by the frontend.', children: [] },
            { name: 'calendar_reminders/', type: 'folder', desc: 'Polls for tasks and events due within the reminder window and pushes reminder messages to the proactive queue.', children: [] },
            { name: 'voice_runtime/', type: 'folder', desc: 'Wake-word detection loop using Vosk or a keyword spotter. When the wake word fires, hands control to the voice router for a full STT → LLM → TTS round-trip.', children: [] },
          ]
        },
        {
          name: 'models/', type: 'folder',
          desc: 'SQLAlchemy ORM models.',
          children: [
            { name: 'database.py', type: 'file', desc: 'Defines all SQLAlchemy models: Conversation, Message, Fact, Task, CalendarEvent, Activity, AppState, and more. Also creates the DB engine and session factory used across the backend.' },
          ]
        },
      ]
    },
    {
      name: 'frontend/', type: 'folder',
      desc: 'React + Vite + TypeScript UI. Compiled to frontend/dist/ for production. In dev, proxies /api/* to localhost:8899.',
      children: [
        {
          name: 'src/', type: 'folder',
          desc: 'All TypeScript source code.',
          children: [
            { name: 'App.tsx', type: 'file', desc: 'Root React component. Routes between three view modes: dev (developer panel), user (voice screen), and luna (full-screen dashboard). Reads active view from Zustand store. Runs startup health check and periodic proactive message polling.' },
            { name: 'main.tsx', type: 'file', desc: 'Vite entry point. Mounts App into the DOM, sets up the global error boundary.' },
            { name: 'index.css', type: 'file', desc: 'Global styles. Tailwind base layers, custom scrollbar styles, prose typography, and luna-* CSS variable definitions.' },
            {
              name: 'api/', type: 'folder',
              desc: 'Typed wrappers around the backend HTTP API.',
              children: [
                { name: 'client.ts', type: 'file', desc: 'Core HTTP client. BASE URL from electronAPI.apiBase (Electron) or same-origin (browser). The `api` object exports all typed request helpers. streamChat() implements the SSE stream reader for chat responses.' },
                { name: 'chat.ts', type: 'file', desc: 'Additional chat API helpers if needed alongside client.ts.' },
              ]
            },
            {
              name: 'components/', type: 'folder',
              desc: 'Feature-grouped UI components.',
              children: [
                { name: 'Chat/', type: 'folder', desc: 'ChatWindow — message list and scroll container. InputBar — text input, voice toggle, and submit. MessageBubble — renders individual messages with markdown, widgets, and tool call indicators.', children: [] },
                { name: 'Voice/', type: 'folder', desc: 'VoiceOrb — animated orb that reflects voice state (idle/listening/processing/speaking) via an SSE stream. PhoneMic — mobile-optimised recording UI with push-to-talk.', children: [] },
                { name: 'Dynamic/', type: 'folder', desc: 'DynamicWidgetOverlay — renders Luna-generated widget overlays (steps, timelines, code blocks, comparisons, tabs). GeneratedScene and ThreeDScene — render Three.js 3D scenes from LLM-generated code via [SCENE:…] commands.', children: [] },
                { name: 'Map/', type: 'folder', desc: 'HologramMapOverlay — full-screen MapLibre GL map with Luna holographic styling. Triggered by [MAP:…] commands in chat. Supports location search and route display.', children: [] },
                { name: 'Luna/', type: 'folder', desc: 'LunaDashboardView — full-screen HUD with weather, markets, and news widgets. LunaDashboardToggle — sidebar button to switch into dashboard mode. lunaDashboardApi.ts — cached data fetching for dashboard widgets.', children: [] },
                { name: 'Layout/', type: 'folder', desc: 'Sidebar — navigation between chat, memory, calendar, agent, and other views. TitleBar — Electron window drag region with controls. AwayScreen — idle overlay. SpeakerPicker — audio output device selector.', children: [] },
                { name: 'Agent/', type: 'folder', desc: 'AgentView — shows active tasks, workspace files, skill registry, and permission editor for each registered tool.', children: [] },
                { name: 'Spotify/', type: 'folder', desc: 'SpotifyPlayer — now-playing card with track info and playback controls (play/pause/skip/volume), embedded in the chat sidebar.', children: [] },
                { name: 'Auth/', type: 'folder', desc: 'LunaLogin stub — kept for future JWT login UI for the Business variant.', children: [] },
              ]
            },
            { name: 'hooks/', type: 'folder', desc: 'Reusable React hooks. useCamera.ts — periodically captures camera frames and POSTs them to /api/vision/frame.', children: [] },
            { name: 'store/', type: 'folder', desc: 'Zustand global store (index.ts). All application state: active conversation, messages, memory facts, personality, voice status, sidebar view, Spotify state, permissions, and map overlay state.', children: [] },
            { name: 'types/', type: 'folder', desc: 'Shared TypeScript interfaces. electron.d.ts declares the window.electronAPI shape exposed by the preload script.', children: [] },
          ]
        },
        { name: 'vite.config.ts', type: 'file', desc: 'Vite dev server config. Proxies /api/* → http://localhost:8899 so the frontend can call the backend in dev without CORS issues.' },
        { name: 'tailwind.config.js', type: 'file', desc: 'Tailwind CSS config. Defines the custom luna-* colour palette (deep purples and near-black), custom animations (pulse-slow, glow, float), and content paths.' },
        { name: 'tsconfig.json', type: 'file', desc: 'TypeScript compiler config. Strict mode enabled. Path aliases for @ → src/.' },
      ]
    },
    {
      name: 'electron/', type: 'folder',
      desc: 'Electron desktop shell. Manages window creation, backend process lifecycle, system tray, and the contextBridge IPC layer.',
      children: [
        { name: 'main.js', type: 'file', desc: 'Main process entry. Creates the BrowserWindow, spawns the FastAPI backend as a child process with exponential-backoff restart (stops after 3 crashes in 60s and shows an error dialog), sets up the system tray icon, and handles IPC messages from the renderer.' },
        { name: 'preload.js', type: 'file', desc: 'contextBridge script. Exposes window.electronAPI with: apiBase (backend URL), isElectron (true), window controls, notify, openUrl, Spotify OAuth helpers, clipboard, and away mode. Does not expose any secrets.' },
      ]
    },
    {
      name: 'cli/', type: 'folder',
      desc: 'Developer CLI.',
      children: [
        { name: 'luna.mjs', type: 'file', desc: 'Main CLI entry point (Node.js ESM). Implements all `luna <command>` subcommands: setup, dev, web, backend, docker, doctor, health, chat, tunnel, build, check, processes, clean, and more. Registered as the luna bin in package.json so npm link exposes it as the `luna` command.' },
      ]
    },
    {
      name: 'scripts/', type: 'folder',
      desc: 'Automation scripts invoked by CLI commands.',
      children: [
        { name: 'docker.mjs', type: 'file', desc: 'Docker automation. Auto-detects mode (business / cloud / GPU / CPU) from .env by reading luna_variant and llm_provider. Runs preflight checks, starts the correct compose stack, waits for /api/system/health, and pulls Ollama models into the running container.' },
        { name: 'setup.mjs', type: 'file', desc: 'Interactive first-time setup wizard. Prompts for variant (personal/business) and LLM provider, copies the correct .env example file, installs Python dependencies into .venv, and pulls Ollama models.' },
        { name: 'ensure-global-path.mjs', type: 'file', desc: 'Checks that npm global bin directory is on PATH after npm link. Prints a warning with fix instructions if not.' },
      ]
    },
    {
      name: 'docs-site/', type: 'folder',
      desc: 'This documentation website. Built with Next.js, deployed to Vercel.',
      children: [
        { name: 'pages/', type: 'folder', desc: 'Next.js pages — one file per documentation page. Each page wraps content in DocsLayout which provides the sidebar, TOC panel, and top bar.', children: [] },
        { name: 'components/', type: 'folder', desc: 'Shared doc components: DocsLayout (nav + TOC + theme toggle), Callout, CodeFile, Steps/Step (numbered step list), NextSteps (bottom navigation cards).', children: [] },
        { name: 'styles/', type: 'folder', desc: 'Global CSS for the docs site — integration cards (.int-card), callout boxes (.callout-*), code file blocks (.code-file), and the three-column sidebar layout.', children: [] },
      ]
    },
    {
      name: 'data/', type: 'folder',
      desc: 'Runtime data directory. Entirely gitignored. Created automatically on first run. Never commit this.',
      children: [
        { name: 'luna.db', type: 'file', desc: 'SQLite database. Contains all conversations, messages, memory facts, tasks, calendar events, personality state, and activity records.' },
        { name: 'chroma/', type: 'folder', desc: 'ChromaDB vector store. Stores fact embeddings for semantic search. Written and queried by memory_manager.py.', children: [] },
        { name: 'workspace/', type: 'folder', desc: 'Agent sandbox. Files created by Luna during task execution. User-created skills can also live at workspace/skills/. Path-traversal protected.', children: [] },
        { name: 'users.json', type: 'file', desc: 'Business variant user store. Flat JSON file containing user records (id, username, role, token_hash). Managed by the admin router. Never commit.' },
        { name: 'permissions.json', type: 'file', desc: 'Persisted per-tool permission overrides. Written by the agent permissions API. Loaded on startup by the tool registry.' },
        { name: 'audit.log', type: 'file', desc: 'Append-only log of every tool execution. Each line is a JSON object with timestamp, tool name, input, permission mode, and result summary.' },
      ]
    },
    { name: '.env', type: 'file', desc: 'Your local environment config. Never committed. Copied from .env.personal.example or .env.business.example by the setup wizard. Contains LLM provider keys, variant selection, channel tokens, and JWT secret.' },
    { name: '.env.personal.example', type: 'file', desc: 'Personal variant .env template. Ollama default, auth off, voice and Spotify enabled, single-user.' },
    { name: '.env.business.example', type: 'file', desc: 'Business variant .env template. Anthropic recommended, jwt_secret required, rate limiting on, channel token placeholders with setup instructions.' },
    { name: 'compose.yml', type: 'file', desc: 'Default Docker Compose file. Starts Ollama and Luna. Used for personal variant with local CPU inference.' },
    { name: 'compose.gpu.yml', type: 'file', desc: 'GPU overlay. Extends compose.yml to add NVIDIA runtime and GPU device reservations to the Ollama container.' },
    { name: 'compose.cloud.yml', type: 'file', desc: 'Cloud LLM compose file. Starts only the Luna service (no Ollama container). Used when llm_provider is a cloud provider (anthropic, google, groq, etc.).' },
    { name: 'compose.business.yml', type: 'file', desc: 'Business variant compose file. Forces luna_variant=business, host=0.0.0.0, and rate_limit_enabled=true. Includes a commented nginx block for HTTPS/TLS termination.' },
    { name: 'package.json', type: 'file', desc: 'Root workspace package.json. Defines all npm run scripts (dev, backend, build, docker, etc.) and the luna bin entry for npm link. Lists docs-site as a workspace package.' },
    { name: 'architecture.svg', type: 'file', desc: 'System architecture diagram showing the three-layer structure (Electron → React → FastAPI) and how components connect.' },
  ]
};

// ── Add paths recursively ────────────────────────────────────────────────────
function addPaths(node, parentPath = '') {
  const path = parentPath + node.name;
  node.path = path;
  if (node.children) {
    node.children.forEach(c => addPaths(c, path));
  }
  return node;
}

const TREE = addPaths(RAW_TREE);

// ── Build flat map for O(1) lookup ───────────────────────────────────────────
function buildMap(node, map = {}) {
  map[node.path] = node;
  if (node.children) node.children.forEach(c => buildMap(c, map));
  return map;
}

const NODE_MAP = buildMap(TREE);

// ── FileNode component ────────────────────────────────────────────────────────
function FileNode({ node, depth, selectedPath, onSelect, expanded, onToggle }) {
  const isFolder = node.type === 'folder';
  const isOpen = expanded.has(node.path);
  const isSelected = selectedPath === node.path;

  const handleClick = () => {
    if (isFolder) {
      onToggle(node.path);
      onSelect(node);
    } else {
      onSelect(node);
    }
  };

  return (
    <div>
      <div
        onClick={handleClick}
        style={{
          paddingLeft: depth * 14 + 8,
          paddingRight: 8,
          paddingTop: 3,
          paddingBottom: 3,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          borderRadius: 4,
          background: isSelected ? 'rgba(124,58,237,0.18)' : 'transparent',
          color: isSelected ? '#c4b5fd' : 'inherit',
          fontSize: 13,
          fontFamily: 'monospace',
          userSelect: 'none',
          transition: 'background 0.1s',
          borderLeft: isSelected ? '2px solid #7c3aed' : '2px solid transparent',
        }}
      >
        <span style={{ fontSize: 9, width: 10, flexShrink: 0, opacity: 0.5, fontFamily: 'sans-serif' }}>
          {isFolder ? (isOpen ? '▼' : '▶') : ''}
        </span>
        <span style={{ fontSize: 14, flexShrink: 0 }}>
          {isFolder ? (isOpen ? '📂' : '📁') : fileIcon(node.name)}
        </span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.name}
        </span>
      </div>
      {isFolder && isOpen && node.children && node.children.map(child => (
        <FileNode
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          onSelect={onSelect}
          expanded={expanded}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────
function Breadcrumb({ path }) {
  const parts = path.replace(/\/$/, '').split('/').filter(Boolean);
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 12, opacity: 0.5, marginBottom: 12, letterSpacing: '0.02em' }}>
      {parts.map((p, i) => (
        <span key={i}>
          {i > 0 && <span style={{ margin: '0 3px', opacity: 0.4 }}>/</span>}
          {p}{i < parts.length - 1 ? '/' : ''}
        </span>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ProjectStructure() {
  const [selected, setSelected] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set([
    TREE.path,
    TREE.path + 'backend/',
    TREE.path + 'backend/routers/',
    TREE.path + 'backend/services/',
    TREE.path + 'frontend/',
    TREE.path + 'frontend/src/',
  ]));

  const onSelect = (node) => setSelected(node);

  const onToggle = (path) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  return (
    <DocsLayout
      title="Project Structure"
      description="Interactive file explorer for the Luna monorepo. Click any file to see what it does."
      toc={toc}
    >
      <p>
        Click a file or folder to read its description. Folders expand and collapse on click.
        The tree opens with the main backend and frontend directories pre-expanded.
      </p>

      <section id="explorer">
        <div style={{
          display: 'grid',
          gridTemplateColumns: selected ? '1fr 1fr' : '1fr',
          gap: 0,
          border: '1px solid rgba(124,58,237,0.2)',
          borderRadius: 8,
          overflow: 'hidden',
          minHeight: 480,
        }}>
          {/* Tree panel */}
          <div style={{
            overflowY: 'auto',
            maxHeight: 600,
            padding: '8px 4px',
            borderRight: selected ? '1px solid rgba(124,58,237,0.2)' : 'none',
            background: 'rgba(0,0,0,0.15)',
          }}>
            <FileNode
              node={TREE}
              depth={0}
              selectedPath={selected?.path}
              onSelect={onSelect}
              expanded={expanded}
              onToggle={onToggle}
            />
          </div>

          {/* Detail panel */}
          {selected && (
            <div style={{ padding: '20px 24px', overflowY: 'auto', maxHeight: 600 }}>
              <Breadcrumb path={selected.path} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <span style={{ fontSize: 28 }}>
                  {selected.type === 'folder'
                    ? (expanded.has(selected.path) ? '📂' : '📁')
                    : fileIcon(selected.name)}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: 16, fontWeight: 600 }}>
                  {selected.name}
                </span>
                <span style={{
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 12,
                  background: selected.type === 'folder'
                    ? 'rgba(124,58,237,0.15)'
                    : 'rgba(16,185,129,0.15)',
                  color: selected.type === 'folder' ? '#a78bfa' : '#6ee7b7',
                  fontFamily: 'monospace',
                }}>
                  {selected.type}
                </span>
              </div>
              <p style={{ lineHeight: 1.7, fontSize: 14 }}>{selected.desc}</p>
              {selected.type === 'folder' && selected.children?.length > 0 && (
                <p style={{ fontSize: 12, opacity: 0.5, marginTop: 12 }}>
                  {selected.children.length} {selected.children.length === 1 ? 'item' : 'items'}
                  {' — click to expand'}
                </p>
              )}
            </div>
          )}

          {!selected && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0.3,
              fontSize: 13,
              fontFamily: 'monospace',
              padding: 24,
            }}>
              ← click a file to see its description
            </div>
          )}
        </div>

        <p style={{ marginTop: 12, fontSize: 13, opacity: 0.5 }}>
          Tip: <code>data/</code> is gitignored — never commit it. <code>backend/</code> is Python,
          <code>frontend/</code> is TypeScript.
        </p>
      </section>

      <section id="entry">
        <h2>Key entry points</h2>
        <p>When adding new functionality, these are the files to start with:</p>

        <table>
          <thead><tr><th>File</th><th>What to do here</th></tr></thead>
          <tbody>
            <tr><td><code>backend/main.py</code></td><td>Mount new FastAPI routers.</td></tr>
            <tr><td><code>backend/config.py</code></td><td>Add new .env settings as typed fields.</td></tr>
            <tr><td><code>backend/services/tool_registry.py</code></td><td>Register new tools with a default permission mode.</td></tr>
            <tr><td><code>backend/services/llm.py</code></td><td>Add a new LLM provider streaming generator.</td></tr>
            <tr><td><code>backend/processes/registry.py</code></td><td>Register new background workers.</td></tr>
            <tr><td><code>frontend/src/App.tsx</code></td><td>Add new top-level view modes.</td></tr>
            <tr><td><code>frontend/src/store/index.ts</code></td><td>Add new global state slices and actions.</td></tr>
            <tr><td><code>electron/main.js</code></td><td>Add native menus, IPC handlers, or OS integrations.</td></tr>
            <tr><td><code>cli/luna.mjs</code></td><td>Add new developer CLI subcommands.</td></tr>
          </tbody>
        </table>

        <Callout type="info" title="Where new code belongs">
          <p>Routes go in <code>backend/routers/</code>. Business logic goes in <code>backend/services/</code>.
          Routers should be thin — validate input, call a service, return the result.
          Never put complex logic directly in a router.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/architecture', label: 'Deep dive', title: 'Architecture',    desc: 'How the layers connect and the contribution boundaries between them.' },
        { href: '/contributing', label: 'Community', title: 'Contributing',    desc: 'Where new code belongs and how to write a clean PR.' },
        { href: '/api',          label: 'Platform',  title: 'API reference',   desc: 'Full HTTP endpoint documentation for every router.' },
      ]} />
    </DocsLayout>
  );
}

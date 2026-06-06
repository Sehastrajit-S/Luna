'use strict'

const fs = require('fs')
const http = require('http')
const path = require('path')
const crypto = require('crypto')

let settingsWindow = null

const PUBLIC_KEYS = [
  'luna_variant',
  'user_name',
  'business_name',
  'business_description',
  'business_tone',
  'llm_provider',
  'ollama_base_url',
  'ollama_model',
  'ollama_embed_model',
  'openai_base_url',
  'openai_api_key',
  'openai_model',
  'openai_embed_model',
  'nvidia_nim_base_url',
  'nvidia_nim_api_key',
  'nvidia_nim_model',
  'embedding_provider',
  'anthropic_api_key',
  'anthropic_model',
  'google_api_key',
  'google_model',
  'groq_api_key',
  'groq_model',
  'cohere_api_key',
  'cohere_model',
  'mistral_api_key',
  'mistral_model',
  'spotify_client_id',
  'spotify_client_secret',
  'google_workspace_client_id',
  'google_workspace_client_secret',
  'google_workspace_refresh_token',
  'google_workspace_access_token',
  'microsoft_workspace_client_id',
  'microsoft_workspace_client_secret',
  'microsoft_workspace_tenant_id',
  'microsoft_workspace_refresh_token',
  'microsoft_workspace_access_token',
  'fitbit_client_id',
  'fitbit_client_secret',
  'google_fit_client_id',
  'google_fit_client_secret',
  'oura_api_key',
  'withings_client_id',
  'withings_client_secret',
  'garmin_email',
  'garmin_password',
  'health_webhook_secret',
  'jwt_secret',
  'rate_limit_enabled',
  'rate_limit_per_minute',
  'rate_limit_burst',
  'telegram_bot_token',
  'discord_bot_token',
  'discord_public_key',
  'slack_bot_token',
  'slack_signing_secret',
  'github_token',
  'github_webhook_secret',
  'github_default_repo',
  'github_notify_slack_channel',
  'github_notify_telegram_chat_id',
  'the_news_api',
  'open_weather',
  'alpha_vantage',
  'weather_lat',
  'weather_lon',
  'weather_city',
  'weather_timezone',
]

function envPath(app, root, isDev) {
  return isDev ? path.join(root, '.env') : path.join(app.getPath('userData'), '.env')
}

function parseEnv(text) {
  const out = {}
  for (const raw of String(text || '').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#') || !line.includes('=')) continue
    const i = line.indexOf('=')
    const key = line.slice(0, i).trim()
    let value = line.slice(i + 1).trim()
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    out[key] = value
  }
  return out
}

function readEnv(file) {
  try {
    return parseEnv(fs.readFileSync(file, 'utf8'))
  } catch {
    return {}
  }
}

function serializeEnv(config) {
  const variant = config.luna_variant || 'personal'
  const lines = [
    'app_name=L.U.N.A.',
    'host=127.0.0.1',
    'port=8899',
    'debug=false',
    `luna_variant=${variant}`,
    '',
    '# LLM provider: ollama, openai-compatible, nvidia-nim, anthropic, google, groq, cohere, mistral',
    `llm_provider=${config.llm_provider || 'ollama'}`,
    `embedding_provider=${config.embedding_provider || 'ollama'}`,
    '',
    '# Local Ollama',
    `ollama_base_url=${config.ollama_base_url || 'http://localhost:11434'}`,
    `ollama_model=${config.ollama_model || 'qwen2.5:7b'}`,
    `ollama_embed_model=${config.ollama_embed_model || 'nomic-embed-text'}`,
    '',
    '# OpenAI-compatible APIs',
    `openai_base_url=${config.openai_base_url || 'https://api.openai.com/v1'}`,
    `openai_api_key=${config.openai_api_key || ''}`,
    `openai_model=${config.openai_model || 'gpt-4o-mini'}`,
    `openai_embed_model=${config.openai_embed_model || 'text-embedding-3-small'}`,
    `nvidia_nim_base_url=${config.nvidia_nim_base_url || 'https://integrate.api.nvidia.com/v1'}`,
    `nvidia_nim_api_key=${config.nvidia_nim_api_key || ''}`,
    `nvidia_nim_model=${config.nvidia_nim_model || 'meta/llama-3.1-8b-instruct'}`,
    '',
    '# Native cloud providers',
    `anthropic_api_key=${config.anthropic_api_key || ''}`,
    `anthropic_model=${config.anthropic_model || 'claude-sonnet-4-5'}`,
    `google_api_key=${config.google_api_key || ''}`,
    `google_model=${config.google_model || 'gemini-2.0-flash'}`,
    `groq_api_key=${config.groq_api_key || ''}`,
    `groq_model=${config.groq_model || 'llama-3.3-70b-versatile'}`,
    `cohere_api_key=${config.cohere_api_key || ''}`,
    `cohere_model=${config.cohere_model || 'command-r-plus'}`,
    `mistral_api_key=${config.mistral_api_key || ''}`,
    `mistral_model=${config.mistral_model || 'mistral-large-latest'}`,
    '',
    '# Personal integrations',
    `spotify_client_id=${config.spotify_client_id || ''}`,
    `spotify_client_secret=${config.spotify_client_secret || ''}`,
    '',
    '# Google Workspace (OAuth2)',
    `google_workspace_client_id=${config.google_workspace_client_id || ''}`,
    `google_workspace_client_secret=${config.google_workspace_client_secret || ''}`,
    `google_workspace_refresh_token=${config.google_workspace_refresh_token || ''}`,
    `google_workspace_access_token=${config.google_workspace_access_token || ''}`,
    '',
    '# Microsoft 365 (OAuth2)',
    `microsoft_workspace_client_id=${config.microsoft_workspace_client_id || ''}`,
    `microsoft_workspace_client_secret=${config.microsoft_workspace_client_secret || ''}`,
    `microsoft_workspace_tenant_id=${config.microsoft_workspace_tenant_id || 'common'}`,
    `microsoft_workspace_refresh_token=${config.microsoft_workspace_refresh_token || ''}`,
    `microsoft_workspace_access_token=${config.microsoft_workspace_access_token || ''}`,
    '',
    '# Health platforms',
    `fitbit_client_id=${config.fitbit_client_id || ''}`,
    `fitbit_client_secret=${config.fitbit_client_secret || ''}`,
    `google_fit_client_id=${config.google_fit_client_id || ''}`,
    `google_fit_client_secret=${config.google_fit_client_secret || ''}`,
    `oura_api_key=${config.oura_api_key || ''}`,
    `withings_client_id=${config.withings_client_id || ''}`,
    `withings_client_secret=${config.withings_client_secret || ''}`,
    `garmin_email=${config.garmin_email || ''}`,
    `garmin_password=${config.garmin_password || ''}`,
    `health_webhook_secret=${config.health_webhook_secret || ''}`,
    '',
    '# Business / production',
    `jwt_secret=${config.jwt_secret || ''}`,
    `rate_limit_enabled=${config.rate_limit_enabled || (variant === 'business' ? 'true' : 'false')}`,
    `rate_limit_per_minute=${config.rate_limit_per_minute || '60'}`,
    `rate_limit_burst=${config.rate_limit_burst || '20'}`,
    `business_name=${config.business_name || ''}`,
    `business_description=${config.business_description || ''}`,
    `business_tone=${config.business_tone || 'professional'}`,
    '',
    '# Messaging and developer channels',
    `telegram_bot_token=${config.telegram_bot_token || ''}`,
    `discord_bot_token=${config.discord_bot_token || ''}`,
    `discord_public_key=${config.discord_public_key || ''}`,
    `slack_bot_token=${config.slack_bot_token || ''}`,
    `slack_signing_secret=${config.slack_signing_secret || ''}`,
    `github_token=${config.github_token || ''}`,
    `github_webhook_secret=${config.github_webhook_secret || ''}`,
    `github_default_repo=${config.github_default_repo || ''}`,
    `github_notify_slack_channel=${config.github_notify_slack_channel || ''}`,
    `github_notify_telegram_chat_id=${config.github_notify_telegram_chat_id || ''}`,
    '',
    '# External data',
    `the_news_api=${config.the_news_api || ''}`,
    `open_weather=${config.open_weather || ''}`,
    `alpha_vantage=${config.alpha_vantage || ''}`,
    `weather_lat=${config.weather_lat || '40.7128'}`,
    `weather_lon=${config.weather_lon || '-74.0060'}`,
    `weather_city=${config.weather_city || 'New York'}`,
    `weather_timezone=${config.weather_timezone || 'America/New_York'}`,
    '',
    '# Persona',
    `luna_name=${config.luna_name || 'L.U.N.A.'}`,
    `user_name=${config.user_name || 'friend'}`,
    '',
  ]
  return lines.join('\n')
}

function writeEnv(file, next) {
  const current = readEnv(file)
  const config = { ...current }
  for (const key of PUBLIC_KEYS) {
    if (Object.prototype.hasOwnProperty.call(next, key)) {
      config[key] = String(next[key] ?? '').trim()
    }
  }
  if (config.luna_variant === 'business' && !config.jwt_secret) {
    config.jwt_secret = crypto.randomBytes(32).toString('hex')
  }
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, serializeEnv(config), 'utf8')
  return config
}

function envForBackend(file) {
  return readEnv(file)
}

function needsFirstRunConfig(file) {
  const env = readEnv(file)
  return !env.luna_variant || !env.llm_provider
}

// Inline logo — no file read needed; crescent uses clip-path so url() refs work in data: URLs
const LOGO_SVG = `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M21 8C10.5 8 2 16.5 2 27C2 37.5 10.5 46 21 46C27.2 46 32.7 43.1 36.3 38.6C33.5 39.7 30.3 40.1 27 39.3C17.1 36.8 11.2 26.6 13.8 16.7C15.7 9.7 18.3 8 21 8Z" fill="#8b5cf6"/>
  <ellipse cx="26" cy="22" rx="21" ry="8" stroke="#a78bfa" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="3 4" opacity="0.45" transform="rotate(-28 26 22)"/>
  <circle cx="40" cy="9" r="1.8" fill="#ddd6fe" opacity="0.85"/>
  <circle cx="7" cy="8" r="1.1" fill="#c4b5fd" opacity="0.65"/>
  <circle cx="43" cy="34" r="1.1" fill="#c4b5fd" opacity="0.5"/>
</svg>`

function html(mode) {
  const firstRun = mode === 'first-run'
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>L.U.N.A. Setup</title>
  <style>
    *{box-sizing:border-box} body{margin:0;background:#09090f;color:#eef2ff;font-family:Inter,Segoe UI,Arial,sans-serif}
    .shell{height:100vh;display:grid;grid-template-columns:260px 1fr}
    aside{background:#11111a;border-right:1px solid #27273a;padding:28px 22px}
    aside svg{width:58px;height:58px;margin-bottom:16px;display:block}
    main{overflow:auto;padding:28px 34px 96px}
    h1{font-size:22px;margin:0 0 10px} h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#a78bfa;margin:28px 0 12px}
    p{color:#9ca3af;font-size:13px;line-height:1.5}
    .brand{font-weight:800;letter-spacing:.18em;font-size:22px;margin-bottom:8px}
    .pill{display:inline-flex;border:1px solid #373753;border-radius:8px;overflow:hidden;margin:18px 0;width:100%}
    .pill button{flex:1;background:#151522;color:#9ca3af;border:0;padding:12px;cursor:pointer;font-weight:700}
    .pill button.active{background:#6d28d9;color:white}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
    .field{display:flex;flex-direction:column;gap:7px}
    label{font-size:11px;color:#c4b5fd;text-transform:uppercase;letter-spacing:.08em}
    input,select,textarea{width:100%;background:#151522;border:1px solid #303049;color:#f8fafc;border-radius:8px;padding:10px 11px;outline:none}
    textarea{min-height:74px;resize:vertical}.wide{grid-column:1 / -1}.hint{font-size:11px;color:#7c8194;margin-top:6px}
    .footer{position:fixed;right:0;bottom:0;left:260px;background:rgba(9,9,15,.92);border-top:1px solid #27273a;padding:14px 34px;display:flex;justify-content:space-between;gap:12px}
    .primary,.secondary{border:0;border-radius:8px;padding:10px 16px;font-weight:800;cursor:pointer}
    .primary{background:#7c3aed;color:white}.secondary{background:#1f2030;color:#d1d5db}
    .status{font-size:12px;color:#a7f3d0;align-self:center}.hidden{display:none}
    body.first-run .settings-only, body.first-run #personalSection, body.first-run #channelsSection{display:none}
    body.first-run .provider-field{display:none}
    body.first-run .provider-field.active{display:flex}
  </style>
</head>
<body class="${firstRun ? 'first-run' : 'settings'}">
  <div class="shell">
    <aside>
      ${LOGO_SVG}
      <div class="brand">L.U.N.A.</div>
      <p>${firstRun ? 'Choose Personal or Business and set the basics. You can add keys later inside Luna.' : 'Update desktop runtime settings and credentials.'}</p>
      <div class="pill">
        <button id="personalBtn" type="button">Personal</button>
        <button id="businessBtn" type="button">Business</button>
      </div>
      <p id="variantHelp"></p>
    </aside>
    <main>
      <h1>${mode === 'first-run' ? 'First-run setup' : 'Settings'}</h1>
      <p>${firstRun ? 'Personal setup only needs the basics. Spotify, GitHub, Slack, Discord, weather, and other credentials can be added later from Settings.' : 'Secrets are stored in your local Luna environment file. Restart Luna after changing provider, auth, or channel settings.'}</p>

      <h2>Required</h2>
      <div class="grid">
        <div class="field"><label>User name</label><input id="user_name" placeholder="friend"></div>
        <div class="field"><label>Model provider</label><select id="llm_provider">
          <option value="ollama">Ollama local</option>
          <option value="openai-compatible">OpenAI-compatible</option>
          <option value="nvidia-nim">NVIDIA NIM</option>
          <option value="anthropic">Anthropic</option>
          <option value="google">Google Gemini</option>
          <option value="groq">Groq</option>
          <option value="cohere">Cohere</option>
          <option value="mistral">Mistral</option>
        </select></div>
      </div>

      <h2>Model details</h2>
      <div class="grid">
        <div class="field provider-field" data-provider="ollama"><label>Ollama base URL</label><input id="ollama_base_url" placeholder="http://localhost:11434"></div>
        <div class="field provider-field" data-provider="ollama"><label>Ollama chat model</label><input id="ollama_model" placeholder="qwen2.5:7b"></div>
        <div class="field settings-only"><label>Embedding provider</label><select id="embedding_provider"><option value="ollama">Ollama</option><option value="openai-compatible">OpenAI-compatible</option></select></div>
        <div class="field settings-only"><label>Ollama embed model</label><input id="ollama_embed_model" placeholder="nomic-embed-text"></div>
      </div>

      <section id="advancedProviderSection">
      <h2 class="settings-only">Cloud / compatible providers</h2>
      <div class="grid">
        <div class="field provider-field" data-provider="openai-compatible"><label>Base URL</label><input id="openai_base_url" placeholder="https://api.openai.com/v1"></div>
        <div class="field provider-field" data-provider="openai-compatible"><label>API key</label><input id="openai_api_key" type="password"></div>
        <div class="field provider-field" data-provider="openai-compatible"><label>Model</label><input id="openai_model" placeholder="gpt-4o-mini"></div>
        <div class="field settings-only"><label>OpenAI embed model</label><input id="openai_embed_model" placeholder="text-embedding-3-small"></div>
        <div class="field provider-field" data-provider="nvidia-nim"><label>NVIDIA NIM base URL</label><input id="nvidia_nim_base_url" placeholder="https://integrate.api.nvidia.com/v1"></div>
        <div class="field provider-field" data-provider="nvidia-nim"><label>NVIDIA NIM API key</label><input id="nvidia_nim_api_key" type="password"></div>
        <div class="field provider-field" data-provider="nvidia-nim"><label>NVIDIA NIM model</label><input id="nvidia_nim_model" placeholder="meta/llama-3.1-8b-instruct"></div>
        <div class="field provider-field" data-provider="anthropic"><label>Anthropic key</label><input id="anthropic_api_key" type="password"></div>
        <div class="field provider-field" data-provider="anthropic"><label>Anthropic model</label><input id="anthropic_model" placeholder="claude-sonnet-4-5"></div>
        <div class="field provider-field" data-provider="google"><label>Google key</label><input id="google_api_key" type="password"></div>
        <div class="field provider-field" data-provider="google"><label>Google model</label><input id="google_model" placeholder="gemini-2.0-flash"></div>
        <div class="field provider-field" data-provider="groq"><label>Groq key</label><input id="groq_api_key" type="password"></div>
        <div class="field provider-field" data-provider="groq"><label>Groq model</label><input id="groq_model" placeholder="llama-3.3-70b-versatile"></div>
        <div class="field provider-field" data-provider="cohere"><label>Cohere key</label><input id="cohere_api_key" type="password"></div>
        <div class="field provider-field" data-provider="cohere"><label>Cohere model</label><input id="cohere_model" placeholder="command-r-plus"></div>
        <div class="field provider-field" data-provider="mistral"><label>Mistral key</label><input id="mistral_api_key" type="password"></div>
        <div class="field provider-field" data-provider="mistral"><label>Mistral model</label><input id="mistral_model" placeholder="mistral-large-latest"></div>
      </div>
      </section>

      <section id="personalSection" class="advanced">
        <h2>Personal integrations</h2>
        <div class="grid">
          <div class="field"><label>Spotify client ID</label><input id="spotify_client_id"></div>
          <div class="field"><label>Spotify client secret</label><input id="spotify_client_secret" type="password"></div>
        </div>
      </section>

      <section id="businessSection">
        <h2>Business</h2>
        <div class="grid">
          <div class="field"><label>Business name</label><input id="business_name"></div>
          <div class="field"><label>Business tone</label><select id="business_tone"><option>professional</option><option>friendly</option><option>technical</option><option>concise</option></select></div>
          <div class="field wide"><label>Business description</label><textarea id="business_description"></textarea></div>
          <div class="field wide"><label>JWT secret</label><input id="jwt_secret" type="password" placeholder="Auto-generated if blank"></div>
          <div class="field"><label>Rate limiting</label><select id="rate_limit_enabled"><option value="false">Off</option><option value="true">On</option></select></div>
          <div class="field"><label>Requests per minute</label><input id="rate_limit_per_minute" placeholder="60"></div>
        </div>
      </section>

      <section id="channelsSection" class="advanced">
      <h2>Channels and APIs</h2>
      <div class="grid">
        <div class="field"><label>Telegram bot token</label><input id="telegram_bot_token" type="password"></div>
        <div class="field"><label>Discord bot token</label><input id="discord_bot_token" type="password"></div>
        <div class="field"><label>Discord public key</label><input id="discord_public_key"></div>
        <div class="field"><label>Slack bot token</label><input id="slack_bot_token" type="password"></div>
        <div class="field"><label>Slack signing secret</label><input id="slack_signing_secret" type="password"></div>
        <div class="field"><label>GitHub token</label><input id="github_token" type="password"></div>
        <div class="field"><label>GitHub default repo</label><input id="github_default_repo" placeholder="owner/repo"></div>
        <div class="field"><label>GitHub webhook secret</label><input id="github_webhook_secret" type="password"></div>
        <div class="field"><label>News API key</label><input id="the_news_api" type="password"></div>
        <div class="field"><label>OpenWeather key</label><input id="open_weather" type="password"></div>
        <div class="field"><label>Alpha Vantage key</label><input id="alpha_vantage" type="password"></div>
        <div class="field"><label>Weather city</label><input id="weather_city" placeholder="New York"></div>
      </div>
      </section>
    </main>
    <div class="footer">
      <div id="status" class="status"></div>
      <div>
        <button class="secondary" id="cancelBtn">Cancel</button>
        <button class="primary" id="saveBtn">${mode === 'first-run' ? 'Save and start Luna' : 'Save settings'}</button>
      </div>
    </div>
  </div>
  <script>
    const keys = ${JSON.stringify(PUBLIC_KEYS)}
    const firstRun = ${JSON.stringify(firstRun)}
    const firstRunKeys = ['user_name', 'llm_provider', 'embedding_provider', 'ollama_base_url', 'ollama_model', 'ollama_embed_model']
    const businessFirstRunKeys = ['business_name', 'business_description', 'business_tone', 'jwt_secret', 'rate_limit_enabled', 'rate_limit_per_minute']
    const providerKeys = {
      'ollama': ['ollama_base_url', 'ollama_model', 'embedding_provider', 'ollama_embed_model'],
      'openai-compatible': ['openai_base_url', 'openai_api_key', 'openai_model', 'embedding_provider', 'openai_embed_model'],
      'nvidia-nim': ['nvidia_nim_base_url', 'nvidia_nim_api_key', 'nvidia_nim_model', 'embedding_provider'],
      'anthropic': ['anthropic_api_key', 'anthropic_model'],
      'google': ['google_api_key', 'google_model'],
      'groq': ['groq_api_key', 'groq_model'],
      'cohere': ['cohere_api_key', 'cohere_model'],
      'mistral': ['mistral_api_key', 'mistral_model'],
    }
    let variant = 'personal'
    const el = id => document.getElementById(id)
    const setProvider = provider => {
      for (const field of document.querySelectorAll('.provider-field')) {
        field.classList.toggle('active', !firstRun || field.dataset.provider === provider)
      }
      if (firstRun) {
        el('embedding_provider').value = provider === 'ollama' ? 'ollama' : 'openai-compatible'
      }
    }
    const setVariant = v => {
      variant = v
      el('personalBtn').classList.toggle('active', v === 'personal')
      el('businessBtn').classList.toggle('active', v === 'business')
      el('personalSection').classList.toggle('hidden', v !== 'personal')
      el('businessSection').classList.toggle('hidden', v !== 'business')
      el('variantHelp').textContent = v === 'personal'
        ? 'Personal starts with local desktop controls, chat, memory, and voice. Add optional integrations later from Settings.'
        : 'Business starts with production auth, rate limiting, team channels, and professional assistant behavior.'
      if (v === 'business' && !el('rate_limit_enabled').value) el('rate_limit_enabled').value = 'true'
    }
    el('personalBtn').onclick = () => setVariant('personal')
    el('businessBtn').onclick = () => setVariant('business')
    el('llm_provider').onchange = event => setProvider(event.target.value)
    window.lunaSetup.get().then(({ config }) => {
      for (const key of keys) if (el(key) && config[key] != null) el(key).value = config[key]
      setVariant(config.luna_variant || 'personal')
      setProvider(el('llm_provider').value || 'ollama')
    })
    el('saveBtn').onclick = async () => {
      const config = { luna_variant: variant }
      const keysToSave = firstRun
        ? ['user_name', 'llm_provider'].concat(providerKeys[el('llm_provider').value] || [], variant === 'business' ? businessFirstRunKeys : [])
        : keys
      for (const key of keysToSave) if (el(key)) config[key] = el(key).value
      config.luna_variant = variant
      const res = await window.lunaSetup.save(config)
      el('status').textContent = res.ok ? 'Saved. Restart Luna if the backend is already running.' : (res.error || 'Could not save')
      if (res.ok && '${mode}' === 'first-run') window.close()
    }
    el('cancelBtn').onclick = () => window.close()
  </script>
</body>
</html>`
}

function openSettingsWindow({ BrowserWindow, ipcMain, app, root, isDev, parent = null, mode = 'settings' }) {
  if (settingsWindow && !settingsWindow.isDestroyed()) {
    settingsWindow.focus()
    return settingsWindow
  }
  const file = envPath(app, root, isDev)
  settingsWindow = new BrowserWindow({
    width: 980,
    height: 760,
    minWidth: 840,
    minHeight: 620,
    title: mode === 'first-run' ? 'L.U.N.A. Setup' : 'L.U.N.A. Settings',
    parent: parent || undefined,
    modal: mode === 'first-run',
    backgroundColor: '#09090f',
    webPreferences: {
      preload: path.join(__dirname, 'settingsPreload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  settingsWindow.setMenuBarVisibility(false)

  ipcMain.removeHandler('setup:get')
  ipcMain.removeHandler('setup:save')
  ipcMain.handle('setup:get', () => ({ config: readEnv(file), path: file }))
  ipcMain.handle('setup:save', (_event, config) => {
    try {
      writeEnv(file, config || {})
      const reloadReq = http.request('http://127.0.0.1:8899/api/system/config/reload', { method: 'POST' }, res => res.resume())
      reloadReq.on('error', () => {})
      reloadReq.end()
      return { ok: true }
    } catch (error) {
      return { ok: false, error: String(error?.message || error) }
    }
  })

  settingsWindow.on('closed', () => { settingsWindow = null })
  settingsWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html(mode))}`)
  return settingsWindow
}

function waitForSettingsClosed(win) {
  return new Promise(resolve => {
    if (!win || win.isDestroyed()) { resolve(); return }
    win.on('closed', resolve)
  })
}

module.exports = {
  envPath,
  envForBackend,
  needsFirstRunConfig,
  openSettingsWindow,
  waitForSettingsClosed,
  readEnv,
  writeEnv,
}

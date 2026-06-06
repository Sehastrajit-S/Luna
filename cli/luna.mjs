#!/usr/bin/env node
/**
 * L.U.N.A. CLI
 *
 * Install globally:  npm install -g .   (run once from project root)
 * Then use:          luna <command>
 *
 * Without global install:  npm run luna -- <command>
 */

import { spawn, spawnSync, execSync } from 'node:child_process'
import { existsSync, rmSync, copyFileSync, readFileSync } from 'node:fs'
import { tmpdir, platform } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { createInterface } from 'node:readline/promises'
import { stdin as input, stdout as output } from 'node:process'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root      = resolve(__dirname, '..')
const isWin     = platform() === 'win32'

// ── Colours ───────────────────────────────────────────────────────────────────
const c = {
  reset: '\x1b[0m', bold: '\x1b[1m', dim: '\x1b[2m',
  cyan: '\x1b[36m', green: '\x1b[32m', yellow: '\x1b[33m',
  red: '\x1b[31m', purple: '\x1b[35m', blue: '\x1b[34m',
}
const ok   = m => console.log(`${c.green}  ✓${c.reset} ${m}`)
const warn = m => console.log(`${c.yellow}  !${c.reset} ${m}`)
const err  = m => console.error(`${c.red}  ✗${c.reset} ${m}`)
const head = m => console.log(`\n${c.bold}${c.purple}  ${m}${c.reset}`)
const info = m => console.log(`${c.cyan}  ▸${c.reset} ${m}`)

// ── Command registry ──────────────────────────────────────────────────────────
const COMMANDS = {
  // ── Setup ──
  setup: {
    group: 'Setup',
    summary: 'Auto-install deps, create .env, pull Ollama models',
    run: setup,
  },
  install: {
    group: 'Setup',
    summary: 'Install Node and Python dependencies',
    run: install,
  },

  // ── Development ──
  dev: {
    group: 'Dev',
    summary: 'Start Vite + Electron for desktop development',
    run: () => npm(['run', 'dev', ...rest]),
  },
  'dev:lan': {
    group: 'Dev',
    summary: 'Start dev mode with Vite exposed on your LAN',
    run: () => npm(['run', 'dev:lan', ...rest]),
  },
  web: {
    group: 'Dev',
    summary: 'Start backend + browser UI without Electron',
    run: () => npm(['run', 'web', ...rest]),
  },
  'web:lan': {
    group: 'Dev',
    summary: 'Start browser UI on your LAN for phones and tablets',
    run: () => npm(['run', 'web:lan', ...rest]),
  },
  backend: {
    group: 'Dev',
    summary: 'Start only the FastAPI backend',
    run: () => python(['backend/server.py', ...rest]),
  },
  frontend: {
    group: 'Dev',
    summary: 'Start only the Vite dev server',
    run: () => npm(['run', 'dev', '--workspace=frontend', ...rest]),
  },
  electron: {
    group: 'Dev',
    summary: 'Start only the Electron shell',
    run: () => npm(['start', '--workspace=electron', ...rest]),
  },

  // ── Docker ──
  docker: {
    group: 'Docker',
    summary: 'Build + start with Docker (auto-detects CPU / GPU / cloud)',
    run: () => node(['scripts/docker.mjs', ...rest]),
  },
  'docker:gpu': {
    group: 'Docker',
    summary: 'Force GPU mode (NVIDIA)',
    run: () => node(['scripts/docker.mjs', '--gpu', ...rest]),
  },
  'docker:cloud': {
    group: 'Docker',
    summary: 'Cloud LLM mode (no Ollama)',
    run: () => node(['scripts/docker.mjs', '--cloud', ...rest]),
  },
  'docker:down': {
    group: 'Docker',
    summary: 'Stop all Docker containers',
    run: () => node(['scripts/docker.mjs', '--down']),
  },
  'docker:logs': {
    group: 'Docker',
    summary: 'Tail Docker logs for the luna container',
    run: () => node(['scripts/docker.mjs', '--logs']),
  },
  'docker:pull': {
    group: 'Docker',
    summary: 'Re-pull Ollama models (run after changing ollama_model in .env)',
    run: () => node(['scripts/docker.mjs', '--pull']),
  },
  'docker:business': {
    group: 'Docker',
    summary: 'Start business variant (rate limiting, JWT, professional mode)',
    run: () => node(['scripts/docker.mjs', '--business', ...rest]),
  },

  // ── Build ──
  build: {
    group: 'Build',
    summary: 'Build the React frontend',
    run: () => npm(['run', 'build', ...rest]),
  },
  dist: {
    group: 'Build',
    summary: 'Build frontend + package Electron for Windows',
    run: () => npm(['run', 'dist', ...rest]),
  },

  // ── Diagnostics ──
  doctor: {
    group: 'Diagnostics',
    summary: 'Check Node, Python, Ollama, and Docker availability',
    run: doctor,
  },
  check: {
    group: 'Diagnostics',
    summary: 'Run backend syntax checks (py_compile)',
    run: check,
  },
  processes: {
    group: 'Diagnostics',
    summary: 'List registered background processes',
    run: () => python(['-c',
      'from backend.processes.registry import list_processes; import json; print(json.dumps(list_processes(), indent=2))',
    ]),
  },
  health: {
    group: 'Diagnostics',
    summary: 'Check if the running Luna backend is healthy',
    run: healthCheck,
  },

  // ── Docs ──
  chat: {
    group: 'Chat',
    summary: 'Interactive terminal chat with the running Luna backend',
    run: () => chatCli(rest),
  },

  docs: {
    group: 'Docs',
    summary: 'Start the docs site (Next.js dev server)',
    run: () => npm(['--prefix', 'docs-site', 'run', 'dev']),
  },

  // ── Utility ──
  clean: {
    group: 'Utility',
    summary: 'Remove build artifacts and runtime data',
    run: clean,
  },
  tunnel: {
    group: 'Utility',
    summary: 'Expose local Vite dev server via Cloudflare tunnel',
    run: () => npm(['run', 'tunnel', ...rest]),
  },
  help: {
    group: 'Utility',
    summary: 'Show this help',
    run: () => help(),
  },
}

const command = process.argv[2] ?? 'help'
const rest    = process.argv.slice(3)

if (!COMMANDS[command]) {
  err(`Unknown command: ${command}\n`)
  help(1)
} else {
  COMMANDS[command].run()
}

// ── Help ──────────────────────────────────────────────────────────────────────
function help(exitCode = 0) {
  console.log(`\n${c.bold}${c.purple}  L.U.N.A. CLI${c.reset}`)
  console.log(`  ${c.dim}Large Unified Nexus Mind AI${c.reset}\n`)
  console.log(`  ${c.bold}Usage:${c.reset}  luna <command>`)
  console.log(`          npm run luna -- <command>\n`)

  const groups = [...new Set(Object.values(COMMANDS).map(v => v.group))]
  for (const group of groups) {
    console.log(`  ${c.bold}${c.cyan}${group}${c.reset}`)
    for (const [name, meta] of Object.entries(COMMANDS)) {
      if (meta.group !== group) continue
      console.log(`    ${c.bold}${name.padEnd(16)}${c.reset}${c.dim}${meta.summary}${c.reset}`)
    }
    console.log()
  }
  process.exit(exitCode)
}

// ── Runners ───────────────────────────────────────────────────────────────────
function npm(args)  { run(isWin ? 'npm.cmd' : 'npm', args) }
function python(args) { run(isWin ? 'python' : 'python3', args) }
function node(args) { run(process.execPath, args) }

function run(bin, args) {
  const child = spawn(bin, args, {
    cwd: root,
    stdio: 'inherit',
    shell: isWin && bin.endsWith('.cmd'),
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: '1',
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    },
  })
  child.on('exit', code => process.exit(code ?? 0))
  child.on('error', e => { err(e.message); process.exit(1) })
}

function quiet(cmd) {
  try { return execSync(cmd, { cwd: root, stdio: 'pipe' }).toString().trim() }
  catch { return '' }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
async function setup() {
  console.log(`\n${c.bold}${c.purple}  ██╗     ██╗   ██╗███╗   ██╗ █████╗ ${c.reset}`)
  console.log(`${c.bold}${c.purple}  ███████╗╚██████╔╝██║ ╚████║██║  ██║${c.reset}`)
  console.log(`  ${c.dim}Large Unified Nexus Mind AI — setup${c.reset}\n`)

  const rl = createInterface({ input, output })

  // ── Variant selection ────────────────────────────────────────────────────────
  head('Choose your variant')
  console.log()
  console.log(`  ${c.bold}${c.cyan}1. Personal${c.reset}`)
  console.log(`     ${c.dim}Voice, vision, desktop automation, Spotify, maps.${c.reset}`)
  console.log(`     ${c.dim}Casual AI companion. Single user. No auth required.${c.reset}`)
  console.log()
  console.log(`  ${c.bold}${c.cyan}2. Business${c.reset}`)
  console.log(`     ${c.dim}Professional team assistant. Multi-user JWT auth.${c.reset}`)
  console.log(`     ${c.dim}Rate limiting, Slack/Telegram/Discord channels.${c.reset}`)
  console.log()

  const variantAnswer = await rl.question('  Enter 1 or 2 (default: 1): ')
  const variant = variantAnswer.trim() === '2' ? 'business' : 'personal'
  ok(`Variant: ${variant}`)

  // ── .env ────────────────────────────────────────────────────────────────────
  head('Configuration...')
  const envPath = join(root, '.env')
  if (!existsSync(envPath)) {
    const templateName = variant === 'business' ? '.env.business.example' : '.env.personal.example'
    const ex = join(root, templateName)
    const fallback = join(root, '.env.example')
    const src = existsSync(ex) ? ex : fallback
    if (!existsSync(src)) { err('.env example not found.'); rl.close(); process.exit(1) }
    copyFileSync(src, envPath)
    ok(`Created .env from ${src.replace(root, '.')}`)
    if (variant === 'business') {
      warn('Edit .env — set jwt_secret, business_name, and your LLM provider key.')
    } else {
      warn('Edit .env — set your model name and location before running Luna.')
    }
  } else {
    ok('.env exists')
  }

  // ── Node deps ────────────────────────────────────────────────────────────────
  head('Installing Node dependencies...')
  runSync(isWin ? 'npm.cmd' : 'npm', ['install'])
  runSync(isWin ? 'npm.cmd' : 'npm', ['install', '--prefix', 'frontend'])
  ok('Node dependencies installed')

  // ── Python venv ───────────────────────────────────────────────────────────────
  head('Setting up Python virtual environment...')
  const venvPath = join(root, '.venv')
  if (!existsSync(venvPath)) {
    runSync(isWin ? 'python' : 'python3', ['-m', 'venv', '.venv'])
    ok('Created .venv')
  } else {
    ok('.venv already exists')
  }

  const pip = isWin
    ? join(root, '.venv', 'Scripts', 'pip.exe')
    : join(root, '.venv', 'bin', 'pip')

  runSync(pip, ['install', '--upgrade', 'pip', '--quiet'])
  runSync(pip, ['install', '-r', 'backend/requirements.txt', '--quiet'])
  ok('Python dependencies installed')

  // ── Ollama models (personal only — business typically uses cloud) ─────────────
  const envVars = readEnvFile()
  const llmProvider = envVars.llm_provider || 'ollama'

  if (llmProvider === 'ollama') {
    head('Pulling Ollama models...')
    const chatModel  = envVars.ollama_model       || 'qwen2.5:7b'
    const embedModel = envVars.ollama_embed_model || 'nomic-embed-text'
    if (quiet('ollama --version')) {
      for (const model of [chatModel, embedModel]) {
        info(`Pulling ${model}...`)
        runSync('ollama', ['pull', model])
        ok(model)
      }
    } else {
      warn('Ollama not found — install it from https://ollama.com/ and pull models manually:')
      warn(`  ollama pull ${chatModel}`)
      warn(`  ollama pull ${embedModel}`)
    }
  } else {
    info(`LLM provider: ${llmProvider} — skipping Ollama model pull.`)
  }

  rl.close()

  console.log(`\n${c.bold}${c.green}  Setup complete! (${variant} variant)${c.reset}\n`)

  if (variant === 'business') {
    console.log(`  ${c.bold}Next steps:${c.reset}`)
    console.log(`    1. Edit ${c.cyan}.env${c.reset} — set ${c.bold}jwt_secret${c.reset}, ${c.bold}business_name${c.reset}`)
    console.log(`    2. Add your LLM API key (anthropic_api_key, groq_api_key, etc.)`)
    console.log(`    3. Configure Slack / Telegram tokens for team messaging`)
    console.log()
    console.log(`  Start:  ${c.cyan}luna docker:business${c.reset}  (Docker, recommended)`)
    console.log(`          ${c.cyan}luna backend${c.reset}           (local API only)`)
    console.log()
    console.log(`  Admin:  ${c.cyan}POST /api/admin/users${c.reset} to create per-user JWT tokens`)
  } else {
    console.log(`  Start Luna:  ${c.cyan}luna dev${c.reset}       (desktop with Electron)`)
    console.log(`               ${c.cyan}luna docker${c.reset}    (any device via Docker)`)
    console.log(`               ${c.cyan}luna backend${c.reset}   (API only)`)
  }
  console.log()
}

// ── Install (deps only) ───────────────────────────────────────────────────────
function install() {
  head('Installing Node dependencies...')
  runSync(isWin ? 'npm.cmd' : 'npm', ['install'])
  runSync(isWin ? 'npm.cmd' : 'npm', ['install', '--prefix', 'frontend'])
  ok('Node done')

  const pip = isWin
    ? join(root, '.venv', 'Scripts', 'pip.exe')
    : join(root, '.venv', 'bin', 'pip')

  if (existsSync(pip)) {
    head('Installing Python dependencies...')
    runSync(pip, ['install', '-r', 'backend/requirements.txt', '--quiet'])
    ok('Python done')
  } else {
    warn('No .venv found — run: luna setup')
  }
}

// ── Health check ──────────────────────────────────────────────────────────────
async function healthCheck() {
  const env  = readEnvFile()
  const port = env.port || '8899'
  const url  = `http://localhost:${port}/api/system/health`
  info(`GET ${url}`)
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const body = await r.json()
    if (r.ok) { ok(`Healthy — ${JSON.stringify(body)}`); process.exit(0) }
    else      { err(`Unhealthy ${r.status} — ${JSON.stringify(body)}`); process.exit(1) }
  } catch (e) {
    err(`Not reachable: ${e.message}`)
    process.exit(1)
  }
}

// ── Doctor ────────────────────────────────────────────────────────────────────
async function chatCli(args = []) {
  const env = readEnvFile()
  const port = env.port || '8899'
  const baseUrl = process.env.LUNA_URL || env.luna_url || `http://localhost:${port}`
  let conversationId = null
  const approveAll = args.includes('--yes') || args.includes('-y')
  const denyAll = args.includes('--no')
  const firstMessage = args.filter(a => !['--yes', '-y', '--no'].includes(a)).join(' ').trim()

  console.log(`${c.bold}
  ██╗     ██╗   ██╗███╗   ██╗ █████╗
  ██║     ██║   ██║████╗  ██║██╔══██╗
  ██║     ██║   ██║██╔██╗ ██║███████║
  ██║     ██║   ██║██║╚██╗██║██╔══██║
  ███████╗╚██████╔╝██║ ╚████║██║  ██║
  ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
${c.reset}  Large Unified Nexus Mind AI
`)
  console.log(`  ${c.dim}${baseUrl}${c.reset}`)
  console.log(`  ${c.dim}Type /exit or press Ctrl+C to quit. Type /new for a new conversation. Type /help for CLI commands.${c.reset}\n`)

  // ── Start a local backend unless an existing one could not be stopped ───────
  let _backendProc = null
  let _usingExistingBackend = false
  const isBackendUp = async () => {
    try {
      const r = await fetch(`${baseUrl}/api/system/health`, { signal: AbortSignal.timeout(1500) })
      return r.ok
    } catch { return false }
  }

  // Kill any running backend on this port so we always load the latest code
  if (await isBackendUp()) {
    try {
      await fetch(`${baseUrl}/api/system/shutdown`, { method: 'POST', signal: AbortSignal.timeout(1000) })
    } catch {}
    // Give it a moment to die, then force-kill via port if still up
    await new Promise(r => setTimeout(r, 800))
    if (await isBackendUp()) {
      if (isWin) {
        spawnSync('cmd', ['/c', `for /f "tokens=5" %a in ('netstat -ano ^| findstr :${port} ^| findstr LISTENING') do taskkill /F /PID %a`], { shell: false })
      } else {
        spawnSync('sh', ['-c', `lsof -ti:${port} | xargs kill -9 2>/dev/null`], { shell: false })
      }
      await new Promise(r => setTimeout(r, 400))
    }
    if (await isBackendUp()) {
      warn(`A Luna backend is already running on ${baseUrl}; using it instead of starting another one.`)
      warn('If this is Docker and you need desktop controls, run `npm run docker:down` first, then `luna chat`.')
      _usingExistingBackend = true
    }
  }

  if (!_usingExistingBackend) {
    info('Starting backend...')
    const py = isWin ? 'python' : 'python3'
    _backendProc = spawn(py, ['backend/server.py'], {
      cwd: root,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      detached: false,
    })
    _backendProc.on('error', e => { err(`Backend failed to start: ${e.message}`); process.exit(1) })
    // Wait up to 20 s for the backend to be ready
    let attempts = 0
    while (attempts < 40) {
      await new Promise(r => setTimeout(r, 500))
      if (await isBackendUp()) break
      attempts++
      if (attempts % 6 === 0) process.stdout.write('.')
    }
    process.stdout.write('\n')
    if (!(await isBackendUp())) {
      err('Backend did not start in time. Run `luna backend` to see error output.')
      process.exit(1)
    }
    ok('Backend ready')

    // Kill backend when chat exits
    const cleanup = () => { try { _backendProc.kill() } catch {} }
    process.on('exit', cleanup)
    process.on('SIGINT', () => { cleanup(); process.exit(0) })
    process.on('SIGTERM', () => { cleanup(); process.exit(0) })
  }

  conversationId = await getSharedConversation()
  if (conversationId) info(`Resuming shared conversation #${conversationId}`)

  async function getSharedConversation() {
    try {
      const r = await fetch(`${baseUrl}/api/chat/context`, { signal: AbortSignal.timeout(2000) })
      if (!r.ok) return null
      const body = await r.json()
      return Number.isInteger(body.active_conversation_id) ? body.active_conversation_id : null
    } catch {
      return null
    }
  }

  async function setSharedConversation(id) {
    try {
      await fetch(`${baseUrl}/api/chat/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active_conversation_id: id ?? null }),
        signal: AbortSignal.timeout(2000),
      })
    } catch {}
  }

  async function confirmTool(data, rl = null) {
    if (approveAll) return true
    if (denyAll) return false
    if (!input.isTTY) return false

    output.write(`\n${c.yellow}Confirmation required:${c.reset} ${data.message || `Run ${data.tool}?`}\n`)
    if (data.tool) output.write(`${c.dim}Tool: ${data.tool} ${JSON.stringify(data.args || {})}${c.reset}\n`)

    let answer = ''
    if (rl) {
      answer = await rl.question(`${c.yellow}Approve?${c.reset} [y/N] `)
    } else {
      const confirmRl = createInterface({ input, output })
      try {
        answer = await confirmRl.question(`${c.yellow}Approve?${c.reset} [y/N] `)
      } finally {
        confirmRl.close()
      }
    }
    return /^(y|yes)$/i.test(answer.trim())
  }

  async function submitConfirmation(confirmId, approved) {
    try {
      const r = await fetch(`${baseUrl}/api/chat/confirm/${encodeURIComponent(confirmId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved }),
      })
      if (!r.ok) warn(`Confirmation failed: ${r.status} ${r.statusText}`)
    } catch (e) {
      warn(`Confirmation failed: ${e.message}`)
    }
  }

  function describeCommand(cmd) {
    if (!cmd || typeof cmd !== 'object') return 'command'
    if (cmd.type === 'map') return `map ${cmd.action || 'open'}${cmd.query ? `: ${cmd.query}` : ''}`
    if (cmd.type === 'widget') return `widget ${cmd.kind || 'summary'}${cmd.title ? `: ${cmd.title}` : ''}`
    if (cmd.type === 'browse') return `open ${cmd.url || ''}`.trim()
    if (cmd.type === 'launch') return `launch ${cmd.app || ''}`.trim()
    if (cmd.type === 'spotify' || cmd.type === 'spotify_queue') return `${cmd.type}: ${cmd.query || ''}`.trim()
    if (cmd.type === 'away') return `away mode ${cmd.action || ''}`.trim()
    return `${cmd.type || 'command'} ${JSON.stringify(cmd)}`
  }

  async function sendMessage(message, rl = null) {
    const body = { message }
    if (conversationId) body.conversation_id = conversationId

    let wrote = false
    let waiting = true
    let dotIndex = 0
    output.write(`${c.purple}Luna>${c.reset} `)
    const dots = ['.', '..', '...']
    const timer = setInterval(() => {
      if (!waiting) return
      output.write(`\r\x1b[2K${c.purple}Luna>${c.reset} ${c.dim}${dots[dotIndex]}${c.reset}`)
      dotIndex = (dotIndex + 1) % dots.length
    }, 350)

    const stopWaiting = () => {
      if (!waiting) return
      waiting = false
      clearInterval(timer)
      output.write(`\r\x1b[2K${c.purple}Luna>${c.reset} `)
    }

    try {
      const response = await fetch(`${baseUrl}/api/chat/stream?cli=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const text = await response.text().catch(() => '')
        stopWaiting()
        output.write('\n')
        err(`Chat failed ${response.status}: ${text || response.statusText}`)
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      for await (const chunk of response.body) {
        buffer += decoder.decode(chunk, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          for (const line of event.split('\n')) {
            if (!line.startsWith('data:')) continue
            const raw = line.slice(5).trim()
            if (!raw) continue

            let data
            try { data = JSON.parse(raw) }
            catch { continue }

            if (data.type === 'meta' && data.conversation_id) {
              conversationId = data.conversation_id
            } else if ((data.type === 'message_part' && data.content) || (data.type === 'token' && data.token)) {
              stopWaiting()
              output.write(data.content || data.token)
              wrote = true
            } else if (data.type === 'confirmation_required') {
              stopWaiting()
              const approved = await confirmTool(data, rl)
              await submitConfirmation(data.confirm_id, approved)
              output.write(`${c.dim}${approved ? 'Approved.' : 'Denied.'}${c.reset}\n`)
            } else if (data.type === 'proactive' && data.message) {
              stopWaiting()
              output.write(`\n${c.blue}Proactive>${c.reset} ${data.message}\n`)
              wrote = true
            } else if (data.type === 'commands' && Array.isArray(data.commands)) {
              stopWaiting()
              for (const cmd of data.commands) {
                output.write(`\n${c.dim}[command] ${describeCommand(cmd)}${c.reset}`)
              }
            } else if (data.type === 'plan') {
              stopWaiting()
              const steps = Array.isArray(data.steps) ? data.steps : []
              output.write(`\n${c.blue}Plan>${c.reset} ${steps.length || data.total || 0} step${(steps.length || data.total) === 1 ? '' : 's'}\n`)
              steps.forEach((step, index) => output.write(`${c.dim}${index + 1}. ${step}${c.reset}\n`))
            } else if (data.type === 'plan_progress') {
              stopWaiting()
              output.write(`\n${c.dim}[plan] step ${data.step ?? '?'} of ${data.total ?? '?'} complete${c.reset}\n`)
            } else if (data.type === 'plan_done') {
              stopWaiting()
              output.write(`\n${c.green}Plan complete>${c.reset} ${data.summary || 'done'}\n`)
            } else if (data.type === 'error') {
              stopWaiting()
              output.write('\n')
              err(data.message || 'Chat stream error')
            } else if (data.type === 'done' && data.conversation_id) {
              conversationId = data.conversation_id
            }
          }
        }
      }
    } catch (e) {
      stopWaiting()
      output.write('\n')
      err(`Not reachable: ${e.message}`)
      info('Restart with: luna chat')
      return
    } finally {
      if (waiting) {
        waiting = false
        clearInterval(timer)
      }
    }

    if (!wrote) stopWaiting()
    output.write(wrote ? '\n\n' : '(no response)\n\n')
  }

  if (firstMessage) {
    await sendMessage(firstMessage)
    if (_backendProc) {
      try { _backendProc.kill() } catch {}
    }
    process.exit(0)
  }

  const rl = createInterface({ input, output })
  try {
    while (true) {
      const message = (await rl.question(`${c.cyan}You>${c.reset} `)).trim()
      if (!message) continue
      if (message === '/exit' || message === '/quit') break
      if (message === '/new') {
        conversationId = null
        await setSharedConversation(null)
        ok('Started a new conversation')
        continue
      }
      if (message === '/help') {
        console.log(`${c.dim}/new      start a new conversation${c.reset}`)
        console.log(`${c.dim}/exit     quit chat${c.reset}`)
        console.log(`${c.dim}/quit     quit chat${c.reset}`)
        console.log(`${c.dim}Use natural language for tools, files, web research, workspace integrations, plans, and app actions.${c.reset}`)
        continue
      }
      await sendMessage(message, rl)
    }
  } finally {
    rl.close()
  }
}

function doctor() {
  head('Environment check...')
  const checks = [
    ['node',   ['--version']],
    ['npm',    ['--version']],
    [isWin ? 'python' : 'python3', ['--version']],
    ['ollama', ['--version']],
    ['docker', ['--version']],
    ['git',    ['--version']],
  ]
  let i = 0
  const next = () => {
    if (i >= checks.length) return
    const [bin, args] = checks[i++]
    const r = spawnSync(bin, args, { stdio: 'pipe', shell: isWin })
    const out = (r.stdout?.toString() || r.stderr?.toString() || '').trim().split('\n')[0]
    const label = bin.replace(/\.exe$|\.cmd$/, '').padEnd(10)
    if (r.status === 0) ok(`${label} ${out}`)
    else                warn(`${label} not found`)
    next()
  }
  next()
}

// ── Check ─────────────────────────────────────────────────────────────────────
function check() {
  const cacheDir = join(tmpdir(), `luna-pycache-${process.pid}`)
  if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
  const files = [
    'backend/main.py', 'backend/server.py',
    'backend/routers/luna.py', 'backend/routers/agent.py',
    'backend/services/llm.py', 'backend/processes/registry.py',
  ]
  const child = spawn(isWin ? 'python' : 'python3',
    ['-m', 'py_compile', ...files],
    {
      cwd: root, stdio: 'inherit', shell: false,
      env: { ...process.env, PYTHONPYCACHEPREFIX: cacheDir, PYTHONIOENCODING: 'utf-8' },
    }
  )
  child.on('exit', code => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    if (code === 0) ok('Backend syntax OK')
    process.exit(code ?? 0)
  })
  child.on('error', e => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    err(e.message); process.exit(1)
  })
}

// ── Clean ─────────────────────────────────────────────────────────────────────
function clean() {
  const targets = ['data', 'dist', 'dist-electron', 'frontend/dist', '.pytest_cache']
  const files   = ['.env', 'run.log', 'run_err.log', 'server.log', 'server_err.log', 'cloudflared.exe']
  for (const t of [...targets, ...files]) {
    const p = join(root, t)
    if (existsSync(p)) { rmSync(p, { recursive: true, force: true }); info(`removed ${t}`) }
  }
  ok('Clean done')
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function runSync(bin, args) {
  const r = spawnSync(bin, args, {
    cwd: root, stdio: 'inherit', shell: isWin && bin.endsWith('.cmd'),
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
  })
  if (r.status !== 0) { err(`${bin} exited with code ${r.status}`); process.exit(r.status ?? 1) }
}

function readEnvFile() {
  if (process.env.LUNA_ENV_FILE) return parseEnvFiles([process.env.LUNA_ENV_FILE])

  const baseEnv = parseEnvFiles(['.env'])
  const variant = (process.env.LUNA_VARIANT || process.env.luna_variant || baseEnv.luna_variant || 'personal')
    .trim()
    .toLowerCase()

  const envFiles = ['.env']
  if (variant === 'personal' || variant === 'business') envFiles.push(`.env.${variant}`)

  return parseEnvFiles(envFiles)
}

function parseEnvFiles(files) {
  const existingFiles = files
    .map(p => resolve(root, p))
    .filter(p => existsSync(p))

  if (existingFiles.length === 0) return {}

  return Object.fromEntries(
    existingFiles.flatMap(p => readFileSync(p, 'utf8').split('\n'))
      .filter(l => l.includes('=') && !l.startsWith('#'))
      .map(l => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()] })
  )
}

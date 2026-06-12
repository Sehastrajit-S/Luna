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
const cliNpmPackage = 'luna-workspace'
const cliGithubPackage = 'github:Sehastrajit/Luna'

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
  'install:command': {
    group: 'Setup',
    summary: 'Print the one-line CLI installer',
    run: installCommand,
  },
  update: {
    group: 'Setup',
    summary: 'Pull latest Luna code and refresh dependencies',
    run: () => updateCli(rest),
  },
  'self:update': {
    group: 'Setup',
    summary: 'Alias for update',
    run: () => updateCli(rest),
  },
  'cli:install': {
    group: 'Setup',
    summary: 'Install the luna command globally with npm link',
    run: installCli,
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
  status: {
    group: 'Diagnostics',
    summary: 'Show backend, model, app, and permission status',
    run: statusCli,
  },

  // ── Docs ──
  chat: {
    group: 'Chat',
    summary: 'Interactive terminal chat with the running Luna backend',
    run: () => chatCli(rest),
  },
  model: {
    group: 'Chat',
    summary: 'List or switch model provider (luna model [provider] [model])',
    run: () => modelCli(rest),
  },
  connect_app: {
    group: 'Chat',
    summary: 'Show app connector status or setup hints',
    run: () => connectAppCli(rest),
  },
  apps: {
    group: 'Chat',
    summary: 'Alias for connect_app',
    run: () => connectAppCli(rest),
  },
  bugfix: {
    group: 'Chat',
    summary: 'Run enterprise bugfix workflow from the CLI (luna bugfix "<bug>")',
    run: () => bugfixRun(rest),
  },

  // ── Skills marketplace ──
  'skill:list': {
    group: 'Skills',
    summary: 'List installed skills (built-in + user-installed)',
    run: () => skillList(),
  },
  'skill:search': {
    group: 'Skills',
    summary: 'Search the community skills registry (luna skill:search <query>)',
    run: () => skillSearch(rest),
  },
  'skill:install': {
    group: 'Skills',
    summary: 'Install a skill from a git URL or local path (luna skill:install <source>)',
    run: () => skillInstall(rest),
  },
  'skill:remove': {
    group: 'Skills',
    summary: 'Remove an installed skill (luna skill:remove <id>)',
    run: () => skillRemove(rest),
  },
  'skill:refresh': {
    group: 'Skills',
    summary: 'Refresh the community registry cache',
    run: () => skillRefresh(),
  },
  'skill:validate': {
    group: 'Skills',
    summary: 'Validate a local skill folder for publish-readiness (luna skill:validate <path>)',
    run: () => skillValidate(rest),
  },

  // ── Multi-agent crew ──
  crew: {
    group: 'Agents',
    summary: 'Run a multi-agent crew against a task (luna crew "<task>")',
    run: () => crewRun(rest),
  },
  'crew:roles': {
    group: 'Agents',
    summary: 'List available agent roles',
    run: () => crewRoles(),
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

function hasArg(args, flag) {
  return args.includes(flag)
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

function installCommand() {
  head('One-line Luna CLI install')
  console.log(`  ${c.bold}npm i -g ${cliNpmPackage}${c.reset}`)
  console.log()
  console.log(`${c.dim}Shortest first run without a permanent install:${c.reset}`)
  console.log(`  ${c.bold}npx ${cliNpmPackage} setup${c.reset}`)
  console.log()
  console.log(`${c.dim}Works on macOS, Windows, and Linux when Node.js/npm are installed.${c.reset}`)
  console.log(`${c.dim}If the npm package is not published yet, use:${c.reset}`)
  console.log(`  ${c.bold}npm i -g ${cliGithubPackage}${c.reset}`)
  console.log()
  info('Then run: luna setup')
}

function updateCli(args = []) {
  const force = hasArg(args, '--force')
  const skipInstall = hasArg(args, '--skip-install')
  const skipCheck = hasArg(args, '--skip-check')
  const doRelink = hasArg(args, '--link') || hasArg(args, '--relink')
  const branch = quiet('git branch --show-current') || 'current branch'
  const trackedStatus = quiet('git status --porcelain --untracked-files=no')

  head('Updating Luna')
  info(`Repository: ${root}`)
  info(`Branch: ${branch}`)

  if (trackedStatus && !force) {
    warn('Tracked files have local changes. Commit, stash, or rerun with --force to continue.')
    console.log(`${c.dim}${trackedStatus.split('\n').slice(0, 12).join('\n')}${c.reset}`)
    if (trackedStatus.split('\n').length > 12) console.log(`${c.dim}...${c.reset}`)
    process.exit(1)
  }

  runSync('git', ['fetch', '--prune'])
  runSync('git', ['pull', '--ff-only'])

  if (!skipInstall) {
    runSync(isWin ? 'npm.cmd' : 'npm', ['install'])
  } else {
    warn('Skipped dependency install')
  }

  if (doRelink) {
    runSync(isWin ? 'npm.cmd' : 'npm', ['link'])
  }

  if (!skipCheck) {
    runSync(isWin ? 'npm.cmd' : 'npm', ['run', 'test:smoke'])
  } else {
    warn('Skipped smoke checks')
  }

  ok('Luna update complete')
  info('Use: luna update --skip-check for a faster local refresh')
}

// ── Health check ──────────────────────────────────────────────────────────────
function installCli() {
  head('Installing Luna CLI globally...')
  runSync(isWin ? 'npm.cmd' : 'npm', ['link'])
  ok('Installed global `luna` command')
  info('Try: luna help')
  info('Remove later with: npm unlink -g luna-workspace')
}

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

  console.log(`${c.bold}${c.purple}
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

  async function apiJson(path, opts = {}) {
    const r = await fetch(`${baseUrl}${path}`, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      signal: opts.signal || AbortSignal.timeout(120000),
    })
    const text = await r.text()
    let body = null
    try { body = text ? JSON.parse(text) : null } catch { body = { raw: text } }
    if (!r.ok) throw new Error((body && (body.detail || body.error)) || `HTTP ${r.status}`)
    return body
  }

  async function modelCommand(raw = '') {
    const parts = raw.trim().split(/\s+/).filter(Boolean)
    const settings = await apiJson('/api/coding/settings')
    const providers = settings.providers || {}
    const modelKey = {
      ollama: 'ollama_model',
      anthropic: 'anthropic_model',
      groq: 'groq_model',
      google: 'google_model',
      'openai-compatible': 'openai_model',
      mistral: 'mistral_model',
      cohere: 'cohere_model',
      'nvidia-nim': 'nvidia_nim_model',
    }

    if (parts.length === 0 || parts[0] === 'list') {
      console.log(`\n${c.bold}Models${c.reset}`)
      console.log(`  active provider: ${c.cyan}${settings.llm_provider}${c.reset}`)
      for (const [id, meta] of Object.entries(providers)) {
        const key = modelKey[id]
        const model = key ? settings[key] : ''
        const mark = id === settings.llm_provider ? '*' : ' '
        const configured = meta.configured ? c.green + 'configured' + c.reset : c.yellow + 'missing key' + c.reset
        console.log(`  ${mark} ${c.bold}${id.padEnd(18)}${c.reset} ${configured} ${c.dim}${model || ''}${c.reset}`)
      }
      console.log(`\n  ${c.dim}Use: /model <provider> [model]${c.reset}`)
      return
    }

    const provider = parts[0]
    if (!providers[provider]) {
      warn(`Unknown provider: ${provider}`)
      info(`Use /model list`)
      return
    }

    const payload = { llm_provider: provider }
    const model = parts.slice(1).join(' ').trim()
    if (model && modelKey[provider]) payload[modelKey[provider]] = model
    const updated = await apiJson('/api/coding/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    ok(`Model updated: ${provider}${model ? ` / ${model}` : ''}`)
    if (updated.updated) console.log(`${c.dim}${JSON.stringify(updated.updated)}${c.reset}`)
  }

  async function connectAppCommand(raw = '') {
    const app = raw.trim().toLowerCase()
    const envNow = readEnvFile()
    const workspace = await apiJson('/api/integrations/workspace/status').catch(() => null)
    const rows = [
      ['GitHub', Boolean(envNow.github_token), 'github_token'],
      ['Slack', Boolean(envNow.slack_bot_token), 'slack_bot_token'],
      ['Jira', Boolean(envNow.jira_base_url && envNow.jira_email && envNow.jira_api_token), 'jira_base_url, jira_email, jira_api_token'],
      ['Google Workspace', Boolean(workspace?.google?.configured), 'google_workspace_refresh_token or access token'],
      ['Microsoft 365', Boolean(workspace?.microsoft?.configured), 'microsoft_workspace_refresh_token or access token'],
      ['Salesforce', false, 'not implemented yet'],
      ['Notion', false, 'not implemented yet'],
      ['Database tools', false, 'not implemented yet'],
      ['Internal APIs', false, 'not implemented yet'],
    ]

    if (!app || app === 'list' || app === 'status') {
      console.log(`\n${c.bold}Connected Apps${c.reset}`)
      for (const [name, configured, hint] of rows) {
        const status = configured ? `${c.green}configured${c.reset}` : `${c.yellow}not configured${c.reset}`
        console.log(`  ${name.padEnd(18)} ${status} ${c.dim}${hint}${c.reset}`)
      }
      console.log(`\n  ${c.dim}Use: /connect_app google | github | slack | jira${c.reset}`)
      return
    }

    if (app === 'google') {
      console.log(`Open this URL to connect Google Workspace:\n${c.cyan}${baseUrl}/api/integrations/workspace/google/oauth/start${c.reset}`)
      return
    }
    if (app === 'github') {
      console.log(`Set ${c.cyan}github_token${c.reset} in .env with repo scope, then restart chat.`)
      return
    }
    if (app === 'slack') {
      console.log(`Set ${c.cyan}slack_bot_token${c.reset}, ${c.cyan}slack_signing_secret${c.reset}, and optional ${c.cyan}slack_default_channel${c.reset} in .env.`)
      console.log(`${c.dim}For history/search, grant Slack search/conversations scopes to the bot token.${c.reset}`)
      return
    }
    if (app === 'jira') {
      console.log(`Set ${c.cyan}jira_base_url${c.reset}, ${c.cyan}jira_email${c.reset}, and ${c.cyan}jira_api_token${c.reset} in .env.`)
      return
    }
    warn(`No connector setup helper for '${app}'. Use /connect_app to see supported apps.`)
  }

  async function bugfixCommand(raw = '', rl = null) {
    const bugQuery = raw.trim()
    if (!bugQuery) {
      warn('Usage: /bugfix <bug description>')
      return
    }
    const approved = await confirmTool({
      tool: 'enterprise_bugfix_workflow',
      message: `Run enterprise bugfix workflow for "${bugQuery}"?`,
      args: { bug_query: bugQuery },
    }, rl)
    if (!approved) {
      warn('Bugfix workflow cancelled.')
      return
    }
    const result = await apiJson('/api/agent/enterprise/bugfix', {
      method: 'POST',
      body: JSON.stringify({ bug_query: bugQuery }),
      signal: AbortSignal.timeout(900000),
    })
    renderBugfixResult(result)
  }

  async function statusCommand() {
    const health = await apiJson('/api/system/health').catch(e => ({ error: e.message }))
    console.log(`\n${c.bold}Status${c.reset}`)
    console.log(`  backend        ${health.error ? c.red + health.error + c.reset : c.green + 'healthy' + c.reset}`)
    await modelCommand('list')
    await connectAppCommand('status')
  }

  async function updateCommand(raw = '', rl = null) {
    const args = raw.trim() ? raw.trim().split(/\s+/) : []
    const approved = await confirmTool({
      tool: 'luna_update',
      message: `Run Luna update${args.length ? ` with ${args.join(' ')}` : ''}?`,
      args: { flags: args },
    }, rl)
    if (!approved) {
      warn('Update cancelled.')
      return
    }
    updateCli(args)
  }

  async function skillsCommand() {
    const data = await apiJson('/api/skills/installed')
    const skills = data.skills || []
    console.log(`\n${c.bold}Skills${c.reset}`)
    if (!skills.length) {
      warn('No skills installed.')
      return
    }
    for (const s of skills) {
      const origin = s.origin ? ` ${c.dim}[${s.origin}]${c.reset}` : ''
      console.log(`  ${c.cyan}${String(s.id || '').padEnd(28)}${c.reset}${origin} ${c.dim}${s.description || ''}${c.reset}`)
    }
  }

  async function permissionsCommand() {
    const data = await apiJson('/api/agent/permissions')
    console.log(`\n${c.bold}Tool Permissions${c.reset}`)
    const tools = data.tools || {}
    for (const [name, meta] of Object.entries(tools)) {
      if (meta.mode === 'allow' && meta.risk === 'safe') continue
      const color = meta.mode === 'allow' ? c.green : meta.mode === 'confirm' ? c.yellow : c.red
      console.log(`  ${name.padEnd(32)} ${color}${meta.mode}${c.reset} ${c.dim}${meta.risk}${c.reset}`)
    }
    console.log(`\n  ${c.dim}Only non-default or risky tools are shown.${c.reset}`)
  }

  async function crewCommand(raw = '') {
    const task = raw.trim()
    if (!task) {
      warn('Usage: /crew <task description>')
      return
    }
    const r = await fetch(`${baseUrl}/api/agent/crew/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task }),
      signal: AbortSignal.timeout(300000),
    })
    if (!r.ok || !r.body) throw new Error(`Crew failed: HTTP ${r.status}`)
    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() || ''
      for (const part of parts) {
        const line = part.replace(/^data:\s*/, '').trim()
        if (!line) continue
        let ev
        try { ev = JSON.parse(line) } catch { continue }
        renderCrewEvent(ev, () => {})
      }
    }
    console.log()
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
        console.log(`${c.dim}/new          start a new conversation${c.reset}`)
        console.log(`${c.dim}/status       show backend, model, and connector status${c.reset}`)
        console.log(`${c.dim}/model        list or choose model: /model <provider> [model]${c.reset}`)
        console.log(`${c.dim}/connect_app  show configured apps or setup hints${c.reset}`)
        console.log(`${c.dim}/apps         alias for /connect_app${c.reset}`)
        console.log(`${c.dim}/skills       list installed skills${c.reset}`)
        console.log(`${c.dim}/permissions  show risky or non-default tool permissions${c.reset}`)
        console.log(`${c.dim}/crew         run a multi-agent crew: /crew <task>${c.reset}`)
        console.log(`${c.dim}/bugfix       run enterprise bugfix workflow${c.reset}`)
        console.log(`${c.dim}/update       pull latest Luna code and refresh dependencies${c.reset}`)
        console.log(`${c.dim}/exit         quit chat${c.reset}`)
        console.log(`${c.dim}/quit         quit chat${c.reset}`)
        console.log(`${c.dim}Use natural language for tools, files, web research, workspace integrations, plans, and app actions.${c.reset}`)
        continue
      }
      if (message === '/status') {
        try { await statusCommand() }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/model' || message.startsWith('/model ')) {
        try { await modelCommand(message.slice('/model'.length)) }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/connect_app' || message.startsWith('/connect_app ') || message === '/apps' || message.startsWith('/apps ')) {
        const prefix = message.startsWith('/apps') ? '/apps' : '/connect_app'
        try { await connectAppCommand(message.slice(prefix.length)) }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/skills') {
        try { await skillsCommand() }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/permissions') {
        try { await permissionsCommand() }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/crew' || message.startsWith('/crew ')) {
        try { await crewCommand(message.slice('/crew'.length)) }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/bugfix' || message.startsWith('/bugfix ')) {
        try { await bugfixCommand(message.slice('/bugfix'.length), rl) }
        catch (e) { err(e.message) }
        continue
      }
      if (message === '/update' || message.startsWith('/update ')) {
        try { await updateCommand(message.slice('/update'.length), rl) }
        catch (e) { err(e.message) }
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

// ── Skills marketplace ────────────────────────────────────────────────────────
async function skillApiBase() {
  const env = readEnvFile()
  const port = env.port || '8899'
  return process.env.LUNA_URL || env.luna_url || `http://localhost:${port}`
}

async function skillFetch(path, opts = {}) {
  const base = await skillApiBase()
  try {
    const r = await fetch(`${base}${path}`, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      signal: AbortSignal.timeout(60000),
    })
    const text = await r.text()
    let body = null
    try { body = text ? JSON.parse(text) : null } catch { body = { raw: text } }
    if (!r.ok) {
      const detail = (body && body.detail) || `HTTP ${r.status}`
      throw new Error(detail)
    }
    return body
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Backend did not respond within 60s')
    throw new Error(`Backend unreachable at ${base} — is it running? (${e.message})`)
  }
}

async function skillList() {
  head('Installed skills')
  try {
    const data = await skillFetch('/api/skills/installed')
    const skills = data.skills || []
    if (skills.length === 0) { warn('No skills installed.'); return }
    const builtins = skills.filter(s => s.origin === 'builtin')
    const userInstalled = skills.filter(s => s.origin === 'user')
    if (builtins.length) {
      console.log(`\n  ${c.bold}Built-in${c.reset}`)
      for (const s of builtins) {
        console.log(`    ${c.cyan}${s.id.padEnd(28)}${c.reset}${c.dim}${s.description}${c.reset}`)
      }
    }
    if (userInstalled.length) {
      console.log(`\n  ${c.bold}Installed${c.reset}`)
      for (const s of userInstalled) {
        const perms = (s.permissions || []).join(', ') || 'none'
        console.log(`    ${c.green}${s.id.padEnd(28)}${c.reset}v${s.version}  ${c.dim}[${perms}]${c.reset}`)
        console.log(`    ${' '.repeat(28)}${c.dim}${s.description}${c.reset}`)
      }
    }
    console.log()
  } catch (e) { err(e.message); process.exit(1) }
}

async function skillSearch(args) {
  const query = args.join(' ').trim()
  head(query ? `Searching registry for "${query}"` : 'Browsing registry')
  try {
    const path = query
      ? `/api/skills/registry/search?q=${encodeURIComponent(query)}`
      : '/api/skills/registry'
    const data = await skillFetch(path)
    const skills = data.skills || []
    if (skills.length === 0) { warn('No matching skills.'); return }
    console.log()
    for (const s of skills) {
      const verified = s.verified ? `${c.green} ✓ verified${c.reset}` : ''
      const stars = s.stars ? ` ${c.yellow}★${s.stars}${c.reset}` : ''
      console.log(`  ${c.bold}${s.id}${c.reset} v${s.version}${verified}${stars}`)
      console.log(`    ${c.dim}${s.description}${c.reset}`)
      console.log(`    ${c.dim}source: ${s.source}${c.reset}`)
      if ((s.permissions || []).length) {
        console.log(`    ${c.dim}permissions: ${s.permissions.join(', ')}${c.reset}`)
      }
      console.log()
    }
    info('Install with:  luna skill:install <source>')
  } catch (e) { err(e.message); process.exit(1) }
}

async function skillInstall(args) {
  const source = (args.find(a => !a.startsWith('--')) || '').trim()
  if (!source) { err('Usage: luna skill:install <git-url | github:user/repo | path>'); process.exit(1) }
  const overwrite = args.includes('--overwrite')
  const yes = args.includes('--yes') || args.includes('-y')
  head(`Installing ${source}`)

  const attempt = async (confirmDangerous) => skillFetch('/api/skills/install', {
    method: 'POST',
    body: JSON.stringify({ source, overwrite, confirm_dangerous: confirmDangerous }),
  })

  try {
    let result
    try {
      result = await attempt(false)
    } catch (e) {
      if (/dangerous permissions/i.test(e.message)) {
        if (!yes) {
          warn(e.message)
          const rl = createInterface({ input, output })
          const ans = (await rl.question('Continue with these permissions? [y/N] ')).trim().toLowerCase()
          rl.close()
          if (ans !== 'y' && ans !== 'yes') { warn('Install cancelled.'); return }
        }
        result = await attempt(true)
      } else { throw e }
    }
    const s = result.skill
    ok(`Installed ${c.bold}${s.skill_id}${c.reset} v${s.version} → ${c.dim}${s.path}${c.reset}`)
    if ((s.dangerous_permissions || []).length) {
      warn(`Granted dangerous permissions: ${s.dangerous_permissions.join(', ')}`)
    }
  } catch (e) { err(e.message); process.exit(1) }
}

async function skillRemove(args) {
  const id = (args[0] || '').trim()
  if (!id) { err('Usage: luna skill:remove <skill-id>'); process.exit(1) }
  head(`Removing ${id}`)
  try {
    await skillFetch(`/api/skills/${encodeURIComponent(id)}`, { method: 'DELETE' })
    ok(`Removed ${id}`)
  } catch (e) { err(e.message); process.exit(1) }
}

async function skillRefresh() {
  head('Refreshing community registry')
  try {
    const data = await skillFetch('/api/skills/registry/refresh', { method: 'POST' })
    ok(`Registry refreshed (${data.count} skills)`)
  } catch (e) { err(e.message); process.exit(1) }
}

async function skillValidate(args) {
  const target = (args[0] || '').trim()
  if (!target) { err('Usage: luna skill:validate <path>'); process.exit(1) }
  head(`Validating ${target}`)
  try {
    const report = await skillFetch('/api/skills/validate', {
      method: 'POST',
      body: JSON.stringify({ path: resolve(target) }),
    })
    if (report.ok) ok(`${report.skill_id} v${report.version} — ready to publish`)
    else err(`${report.skill_id || '(unknown)'} — validation failed`)
    for (const e of report.errors || [])   console.log(`  ${c.red}error  ${c.reset}${e}`)
    for (const w of report.warnings || []) console.log(`  ${c.yellow}warn   ${c.reset}${w}`)
    for (const i of report.info || [])     console.log(`  ${c.dim}info   ${i}${c.reset}`)
    process.exit(report.ok ? 0 : 1)
  } catch (e) { err(e.message); process.exit(1) }
}

// ── Multi-agent crew ─────────────────────────────────────────────────────────
async function modelCli(args = []) {
  const provider = (args[0] || '').trim()
  const model = args.slice(1).join(' ').trim()
  try {
    const settings = await skillFetch('/api/coding/settings')
    if (!provider || provider === 'list') {
      renderModelStatus(settings)
      return
    }
    const modelKey = providerModelKey(provider)
    if (!settings.providers?.[provider]) {
      err(`Unknown provider: ${provider}`)
      process.exit(1)
    }
    const payload = { llm_provider: provider }
    if (model && modelKey) payload[modelKey] = model
    const updated = await skillFetch('/api/coding/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    ok(`Model updated: ${provider}${model ? ` / ${model}` : ''}`)
    if (updated.updated) console.log(`${c.dim}${JSON.stringify(updated.updated)}${c.reset}`)
  } catch (e) { err(e.message); process.exit(1) }
}

async function connectAppCli(args = []) {
  const app = (args[0] || '').trim().toLowerCase()
  try {
    const workspace = await skillFetch('/api/integrations/workspace/status').catch(() => null)
    renderConnectorStatus(app, workspace)
  } catch (e) { err(e.message); process.exit(1) }
}

async function statusCli() {
  head('Runtime status')
  try {
    await healthCheckNoExit()
    renderModelStatus(await skillFetch('/api/coding/settings'))
    const workspace = await skillFetch('/api/integrations/workspace/status').catch(() => null)
    renderConnectorStatus('', workspace)
    const permissions = await skillFetch('/api/agent/permissions').catch(() => null)
    if (permissions?.tools) {
      console.log(`\n${c.bold}Risky Tool Permissions${c.reset}`)
      for (const [name, meta] of Object.entries(permissions.tools)) {
        if (meta.risk === 'safe' && meta.mode === 'allow') continue
        const color = meta.mode === 'allow' ? c.green : meta.mode === 'confirm' ? c.yellow : c.red
        console.log(`  ${name.padEnd(32)} ${color}${meta.mode}${c.reset} ${c.dim}${meta.risk}${c.reset}`)
      }
    }
  } catch (e) { err(e.message); process.exit(1) }
}

async function healthCheckNoExit() {
  const env = readEnvFile()
  const port = env.port || '8899'
  const url = process.env.LUNA_URL || env.luna_url || `http://localhost:${port}`
  const r = await fetch(`${url}/api/system/health`, { signal: AbortSignal.timeout(5000) })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(`Backend unhealthy ${r.status}: ${JSON.stringify(body)}`)
  ok(`Backend healthy at ${url}`)
}

function renderModelStatus(settings) {
  const providers = settings.providers || {}
  console.log(`\n${c.bold}Models${c.reset}`)
  console.log(`  active provider: ${c.cyan}${settings.llm_provider}${c.reset}`)
  for (const [id, meta] of Object.entries(providers)) {
    const key = providerModelKey(id)
    const current = id === settings.llm_provider ? '*' : ' '
    const configured = meta.configured ? c.green + 'configured' + c.reset : c.yellow + 'missing key' + c.reset
    console.log(`  ${current} ${c.bold}${id.padEnd(18)}${c.reset} ${configured} ${c.dim}${key ? settings[key] || '' : ''}${c.reset}`)
  }
  console.log(`\n  ${c.dim}Set with: luna model <provider> [model]${c.reset}`)
}

function renderConnectorStatus(app = '', workspace = null) {
  const envNow = readEnvFile()
  const rows = [
    ['github', 'GitHub', Boolean(envNow.github_token), 'set github_token in .env'],
    ['slack', 'Slack', Boolean(envNow.slack_bot_token), 'set slack_bot_token, slack_signing_secret, optional slack_default_channel'],
    ['jira', 'Jira', Boolean(envNow.jira_base_url && envNow.jira_email && envNow.jira_api_token), 'set jira_base_url, jira_email, jira_api_token'],
    ['google', 'Google Workspace', Boolean(workspace?.google?.configured), 'open /api/integrations/workspace/google/oauth/start'],
    ['microsoft', 'Microsoft 365', Boolean(workspace?.microsoft?.configured), 'set microsoft workspace OAuth token or refresh token'],
    ['salesforce', 'Salesforce', false, 'not implemented yet'],
    ['notion', 'Notion', false, 'not implemented yet'],
    ['database', 'Database tools', false, 'not implemented yet'],
    ['internal', 'Internal APIs', false, 'not implemented yet'],
  ]
  const selected = app && app !== 'list' && app !== 'status' ? rows.filter(([id]) => id === app) : rows
  if (!selected.length) {
    warn(`Unknown app: ${app}`)
    info('Known apps: github, slack, jira, google, microsoft')
    return
  }
  console.log(`\n${c.bold}Connected Apps${c.reset}`)
  for (const [, name, configured, hint] of selected) {
    const status = configured ? `${c.green}configured${c.reset}` : `${c.yellow}not configured${c.reset}`
    console.log(`  ${name.padEnd(18)} ${status} ${c.dim}${hint}${c.reset}`)
  }
}

function providerModelKey(provider) {
  return {
    ollama: 'ollama_model',
    anthropic: 'anthropic_model',
    groq: 'groq_model',
    google: 'google_model',
    'openai-compatible': 'openai_model',
    mistral: 'mistral_model',
    cohere: 'cohere_model',
    'nvidia-nim': 'nvidia_nim_model',
  }[provider]
}

async function crewRoles() {
  head('Available agent roles')
  try {
    const data = await skillFetch('/api/agent/crew/roles')
    for (const r of data.roles || []) {
      console.log(`  ${c.bold}${r.role.padEnd(12)}${c.reset}${c.dim}${r.description}${c.reset}`)
      const tools = (r.allowed_tools || []).join(', ') || 'none'
      console.log(`              ${c.dim}tools: ${tools}  temp: ${r.temperature}${c.reset}`)
    }
    console.log()
  } catch (e) { err(e.message); process.exit(1) }
}

async function crewRun(args) {
  const task = args.join(' ').trim()
  if (!task) { err('Usage: luna crew "<task description>"'); process.exit(1) }
  head(`Crew running: ${task}`)
  const base = await skillApiBase()
  try {
    const r = await fetch(`${base}/api/agent/crew/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task }),
      signal: AbortSignal.timeout(300000),
    })
    if (!r.ok || !r.body) {
      const errText = await r.text().catch(() => '')
      throw new Error(`HTTP ${r.status} ${errText}`)
    }
    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let lastRole = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() || ''
      for (const part of parts) {
        const line = part.replace(/^data:\s*/, '').trim()
        if (!line) continue
        let ev
        try { ev = JSON.parse(line) } catch { continue }
        renderCrewEvent(ev, (newRole) => { lastRole = newRole })
      }
    }
    console.log()
    ok('Crew complete')
  } catch (e) { err(e.message); process.exit(1) }
}

async function bugfixRun(args) {
  const parsed = parseBugfixArgs(args)
  if (!parsed.bug_query) {
    err('Usage: luna bugfix "<bug description>" [--repo owner/repo] [--jira KEY] [--pr 123] [--slack query] [--yes]')
    process.exit(1)
  }

  const yes = parsed.yes
  delete parsed.yes
  head(`Enterprise bugfix: ${parsed.bug_query}`)

  if (!yes && input.isTTY) {
    const rl = createInterface({ input, output })
    try {
      const ans = (await rl.question(`${c.yellow}Run workflow and allow branch/commit/push/PR if tests pass?${c.reset} [y/N] `)).trim()
      if (!/^(y|yes)$/i.test(ans)) {
        warn('Cancelled.')
        return
      }
    } finally {
      rl.close()
    }
  } else if (!yes) {
    err('Refusing to run non-interactively without --yes')
    process.exit(1)
  }

  const base = await skillApiBase()
  try {
    const r = await fetch(`${base}/api/agent/enterprise/bugfix`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed),
      signal: AbortSignal.timeout(900000),
    })
    const text = await r.text()
    let result
    try { result = JSON.parse(text) } catch { result = { ok: false, summary: text } }
    renderBugfixResult(result)
    process.exit(r.ok && result.ok ? 0 : 1)
  } catch (e) {
    err(`Bugfix workflow failed: ${e.message}`)
    process.exit(1)
  }
}

function parseBugfixArgs(args) {
  const out = {}
  const words = []
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (arg === '--yes' || arg === '-y') out.yes = true
    else if (arg === '--repo') out.repo = args[++i] || ''
    else if (arg === '--jira') out.jira_key = args[++i] || ''
    else if (arg === '--pr') out.pr_number = Number(args[++i] || 0)
    else if (arg === '--slack') out.slack_query = args[++i] || ''
    else if (arg === '--channel') out.slack_channel = args[++i] || ''
    else if (arg === '--test') out.test_command = args[++i] || ''
    else if (arg === '--no-pr') out.create_pr = false
    else words.push(arg)
  }
  out.bug_query = words.join(' ').trim()
  return out
}

function renderBugfixResult(result) {
  const status = result.ok ? c.green : c.yellow
  console.log(`\n${status}${result.ok ? 'Completed' : 'Stopped'}${c.reset}: ${result.summary || ''}`)
  for (const step of result.steps || []) {
    const color = step.status === 'ok' ? c.green : step.status === 'skipped' ? c.yellow : c.red
    console.log(`  ${color}${step.status.padEnd(7)}${c.reset} ${step.name}${step.detail ? ` ${c.dim}${step.detail}${c.reset}` : ''}`)
  }
  if ((result.changed_files || []).length) {
    console.log(`\n${c.bold}Changed files${c.reset}`)
    for (const file of result.changed_files) console.log(`  ${file}`)
  }
  if (result.pr?.url) {
    console.log(`\n${c.bold}Pull request${c.reset}`)
    console.log(`  ${c.cyan}${result.pr.url}${c.reset}`)
  }
  console.log()
}

function renderCrewEvent(ev, setRole) {
  switch (ev.type) {
    case 'crew_start':
      info(`Task accepted: ${ev.task}`)
      break
    case 'plan_ready':
      console.log(`\n  ${c.bold}Plan${c.reset}`)
      for (const s of ev.subtasks || []) {
        console.log(`    ${c.cyan}[${s.index}] ${s.role.padEnd(11)}${c.reset}${c.dim}${s.task}${c.reset}`)
      }
      console.log()
      break
    case 'agent_start':
      console.log(`\n  ${c.bold}${c.purple}▸ ${ev.role}${c.reset}  ${c.dim}${ev.task}${c.reset}`)
      setRole(ev.role)
      break
    case 'agent_token':
      process.stdout.write(ev.content || '')
      break
    case 'agent_result':
      console.log()
      break
    case 'critic_review':
      const verdict = ev.verdict === 'approved' ? c.green : c.yellow
      console.log(`\n  ${verdict}critic: ${ev.verdict}${c.reset} ${c.dim}${ev.reason || ''}${c.reset}`)
      break
    case 'revision_request':
      warn(`Revising (round ${ev.round}): ${ev.reason}`)
      break
    case 'crew_done':
      console.log(`\n${c.bold}${c.green}  Final answer${c.reset}\n`)
      console.log(ev.answer || '(empty)')
      break
    case 'error':
    case 'agent_error':
      err(`${ev.role || 'crew'}: ${ev.message || 'unknown error'}`)
      break
  }
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

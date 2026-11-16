#!/usr/bin/env node
/**
 * Luna Docker automation — auto-detects the right mode.
 *
 * Detection order:
 *   1. llm_provider=openai-compatible in .env  → cloud mode (no Ollama)
 *   2. NVIDIA GPU detected on host             → local + GPU
 *   3. fallback                                → local CPU
 *
 * Override with flags:
 *   npm run docker -- --cpu    force CPU even if GPU is present
 *   npm run docker -- --gpu    force GPU
 *   npm run docker -- --cloud  force cloud
 *
 * Other commands:
 *   npm run docker:down        stop all containers
 *   npm run docker:logs        tail luna logs
 *   npm run docker:pull        re-pull models (after model change)
 */

import { execSync, spawnSync } from 'child_process';
import { existsSync, readFileSync, copyFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);

// ── Colours ───────────────────────────────────────────────────────────────────
const c = {
  reset: '\x1b[0m', bold: '\x1b[1m',
  cyan: '\x1b[36m', green: '\x1b[32m',
  yellow: '\x1b[33m', red: '\x1b[31m', purple: '\x1b[35m',
};
const log   = m => console.log(`${c.cyan}  ▸${c.reset} ${m}`);
const ok    = m => console.log(`${c.green}  ✓${c.reset} ${m}`);
const warn  = m => console.log(`${c.yellow}  !${c.reset} ${m}`);
const fail  = m => { console.error(`${c.red}  ✗${c.reset} ${m}`); process.exit(1); };
const head  = m => console.log(`\n${c.bold}${c.purple}  ${m}${c.reset}`);
const run   = (cmd, opts) => execSync(cmd, { stdio: 'inherit', cwd: ROOT, ...opts });
const quiet = (cmd)       => { try { return execSync(cmd, { cwd: ROOT, stdio: 'pipe' }).toString().trim(); } catch { return ''; } };

// ── Banner ─────────────────────────────────────────────────────────────────────
console.log(`\n${c.bold}${c.purple}`);
console.log('  ██╗     ██╗   ██╗███╗   ██╗ █████╗ ');
console.log('  ██║     ██║   ██║████╗  ██║██╔══██╗');
console.log('  ██║     ██║   ██║██╔██╗ ██║███████║');
console.log('  ██║     ██║   ██║██║╚██╗██║██╔══██║');
console.log('  ███████╗╚██████╔╝██║ ╚████║██║  ██║');
console.log('  ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝');
console.log(`${c.reset}  Large Unified Nexus Mind AI\n`);

// ── Helpers ───────────────────────────────────────────────────────────────────
function readEnv() {
  const p = join(ROOT, '.env');
  if (!existsSync(p)) return {};
  return Object.fromEntries(
    readFileSync(p, 'utf8').split('\n')
      .filter(l => l.includes('=') && !l.startsWith('#'))
      .map(l => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
  );
}

function hasNvidiaGpu() {
  // Try nvidia-smi on the host
  const r = spawnSync('nvidia-smi', [], { stdio: 'pipe' });
  if (r.status === 0) return true;
  // Try via docker (catches WSL2 GPU passthrough even when nvidia-smi isn't on PATH)
  const d = spawnSync('docker', ['run', '--rm', '--gpus', 'all', '--entrypoint', 'nvidia-smi',
    'nvidia/cuda:12.3.1-base-ubuntu22.04'], { stdio: 'pipe', timeout: 15000 });
  return d.status === 0;
}

function detectMode(env) {
  if (args.includes('--business')) return 'business';
  if (args.includes('--cloud'))    return 'cloud';
  if (args.includes('--gpu'))      return 'gpu';
  if (args.includes('--cpu'))      return 'cpu';

  // Auto-detect from .env
  const variant  = (env.luna_variant  || '').trim().toLowerCase();
  const provider = (env.llm_provider  || '').trim().toLowerCase();

  if (variant === 'business') return 'business';

  const cloudProviders = ['anthropic', 'google', 'groq', 'cohere', 'mistral', 'openai-compatible', 'nvidia-nim'];
  if (cloudProviders.includes(provider)) return 'cloud';

  // Auto-detect GPU
  log('Checking for NVIDIA GPU...');
  if (hasNvidiaGpu()) return 'gpu';

  return 'cpu';
}

function composeArgs(mode) {
  if (mode === 'business') return ['-f', 'deploy/compose.business.yml'];
  if (mode === 'cloud')    return ['-f', 'deploy/compose.cloud.yml'];
  if (mode === 'gpu')      return ['-f', 'deploy/compose.yml', '-f', 'deploy/compose.gpu.yml'];
  return ['-f', 'deploy/compose.yml'];
}

function dc(mode, ...extra) {
  return ['docker', 'compose', ...composeArgs(mode), ...extra].join(' ');
}

async function waitForHealth(url, maxMs = 180_000) {
  process.stdout.write(`${c.cyan}  ▸${c.reset} Waiting for Luna`);
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (res.ok) { console.log(` ${c.green}ready!${c.reset}`); return true; }
    } catch { /* not ready */ }
    process.stdout.write('.');
    await new Promise(r => setTimeout(r, 2000));
  }
  console.log();
  return false;
}

async function pullModels(mode, env) {
  if (mode === 'cloud') return;
  head('Pulling models into Ollama...');
  const chat  = env.ollama_model       || 'qwen2.5:7b';
  const embed = env.ollama_embed_model || 'nomic-embed-text';

  // Wait for Ollama API
  let ollamaReady = false;
  for (let i = 0; i < 20; i++) {
    try {
      const r = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(3000) });
      if (r.ok) { ollamaReady = true; break; }
    } catch { /* wait */ }
    await new Promise(r => setTimeout(r, 3000));
  }

  if (!ollamaReady) {
    warn('Ollama not responding. Pull models manually:');
    warn(`  docker compose exec ollama ollama pull ${chat}`);
    warn(`  docker compose exec ollama ollama pull ${embed}`);
    return;
  }

  for (const model of [chat, embed]) {
    log(`Pulling ${c.bold}${model}${c.reset} ...`);
    try {
      run(`docker compose ${composeArgs(mode).join(' ')} exec -T ollama ollama pull ${model}`);
      ok(model);
    } catch {
      warn(`Could not pull ${model} — run manually: docker compose exec ollama ollama pull ${model}`);
    }
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────
(async () => {

  // ── Shortcuts ─────────────────────────────────────────────────────────────
  if (args.includes('--down') || args[0] === 'down') {
    for (const f of ['compose.yml', 'compose.cloud.yml', 'compose.business.yml']) {
      if (existsSync(join(ROOT, f)))
        quiet(`docker compose -f ${f} down`);
    }
    ok('Stopped'); process.exit(0);
  }
  if (args.includes('--logs') || args[0] === 'logs') {
    const f = existsSync(join(ROOT, 'compose.cloud.yml')) ? 'compose.cloud.yml' : 'compose.yml';
    run(`docker compose -f ${f} logs -f luna`); process.exit(0);
  }

  // ── Preflight ─────────────────────────────────────────────────────────────
  head('Checking requirements...');

  if (!quiet('docker --version')) fail('Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/');
  ok('Docker: ' + quiet('docker --version'));

  if (!quiet('docker compose version')) fail('Docker Compose not found.');
  ok('Docker Compose: ' + quiet('docker compose version'));

  if (!quiet('docker info')) fail('Docker daemon is not running. Start Docker Desktop and try again.');
  ok('Docker daemon running');

  // ── .env setup ────────────────────────────────────────────────────────────
  head('Configuration...');
  const envPath = join(ROOT, '.env');
  if (!existsSync(envPath)) {
    const ex = join(ROOT, '.env.example');
    if (!existsSync(ex)) fail('.env.example not found.');
    copyFileSync(ex, envPath);
    ok('Created .env from .env.example');
    warn('Review .env — set your model name, location, and any API keys before the next run.');
  } else {
    ok('.env found');
  }
  const env = readEnv();

  // ── Auto-detect mode ──────────────────────────────────────────────────────
  const mode = detectMode(env);

  head(`Mode: ${mode === 'cloud' ? 'Cloud LLM (no Ollama)' : mode === 'gpu' ? 'Local + NVIDIA GPU' : 'Local Ollama (CPU)'}`);
  if (mode === 'cloud') {
    log(`Provider:  ${env.openai_base_url || '(set openai_base_url in .env)'}`);
    log(`Model:     ${env.openai_model    || '(set openai_model in .env)'}`);
    if (!env.openai_api_key) warn('openai_api_key is not set in .env');
  } else {
    log(`Chat model:  ${env.ollama_model       || 'qwen2.5:7b'}`);
    log(`Embed model: ${env.ollama_embed_model || 'nomic-embed-text'}`);
  }

  // ── Build + start ─────────────────────────────────────────────────────────
  head('Building and starting containers...');
  run(dc(mode, 'up', '-d', '--build'));
  ok('Containers up');

  // ── Pull models ───────────────────────────────────────────────────────────
  await pullModels(mode, env);

  // ── Health check ──────────────────────────────────────────────────────────
  head('Health check...');
  const port = env.port || '8899';
  const healthy = await waitForHealth(`http://localhost:${port}/api/system/health`);
  if (!healthy) warn('Still starting — check: npm run docker:logs');

  // ── Done ──────────────────────────────────────────────────────────────────
  console.log(`\n${c.bold}${c.green}  L.U.N.A. is running!${c.reset}\n`);
  console.log(`  ${c.bold}Chat UI${c.reset}     →  ${c.cyan}http://localhost:${port}${c.reset}`);
  console.log(`  ${c.bold}API docs${c.reset}    →  ${c.cyan}http://localhost:${port}/docs${c.reset}`);
  console.log(`  ${c.bold}Logs${c.reset}        →  ${c.yellow}npm run docker:logs${c.reset}`);
  console.log(`  ${c.bold}Stop${c.reset}        →  ${c.yellow}npm run docker:down${c.reset}`);
  console.log(`  ${c.bold}Upgrade${c.reset}     →  ${c.yellow}git pull && npm run docker${c.reset}`);
  if (mode === 'cpu')   console.log(`\n  ${c.yellow}GPU detected? Force it:${c.reset} npm run docker -- --gpu`);
  if (mode !== 'cloud') console.log(`  ${c.yellow}Cloud model? Set llm_provider=openai-compatible in .env and rerun.${c.reset}`);
  console.log(`\n  Voice + Electron shell require the desktop install.\n`);

})().catch(err => { fail(err.message); });

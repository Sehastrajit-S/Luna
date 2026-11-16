// README screenshots of Luna's UI, driven over the Chrome DevTools Protocol.
// Usage: node readme-shots.mjs <chrome.exe> <profileDir> <outDir> <url> <heroConversationId>
import { spawn } from 'node:child_process'
import { writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

const [chrome, profileDir, outDir, url, heroId] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
const port = 9334
const proc = spawn(chrome, ['--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars', `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`, 'about:blank'], { stdio: 'ignore' })
const sleep = ms => new Promise(r => setTimeout(r, ms))

try {
  let target
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200)
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page') } catch {}
  }
  if (!target) throw new Error('Chrome did not start')

  const ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise(r => ws.addEventListener('open', r))
  let id = 0
  const pending = new Map()
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) } })
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
  const run = async expr => {
    const res = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })
    if (res.result?.exceptionDetails) throw new Error(`${expr}: ${res.result.exceptionDetails.text}`)
    return res.result?.result?.value
  }
  const shot = async (name, clip) => {
    const res = await send('Page.captureScreenshot', clip ? { format: 'png', clip: { ...clip, x: 0, y: 0, scale: 1 } } : { format: 'png' })
    writeFileSync(join(outDir, name), Buffer.from(res.result.data, 'base64'))
    console.log('saved', name)
  }

  // Stand-in for the Electron preload so desktop shots show the app window and
  // the desktop-only Settings → Server section. Servers listed are fictional.
  const desktopBridge = `
    window.electronAPI = {
      isElectron: true, apiBase: location.origin, apiToken: '', serverMode: 'remote',
      minimize() {}, maximize() {}, close() {}, toggleFullscreen() {},
      isMaximized: async () => false, isFullscreen: async () => false,
      onMaximizeChange: () => () => {}, onFullscreenChange: () => () => {}, onShowSettings: () => () => {},
      onUpdateStatus: () => () => {}, notify() {}, openUrl() {}, copyText() {}, openSettings() {}, quit() {},
      getLocalToken: async () => '',
      getServerConfig: async () => ({ mode: 'remote', url: '', hasToken: false }),
      discoverServers: async () => ({ servers: [
        { name: 'studio-pc', url: 'https://studio-pc.tail4f2a9.ts.net:8899', authorized: true, isSelf: false },
        { name: 'home-server', url: 'https://home-server.tail4f2a9.ts.net:8899', authorized: false, isSelf: false },
      ] }),
      testServer: async () => ({ ok: true, message: 'Connected to studio-pc. Your Tailscale account is trusted, no token needed.' }),
      saveServer: async () => ({ ok: true }),
    };`

  await send('Page.enable')
  const load = async (bridge) => {
    const added = bridge ? (await send('Page.addScriptToEvaluateOnNewDocument', { source: desktopBridge })).result.identifier : null
    await send('Page.navigate', { url })
    await sleep(3000)
    if (added) await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: added })
  }
  const nav = name => run(`document.querySelector('[data-nav="${name}"]').click()`)

  // ── Desktop ──
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1.5, mobile: false })
  await load(true)
  await run(`lunaOpenConversation(${heroId})`)
  await sleep(1200)
  await shot('desktop-chat.png')

  await run(`lunaOpenConversation(${Number(heroId) - 2})`)  // Q3 roadmap with attachments
  await sleep(1000)
  await shot('desktop-attachments.png')

  await nav('library'); await sleep(1200)
  await shot('desktop-library.png')

  await nav('settings'); await sleep(1500)
  await run(`(() => { const m = document.getElementById('server-mode'); m.value = 'remote'; m.dispatchEvent(new Event('change')) })()`)
  await sleep(800)
  await run(`document.querySelector('.server-option').click()`)
  await sleep(300)
  // Crop just below the Server section: the settings below come from the local .env.
  const serverBottom = await run(`Math.ceil(document.getElementById('server-connection').getBoundingClientRect().bottom + 24)`)
  await shot('desktop-server.png', { width: 1440, height: serverBottom })

  await nav('capabilities'); await sleep(1500)
  await shot('desktop-capabilities.png')

  // ── Phone ──
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true })
  await send('Emulation.setTouchEmulationEnabled', { enabled: true })
  await load(false)
  await run(`lunaOpenConversation(${heroId})`)
  await sleep(1200)
  await shot('mobile-chat.png')
  await run(`document.querySelector('.mobile-nav-btn').click()`); await sleep(500)
  await shot('mobile-menu.png')
  await nav('library'); await sleep(1200)
  await shot('mobile-library.png')

  ws.close()
} finally {
  proc.kill()
}

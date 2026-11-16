/**
 * Finds Luna servers on your tailnet, so connecting needs no copy-pasting.
 *
 * Asks the local Tailscale client for the devices on the tailnet, then probes
 * each online one at https://<device>.<tailnet>.ts.net:8899/api/remote/hello
 * (the port `luna serve --tailscale` uses). The server answers whether this
 * device would be let in: your own devices are, via Tailscale identity.
 */
'use strict'

const fs = require('fs')
const { execFile } = require('child_process')

const LUNA_PORT = 8899
const PROBE_TIMEOUT_MS = 3500
const WINDOWS_TAILSCALE = 'C:\\Program Files\\Tailscale\\tailscale.exe'

function tailscaleBinary() {
  if (process.platform === 'win32' && fs.existsSync(WINDOWS_TAILSCALE)) return WINDOWS_TAILSCALE
  if (process.platform === 'darwin' && fs.existsSync('/Applications/Tailscale.app/Contents/MacOS/Tailscale')) {
    return '/Applications/Tailscale.app/Contents/MacOS/Tailscale'
  }
  return 'tailscale'
}

function tailscaleStatus() {
  return new Promise(resolve => {
    execFile(tailscaleBinary(), ['status', '--json'], { timeout: 5000, windowsHide: true }, (error, stdout) => {
      if (error) {
        resolve({ error: error.code === 'ENOENT' ? 'Tailscale isn’t installed on this computer.' : 'Couldn’t read Tailscale status.' })
        return
      }
      try {
        const status = JSON.parse(stdout)
        if (status.BackendState !== 'Running') resolve({ error: 'Tailscale isn’t connected on this computer. Open Tailscale and sign in.' })
        else resolve({ status })
      } catch {
        resolve({ error: 'Couldn’t read Tailscale status.' })
      }
    })
  })
}

function devices(status) {
  const self = status.Self || {}
  const list = [{ ...self, isSelf: true }, ...Object.values(status.Peer || {}).map(p => ({ ...p, isSelf: false }))]
  return list
    .filter(d => d.DNSName && (d.isSelf || d.Online))
    .map(d => ({
      name: d.HostName || d.DNSName.split('.')[0],
      host: d.DNSName.replace(/\.$/, ''),
      isSelf: d.isSelf,
      sameOwner: d.UserID === self.UserID,
    }))
}

async function probe(device) {
  const url = `https://${device.host}:${LUNA_PORT}`
  try {
    const res = await fetch(`${url}/api/remote/hello`, { signal: AbortSignal.timeout(PROBE_TIMEOUT_MS) })
    if (!res.ok) return null
    const hello = await res.json()
    if (!hello?.luna) return null
    return { ...device, url, name: hello.name || device.name, authorized: Boolean(hello.authorized), via: hello.via || null }
  } catch {
    return null // not running Luna, not shared, or offline
  }
}

/** Returns { servers: [...] } or { error }. Other devices first, this computer last. */
async function discover() {
  const { status, error } = await tailscaleStatus()
  if (error) return { error, servers: [] }
  const found = (await Promise.all(devices(status).map(probe))).filter(Boolean)
  found.sort((a, b) => Number(a.isSelf) - Number(b.isSelf) || Number(b.authorized) - Number(a.authorized) || a.name.localeCompare(b.name))
  return { servers: found }
}

module.exports = { discover, LUNA_PORT }

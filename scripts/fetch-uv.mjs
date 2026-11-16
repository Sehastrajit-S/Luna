#!/usr/bin/env node
/**
 * Download the pinned `uv` binary for each target into interfaces/desktop/vendor/uv/<platform>-<arch>/,
 * verifying its SHA-256 against the release's checksum file. The desktop build ships these
 * so the installed app can set up its own Python on first launch.
 *
 * Usage: node scripts/fetch-uv.mjs win32-x64 [darwin-arm64 darwin-x64 linux-x64 linux-arm64]
 */
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const UV_VERSION = '0.13.6'
const TRIPLES = {
  'win32-x64': 'x86_64-pc-windows-msvc',
  'darwin-arm64': 'aarch64-apple-darwin',
  'darwin-x64': 'x86_64-apple-darwin',
  'linux-x64': 'x86_64-unknown-linux-gnu',
  'linux-arm64': 'aarch64-unknown-linux-gnu',
}

const root = resolve(import.meta.dirname, '..')
const vendor = join(root, 'interfaces', 'desktop', 'vendor', 'uv')
const targets = process.argv.slice(2)
if (!targets.length || targets.some(t => !TRIPLES[t])) {
  console.error(`Usage: node scripts/fetch-uv.mjs <${Object.keys(TRIPLES).join('|')}> ...`)
  process.exit(1)
}

function findFile(dir, name) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      const found = findFile(full, name)
      if (found) return found
    } else if (entry === name) {
      return full
    }
  }
  return null
}

async function download(url) {
  const res = await fetch(url, { redirect: 'follow' })
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`)
  return Buffer.from(await res.arrayBuffer())
}

for (const target of targets) {
  const triple = TRIPLES[target]
  const isWin = target.startsWith('win32')
  const exe = isWin ? 'uv.exe' : 'uv'
  const outDir = join(vendor, target)
  const marker = join(outDir, `.uv-${UV_VERSION}`)
  if (existsSync(join(outDir, exe)) && existsSync(marker)) {
    console.log(`uv ${UV_VERSION} for ${target}: already present`)
    continue
  }

  const archive = `uv-${triple}.${isWin ? 'zip' : 'tar.gz'}`
  const base = `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}`
  const [data, sumFile] = await Promise.all([download(`${base}/${archive}`), download(`${base}/${archive}.sha256`)])
  const expected = sumFile.toString().trim().split(/\s+/)[0].toLowerCase()
  const actual = createHash('sha256').update(data).digest('hex')
  if (actual !== expected) throw new Error(`Checksum mismatch for ${archive}: expected ${expected}, got ${actual}`)

  const tmp = mkdtempSync(join(tmpdir(), 'luna-uv-'))
  const archivePath = join(tmp, archive)
  writeFileSync(archivePath, data)
  // bsdtar (Windows 10+, macOS) reads zip and tar.gz; GNU tar on Linux only needs tar.gz here.
  execFileSync('tar', ['-xf', archivePath, '-C', tmp])
  const bin = findFile(tmp, exe)
  if (!bin) throw new Error(`${exe} not found in ${archive}`)

  rmSync(outDir, { recursive: true, force: true })
  mkdirSync(outDir, { recursive: true })
  copyFileSync(bin, join(outDir, exe))
  if (!isWin) chmodSync(join(outDir, exe), 0o755)
  writeFileSync(marker, `${UV_VERSION}\n`)
  rmSync(tmp, { recursive: true, force: true })
  console.log(`uv ${UV_VERSION} for ${target}: ok (sha256 ${actual.slice(0, 12)}…)`)
}

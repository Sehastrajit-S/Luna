/**
 * Reads and writes the app's .env file.
 *
 * Design note: writeEnv() merges into the EXISTING file's raw lines rather
 * than regenerating the whole file from a fixed template. A template-based
 * rewrite silently drops any key the template doesn't know about the moment
 * anyone saves anything — a real bug hit in production here, since every
 * new setting added over time needs a matching template update or it gets
 * wiped out on the next unrelated save. Merging into existing lines means a
 * key nobody's touched today survives untouched, forever, with zero upkeep.
 */
'use strict'

const fs = require('fs')
const path = require('path')

/**
 * Keys writeEnv() is allowed to change. Anything not listed here is passed
 * through untouched even if the caller's `next` object happens to include
 * it — the allowlist is what makes this safe to expose to a renderer.
 */
const WRITABLE_KEYS = [
  'llm_provider',
  'ollama_base_url',
  'ollama_model',
  'openai_api_key',
  'openai_model',
]

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

function readEnv(envPath) {
  try {
    return parseEnv(fs.readFileSync(envPath, 'utf8'))
  } catch {
    return {}
  }
}

/**
 * Merge `next` into the existing file, line by line, only for keys in
 * WRITABLE_KEYS. Existing lines for other keys, comments, and formatting
 * are left exactly as they were. New writable keys not already present are
 * appended at the end.
 */
function writeEnv(envPath, next) {
  const existingText = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : ''
  const lines = existingText.split(/\r?\n/)
  const seen = new Set()

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line || line.startsWith('#') || !line.includes('=')) continue
    const key = line.slice(0, line.indexOf('=')).trim()
    if (WRITABLE_KEYS.includes(key) && Object.prototype.hasOwnProperty.call(next, key)) {
      lines[i] = `${key}=${String(next[key] ?? '').trim()}`
      seen.add(key)
    }
  }

  for (const key of WRITABLE_KEYS) {
    if (Object.prototype.hasOwnProperty.call(next, key) && !seen.has(key)) {
      lines.push(`${key}=${String(next[key] ?? '').trim()}`)
    }
  }

  fs.mkdirSync(path.dirname(envPath), { recursive: true })
  fs.writeFileSync(envPath, lines.join('\n'), 'utf8')
  return readEnv(envPath)
}

module.exports = { readEnv, writeEnv, WRITABLE_KEYS }

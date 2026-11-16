// Standalone mobile: stream chat directly to AI providers without a Luna backend.

export type DirectProvider = 'groq' | 'openai' | 'anthropic'

export interface DirectChatConfig {
  provider: DirectProvider
  apiKey: string
  model: string
}

interface ChatMsg { role: 'user' | 'assistant' | 'system'; content: string }

const PROVIDERS: Record<DirectProvider, { baseUrl: string; defaultModel: string; format: 'openai' | 'anthropic' }> = {
  groq: {
    baseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
    format: 'openai',
  },
  openai: {
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o-mini',
    format: 'openai',
  },
  anthropic: {
    baseUrl: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-haiku-4-5-20251001',
    format: 'anthropic',
  },
}

// Global singleton — set once at boot
let _config: DirectChatConfig | null = null

export function initDirectChat(config: DirectChatConfig) { _config = config }
export function getDirectConfig(): DirectChatConfig | null { return _config }
export function clearDirectChat() { _config = null }
export function isStandaloneMode(): boolean { return _config !== null }

// ── Streaming ──────────────────────────────────────────────────────────────────

export async function* streamDirect(
  history: ChatMsg[],
  userMessage: string,
): AsyncGenerator<string> {
  if (!_config) throw new Error('No direct chat config')
  const { provider, apiKey, model } = _config
  const prov = PROVIDERS[provider]
  const resolvedModel = model || prov.defaultModel

  if (prov.format === 'openai') {
    yield* streamOpenAICompat(prov.baseUrl, apiKey, resolvedModel, history, userMessage)
  } else {
    yield* streamAnthropic(apiKey, resolvedModel, history, userMessage)
  }
}

async function* streamOpenAICompat(
  baseUrl: string,
  apiKey: string,
  model: string,
  history: ChatMsg[],
  userMessage: string,
): AsyncGenerator<string> {
  const messages = [
    { role: 'system', content: 'You are Luna, a thoughtful and helpful AI companion.' },
    ...history,
    { role: 'user', content: userMessage },
  ]

  const resp = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ model, messages, stream: true }),
  })

  if (!resp.ok) throw new Error(`${provider_label(baseUrl)} ${resp.status}: ${await resp.text()}`)

  yield* parseSseDelta(resp, c => c.choices?.[0]?.delta?.content)
}

async function* streamAnthropic(
  apiKey: string,
  model: string,
  history: ChatMsg[],
  userMessage: string,
): AsyncGenerator<string> {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model,
      max_tokens: 2048,
      system: 'You are Luna, a thoughtful and helpful AI companion.',
      messages: [...history, { role: 'user', content: userMessage }],
      stream: true,
    }),
  })

  if (!resp.ok) throw new Error(`Anthropic ${resp.status}: ${await resp.text()}`)

  yield* parseSseDelta(resp, c => c.type === 'content_block_delta' ? c.delta?.text : undefined)
}

// Read an SSE stream and yield the string extracted by `extract` from each data JSON
async function* parseSseDelta(
  resp: Response,
  extract: (json: any) => string | undefined,
): AsyncGenerator<string> {
  const reader  = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6)
      if (raw === '[DONE]') return
      try {
        const token = extract(JSON.parse(raw))
        if (token) yield token
      } catch {}
    }
  }
}

function provider_label(baseUrl: string) {
  if (baseUrl.includes('groq')) return 'Groq'
  if (baseUrl.includes('openai')) return 'OpenAI'
  return 'API'
}

// ── Default models per provider ────────────────────────────────────────────────

export const PROVIDER_OPTIONS: Array<{ value: DirectProvider; label: string; models: string[] }> = [
  {
    value: 'groq',
    label: 'Groq (free, fast)',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
  },
  {
    value: 'openai',
    label: 'OpenAI',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
  },
  {
    value: 'anthropic',
    label: 'Anthropic',
    models: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8'],
  },
]

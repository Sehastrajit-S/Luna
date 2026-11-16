// BASE is a mutable variable so it can be updated at boot time on mobile.
// Electron: set from preload bridge (apiBase).
// Mobile (Capacitor): set from Preferences at app startup via initApiBase().
// Web/dev: empty string → same-origin (FastAPI serves the frontend).
let BASE: string = (window as any).electronAPI?.apiBase ?? ''

export function initApiBase(url: string) {
  BASE = url.replace(/\/$/, '')
}

export function getApiBase(): string {
  return BASE
}

// Access token for a remote server (`luna serve --tailscale`). A server on the
// same machine accepts requests without it; a proxied one answers 401.
let TOKEN = ''

export function initApiToken(token: string) {
  TOKEN = token.trim()
}

export function authHeaders(): Record<string, string> {
  return TOKEN ? { 'X-Luna-Token': TOKEN } : {}
}

function isServerApiUrl(url: string): boolean {
  if (!BASE) return false
  try {
    const target = new URL(url, location.href)
    return target.origin === new URL(BASE).origin && target.pathname.startsWith('/api/')
  } catch {
    return false
  }
}

/** For EventSource URLs, which can't carry headers. */
export function withAuthQuery(url: string): string {
  if (!TOKEN || !isServerApiUrl(url)) return url
  const target = new URL(url, location.href)
  target.searchParams.set('luna_token', TOKEN)
  return target.toString()
}

/**
 * Checks a server before saving it: health is public, settings needs the
 * token when the server is remote, so passing both proves the pair works.
 */
export async function testServer(base: string, token: string): Promise<{ ok: boolean; message: string }> {
  try {
    const health = await fetch(`${base}/api/system/health`, { signal: AbortSignal.timeout(6000) })
    if (!health.ok) return { ok: false, message: `Server returned ${health.status}` }
  } catch (e: any) {
    return {
      ok: false,
      message: e?.name === 'TimeoutError'
        ? 'Connection timed out. Is the server reachable from this device (same Wi-Fi or tailnet)?'
        : `Cannot reach server: ${e?.message ?? e}`,
    }
  }
  const headers: Record<string, string> = token.trim() ? { 'X-Luna-Token': token.trim() } : {}
  try {
    const settings = await fetch(`${base}/api/settings`, { headers, signal: AbortSignal.timeout(6000) })
    if (settings.status === 401 || settings.status === 403) {
      return { ok: false, message: token.trim() ? 'Server reached, but it rejected the access token.' : 'Server reached. It needs the access token printed by `luna serve --tailscale`.' }
    }
  } catch {
    // Older servers or blocked settings: health already proved reachability.
  }
  return { ok: true, message: 'Connected. Server is reachable.' }
}

let fetchPatched = false

/** Adds the token to every fetch() aimed at the server's /api, wherever it's called from. */
export function installAuthFetch() {
  if (fetchPatched) return
  fetchPatched = true
  const nativeFetch = window.fetch.bind(window)
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url
    if (!TOKEN || !isServerApiUrl(url)) return nativeFetch(input, init)
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
    if (!headers.has('X-Luna-Token')) headers.set('X-Luna-Token', TOKEN)
    return nativeFetch(input, { ...init, headers })
  }
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts.headers },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  // Tool confirmation
  confirmTool: (confirm_id: string, approved: boolean) =>
    request<any>(`/api/chat/confirm/${confirm_id}`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    }),

  // Chat
  listConversations: () => request<any[]>('/api/chat/conversations'),
  getConversation: (id: number) => request<any>(`/api/chat/conversations/${id}`),
  getChatContext: () => request<{ active_conversation_id: number | null }>('/api/chat/context'),
  setChatContext: (active_conversation_id: number | null) =>
    request<{ active_conversation_id: number | null }>('/api/chat/context', {
      method: 'POST',
      body: JSON.stringify({ active_conversation_id }),
    }),
  deleteConversation: (id: number) =>
    request<any>(`/api/chat/conversations/${id}`, { method: 'DELETE' }),

  // Memory
  getFacts: (category?: string) =>
    request<any[]>(`/api/memory/facts${category ? `?category=${category}` : ''}`),
  addFact: (data: { category: string; content: string; confidence?: number }) =>
    request<any>('/api/memory/facts', { method: 'POST', body: JSON.stringify(data) }),
  deleteFact: (id: number) =>
    request<any>(`/api/memory/facts/${id}`, { method: 'DELETE' }),
  searchMemory: (q: string) => request<any>(`/api/memory/search?q=${encodeURIComponent(q)}`),
  compactMemory: () => request<{ ok: boolean; removed: number }>('/api/memory/compact', { method: 'POST' }),
  getPersonality: () => request<any>('/api/memory/personality'),
  getActivities: () => request<any[]>('/api/memory/activities'),

  // Calendar
  getTasks: (completed?: boolean) =>
    request<any[]>(`/api/calendar/tasks${completed !== undefined ? `?completed=${completed}` : ''}`),
  createTask: (data: any) =>
    request<any>('/api/calendar/tasks', { method: 'POST', body: JSON.stringify(data) }),
  completeTask: (id: number) =>
    request<any>(`/api/calendar/tasks/${id}/complete`, { method: 'PATCH' }),
  deleteTask: (id: number) =>
    request<any>(`/api/calendar/tasks/${id}`, { method: 'DELETE' }),

  getEvents: (upcomingOnly?: boolean) =>
    request<any[]>(`/api/calendar/events${upcomingOnly ? '?upcoming_only=true' : ''}`),
  createEvent: (data: any) =>
    request<any>('/api/calendar/events', { method: 'POST', body: JSON.stringify(data) }),
  deleteEvent: (id: number) =>
    request<any>(`/api/calendar/events/${id}`, { method: 'DELETE' }),

  // Spotify
  spotifyStatus:  () => request<any>('/api/spotify/status'),
  spotifyAuthUrl: () => request<{ url: string }>('/api/spotify/auth-url'),
  spotifyPlay:    (query?: string) => request<any>('/api/spotify/play', { method: 'POST', body: JSON.stringify({ query }) }),
  spotifyPause:   () => request<any>('/api/spotify/pause', { method: 'POST' }),
  spotifyNext:    () => request<any>('/api/spotify/next',  { method: 'POST' }),
  spotifyPrev:    () => request<any>('/api/spotify/prev',  { method: 'POST' }),

  // Health integrations
  healthStatus: () => request<any>('/api/health/status'),

  // System
  launchApp: (name: string) =>
    request<any>('/api/system/launch', { method: 'POST', body: JSON.stringify({ name }) }),
  getProactive: () => request<{ messages: string[] }>('/api/system/proactive'),
  health: () => request<any>('/api/system/health'),

  // Agent platform
  getAgentSkills: () => request<any[]>('/api/agent/skills'),
  getAgentAudit: (limit = 100) => request<any[]>(`/api/agent/audit?limit=${limit}`),
  getAgentPermissions: () => request<any>('/api/agent/permissions'),
  setAgentPermission: (tool: string, mode: 'allow' | 'confirm' | 'block') =>
    request<any>(`/api/agent/permissions/${encodeURIComponent(tool)}`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    }),
  getWorkspace: (path = '') =>
    request<any[]>(`/api/agent/workspace${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  writeWorkspace: (path: string, content: string) =>
    request<any>('/api/agent/workspace/write', {
      method: 'POST',
      body: JSON.stringify({ path, content }),
    }),
  getAgentTasks: () => request<any[]>('/api/agent/tasks'),
  createAgentTask: (description: string) =>
    request<any>('/api/agent/tasks', {
      method: 'POST',
      body: JSON.stringify({ description }),
    }),
  getBrowserStatus: () => request<any>('/api/agent/browser/status'),

  // Voice / Vosk
  getVoskStatus: () => request<{ vosk_ready: boolean; vosk_package: boolean }>('/api/voice/vosk-status'),
  getElevenLabsVoices: () => request<{ voices: { voice_id: string; name: string }[] }>('/api/voice/elevenlabs-voices'),

  // Coding agent settings
  getCodingSettings: () => request<any>('/api/coding/settings'),
  updateCodingSettings: (data: Record<string, unknown>) =>
    request<any>('/api/coding/settings', { method: 'POST', body: JSON.stringify(data) }),
  getCodingModels: () => request<{ models: string[]; current: string }>('/api/coding/models'),
  getCodingStatus: () => request<any>('/api/coding/status'),
}

export async function* streamVoskInstall(): AsyncGenerator<{ line?: string; done?: boolean; error?: string }> {
  const res = await fetch(`${BASE}/api/voice/install-vosk`, { method: 'POST' })
  if (!res.ok || !res.body) throw new Error('Install failed')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)) } catch {}
      }
    }
  }
}

export async function* streamChat(
  message: string,
  conversationId?: number
): AsyncGenerator<{ type: string; [key: string]: any }> {
  const res = await fetch(`${BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })

  if (!res.ok || !res.body) throw new Error('Stream failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6))
        } catch {
          // skip malformed
        }
      }
    }
  }
}

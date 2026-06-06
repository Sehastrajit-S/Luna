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

export function authHeaders(): Record<string, string> {
  return {}
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

  // Vision
  getVisionStatus: () => request<{ moondream_installed: boolean; ollama_available: boolean }>('/api/vision/status'),

  // Voice / Vosk
  getVoskStatus: () => request<{ vosk_ready: boolean; vosk_package: boolean }>('/api/voice/vosk-status'),

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

export async function* streamMoondreamInstall(): AsyncGenerator<{ line?: string; done?: boolean; ok?: boolean; error?: string }> {
  const res = await fetch(`${BASE}/api/vision/install`, { method: 'POST' })
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

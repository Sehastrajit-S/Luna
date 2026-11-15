const baseUrl = () => window.electronAPI?.apiBase ?? ''

export function lunaUrl(path: string) {
  return `${baseUrl()}${path}`
}

export async function fetchLuna<T>(path: string): Promise<T> {
  const response = await fetch(lunaUrl(path))
  if (!response.ok) throw new Error(`${path} ${response.status} ${response.statusText}`)
  return response.json()
}

const lunaCache = new Map<string, { expires: number; data: unknown }>()
const lunaInflight = new Map<string, Promise<unknown>>()

export async function fetchLunaCached<T>(path: string, ttlMs: number): Promise<T> {
  const now = Date.now()
  const cached = lunaCache.get(path)
  if (cached && cached.expires > now) return cached.data as T

  const inflight = lunaInflight.get(path)
  if (inflight) return inflight as Promise<T>

  const request = fetchLuna<T>(path)
    .then(data => {
      lunaCache.set(path, { data, expires: Date.now() + ttlMs })
      return data
    })
    .finally(() => lunaInflight.delete(path))

  lunaInflight.set(path, request)
  return request
}

export function asArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[]
  if (data && typeof data === 'object' && Array.isArray((data as any).value)) {
    return (data as any).value as T[]
  }
  return []
}

import { Capacitor } from '@capacitor/core'
import { Preferences } from '@capacitor/preferences'

export const isMobile   = Capacitor.isNativePlatform()
export const isElectron = !isMobile && !!(window as any).electronAPI
export const isWeb      = !isMobile && !isElectron

const SERVER_URL_KEY  = 'luna_server_url'
const API_KEY_KEY     = 'luna_direct_api_key'
const API_PROVIDER_KEY = 'luna_direct_provider'
const API_MODEL_KEY   = 'luna_direct_model'

// ── Server URL (connect-to-PC mode) ───────────────────────────────────────────

export async function getServerUrl(): Promise<string> {
  if (!isMobile) return (window as any).electronAPI?.apiBase ?? ''
  const { value } = await Preferences.get({ key: SERVER_URL_KEY })
  return value ?? ''
}

export async function setServerUrl(url: string): Promise<void> {
  await Preferences.set({ key: SERVER_URL_KEY, value: url.replace(/\/$/, '') })
}

export async function clearServerUrl(): Promise<void> {
  await Preferences.remove({ key: SERVER_URL_KEY })
}

// ── Standalone / direct AI mode ────────────────────────────────────────────────

export async function getDirectApiKey(): Promise<string> {
  const { value } = await Preferences.get({ key: API_KEY_KEY })
  return value ?? ''
}

export async function setDirectApiKey(key: string): Promise<void> {
  await Preferences.set({ key: API_KEY_KEY, value: key.trim() })
}

export async function getDirectProvider(): Promise<string> {
  const { value } = await Preferences.get({ key: API_PROVIDER_KEY })
  return value ?? 'groq'
}

export async function setDirectProvider(p: string): Promise<void> {
  await Preferences.set({ key: API_PROVIDER_KEY, value: p })
}

export async function getDirectModel(): Promise<string> {
  const { value } = await Preferences.get({ key: API_MODEL_KEY })
  return value ?? ''
}

export async function setDirectModel(m: string): Promise<void> {
  await Preferences.set({ key: API_MODEL_KEY, value: m })
}

export async function clearDirectConfig(): Promise<void> {
  await Promise.all([
    Preferences.remove({ key: API_KEY_KEY }),
    Preferences.remove({ key: API_PROVIDER_KEY }),
    Preferences.remove({ key: API_MODEL_KEY }),
  ])
}

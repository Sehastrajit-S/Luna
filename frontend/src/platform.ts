import { Capacitor } from '@capacitor/core'
import { Preferences } from '@capacitor/preferences'

export const isMobile   = Capacitor.isNativePlatform()
export const isElectron = !isMobile && !!(window as any).electronAPI
export const isWeb      = !isMobile && !isElectron

// Keys stored in Capacitor Preferences (mobile) / localStorage (web fallback)
const SERVER_URL_KEY = 'luna_server_url'

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

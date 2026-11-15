import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, CheckCircle, ExternalLink, Loader2, Key, Webhook, Info } from 'lucide-react'
import { siSpotify, siTelegram, siDiscord, siGithub, siFitbit, siGarmin, siSamsung, siApple } from 'simple-icons'
import { api } from '../../api/client'

// ── Auth type ──────────────────────────────────────────────────────────────────
// oauth          - credential fields + "Sign in with X" button (backend handles callback)
// apikey         - plain credential/key fields, save to env
// webhook        - shows Luna endpoint URL + optional secret
// info           - no config, just install instructions

type AuthType = 'oauth' | 'apikey' | 'webhook' | 'info'

// ── Simple-icons wrapper ───────────────────────────────────────────────────────

function SiIcon({ icon, bg, iconColor, size = 28 }: { icon: { path: string; hex: string }; bg?: string; iconColor?: string; size?: number }) {
  const brandFill = `#${icon.hex}`
  const fill = iconColor ?? brandFill
  const inner = Math.round(size * 0.6)
  const isDark = icon.hex === '000000' || icon.hex === '181717' || icon.hex === '1428A0'
  const defaultBg = isDark ? '#1e1e1e' : `${brandFill}18`
  return (
    <span className="inline-flex items-center justify-center rounded-lg shrink-0"
      style={{ width: size, height: size, background: bg ?? defaultBg, border: `1px solid ${iconColor ? '#ffffff20' : brandFill + '30'}` }}>
      <svg viewBox="0 0 24 24" width={inner} height={inner} fill={fill}>
        <path d={icon.path} />
      </svg>
    </span>
  )
}

// ── SVG / image logos ─────────────────────────────────────────────────────────

// Multi-colour logos (not in simple-icons)
const GoogleWorkspaceLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
)

const Microsoft365Logo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <rect x="1"  y="1"  width="10" height="10" rx="1" fill="#F25022"/>
    <rect x="13" y="1"  width="10" height="10" rx="1" fill="#7FBA00"/>
    <rect x="1"  y="13" width="10" height="10" rx="1" fill="#00A4EF"/>
    <rect x="13" y="13" width="10" height="10" rx="1" fill="#FFB900"/>
  </svg>
)

const SlackLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
    <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#2EB67D"/>
    <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.268 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#ECB22E"/>
    <path d="M15.165 18.958a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.268a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#36C5F0"/>
  </svg>
)

// Simple-icons based
const SpotifyLogo      = () => <SiIcon icon={siSpotify} />
const TelegramLogo     = () => <SiIcon icon={siTelegram} />
const DiscordLogo      = () => <SiIcon icon={siDiscord} />
const GitHubLogo       = () => <SiIcon icon={siGithub} bg="#1e1e1e" iconColor="#ffffff" />
const FitbitLogo       = () => <SiIcon icon={siFitbit} />
const GarminLogo       = () => <SiIcon icon={siGarmin} bg="#1a2a3a" iconColor="#007CC3" />
const SamsungHealthLogo = () => <SiIcon icon={siSamsung} />
const AppleHealthLogo  = () => <SiIcon icon={siApple} bg="#f0f0f0" iconColor="#000000" />

// PNG for Google Fit (no simple-icons equivalent)
const GoogleFitLogo = () => <img src={`${import.meta.env.BASE_URL}images/google-fit.png`} alt="Google Fit" className="w-7 h-7 object-contain" />

// Custom SVGs for remaining brands
const VSCodeLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z" fill="#007ACC"/>
  </svg>
)

const OuraLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <circle cx="12" cy="12" r="9" fill="none" stroke="#1A1A2E" strokeWidth="3"/>
    <circle cx="12" cy="12" r="5" fill="none" stroke="#6C63FF" strokeWidth="2.5"/>
    <circle cx="12" cy="12" r="1.5" fill="#6C63FF"/>
  </svg>
)

const WithingsLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <path d="M2 17L6.5 7 12 14l5.5-7L22 17" stroke="#00A878" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

const WeatherLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <circle cx="12" cy="12" r="4" fill="#F6A623"/>
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="#F6A623" strokeWidth="2" strokeLinecap="round"/>
  </svg>
)

const NewsLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <rect x="2" y="3" width="20" height="18" rx="2" fill="none" stroke="#E85D04" strokeWidth="1.5"/>
    <path d="M6 8h12M6 12h12M6 16h7" stroke="#E85D04" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const StocksLogo = () => (
  <svg viewBox="0 0 24 24" width={28} height={28}>
    <polyline points="3,17 8,11 13,14 20,6" fill="none" stroke="#00BFA5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M17 6h3v3" fill="none" stroke="#00BFA5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// ── Integration definitions ───────────────────────────────────────────────────

export interface Field { key: string; label: string; type: 'text' | 'password'; placeholder: string }

export interface Integration {
  id: string
  name: string
  category: 'workspace' | 'music' | 'communication' | 'health' | 'data' | 'developer'
  authType: AuthType
  description: string
  logo: React.ReactNode
  helpText: string
  helpUrl: string
  fields: Field[]
  oauthPlatform?: string   // for health OAuth: platform name passed to /api/health/oauth/authorize/{platform}
  oauthType?: 'spotify' | 'health'
  webhookPath?: string     // for webhook type: the Luna endpoint URL
}

const BASE = window.electronAPI?.apiBase ?? 'http://127.0.0.1:8899'

export const INTEGRATIONS: Integration[] = [
  // ── Workspace ──────────────────────────────────────────────────────────────
  {
    id: 'google_workspace', name: 'Google Workspace', category: 'workspace', authType: 'apikey',
    description: 'Gmail, Calendar, Drive & Docs',
    logo: <GoogleWorkspaceLogo />,
    helpText: '1. Go to console.cloud.google.com\n2. Create a project and enable Gmail, Calendar, Drive APIs\n3. Create OAuth 2.0 credentials (Desktop app)\n4. Copy Client ID and Secret\n5. Run the OAuth flow to get your refresh token',
    helpUrl: 'https://console.cloud.google.com',
    fields: [
      { key: 'google_workspace_client_id',     label: 'Client ID',      type: 'text',     placeholder: 'your-id.apps.googleusercontent.com' },
      { key: 'google_workspace_client_secret', label: 'Client Secret',  type: 'password', placeholder: 'GOCSPX-...' },
      { key: 'google_workspace_refresh_token', label: 'Refresh Token',  type: 'password', placeholder: 'obtained via OAuth flow' },
    ],
  },
  {
    id: 'microsoft_365', name: 'Microsoft 365', category: 'workspace', authType: 'apikey',
    description: 'Outlook, Teams, Calendar & OneDrive',
    logo: <Microsoft365Logo />,
    helpText: '1. Go to portal.azure.com → App registrations\n2. New registration → add Mail, Calendar, Files.ReadWrite permissions\n3. Create a client secret\n4. Copy Client ID, Tenant ID, and Secret',
    helpUrl: 'https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps',
    fields: [
      { key: 'microsoft_workspace_client_id',     label: 'Client ID',      type: 'text',     placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
      { key: 'microsoft_workspace_client_secret', label: 'Client Secret',  type: 'password', placeholder: 'your-client-secret' },
      { key: 'microsoft_workspace_tenant_id',     label: 'Tenant ID',      type: 'text',     placeholder: 'common' },
      { key: 'microsoft_workspace_refresh_token', label: 'Refresh Token',  type: 'password', placeholder: 'obtained via OAuth flow' },
    ],
  },
  // ── Music ──────────────────────────────────────────────────────────────────
  {
    id: 'spotify', name: 'Spotify', category: 'music', authType: 'oauth', oauthType: 'spotify',
    description: 'Music playback and now-playing',
    logo: <SpotifyLogo />,
    helpText: '1. Go to developer.spotify.com/dashboard\n2. Create an app\n3. Add redirect URI: http://127.0.0.1:8899/api/spotify/callback\n4. Copy Client ID and Secret below, then click Connect',
    helpUrl: 'https://developer.spotify.com/dashboard',
    fields: [
      { key: 'spotify_client_id',     label: 'Client ID',     type: 'text',     placeholder: 'your-spotify-client-id' },
      { key: 'spotify_client_secret', label: 'Client Secret', type: 'password', placeholder: 'your-spotify-client-secret' },
    ],
  },
  // ── Communication ──────────────────────────────────────────────────────────
  {
    id: 'telegram', name: 'Telegram', category: 'communication', authType: 'apikey',
    description: 'Bot messaging and notifications',
    logo: <TelegramLogo />,
    helpText: '1. Open Telegram\n2. Search for @BotFather\n3. Send /newbot and follow the prompts\n4. Copy the bot token you receive',
    helpUrl: 'https://t.me/BotFather',
    fields: [{ key: 'telegram_bot_token', label: 'Bot Token', type: 'password', placeholder: '123456:ABC-DEF...' }],
  },
  {
    id: 'discord', name: 'Discord', category: 'communication', authType: 'apikey',
    description: 'Community server bot',
    logo: <DiscordLogo />,
    helpText: '1. Go to discord.com/developers/applications\n2. New Application → Bot section\n3. Copy Token\n4. Copy Public Key from General Information for interaction verification',
    helpUrl: 'https://discord.com/developers/applications',
    fields: [
      { key: 'discord_bot_token',  label: 'Bot Token',  type: 'password', placeholder: 'your-discord-bot-token' },
      { key: 'discord_public_key', label: 'Public Key', type: 'text',     placeholder: 'your-public-key' },
    ],
  },
  {
    id: 'slack', name: 'Slack', category: 'communication', authType: 'apikey',
    description: 'Team workspace messaging',
    logo: <SlackLogo />,
    helpText: '1. Go to api.slack.com/apps → Create New App\n2. Add Bot Token Scopes: chat:write, channels:read\n3. Install to workspace\n4. Copy Bot Token and Signing Secret',
    helpUrl: 'https://api.slack.com/apps',
    fields: [
      { key: 'slack_bot_token',      label: 'Bot Token',      type: 'password', placeholder: 'xoxb-...' },
      { key: 'slack_signing_secret', label: 'Signing Secret', type: 'password', placeholder: 'your-signing-secret' },
    ],
  },
  {
    id: 'github', name: 'GitHub', category: 'communication', authType: 'apikey',
    description: 'Code repos and webhook events',
    logo: <GitHubLogo />,
    helpText: '1. Go to github.com/settings/tokens\n2. Generate new token (classic)\n3. Select repo and notifications scopes\n4. Copy the token',
    helpUrl: 'https://github.com/settings/tokens',
    fields: [
      { key: 'github_token',          label: 'Personal Access Token', type: 'password', placeholder: 'ghp_...' },
      { key: 'github_default_repo',   label: 'Default Repo (optional)', type: 'text',   placeholder: 'owner/repo' },
      { key: 'github_webhook_secret', label: 'Webhook Secret (optional)', type: 'password', placeholder: 'random secret' },
    ],
  },
  // ── Health ─────────────────────────────────────────────────────────────────
  {
    id: 'fitbit', name: 'Fitbit', category: 'health', authType: 'oauth', oauthType: 'health', oauthPlatform: 'fitbit',
    description: 'Steps, sleep, heart rate',
    logo: <FitbitLogo />,
    helpText: '1. Go to dev.fitbit.com → Create App (Personal)\n2. Set OAuth 2.0 redirect URI to:\n   http://127.0.0.1:8899/api/health/oauth/callback\n3. Copy Client ID and Secret, then click Connect',
    helpUrl: 'https://dev.fitbit.com/apps/new',
    fields: [
      { key: 'fitbit_client_id',     label: 'Client ID',     type: 'text',     placeholder: 'your-fitbit-client-id' },
      { key: 'fitbit_client_secret', label: 'Client Secret', type: 'password', placeholder: 'your-fitbit-client-secret' },
    ],
  },
  {
    id: 'google_fit', name: 'Google Fit', category: 'health', authType: 'oauth', oauthType: 'health', oauthPlatform: 'google_fit',
    description: 'Activity, calories, heart rate',
    logo: <GoogleFitLogo />,
    helpText: '1. Go to console.cloud.google.com\n2. Enable the Fitness API\n3. Create OAuth 2.0 credentials\n4. Set redirect URI to:\n   http://127.0.0.1:8899/api/health/oauth/callback\n5. Copy Client ID and Secret, then click Connect',
    helpUrl: 'https://console.cloud.google.com',
    fields: [
      { key: 'google_fit_client_id',     label: 'Client ID',     type: 'text',     placeholder: 'your-id.apps.googleusercontent.com' },
      { key: 'google_fit_client_secret', label: 'Client Secret', type: 'password', placeholder: 'GOCSPX-...' },
    ],
  },
  {
    id: 'oura', name: 'Oura Ring', category: 'health', authType: 'apikey',
    description: 'Sleep, readiness, HRV',
    logo: <OuraLogo />,
    helpText: '1. Go to cloud.ouraring.com/user/settings\n2. Personal Access Tokens section\n3. Generate a new token\n4. Copy it below',
    helpUrl: 'https://cloud.ouraring.com/user/settings',
    fields: [{ key: 'oura_api_key', label: 'Personal Access Token', type: 'password', placeholder: 'your-oura-token' }],
  },
  {
    id: 'withings', name: 'Withings', category: 'health', authType: 'oauth', oauthType: 'health', oauthPlatform: 'withings',
    description: 'Weight, blood pressure, body composition',
    logo: <WithingsLogo />,
    helpText: '1. Go to developer.withings.com\n2. Create an application\n3. Set redirect URI to:\n   http://127.0.0.1:8899/api/health/oauth/callback\n4. Copy Client ID and Secret, then click Connect',
    helpUrl: 'https://developer.withings.com',
    fields: [
      { key: 'withings_client_id',     label: 'Client ID',     type: 'text',     placeholder: 'your-withings-client-id' },
      { key: 'withings_client_secret', label: 'Client Secret', type: 'password', placeholder: 'your-withings-client-secret' },
    ],
  },
  {
    id: 'garmin', name: 'Garmin', category: 'health', authType: 'apikey',
    description: 'GPS, steps, heart rate, sleep',
    logo: <GarminLogo />,
    helpText: 'Enter your Garmin Connect account credentials. Luna uses these to fetch your activity data directly from Garmin Connect.',
    helpUrl: 'https://connect.garmin.com',
    fields: [
      { key: 'garmin_email',    label: 'Garmin Email',    type: 'text',     placeholder: 'you@example.com' },
      { key: 'garmin_password', label: 'Garmin Password', type: 'password', placeholder: 'your password' },
    ],
  },
  {
    id: 'apple_health', name: 'Apple Health', category: 'health', authType: 'webhook',
    description: 'iOS health data via webhook',
    logo: <AppleHealthLogo />,
    webhookPath: '/api/health/webhook/apple',
    helpText: '1. Install "Health Auto Export" on iPhone\n2. Set webhook URL to:\n   http://YOUR_IP:8899/api/health/webhook/apple\n3. Set the secret below as the Authorization token in the app',
    helpUrl: 'https://apps.apple.com/app/health-auto-export-json-csv/id1477944755',
    fields: [{ key: 'health_webhook_secret', label: 'Webhook Secret', type: 'password', placeholder: 'choose a random secret' }],
  },
  {
    id: 'samsung_health', name: 'Samsung Health', category: 'health', authType: 'webhook',
    description: 'Android health data via webhook',
    logo: <SamsungHealthLogo />,
    webhookPath: '/api/health/webhook/samsung',
    helpText: '1. Use a compatible Samsung Health exporter app\n2. Set the webhook URL to:\n   http://YOUR_IP:8899/api/health/webhook/samsung\n3. Set this secret in the Authorization header',
    helpUrl: 'https://health.samsung.com',
    fields: [{ key: 'health_webhook_secret', label: 'Webhook Secret', type: 'password', placeholder: 'shared secret' }],
  },
  // ── Data ───────────────────────────────────────────────────────────────────
  {
    id: 'weather', name: 'OpenWeather', category: 'data', authType: 'apikey',
    description: 'Current conditions and forecast',
    logo: <WeatherLogo />,
    helpText: '1. Sign up at openweathermap.org\n2. Copy your API key from the profile page\n3. Set your city or coordinates below',
    helpUrl: 'https://openweathermap.org/api',
    fields: [
      { key: 'open_weather',     label: 'API Key',   type: 'password', placeholder: 'your-openweather-key' },
      { key: 'weather_city',    label: 'City',      type: 'text',     placeholder: 'New York' },
      { key: 'weather_lat',     label: 'Latitude',  type: 'text',     placeholder: '40.7128' },
      { key: 'weather_lon',     label: 'Longitude', type: 'text',     placeholder: '-74.0060' },
      { key: 'weather_timezone',label: 'Timezone',  type: 'text',     placeholder: 'America/New_York' },
    ],
  },
  {
    id: 'news', name: 'News API', category: 'data', authType: 'apikey',
    description: 'Top headlines and articles',
    logo: <NewsLogo />,
    helpText: '1. Sign up at thenewsapi.com\n2. Copy your API token from the dashboard\nFree tier includes 100 requests/day.',
    helpUrl: 'https://www.thenewsapi.com',
    fields: [{ key: 'the_news_api', label: 'API Token', type: 'password', placeholder: 'your-news-api-token' }],
  },
  {
    id: 'stocks', name: 'Alpha Vantage', category: 'data', authType: 'apikey',
    description: 'Stock prices and market data',
    logo: <StocksLogo />,
    helpText: '1. Go to alphavantage.co\n2. Click "Get Free API Key"\n3. Copy it below\nFree tier: 25 requests/day.',
    helpUrl: 'https://www.alphavantage.co/support/#api-key',
    fields: [{ key: 'alpha_vantage', label: 'API Key', type: 'password', placeholder: 'your-alpha-vantage-key' }],
  },
  // ── Developer ──────────────────────────────────────────────────────────────
  {
    id: 'vscode', name: 'VS Code', category: 'developer', authType: 'info',
    description: 'Luna AI extension for VS Code',
    logo: <VSCodeLogo />,
    helpText: 'The Luna VS Code extension brings AI chat, code generation, and Luna context directly into your editor.\n\n1. Open VS Code\n2. Go to Extensions (Ctrl+Shift+X)\n3. Search for "Luna AI"\n4. Click Install\n\nOr install manually from the VSIX file in integrations/vscode/.',
    helpUrl: 'https://marketplace.visualstudio.com/vscode',
    fields: [],
  },
]

export const CATEGORIES = [
  { id: 'workspace',  label: 'Workspace' },
  { id: 'music',      label: 'Music & Media' },
  { id: 'communication', label: 'Communication' },
  { id: 'health',     label: 'Health & Fitness' },
  { id: 'data',       label: 'Data & APIs' },
  { id: 'developer',  label: 'Developer Tools' },
] as const

// ── Auth type badge ───────────────────────────────────────────────────────────

function AuthBadge({ type }: { type: AuthType }) {
  if (type === 'oauth')    return <span className="text-[10px] flex items-center gap-0.5 text-blue-400"><Key size={9}/> OAuth</span>
  if (type === 'webhook')  return <span className="text-[10px] flex items-center gap-0.5 text-purple-400"><Webhook size={9}/> Webhook</span>
  if (type === 'info')     return <span className="text-[10px] flex items-center gap-0.5 text-luna-dim"><Info size={9}/> Extension</span>
  return null
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  configured: Set<string>
  onConfigured: (id: string) => void
}

export function IntegrationStore({ configured, onConfigured }: Props) {
  const [selected, setSelected] = useState<Integration | null>(null)
  const [step, setStep]         = useState<'guide' | 'fields' | 'connect' | 'done'>('guide')
  const [values, setValues]     = useState<Record<string, string>>({})
  const [saving, setSaving]     = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError]       = useState('')
  const pollRef                 = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const openIntegration = async (intg: Integration) => {
    setSelected(intg); setStep('guide'); setError('')
    if (intg.fields.length === 0) return
    const res = await window.electronAPI?.getEnvConfig?.()
    if (res?.ok && res.config) {
      setValues(Object.fromEntries(intg.fields.map(f => [f.key, res.config![f.key] ?? ''])))
    } else {
      setValues(Object.fromEntries(intg.fields.map(f => [f.key, ''])))
    }
  }

  const saveCredentials = async () => {
    if (!selected) return
    setSaving(true); setError('')
    const res = await window.electronAPI?.saveEnvConfig?.(values)
    setSaving(false)
    if (!res?.ok) { setError(res?.error || 'Save failed — only works in the desktop app.'); return }
    if (selected.authType === 'oauth') {
      setStep('connect')
    } else {
      onConfigured(selected.id); setStep('done')
    }
  }

  const startOAuth = async () => {
    if (!selected) return
    setConnecting(true); setError('')

    let authUrl = ''
    try {
      if (selected.oauthType === 'spotify') {
        const res = await api.spotifyAuthUrl()
        authUrl = res.url
      } else if (selected.oauthType === 'health' && selected.oauthPlatform) {
        authUrl = `${BASE}/api/health/oauth/authorize/${selected.oauthPlatform}`
      }
    } catch {
      setError('Could not get auth URL — make sure the backend is running and credentials are saved.')
      setConnecting(false); return
    }

    if (authUrl) window.electronAPI?.openUrl(authUrl)

    // Poll for connection
    pollRef.current = setInterval(async () => {
      try {
        if (selected.oauthType === 'spotify') {
          const s = await api.spotifyStatus()
          if (s.connected) { clearInterval(pollRef.current!); onConfigured(selected.id); setStep('done'); setConnecting(false) }
        } else if (selected.oauthType === 'health') {
          const s = await api.healthStatus()
          const platform = selected.oauthPlatform!
          if (s[platform]?.configured || s[platform]?.last_sync) {
            clearInterval(pollRef.current!); onConfigured(selected.id); setStep('done'); setConnecting(false)
          }
        }
      } catch {}
    }, 2000)

    // Timeout after 3 min
    setTimeout(() => {
      if (pollRef.current) { clearInterval(pollRef.current); setConnecting(false) }
    }, 180_000)
  }

  if (!selected) {
    return (
      <div className="space-y-8">
        {CATEGORIES.map(cat => {
          const items = INTEGRATIONS.filter(i => i.category === cat.id)
          return (
            <div key={cat.id} className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-luna-dim">{cat.label}</h4>
              <div className="grid grid-cols-3 gap-3">
                {items.map(intg => (
                  <button key={intg.id} onClick={() => openIntegration(intg)}
                    className="flex items-center gap-3 p-3 rounded-xl border border-luna-border bg-luna-card hover:bg-luna-surface hover:border-luna-primary/40 transition-all group text-left">
                    <div className="relative shrink-0">
                      <div className="w-10 h-10 rounded-lg bg-luna-surface border border-luna-border/50 flex items-center justify-center group-hover:border-luna-primary/30 transition-colors">
                        {intg.logo}
                      </div>
                      {configured.has(intg.id) && (
                        <CheckCircle size={12} className="absolute -top-1 -right-1 text-green-400 bg-luna-bg rounded-full" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="text-xs font-medium text-luna-text truncate">{intg.name}</p>
                        <AuthBadge type={intg.authType} />
                      </div>
                      <p className="text-[10px] text-luna-dim leading-tight mt-0.5 truncate">{intg.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div key={selected.id + step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="max-w-xl space-y-6">
        {/* Back + header */}
        <div className="flex items-center gap-4">
          <button onClick={() => {
            if (step === 'guide' || step === 'done') { setSelected(null) }
            else if (step === 'fields') setStep('guide')
            else if (step === 'connect') setStep('fields')
          }} className="flex items-center gap-1.5 text-xs text-luna-dim hover:text-luna-text transition-colors">
            <ArrowLeft size={14} /> Back
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-luna-card border border-luna-border flex items-center justify-center">{selected.logo}</div>
            <div>
              <p className="text-sm font-semibold text-luna-text">{selected.name}</p>
              <p className="text-[11px] text-luna-dim">{selected.description}</p>
            </div>
            {configured.has(selected.id) && (
              <span className="text-[10px] px-2 py-0.5 rounded-full border text-green-400 border-green-400/30 bg-green-400/10">Connected</span>
            )}
          </div>
        </div>

        {/* Progress dots for oauth */}
        {selected.authType === 'oauth' && (
          <div className="flex items-center gap-2 text-xs text-luna-dim">
            {['guide', 'fields', 'connect'].map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${step === s ? 'bg-luna-accent' : ['guide','fields','connect'].indexOf(step) > i ? 'bg-green-400' : 'bg-luna-border'}`} />
                <span className={step === s ? 'text-luna-text' : ''}>{['Setup', 'Credentials', 'Authorize'][i]}</span>
                {i < 2 && <span className="text-luna-border">→</span>}
              </div>
            ))}
          </div>
        )}

        {/* Guide step */}
        {step === 'guide' && (
          <div className="space-y-4">
            {selected.authType === 'webhook' && selected.webhookPath && (
              <div className="bg-luna-card border border-luna-border/60 rounded-xl p-3 flex items-center gap-2">
                <Webhook size={13} className="text-purple-400 shrink-0" />
                <div>
                  <p className="text-[11px] text-luna-dim">Luna endpoint</p>
                  <p className="text-xs text-luna-text font-mono">{BASE}{selected.webhookPath}</p>
                </div>
              </div>
            )}
            <div className="bg-luna-card border border-luna-border/60 rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-luna-text uppercase tracking-wide">Setup guide</p>
              <div className="space-y-1">
                {selected.helpText.split('\n').map((line, i) => (
                  <p key={i} className={`text-sm leading-relaxed ${line.trim() === '' ? 'h-2' : line.match(/^\d\./) ? 'text-luna-text' : 'text-luna-dim'}`}>{line}</p>
                ))}
              </div>
              <button onClick={() => window.electronAPI?.openUrl(selected.helpUrl)}
                className="inline-flex items-center gap-1.5 text-xs text-luna-accent hover:underline">
                <ExternalLink size={11} /> Open {selected.name}
              </button>
            </div>
            {selected.authType === 'info'
              ? <div className="text-xs text-luna-dim bg-luna-card border border-luna-border/60 rounded-xl p-3">No configuration needed — just install the extension.</div>
              : <button onClick={() => setStep('fields')}
                  className="w-full py-3 rounded-xl bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-sm font-medium hover:bg-luna-primary/30 transition-colors">
                  {selected.authType === 'oauth' ? 'Enter credentials →' : 'Configure →'}
                </button>
            }
          </div>
        )}

        {/* Fields step */}
        {step === 'fields' && (
          <div className="space-y-4">
            {selected.fields.map(field => (
              <div key={field.key} className="space-y-1.5">
                <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">{field.label}</label>
                <input type={field.type} placeholder={field.placeholder} value={values[field.key] ?? ''}
                  onChange={e => setValues(v => ({ ...v, [field.key]: e.target.value }))}
                  className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60 font-mono"/>
              </div>
            ))}
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button onClick={saveCredentials} disabled={saving}
              className="w-full py-3 rounded-xl bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-sm font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}
              {saving ? 'Saving…' : selected.authType === 'oauth' ? 'Save & continue →' : 'Save credentials'}
            </button>
          </div>
        )}

        {/* Connect / OAuth step */}
        {step === 'connect' && (
          <div className="space-y-4">
            <div className="bg-luna-card border border-luna-border/60 rounded-xl p-4 text-center space-y-3">
              <div className="w-14 h-14 rounded-xl bg-luna-surface border border-luna-border mx-auto flex items-center justify-center">
                {selected.logo}
              </div>
              <p className="text-sm text-luna-text font-medium">Connect your {selected.name} account</p>
              <p className="text-xs text-luna-dim">A browser window will open for authorization. Come back here after approving.</p>
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button onClick={startOAuth} disabled={connecting}
              className="w-full py-3 rounded-xl bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-sm font-semibold hover:bg-luna-primary/30 transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
              {connecting ? <><Loader2 size={14} className="animate-spin" /> Waiting for authorization…</> : `Sign in with ${selected.name} →`}
            </button>
            {connecting && (
              <p className="text-[11px] text-luna-dim text-center">
                Authorized in the browser? Luna will detect it automatically.
              </p>
            )}
          </div>
        )}

        {/* Done */}
        {step === 'done' && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-16 h-16 rounded-full bg-green-400/10 border border-green-400/30 flex items-center justify-center">
              <CheckCircle size={32} className="text-green-400" />
            </div>
            <div>
              <p className="text-luna-text font-semibold">{selected.name} connected</p>
              <p className="text-luna-dim text-xs mt-1">Credentials saved. Some changes require restarting Luna.</p>
            </div>
            <button onClick={() => setSelected(null)}
              className="px-6 py-2 rounded-xl bg-luna-card border border-luna-border text-luna-dim text-sm hover:text-luna-text transition-colors">
              Back to integrations
            </button>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

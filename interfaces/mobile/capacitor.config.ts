import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.luna.companion',
  appName: 'Luna',
  webDir: 'dist',
  server: {
    // Use https scheme on Android so fetch() works without mixed-content blocks
    androidScheme: 'https',
  },
  android: {
    // Keep screen on while the app is in the foreground
    allowMixedContent: false,
    backgroundColor: '#09090f',
  },
  ios: {
    backgroundColor: '#09090f',
    contentInset: 'always',
    scrollEnabled: false,
  },
  plugins: {
    Preferences: {
      group: 'LunaStorage',
    },
  },
}

export default config

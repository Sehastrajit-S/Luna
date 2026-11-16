import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { isMobile, getDirectApiKey, getDirectProvider, getDirectModel, getServerUrl, getServerToken } from './platform'
import { initDirectChat } from './api/directChat'
import type { DirectProvider } from './api/directChat'
import { initApiBase, initApiToken, installAuthFetch } from './api/client'

async function boot() {
  if (isMobile) {
    // Server mode: restore the saved server and its access token.
    const serverUrl = await getServerUrl()
    if (serverUrl) initApiBase(serverUrl)
    initApiToken(await getServerToken())
    installAuthFetch()

    const apiKey = await getDirectApiKey()
    if (apiKey) {
      const provider = (await getDirectProvider()) as DirectProvider
      const model    = await getDirectModel()
      initDirectChat({ provider, apiKey, model })
    }
    // No API key → isStandaloneMode() = false → App shows MobileSetup
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}

boot()

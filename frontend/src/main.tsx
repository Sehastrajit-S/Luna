import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { isMobile, getDirectApiKey, getDirectProvider, getDirectModel } from './platform'
import { initDirectChat } from './api/directChat'
import type { DirectProvider } from './api/directChat'

async function boot() {
  if (isMobile) {
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

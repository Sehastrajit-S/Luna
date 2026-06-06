import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { isMobile, getServerUrl } from './platform'
import { initApiBase } from './api/client'

async function boot() {
  // On mobile, read the persisted server URL before mounting so every
  // fetch() in the app already has the right BASE from the first render.
  if (isMobile) {
    const url = await getServerUrl()
    if (url) initApiBase(url)
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}

boot()

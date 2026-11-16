/**
 * Browser host for the renderer. The backend serves this same UI at "/", so
 * web and desktop stay one codebase. In Electron the preload has already set
 * window.electronAPI and this file does nothing.
 *
 * In a browser it provides the few host calls the renderer uses: the API base
 * (same origin), opening links in a new tab, and the local access token that
 * settings writes require. The token is never handed out by the server; it is
 * read from a `#token=` link (printed by `luna web`) or pasted once, then kept
 * in this browser's localStorage.
 */
'use strict'

;(function () {
  if (window.electronAPI) return

  const TOKEN_KEY = 'luna_local_token'

  function readStoredToken() {
    try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
  }

  function storeToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token)
      else localStorage.removeItem(TOKEN_KEY)
    } catch { /* private mode: token lasts for this page only */ }
  }

  let token = readStoredToken()
  const match = location.hash.match(/(?:^#|&)token=([^&]+)/)
  if (match) {
    token = decodeURIComponent(match[1])
    storeToken(token)
    history.replaceState(null, '', location.pathname + location.search)
  }

  document.documentElement.classList.add('is-web')

  window.electronAPI = {
    isElectron: false,
    isWeb: true,
    apiBase: location.origin,
    openUrl: url => {
      if (typeof url === 'string' && /^https?:\/\//i.test(url)) window.open(url, '_blank', 'noopener')
    },
    getLocalToken: async () => token,
    // Called after the server rejects a request (a settings save, or any API
    // call when Luna is reached remotely): ask for the token once.
    requestLocalToken: async () => {
      const entered = window.prompt(
        'Luna needs its access token.\n' +
        'Run `luna web` (or `luna serve --tailscale` for remote access) for a link that includes it,\n' +
        'or paste the contents of data/local_api_token from the server:'
      )
      token = (entered || '').trim()
      storeToken(token)
      return token
    },
  }
})()

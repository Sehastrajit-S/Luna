/**
 * Adds Luna's access token to every request this UI makes to its server's
 * /api routes. A local server accepts requests without it, but a server
 * reached over Tailscale (or any proxy) rejects them with 401 — see
 * server/core/access.py.
 *
 * Token source: the desktop preload (apiToken / getLocalToken), or in a
 * browser the `#token=` link handled by web-shim.js. In a browser a 401 asks
 * for the token once and retries.
 */
'use strict'

;(function () {
  const host = window.electronAPI
  if (!host?.apiBase || window.__lunaAuthFetch) return
  window.__lunaAuthFetch = true

  const apiOrigin = new URL(host.apiBase, location.href).origin
  const nativeFetch = window.fetch.bind(window)
  let token = host.apiToken || ''
  let pendingPrompt = null

  function isApiRequest(url) {
    try {
      const target = new URL(url, location.href)
      return target.origin === apiOrigin && target.pathname.startsWith('/api/')
    } catch {
      return false
    }
  }

  async function currentToken() {
    if (!token && host.getLocalToken) {
      try { token = (await host.getLocalToken()) || '' } catch { /* stays empty */ }
    }
    return token
  }

  function withToken(input, init, value) {
    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
    if (value && !headers.has('X-Luna-Token')) headers.set('X-Luna-Token', value)
    return { ...init, headers }
  }

  async function askForToken() {
    if (!host.requestLocalToken) return ''
    // Many requests fail at once on first load; prompt once for all of them.
    pendingPrompt ||= Promise.resolve(host.requestLocalToken()).finally(() => { pendingPrompt = null })
    token = (await pendingPrompt) || ''
    return token
  }

  window.fetch = async function lunaFetch(input, init) {
    const url = typeof input === 'string' || input instanceof URL ? String(input) : input?.url
    if (!url || !isApiRequest(url)) return nativeFetch(input, init)

    const response = await nativeFetch(input, withToken(input, init, await currentToken()))
    if (response.status !== 401 || !host.requestLocalToken) return response
    // Bodies that are streams can't be re-sent; leave those to the caller.
    if (init?.body instanceof ReadableStream) return response
    const fresh = await askForToken()
    return fresh ? nativeFetch(input, withToken(input, init, fresh)) : response
  }

  /** For XMLHttpRequest, which this wrapper doesn't cover. */
  window.lunaAuthHeaders = function () {
    return token ? { 'X-Luna-Token': token } : {}
  }

  /** For URLs opened outside fetch (EventSource, links opened in a browser). */
  window.lunaAuthUrl = function (url) {
    if (!token || !isApiRequest(url)) return url
    const target = new URL(url, location.href)
    target.searchParams.set('luna_token', token)
    return target.toString()
  }
})()

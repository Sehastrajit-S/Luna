/**
 * Library view: files you've attached in chats ("Uploaded") and files Luna
 * wrote into its workspace ("Created by Luna"). Uses fileBadge/formatBytes
 * from attachments.js. Opening a file goes through the browser (or, in the
 * desktop app, the system browser), so remote servers get the token in the URL.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const list = document.getElementById('library-list')
  const search = document.getElementById('library-search')
  const tabs = document.querySelectorAll('[data-library-tab]')
  if (!list || !search) return

  let tab = 'uploads'
  let requestId = 0
  let debounce = null

  const ENDPOINT = { uploads: '/api/library/uploads', created: '/api/library/created' }
  const EMPTY = {
    uploads: 'No files yet. Attach a file in a chat and it will appear here.',
    created: 'Luna hasn’t created any files yet. Ask it to write a document, dataset or code file.',
  }

  function openUrl(path) {
    const url = `${API}${path}`
    const authed = window.lunaAuthUrl ? window.lunaAuthUrl(url) : url
    if (window.electronAPI?.openUrl) window.electronAPI.openUrl(authed)
    else window.open(authed, '_blank', 'noopener')
  }

  function when(iso) {
    if (!iso) return ''
    const date = new Date(iso)
    const days = Math.floor((Date.now() - date) / 86400000)
    if (days < 1) return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    if (days < 7) return date.toLocaleDateString([], { weekday: 'short' })
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' })
  }

  function row(item) {
    const name = item.filename || item.name
    const badge = typeof fileBadge === 'function' ? fileBadge(name) : { label: 'FILE', tone: 'code' }

    const li = document.createElement('li')
    li.className = `library-item file-chip-${badge.tone}`

    const open = document.createElement('button')
    open.type = 'button'
    open.className = 'library-open'
    open.title = `Open ${name}`
    open.addEventListener('click', () => openUrl(tab === 'uploads'
      ? `/api/files/${encodeURIComponent(item.id)}/raw`
      : `/api/library/created/raw?path=${encodeURIComponent(item.path)}`))

    const icon = document.createElement('span')
    icon.className = 'file-chip-icon'
    icon.textContent = badge.label
    const text = document.createElement('span')
    text.className = 'library-text'
    const title = document.createElement('span')
    title.className = 'library-name'
    title.textContent = name
    const meta = document.createElement('span')
    meta.className = 'library-meta'
    const size = typeof formatBytes === 'function' ? formatBytes(item.size_bytes) : ''
    meta.textContent = tab === 'uploads'
      ? [item.summary_line || size, when(item.created_at)].filter(Boolean).join(' · ')
      : [item.folder, size, when(item.modified_at)].filter(Boolean).join(' · ')
    text.append(title, meta)
    open.append(icon, text)
    li.append(open)

    if (tab === 'uploads' && item.conversation_id && window.lunaOpenConversation) {
      const chat = document.createElement('button')
      chat.type = 'button'
      chat.className = 'library-chat'
      chat.textContent = item.conversation_title ? `In “${item.conversation_title}”` : 'Open chat'
      chat.title = 'Go to the chat this file was shared in'
      chat.addEventListener('click', () => window.lunaOpenConversation(item.conversation_id))
      li.append(chat)
    }
    return li
  }

  function message(text, tone = '') {
    const li = document.createElement('li')
    li.className = `library-empty${tone ? ' is-' + tone : ''}`
    li.textContent = text
    list.replaceChildren(li)
  }

  async function load() {
    const id = ++requestId
    const current = tab
    const q = search.value.trim()
    message('Loading…')
    try {
      const response = await fetch(`${API}${ENDPOINT[current]}${q ? `?q=${encodeURIComponent(q)}` : ''}`)
      if (!response.ok) throw new Error(`Library returned ${response.status}`)
      const data = await response.json()
      if (id !== requestId) return // a newer search or tab switch won
      const items = data.items || []
      if (!q) document.getElementById(`library-count-${current}`).textContent = items.length ? String(items.length) : ''
      if (!items.length) return message(q ? `Nothing matches “${q}”.` : EMPTY[current])
      list.replaceChildren(...items.map(row))
      if (data.truncated) {
        const more = document.createElement('li')
        more.className = 'library-empty'
        more.textContent = 'Showing the 500 most recent files. Search to find older ones.'
        list.append(more)
      }
    } catch (error) {
      if (id === requestId) message('Couldn’t load the library. Is Luna’s server running?', 'error')
      console.error('Library load failed', error)
    }
  }

  tabs.forEach(button => button.addEventListener('click', () => {
    tab = button.dataset.libraryTab
    tabs.forEach(b => {
      const active = b === button
      b.classList.toggle('is-active', active)
      b.setAttribute('aria-selected', String(active))
    })
    load()
  }))

  search.addEventListener('input', () => {
    clearTimeout(debounce)
    debounce = setTimeout(load, 220)
  })

  window.loadLibraryView = load
})()

/**
 * Library view: files you've attached in chats ("Uploaded") and files Luna
 * wrote into its workspace ("Created by Luna"). Uses fileBadge/formatBytes
 * from attachments.js. Clicking a file previews it in place (Markdown,
 * text/code, CSV, images, PDF, audio/video); every file can also be
 * downloaded, or opened in the browser (remote servers get the token in the URL).
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

  function authed(path) {
    const url = `${API}${path}`
    return window.lunaAuthUrl ? window.lunaAuthUrl(url) : url
  }

  function openUrl(path) {
    if (window.electronAPI?.openUrl) window.electronAPI.openUrl(authed(path))
    else window.open(authed(path), '_blank', 'noopener')
  }

  // Uploads have an attachment id; files Luna created have a workspace path.
  const rawPath = item => item.id
    ? `/api/files/${encodeURIComponent(item.id)}/raw`
    : `/api/library/created/raw?path=${encodeURIComponent(item.path)}`
  const withDownload = path => `${path}${path.includes('?') ? '&' : '?'}download=1`

  // Fetch with the authenticated fetch, then save from a blob URL, so it works
  // the same in the desktop app (save dialog) and in a browser.
  async function download(item, button) {
    const name = item.filename || item.name
    const label = button?.innerHTML
    if (button) { button.disabled = true; button.classList.add('is-busy') }
    try {
      const response = await fetch(`${API}${withDownload(rawPath(item))}`)
      if (!response.ok) throw new Error(`Download failed (${response.status})`)
      const url = URL.createObjectURL(await response.blob())
      const a = Object.assign(document.createElement('a'), { href: url, download: name })
      document.body.append(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
      if (button) button.innerHTML = label
    } catch (error) {
      console.error('Library download failed', error)
      if (button) button.title = 'Download failed. Click to retry.'
    } finally {
      if (button) { button.disabled = false; button.classList.remove('is-busy') }
    }
  }

  // ── Preview ────────────────────────────────────────────────────────────────
  const sheet = document.getElementById('library-preview')
  const sheetBody = document.getElementById('library-preview-body')
  const sheetName = document.getElementById('library-preview-name')
  const sheetMeta = document.getElementById('library-preview-meta')
  const sheetClose = document.getElementById('library-preview-close')
  const sheetDownload = document.getElementById('library-preview-download')
  const sheetOpen = document.getElementById('library-preview-open')
  let previewItem = null
  let previewToken = 0
  let lastFocus = null

  const KINDS = [
    [/^(md|markdown)$/, 'markdown'],
    [/^(csv|tsv)$/, 'table'],
    [/^(png|jpe?g|gif|webp|bmp|svg|ico|avif)$/, 'image'],
    [/^pdf$/, 'pdf'],
    [/^(mp3|wav|ogg|oga|m4a|aac|flac|opus)$/, 'audio'],
    [/^(mp4|webm|mov|m4v|ogv)$/, 'video'],
    [/^(txt|log|json|jsonl|ya?ml|toml|ini|cfg|conf|xml|html?|css|scss|js|mjs|cjs|ts|tsx|jsx|py|rb|go|rs|java|kt|c|h|cpp|hpp|cs|php|sh|bash|zsh|ps1|bat|sql|r|swift|lua|ipynb|srt|vtt|tex)$/, 'text'],
  ]
  const MAX_TEXT_BYTES = 1024 * 1024
  const MAX_TABLE_ROWS = 500

  function previewKind(name) {
    const ext = ((String(name).match(/\.([a-z0-9]+)$/i) || [])[1] || '').toLowerCase()
    const match = KINDS.find(([re]) => re.test(ext))
    return match ? match[1] : null
  }

  function note(text, tone = '') {
    return Object.assign(document.createElement('p'), {
      className: `library-preview-note${tone ? ' is-' + tone : ''}`, textContent: text,
    })
  }

  // CSV/TSV with quoted fields ("a, b" and "" escapes); stops after the row cap.
  function parseDelimited(text, delimiter) {
    const rows = []
    let row = []
    let cell = ''
    let quoted = false
    for (let i = 0; i < text.length && rows.length <= MAX_TABLE_ROWS + 1; i++) {
      const ch = text[i]
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++ }
        else if (ch === '"') quoted = false
        else cell += ch
      } else if (ch === '"' && cell === '') {
        quoted = true
      } else if (ch === delimiter) {
        row.push(cell); cell = ''
      } else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i + 1] === '\n') i++
        row.push(cell); rows.push(row); row = []; cell = ''
      } else {
        cell += ch
      }
    }
    if (cell || row.length) { row.push(cell); rows.push(row) }
    return rows.filter(r => r.some(c => c.trim()))
  }

  function tableView(text, delimiter) {
    const rows = parseDelimited(text, delimiter)
    if (!rows.length) return [note('This file is empty.')]
    const wrap = document.createElement('div')
    wrap.className = 'library-preview-table'
    const table = document.createElement('table')
    rows.slice(0, MAX_TABLE_ROWS + 1).forEach((cells, index) => {
      const tr = document.createElement('tr')
      for (const value of cells) tr.append(Object.assign(document.createElement(index ? 'td' : 'th'), { textContent: value }))
      table.append(tr)
    })
    wrap.append(table)
    return rows.length > MAX_TABLE_ROWS + 1
      ? [wrap, note(`Showing the first ${MAX_TABLE_ROWS} rows. Download the file for the rest.`)]
      : [wrap]
  }

  async function previewText(item, kind) {
    const response = await fetch(`${API}${rawPath(item)}`)
    if (!response.ok) throw new Error(`Preview failed (${response.status})`)
    const blob = await response.blob()
    const text = await blob.slice(0, MAX_TEXT_BYTES).text()
    const nodes = []
    if (kind === 'markdown' && typeof window.renderMarkdown === 'function') {
      const doc = document.createElement('div')
      doc.className = 'bubble library-preview-doc'
      const md = document.createElement('div')
      md.className = 'md'
      md.innerHTML = window.renderMarkdown(text)
      doc.append(md)
      nodes.push(doc)
    } else if (kind === 'table') {
      nodes.push(...tableView(text, /\.tsv$/i.test(item.filename || item.name) ? '\t' : ','))
    } else {
      nodes.push(Object.assign(document.createElement('pre'), { className: 'library-preview-code', textContent: text }))
    }
    if (blob.size > MAX_TEXT_BYTES) nodes.push(note('Showing the first 1 MB. Download the file for the rest.'))
    return nodes
  }

  // Images, PDFs and media load straight from the server so large files stream.
  function previewMedia(item, kind) {
    const name = item.filename || item.name
    const src = authed(rawPath(item))
    if (kind === 'image') {
      const img = Object.assign(document.createElement('img'), { className: 'library-preview-image', src, alt: name })
      img.addEventListener('error', () => img.replaceWith(note('Couldn’t show this image. Download it instead.', 'error')))
      return [img]
    }
    if (kind === 'pdf') {
      // Phone browsers (Android Chrome, many WebViews) can't show a PDF inside
      // a page and leave a blank box: send them to Open / Download instead.
      if (navigator.pdfViewerEnabled === false) {
        return [note('PDFs can’t be shown inside the page on this device. Tap Open to view it, or Download to save it.')]
      }
      return [Object.assign(document.createElement('iframe'), { className: 'library-preview-pdf', src, title: name })]
    }
    const media = document.createElement(kind)
    media.className = `library-preview-${kind}`
    media.controls = true
    media.preload = 'metadata'
    media.src = src
    // A meeting recording is a .webm with no picture: shrink the player to a bar.
    media.addEventListener('loadedmetadata', () => {
      if (kind === 'video' && !media.videoWidth) media.classList.add('is-audio')
    })
    media.addEventListener('error', () => media.replaceWith(note('This file can’t be played here. Download it instead.', 'error')))
    return [media]
  }

  async function openPreview(item) {
    const token = ++previewToken
    const name = item.filename || item.name
    const kind = previewKind(name)
    previewItem = item
    sheetName.textContent = name
    const size = typeof formatBytes === 'function' ? formatBytes(item.size_bytes) : ''
    sheetMeta.textContent = [item.folder || item.conversation_title, size].filter(Boolean).join(' · ')
    sheetBody.replaceChildren(note('Loading…'))
    if (sheet.hidden) lastFocus = document.activeElement
    sheet.hidden = false
    sheetClose.focus()
    try {
      let nodes
      if (!kind) nodes = [note('There’s no preview for this kind of file. Download it, or open it in your browser.')]
      else if (kind === 'markdown' || kind === 'table' || kind === 'text') nodes = await previewText(item, kind)
      else nodes = previewMedia(item, kind)
      if (token === previewToken) sheetBody.replaceChildren(...nodes)
    } catch (error) {
      console.error('Library preview failed', error)
      if (token === previewToken) sheetBody.replaceChildren(note('Couldn’t load this file. Is Luna’s server running?', 'error'))
    }
  }

  function closePreview() {
    if (!sheet || sheet.hidden) return
    previewToken++
    sheet.hidden = true
    sheetBody.replaceChildren()            // also stops any playing audio/video
    previewItem = null
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus()
  }

  if (sheet) {
    sheet.addEventListener('click', event => { if (event.target === sheet) closePreview() })
    sheetClose.addEventListener('click', closePreview)
    sheetDownload.addEventListener('click', () => { if (previewItem) download(previewItem, sheetDownload) })
    sheetOpen.addEventListener('click', () => { if (previewItem) openUrl(rawPath(previewItem)) })
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !sheet.hidden) closePreview() })
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
    open.title = `Preview ${name}`
    open.addEventListener('click', () => openPreview(item))

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

    const save = document.createElement('button')
    save.type = 'button'
    save.className = 'library-download'
    save.title = `Download ${name}`
    save.setAttribute('aria-label', `Download ${name}`)
    save.innerHTML = '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    save.addEventListener('click', () => download(item, save))
    li.append(save)
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

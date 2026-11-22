/**
 * Notes app (sidebar → Apps → Notes): a list of notes and an editor that
 * autosaves as you type. Pinned notes stay on top; an untouched empty note is
 * thrown away when you move on. Data lives in Luna's database via /api/notes.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const $ = id => document.getElementById(id)
  const root = $('view-notes')
  if (!root) return

  const SAVE_DELAY = 600
  const list = $('notes-list')
  const search = $('notes-search')
  const titleInput = $('note-title')
  const bodyInput = $('note-body')
  const savedLabel = $('note-saved')

  let notes = []          // summaries: id, title, preview, pinned, updated_at
  let current = null      // full note being edited
  let dirty = false
  let saveTimer = null
  let saving = Promise.resolve()
  let searchTimer = null
  let loadId = 0

  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }

  async function api(path = '', options = {}) {
    const response = await fetch(`${API}/api/notes${path}`, {
      ...options,
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    })
    if (response.status === 204) return null
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = body.detail
      throw new Error(typeof detail === 'object' && detail?.message ? detail.message : `Something went wrong (${response.status}).`)
    }
    return body
  }

  const displayTitle = n => n.heading || n.title?.trim() || 'New note'
  const isEmpty = n => !n.title?.trim() && !(n.body ?? '').trim()

  function when(iso) {
    const d = new Date(iso)
    const today = new Date()
    const days = Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()) -
      new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5)
    if (days === 0) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    if (days === 1) return 'Yesterday'
    if (days < 7) return d.toLocaleDateString(undefined, { weekday: 'long' })
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === today.getFullYear() ? undefined : 'numeric' })
  }

  // ── list ───────────────────────────────────────────────────────────────
  function renderList() {
    list.innerHTML = ''
    const q = search.value.trim()
    if (!notes.length) {
      list.append(el('li', 'notes-empty', q ? 'No notes match.' : 'No notes yet. Tap + to write one.'))
      return
    }
    let section = null
    for (const n of notes) {
      const name = n.pinned ? 'Pinned' : 'Notes'
      if (name !== section) {
        section = name
        if (notes.some(x => x.pinned)) list.append(el('li', 'notes-section', name))
      }
      const li = el('li')
      const b = el('button', `note-item${current?.id === n.id ? ' is-active' : ''}`)
      b.type = 'button'
      b.dataset.id = n.id
      const meta = el('span', 'note-item-meta')
      meta.append(el('span', 'note-item-date', when(n.updated_at)), el('span', 'note-item-preview', n.preview || 'No additional text'))
      b.append(el('span', 'note-item-title', displayTitle(n)), meta)
      b.addEventListener('click', () => openNote(n.id))
      li.append(b)
      list.append(li)
    }
  }

  async function loadList() {
    const id = ++loadId
    const q = search.value.trim()
    try {
      const data = await api(q ? `?q=${encodeURIComponent(q)}` : '')
      if (id !== loadId) return
      notes = data.notes
      renderList()
    } catch (error) {
      list.innerHTML = ''
      list.append(el('li', 'notes-empty', `Couldn’t load notes. ${error.message}`))
    }
  }

  // ── editor ─────────────────────────────────────────────────────────────
  function showEditor(on) {
    root.classList.toggle('is-editing', on)
    $('note-editor').hidden = !on
    $('note-placeholder').hidden = on
  }

  function fillEditor(n) {
    titleInput.value = n.title || ''
    bodyInput.value = n.body || ''
    $('note-pin').setAttribute('aria-pressed', String(!!n.pinned))
    $('note-pin').title = n.pinned ? 'Unpin' : 'Pin to top'
    $('note-date').textContent = new Date(n.updated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    savedLabel.textContent = ''
    autosize()
  }

  async function leaveCurrent() {
    if (!current) return
    await flush()
    // A note left completely empty isn't worth keeping.
    if (isEmpty(current)) {
      const id = current.id
      notes = notes.filter(n => n.id !== id)
      try { await api(`/${id}`, { method: 'DELETE' }) } catch { /* it'll show up again; fine */ }
    }
  }

  async function openNote(id) {
    if (current?.id === id) { showEditor(true); return }
    await leaveCurrent()
    try {
      current = await api(`/${id}`)
      fillEditor(current)
      showEditor(true)
      renderList()
    } catch (error) {
      savedLabel.textContent = error.message
    }
  }

  async function newNote() {
    await leaveCurrent()
    try {
      current = await api('', { method: 'POST', body: JSON.stringify({}) })
      search.value = ''
      notes.splice(notes.filter(n => n.pinned).length, 0, summaryOf(current))
      fillEditor(current)
      showEditor(true)
      renderList()
      titleInput.focus()
    } catch (error) {
      window.alert(`Couldn’t create a note. ${error.message}`)
    }
  }

  // Same as the server's heading_and_preview: untitled notes are named by their first line.
  function summaryOf(n) {
    let heading = (n.title || '').trim()
    let lines = (n.body || '').split('\n')
    if (!heading) {
      const first = lines.findIndex(line => line.trim())
      if (first >= 0) { heading = lines[first].trim().slice(0, 120); lines = lines.slice(first + 1) }
    }
    const text = lines.join(' ').split(/\s+/).join(' ').trim()
    return { id: n.id, title: n.title, heading, pinned: n.pinned, updated_at: n.updated_at,
      preview: text.slice(0, 140) + (text.length > 140 ? '…' : '') }
  }

  // Keep the list item in step with the editor, moving it to the top of its section.
  function syncListItem() {
    if (!current) return
    const summary = summaryOf(current)
    notes = notes.filter(n => n.id !== current.id)
    const at = current.pinned ? 0 : notes.filter(n => n.pinned).length
    notes.splice(at, 0, summary)
    renderList()
  }

  function onEdit() {
    if (!current) return
    current.title = titleInput.value
    current.body = bodyInput.value
    current.updated_at = new Date().toISOString()
    dirty = true
    savedLabel.textContent = 'Editing…'
    clearTimeout(saveTimer)
    saveTimer = setTimeout(flush, SAVE_DELAY)
    syncListItem()
  }

  function flush({ keepalive = false } = {}) {
    clearTimeout(saveTimer)
    if (!current || !dirty) return saving
    dirty = false
    const note = current
    const body = JSON.stringify({ title: note.title, body: note.body })
    saving = saving.then(async () => {
      try {
        if (keepalive) {
          await fetch(`${API}/api/notes/${note.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body, keepalive: true })
          return
        }
        const saved = await api(`/${note.id}`, { method: 'PATCH', body })
        if (current?.id === note.id && !dirty) {
          current.updated_at = saved.updated_at
          savedLabel.textContent = 'Saved'
          $('note-date').textContent = new Date(saved.updated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
        }
      } catch (error) {
        if (current?.id === note.id) {
          dirty = true                       // try again on the next edit or when leaving
          savedLabel.textContent = `Not saved: ${error.message}`
        }
      }
    })
    return saving
  }

  async function togglePin() {
    if (!current) return
    await flush()
    try {
      const saved = await api(`/${current.id}`, { method: 'PATCH', body: JSON.stringify({ pinned: !current.pinned }) })
      current.pinned = saved.pinned
      $('note-pin').setAttribute('aria-pressed', String(saved.pinned))
      $('note-pin').title = saved.pinned ? 'Unpin' : 'Pin to top'
      await loadList()
    } catch (error) {
      savedLabel.textContent = error.message
    }
  }

  async function deleteNote() {
    if (!current) return
    if (!isEmpty(current) && !window.confirm(`Delete “${displayTitle(current)}”?`)) return
    clearTimeout(saveTimer)
    dirty = false
    const id = current.id
    try {
      await api(`/${id}`, { method: 'DELETE' })
      current = null
      notes = notes.filter(n => n.id !== id)
      showEditor(false)
      renderList()
    } catch (error) {
      savedLabel.textContent = error.message
    }
  }

  function askLuna() {
    if (!current) return
    flush()
    const text = (current.body || '').trim()
    const prompt = [
      `Here's my note “${displayTitle(current)}”. Tidy it up into clear points, then tell me anything I should follow up on.`,
      '',
      '---',
      current.title?.trim() ? current.title.trim() : '',
      text || '(empty)',
    ].filter((line, i) => i < 3 || line).join('\n')
    window.lunaAskInNewChat?.(prompt)
  }

  async function back() {
    await leaveCurrent()
    current = null
    showEditor(false)
    renderList()
  }

  function autosize() {
    // On phones the page scrolls; let the text area grow with its text.
    bodyInput.style.height = 'auto'
    bodyInput.style.height = `${Math.max(bodyInput.scrollHeight, 240)}px`
  }

  // ── wiring ─────────────────────────────────────────────────────────────
  $('notes-new').addEventListener('click', newNote)
  $('note-pin').addEventListener('click', togglePin)
  $('note-delete').addEventListener('click', deleteNote)
  $('note-ask').addEventListener('click', askLuna)
  $('note-back').addEventListener('click', back)
  $('note-placeholder-new').addEventListener('click', newNote)
  titleInput.addEventListener('input', onEdit)
  bodyInput.addEventListener('input', () => { onEdit(); autosize() })
  titleInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); bodyInput.focus() }
  })
  search.addEventListener('input', () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(loadList, 200)
  })
  window.addEventListener('pagehide', () => flush({ keepalive: true }))
  // Leaving the Notes page saves too.
  new MutationObserver(() => {
    if (root.classList.contains('is-hidden')) flush()
  }).observe(root, { attributes: true, attributeFilter: ['class'] })

  window.loadNotesView = () => {
    loadList()
    if (!current) showEditor(false)
  }
})()

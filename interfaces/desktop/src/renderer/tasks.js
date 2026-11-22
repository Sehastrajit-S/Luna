/**
 * Tasks app (sidebar → Apps → Tasks). The same tasks Luna adds from chat and
 * the dashboard shows. Smart views (Today, Upcoming, Anytime, All, Completed)
 * plus your own lists; quick add understands "tomorrow 5pm #work !high".
 *
 * Due times: a task "due on a day" is stored as 11:59 PM local that day and
 * shown without a time; anything else shows its time.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const $ = id => document.getElementById(id)
  const root = $('view-tasks')
  if (!root) return

  const VIEWS = [
    { key: 'today', name: 'Today', icon: '☀' },
    { key: 'upcoming', name: 'Upcoming', icon: '◷' },
    { key: 'anytime', name: 'Anytime', icon: '◇' },
    { key: 'all', name: 'All tasks', icon: '☰' },
    { key: 'completed', name: 'Completed', icon: '✓' },
  ]
  const PRIORITY_RANK = { high: 0, medium: 1, low: 2 }
  const WEEKDAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

  let tasks = []
  let lists = []
  let extraLists = []          // lists made with "New list" that have no tasks yet
  let completedTotal = 0
  let view = 'today'
  let editing = null
  let loading = false

  // ── helpers ────────────────────────────────────────────────────────────
  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }
  const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
  const dayKey = d => d.toLocaleDateString('en-CA')
  const endOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 0)
  const isDateOnly = d => d.getHours() === 23 && d.getMinutes() === 59
  const due = t => (t.due_date ? new Date(t.due_date) : null)
  const today = () => startOfDay(new Date())

  function isOverdue(t) {
    const d = due(t)
    if (!d || t.completed) return false
    return isDateOnly(d) ? startOfDay(d) < today() : d < new Date()
  }

  function dayLabel(d) {
    const diff = Math.round((startOfDay(d) - today()) / 864e5)
    if (diff === 0) return 'Today'
    if (diff === 1) return 'Tomorrow'
    if (diff === -1) return 'Yesterday'
    if (diff > 1 && diff < 7) return d.toLocaleDateString(undefined, { weekday: 'long' })
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric',
      year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' })
  }
  function dueText(t) {
    const d = due(t)
    if (!d) return ''
    const time = isDateOnly(d) ? '' : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    const day = dayLabel(d)
    return time ? (day === 'Today' ? time : `${day}, ${time}`) : day
  }

  async function api(path = '', options = {}) {
    const response = await fetch(`${API}/api/tasks${path}`, {
      ...options,
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    })
    if (response.status === 204) return null
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = body.detail
      throw new Error(typeof detail === 'object' && detail?.message ? detail.message
        : Array.isArray(detail) ? (detail[0]?.msg || 'Check the fields and try again.').replace(/^Value error, /, '')
        : `Something went wrong (${response.status}).`)
    }
    return body
  }

  function status(text, isError = false) {
    const node = $('tk-status')
    node.hidden = !text
    node.textContent = text || ''
    node.classList.toggle('is-error', isError)
  }

  // ── which tasks a view shows ───────────────────────────────────────────
  function inView(t, key = view) {
    if (key === 'completed') return t.completed
    if (t.completed) return false
    const d = due(t)
    if (key === 'today') return !!d && startOfDay(d) <= today()
    if (key === 'upcoming') return !!d && startOfDay(d) > today()
    if (key === 'anytime') return !d
    if (key === 'all') return true
    if (key.startsWith('list:')) return t.list_name === key.slice(5)
    return false
  }

  function sortOpen(a, b) {
    const da = due(a), db = due(b)
    if (!!da !== !!db) return da ? -1 : 1
    if (da && db && da - db) return da - db
    return (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1) || b.id - a.id
  }

  function groupFor(t) {
    if (view === 'completed') return null
    const d = due(t)
    if (!d) return view === 'anytime' ? null : 'No date'
    if (isOverdue(t)) return 'Overdue'
    return dayLabel(d)
  }

  // ── rendering ──────────────────────────────────────────────────────────
  function allLists() {
    return [...new Set([...lists, ...extraLists])].sort((a, b) => a.localeCompare(b))
  }
  function viewName(key = view) {
    return key.startsWith('list:') ? key.slice(5) : VIEWS.find(v => v.key === key)?.name || 'Tasks'
  }

  function renderNav() {
    const nav = $('tk-views')
    nav.innerHTML = ''
    const item = (key, icon, name) => {
      const b = el('button', `tk-view${key === view ? ' is-active' : ''}`)
      b.type = 'button'
      b.setAttribute('role', 'tab')
      b.setAttribute('aria-selected', String(key === view))
      const count = key === 'completed' ? completedTotal : tasks.filter(t => inView(t, key)).length
      const overdue = key === 'today' ? tasks.filter(isOverdue).length : 0
      b.append(el('span', 'tk-view-icon', icon), el('span', 'tk-view-name', name),
        el('span', `tk-view-count${overdue ? ' is-overdue' : ''}`, count ? String(count) : ''))
      b.addEventListener('click', () => { view = key; render(); $('tk-add-input').focus({ preventScroll: true }) })
      nav.append(b)
    }
    VIEWS.forEach(v => item(v.key, v.icon, v.name))
    nav.append(el('p', 'tk-nav-label', 'Lists'))
    allLists().forEach(name => item(`list:${name}`, '#', name))
    const add = el('button', 'tk-view tk-new-list', null)
    add.type = 'button'
    add.append(el('span', 'tk-view-icon', '+'), el('span', 'tk-view-name', 'New list'))
    add.addEventListener('click', newList)
    nav.append(add)
  }

  function renderList() {
    const box = $('tk-list')
    box.innerHTML = ''
    $('tk-view-title').textContent = viewName()
    const q = $('tk-search').value.trim().toLowerCase()
    let shown = tasks.filter(t => inView(t))
    if (q) shown = shown.filter(t => `${t.title} ${t.description} ${t.list_name || ''}`.toLowerCase().includes(q))
    shown.sort(view === 'completed'
      ? (a, b) => (b.completed_at || '').localeCompare(a.completed_at || '')
      : sortOpen)

    $('tk-clear').hidden = view !== 'completed' || !completedTotal
    if (!shown.length) {
      const empty = q ? 'No tasks match.'
        : view === 'today' ? 'Nothing due today. Enjoy it — or add something above.'
        : view === 'completed' ? 'No completed tasks yet.'
        : view.startsWith('list:') ? `No tasks in ${viewName()} yet.`
        : 'No tasks here.'
      box.append(el('p', 'tk-empty', empty))
      return
    }
    let current
    let ul
    for (const t of shown) {
      const g = groupFor(t)
      if (!ul || g !== current) {
        current = g
        if (g) box.append(el('h3', `tk-group${g === 'Overdue' ? ' is-overdue' : ''}`, g))
        ul = el('ul', 'tk-items')
        box.append(ul)
      }
      ul.append(row(t))
    }
    if (view === 'completed' && completedTotal > shown.length && !q) {
      box.append(el('p', 'tk-empty', `Showing the latest ${shown.length} of ${completedTotal}.`))
    }
  }

  function row(t) {
    const li = el('li', `tk-item${t.completed ? ' is-done' : ''}`)
    li.dataset.id = t.id
    const check = el('button', `tk-check is-${t.priority}`)
    check.type = 'button'
    check.setAttribute('role', 'checkbox')
    check.setAttribute('aria-checked', String(t.completed))
    check.setAttribute('aria-label', t.completed ? `Mark "${t.title}" as not done` : `Complete "${t.title}"`)
    check.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    check.addEventListener('click', event => { event.stopPropagation(); toggle(t, li) })

    const body = el('button', 'tk-body')
    body.type = 'button'
    body.append(el('span', 'tk-title', t.title))
    const meta = el('span', 'tk-meta')
    if (t.due_date) meta.append(el('span', `tk-chip tk-due${isOverdue(t) ? ' is-overdue' : ''}`, dueText(t)))
    if (t.list_name && view !== `list:${t.list_name}`) meta.append(el('span', 'tk-chip', `# ${t.list_name}`))
    if (t.priority === 'high' && !t.completed) meta.append(el('span', 'tk-chip is-high', '! High'))
    if (t.description) meta.append(el('span', 'tk-chip tk-notes', '¶ Notes'))
    if (meta.childNodes.length) body.append(meta)
    body.addEventListener('click', () => openSheet(t))
    li.append(check, body)
    return li
  }

  function render() {
    renderNav()
    renderList()
    updatePreview()
  }

  // ── loading & actions ──────────────────────────────────────────────────
  async function load() {
    if (loading) return
    loading = true
    try {
      const data = await api()
      tasks = data.tasks
      lists = data.lists
      completedTotal = data.completed_total
      extraLists = extraLists.filter(name => !lists.includes(name))
      if (view.startsWith('list:') && !allLists().includes(view.slice(5))) view = 'today'
      status('')
      render()
    } catch (error) {
      status(`Couldn’t load your tasks. ${error.message}`, true)
    } finally {
      loading = false
    }
  }

  async function toggle(t, li) {
    const done = !t.completed
    li.classList.add(done ? 'is-completing' : 'is-reopening')
    li.querySelector('.tk-check').setAttribute('aria-checked', String(done))
    try {
      const updated = await api(`/${t.id}`, { method: 'PATCH', body: JSON.stringify({ completed: done }) })
      Object.assign(t, updated)
      completedTotal += done ? 1 : -1
      setTimeout(render, 380)      // let the check animation play before the row moves
    } catch (error) {
      li.classList.remove('is-completing', 'is-reopening')
      li.querySelector('.tk-check').setAttribute('aria-checked', String(!done))
      status(error.message, true)
    }
  }

  // ── quick add: "Call mom tomorrow 5pm #family !high" ───────────────────
  function parseQuick(text) {
    let title = ` ${text} `
    let list = null
    let priority = null
    let day = null
    let time = null
    const take = (re, fn) => {
      title = title.replace(re, (...m) => { fn(m); return ' ' })
    }
    take(/\s#([\p{L}\p{N}_-]{1,40})(?=\s)/u, m => { list = m[1].replace(/_/g, ' ') })
    take(/\s!(high|h|1|!)(?=\s)/i, () => { priority = 'high' })
    take(/\s!(low|l|3)(?=\s)/i, () => { priority = 'low' })
    take(/\s(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?=\s)/i, m => {
      let h = Number(m[1]) % 12
      if (m[3].toLowerCase() === 'pm') h += 12
      if (Number(m[1]) <= 12 && Number(m[2] || 0) < 60) time = [h, Number(m[2] || 0)]
    })
    take(/\sat\s+(\d{1,2}):(\d{2})(?=\s)/i, m => {
      if (Number(m[1]) < 24 && Number(m[2]) < 60) time = [Number(m[1]), Number(m[2])]
    })
    take(/\s(today|tonight)(?=\s)/i, m => { day = today(); if (m[1].toLowerCase() === 'tonight' && !time) time = [20, 0] })
    take(/\s(tomorrow|tmrw|tmr)(?=\s)/i, () => { day = addDays(today(), 1) })
    take(/\s(?:on\s+|next\s+)?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)(?=\s)/i, m => {
      const target = WEEKDAYS.indexOf(m[1].toLowerCase())
      const diff = (target - today().getDay() + 7) % 7 || 7
      day = addDays(today(), diff)
    })
    title = title.replace(/\s+/g, ' ').trim()

    let dueDate = null
    if (day || time) {
      const base = day || today()
      if (time) {
        dueDate = new Date(base.getFullYear(), base.getMonth(), base.getDate(), time[0], time[1])
        if (!day && dueDate < new Date()) dueDate = addDays(dueDate, 1)     // "5pm" after 5pm → tomorrow
      } else {
        dueDate = endOfDay(base)
      }
    }
    return { title, list, priority, dueDate }
  }

  // What a bare task gets from the current view: Today → due today; a list → that list.
  function withContext(parsed) {
    const out = { ...parsed }
    if (!out.dueDate && view === 'today') out.dueDate = endOfDay(today())
    if (!out.list && view.startsWith('list:')) out.list = view.slice(5)
    return out
  }

  function updatePreview() {
    const box = $('tk-add-preview')
    const text = $('tk-add-input').value
    box.innerHTML = ''
    $('tk-add-hint').hidden = !!text.trim()
    if (!text.trim()) { box.hidden = true; return }
    const p = withContext(parseQuick(text))
    const chips = []
    if (p.dueDate) chips.push(dueText({ due_date: p.dueDate.toISOString() }))
    if (p.list) chips.push(`# ${p.list}`)
    if (p.priority === 'high') chips.push('! High')
    if (p.priority === 'low') chips.push('Low')
    chips.forEach(c => box.append(el('span', 'tk-chip', c)))
    box.hidden = !chips.length
  }

  async function quickAdd(event) {
    event.preventDefault()
    const input = $('tk-add-input')
    const p = withContext(parseQuick(input.value))
    if (!p.title) return
    input.disabled = true
    try {
      const created = await api('', { method: 'POST', body: JSON.stringify({
        title: p.title, due_date: p.dueDate ? p.dueDate.toISOString() : null,
        priority: p.priority || 'medium', list_name: p.list,
      }) })
      input.value = ''
      tasks.push(created)
      if (created.list_name && !lists.includes(created.list_name)) lists.push(created.list_name)
      // Added somewhere this view doesn't show (e.g. "tomorrow" from Today): say where it went.
      status(inView(created) ? '' : `Added to ${created.due_date ? dueText(created) : created.list_name || 'Anytime'}.`)
      render()
    } catch (error) {
      status(error.message, true)
    } finally {
      input.disabled = false
      input.focus()
    }
  }

  function newList() {
    const name = (window.prompt('Name the new list') || '').trim().replace(/^#/, '').slice(0, 40)
    if (!name) return
    if (!allLists().includes(name)) extraLists.push(name)
    view = `list:${name}`
    render()
    $('tk-add-input').focus()
  }

  // ── edit sheet ─────────────────────────────────────────────────────────
  function openSheet(t) {
    editing = t
    const f = $('tk-form').elements
    f.task_title.value = t.title
    f.notes.value = t.description || ''
    const d = due(t)
    f.date.value = d ? dayKey(d) : ''
    f.time.value = d && !isDateOnly(d) ? `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}` : ''
    f.task_list.value = t.list_name || ''
    setPriority(t.priority || 'medium')
    const dl = $('tk-list-options')
    dl.innerHTML = ''
    allLists().forEach(name => dl.append(new Option(name)))
    $('tk-form-error').hidden = true
    $('tk-form-done').textContent = t.completed ? 'Mark not done' : 'Mark done'
    $('tk-sheet').hidden = false
    setTimeout(() => f.task_title.focus(), 50)
  }
  function closeSheet() {
    $('tk-sheet').hidden = true
    editing = null
  }
  function setPriority(value) {
    document.querySelectorAll('#tk-priority .bud-seg-btn').forEach(b => {
      const on = b.dataset.priority === value
      b.classList.toggle('is-active', on)
      b.setAttribute('aria-checked', String(on))
    })
  }
  function formError(message) {
    $('tk-form-error').textContent = message
    $('tk-form-error').hidden = !message
  }

  async function saveSheet(event) {
    event.preventDefault()
    if (!editing) return
    const f = $('tk-form').elements
    const title = f.task_title.value.trim()
    if (!title) return formError('Give the task a title.')
    let dueDate = null
    if (f.date.value) {
      const [y, m, d] = f.date.value.split('-').map(Number)
      if (f.time.value) {
        const [h, min] = f.time.value.split(':').map(Number)
        dueDate = new Date(y, m - 1, d, h, min)
      } else {
        dueDate = endOfDay(new Date(y, m - 1, d))
      }
    } else if (f.time.value) {
      return formError('Pick a date for that time.')
    }
    const priority = document.querySelector('#tk-priority .is-active')?.dataset.priority || 'medium'
    try {
      $('tk-form-save').disabled = true
      const updated = await api(`/${editing.id}`, { method: 'PATCH', body: JSON.stringify({
        title, description: f.notes.value, due_date: dueDate ? dueDate.toISOString() : null,
        priority, list_name: f.task_list.value.trim() || null,
      }) })
      Object.assign(editing, updated)
      closeSheet()
      await load()
    } catch (error) {
      formError(error.message)
    } finally {
      $('tk-form-save').disabled = false
    }
  }

  async function deleteFromSheet() {
    if (!editing || !window.confirm(`Delete "${editing.title}"?`)) return
    try {
      await api(`/${editing.id}`, { method: 'DELETE' })
      closeSheet()
      await load()
    } catch (error) {
      formError(error.message)
    }
  }

  async function toggleFromSheet() {
    if (!editing) return
    try {
      await api(`/${editing.id}`, { method: 'PATCH', body: JSON.stringify({ completed: !editing.completed }) })
      closeSheet()
      await load()
    } catch (error) {
      formError(error.message)
    }
  }

  async function clearCompleted() {
    if (!window.confirm(`Delete all ${completedTotal} completed tasks? This can’t be undone.`)) return
    try {
      await api('/completed', { method: 'DELETE' })
      await load()
    } catch (error) {
      status(error.message, true)
    }
  }

  function planDay() {
    const open = tasks.filter(t => inView(t, 'today')).sort(sortOpen)
    const anytime = tasks.filter(t => inView(t, 'anytime')).slice(0, 10)
    const line = t => `- ${t.title}${t.due_date ? ` (${isOverdue(t) ? 'overdue, ' : ''}${dueText(t)})` : ''}${t.priority === 'high' ? ' [high priority]' : ''}${t.list_name ? ` #${t.list_name}` : ''}`
    const text = [
      'Help me plan my day. Put these in a sensible order with rough time estimates, and tell me what I should move to another day.',
      '',
      open.length ? 'Due today or overdue:' : 'Nothing is due today.',
      ...open.map(line),
      ...(anytime.length ? ['', 'No date (pick any worth doing today):', ...anytime.map(line)] : []),
    ].join('\n')
    window.lunaAskInNewChat?.(text)
  }

  // ── wiring ─────────────────────────────────────────────────────────────
  $('tk-add').addEventListener('submit', quickAdd)
  $('tk-add-input').addEventListener('input', updatePreview)
  $('tk-search').addEventListener('input', renderList)
  $('tk-clear').addEventListener('click', clearCompleted)
  $('tk-plan').addEventListener('click', planDay)
  $('tk-form').addEventListener('submit', saveSheet)
  $('tk-form-close').addEventListener('click', closeSheet)
  $('tk-form-delete').addEventListener('click', deleteFromSheet)
  $('tk-form-done').addEventListener('click', toggleFromSheet)
  $('tk-sheet').addEventListener('click', event => { if (event.target === $('tk-sheet')) closeSheet() })
  document.querySelectorAll('#tk-priority .bud-seg-btn').forEach(b => b.addEventListener('click', () => setPriority(b.dataset.priority)))
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !$('tk-sheet').hidden) closeSheet()
  })

  window.loadTasksView = () => {
    status('')
    load()
  }
})()

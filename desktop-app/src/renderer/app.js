/**
 * Visual-only interactions for the UI scaffold — no chat/backend wiring yet.
 * Clicking things just updates local UI state (active nav item, active
 * recent chat) so the mockup feels alive. Real behavior comes later.
 *
 * Exception: the traffic-light buttons are wired for real, since they map
 * directly to window controls main-preload.js already exposes.
 */
'use strict'

// ── Explore search overlay ──────────────────────────────────────────────────
const searchInput = document.querySelector('.search-box input')
const exploreOverlay = document.getElementById('explore-overlay')
const exploreInput = document.getElementById('explore-input')
const exploreButton = document.querySelector('[data-nav="explore"]')

function openExplore(query = '') {
  exploreOverlay?.classList.remove('is-hidden')
  document.body.classList.add('explore-open')
  if (exploreInput) {
    exploreInput.value = query
    requestAnimationFrame(() => exploreInput.focus())
  }
}

function closeExplore() {
  exploreOverlay?.classList.add('is-hidden')
  document.body.classList.remove('explore-open')
}

exploreButton?.addEventListener('click', () => openExplore())
document.querySelector('.explore-backdrop')?.addEventListener('click', closeExplore)
document.querySelector('.explore-close')?.addEventListener('click', closeExplore)
document.querySelectorAll('[data-explore-query]').forEach(button => {
  button.addEventListener('click', () => {
    openExplore(button.dataset.exploreQuery)
    exploreInput?.select()
  })
})
exploreInput?.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeExplore()
  if (e.key === 'Enter' && exploreInput.value.trim()) closeExplore()
})

window.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    openExplore(searchInput?.value ?? '')
  }
  if (e.key === 'Escape' && !exploreOverlay?.classList.contains('is-hidden')) closeExplore()
})

document.querySelectorAll('[data-window-action]').forEach(btn => {
  btn.addEventListener('click', () => {
    const api = window.electronAPI
    if (!api) return // e.g. previewing this file outside Electron
    const action = btn.dataset.windowAction
    if (action === 'close') api.close()
    else if (action === 'minimize') api.minimize()
    else if (action === 'fullscreen') api.toggleFullscreen()
  })
})

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('is-active'))
    btn.classList.add('is-active')
    if (btn.dataset.nav === 'capabilities') {
      showView(viewCapabilities)
      loadCapabilities()
    } else if (btn.dataset.nav === 'settings') {
      openSettingsView()
    }
  })
})

function openSettingsView() {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('is-active', b.dataset.nav === 'settings'))
  showView(viewSettings)
  window.loadSettingsView?.()
}
// "Settings…" from the app menu or tray.
window.electronAPI?.onShowSettings?.(openSettingsView)

document.querySelectorAll('[data-capability-filter]').forEach(button => {
  button.addEventListener('click', () => {
    const filter = button.dataset.capabilityFilter
    document.querySelectorAll('[data-capability-filter]').forEach(item => item.classList.toggle('is-active', item === button))
    document.querySelectorAll('[data-capability-category]').forEach(card => {
      card.classList.toggle('is-filtered-out', filter !== 'all' && card.dataset.capabilityCategory !== filter)
    })
    document.querySelectorAll('#skills-grid .capability-card').forEach(card => {
      card.classList.toggle('is-filtered-out', filter !== 'all' && filter !== 'skill')
    })
  })
})

document.querySelectorAll('.recent-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.recent-item').forEach(b => b.classList.remove('is-active'))
    btn.classList.add('is-active')
  })
})

// ── New chat ────────────────────────────────────────────────────────────────
const newChatButton = document.getElementById('new-chat-btn')
const conversation = document.getElementById('conversation')
const emptyConversation = document.getElementById('empty-conversation')
const API_BASE = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
let activeConversationId = null

async function loadCapabilities() {
  const grid = document.getElementById('skills-grid')
  const count = document.getElementById('skills-count')
  if (!grid) return
  try {
    const response = await fetch(`${API_BASE}/api/skills/installed`)
    if (!response.ok) throw new Error(`Skills returned ${response.status}`)
    const skills = (await response.json()).skills || []
    if (count) count.textContent = `${skills.length} installed`
    grid.innerHTML = ''
    if (!skills.length) {
      grid.innerHTML = '<p class="capability-empty">No local skills installed.</p>'
      return
    }
    skills.forEach(skill => {
      const card = document.createElement('article')
      card.className = 'capability-card'
      card.dataset.capabilityCategory = 'skill'
      card.innerHTML = '<span class="capability-icon">✦</span><div><h3></h3><p></p></div>'
      card.querySelector('h3').textContent = skill.name || skill.id
      card.querySelector('p').textContent = skill.description || 'Installed Luna skill.'
      grid.append(card)
    })
  } catch (error) {
    grid.innerHTML = '<p class="capability-empty">Could not load skills.</p>'
    console.error('Could not load skills', error)
  }
}

document.getElementById('github-configure-btn')?.addEventListener('click', () => openSettingsView())

// ── Developer dashboard: local checkout + GitHub repo pulse ────────────────
function timeAgo(iso) {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60) return 'just now'
  const units = [[31536000, 'y'], [2592000, 'mo'], [86400, 'd'], [3600, 'h'], [60, 'm']]
  for (const [size, label] of units) if (secs >= size) return `${Math.floor(secs / size)}${label} ago`
  return 'just now'
}

function devEl(tag, className, text) {
  const el = document.createElement(tag)
  if (className) el.className = className
  if (text != null) el.textContent = text
  return el
}

function devLink(url, text, className = 'dev-link') {
  const a = devEl('a', className, text)
  if (url && /^https:\/\//.test(url)) a.href = url
  return a
}

async function loadDevDashboard(force = false) {
  const $ = id => document.getElementById(id)
  const refresh = $('dev-refresh-btn')
  if (refresh) { refresh.disabled = true; refresh.textContent = 'Refreshing…' }
  let data
  try {
    const response = await fetch(`${API_BASE}/api/system/dev-dashboard${force ? '?refresh=true' : ''}`)
    if (!response.ok) throw new Error(`Dashboard returned ${response.status}`)
    data = await response.json()
  } catch (error) {
    data = { local: { available: false }, github: null, error: { message: 'Couldn’t reach Luna’s backend.' } }
  } finally {
    if (refresh) { refresh.disabled = false; refresh.textContent = 'Refresh' }
  }
  const gh = data.github
  const local = data.local || {}

  const repoLink = $('dev-repo')
  repoLink.textContent = gh?.repo || 'No repository'
  if (gh?.url) repoLink.href = gh.url; else repoLink.removeAttribute('href')
  const source = $('dev-source')
  source.hidden = !(gh && gh.source === 'public')
  source.textContent = 'public data'

  const alert = $('dev-alert')
  const problem = gh?.token_problem || data.error?.message
  alert.hidden = !problem
  alert.textContent = problem
    ? (gh?.token_problem ? `Showing public data only — ${gh.token_problem}` : problem)
    : ''

  const n = v => (v == null ? '—' : String(v))
  $('dev-commits').textContent = n(gh?.commits_30d)
  const spark = $('dev-spark')
  const days = gh?.commit_days || []
  const peak = Math.max(1, ...days)
  spark.replaceChildren(...days.map((count, i) => {
    const bar = devEl('span', count ? 'is-on' : '')
    bar.style.height = `${Math.max(2, Math.round((count / peak) * 26))}px`
    bar.title = `${count} commit${count === 1 ? '' : 's'} · ${days.length - 1 - i === 0 ? 'today' : `${days.length - 1 - i}d ago`}`
    return bar
  }))
  const lastCommit = gh?.recent_commits?.[0]
  if (gh && !gh.commits_30d && lastCommit) spark.title = `Last commit ${timeAgo(lastCommit.date)}`

  const prs = gh?.open_prs || []
  $('dev-prs').textContent = gh ? String(prs.length) : '—'
  $('dev-prs-sub').textContent = prs[0] ? `#${prs[0].number} ${prs[0].title}` : gh ? 'Nothing waiting' : ''
  $('dev-issues').textContent = n(gh?.open_issues)
  $('dev-issues-sub').textContent = gh?.open_issues === 0 ? 'All clear' : ''

  const ci = gh?.ci
  const ciEl = $('dev-ci')
  const state = !ci ? 'none' : ci.status !== 'completed' ? 'running' : (ci.conclusion === 'success' ? 'pass' : 'fail')
  ciEl.replaceChildren(devEl('span', `dev-dot is-${state}`),
    document.createTextNode({ none: 'No runs', running: 'Running', pass: 'Passing', fail: ci?.conclusion ? ci.conclusion[0].toUpperCase() + ci.conclusion.slice(1) : 'Failing' }[state]))
  $('dev-ci-sub').textContent = ci ? `${ci.name} · ${ci.branch} · ${timeAgo(ci.updated)}` : gh ? 'No GitHub Actions workflows' : ''

  $('dev-branch').textContent = local.available ? local.branch : '—'
  const syncParts = []
  if (local.available) {
    syncParts.push(local.changed ? `${local.changed} changed` : 'clean')
    if (local.untracked) syncParts.push(`${local.untracked} untracked`)
    if (local.ahead) syncParts.push(`${local.ahead} ahead`)
    if (local.behind) syncParts.push(`${local.behind} behind`)
    if (local.ahead === 0 && local.behind === 0) syncParts.push('in sync')
  }
  $('dev-local-sub').textContent = local.available ? syncParts.join(' · ') : 'Not a git checkout'

  const commitList = $('dev-commit-list')
  const commits = gh?.recent_commits || []
  commitList.replaceChildren(...(commits.length ? commits.map(c => {
    const li = devEl('li')
    const top = devEl('div', 'dev-row')
    top.append(devLink(c.url, c.sha, 'dev-link dev-sha'), devEl('span', 'dev-msg', c.message))
    li.append(top, devEl('span', 'dev-meta', `${c.author} · ${timeAgo(c.date)}`))
    return li
  }) : [devEl('li', 'dev-empty', gh ? 'No commits yet' : 'Unavailable')]))

  const prList = $('dev-pr-list')
  const items = []
  for (const pr of prs.slice(0, 5)) {
    const li = devEl('li')
    const top = devEl('div', 'dev-row')
    top.append(devLink(pr.url, `#${pr.number}`, 'dev-link dev-sha'), devEl('span', 'dev-msg', `${pr.draft ? '[draft] ' : ''}${pr.title}`))
    li.append(top, devEl('span', 'dev-meta', `${pr.author} · updated ${timeAgo(pr.updated)}`))
    items.push(li)
  }
  for (const c of (gh?.review_comments || []).slice(0, 4)) {
    const li = devEl('li', 'dev-comment')
    const top = devEl('div', 'dev-row')
    top.append(devLink(c.url, `#${c.pr}`, 'dev-link dev-sha'), devEl('span', 'dev-msg', c.body))
    li.append(top, devEl('span', 'dev-meta', `review comment · ${c.author}`))
    items.push(li)
  }
  prList.replaceChildren(...(items.length ? items : [devEl('li', 'dev-empty', gh ? 'No open pull requests' : 'Unavailable')]))
}

document.getElementById('dev-refresh-btn')?.addEventListener('click', () => loadDevDashboard(true))
// Dashboard links open in the system browser, never inside the app window.
document.getElementById('dev-dashboard')?.addEventListener('click', event => {
  const link = event.target.closest('a.dev-link')
  if (!link) return
  event.preventDefault()
  if (link.href) window.electronAPI?.openUrl?.(link.href)
})

// The backend keeps one "active conversation" shared by every Luna surface
// (desktop, CLI, voice). A message sent without an id is appended to it, and
// it's what reopens on launch — so switching chats here must update it too.
let contextSync = Promise.resolve()
function syncActiveConversation(id) {
  contextSync = fetch(`${API_BASE}/api/chat/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ active_conversation_id: id }),
  }).catch(error => console.error('Could not update active conversation', error))
  return contextSync
}

// Starter suggestions ("Create itinerary", …) belong to an empty chat only:
// shown with the empty state, gone once the conversation has messages.
const quickActions = document.querySelector('.quick-actions')

function setEmptyState(isEmpty) {
  emptyConversation?.classList.toggle('is-hidden', !isEmpty)
  quickActions?.classList.toggle('is-hidden', !isEmpty)
}

function startNewChat() {
  document.querySelectorAll('.recent-item').forEach(item => item.classList.remove('is-active'))
  conversation?.querySelectorAll('.msg-row, .msg-time').forEach(message => message.remove())
  setEmptyState(true)
  activeConversationId = null
  viewToken += 1
  syncActiveConversation(null)
  updateSendState()
  showChat()
  composerInput?.focus()
}

newChatButton?.addEventListener('click', startNewChat)

// A suggestion fills the message box with a starter to finish, e.g.
// "Create an itinerary for " — it doesn't send on its own.
const QUICK_ACTION_STARTERS = {
  'create itinerary': 'Create an itinerary for ',
  'suggest hotels': 'Suggest hotels in ',
  'food recommendations': 'Recommend places to eat in ',
  'travel tips': 'Give me travel tips for ',
}
quickActions?.querySelectorAll('button').forEach(button => {
  button.addEventListener('click', () => {
    const label = button.textContent.trim().toLowerCase()
    const starter = QUICK_ACTION_STARTERS[label] || `${button.textContent.trim()}: `
    composerInput.value = starter
    composerInput.focus()
    composerInput.setSelectionRange(starter.length, starter.length)
  })
})

// Composer + backend chat stream.
const composerInput = document.querySelector('.composer-input')
const sendBtn = document.querySelector('.send-btn')

// Replies still streaming. Switching chats clears the message list, so each
// stream keeps its own reply row and puts it back when its chat is reopened.
const liveStreams = new Set()
// Changes whenever the user opens another chat or starts a new one, so a
// stream never moves the user back to its conversation.
let viewToken = 0

function streamFor(conversationId) {
  for (const stream of liveStreams) {
    if (stream.conversationId === conversationId) return stream
  }
  return null
}

function updateSendState() {
  const busy = Boolean(streamFor(activeConversationId))
  sendBtn.disabled = busy
  sendBtn.classList.toggle('is-sending', busy)
}

function clearConversationView() {
  conversation?.querySelectorAll('.msg-row, .msg-time').forEach(message => message.remove())
  setEmptyState(false)
}

function appendConversationMessage(message) {
  if (message.role === 'user') {
    appendUserMessage(message.content, message.attachments || [], message.created_at)
    return
  }
  const text = createAssistantMessage()
  setAssistantContent(text, message.content)
}

async function openConversation(id) {
  try {
    const response = await fetch(`${API_BASE}/api/chat/conversations/${id}`)
    if (!response.ok) throw new Error(`Conversation returned ${response.status}`)
    const data = await response.json()
    activeConversationId = data.id
    viewToken += 1
    syncActiveConversation(data.id)
    clearConversationView()
    data.messages.forEach(appendConversationMessage)
    // A reply still being written isn't in the history yet: put the live row back.
    const live = streamFor(data.id)
    if (live?.row && data.messages[data.messages.length - 1]?.role === 'user') conversation.append(live.row)
    updateSendState()
    document.querySelectorAll('.recent-item').forEach(item => item.classList.toggle('is-active', item.dataset.conversationId === String(id)))
    showChat()
    conversation.scrollTop = conversation.scrollHeight
  } catch (error) {
    console.error('Could not open conversation', error)
  }
}

// ── Chat options menu (⋯ on each recent chat) ──────────────────────────────
let openMenu = null

function closeChatMenu() {
  openMenu?.menu.remove()
  openMenu?.row.classList.remove('menu-open')
  openMenu = null
}

function openChatMenu(row, item) {
  const wasOpen = openMenu?.row === row
  closeChatMenu()
  if (wasOpen) return
  const menu = document.createElement('div')
  menu.className = 'chat-menu'
  menu.setAttribute('role', 'menu')
  menu.addEventListener('click', event => event.stopPropagation())

  const showActions = () => {
    menu.innerHTML = '<button type="button" class="chat-menu-item is-danger" role="menuitem">' +
      '<svg viewBox="0 0 24 24" width="15" height="15"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '<span>Delete</span></button>'
    menu.querySelector('button').addEventListener('click', showConfirm)
    menu.querySelector('button').focus()
  }

  // Deleting can't be undone (messages and attached files go too), so confirm in place.
  const showConfirm = () => {
    menu.innerHTML = '<p class="chat-menu-title">Delete this chat?</p>' +
      '<p class="chat-menu-note">Its messages and attached files will be permanently deleted.</p>' +
      '<div class="chat-menu-actions"><button type="button" class="chat-menu-btn">Cancel</button>' +
      '<button type="button" class="chat-menu-btn is-danger">Delete</button></div>'
    const [cancel, confirm] = menu.querySelectorAll('.chat-menu-btn')
    cancel.addEventListener('click', closeChatMenu)
    confirm.addEventListener('click', () => deleteConversation(item.id, confirm))
    confirm.focus()
  }

  showActions()
  row.classList.add('menu-open')
  // Attached to <body> with fixed coordinates: the recent list scrolls and
  // would clip a menu placed inside it.
  document.body.append(menu)
  const anchor = row.querySelector('.recent-more').getBoundingClientRect()
  const place = () => {
    const height = menu.offsetHeight
    const below = anchor.bottom + 4
    menu.style.top = `${below + height > window.innerHeight - 8 ? Math.max(8, anchor.top - height - 4) : below}px`
    menu.style.left = `${Math.max(8, anchor.right - menu.offsetWidth)}px`
  }
  place()
  new MutationObserver(place).observe(menu, { childList: true })  // confirm step is taller
  openMenu = { row, menu }
}

async function deleteConversation(id, button) {
  button.disabled = true
  button.textContent = 'Deleting…'
  try {
    const response = await fetch(`${API_BASE}/api/chat/conversations/${id}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Delete returned ${response.status}`)
    closeChatMenu()
    if (id === activeConversationId) startNewChat()
    await loadConversations()
  } catch (error) {
    console.error('Could not delete conversation', error)
    button.disabled = false
    button.textContent = 'Try again'
  }
}

document.addEventListener('click', closeChatMenu)
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeChatMenu() })

async function loadConversations() {
  const list = document.getElementById('recent-list')
  if (!list) return
  try {
    const response = await fetch(`${API_BASE}/api/chat/conversations?limit=20`)
    if (!response.ok) throw new Error(`Conversations returned ${response.status}`)
    const conversations = await response.json()
    list.innerHTML = ''
    if (!conversations.length) {
      list.innerHTML = '<li class="recent-empty">No conversations yet</li>'
      return
    }
    conversations.forEach(item => {
      const li = document.createElement('li')
      li.className = 'recent-row'
      const button = document.createElement('button')
      button.className = 'recent-item'
      button.dataset.conversationId = item.id
      button.type = 'button'
      button.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 5h16v11H8l-4 4z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/></svg><span></span>'
      button.querySelector('span').textContent = item.title || `Conversation ${item.id}`
      button.addEventListener('click', () => openConversation(item.id))
      if (item.id === activeConversationId) button.classList.add('is-active')

      const more = document.createElement('button')
      more.className = 'recent-more'
      more.type = 'button'
      more.setAttribute('aria-label', 'Chat options')
      more.setAttribute('aria-haspopup', 'menu')
      more.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="19" cy="12" r="1.6" fill="currentColor"/></svg>'
      more.addEventListener('click', event => {
        event.stopPropagation()
        openChatMenu(li, item)
      })

      li.append(button, more)
      list.append(li)
    })
  } catch (error) {
    list.innerHTML = '<li class="recent-empty">Could not load conversations</li>'
    console.error('Could not load conversations', error)
  }
}

async function loadTasks() {
  const list = document.getElementById('task-list')
  if (!list) return
  list.innerHTML = '<li class="task-empty">Loading tasks…</li>'
  try {
    const response = await fetch(`${API_BASE}/api/calendar/tasks?completed=false`)
    if (!response.ok) throw new Error(`Tasks returned ${response.status}`)
    const tasks = await response.json()
    list.innerHTML = ''
    if (!tasks.length) {
      list.innerHTML = '<li class="task-empty">No open tasks</li>'
      return
    }
    tasks.forEach(task => {
      const item = document.createElement('li')
      item.className = 'task-item'
      item.innerHTML = `<label><input type="checkbox" data-task-id="${task.id}" /><span class="task-check" aria-hidden="true"></span><span class="task-title"></span><span class="task-due"></span></label>`
      item.querySelector('.task-title').textContent = task.title
      if (task.due_date) {
        const due = new Date(task.due_date)
        item.querySelector('.task-due').textContent = due.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
      }
      item.querySelector('input').addEventListener('change', async event => {
        const checkbox = event.currentTarget
        checkbox.disabled = true
        try {
          const complete = await fetch(`${API_BASE}/api/calendar/tasks/${task.id}/complete`, { method: 'PATCH' })
          if (!complete.ok) throw new Error(`Task completion returned ${complete.status}`)
          item.classList.add('is-complete')
          setTimeout(() => item.remove(), 220)
        } catch (error) {
          checkbox.checked = false
          checkbox.disabled = false
          console.error('Could not complete task', error)
        }
      })
      list.append(item)
    })
  } catch (error) {
    list.innerHTML = '<li class="task-empty">Could not load tasks</li>'
    console.error('Could not load tasks', error)
  }
}

// The chatbox shows where answers come from (the provider), not the full model
// tag — those are long and unreadable. The exact model stays in the tooltip.
const PROVIDER_LABELS = {
  ollama: 'Ollama',
  'openai-compatible': 'OpenAI-compatible',
  'nvidia-nim': 'NVIDIA NIM',
  anthropic: 'Anthropic',
  google: 'Google',
  groq: 'Groq',
  cohere: 'Cohere',
  mistral: 'Mistral',
}

fetch(`${API_BASE}/api/system/health`)
  .then(response => response.ok ? response.json() : Promise.reject(new Error('health check failed')))
  .then(status => {
    const modelLabel = document.getElementById('model-label')
    if (!modelLabel) return
    const provider = String(status.llm_provider || 'ollama').toLowerCase()
    modelLabel.textContent = PROVIDER_LABELS[provider] || status.llm_provider
    if (status.model) modelLabel.parentElement.title = status.model
  })
  .catch(() => {
    const modelLabel = document.getElementById('model-label')
    if (modelLabel) modelLabel.textContent = 'Ollama'
  })

function formatMessageTime(date) {
  if (Number.isNaN(date.getTime())) date = new Date()
  const clock = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return clock
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) return `Yesterday ${clock}`
  return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${clock}`
}

function appendUserMessage(text, attachments = [], sentAt = null) {
  setEmptyState(false)
  const row = document.createElement('div')
  row.className = 'msg-row msg-row-user'
  row.innerHTML = `<div class="bubble bubble-user"><p></p></div><span class="avatar avatar-sm">J</span>`
  row.querySelector('p').textContent = text
  if (attachments.length) {
    const list = document.createElement('div')
    list.className = 'msg-attachments'
    attachments.forEach(att => list.append(buildFileChip(att, { sent: true })))
    row.querySelector('.bubble').prepend(list)
  }
  conversation?.append(row)
  const time = document.createElement('p')
  time.className = 'msg-time msg-time-user'
  // History shows when each message was actually sent (API times are UTC ISO).
  time.textContent = formatMessageTime(sentAt ? new Date(sentAt) : new Date())
  conversation?.append(time)
}

function createAssistantMessage() {
  const row = document.createElement('div')
  row.className = 'msg-row msg-row-luna'
  row.innerHTML = `<span class="avatar avatar-luna"><img src="../../resources/logo_icon.png" width="16" height="16" alt="" /></span><div class="bubble bubble-luna"><div class="md"></div></div>`
  conversation?.append(row)
  return row.querySelector('.bubble .md')
}

// Command tags are executed by the backend and stripped from live replies, but
// stored history still contains them — hide them when re-rendering.
const COMMAND_TAG_RE = /\s*\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|FACE|WEB_SEARCH|WEB_RESEARCH|WEB_FETCH|AWAY):[^\]]*\]/g

// Result cards (product photos etc.) ride along as <!--luna-cards:[...]-->.
const CARDS_RE = /<!--luna-cards:([\s\S]*?)-->/

// Luna replies are Markdown; markdown.js escapes everything before adding tags.
function setAssistantContent(element, markdown) {
  let text = String(markdown || '').replace(COMMAND_TAG_RE, '').trim()
  let cards = []
  const match = text.match(CARDS_RE)
  if (match) {
    try { cards = JSON.parse(match[1]) } catch { cards = [] }
    text = text.replace(CARDS_RE, '').trim()
  }
  if (typeof window.renderMarkdown !== 'function') {
    element.textContent = text
    return
  }
  const cardsHtml = cards.length && typeof window.renderCards === 'function' ? window.renderCards(cards) : ''
  element.innerHTML = cardsHtml + window.renderMarkdown(text)
}

// A card image that fails to load (hotlink-blocked, removed) collapses to a
// neutral placeholder instead of a broken-image icon.
conversation?.addEventListener('error', event => {
  const img = event.target
  if (img instanceof HTMLImageElement && img.closest('.md-card-img')) {
    img.closest('.md-card-img').classList.add('is-empty')
    img.remove()
  }
}, true)

// Links in replies open in the system browser — never navigate the app window.
conversation?.addEventListener('click', event => {
  const anchor = event.target.closest('a.md-link')
  if (!anchor) return
  event.preventDefault()
  window.electronAPI?.openUrl?.(anchor.href)
})

async function sendMessage({ spoken, onPart } = {}) {
  let text = (spoken ?? composerInput.value).trim()
  if (streamFor(activeConversationId) || (!text && !pendingAttachments.length)) return
  if (pendingAttachments.some(a => a.status === 'uploading')) {
    // Like hosted chat apps: the message goes out once its files are ready.
    sendBtn.classList.add('is-waiting')
    await Promise.allSettled(pendingAttachments.map(a => a.promise))
    sendBtn.classList.remove('is-waiting')
  }
  const ready = pendingAttachments.filter(a => a.status === 'ready').map(a => a.data)
  if (!text && !ready.length) return
  if (!text) text = ready.length === 1 ? 'Take a look at this file.' : 'Take a look at these files.'

  const origin = { conversationId: activeConversationId, view: viewToken }
  const stream = { conversationId: activeConversationId, row: null }
  liveStreams.add(stream)
  updateSendState()
  if (spoken === undefined) composerInput.value = ''
  clearPendingAttachments()
  appendUserMessage(text, ready)
  const assistantText = createAssistantMessage()
  stream.row = assistantText.closest('.msg-row')
  assistantText.textContent = ready.length ? 'Reading your file' + (ready.length > 1 ? 's' : '') + '…' : 'Thinking…'
  conversation.scrollTop = conversation.scrollHeight
  // Only follow this stream's conversation while the user is still looking at it.
  const stillHere = () => viewToken === origin.view

  try {
    // A just-clicked "New chat" must reach the backend first, or this message
    // would be appended to the previous active conversation.
    await contextSync
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        conversation_id: activeConversationId,
        attachment_ids: ready.map(a => a.id),
      }),
    })
    if (!response.ok || !response.body) throw new Error(`Backend returned ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const steps = typeof window.createAgentSteps === 'function' ? window.createAgentSteps(assistantText) : null
    let buffer = ''
    let assistant = ''
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      const events = buffer.split(/\n\n/)
      buffer = events.pop() || ''
      for (const event of events) {
        const line = event.split('\n').find(item => item.startsWith('data:'))
        if (!line) continue
        const payload = JSON.parse(line.slice(5).trim())
        if (steps && steps.handle(payload)) {
          // Tool steps render in their own panel; drop the "Thinking…" placeholder.
          if (!assistant && payload.type === 'tool_call') assistantText.textContent = ''
        } else if (payload.type === 'meta' || payload.type === 'done') {
          if (payload.conversation_id) {
            stream.conversationId = payload.conversation_id
            if (stillHere()) activeConversationId = payload.conversation_id
          }
        } else if (payload.type === 'message_part') {
          // The backend streams one paragraph per part without separators.
          const part = payload.content || ''
          const needsBreak = assistant && part && !/\n\s*$/.test(assistant) && !/^\s*\n/.test(part)
          assistant += needsBreak ? `\n\n${part}` : part
          setAssistantContent(assistantText, assistant)
          if (part) onPart?.(part)
        } else if (payload.type === 'error') {
          throw new Error(payload.message || 'Luna could not respond')
        }
        if (stream.row?.isConnected) conversation.scrollTop = conversation.scrollHeight
      }
      if (done) break
    }
    if (!assistant) assistantText.textContent = 'I did not receive a response.'
    await loadConversations()
    return assistant
  } catch (error) {
    assistantText.textContent = `I couldn't reach Luna's backend. ${error.message}`
    assistantText.classList.add('chat-error')
    throw error
  } finally {
    liveStreams.delete(stream)
    updateSendState()
    if (stream.row?.isConnected) composerInput.focus()
  }
}

function flashSend() {
  if (!composerInput.value.trim() || streamFor(activeConversationId)) return
  sendBtn.style.transform = 'scale(0.9)'
  setTimeout(() => { sendBtn.style.transform = '' }, 120)
  sendMessage().catch(() => {})   // the error is already shown in the reply bubble
}

// Voice mode (voice-input.js) sends spoken turns through the normal chat path
// and hears each reply paragraph as it streams in.
window.lunaChat = {
  isBusy: () => !!streamFor(activeConversationId),
  send(text, { onPart } = {}) {
    return sendMessage({ spoken: text, onPart })
  },
}
sendBtn?.addEventListener('click', flashSend)
composerInput?.addEventListener('keydown', e => {
  if (e.key === 'Enter') flashSend()
})
loadConversations()

async function initializeChat() {
  try {
    const response = await fetch(`${API_BASE}/api/chat/context`)
    const context = response.ok ? await response.json() : {}
    if (context.active_conversation_id) {
      await openConversation(context.active_conversation_id)
    } else {
      startNewChat()
    }
  } catch (error) {
    console.error('Could not initialize chat', error)
    startNewChat()
  }
}

initializeChat()

// ── Dashboard toggle (UI only — clicking the Luna logo swaps the view) ─────
const brandBtn = document.getElementById('brand-btn')
const viewChat = document.getElementById('view-chat')
const viewDashboard = document.getElementById('view-dashboard')
const viewCapabilities = document.getElementById('view-capabilities')
const viewSettings = document.getElementById('view-settings')

// Exactly one view is visible at a time — hiding only some of them left the
// previous view stacked under the new one.
function showView(target) {
  ;[viewChat, viewDashboard, viewCapabilities, viewSettings].forEach(view => {
    view?.classList.toggle('is-hidden', view !== target)
  })
  const navFor = { [viewCapabilities?.id]: 'capabilities', [viewSettings?.id]: 'settings' }
  document.querySelectorAll('.nav-item[data-nav="capabilities"], .nav-item[data-nav="settings"]').forEach(item => {
    item.classList.toggle('is-active', navFor[target?.id] === item.dataset.nav)
  })
}

function showDashboard() {
  showView(viewDashboard)
  renderCalendar()
  loadTasks()
  loadDevDashboard()
}
function showChat() {
  showView(viewChat)
}
brandBtn?.addEventListener('click', () => {
  const dashboardOpen = !viewDashboard.classList.contains('is-hidden')
  if (dashboardOpen) showChat()
  else showDashboard()
})

// ── Activity calendar (real): messages per local day from the backend ──────
let calendarMonth = (() => { const d = new Date(); return { year: d.getFullYear(), month: d.getMonth() } })()
let calendarData = null

async function renderCalendar() {
  const grid = document.getElementById('calendar-grid')
  const label = document.getElementById('dashboard-month-label')
  const navLabel = document.getElementById('month-nav-label')
  const now = new Date()
  const { year, month } = calendarMonth
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth()
  label.textContent = now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  if (navLabel) navLabel.textContent = new Date(year, month, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const nextBtn = document.getElementById('month-next')
  if (nextBtn) nextBtn.disabled = isCurrentMonth

  try {
    const response = await fetch(`${API_BASE}/api/chat/activity?year=${year}&month=${month + 1}`)
    if (!response.ok) throw new Error(`Activity returned ${response.status}`)
    calendarData = await response.json()
  } catch (error) {
    console.error('Could not load activity', error)
    calendarData = { days: [], total_messages: null, streak: null, most_active: null }
  }

  const byDay = new Map((calendarData.days || []).map(d => [d.day, d]))
  const firstWeekday = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  grid.innerHTML = ''
  const addCell = (day, className, title) => {
    const cell = document.createElement('div')
    cell.className = className
    if (day != null) {
      cell.innerHTML = `<span class="cal-day-num">${day}</span>`
      cell.dataset.day = String(day)
      cell.title = title
      cell.addEventListener('click', () => selectDay(day))
    }
    grid.appendChild(cell)
  }
  for (let i = 0; i < firstWeekday; i++) addCell(null, 'cal-day is-empty')
  for (let day = 1; day <= daysInMonth; day++) {
    const info = byDay.get(day) || { level: 0, messages: 0 }
    const isToday = isCurrentMonth && day === now.getDate()
    const isFuture = isCurrentMonth && day > now.getDate()
    const title = info.messages ? `${info.messages} message${info.messages === 1 ? '' : 's'}` : 'No chats'
    addCell(day, `cal-day level-${info.level}${isToday ? ' is-today' : ''}${isFuture ? ' is-future' : ''}`, title)
  }
  const trailing = (7 - ((firstWeekday + daysInMonth) % 7)) % 7
  for (let i = 0; i < trailing; i++) addCell(null, 'cal-day is-empty')

  const total = calendarData.total_messages
  document.getElementById('stat-messages').textContent = total == null ? '—' : total.toLocaleString()
  const streak = calendarData.streak
  document.getElementById('stat-streak').textContent = streak == null ? '—' : `${streak} day${streak === 1 ? '' : 's'}`
  document.getElementById('stat-active').textContent = calendarData.most_active || '—'
  const monthLabel = document.querySelector('#stat-messages + .stat-label')
  if (monthLabel) monthLabel.textContent = isCurrentMonth ? 'Messages this month' : 'Messages that month'

  selectDay(isCurrentMonth ? now.getDate() : daysInMonth)
}

document.getElementById('month-prev')?.addEventListener('click', () => {
  calendarMonth = calendarMonth.month === 0 ? { year: calendarMonth.year - 1, month: 11 } : { year: calendarMonth.year, month: calendarMonth.month - 1 }
  renderCalendar()
})
document.getElementById('month-next')?.addEventListener('click', () => {
  const now = new Date()
  if (calendarMonth.year === now.getFullYear() && calendarMonth.month === now.getMonth()) return
  calendarMonth = calendarMonth.month === 11 ? { year: calendarMonth.year + 1, month: 0 } : { year: calendarMonth.year, month: calendarMonth.month + 1 }
  renderCalendar()
})

function selectDay(day) {
  document.querySelectorAll('.cal-day').forEach(cell => cell.classList.remove('is-selected'))
  document.querySelector(`.cal-day[data-day="${day}"]`)?.classList.add('is-selected')

  const now = new Date()
  const { year, month } = calendarMonth
  const isToday = year === now.getFullYear() && month === now.getMonth() && day === now.getDate()
  document.getElementById('day-detail-date').textContent = isToday
    ? 'Today'
    : new Date(year, month, day).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

  const info = (calendarData?.days || []).find(d => d.day === day) || { messages: 0, chats: 0, topics: [] }
  const activity = document.getElementById('day-activity')
  const topics = document.getElementById('day-topics')
  if (activity) {
    activity.textContent = info.messages
      ? `${info.messages} message${info.messages === 1 ? '' : 's'} across ${info.chats} chat${info.chats === 1 ? '' : 's'}`
      : 'No chats this day'
  }
  if (topics) {
    topics.replaceChildren(...(info.topics || []).map(topic => {
      const li = document.createElement('li')
      li.textContent = topic
      return li
    }))
  }
}


// ── Reminders from Luna (event heads-ups, task due) ─────────────────────────
// The backend also raises a Windows notification; this shows it in-app too.
const toastHost = document.createElement('div')
toastHost.className = 'luna-toasts'
document.body.append(toastHost)

function showToast(message) {
  const toast = document.createElement('div')
  toast.className = 'luna-toast'
  const text = document.createElement('span')
  text.textContent = message
  const close = document.createElement('button')
  close.type = 'button'
  close.setAttribute('aria-label', 'Dismiss')
  close.textContent = '×'
  close.addEventListener('click', () => toast.remove())
  toast.append(text, close)
  toastHost.append(toast)
  setTimeout(() => toast.classList.add('is-leaving'), 12000)
  setTimeout(() => toast.remove(), 12600)
}

async function pollReminders() {
  try {
    const response = await fetch(`${API_BASE}/api/system/proactive`)
    if (response.ok) ((await response.json()).messages || []).forEach(showToast)
  } catch { /* backend restarting — try again next tick */ }
}
setInterval(pollReminders, 30000)

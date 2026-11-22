/**
 * News tab: headlines by category from BBC, The Guardian and NPR
 * (GET /api/news). The first story is shown large; tapping a story opens the
 * article. The chosen category is remembered on this device.
 *
 * Swipe a story left (touch, mouse drag or a two-finger trackpad swipe) to
 * reveal "Ask Luna"; a long swipe goes straight to it. Asking opens a new chat
 * with the story as context. Mouse and keyboard users also get an Ask button.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const tabs = document.getElementById('news-tabs')
  const grid = document.getElementById('news-grid')
  const title = document.getElementById('news-title')
  const sub = document.getElementById('news-sub')
  const refreshBtn = document.getElementById('news-refresh')
  if (!tabs || !grid) return

  const KEY = 'luna_news_category'
  const HINT_KEY = 'luna_news_ask_seen'
  const hint = document.getElementById('news-hint')
  try { if (hint && localStorage.getItem(HINT_KEY)) hint.hidden = true } catch { /* fine */ }
  let category = (() => { try { return localStorage.getItem(KEY) || 'top' } catch { return 'top' } })()
  let requestId = 0
  let loadedAt = 0

  function openStory(url) {
    if (!/^https?:\/\//.test(url)) return
    if (window.electronAPI?.openUrl) window.electronAPI.openUrl(url)
    else window.open(url, '_blank', 'noopener')
  }

  function renderTabs(categories) {
    tabs.replaceChildren(...categories.map(c => {
      const button = document.createElement('button')
      button.type = 'button'
      button.className = `capability-filter${c.key === category ? ' is-active' : ''}`
      button.setAttribute('role', 'tab')
      button.setAttribute('aria-selected', String(c.key === category))
      button.textContent = c.key === 'top' ? 'Top' : c.label
      button.addEventListener('click', () => {
        if (c.key === category) return
        category = c.key
        try { localStorage.setItem(KEY, category) } catch { /* fine */ }
        load()
      })
      return button
    }))
    // On phones the pills scroll sideways: keep the chosen one in view.
    tabs.querySelector('.is-active')?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }

  // ── Ask Luna about a story ───────────────────────────────────────────────
  const askSheet = document.getElementById('news-ask')
  const askForm = document.getElementById('news-ask-form')
  const askInput = document.getElementById('news-ask-input')
  let askStory = null
  let askReturnFocus = null

  function openAsk(s) {
    if (!askSheet) return
    closeSwiped()
    askStory = s
    askReturnFocus = document.activeElement
    document.getElementById('news-ask-meta').textContent = [s.source, s.ago].filter(Boolean).join(' · ')
    document.getElementById('news-ask-title').textContent = s.title
    askInput.value = ''
    if (hint) hint.hidden = true           // they've found it
    try { localStorage.setItem(HINT_KEY, '1') } catch { /* fine */ }
    askSheet.hidden = false
    askInput.focus()
  }

  function closeAsk() {
    if (!askSheet || askSheet.hidden) return
    askSheet.hidden = true
    askStory = null
    if (askReturnFocus && document.contains(askReturnFocus)) askReturnFocus.focus()
  }

  function ask(question) {
    const s = askStory
    question = String(question || '').trim()
    if (!s || !question) return
    closeAsk()
    // Question first so the chat reads naturally; the story follows as context.
    const lines = [question, '', `News story: “${s.title}”`, [s.source, s.ago].filter(Boolean).join(' · ')]
    if (s.summary) lines.push(s.summary)
    lines.push(s.link)
    window.lunaAskInNewChat?.(lines.filter((line, i) => line || i === 1).join('\n'))
  }

  if (askSheet) {
    askSheet.addEventListener('click', event => { if (event.target === askSheet) closeAsk() })
    document.getElementById('news-ask-close').addEventListener('click', closeAsk)
    document.getElementById('news-ask-chips').addEventListener('click', event => {
      if (event.target.closest('button')) ask(event.target.closest('button').textContent)
    })
    askForm.addEventListener('submit', event => { event.preventDefault(); ask(askInput.value) })
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !askSheet.hidden) closeAsk() })
  }

  // ── Swipe left to reveal "Ask Luna" ──────────────────────────────────────
  // The card follows the finger with a GPU transform (one write per frame, no
  // style changes on the card's image or text), and a release springs to the
  // nearest state, or the flick direction when the finger was moving fast.
  const REVEAL = 112          // px the card slides to show the action
  const FLICK = 0.45          // px/ms: a flick this fast decides on its own
  const EASE = 'transform 0.42s cubic-bezier(.2,.9,.25,1)'
  let swiped = null           // the one story currently slid open

  function paint(item, x) {
    const card = item._card
    card.style.transform = x ? `translate3d(${x}px,0,0)` : ''
    // The action fades and grows in with the reveal (opacity/transform only).
    const p = Math.min(1, -x / REVEAL)
    item._action.style.opacity = String(p)
    item._actionInner.style.transform = `scale(${0.85 + 0.15 * p})`
  }

  function slideTo(item, x) {
    const card = item._card
    card.style.transition = EASE
    item._actionInner.style.transition = EASE
    item._action.style.transition = 'opacity 0.3s ease'
    paint(item, x)
    item.classList.toggle('is-open', x < 0)
    card.addEventListener('transitionend', () => {
      card.style.transition = ''
      card.style.willChange = ''
    }, { once: true })
  }

  function closeSwiped(except) {
    if (swiped && swiped !== except) slideTo(swiped, 0)
    if (swiped !== except) swiped = null
  }

  function settle(item, s, x, velocity) {
    const width = item.getBoundingClientRect().width
    if (x < -width * 0.55) {                       // long swipe: straight to the question
      slideTo(item, 0)
      swiped = null
      openAsk(s)
    } else if (velocity < -FLICK || (velocity <= FLICK && x < -REVEAL / 2)) {
      slideTo(item, -REVEAL)
      swiped = item
    } else {
      slideTo(item, 0)
      if (swiped === item) swiped = null
    }
  }

  // px/ms over the last ~100 ms of movement; 0 if the finger paused before lifting.
  function flickSpeed(samples, upTime) {
    const last = samples[samples.length - 1]
    if (!last || upTime - last[0] > 90) return 0
    const first = samples.find(([t]) => last[0] - t <= 100) || last
    const elapsed = last[0] - first[0]
    return elapsed >= 8 ? (last[1] - first[1]) / elapsed : 0
  }

  function enableSwipe(item, card, s) {
    let start = null
    let dragging = false
    let suppressClick = false
    let frame = 0
    let x = 0
    let samples = []                               // recent [time, clientX] for flick speed

    const offset = dx => {
      const raw = Math.min(0, start.base + dx)
      // Past the action it resists, like it's attached by a spring.
      return raw < -REVEAL ? -REVEAL + (raw + REVEAL) * 0.35 : raw
    }

    card.addEventListener('pointerdown', event => {
      if (event.button !== 0) return
      const base = item.classList.contains('is-open') ? -REVEAL : 0
      start = { x: event.clientX, y: event.clientY, base, id: event.pointerId }
      dragging = false
      samples = [[event.timeStamp, event.clientX]]
    })
    card.addEventListener('pointermove', event => {
      if (!start || event.pointerId !== start.id) return
      const dx = event.clientX - start.x
      const dy = event.clientY - start.y
      if (!dragging) {
        if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx)) { start = null; return }   // a scroll
        if (Math.abs(dx) < 6) return
        dragging = true
        closeSwiped(item)
        card.setPointerCapture?.(event.pointerId)
        card.style.transition = 'none'
        item._actionInner.style.transition = 'none'
        item._action.style.transition = 'none'
        card.style.willChange = 'transform'
        start.x = event.clientX                    // no jump from the dead zone
      }
      samples.push([event.timeStamp, event.clientX])
      if (samples.length > 12) samples.shift()
      x = offset(event.clientX - start.x)
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; paint(item, x) })
    })
    const finish = event => {
      if (!start || event.pointerId !== start.id) return
      if (dragging) {
        cancelAnimationFrame(frame)
        frame = 0
        suppressClick = true
        const velocity = flickSpeed(samples, event.timeStamp)
        settle(item, s, offset(event.clientX - start.x), velocity)
      }
      start = null
      dragging = false
    }
    card.addEventListener('pointerup', finish)
    card.addEventListener('pointercancel', () => {
      if (!start) return
      cancelAnimationFrame(frame)
      frame = 0
      if (dragging) slideTo(item, start.base)
      start = null
      dragging = false
    })

    // A click right after a drag is the end of the swipe, not "open the article".
    card.addEventListener('click', event => {
      event.preventDefault()
      if (suppressClick) { suppressClick = false; return }
      if (item.classList.contains('is-open')) { slideTo(item, 0); swiped = null; return }
      openStory(s.link)
    })

    // Two-finger trackpad swipe sends horizontal wheel events.
    let wheelX = 0
    let wheelTimer = null
    item.addEventListener('wheel', event => {
      if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return
      event.preventDefault()
      wheelX += event.deltaX
      clearTimeout(wheelTimer)
      wheelTimer = setTimeout(() => { wheelX = 0 }, 180)
      if (wheelX > 60 && !item.classList.contains('is-open')) {
        closeSwiped(item); slideTo(item, -REVEAL); swiped = item; wheelX = 0
      } else if (wheelX < -60 && item.classList.contains('is-open')) {
        slideTo(item, 0); swiped = null; wheelX = 0
      }
    }, { passive: false })
  }

  document.addEventListener('pointerdown', event => {
    if (swiped && !swiped.contains(event.target)) closeSwiped()
  })

  function story(s, lead) {
    const item = document.createElement('div')
    item.className = `news-item${lead ? ' is-lead' : ''}`

    const action = document.createElement('button')
    action.type = 'button'
    action.className = 'news-swipe-action'
    action.tabIndex = -1                 // keyboard users get the Ask button instead
    action.innerHTML = '<span class="news-swipe-inner"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" fill="currentColor"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" fill="currentColor" opacity=".7"/></svg><span>Ask Luna</span></span>'
    action.addEventListener('click', () => openAsk(s))
    item._action = action
    item._actionInner = action.firstElementChild

    const card = document.createElement('a')
    card.className = `news-card${lead ? ' is-lead' : ''}${s.image ? '' : ' no-image'}`
    card.href = s.link
    card.draggable = false
    item._card = card
    enableSwipe(item, card, s)

    const askBtn = document.createElement('button')
    askBtn.type = 'button'
    askBtn.className = 'news-ask-btn'
    askBtn.textContent = 'Ask Luna'
    askBtn.title = 'Ask Luna about this story'
    askBtn.addEventListener('click', () => openAsk(s))

    if (s.image) {
      const media = document.createElement('span')
      media.className = 'news-card-img'
      const img = document.createElement('img')
      img.src = s.image
      img.alt = ''
      img.loading = 'lazy'
      img.referrerPolicy = 'no-referrer'
      img.draggable = false
      img.addEventListener('error', () => { media.remove(); card.classList.add('no-image') })
      media.append(img)
      card.append(media)
    }
    const body = document.createElement('span')
    body.className = 'news-card-body'
    const meta = document.createElement('span')
    meta.className = 'news-card-meta'
    meta.textContent = [s.source, s.ago].filter(Boolean).join(' · ')
    const heading = document.createElement('span')
    heading.className = 'news-card-title'
    heading.textContent = s.title
    body.append(meta, heading)
    if (s.summary && (lead || !s.image)) {
      const summary = document.createElement('span')
      summary.className = 'news-card-summary'
      summary.textContent = s.summary
      body.append(summary)
    }
    card.append(body)
    item.append(action, card, askBtn)
    return item
  }

  function message(text, tone = '') {
    const p = document.createElement('p')
    p.className = `news-empty${tone ? ' is-' + tone : ''}`
    p.textContent = text
    grid.replaceChildren(p)
  }

  async function load({ refresh = false } = {}) {
    const id = ++requestId
    refreshBtn.disabled = true
    if (!grid.children.length || !refresh) message('Loading headlines…')
    try {
      const response = await fetch(`${API}/api/news?category=${encodeURIComponent(category)}${refresh ? '&refresh=true' : ''}`)
      if (!response.ok) throw new Error(`News returned ${response.status}`)
      const data = await response.json()
      if (id !== requestId) return
      category = data.category
      renderTabs(data.categories || [])
      title.textContent = data.category === 'top' ? 'News' : data.label
      const stories = data.stories || []
      if (!stories.length) {
        message('Couldn’t reach the news feeds just now. Try Refresh in a minute.', 'error')
      } else {
        const leadIndex = Math.max(0, stories.findIndex(s => s.image))
        const ordered = [stories[leadIndex], ...stories.filter((_s, i) => i !== leadIndex)]
        swiped = null
        grid.replaceChildren(...ordered.map((s, i) => story(s, i === 0)))
        grid.scrollTop = 0
      }
      loadedAt = Date.now()
      sub.textContent = `Headlines from BBC, The Guardian and NPR · updated ${new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
    } catch (error) {
      if (id === requestId) message('Couldn’t load the news. Is Luna’s server running?', 'error')
      console.error('News load failed', error)
    } finally {
      if (id === requestId) refreshBtn.disabled = false
    }
  }

  refreshBtn.addEventListener('click', () => load({ refresh: true }))

  // Opening the tab reuses what's on screen unless it's more than 10 minutes old.
  window.loadNewsView = () => {
    if (!loadedAt || Date.now() - loadedAt > 10 * 60 * 1000) load()
  }
})()

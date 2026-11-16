/**
 * News tab: headlines by category from BBC, The Guardian and NPR
 * (GET /api/news). The first story is shown large; tapping a story opens the
 * article. The chosen category is remembered on this device.
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

  function story(s, lead) {
    const card = document.createElement('a')
    card.className = `news-card${lead ? ' is-lead' : ''}${s.image ? '' : ' no-image'}`
    card.href = s.link
    card.addEventListener('click', event => { event.preventDefault(); openStory(s.link) })

    if (s.image) {
      const media = document.createElement('span')
      media.className = 'news-card-img'
      const img = document.createElement('img')
      img.src = s.image
      img.alt = ''
      img.loading = 'lazy'
      img.referrerPolicy = 'no-referrer'
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
    return card
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

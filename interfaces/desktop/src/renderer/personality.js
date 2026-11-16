/**
 * Personality panel at the bottom of the sidebar: Luna's current mood, energy and the
 * conversation style she has learned (from /api/memory/personality).
 *
 * Shown or hidden by Settings → Appearance → Personality panel (show_personality_panel).
 * Refreshes after every reply (the `luna:reply-done` event from app.js) and once a minute.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const card = document.getElementById('persona-card')
  if (!card) return

  const MOODS = {
    happy:       { label: 'Happy',       color: '#fbbf24' },
    playful:     { label: 'Playful',     color: '#f472b6' },
    thoughtful:  { label: 'Thoughtful',  color: '#818cf8' },
    excited:     { label: 'Excited',     color: '#fb923c' },
    concerned:   { label: 'Concerned',   color: '#60a5fa' },
    warm:        { label: 'Warm',        color: '#f9a8d4' },
    neutral:     { label: 'Calm',        color: '#a1a1aa' },
    curious:     { label: 'Curious',     color: '#34d399' },
    melancholic: { label: 'Quiet',       color: '#94a3b8' },
  }
  // Learned style, from the engine's preference learning (0..1 each)
  const TRAITS = [
    ['humor', 'Humor'],
    ['emotional_support', 'Warmth'],
    ['depth', 'Depth'],
    ['verbosity', 'Detail'],
    ['question_frequency', 'Curiosity'],
    ['formality', 'Formality'],
  ]
  const STYLE_KEY = 'luna_persona_style_open'
  const REFRESH_MS = 60_000

  let enabled = false
  let timer = null

  const el = id => card.querySelector(`[data-persona="${id}"]`)
  const pct = value => `${Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100)}%`

  function storedOpen() {
    try { return localStorage.getItem(STYLE_KEY) === '1' } catch { return false }
  }

  function setStyleOpen(open) {
    card.classList.toggle('is-style-open', open)
    el('style-toggle').setAttribute('aria-expanded', String(open))
    try { localStorage.setItem(STYLE_KEY, open ? '1' : '0') } catch { /* private mode */ }
  }

  function render(state) {
    const mood = MOODS[state.current_mood] || { label: state.current_mood || 'Calm', color: '#a1a1aa' }
    el('mood').textContent = mood.label
    el('dot').style.background = mood.color
    el('dot').style.boxShadow = `0 0 ${6 + 10 * (state.mood_intensity || 0)}px ${mood.color}`
    el('energy-bar').style.width = pct(state.energy_level)
    el('energy-value').textContent = pct(state.energy_level)

    const traits = el('traits')
    traits.replaceChildren(...TRAITS.map(([key, label]) => {
      const row = document.createElement('div')
      row.className = 'persona-trait'
      row.innerHTML = '<span class="persona-trait-name"></span><span class="persona-trait-track"><span class="persona-trait-fill"></span></span>'
      row.querySelector('.persona-trait-name').textContent = label
      row.querySelector('.persona-trait-fill').style.width = pct(state[key])
      row.title = `${label}: ${pct(state[key])}`
      return row
    }))

    const n = Number(state.total_interactions) || 0
    el('count').textContent = n === 1 ? 'Shaped by 1 conversation' : `Shaped by ${n.toLocaleString()} conversations`
  }

  async function refresh() {
    if (!enabled) return
    try {
      const response = await fetch(`${API}/api/memory/personality`)
      if (!response.ok) throw new Error(`personality ${response.status}`)
      render(await response.json())
      card.classList.remove('is-offline')
    } catch {
      card.classList.add('is-offline')   // keep the last state; it updates when the server answers
    }
  }

  function setEnabled(on) {
    enabled = Boolean(on)
    card.hidden = !enabled
    clearInterval(timer)
    timer = null
    if (enabled) {
      refresh()
      timer = setInterval(refresh, REFRESH_MS)
    }
  }

  function parseFlag(value) {
    return value === true || String(value).toLowerCase() === 'true'
  }

  async function init() {
    setStyleOpen(storedOpen())
    el('style-toggle').addEventListener('click', () => setStyleOpen(!card.classList.contains('is-style-open')))
    try {
      const response = await fetch(`${API}/api/settings`)
      const fields = response.ok ? (await response.json()).fields || [] : []
      const field = fields.find(f => f.key === 'show_personality_panel')
      setEnabled(field ? parseFlag(field.value) : true)
    } catch {
      setEnabled(true)   // server still starting: show it and let refresh() catch up
    }
  }

  window.addEventListener('luna:settings', event => {
    if (event.detail && 'show_personality_panel' in event.detail) setEnabled(parseFlag(event.detail.show_personality_panel))
  })
  window.addEventListener('luna:reply-done', () => refresh())

  init()
})()

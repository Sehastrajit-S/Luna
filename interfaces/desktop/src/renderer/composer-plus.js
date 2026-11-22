/**
 * The composer's + button: attach files, or pick a skill for the next message
 * (e.g. Compare store prices). A picked skill shows as a chip in the composer
 * and is sent with that one message (POST /api/chat/stream `skill`); the
 * server then answers with that skill instead of guessing.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const plusBtn = document.getElementById('plus-btn')
  const menu = document.getElementById('plus-menu')
  const skillsBox = document.getElementById('plus-skills')
  const attachItem = document.getElementById('attach-btn')
  const chip = document.getElementById('skill-chip')
  const chipName = document.getElementById('skill-chip-name')
  const chipRemove = document.getElementById('skill-chip-remove')
  const input = document.querySelector('.composer-input')
  if (!plusBtn || !menu || !input) return

  const defaultPlaceholder = input.placeholder
  let current = null
  let loaded = false

  const ICONS = { 'store-prices': '$' }

  const panels = {
    root: menu.querySelector('[data-panel="root"]'),
    skills: menu.querySelector('[data-panel="skills"]'),
  }

  function activePanel() {
    return panels.skills && !panels.skills.hidden ? 'skills' : 'root'
  }

  function items() {
    return [...(panels[activePanel()] || menu).querySelectorAll('.plus-item:not([disabled]), .plus-back')]
  }

  // Skills open as a second panel inside the menu, with a back button.
  function showPanel(name) {
    for (const [key, panel] of Object.entries(panels)) if (panel) panel.hidden = key !== name
    if (name === 'skills' && !loaded) loadSkills()
    const first = name === 'skills' ? panels.skills.querySelector('.plus-item') || panels.skills.querySelector('.plus-back')
      : document.getElementById('plus-skills-open')
    first?.focus()
  }

  function open() {
    menu.hidden = false
    plusBtn.setAttribute('aria-expanded', 'true')
    plusBtn.classList.add('is-open')
    for (const [key, panel] of Object.entries(panels)) if (panel) panel.hidden = key !== 'root'
    items()[0]?.focus()
  }

  function close({ focusInput = false } = {}) {
    if (menu.hidden) return
    menu.hidden = true
    plusBtn.setAttribute('aria-expanded', 'false')
    plusBtn.classList.remove('is-open')
    if (focusInput) input.focus()
  }

  function setSkill(skill) {
    current = skill
    chip.hidden = !skill
    chipName.textContent = skill ? `${ICONS[skill.id] || '✦'} ${skill.name}` : ''
    input.placeholder = skill?.placeholder || defaultPlaceholder
    document.querySelector('.composer-bar')?.classList.toggle('has-skill', Boolean(skill))
  }

  function skillItem(skill) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'plus-item'
    btn.setAttribute('role', 'menuitem')
    btn.dataset.skill = skill.id

    const icon = document.createElement('span')
    icon.className = 'plus-item-icon'
    icon.textContent = ICONS[skill.id] || '✦'
    const text = document.createElement('span')
    text.className = 'plus-item-text'
    const name = document.createElement('span')
    name.className = 'plus-item-name'
    name.textContent = skill.name
    const desc = document.createElement('span')
    desc.className = 'plus-item-desc'
    desc.textContent = skill.ready ? skill.description : skill.setup || 'Needs setup in Settings'
    text.append(name, desc)
    // Store logos (favicons via Google) under Compare store prices.
    const icons = (skill.icons || []).filter(i => /^https:\/\/www\.google\.com\/s2\/favicons\?/.test(i.url || ''))
    if (icons.length) {
      const row = document.createElement('span')
      row.className = 'plus-item-logos'
      for (const icon of icons) {
        const img = document.createElement('img')
        img.src = icon.url
        img.alt = icon.name
        img.title = icon.name
        img.width = img.height = 16
        img.loading = 'lazy'
        img.referrerPolicy = 'no-referrer'
        row.append(img)
      }
      text.append(row)
    }
    btn.append(icon, text)
    if (!skill.ready) btn.classList.add('needs-setup')

    btn.addEventListener('click', () => {
      close()
      if (!skill.ready) {
        if (typeof openSettingsView === 'function') openSettingsView()
        return
      }
      setSkill(skill)
      input.focus()
    })
    return btn
  }

  async function loadSkills() {
    try {
      const response = await fetch(`${API}/api/skills/pickable`)
      if (!response.ok) throw new Error(`Skills returned ${response.status}`)
      const skills = (await response.json()).skills || []
      skillsBox.replaceChildren(...skills.map(skillItem))
      loaded = true
      if (activePanel() === 'skills' && menu.contains(document.activeElement)) skillsBox.querySelector('.plus-item')?.focus()
    } catch (error) {
      const p = document.createElement('p')
      p.className = 'plus-empty'
      p.textContent = 'Couldn’t load skills. Is Luna’s server running?'
      skillsBox.replaceChildren(p)
      console.error('Could not load skills for the + menu', error)
    }
  }

  plusBtn.addEventListener('click', event => {
    event.stopPropagation()
    if (menu.hidden) open()
    else close()
  })

  // attachments.js opens the file picker; the menu just gets out of the way.
  attachItem?.addEventListener('click', () => close())

  document.getElementById('plus-skills-open')?.addEventListener('click', event => {
    event.stopPropagation()
    showPanel('skills')
  })
  document.getElementById('plus-skills-back')?.addEventListener('click', event => {
    event.stopPropagation()
    showPanel('root')
  })
  document.getElementById('plus-meeting')?.addEventListener('click', () => {
    close()
    window.lunaOpenMeeting?.()
  })
  document.getElementById('plus-scan')?.addEventListener('click', () => {
    close()
    window.lunaOpenScanner?.()
  })

  document.addEventListener('click', event => {
    if (!menu.hidden && !menu.contains(event.target) && event.target !== plusBtn) close()
  })

  menu.addEventListener('keydown', event => {
    const list = items()
    const at = list.indexOf(document.activeElement)
    if (event.key === 'Escape' && activePanel() === 'skills') { event.preventDefault(); showPanel('root') }
    else if (event.key === 'Escape') { event.preventDefault(); close({ focusInput: true }) }
    else if (event.key === 'ArrowLeft' && activePanel() === 'skills') { event.preventDefault(); showPanel('root') }
    else if (event.key === 'ArrowRight' && document.activeElement?.id === 'plus-skills-open') { event.preventDefault(); showPanel('skills') }
    else if (event.key === 'ArrowDown') { event.preventDefault(); list[(at + 1) % list.length]?.focus() }
    else if (event.key === 'ArrowUp') { event.preventDefault(); list[(at - 1 + list.length) % list.length]?.focus() }
    else if (event.key === 'Tab') close()
  })

  chipRemove?.addEventListener('click', () => { setSkill(null); input.focus() })

  // Backspace in an empty box removes the skill, like removing a tag.
  input.addEventListener('keydown', event => {
    if (event.key === 'Backspace' && current && !input.value) setSkill(null)
  })

  window.lunaComposerSkill = {
    get current() { return current },
    /** The picked skill for the message being sent, then cleared: it applies once. */
    take() {
      const skill = current
      setSkill(null)
      return skill
    },
  }
})()

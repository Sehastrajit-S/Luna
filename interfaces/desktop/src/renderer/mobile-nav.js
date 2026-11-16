/**
 * Showing and hiding the sidebar.
 *
 * Wide screens: a button at the top of the sidebar hides it, and a matching
 * button in the top bar brings it back. The choice is remembered.
 * Narrow screens (see the Mobile section of styles.css): the sidebar is a
 * drawer; the top-bar button opens it and picking something closes it.
 * Ctrl+\ (⌘+\ on Mac) toggles it either way.
 */
'use strict'

;(function () {
  const sidebar = document.querySelector('.sidebar')
  const topbar = document.querySelector('.topbar')
  if (!sidebar || !topbar) return

  const narrow = window.matchMedia('(max-width: 760px)')
  const STORE_KEY = 'luna_sidebar_hidden'
  const PANEL_ICON = '<svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true"><rect x="3.5" y="4.5" width="17" height="15" rx="3" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M9.5 4.5v15" stroke="currentColor" stroke-width="1.8"/></svg>'
  const MENU_ICON = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'

  // Top bar: opens the drawer (narrow) or shows the hidden sidebar (wide).
  const showBtn = document.createElement('button')
  showBtn.type = 'button'
  showBtn.className = 'mobile-nav-btn'
  topbar.prepend(showBtn)

  // Sidebar: hides it (wide) or closes the drawer (narrow).
  const hideBtn = document.createElement('button')
  hideBtn.type = 'button'
  hideBtn.className = 'sidebar-hide-btn'
  hideBtn.innerHTML = PANEL_ICON
  sidebar.prepend(hideBtn)

  const backdrop = document.createElement('div')
  backdrop.className = 'mobile-nav-backdrop'
  backdrop.setAttribute('aria-hidden', 'true')
  document.body.append(backdrop)

  const shortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘\\' : 'Ctrl+\\'

  function remembered() {
    try { return localStorage.getItem(STORE_KEY) === '1' } catch { return false }
  }

  function render() {
    const drawerOpen = document.body.classList.contains('nav-open')
    const hidden = document.body.classList.contains('sidebar-hidden')
    if (narrow.matches) {
      showBtn.innerHTML = MENU_ICON
      showBtn.setAttribute('aria-label', drawerOpen ? 'Close menu' : 'Open menu')
      showBtn.setAttribute('aria-expanded', String(drawerOpen))
      hideBtn.setAttribute('aria-label', 'Close menu')
      hideBtn.title = 'Close menu'
    } else {
      showBtn.innerHTML = PANEL_ICON
      showBtn.setAttribute('aria-label', 'Show sidebar')
      showBtn.title = `Show sidebar (${shortcut})`
      showBtn.removeAttribute('aria-expanded')
      hideBtn.setAttribute('aria-label', 'Hide sidebar')
      hideBtn.title = `Hide sidebar (${shortcut})`
    }
    sidebar.toggleAttribute('inert', !narrow.matches && hidden)
  }

  function setDrawer(open) {
    document.body.classList.toggle('nav-open', open)
    render()
  }

  // The desktop app's window controls live in the sidebar; while it's hidden
  // they move to the top bar (moving keeps their click handlers).
  const windowControls = sidebar.querySelector('.traffic-lights')
  function placeWindowControls() {
    if (!windowControls || document.documentElement.classList.contains('is-web')) return
    const hidden = document.body.classList.contains('sidebar-hidden') && !narrow.matches
    if (hidden && windowControls.parentElement !== topbar) topbar.prepend(windowControls)
    else if (!hidden && windowControls.parentElement !== sidebar) hideBtn.after(windowControls)
  }

  function setHidden(hidden, { focus = false } = {}) {
    document.body.classList.toggle('sidebar-hidden', hidden)
    try { localStorage.setItem(STORE_KEY, hidden ? '1' : '0') } catch { /* fine */ }
    placeWindowControls()
    render()
    if (focus) (hidden ? showBtn : hideBtn).focus()
  }

  function toggle() {
    if (narrow.matches) setDrawer(!document.body.classList.contains('nav-open'))
    else setHidden(!document.body.classList.contains('sidebar-hidden'), { focus: true })
  }

  showBtn.addEventListener('click', () => {
    if (narrow.matches) setDrawer(!document.body.classList.contains('nav-open'))
    else setHidden(false, { focus: true })
  })
  hideBtn.addEventListener('click', () => {
    if (narrow.matches) setDrawer(false)
    else setHidden(true, { focus: true })
  })
  backdrop.addEventListener('click', () => setDrawer(false))
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('nav-open')) setDrawer(false)
    if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key === '\\') {
      event.preventDefault()
      toggle()
    }
  })

  // Picking a view, a conversation or New Chat closes the drawer — but not the
  // "⋯" menu on a conversation, which opens its own menu.
  sidebar.addEventListener('click', event => {
    if (!narrow.matches) return
    const target = event.target.closest('button')
    if (!target || target === hideBtn || target.closest('.recent-more') || target.classList.contains('show-more')) return
    setDrawer(false)
  })

  narrow.addEventListener('change', () => {
    document.body.classList.remove('nav-open')
    placeWindowControls()
    render()
  })

  document.body.classList.toggle('sidebar-hidden', remembered())
  placeWindowControls()
  render()
})()

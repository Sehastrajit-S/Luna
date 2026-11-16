/**
 * Mobile drawer. On narrow screens (see the Mobile section of styles.css) the
 * sidebar slides in from the left; this adds the menu button that opens it and
 * closes it again after you pick something. Does nothing visible on wide
 * screens: the button and backdrop are hidden there.
 */
'use strict'

;(function () {
  const sidebar = document.querySelector('.sidebar')
  const topbar = document.querySelector('.topbar')
  if (!sidebar || !topbar) return

  const narrow = window.matchMedia('(max-width: 760px)')

  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'mobile-nav-btn'
  button.setAttribute('aria-label', 'Open menu')
  button.setAttribute('aria-expanded', 'false')
  button.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  topbar.prepend(button)

  const backdrop = document.createElement('div')
  backdrop.className = 'mobile-nav-backdrop'
  backdrop.setAttribute('aria-hidden', 'true')
  document.body.append(backdrop)

  function setOpen(open) {
    document.body.classList.toggle('nav-open', open)
    button.setAttribute('aria-expanded', String(open))
    button.setAttribute('aria-label', open ? 'Close menu' : 'Open menu')
  }

  button.addEventListener('click', () => setOpen(!document.body.classList.contains('nav-open')))
  backdrop.addEventListener('click', () => setOpen(false))
  document.addEventListener('keydown', event => { if (event.key === 'Escape') setOpen(false) })

  // Picking a view, a conversation or New Chat closes the drawer — but not the
  // "⋯" menu on a conversation, which opens its own menu.
  sidebar.addEventListener('click', event => {
    if (!narrow.matches) return
    const target = event.target.closest('button')
    if (!target || target.closest('.recent-more') || target.classList.contains('show-more')) return
    setOpen(false)
  })

  narrow.addEventListener('change', event => { if (!event.matches) setOpen(false) })
})()

/**
 * Budget app (Capabilities → Apps → Budget): monthly overview, categories
 * with limits, expenses and income, a 6-month trend, receipt scanning
 * (on-device OCR on the Luna server), CSV export and "Ask Luna".
 * Data lives in Luna's database via /api/budget.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const $ = id => document.getElementById(id)
  const root = $('view-budget')
  if (!root) return

  const money = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' })
  const fmt = n => money.format(n || 0)
  const today = () => new Date().toLocaleDateString('en-CA')            // YYYY-MM-DD, local time
  const thisMonth = () => today().slice(0, 7)

  let month = thisMonth()
  let data = null
  let requestId = 0
  let sheet = null          // { type: 'txn'|'category', item }

  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }

  function shiftMonth(m, delta) {
    const [y, mo] = m.split('-').map(Number)
    const d = new Date(y, mo - 1 + delta, 1)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  }
  const monthName = (m, opts = { month: 'long', year: 'numeric' }) => {
    const [y, mo] = m.split('-').map(Number)
    return new Date(y, mo - 1, 1).toLocaleDateString(undefined, opts)
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}/api/budget${path}`, {
      ...options,
      headers: options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : undefined,
    })
    if (response.status === 204) return null
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = body.detail
      const message = typeof detail === 'object' && detail?.message ? detail.message
        : Array.isArray(detail) ? 'Check the amount and fields, then try again.'
        : `Something went wrong (${response.status}).`
      throw new Error(message)
    }
    return body
  }

  function status(text, isError = false) {
    const node = $('bud-status')
    node.hidden = !text
    node.textContent = text || ''
    node.classList.toggle('is-error', isError)
  }

  // ── Loading ────────────────────────────────────────────────────────────
  async function load() {
    const id = ++requestId
    $('bud-month-label').textContent = monthName(month)
    $('bud-next').disabled = month >= thisMonth()
    try {
      const result = await api(`/summary?month=${month}`)
      if (id !== requestId) return
      data = result
      render()
    } catch (error) {
      if (id !== requestId) return
      $('bud-hero').innerHTML = ''
      $('bud-hero').append(el('p', 'bud-empty', `Couldn’t load your budget. ${error.message}`))
    }
  }

  function render() {
    renderHero()
    renderCategories()
    renderTrend()
    renderTransactions()
  }

  // ── Overview ───────────────────────────────────────────────────────────
  function renderHero() {
    const hero = $('bud-hero')
    hero.innerHTML = ''
    const d = data
    const main = el('div', 'bud-hero-main')
    if (d.budget > 0) {
      const over = d.left < 0
      main.append(
        el('p', 'bud-hero-label', over ? 'Over budget' : 'Left to spend'),
        el('p', `bud-hero-amount${over ? ' is-over' : ''}`, fmt(Math.abs(d.left))),
        el('p', 'bud-hero-sub', `${fmt(d.spent)} spent of ${fmt(d.budget)}`),
      )
      const bar = el('div', 'bud-bar bud-hero-bar')
      const fill = el('span', `bud-bar-fill${over ? ' is-over' : ''}`)
      fill.style.width = `${Math.min(100, (d.spent / d.budget) * 100)}%`
      bar.append(fill)
      if (d.days_elapsed && d.days_elapsed < d.days_in_month) {
        const pace = el('i', 'bud-bar-pace')
        pace.style.left = `${(d.days_elapsed / d.days_in_month) * 100}%`
        pace.title = 'Today'
        bar.append(pace)
      }
      main.append(bar)
    } else {
      main.append(
        el('p', 'bud-hero-label', 'Spent'),
        el('p', 'bud-hero-amount', fmt(d.spent)),
        el('p', 'bud-hero-sub', 'Set a monthly limit on a category to see what’s left.'),
      )
    }
    const stats = el('div', 'bud-stats')
    const stat = (label, value, cls = '') => {
      const s = el('div', `bud-stat ${cls}`)
      s.append(el('span', 'bud-stat-label', label), el('strong', '', value))
      stats.append(s)
    }
    stat('Income', fmt(d.income))
    stat(d.saved < 0 ? 'Overspent' : 'Saved', fmt(Math.abs(d.saved)), d.saved < 0 ? 'is-over' : '')
    stat('Per day', fmt(d.daily_average))
    if (month === thisMonth()) stat('On pace for', fmt(d.projected), d.budget > 0 && d.projected > d.budget ? 'is-over' : '')
    hero.append(main, stats)
  }

  // ── Categories ─────────────────────────────────────────────────────────
  function renderCategories() {
    const list = $('bud-cats')
    list.innerHTML = ''
    const cats = [...data.categories].sort((a, b) => b.spent - a.spent || (b.limit > 0) - (a.limit > 0))
    for (const c of cats) {
      const li = el('li')
      const row = el('button', 'bud-cat')
      row.type = 'button'
      if (c.id == null) row.disabled = true
      const over = c.limit > 0 && c.spent > c.limit
      const head = el('div', 'bud-cat-head')
      head.append(
        el('span', 'bud-icon', c.icon || c.name[0]),
        el('span', 'bud-cat-name', c.name),
        el('span', `bud-cat-amount${over ? ' is-over' : ''}`,
          c.limit > 0 ? `${fmt(c.spent)} / ${fmt(c.limit)}` : c.spent ? fmt(c.spent) : 'Set limit'),
      )
      row.append(head)
      if (c.limit > 0) {
        const bar = el('div', 'bud-bar')
        const fill = el('span', `bud-bar-fill${over ? ' is-over' : ''}`)
        fill.style.width = `${Math.min(100, (c.spent / c.limit) * 100)}%`
        bar.append(fill)
        row.append(bar)
      }
      row.addEventListener('click', () => openCategory(c))
      li.append(row)
      list.append(li)
    }
  }

  // ── Trend ──────────────────────────────────────────────────────────────
  function renderTrend() {
    const box = $('bud-trend')
    box.innerHTML = ''
    const max = Math.max(1, ...data.trend.flatMap(t => [t.spent, t.income]))
    for (const t of data.trend) {
      const col = el('button', `bud-trend-col${t.month === month ? ' is-current' : ''}`)
      col.type = 'button'
      col.title = `${monthName(t.month)}: spent ${fmt(t.spent)}, income ${fmt(t.income)}`
      col.setAttribute('aria-label', col.title)
      const bars = el('div', 'bud-trend-bars')
      for (const [kind, value] of [['spent', t.spent], ['income', t.income]]) {
        const b = el('span', `bud-trend-bar is-${kind}`)
        b.style.height = `${(value / max) * 100}%`
        bars.append(b)
      }
      col.append(bars, el('span', 'bud-trend-label', monthName(t.month, { month: 'short' })))
      col.addEventListener('click', () => { month = t.month; load() })
      box.append(col)
    }
  }

  // ── Transactions ───────────────────────────────────────────────────────
  function dayLabel(iso) {
    const d = new Date(`${iso}T00:00:00`)
    const t = today()
    const y = new Date(Date.now() - 864e5).toLocaleDateString('en-CA')
    if (iso === t) return 'Today'
    if (iso === y) return 'Yesterday'
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  }

  function renderTransactions() {
    const box = $('bud-txns')
    box.innerHTML = ''
    const names = Object.fromEntries(data.categories.map(c => [c.id, c]))
    const q = $('bud-search').value.trim().toLowerCase()
    const txns = data.transactions.filter(t => !q || [
      t.description, names[t.category_id]?.name, t.kind === 'income' ? 'income' : '', String(t.amount),
    ].join(' ').toLowerCase().includes(q))

    if (!txns.length) {
      box.append(el('p', 'bud-empty', q ? 'No entries match.'
        : `Nothing logged for ${monthName(month)} yet. Add an expense or scan a receipt.`))
      return
    }
    let group = null
    for (const t of txns) {
      if (!group || group.date !== t.date) {
        group = { date: t.date, total: 0, list: el('ul', 'bud-txn-list'), head: el('div', 'bud-day') }
        group.head.append(el('span', '', dayLabel(t.date)), el('span', 'bud-day-total'))
        box.append(group.head, group.list)
      }
      if (t.kind === 'expense') group.total += t.amount
      group.head.querySelector('.bud-day-total').textContent = group.total ? `−${fmt(group.total)}` : ''

      const cat = names[t.category_id]
      const income = t.kind === 'income'
      const li = el('li')
      const row = el('button', 'bud-txn')
      row.type = 'button'
      const text = el('span', 'bud-txn-text')
      text.append(
        el('span', 'bud-txn-title', t.description || (income ? 'Income' : cat?.name || 'Expense')),
        el('span', 'bud-txn-meta', [income ? 'Income' : cat?.name || 'Uncategorized', t.source === 'receipt' ? 'Receipt' : '']
          .filter(Boolean).join(' · ')),
      )
      row.append(
        el('span', `bud-icon${income ? ' is-income' : ''}`, income ? '↓' : cat?.icon || '•'),
        text,
        el('span', `bud-txn-amount${income ? ' is-income' : ''}`, `${income ? '+' : '−'}${fmt(t.amount)}`),
      )
      row.addEventListener('click', () => openTransaction(t))
      li.append(row)
      group.list.append(li)
    }
  }

  // ── Sheet (add/edit forms) ─────────────────────────────────────────────
  function field(label, input) {
    const wrap = el('label', 'bud-field')
    wrap.append(el('span', 'bud-field-label', label), input)
    return wrap
  }
  function input(name, value = '', attrs = {}) {
    const node = el('input', 'bud-input')
    node.name = name
    node.value = value ?? ''
    Object.assign(node, attrs)
    return node
  }

  function showSheet(title, fields, { canDelete = false } = {}) {
    $('bud-form-title').textContent = title
    const box = $('bud-fields')
    box.innerHTML = ''
    box.append(...fields)
    $('bud-form-delete').hidden = !canDelete
    $('bud-form-error').hidden = true
    $('bud-form-save').disabled = false
    $('bud-sheet').hidden = false
    // Focus the first empty field (the amount, when adding).
    const first = [...box.querySelectorAll('input')].find(i => !i.value && i.type !== 'hidden') || box.querySelector('input')
    setTimeout(() => first?.focus(), 50)
  }
  function closeSheet() {
    $('bud-sheet').hidden = true
    sheet = null
  }
  function formError(message) {
    const node = $('bud-form-error')
    node.textContent = message
    node.hidden = !message
  }

  function openTransaction(item, { kind = 'expense', draft = null } = {}) {
    const existing = item && item.id != null
    const k = existing ? item.kind : kind
    sheet = { type: 'txn', item: existing ? item : null, kind: k, source: draft ? 'receipt' : 'manual' }

    const seg = el('div', 'bud-seg')
    seg.setAttribute('role', 'radiogroup')
    for (const [value, label] of [['expense', 'Expense'], ['income', 'Income']]) {
      const b = el('button', `bud-seg-btn${value === k ? ' is-active' : ''}`, label)
      b.type = 'button'
      b.setAttribute('role', 'radio')
      b.setAttribute('aria-checked', String(value === k))
      b.addEventListener('click', () => {
        sheet.kind = value
        seg.querySelectorAll('.bud-seg-btn').forEach(x => {
          const on = x === b
          x.classList.toggle('is-active', on)
          x.setAttribute('aria-checked', String(on))
        })
        catField.hidden = value === 'income'
        $('bud-form-title').textContent = `${existing ? 'Edit' : 'Add'} ${value}`
      })
      seg.append(b)
    }

    const amount = input('amount', existing ? item.amount : draft?.amount ?? '', {
      type: 'text', inputMode: 'decimal', placeholder: '0.00', autocomplete: 'off',
    })
    amount.classList.add('bud-input-amount')
    const desc = input('description', existing ? item.description : draft?.merchant || '', {
      type: 'text', placeholder: k === 'income' ? 'Paycheck, refund…' : 'Coffee, groceries…', maxLength: 200,
    })
    const select = el('select', 'bud-input')
    select.name = 'category_id'
    const pick = existing ? item.category_id
      : data.categories.find(c => draft?.category && c.name === draft.category)?.id
    select.append(new Option('Uncategorized', ''))
    for (const c of data.categories.filter(c => c.id != null)) {
      select.append(new Option(`${c.icon ? c.icon + ' ' : ''}${c.name}`, c.id, false, c.id === pick))
    }
    const date = input('date', existing ? item.date : draft?.date || (month === thisMonth() ? today() : `${month}-01`), {
      type: 'date', max: today(),
    })
    const catField = field('Category', select)
    catField.hidden = k === 'income'

    const fields = [seg, field('Amount', amount), field('Description', desc), catField, field('Date', date)]
    if (draft) fields.unshift(el('p', 'bud-draft-note', 'Read from your receipt. Check the amount before saving.'))
    showSheet(`${existing ? 'Edit' : 'Add'} ${k}`, fields, { canDelete: existing })
  }

  function openCategory(c) {
    const existing = c && c.id != null
    sheet = { type: 'category', item: existing ? c : null }
    const icon = input('icon', existing ? c.icon : '', { type: 'text', maxLength: 8, placeholder: '🛒' })
    icon.classList.add('bud-input-icon')
    const name = input('name', existing ? c.name : '', { type: 'text', maxLength: 40, placeholder: 'e.g. Pets' })
    const limit = input('limit', existing && c.limit ? c.limit : '', {
      type: 'text', inputMode: 'decimal', placeholder: 'No limit', autocomplete: 'off',
    })
    const row = el('div', 'bud-field-row')
    row.append(field('Icon', icon), field('Name', name))
    const hint = el('p', 'bud-draft-note', existing ? 'Deleting a category keeps its expenses as Uncategorized.' : '')
    showSheet(existing ? 'Edit category' : 'New category', [row, field('Monthly limit', limit), ...(existing ? [hint] : [])], { canDelete: existing })
  }

  function readAmount(value, { optional = false } = {}) {
    const clean = String(value).replace(/[$,\s]/g, '')
    if (!clean && optional) return 0
    const n = Number(clean)
    if (!Number.isFinite(n) || (optional ? n < 0 : n <= 0)) return null
    return Math.round(n * 100) / 100
  }

  async function save(event) {
    event.preventDefault()
    if (!sheet) return
    const form = $('bud-form')
    const value = name => form.querySelector(`[name="${name}"]`)?.value ?? ''
    const saveBtn = $('bud-form-save')
    formError('')
    try {
      if (sheet.type === 'txn') {
        const amount = readAmount(value('amount'))
        if (amount == null) return formError('Enter an amount above zero, like 12.50.')
        const body = {
          amount, kind: sheet.kind, description: value('description').trim(), date: value('date') || null,
          category_id: sheet.kind === 'income' || !value('category_id') ? null : Number(value('category_id')),
        }
        saveBtn.disabled = true
        if (sheet.item) await api(`/transactions/${sheet.item.id}`, { method: 'PATCH', body: JSON.stringify(body) })
        else await api('/transactions', { method: 'POST', body: JSON.stringify({ ...body, source: sheet.source }) })
        // Saving into another month: jump there so the entry is visible.
        if (body.date && body.date.slice(0, 7) !== month) month = body.date.slice(0, 7)
      } else {
        const limit = readAmount(value('limit'), { optional: true })
        if (limit == null) return formError('The limit must be a number, like 300.')
        if (!value('name').trim()) return formError('Give the category a name.')
        const body = { name: value('name').trim(), icon: value('icon').trim(), limit }
        saveBtn.disabled = true
        if (sheet.item) await api(`/categories/${sheet.item.id}`, { method: 'PATCH', body: JSON.stringify(body) })
        else await api('/categories', { method: 'POST', body: JSON.stringify(body) })
      }
      closeSheet()
      await load()
    } catch (error) {
      formError(error.message)
    } finally {
      saveBtn.disabled = false
    }
  }

  async function remove() {
    if (!sheet?.item) return
    const what = sheet.type === 'txn' ? 'this entry' : `the ${sheet.item.name} category`
    if (!window.confirm(`Delete ${what}?`)) return
    try {
      await api(sheet.type === 'txn' ? `/transactions/${sheet.item.id}` : `/categories/${sheet.item.id}`, { method: 'DELETE' })
      closeSheet()
      await load()
    } catch (error) {
      formError(error.message)
    }
  }

  // ── Receipt, export, ask ───────────────────────────────────────────────
  async function scanReceipt(file) {
    if (!file) return
    status('Reading your receipt…')
    try {
      const form = new FormData()
      form.append('image', file, file.name || 'receipt.jpg')
      const draft = await api('/receipt', { method: 'POST', body: form })
      status('')
      if (!data) await load()
      openTransaction(null, { kind: 'expense', draft })
      if (!draft.amount) formError('Couldn’t find the total. Type it in.')
    } catch (error) {
      status(error.message, true)
    }
  }

  async function exportCsv() {
    try {
      const response = await fetch(`${API}/api/budget/export.csv?month=${month}`)
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const url = URL.createObjectURL(await response.blob())
      const a = Object.assign(document.createElement('a'), { href: url, download: `luna-budget-${month}.csv` })
      document.body.append(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (error) {
      status(error.message, true)
    }
  }

  function askLuna() {
    if (!data) return
    const d = data
    const lines = [
      `Here's my budget for ${monthName(month)}. Look at it and give me a few practical suggestions.`,
      '',
      `Income: ${fmt(d.income)} · Spent: ${fmt(d.spent)}${d.budget ? ` · Budget: ${fmt(d.budget)}` : ''}`,
      month === thisMonth() ? `Day ${d.days_elapsed} of ${d.days_in_month}; on pace to spend ${fmt(d.projected)}.` : '',
      '',
      'By category:',
      ...d.categories.filter(c => c.spent || c.limit)
        .map(c => `- ${c.name}: ${fmt(c.spent)}${c.limit ? ` of ${fmt(c.limit)}` : ' (no limit)'}`),
      '',
      'Last 6 months (spent / income):',
      ...d.trend.map(t => `- ${monthName(t.month, { month: 'short', year: 'numeric' })}: ${fmt(t.spent)} / ${fmt(t.income)}`),
    ].filter((line, i, all) => line !== '' || all[i - 1] !== '')
    window.lunaAskInNewChat?.(lines.join('\n'))
  }

  // ── Wiring ─────────────────────────────────────────────────────────────
  $('bud-prev').addEventListener('click', () => { month = shiftMonth(month, -1); load() })
  $('bud-next').addEventListener('click', () => { if (month < thisMonth()) { month = shiftMonth(month, 1); load() } })
  $('bud-add-expense').addEventListener('click', () => data && openTransaction(null, { kind: 'expense' }))
  $('bud-add-income').addEventListener('click', () => data && openTransaction(null, { kind: 'income' }))
  $('bud-add-category').addEventListener('click', () => data && openCategory(null))
  $('bud-receipt').addEventListener('change', event => {
    const file = event.target.files?.[0]
    event.target.value = ''            // same photo twice still fires change
    scanReceipt(file)
  })
  $('bud-export').addEventListener('click', exportCsv)
  $('bud-ask').addEventListener('click', askLuna)
  $('bud-search').addEventListener('input', () => data && renderTransactions())
  $('bud-form').addEventListener('submit', save)
  $('bud-form-delete').addEventListener('click', remove)
  $('bud-form-close').addEventListener('click', closeSheet)
  $('bud-sheet').addEventListener('click', event => { if (event.target === $('bud-sheet')) closeSheet() })
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !$('bud-sheet').hidden) closeSheet()
  })

  window.loadBudgetView = () => {
    status('')
    load()
  }
})()

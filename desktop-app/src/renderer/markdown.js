/**
 * Minimal, safe Markdown → HTML for Luna's chat bubbles.
 *
 * Everything is HTML-escaped before any markup is added, so model output can
 * never inject tags or attributes. Supports what Luna actually emits:
 * headings, bullet/numbered lists, bold/italic, inline + fenced code, links,
 * bare URLs, horizontal rules, and a numbered "References:" section.
 */
'use strict'

;(function () {
  const escapeHtml = text => text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

  const SAFE_URL = /^https?:\/\/[^\s<>"']+$/i

  function link(url, label) {
    // Trailing punctuation usually belongs to the sentence, not the URL.
    const trail = url.match(/[.,;:!?)]+$/)
    let clean = url
    let after = ''
    if (trail && !(trail[0] === ')' && url.includes('('))) {
      clean = url.slice(0, -trail[0].length)
      after = trail[0]
    }
    if (!SAFE_URL.test(clean.replace(/&amp;/g, '&'))) return (label || url)
    return `<a class="md-link" href="${clean}" title="${clean}">${label || clean}</a>${after}`
  }

  function renderInline(raw) {
    const codeSpans = []
    let text = raw.replace(/`([^`\n]+)`/g, (_m, code) => {
      codeSpans.push(`<code>${escapeHtml(code)}</code>`)
      return `\u0000${codeSpans.length - 1}\u0000`
    })
    text = escapeHtml(text)

    const links = []
    const stash = html => { links.push(html); return `\u0001${links.length - 1}\u0001` }
    text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, label, url) => stash(link(url, label)))
    // Stop bare URLs at escaped quotes/brackets so they can't swallow text.
    text = text.replace(/https?:\/\/(?:(?!&quot;|&#39;|&lt;|&gt;)[^\s<])+/g, url => stash(link(url)))

    text = text
      .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
      .replace(/__(?=\S)([\s\S]*?\S)__/g, '<strong>$1</strong>')
      .replace(/(^|[^*\w])\*(?=\S)([^*\n]*?\S)\*(?!\*)/g, '$1<em>$2</em>')
      .replace(/(^|[^_\w])_(?=\S)([^_\n]*?\S)_(?![_\w])/g, '$1<em>$2</em>')

    return text
      .replace(/\u0001(\d+)\u0001/g, (_m, i) => links[Number(i)])
      .replace(/\u0000(\d+)\u0000/g, (_m, i) => codeSpans[Number(i)])
  }

  function renderMarkdown(source) {
    const lines = String(source || '')
      .replace(/\r\n?/g, '\n')
      // "References: [1] a [2] b" on one line → heading + one entry per line.
      .replace(/^(\s*\**references?\**:?\**)[ \t]+(?=\[\d+\])(.*)$/gim,
        (_m, head, rest) => `${head}\n${rest.split(/\s+(?=\[\d+\]\s)/).join('\n')}`)
      .split('\n')
    const out = []
    let paragraph = []
    let list = null // { type: 'ul' | 'ol', items: [] }
    let inReferences = false
    const refs = [] // raw "Title - url" lines from the References section

    const flushParagraph = () => {
      if (paragraph.length) out.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`)
      paragraph = []
    }
    const flushList = () => {
      if (list) out.push(`<${list.type}>${list.items.map(item => `<li>${renderInline(item)}</li>`).join('')}</${list.type}>`)
      list = null
    }
    const flush = () => { flushParagraph(); flushList() }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]

      const fence = line.match(/^\s*```\s*([\w+-]*)\s*$/)
      if (fence) {
        flush()
        const code = []
        i += 1
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) code.push(lines[i++])
        out.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`)
        continue
      }

      if (!line.trim()) { flush(); continue }

      const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/)
      if (heading) {
        flush()
        const level = Math.min(heading[1].length + 2, 6) // keep headings bubble-sized
        out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
        continue
      }

      if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { flush(); out.push('<hr>'); continue }

      const refsHeading = line.match(/^\s*\**references?:?\**\s*:?\s*$/i)
      if (refsHeading) {
        flush()
        inReferences = true
        continue
      }

      const bullet = line.match(/^\s*[-*•]\s+(.*)$/)
      const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/)
      const ref = inReferences && line.match(/^\s*\[(\d+)\]\s+(.*)$/)
      if (ref) {
        flush()
        refs.push(ref[2])
        continue
      }
      if (bullet || numbered) {
        flushParagraph()
        const type = bullet ? 'ul' : 'ol'
        if (!list || list.type !== type) { flushList(); list = { type, items: [] } }
        list.items.push((bullet || numbered)[1])
        continue
      }

      // Indented continuation of the previous list item.
      if (list && /^\s{2,}\S/.test(line)) {
        list.items[list.items.length - 1] += ' ' + line.trim()
        continue
      }

      flushList()
      paragraph.push(line.trim())
    }
    flush()
    if (refs.length) out.push(renderReferences(refs))
    return out.join('')
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' }
  }

  // Sources collapse into a pill ("6 sources · a.com, b.org…") that expands on
  // click. <details> keeps its open state natively and needs no extra JS.
  function renderReferences(entries) {
    const items = entries.map((entry, i) => {
      const urlMatch = entry.match(/https?:\/\/[^\s<>"']+/)
      const url = urlMatch ? urlMatch[0].replace(/[.,;:!?)]+$/, '') : ''
      let title = (urlMatch ? entry.slice(0, urlMatch.index) : entry).replace(/\s*[-–—|:]\s*$/, '').trim()
      const host = url ? hostOf(url) : ''
      if (!title) title = host || entry
      const safeUrl = url && SAFE_URL.test(url) ? escapeHtml(url) : ''
      const body = `<span class="md-ref-num">${i + 1}</span><span class="md-ref-text"><span class="md-ref-title">${escapeHtml(title)}</span>${host ? `<span class="md-ref-host">${escapeHtml(host)}</span>` : ''}</span>`
      return safeUrl
        ? `<li><a class="md-link md-ref" href="${safeUrl}" title="${safeUrl}">${body}</a></li>`
        : `<li><span class="md-ref">${body}</span></li>`
    })
    const hosts = [...new Set(entries.map(e => hostOf((e.match(/https?:\/\/[^\s<>"']+/) || [''])[0])).filter(Boolean))]
    const preview = hosts.slice(0, 3).map(h => `<span class="md-refs-chip">${escapeHtml(h)}</span>`).join('')
    const more = hosts.length > 3 ? `<span class="md-refs-more">+${hosts.length - 3}</span>` : ''
    const label = `${entries.length} source${entries.length === 1 ? '' : 's'}`
    return `<details class="md-refs"><summary><span class="md-refs-label">${label}</span>${preview}${more}<span class="md-refs-caret" aria-hidden="true"></span></summary><ol class="md-refs-list">${items.join('')}</ol></details>`
  }

  const SAFE_IMAGE = /^https:\/\/[^\s"'<>]+$/i
  const CURRENCY_SYMBOLS = { USD: '$', EUR: '€', GBP: '£', INR: '₹', JPY: '¥', CAD: 'CA$', AUD: 'A$' }

  function formatPrice(price, currency) {
    const code = String(currency || '').toUpperCase()
    return CURRENCY_SYMBOLS[code] ? `${CURRENCY_SYMBOLS[code]}${price}` : `${price}${code ? ' ' + code : ''}`
  }

  // Result cards (e.g. products): image, exact title, price, site — built by
  // the backend from the item pages themselves. Every field is escaped and
  // only https links/images are used.
  function renderCards(cards) {
    const items = (Array.isArray(cards) ? cards : []).filter(c => c && SAFE_URL.test(String(c.url || ''))).slice(0, 8)
    if (!items.length) return ''
    const html = items.map(c => {
      const image = c.image && SAFE_IMAGE.test(String(c.image))
        ? `<span class="md-card-img"><img src="${escapeHtml(c.image)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`
        : '<span class="md-card-img is-empty"></span>'
      const price = c.price ? `<span class="md-card-price">${escapeHtml(formatPrice(c.price, c.currency))}</span>` : ''
      return `<a class="md-link md-card" href="${escapeHtml(c.url)}" title="${escapeHtml(c.title || '')}">${image}` +
        `<span class="md-card-body"><span class="md-card-title">${escapeHtml(c.title || c.url)}</span>${price}` +
        `<span class="md-card-site">${escapeHtml(c.site || '')}</span></span></a>`
    }).join('')
    return `<div class="md-cards">${html}</div>`
  }

  window.renderMarkdown = renderMarkdown
  window.renderCards = renderCards
})()

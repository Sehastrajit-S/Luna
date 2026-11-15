/**
 * Agent steps: the tools Luna calls while answering, shown live above the
 * reply ("Searching the web", "Adding task"), collapsed into one row when the
 * answer arrives. Risky tools pause for Approve / Deny, answered through
 * /api/chat/confirm/<id>. All model/tool text goes in via textContent.
 */
'use strict'

const STEPS_API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'

const TOOL_LABELS = {
  web_search: 'Searching the web',
  use_skill: 'Running a skill',
  web_fetch: 'Reading a page',
  browser_read: 'Reading a page',
  create_task: 'Adding a task',
  create_event: 'Adding to calendar',
  tool_search: 'Finding tools',
  workspace_read: 'Reading a file',
  workspace_write: 'Writing a file',
  google_workspace: 'Using Google',
  microsoft_workspace: 'Using Microsoft 365',
  launch_app: 'Opening an app',
  close_app: 'Closing an app',
  spotify_play: 'Playing on Spotify',
}

function toolLabel(tool) {
  return TOOL_LABELS[tool] || String(tool || 'tool').replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function toolDetail(tool, args) {
  if (!args || typeof args !== 'object') return ''
  const value = args.query || args.request || args.title || args.url || args.path || args.app || args.skill || ''
  return String(value).slice(0, 80)
}

function el(tag, className, text) {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text != null) node.textContent = text
  return node
}

/** One steps panel per assistant message; created on the first tool call. */
function createAgentSteps(mdElement) {
  const bubble = mdElement?.closest('.bubble')
  let panel = null
  let list = null
  let summary = null
  const rows = new Map()
  let count = 0

  function ensurePanel() {
    if (panel || !bubble) return
    panel = el('details', 'agent-steps')
    panel.open = true
    summary = el('summary', 'agent-steps-summary', 'Working…')
    list = el('div', 'agent-steps-list')
    panel.append(summary, list)
    bubble.insertBefore(panel, mdElement)
  }

  function onToolCall(event) {
    ensurePanel()
    if (!list) return
    count += 1
    const row = el('div', 'agent-step is-running')
    row.append(el('span', 'agent-step-dot'), el('span', 'agent-step-label', toolLabel(event.tool)))
    const detail = toolDetail(event.tool, event.args)
    if (detail) row.append(el('span', 'agent-step-detail', detail))
    list.append(row)
    rows.set(event.call_id, row)
    summary.textContent = `Working… ${count} step${count === 1 ? '' : 's'}`
  }

  function onToolResult(event) {
    const row = rows.get(event.call_id)
    if (!row) return
    row.classList.remove('is-running')
    row.classList.add(event.ok ? 'is-ok' : 'is-error')
    if (event.summary) row.title = event.summary
  }

  function onConfirm(event) {
    ensurePanel()
    if (!list) return
    const card = el('div', 'agent-confirm')
    card.append(el('div', 'agent-confirm-text', event.message || `Allow ${toolLabel(event.tool)}?`))
    const actions = el('div', 'agent-confirm-actions')
    const approve = el('button', 'agent-confirm-btn is-approve', 'Approve')
    const deny = el('button', 'agent-confirm-btn', 'Deny')
    approve.type = deny.type = 'button'
    const answer = async (approved) => {
      approve.disabled = deny.disabled = true
      card.classList.add(approved ? 'is-approved' : 'is-denied')
      try {
        await fetch(`${STEPS_API}/api/chat/confirm/${encodeURIComponent(event.confirm_id)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved }),
        })
      } catch {
        card.classList.add('is-error')
      }
    }
    approve.addEventListener('click', () => answer(true))
    deny.addEventListener('click', () => answer(false))
    actions.append(approve, deny)
    card.append(actions)
    card.dataset.confirmId = event.confirm_id
    list.append(card)
    panel.open = true
  }

  function onConfirmResolved(event) {
    const card = list?.querySelector(`[data-confirm-id="${CSS.escape(event.confirm_id || '')}"]`)
    if (!card) return
    card.querySelectorAll('button').forEach(b => { b.disabled = true })
    card.classList.add(event.approved ? 'is-approved' : 'is-denied')
  }

  function onDone(event) {
    if (!panel) return
    const failed = list.querySelectorAll('.agent-step.is-error').length
    summary.textContent = `Used ${count} tool${count === 1 ? '' : 's'}` + (failed ? ` · ${failed} failed` : '')
    panel.open = false
  }

  function handle(event) {
    switch (event.type) {
      case 'tool_call': onToolCall(event); return true
      case 'tool_result': onToolResult(event); return true
      case 'confirmation_required': onConfirm(event); return true
      case 'confirmation_resolved': onConfirmResolved(event); return true
      case 'agent_done': onDone(event); return true
      default: return false
    }
  }

  return { handle, get started() { return panel !== null } }
}

window.createAgentSteps = createAgentSteps

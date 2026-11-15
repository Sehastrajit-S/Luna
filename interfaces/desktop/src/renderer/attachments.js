/**
 * Chat attachments: pick / drop / paste files, upload them right away (with
 * progress), show them as chips in the composer, and hand their ids to the
 * next message — the same flow as hosted chat apps. The backend extracts the
 * text (PDF, Word, Excel, CSV, PowerPoint, images, text, code) and keeps the
 * files attached to the conversation for follow-up questions.
 */
'use strict'

const ATTACH_API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
const MAX_FILES_PER_MESSAGE = 10
const MAX_FILE_BYTES = 30 * 1024 * 1024

const attachBtn = document.getElementById('attach-btn')
const attachInput = document.getElementById('attach-input')
const attachmentTray = document.getElementById('attachment-tray')
const dropOverlay = document.getElementById('drop-overlay')

/** @type {{localId:number, file?:File, status:'uploading'|'ready'|'error', progress:number, data?:object, error?:string, xhr?:XMLHttpRequest, promise?:Promise}[]} */
const pendingAttachments = []
let nextLocalId = 1

const FILE_BADGES = [
  [/\.pdf$/i, 'PDF', 'pdf'],
  [/\.docx$/i, 'DOC', 'doc'],
  [/\.pptx$/i, 'PPT', 'ppt'],
  [/\.(xlsx|xlsm)$/i, 'XLS', 'xls'],
  [/\.(csv|tsv)$/i, 'CSV', 'xls'],
  [/\.(png|jpe?g|webp|gif|bmp)$/i, 'IMG', 'img'],
  [/\.(md|markdown|txt|rtf|log)$/i, 'TXT', 'txt'],
  [/\.(html?|json|jsonl|xml|ya?ml|toml)$/i, '</>', 'code'],
]

function fileBadge(name) {
  for (const [re, label, tone] of FILE_BADGES) if (re.test(name)) return { label, tone }
  const ext = (name.match(/\.([a-z0-9]{1,4})$/i) || [])[1]
  return { label: ext ? ext.toUpperCase() : 'FILE', tone: 'code' }
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * One file chip. `att` is either a server AttachmentOut or a pending upload.
 * sent=true renders the compact chip used inside sent message bubbles.
 */
function buildFileChip(att, { sent = false, pending = null } = {}) {
  const name = att.filename || att.file?.name || 'file'
  const badge = fileBadge(name)
  const chip = document.createElement(sent && att.id ? 'button' : 'div')
  chip.className = `file-chip file-chip-${badge.tone}${sent ? ' is-sent' : ''}`
  if (sent && att.id) {
    chip.type = 'button'
    chip.title = `Open ${name}`
    chip.addEventListener('click', () => window.electronAPI?.openUrl?.(`${ATTACH_API}/api/files/${att.id}/raw`))
  }

  const icon = document.createElement('span')
  icon.className = 'file-chip-icon'
  icon.textContent = badge.label
  const text = document.createElement('span')
  text.className = 'file-chip-text'
  const title = document.createElement('span')
  title.className = 'file-chip-name'
  title.textContent = name
  const meta = document.createElement('span')
  meta.className = 'file-chip-meta'
  text.append(title, meta)
  chip.append(icon, text)

  const status = pending?.status || (att.status === 'error' ? 'error' : 'ready')
  if (status === 'uploading') {
    chip.classList.add('is-uploading')
    meta.textContent = pending.progress < 100 ? `Uploading… ${pending.progress}%` : 'Reading…'
    chip.style.setProperty('--progress', `${pending.progress}%`)
  } else if (status === 'error') {
    chip.classList.add('is-error')
    meta.textContent = pending?.error || att.error || "Couldn't read this file"
    chip.title = meta.textContent
  } else {
    meta.textContent = [att.summary_line, formatBytes(att.size_bytes)].filter(Boolean).join(' · ')
    if (att.error) chip.title = att.error   // readable, with a warning (e.g. partly scanned)
  }

  if (pending) {
    const remove = document.createElement('button')
    remove.type = 'button'
    remove.className = 'file-chip-remove'
    remove.setAttribute('aria-label', `Remove ${name}`)
    remove.textContent = '×'
    remove.addEventListener('click', () => removePendingAttachment(pending.localId))
    chip.append(remove)
  }
  return chip
}

function renderAttachmentTray() {
  if (!attachmentTray) return
  attachmentTray.replaceChildren(...pendingAttachments.map(p =>
    buildFileChip(p.data || { filename: p.file?.name }, { pending: p })))
  attachmentTray.hidden = pendingAttachments.length === 0
}

function uploadFile(entry) {
  entry.promise = new Promise(resolve => {
    const form = new FormData()
    form.append('file', entry.file)
    if (typeof activeConversationId === 'number') form.append('conversation_id', String(activeConversationId))
    const xhr = new XMLHttpRequest()
    entry.xhr = xhr
    xhr.open('POST', `${ATTACH_API}/api/files`)
    xhr.upload.onprogress = e => {
      if (!e.lengthComputable) return
      entry.progress = Math.min(100, Math.round((e.loaded / e.total) * 100))
      renderAttachmentTray()
    }
    xhr.onload = () => {
      let body = null
      try { body = JSON.parse(xhr.responseText) } catch { /* non-JSON error page */ }
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        entry.data = body
        entry.status = body.status === 'error' ? 'error' : 'ready'
        if (entry.status === 'error') entry.error = body.error || "Couldn't read this file"
      } else {
        entry.status = 'error'
        entry.error = body?.detail || `Upload failed (${xhr.status})`
      }
      renderAttachmentTray()
      resolve()
    }
    xhr.onerror = () => {
      entry.status = 'error'
      entry.error = "Couldn't reach Luna's backend"
      renderAttachmentTray()
      resolve()
    }
    xhr.onabort = () => resolve()
    xhr.send(form)
  })
}

function addFiles(fileList) {
  const files = Array.from(fileList || [])
  for (const file of files) {
    if (pendingAttachments.length >= MAX_FILES_PER_MESSAGE) {
      pendingAttachments.push({ localId: nextLocalId++, file, status: 'error', progress: 0,
        error: `Up to ${MAX_FILES_PER_MESSAGE} files per message` })
      continue
    }
    const entry = { localId: nextLocalId++, file, status: 'uploading', progress: 0 }
    pendingAttachments.push(entry)
    if (file.size > MAX_FILE_BYTES) {
      entry.status = 'error'
      entry.error = 'Files can be up to 30 MB'
    } else if (file.size === 0) {
      entry.status = 'error'
      entry.error = 'This file is empty'
    } else {
      uploadFile(entry)
    }
  }
  renderAttachmentTray()
  composerInput?.focus()
}

function removePendingAttachment(localId) {
  const index = pendingAttachments.findIndex(p => p.localId === localId)
  if (index === -1) return
  const [entry] = pendingAttachments.splice(index, 1)
  if (entry.status === 'uploading') entry.xhr?.abort()
  // Uploaded but never sent: tell the backend to drop it.
  if (entry.data?.id) fetch(`${ATTACH_API}/api/files/${entry.data.id}`, { method: 'DELETE' }).catch(() => {})
  renderAttachmentTray()
}

/** Called once a message has taken the ready files; errored ones are discarded. */
function clearPendingAttachments() {
  pendingAttachments.splice(0, pendingAttachments.length)
  renderAttachmentTray()
}

attachBtn?.addEventListener('click', () => attachInput?.click())
attachInput?.addEventListener('change', () => {
  addFiles(attachInput.files)
  attachInput.value = ''   // allow picking the same file again
})

// Paste files (e.g. a screenshot) straight into the message box.
document.querySelector('.composer-input')?.addEventListener('paste', event => {
  const files = event.clipboardData?.files
  if (files && files.length) {
    event.preventDefault()
    addFiles(files)
  }
})

// Drag and drop anywhere in the window.
let dragDepth = 0
const hasFiles = event => Array.from(event.dataTransfer?.types || []).includes('Files')
window.addEventListener('dragenter', event => {
  if (!hasFiles(event)) return
  event.preventDefault()
  dragDepth += 1
  if (dropOverlay) dropOverlay.hidden = false
})
window.addEventListener('dragover', event => {
  if (hasFiles(event)) event.preventDefault()
})
window.addEventListener('dragleave', event => {
  if (!hasFiles(event)) return
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0 && dropOverlay) dropOverlay.hidden = true
})
window.addEventListener('drop', event => {
  if (!hasFiles(event)) return
  event.preventDefault()   // never let Electron navigate to the dropped file
  dragDepth = 0
  if (dropOverlay) dropOverlay.hidden = true
  addFiles(event.dataTransfer.files)
})

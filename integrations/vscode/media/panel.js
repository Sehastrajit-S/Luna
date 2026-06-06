// @ts-check
/// <reference lib="dom" />
(function () {
  'use strict';

  // @ts-ignore
  const vscode = acquireVsCodeApi();

  const LOGO = (typeof window !== 'undefined' && /** @type {any} */(window).__LUNA_LOGO__) || '';

  function _emptyState() {
    const logo = LOGO ? `<img src="${LOGO}" class="empty-logo" alt="Luna">` : '';
    return `<div class="empty-state">
      ${logo}
      <div class="empty-title">Luna AI</div>
      <div class="empty-sub">Ask anything &middot; Explain &middot; Fix bugs &middot; Search the web<br>Use <kbd>@</kbd> to reference files &middot; Right-click code for quick actions.</div>
    </div>`;
  }

  /** @type {HTMLDivElement} */  const messages     = /** @type {any} */ (document.getElementById('messages'));
  /** @type {HTMLTextAreaElement} */ const input    = /** @type {any} */ (document.getElementById('input'));
  /** @type {HTMLButtonElement} */ const sendBtn    = /** @type {any} */ (document.getElementById('send-btn'));
  /** @type {HTMLButtonElement} */ const newBtn     = /** @type {any} */ (document.getElementById('new-btn'));
  /** @type {HTMLDivElement} */  const workspaceBar = /** @type {any} */ (document.getElementById('workspace-bar'));
  /** @type {HTMLDivElement} */  const planPanel    = /** @type {any} */ (document.getElementById('plan-panel'));
  /** @type {HTMLDivElement} */  const mentionMenu  = /** @type {any} */ (document.getElementById('mention-menu'));

  let streaming = false;
  /** @type {HTMLElement|null} */ let activeBubble = null;
  let activeText = '';
  /** @type {HTMLElement|null} */ let activeToolCard = null;
  /** @type {string[]} */ let workspaceFiles = [];
  /** @type {string[]} */ let planSteps = [];

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function esc(/** @type {string} */ s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function scrollBottom() { messages.scrollTop = messages.scrollHeight; }

  function removeEmptyState() {
    const e = messages.querySelector('.empty-state');
    if (e) e.remove();
  }

  // ── Markdown renderer ─────────────────────────────────────────────────────────

  function md(/** @type {string} */ raw) {
    /** @type {{lang:string, code:string}[]} */ const blocks = [];
    let s = raw.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      blocks.push({ lang: lang || 'text', code: code.trimEnd() });
      return `\x00BLOCK${blocks.length - 1}\x00`;
    });

    s = s.replace(/`([^`\n]+)`/g, (_, c) => `<code>${esc(c)}</code>`);
    s = s.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/_(.+?)_/g, '<em>$1</em>');
    s = s.replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>');
    s = s.replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>');
    s = s.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
    s = s.replace(/^-{3,}$/gm, '<hr>');

    const refIdx = s.search(/^References:\s*$/im);
    let bodyPart = refIdx >= 0 ? s.slice(0, refIdx) : s;
    const refPart = refIdx >= 0 ? s.slice(refIdx) : '';

    bodyPart = bodyPart.replace(/((?:^[ \t]*[-*]\s.+\n?)+)/gm, (block) => {
      const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[ \t]*[-*]\s/, '').trim()}</li>`);
      return `<ul>${items.join('')}</ul>`;
    });
    bodyPart = bodyPart.replace(/((?:^[ \t]*\d+\.\s.+\n?)+)/gm, (block) => {
      const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[ \t]*\d+\.\s/, '').trim()}</li>`);
      return `<ol>${items.join('')}</ol>`;
    });
    bodyPart = bodyPart.replace(/\n{2,}/g, '\n</p><p>\n');
    bodyPart = `<p>${bodyPart}</p>`;
    for (const tag of ['ul', 'ol', 'h1', 'h2', 'h3', 'hr']) {
      bodyPart = bodyPart.replace(new RegExp(`<p>\\s*(<${tag}[\\s>])`, 'g'), '$1');
      bodyPart = bodyPart.replace(new RegExp(`(</${tag}>)\\s*</p>`, 'g'), '$1');
    }
    bodyPart = bodyPart.replace(/<p>\s*<\/p>/g, '');
    bodyPart = bodyPart.replace(/(?<!>)\n(?!<)/g, '<br>');

    let refHtml = '';
    if (refPart) {
      refHtml = `<div class="references"><strong style="color:#6366f1;font-size:10px;">References</strong><br>`;
      refPart.replace(/\[(\d+)\]\s*(https?:\/\/[^\s<"]+)/g, (_, n, url) => {
        const domain = (() => { try { return new URL(url).hostname.replace('www.', ''); } catch { return url; } })();
        refHtml += `<a href="#" data-url="${esc(url)}">[${n}] ${esc(domain)}</a><br>`;
        return '';
      });
      refHtml += '</div>';
    }

    let out = bodyPart.replace(/\x00BLOCK(\d+)\x00/g, (_, i) => {
      const { lang, code } = blocks[parseInt(i)];
      const id = `cb-${Date.now()}-${i}`;
      return `<div class="code-block">
  <div class="code-header">
    <span class="code-lang">${esc(lang)}</span>
    <div class="code-actions">
      <button class="btn-copy" data-id="${id}" title="Copy">Copy</button>
      <button class="btn-insert" data-id="${id}" title="Insert into active editor">Insert</button>
    </div>
  </div>
  <pre id="${id}">${esc(code)}</pre>
</div>`;
    });

    return out + refHtml;
  }

  // ── Plan panel ────────────────────────────────────────────────────────────────

  function showPlan(summary, steps) {
    planSteps = steps;
    planPanel.innerHTML = '';

    const header = document.createElement('div');
    header.className = 'plan-header';
    header.innerHTML = `<span class="plan-icon">📋</span><span class="plan-summary">${esc(summary)}</span>`;
    planPanel.appendChild(header);

    const list = document.createElement('ol');
    list.className = 'plan-steps';
    steps.forEach((step, i) => {
      const li = document.createElement('li');
      li.className = 'plan-step pending';
      li.dataset.index = String(i);
      li.innerHTML = `<span class="step-status">⏳</span><span class="step-text">${esc(step)}</span>`;
      list.appendChild(li);
    });
    planPanel.appendChild(list);
    planPanel.classList.remove('hidden');
    scrollBottom();
  }

  function updatePlanStep(index, status) {
    const li = planPanel.querySelector(`[data-index="${index}"]`);
    if (!li) return;
    li.className = `plan-step ${status}`;
    const icon = li.querySelector('.step-status');
    if (icon) icon.textContent = status === 'running' ? '🔄' : status === 'done' ? '✅' : '⏳';
  }

  // ── Message builders ──────────────────────────────────────────────────────────

  function addUser(/** @type {string} */ text) {
    removeEmptyState();
    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `<span class="role">You</span><div class="bubble">${esc(text).replace(/\n/g, '<br>')}</div>`;
    messages.appendChild(div);
    scrollBottom();
  }

  function addAssistant(/** @type {string} */ text) {
    removeEmptyState();
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = `<span class="role">Luna</span><div class="bubble md">${md(text)}</div>`;
    messages.appendChild(div);
    attachCodeActions(div);
    scrollBottom();
  }

  function startAssistant() {
    removeEmptyState();
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = `<span class="role">Luna</span><div class="bubble md"><div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>`;
    messages.appendChild(div);
    activeBubble = div.querySelector('.bubble');
    activeText = '';
    scrollBottom();
  }

  function appendToken(/** @type {string} */ token) {
    if (!activeBubble) startAssistant();
    activeText += token;
    if (activeBubble) {
      activeBubble.innerHTML = md(activeText);
      scrollBottom();
    }
  }

  function finalizeAssistant() {
    if (activeBubble) {
      activeBubble.innerHTML = md(activeText);
      attachCodeActions(activeBubble);
    }
    activeBubble = null;
    activeText = '';
  }

  function showError(/** @type {string} */ msg) {
    if (activeBubble) { activeBubble.closest('.msg')?.remove(); activeBubble = null; }
    const div = document.createElement('div');
    div.className = 'error-row';
    div.textContent = msg;
    messages.appendChild(div);
    scrollBottom();
  }

  function showConfirm(/** @type {{confirm_id:string, tool:string, message:string}} */ data) {
    const div = document.createElement('div');
    div.className = 'confirm-banner';
    div.innerHTML = `
      <div class="confirm-label">Luna wants to run a tool</div>
      <div class="confirm-tool">${esc(data.tool)}</div>
      <div style="font-size:10.5px;color:#9ca3af;margin-top:2px">${esc(data.message)}</div>
      <div class="confirm-actions">
        <button class="btn-allow">Allow</button>
        <button class="btn-deny">Deny</button>
      </div>`;
    messages.appendChild(div);
    scrollBottom();
    div.querySelector('.btn-allow')?.addEventListener('click', () => {
      div.remove();
      vscode.postMessage({ type: 'confirm_answer', confirm_id: data.confirm_id, approved: true });
    });
    div.querySelector('.btn-deny')?.addEventListener('click', () => {
      div.remove();
      vscode.postMessage({ type: 'confirm_answer', confirm_id: data.confirm_id, approved: false });
    });
  }

  // ── Tool event rendering ──────────────────────────────────────────────────────

  const TOOL_ICONS = {
    code_read_file:  '📖',
    code_write_file: '✏️',
    code_list_files: '📁',
    code_search:     '🔍',
    code_run_shell:  '⚡',
  };

  function _toolLabel(tool, args) {
    switch (tool) {
      case 'code_read_file':  return `Reading ${args.path || ''}`;
      case 'code_write_file': return `Writing ${args.path || ''}`;
      case 'code_list_files': return `Listing ${args.path || '(root)'}`;
      case 'code_search':     return `Searching "${args.pattern || ''}"`;
      case 'code_run_shell':  return `Running: ${(args.command || '').slice(0, 60)}`;
      default:                return tool;
    }
  }

  function addToolCard(tool, args) {
    finalizeAssistant();
    const icon = TOOL_ICONS[tool] || '🔧';
    const label = _toolLabel(tool, args);
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.innerHTML = `
      <div class="tool-header">
        <span class="tool-icon">${icon}</span>
        <span class="tool-label">${esc(label)}</span>
        <span class="tool-spinner"></span>
      </div>
      <div class="tool-result hidden"></div>`;
    messages.appendChild(card);
    activeToolCard = card;
    scrollBottom();
    return card;
  }

  function populateToolResult(card, tool, result) {
    const spinner = card.querySelector('.tool-spinner');
    if (spinner) spinner.remove();
    const resultDiv = card.querySelector('.tool-result');
    if (!resultDiv) return;

    if (tool === 'code_write_file') {
      const pathMatch = result.match(/^written: (.+?) \(/);
      const filePath = pathMatch ? pathMatch[1] : '';
      resultDiv.innerHTML = `<span class="tool-result-text">${esc(result)}</span>`;
      if (filePath) {
        const btn = document.createElement('button');
        btn.className = 'apply-btn';
        btn.textContent = 'Open in Editor';
        btn.addEventListener('click', () => vscode.postMessage({ type: 'apply_file', path: filePath, content: '' }));
        resultDiv.appendChild(btn);
      }
    } else {
      const lines = result.split('\n').slice(0, 12).join('\n');
      const truncated = result.split('\n').length > 12 ? lines + `\n… (${result.split('\n').length} lines)` : lines;
      resultDiv.innerHTML = `<span class="tool-result-text">${esc(truncated)}</span>`;
    }

    resultDiv.classList.remove('hidden');
    const header = card.querySelector('.tool-header');
    if (header) {
      /** @type {HTMLElement} */ (header).style.cursor = 'pointer';
      header.addEventListener('click', () => resultDiv.classList.toggle('hidden'));
    }
    scrollBottom();
  }

  function addShellConfirm(tool, args) {
    const cmd = (args.command || '').slice(0, 200);
    const div = document.createElement('div');
    div.className = 'confirm-banner';
    div.innerHTML = `
      <div class="confirm-label">Luna wants to run a shell command</div>
      <div class="confirm-tool">${esc(tool)}</div>
      <div class="confirm-cmd">${esc(cmd)}</div>
      <div class="confirm-actions">
        <button class="btn-allow">Allow</button>
        <button class="btn-deny">Deny</button>
      </div>`;
    messages.appendChild(div);
    scrollBottom();
    div.querySelector('.btn-allow')?.addEventListener('click', () => { div.remove(); vscode.postMessage({ type: 'confirm_answer', approved: true }); });
    div.querySelector('.btn-deny')?.addEventListener('click', () => { div.remove(); vscode.postMessage({ type: 'confirm_answer', approved: false }); });
  }

  // ── Code action delegation ────────────────────────────────────────────────────

  function attachCodeActions(/** @type {HTMLElement} */ root) {
    root.querySelectorAll('.btn-copy').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = /** @type {HTMLElement} */ (btn).dataset.id;
        const pre = id ? document.getElementById(id) : null;
        if (!pre) return;
        vscode.postMessage({ type: 'copy_code', code: pre.textContent ?? '' });
        btn.textContent = 'Copied!';
        /** @type {HTMLElement} */ (btn).classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; /** @type {HTMLElement} */ (btn).classList.remove('copied'); }, 1800);
      });
    });
    root.querySelectorAll('.btn-insert').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = /** @type {HTMLElement} */ (btn).dataset.id;
        const pre = id ? document.getElementById(id) : null;
        if (!pre) return;
        vscode.postMessage({ type: 'insert_code', code: pre.textContent ?? '' });
      });
    });
    root.querySelectorAll('a[data-url]').forEach(a => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        const url = /** @type {HTMLElement} */ (a).dataset.url;
        if (url) vscode.postMessage({ type: 'open_url', url });
      });
    });
  }

  messages.addEventListener('click', (/** @type {MouseEvent} */ e) => {
    const t = /** @type {HTMLElement} */ (e.target);
    if (!t) return;
    if (t.classList.contains('btn-copy')) {
      const id = t.dataset.id;
      const pre = id ? document.getElementById(id) : null;
      if (!pre) return;
      vscode.postMessage({ type: 'copy_code', code: pre.textContent ?? '' });
      t.textContent = 'Copied!'; t.classList.add('copied');
      setTimeout(() => { t.textContent = 'Copy'; t.classList.remove('copied'); }, 1800);
    }
    if (t.classList.contains('btn-insert')) {
      const id = t.dataset.id;
      const pre = id ? document.getElementById(id) : null;
      if (pre) vscode.postMessage({ type: 'insert_code', code: pre.textContent ?? '' });
    }
    if (t.tagName === 'A' && t.dataset.url) {
      e.preventDefault();
      vscode.postMessage({ type: 'open_url', url: t.dataset.url });
    }
  });

  // ── @mention autocomplete ─────────────────────────────────────────────────────

  let mentionQuery = '';
  let mentionActive = false;

  function showMentionMenu(query) {
    const filtered = workspaceFiles
      .filter(f => f.toLowerCase().includes(query.toLowerCase()))
      .slice(0, 10);

    if (!filtered.length) { hideMentionMenu(); return; }

    mentionMenu.innerHTML = '';
    filtered.forEach(file => {
      const item = document.createElement('div');
      item.className = 'mention-item';
      const parts = file.split(/[\\/]/);
      const name = parts.pop() || file;
      const dir = parts.join('/');
      item.innerHTML = `<span class="mention-name">${esc(name)}</span>${dir ? `<span class="mention-dir">${esc(dir)}</span>` : ''}`;
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        insertMention(file);
      });
      mentionMenu.appendChild(item);
    });
    mentionMenu.classList.remove('hidden');
    mentionActive = true;
  }

  function hideMentionMenu() {
    mentionMenu.classList.add('hidden');
    mentionActive = false;
    mentionQuery = '';
  }

  function insertMention(file) {
    const val = input.value;
    const pos = input.selectionStart ?? val.length;
    const atPos = val.lastIndexOf('@', pos - 1);
    if (atPos === -1) { hideMentionMenu(); return; }
    const before = val.slice(0, atPos);
    const after = val.slice(pos);
    input.value = before + '@' + file + ' ' + after;
    const newPos = atPos + file.length + 2;
    input.setSelectionRange(newPos, newPos);
    hideMentionMenu();
    autoResize();
    input.focus();
    // Ask extension host to read file content for inline injection
    vscode.postMessage({ type: 'read_file_for_mention', path: file });
  }

  input.addEventListener('keydown', (/** @type {KeyboardEvent} */ e) => {
    if (mentionActive) {
      if (e.key === 'Escape') { hideMentionMenu(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const items = mentionMenu.querySelectorAll('.mention-item');
        const focused = mentionMenu.querySelector('.mention-item.focused');
        const idx = focused ? Array.from(items).indexOf(focused) : -1;
        if (idx < items.length - 1) {
          focused?.classList.remove('focused');
          items[idx + 1]?.classList.add('focused');
        }
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        const items = mentionMenu.querySelectorAll('.mention-item');
        const focused = mentionMenu.querySelector('.mention-item.focused');
        const idx = focused ? Array.from(items).indexOf(focused) : items.length;
        if (idx > 0) {
          focused?.classList.remove('focused');
          items[idx - 1]?.classList.add('focused');
        }
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        const focused = mentionMenu.querySelector('.mention-item.focused');
        if (focused) {
          e.preventDefault();
          const name = /** @type {HTMLElement} */ (focused).querySelector('.mention-name')?.textContent || '';
          const dir = /** @type {HTMLElement} */ (focused).querySelector('.mention-dir')?.textContent || '';
          insertMention(dir ? `${dir}/${name}` : name);
          return;
        }
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  input.addEventListener('input', () => {
    autoResize();
    const val = input.value;
    const pos = input.selectionStart ?? val.length;
    const atPos = val.lastIndexOf('@', pos - 1);
    if (atPos !== -1 && (atPos === 0 || /\s/.test(val[atPos - 1]))) {
      mentionQuery = val.slice(atPos + 1, pos);
      if (!mentionQuery.includes(' ')) {
        showMentionMenu(mentionQuery);
        return;
      }
    }
    hideMentionMenu();
  });

  // ── Send ──────────────────────────────────────────────────────────────────────

  function send() {
    if (streaming) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    autoResize();
    addUser(text);
    vscode.postMessage({ type: 'send', text });
  }

  sendBtn.addEventListener('click', send);

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 130) + 'px';
  }

  newBtn.addEventListener('click', () => {
    messages.innerHTML = _emptyState();
    planPanel.classList.add('hidden');
    planPanel.innerHTML = '';
    planSteps = [];
    workspaceBar.classList.add('hidden');
    vscode.postMessage({ type: 'new_chat' });
  });

  // ── Mode toggle ───────────────────────────────────────────────────────────────

  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = /** @type {HTMLElement} */ (btn).dataset.mode || 'chat';
      vscode.postMessage({ type: 'set_mode', mode });
      messages.innerHTML = _emptyState();
      planPanel.classList.add('hidden');
      planPanel.innerHTML = '';
      planSteps = [];
      workspaceBar.classList.add('hidden');
      input.placeholder = mode === 'code' ? 'Describe what to build or fix… (@file to attach)' : 'Ask Luna…';
    });
  });

  // ── Messages from extension ───────────────────────────────────────────────────

  window.addEventListener('message', (/** @type {MessageEvent} */ e) => {
    const msg = e.data;
    switch (msg.type) {

      case 'stream_start':
        streaming = true;
        sendBtn.disabled = true;
        activeToolCard = null;
        planSteps = [];
        if (msg.mode === 'code' && msg.workspace) {
          workspaceBar.textContent = '📂 ' + msg.workspace;
          workspaceBar.classList.remove('hidden');
        } else {
          workspaceBar.classList.add('hidden');
        }
        startAssistant();
        break;

      case 'token':
        appendToken(msg.content);
        break;

      case 'plan':
        showPlan(msg.summary || 'Execution plan', msg.steps || []);
        break;

      case 'plan_step':
        updatePlanStep(msg.index, msg.status);
        break;

      case 'workspace_index':
        // Silently received — used for context; no UI needed
        break;

      case 'tool_call':
        addToolCard(msg.tool, msg.args || {});
        break;

      case 'tool_result':
        if (activeToolCard) {
          populateToolResult(activeToolCard, msg.tool, msg.result || '');
          activeToolCard = null;
        }
        break;

      case 'shell_confirm':
        if (activeToolCard) {
          const sp = activeToolCard.querySelector('.tool-spinner');
          if (sp) sp.remove();
          activeToolCard = null;
        }
        addShellConfirm(msg.tool, msg.args || {});
        break;

      case 'stream_end':
        streaming = false;
        sendBtn.disabled = false;
        finalizeAssistant();
        // Remove empty trailing bubble
        if (!activeText) {
          const last = messages.lastElementChild;
          if (last && last.classList.contains('msg') && last.classList.contains('assistant')) {
            const bubble = last.querySelector('.bubble');
            if (bubble && bubble.innerHTML.includes('typing')) last.remove();
          }
        }
        break;

      case 'error':
        streaming = false;
        sendBtn.disabled = false;
        showError(msg.message);
        break;

      case 'confirm':
        showConfirm(msg);
        break;

      case 'workspace_files':
        workspaceFiles = msg.files || [];
        break;

      case 'history':
        messages.innerHTML = '';
        (msg.messages || []).forEach((m) => {
          if (m.role === 'user') addUser(m.content || '');
          else if (m.role === 'assistant') addAssistant(m.content || '');
        });
        if (!messages.children.length) messages.innerHTML = _emptyState();
        break;

      case 'prefill':
        input.value = msg.text;
        autoResize();
        input.focus();
        setTimeout(send, 80);
        break;

      case 'clear':
        messages.innerHTML = _emptyState();
        planPanel.classList.add('hidden');
        planPanel.innerHTML = '';
        planSteps = [];
        workspaceBar.classList.add('hidden');
        break;
    }
  });
})();

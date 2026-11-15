"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.LunaChatViewProvider = void 0;
const vscode = __importStar(require("vscode"));
const http = __importStar(require("http"));
const https = __importStar(require("https"));
const path = __importStar(require("path"));
function getNonce() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}
class LunaChatViewProvider {
    constructor(_ctx) {
        this._ctx = _ctx;
        this._codeHistory = [];
        this._mode = 'chat';
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.file(path.join(this._ctx.extensionPath, 'media'))],
        };
        webviewView.webview.html = this._buildHtml(webviewView.webview);
        // Send workspace file list for @mention autocomplete
        this._sendWorkspaceFiles();
        this._loadSharedContext();
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.type) {
                case 'send':
                    if (this._mode === 'code') {
                        await this._streamCode(msg.text);
                    }
                    else {
                        await this._streamChat(msg.text);
                    }
                    break;
                case 'set_mode':
                    this._mode = msg.mode;
                    this._codeHistory = [];
                    this._sendWorkspaceFiles();
                    break;
                case 'insert_code':
                    this._insertIntoEditor(msg.code);
                    break;
                case 'apply_file':
                    this._applyFileEdit(msg.path, msg.content);
                    break;
                case 'copy_code':
                    vscode.env.clipboard.writeText(msg.code);
                    break;
                case 'new_chat':
                    this._conversationId = undefined;
                    this._codeHistory = [];
                    await this._setSharedConversation(null);
                    break;
                case 'open_url':
                    vscode.env.openExternal(vscode.Uri.parse(msg.url));
                    break;
                case 'confirm_answer':
                    break;
                case 'read_file_for_mention': {
                    const content = await this._readWorkspaceFile(msg.path);
                    if (content !== null) {
                        this._post({ type: 'file_content', path: msg.path, content });
                    }
                    break;
                }
            }
        });
    }
    sendUserMessage(text) {
        this._view?.webview.postMessage({ type: 'prefill', text });
    }
    newConversation() {
        this._conversationId = undefined;
        this._codeHistory = [];
        this._view?.webview.postMessage({ type: 'clear' });
    }
    // ── Chat streaming (Luna's /api/chat/stream) ────────────────────────────────
    async _streamChat(userText) {
        const baseUrl = this._baseUrl();
        const body = JSON.stringify({
            message: userText,
            ...(this._conversationId ? { conversation_id: this._conversationId } : {}),
        });
        this._post({ type: 'stream_start', mode: 'chat' });
        await this._doRequest(`${baseUrl}/api/chat/stream`, body, (data) => {
            if (data.type === 'meta' && data.conversation_id) {
                this._conversationId = data.conversation_id;
            }
            else if (data.type === 'message_part' && data.content) {
                this._post({ type: 'token', content: data.content });
            }
            else if (data.type === 'confirmation_required') {
                this._post({ type: 'confirm', message: data.message, confirm_id: data.confirm_id, tool: data.tool });
            }
            else if (data.type === 'done') {
                this._post({ type: 'stream_end' });
                return true;
            }
            else if (data.type === 'error') {
                this._post({ type: 'error', message: data.message });
                return true;
            }
            return false;
        });
    }
    // ── Code Agent streaming (Luna's /api/coding/stream) ───────────────────────
    async _streamCode(userText) {
        const baseUrl = this._baseUrl();
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
        const editor = vscode.window.activeTextEditor;
        const currentFile = editor ? path.relative(workspaceRoot, editor.document.fileName) : '';
        const selection = editor ? editor.document.getText(editor.selection).trim() : '';
        // Build enriched message with editor context
        let enriched = userText;
        if (currentFile) {
            enriched = `[File: ${currentFile}${selection ? `, selected:\n\`\`\`\n${selection.slice(0, 800)}\n\`\`\`` : ''}]\n\n${userText}`;
        }
        this._codeHistory.push({ role: 'user', content: enriched });
        const body = JSON.stringify({
            message: enriched,
            history: this._codeHistory.slice(0, -1), // all prior turns
            workspace_root: workspaceRoot,
            auto_confirm_shell: false,
        });
        let assistantReply = '';
        this._post({ type: 'stream_start', mode: 'code', workspace: workspaceRoot });
        await this._doRequest(`${baseUrl}/api/coding/stream`, body, (data) => {
            if (data.type === 'token') {
                assistantReply += data.content;
                this._post({ type: 'token', content: data.content });
            }
            else if (data.type === 'tool_call') {
                this._post({ type: 'tool_call', tool: data.tool, args: data.args });
            }
            else if (data.type === 'tool_result') {
                this._post({ type: 'tool_result', tool: data.tool, result: data.result });
                // Track write results for Apply button
                if (data.tool === 'code_write_file') {
                    // result format: "written: path (N chars)"
                    // args are passed back from the event
                }
            }
            else if (data.type === 'confirmation_required') {
                this._post({ type: 'shell_confirm', tool: data.tool, args: data.args });
            }
            else if (data.type === 'done') {
                if (assistantReply) {
                    this._codeHistory.push({ role: 'assistant', content: assistantReply });
                }
                this._post({ type: 'stream_end' });
                return true;
            }
            else if (data.type === 'error') {
                this._post({ type: 'error', message: data.message });
                return true;
            }
            return false;
        });
    }
    // ── Shared HTTP request handler ─────────────────────────────────────────────
    _doRequest(urlStr, body, onData) {
        const url = new URL(urlStr);
        const isHttps = url.protocol === 'https:';
        const mod = isHttps ? https : http;
        const options = {
            hostname: url.hostname,
            port: Number(url.port) || (isHttps ? 443 : 80),
            path: `${url.pathname}${url.search}`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(body),
            },
        };
        return new Promise((resolve) => {
            const req = mod.request(options, (res) => {
                let buf = '';
                res.on('data', (chunk) => {
                    buf += chunk.toString();
                    const lines = buf.split('\n');
                    buf = lines.pop() ?? '';
                    for (const line of lines) {
                        if (!line.startsWith('data:'))
                            continue;
                        try {
                            const data = JSON.parse(line.slice(5).trim());
                            if (onData(data)) {
                                resolve();
                                return;
                            }
                        }
                        catch { /* skip */ }
                    }
                });
                res.on('end', () => { this._post({ type: 'stream_end' }); resolve(); });
                res.on('error', (e) => { this._post({ type: 'error', message: e.message }); resolve(); });
            });
            req.on('error', () => {
                this._post({ type: 'error', message: 'Cannot reach Luna backend. Make sure the Luna app is running.' });
                resolve();
            });
            req.setTimeout(120000, () => {
                req.destroy();
                this._post({ type: 'error', message: 'Request timed out.' });
                resolve();
            });
            req.write(body);
            req.end();
        });
    }
    _baseUrl() {
        const config = vscode.workspace.getConfiguration('luna');
        return config.get('backendUrl', 'http://localhost:8899').replace(/\/$/, '');
    }
    _getJson(pathName) {
        const url = new URL(`${this._baseUrl()}${pathName}`);
        const mod = url.protocol === 'https:' ? https : http;
        return new Promise((resolve) => {
            const req = mod.request({
                hostname: url.hostname,
                port: Number(url.port) || (url.protocol === 'https:' ? 443 : 80),
                path: `${url.pathname}${url.search}`,
                method: 'GET',
            }, (res) => {
                let buf = '';
                res.on('data', (chunk) => { buf += chunk.toString(); });
                res.on('end', () => {
                    try {
                        resolve(JSON.parse(buf));
                    }
                    catch {
                        resolve(null);
                    }
                });
            });
            req.on('error', () => resolve(null));
            req.setTimeout(5000, () => { req.destroy(); resolve(null); });
            req.end();
        });
    }
    _postJson(pathName, payload) {
        const body = JSON.stringify(payload);
        const url = new URL(`${this._baseUrl()}${pathName}`);
        const mod = url.protocol === 'https:' ? https : http;
        return new Promise((resolve) => {
            const req = mod.request({
                hostname: url.hostname,
                port: Number(url.port) || (url.protocol === 'https:' ? 443 : 80),
                path: `${url.pathname}${url.search}`,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(body),
                },
            }, (res) => {
                let buf = '';
                res.on('data', (chunk) => { buf += chunk.toString(); });
                res.on('end', () => {
                    try {
                        resolve(JSON.parse(buf));
                    }
                    catch {
                        resolve(null);
                    }
                });
            });
            req.on('error', () => resolve(null));
            req.setTimeout(5000, () => { req.destroy(); resolve(null); });
            req.write(body);
            req.end();
        });
    }
    async _loadSharedContext() {
        const ctx = await this._getJson('/api/chat/context');
        if (!ctx?.active_conversation_id)
            return;
        const conv = await this._getJson(`/api/chat/conversations/${ctx.active_conversation_id}`);
        this._conversationId = ctx.active_conversation_id;
        this._post({ type: 'history', messages: conv?.messages ?? [] });
    }
    async _setSharedConversation(conversationId) {
        await this._postJson('/api/chat/context', { active_conversation_id: conversationId });
    }
    // ── Editor integration ──────────────────────────────────────────────────────
    _insertIntoEditor(code) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Open a file in the editor first.');
            return;
        }
        editor.edit((b) => b.replace(editor.selection, code));
    }
    async _applyFileEdit(filePath, content) {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceRoot) {
            vscode.window.showErrorMessage('No workspace folder open.');
            return;
        }
        const absPath = path.isAbsolute(filePath)
            ? filePath
            : path.join(workspaceRoot, filePath);
        const uri = vscode.Uri.file(absPath);
        const enc = new TextEncoder();
        await vscode.workspace.fs.writeFile(uri, enc.encode(content));
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc, { preview: false });
        vscode.window.showInformationMessage(`Luna wrote ${path.basename(absPath)}`);
    }
    _post(msg) {
        this._view?.webview.postMessage(msg);
    }
    // ── Workspace helpers ───────────────────────────────────────────────────────
    async _sendWorkspaceFiles() {
        const root = vscode.workspace.workspaceFolders?.[0]?.uri;
        if (!root)
            return;
        try {
            const pattern = new vscode.RelativePattern(root, '**/*');
            const uris = await vscode.workspace.findFiles(pattern, '{**/node_modules/**,**/.git/**,**/dist/**,**/build/**,**/__pycache__/**,**/.venv/**}', 500);
            const files = uris.map(u => path.relative(root.fsPath, u.fsPath).replace(/\\/g, '/'));
            this._post({ type: 'workspace_files', files });
        }
        catch { /* no workspace */ }
    }
    async _readWorkspaceFile(filePath) {
        const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!root)
            return null;
        try {
            const absPath = path.isAbsolute(filePath) ? filePath : path.join(root, filePath);
            const bytes = await vscode.workspace.fs.readFile(vscode.Uri.file(absPath));
            return Buffer.from(bytes).toString('utf-8').slice(0, 8000);
        }
        catch {
            return null;
        }
    }
    // ── HTML ────────────────────────────────────────────────────────────────────
    _buildHtml(webview) {
        const base = vscode.Uri.file(path.join(this._ctx.extensionPath, 'media'));
        const cssUri = webview.asWebviewUri(vscode.Uri.joinPath(base, 'panel.css'));
        const jsUri = webview.asWebviewUri(vscode.Uri.joinPath(base, 'panel.js'));
        const logoUri = webview.asWebviewUri(vscode.Uri.joinPath(base, 'luna-icon.svg'));
        const nonce = getNonce();
        return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none';
                 style-src ${webview.cspSource} 'unsafe-inline';
                 img-src ${webview.cspSource};
                 script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${cssUri}" rel="stylesheet">
  <title>Luna AI</title>
</head>
<body>
  <div id="header">
    <div class="header-left">
      <img src="${logoUri}" class="header-logo" alt="Luna">
      <span class="logo-name">Luna</span>
    </div>
    <div class="header-actions">
      <div class="mode-toggle">
        <button class="mode-btn active" data-mode="chat" title="General chat">Chat</button>
        <button class="mode-btn" data-mode="code" title="Coding agent with file access">Code</button>
      </div>
      <button id="new-btn" title="New conversation">&#xff0b;</button>
    </div>
  </div>

  <div id="workspace-bar" class="hidden"></div>
  <div id="plan-panel" class="hidden"></div>

  <div id="messages">
    <div class="empty-state">
      <img src="${logoUri}" class="empty-logo" alt="Luna">
      <div class="empty-title">Luna AI</div>
      <div class="empty-sub">Ask anything &middot; Explain &middot; Fix bugs &middot; Search the web<br>Use <strong>@</strong> to attach files &middot; Right-click code for quick actions.</div>
    </div>
  </div>

  <div id="input-wrap">
    <div id="mention-menu" class="hidden"></div>
    <textarea id="input" placeholder="Ask Luna…" rows="1"></textarea>
    <button id="send-btn" title="Send (Enter)">&#x2191;</button>
  </div>

  <script nonce="${nonce}">window.__LUNA_LOGO__ = "${logoUri}";</script>
  <script nonce="${nonce}" src="${jsUri}"></script>
</body>
</html>`;
    }
}
exports.LunaChatViewProvider = LunaChatViewProvider;
LunaChatViewProvider.viewType = 'luna.chatView';
LunaChatViewProvider.viewTypeSecondary = 'luna.chatViewSecondary';
//# sourceMappingURL=lunaPanel.js.map
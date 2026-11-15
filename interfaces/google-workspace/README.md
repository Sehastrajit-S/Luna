# Luna AI — Google Workspace Add-on

Brings Luna's chat, memory, and AI capabilities into Google Docs, Sheets, and Slides via a sidebar.

## What it does

| Feature | Docs | Sheets | Slides |
|---------|------|--------|--------|
| Chat with Luna | ✓ | ✓ | ✓ |
| Send selected text to Luna | ✓ | ✓ (cells) | ✓ (slide text) |
| Read document for context | ✓ | ✓ (sheet data) | ✓ (current slide) |
| Insert Luna's response | ✓ (at cursor) | ✓ (in cell) | — |
| Persistent conversation | ✓ | ✓ | ✓ |

## Architecture

Apps Script calls Luna's `POST /api/chat/stream` endpoint server-side via `UrlFetchApp`.  
The sidebar HTML runs inside a sandboxed `<iframe>` served by `HtmlService`.  
User preferences (server URL, auth token, conversation ID) are stored per-user via `PropertiesService`.

## Prerequisites

- A Google account
- Luna backend accessible from the internet (or a local tunnel for development)
  - Use [ngrok](https://ngrok.com): `ngrok http 8899` → use the `https://xxx.ngrok.io` URL
  - Or deploy Luna to a server with HTTPS

> Apps Script cannot reach `localhost` — it runs on Google's servers. Use ngrok or a deployed URL.

## Installation

### Option A — Apps Script Editor (recommended for development)

1. Open [script.google.com](https://script.google.com) → **New project**.
2. Replace the default `Code.gs` with the contents of `Code.gs`.
3. Create a new HTML file named `Sidebar` and paste the contents of `Sidebar.html`.
4. Click the **⚙ Project Settings** gear → paste the contents of `appsscript.json` into the manifest editor (enable "Show 'appsscript.json' manifest file in editor" first).
5. Click **Deploy → Test deployments** → **Install** to install as an add-on in your account.
6. Open a Google Doc/Sheet/Slide → the **Luna AI** sidebar appears in the add-ons menu.

### Option B — Google Workspace Marketplace (for team distribution)

1. Publish the add-on to the internal Workspace Marketplace.
2. Team members install from the Marketplace.

## First-time setup

1. Click the **Luna AI** menu → **Open** to open the sidebar.
2. Click the universal actions menu (⋮) → **Settings**.
3. Enter your Luna server URL (must be HTTPS for Apps Script access).
4. Optionally enter a JWT bearer token for business variant.
5. Click **Save settings** → **Test connection** to verify.

## Using the add-on

- **Use Selection** — sends selected text / cells / slide text to Luna with context.
- **Read Document** — sends the first 3 000 characters of the current document.
- **Insert Response** — inserts Luna's last reply at the cursor (Docs) or active cell (Sheets).
- **New Conversation** — clears the conversation ID and starts fresh.

## File reference

| File | Purpose |
|------|---------|
| `appsscript.json` | Manifest — scopes, triggers, host registrations |
| `Code.gs` | Server-side logic: homepage cards, Luna API calls, document read/write |
| `Sidebar.html` | Client-side sidebar UI (chat interface, rendered by HtmlService) |

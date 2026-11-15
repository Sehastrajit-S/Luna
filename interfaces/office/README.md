# Luna AI — Office Add-in

Brings Luna's chat, memory, and AI capabilities into Word, Excel, and PowerPoint via a task pane.

## What it does

| Feature | Word | Excel | PowerPoint |
|---------|------|-------|------------|
| Chat with Luna | ✓ | ✓ | ✓ |
| Send selected text to Luna | ✓ | ✓ (cells) | ✓ (slide text) |
| Insert Luna's response at cursor | ✓ | ✓ (cell) | ✓ |
| Read entire document for context | ✓ | ✓ (sheet data) | — |
| Streaming responses | ✓ | ✓ | ✓ |
| Persistent conversation | ✓ | ✓ | ✓ |

## Prerequisites

- Luna backend running at `http://localhost:8899` (or any accessible URL)
- Microsoft 365 (desktop or web) — Office 2016+ for desktop

## Installation

### Step 1 — start Luna
```
python -m backend.main
```

The add-in files are served automatically at `http://localhost:8899/addin/office/`.

### Step 2 — sideload the manifest

**Word / Excel / PowerPoint desktop (Windows):**
1. Open the app.
2. Go to **Insert → Add-ins → My Add-ins → Upload My Add-in**.
3. Browse to `office-addin/manifest.xml` and click **Upload**.
4. The **Luna AI** button appears in the **Home** ribbon.

**Word / Excel / PowerPoint desktop (Mac):**
1. Copy `manifest.xml` to `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/` (Word), or the equivalent Excel/PowerPoint path.
2. Restart the app — the add-in appears in the ribbon.

**Microsoft 365 web (Office Online):**
1. Open a document in Office Online.
2. Go to **Insert → Add-ins → Upload My Add-in**.
3. Upload `manifest.xml`.

> **HTTPS required for production.** For localhost development, HTTP works. Deploy Luna behind a reverse proxy with TLS for team use.

## Customising the manifest

- Change the `<Id>` GUID to a fresh one for production deploys — [generate one here](https://www.guidgenerator.com).
- Replace `localhost:8899` with your Luna server URL in all `DefaultValue` attributes.
- Replace the icon PNGs in `assets/` (16×16, 32×32, 64×64, 80×80).

## Using the add-in

1. Click **Open Luna** in the Home ribbon.
2. The task pane opens on the right.
3. Type a message and press **Enter** or click **Send**.
4. **Use Selection** — sends your current text selection as context.
5. **Read Document** — sends the first 3 000 characters of the document.
6. **Insert Response** — inserts Luna's last reply at the cursor position.
7. Click ⚙ to configure the server URL and auth token.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Server URL | `http://localhost:8899` | Your Luna backend URL |
| Auth token | (blank) | JWT bearer token — required for business variant |

Settings are persisted in `localStorage` per browser/app session.

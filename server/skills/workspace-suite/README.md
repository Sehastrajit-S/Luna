# Workspace Suite

Gmail, Google Calendar, Drive, Docs, Sheets, Outlook, OneDrive, Excel, Teams, and more — in one skill.

## What it does

Routes workspace requests to the right provider (Google or Microsoft). Read-only tasks execute directly. Actions that send, create, update, delete, invite, upload, or share go through Luna's confirmation flow before execution. If credentials aren't configured, it tells you exactly which OAuth token or env var is missing.

## When it activates

When you ask to work with Google Workspace or Microsoft 365 — email, calendar, files, documents, spreadsheets, tasks, or team collaboration.

## Example prompts

- "Search my Gmail for emails from Anthropic this week"
- "Create a Google Calendar event for tomorrow at 2pm"
- "List the files in my Google Drive root folder"
- "Create a new Google Sheet with these column headers"
- "Search my Outlook inbox for invoices from last month"
- "Add a task to my Microsoft To Do"

## Tools used

| Tool | Purpose |
|---|---|
| `google_workspace` | Gmail, Calendar, Drive, Docs, Sheets, Slides, Tasks, People |
| `microsoft_workspace` | Outlook mail/calendar, OneDrive, Excel, To Do, Teams, profile |

## Setup

Configure OAuth credentials in `.env`:

```env
# Google
google_workspace_client_id=
google_workspace_client_secret=
google_workspace_refresh_token=

# Microsoft
microsoft_workspace_client_id=
microsoft_workspace_client_secret=
microsoft_workspace_tenant_id=common
microsoft_workspace_refresh_token=
```

See [`integrations/google-workspace/`](../../integrations/google-workspace/) and [`integrations/office/`](../../integrations/office/) for platform-specific add-ons.

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

# Workspace Suite

Use this skill when the user asks to check, read, fetch, send, or search their mail, mails, email, emails, or inbox — regardless of whether they name Gmail or Outlook explicitly. Also use it for: Calendar, Drive, Docs, Sheets, Slides, Tasks, Contacts (Google), or Outlook, OneDrive, Excel, To Do, Teams (Microsoft).

Do NOT hand off to the research skill. These are live account operations, not web searches.

Workflow:

1. Identify the provider from the request. Use Google tools for Gmail, Google Calendar, Drive, Docs, Sheets, Slides, Tasks, and People. Use Microsoft tools for Outlook mail/calendar, OneDrive, Excel, To Do, Teams, and profile data.
2. For read-only tasks, call the provider tool directly when configured.
3. For actions that send, create, update, delete, invite, upload, or share, rely on Luna's confirmation flow before execution.
4. Do not assume credentials are configured. If the tool returns an access-token error, tell the user which OAuth token or refresh-token config is missing.
5. When creating or editing cloud documents, summarize what will be changed and where.
6. For files and spreadsheets, preserve source/provenance metadata when the content came from web research or a downloaded dataset.
7. For business variant use, keep responses professional and concise.

Common actions:

- Google: `google_workspace(service="gmail", action="search_messages", args={...})`
- Google Docs: create with `service="docs", action="create_document"` and update through documented raw requests when needed.
- Google Sheets: create or update values with `service="sheets"`.
- Microsoft: `microsoft_workspace(service="mail", action="search_messages", args={...})`
- Microsoft Drive/Excel: use `service="drive"` or `service="excel"` depending on whether the user wants file storage or workbook data.

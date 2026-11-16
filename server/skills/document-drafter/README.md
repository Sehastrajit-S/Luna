# Document Drafter

Draft, rewrite, outline, format, and save documents of any kind.

## What it does

Identifies the document type, audience, purpose, and tone. Fetches external facts via web research when needed and cites sources. Drafts with a clear structure: title, executive summary or opening, sections with concise headings, and action items or conclusion. Saves to the workspace in the format you request.

## When it activates

When you ask to write, rewrite, outline, format, or save a report, proposal, memo, README, policy, essay, plan, brief, or any other document.

## Example prompts

- "Draft a project proposal for a mobile app with a market analysis section"
- "Write a README for this Python library based on the code I pasted"
- "Rewrite this memo in a more formal tone"
- "Outline a go-to-market plan for a SaaS product"
- "Write a privacy policy for a personal website"

## Tools used

| Tool | Purpose |
|---|---|
| `web_research` | Fetch external facts and references for source-backed documents |
| `workspace_write` | Save the final document to the workspace |

## Output

- Brief summary of what was drafted
- Saved workspace path if a file was created
- References if external sources were used

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

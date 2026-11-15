# File Builder

Create, convert, and save files of any format inside Luna's workspace.

## What it does

Writes text files (`.txt`, `.md`, `.csv`, `.json`, `.yaml`, `.html`, `.py`, `.ts`, `.sql`, and more) and binary files (images, PDFs, archives, office binaries, audio) to the workspace. Adds provenance fields and `.source.json` sidecars when creating synthetic data. Always reports the workspace path and size after writing.

## When it activates

When you ask to create, convert, save, or inspect files in Luna's workspace.

## Example prompts

- "Save this JSON response as a workspace file called api_response.json"
- "Create a CSV with these column headers and 20 rows of sample data"
- "Convert this markdown to an HTML file and save it"
- "Write a requirements.txt for a FastAPI project"
- "Save this base64 image to the workspace as logo.png"

## Tools used

| Tool | Purpose |
|---|---|
| `workspace_write` | Write text-based files |
| `workspace_write_base64` | Write binary files from base64 input |
| `workspace_read` | Read existing files to inspect or convert |

## Rules

- Files are only written inside `data/workspace/`
- Binary formats use base64 encoding — never raw binary in text output
- Synthetic data always includes provenance metadata

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

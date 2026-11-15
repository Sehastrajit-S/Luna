# Coding Agent

Write, edit, debug, and run code inside Luna's workspace.

## What it does

Reads existing code before overwriting, thinks through the approach, uses search to locate symbols, writes clean idiomatic code, and can run safe shell commands to verify output. All file operations are scoped to `data/workspace/`.

Uses a dedicated coding model (`qwen2.5-coder:7b` by default, configurable with `coding_model` in `.env`) and has its own streaming endpoint at `POST /api/coding/stream` for IDE integrations.

## When it activates

When you ask to write, edit, review, debug, explain, or run code.

## Example prompts

- "Write a Python script that parses a CSV and outputs a bar chart"
- "Review this function and suggest improvements"
- "Debug why this regex isn't matching"
- "Add error handling to the file I just uploaded"
- "Run the tests and show me the output"

## Tools used

| Tool | Purpose |
|---|---|
| `code_read_file` | Read a workspace file (max 100 KB) |
| `code_edit_file` | Replace exact text in a file — preferred over full rewrites |
| `code_write_file` | Write or overwrite a file — used for new files only |
| `code_list_files` | List a workspace directory |
| `code_search` | Regex/text search across workspace files |
| `code_run_shell` | Run a shell command — requires user confirmation |

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

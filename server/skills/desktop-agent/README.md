# Desktop Agent

Multi-step desktop automation with confirmation gates.

## What it does

Plans before acting, keeps generated files inside Luna's workspace, asks for confirmation before clicks, typing, shell commands, destructive file operations, or external messages, and verifies the result before reporting success. All meaningful actions are recorded in the audit log.

## When it activates

When you ask for multi-step desktop work — automating a workflow, controlling applications, running system operations, or orchestrating a sequence of actions.

## Example prompts

- "Open my browser, search for the latest PyTorch release notes, and save a summary to the workspace"
- "Rename all the PNG files in my Downloads folder to include today's date"
- "Take a screenshot, annotate it, and save it to the workspace"
- "Run my build script and report the output"

## Tools used

Requires `shell` and `confirm-shell-commands` permissions. All shell commands are gated behind user confirmation before execution.

## Safety rules

- Confirmation is required before any click, keystroke, shell command, destructive file operation, or external message.
- Files are only written inside `data/workspace/`.
- Every meaningful action is written to `data/audit.log`.

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

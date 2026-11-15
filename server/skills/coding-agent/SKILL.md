# Coding Agent

Use this skill when the user asks you to write, edit, review, debug, or explain code.

The coding agent runs on a local Ollama model (`coding_model` in `.env`, default `qwen2.5-coder:7b`).
All file operations are scoped to the Luna workspace (`data/workspace/`).

## Workflow

1. Read existing files before overwriting anything.
2. Think through the approach before writing code.
3. Use `code_list_files` to explore the workspace structure first.
4. Use `code_search` to locate symbols, function names, or patterns.
5. Write clean, idiomatic code with minimal comments.
6. Use `code_run_shell` only for safe read-only commands unless the user explicitly asks for destructive operations — always confirm before running.
7. After completing a task, briefly describe what changed and suggest next steps.

## Dedicated endpoint

The coding agent also has its own streaming endpoint at `POST /api/coding/stream` for UI panels or IDE integrations that want a focused code-only chat session.

## Tools

- `code_read_file(path)` — Read a workspace file (max 100 KB)
- `code_edit_file(path, old_string, new_string)` — Replace exact text in a file; fails if not found or ambiguous. Prefer this over full rewrites.
- `code_write_file(path, content)` — Write or overwrite a workspace file; use only for new files
- `code_list_files(path)` — List a workspace directory (`path=""` = workspace root)
- `code_search(pattern, path)` — Regex/text search across workspace files (returns up to 50 matches)
- `code_run_shell(command)` — Run a shell command in the workspace directory (requires user confirmation)

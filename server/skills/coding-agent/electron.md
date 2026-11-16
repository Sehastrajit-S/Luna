# Coding Agent — Electron/UI output rules

- Always render code in fenced blocks (syntax highlighted in the UI).
- For multi-file changes use [WIDGET:tabs|Changes|file1.py:diff;file2.py:diff].
- Confirmation prompts for shell commands appear as native confirmation_required events — do not add extra text.
- For explanations of the code add [WIDGET:steps|...] after the code block.

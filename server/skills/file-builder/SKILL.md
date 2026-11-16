# File Builder

Use this skill when the user asks to create, convert, save, or inspect files in Luna's workspace.

Workflow:

1. Determine the requested path, format, and content source.
2. For text-like files, use `workspace_write`:
   - `.txt`, `.md`, `.csv`, `.tsv`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.html`, `.xml`, `.sql`, `.py`, `.js`, `.ts`, `.tsx`, `.css`.
3. For binary files, use `workspace_write_base64`:
   - Images, PDFs, archives, office binaries, model files, audio, video, or any non-text format.
4. For CSV and JSON:
   - Include headers or schema.
   - Keep values escaped correctly.
   - Avoid trailing commentary inside the file.
5. If creating synthetic data, add provenance fields and a `.source.json` sidecar when practical.
6. After writing, report the workspace path and size.

Rules:

- Never write outside Luna's workspace.
- Do not claim a file is downloaded or sourced unless it was actually downloaded or cited.
- Ask for a destination path only when the user did not provide one and there is no obvious default.

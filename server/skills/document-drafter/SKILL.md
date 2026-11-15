# Document Drafter

Use this skill when the user asks to write, rewrite, outline, format, or save a document such as a report, proposal, memo, README, policy, essay, plan, or brief.

Workflow:

1. Identify the document type, audience, purpose, tone, and requested output format.
2. If external facts are needed, use `web_research` and include references.
3. Draft with a clear structure:
   - Title.
   - Executive summary or opening.
   - Sections with concise headings.
   - Action items or conclusion when appropriate.
4. For source-backed documents, cite claims and include a references section.
5. Save requested documents with `workspace_write`. Use the user's requested extension such as `.md`, `.txt`, `.html`, `.csv`, `.json`, or `.doc.md`.
6. Do not over-format simple documents. Keep the format easy to edit.

Output format:

- Brief summary of what was drafted.
- Saved workspace path if created.
- References if sources were used.

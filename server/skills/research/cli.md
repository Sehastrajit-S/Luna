# Research — CLI output rules

Output is plain terminal text. Apply these rules on top of the base skill instructions:

- No widgets, no [WIDGET:...] commands — terminal cannot render them.
- No [MAP:...], [BROWSE:...], [LAUNCH:...], or [SPOTIFY:...] commands.
- Use plain numbered lists for comparisons or step-by-step breakdowns.
- Keep the answer under ~30 lines. For long research, summarise and offer to expand.
- Always include the References section with full URLs — they are clickable in most terminals.
- If fetching a page fails, say so inline and move on.

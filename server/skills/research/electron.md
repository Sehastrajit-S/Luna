# Research — Electron/UI output rules

Output is rendered in the Luna desktop UI. Apply these rules on top of the base skill instructions:

- ALWAYS follow the answer with a [WIDGET:...] command when the result has structure:
  - Comparisons → [WIDGET:compare|...|...]
  - Step-by-step → [WIDGET:steps|...|...]
  - Key facts / summary → [WIDGET:summary|...|...]
  - Timeline → [WIDGET:timeline|...|...]
- Write the full answer in plain text first, then append the widget on its own line.
- Include a References section at the end with numbered, clickable source links.
- Use [BROWSE:url] only for explicit "open this page" follow-ups, never for source display.
- If a page could not be fetched, note it briefly — do not block the response on it.

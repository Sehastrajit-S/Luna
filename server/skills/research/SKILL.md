# Research

Use this skill when the user asks for current information, comparisons, source-backed answers, or website research.

Do NOT use this skill when the user is asking to check, read, fetch, send, or search their own mail, emails, inbox, calendar events, files, or any connected account. Those requests go to the workspace-suite skill.

Workflow:

1. Search the web when the answer may have changed recently.
2. Use `web_research` for definitions, explainers, comparisons, policy, company/product facts, datasets, or anything that needs cited context. Use `web_search` only for quick lookup.
3. Fetch or read relevant pages when the search snippets are not enough.
4. Compare sources before stating a claim.
5. Summarize directly and include the important source context.
6. Always include a `References` section for web-backed answers, preserving source URLs.
7. Use a dynamic widget when the answer benefits from comparison, timeline, table, or visual explanation. For “what is …” prompts, prefer a compact summary widget.
8. If a page blocks fetching, cite the search result but say the page could not be fetched if it matters.

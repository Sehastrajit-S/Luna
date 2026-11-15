# Research

Web research with source comparison and cited answers.

## What it does

Searches the web, fetches relevant pages, compares sources, and returns a direct answer with a references section. Uses dynamic widgets when the answer benefits from a comparison table, timeline, or visual summary.

## When it activates

Only when your message starts with `/research`. Ordinary questions, even ones about current events or asking for sources, get a normal answer (with a quick web search if needed) and never trigger this skill.

## Example prompts

- "/research differences between GPT-4o and Claude Opus"
- "/research the latest on the EU AI Act"
- "/research compare the top three open-source embedding models"
- "/research who founded Mistral AI and when"

## Tools used

| Tool | Purpose |
|---|---|
| `web_research` | Deep research with source comparison — used for facts, explainers, comparisons |
| `web_search` | Quick lookup when a snippet is enough |
| `web_fetch` | Fetch the full content of a URL when snippets aren't enough |

## Output

Answers include a `References` section with source URLs. Comparisons and timelines use dynamic widgets when running in the desktop app.

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

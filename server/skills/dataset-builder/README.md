# Dataset Builder

Fetch real datasets from primary sources or generate synthetic data with provenance metadata.

## What it does

Searches for datasets from government, scientific, and ML repositories. Cites candidate sources before downloading. Downloads files directly to the workspace with a `.source.json` sidecar that records origin, license, and column definitions. If no real dataset exists, generates synthetic data and clearly labels it as such.

## When it activates

When you ask for a dataset, training data, CSV/JSON/Parquet files, data collection, or synthetic data generation.

## Example prompts

- "Get me a weather dataset for New York from NOAA for the past 10 years"
- "Find a Titanic survival dataset and save it to the workspace as CSV"
- "Generate a synthetic e-commerce transaction dataset with 10,000 rows"
- "Find a Hugging Face dataset for sentiment analysis"

## Tools used

| Tool | Purpose |
|---|---|
| `web_research` | Find and evaluate dataset sources |
| `web_search` | Quick lookup for dataset pages |
| `web_fetch` | Inspect dataset pages and documentation |
| `workspace_write` | Save synthetic data and sidecar metadata |

## Output

- Workspace path of the saved file
- Source references (title, publisher, URL, license)
- Whether the data is real or synthetic
- Path to the `.source.json` sidecar

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |

# Dataset Builder

Use this skill when the user asks for a dataset, training data, CSV/JSON/parquet-style files, source-backed data collection, or synthetic data.

Workflow:

1. Clarify the target only when required: prediction task, geography, date range, granularity, file format, and destination path.
2. Search real sources first with `dataset_search`. Prefer primary or reputable repositories:
   - Government and scientific sources: NOAA/NCEI, NASA, USGS, data.gov, Census, World Bank, OECD.
   - ML repositories: UCI Machine Learning Repository, Hugging Face Datasets, Kaggle dataset pages.
   - Domain-specific official publishers before blogs or mirrors.
3. Cite candidate sources before downloading. Include title, publisher/site, URL, license or access note when visible, and why it fits.
4. Download only after choosing a credible source. Use `web_download_file(url,path)` for direct HTTP(S) files and save into Luna's workspace path requested by the user. A `.source.json` sidecar is written automatically.
5. If the source is Kaggle or another gated provider and no direct file URL is available, cite the dataset page and tell the user credentials or manual export are needed. Do not fake a download.
6. If no real dataset exists or the user asks for generated data, create synthetic data with `workspace_write`.
7. Synthetic data rules:
   - Say clearly that it is synthetic before creating it.
   - Include `is_synthetic`, `source_reference`, and `derivation_note` columns when practical.
   - Add a companion `.source.json` that explains every column, unit, generation rule, random seed if used, and citations for assumptions.
   - Never present synthetic rows as real observations.
8. For model-training datasets, include a short data dictionary and suggested target column. For weather prediction, prefer real historical weather sources such as NOAA/NCEI before Kaggle mirrors.

Output format:

- Confirm the saved workspace path.
- Show the source references.
- Mention whether the file is real downloaded data or synthetic.
- Mention the sidecar metadata path.

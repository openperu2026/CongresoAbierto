# Backend Module

This folder contains the full OpenPeru data pipeline and domain definitions.

## What is here

- `__main__.py`: CLI entrypoint (`python -m backend`).
- `config.py`: environment settings, DB URLs, log helpers, project paths.
- `__init__.py`: enums, parsing helpers, and domain normalization utilities.
- `scrapers/`: raw data extraction from external sources.
- `process/`: transforms raw records into validated Pydantic schemas.
- `database/`: SQLAlchemy models, DB bootstrap, CRUD helpers, and orchestrator.

## Main workflow

1. Scrape raw sources into the raw DB (`data/raw/OpenPeruRaw.db` by default).
2. Process raw rows into clean entities in the processed DB (`data/processed/OpenPeru.db`).
3. Use orchestration flags to run all targets or selected targets only.

## Run

```bash
uv run python -m backend --help
```

Examples:

```bash
# Process pending raw data only
uv run python -m backend

# Scrape + process everything
uv run python -m backend --scrape

# Scrape/process only motions
uv run python -m backend --scrape --only-motions
```

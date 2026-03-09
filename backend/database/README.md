# Database Module

This module defines raw/clean DB schemas and orchestrates persistence.

## Files

- `raw_models.py`: raw ingestion tables (`Raw*`), including tracking fields.
- `models.py`: clean SQLAlchemy models for normalized entities.
- `build_db.py`: create/update SQLite DBs and ensure tracking columns exist.
- `orchestrator.py`: end-to-end ETL runner (scrape + process + load).
- `crud/`: DB helper functions for upserts and lookups used by the orchestrator.
  - `pipeline_core.py`
  - `pipeline_bills.py`
  - `pipeline_motions.py`

## Databases

Configured in `backend/config.py`:

- Raw DB: `settings.RAW_DB_URL` (default `data/raw/OpenPeruRaw.db`)
- Clean DB: `settings.DB_URL` (default `data/processed/OpenPeru.db`)

## Create DBs

```bash
uv run python -m backend.database.build_db
```

## Run orchestrator

```bash
uv run python -m backend --help
```

Examples:

```bash
# Process only (no scrape)
uv run python -m backend

# Scrape + process only bills
uv run python -m backend --scrape --only-bills

# Weekly refresh window = 10 days
uv run python -m backend --scrape --weekly-days 10
```

## Raw tracking semantics

For each latest raw record:

- first version: `changed=True`, `processed=False`
- unchanged new version: `changed=False`, `processed=True`
- changed new version: `changed=True`, `processed=False`

This allows process stages to focus on records that still need clean-table updates.

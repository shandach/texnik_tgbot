# texnik_tgbot backend

## Run locally

### 1) Minimal mode (offline / without external DB)

```bash
python -m pip install -e .
python -m unittest
```

This validates the service logic and API layer using the local FastAPI shim and in-memory repository.

### 2) API server mode (recommended for manual API testing)

```bash
python -m pip install -e .[prod]
uvicorn app.main:app --reload --port 8000
```

Or use one command helper script:

```bash
./scripts/run_api.sh
```

Then open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

> Note: `uvicorn` is included in the `prod` extra, so `pip install -e .` (without `[prod]`) is not enough to start the HTTP server.

## Offline bootstrap (proxy-restricted environments)

```bash
./scripts/bootstrap_offline.sh
```

This script:
- installs editable package in offline-safe mode (`--no-build-isolation`),
- falls back to `setup.py develop` if needed,
- runs syntax compile check and `app.main` import smoke test.

## Repository modes

- If `DATABASE_URL` is set, app uses PostgreSQL repository (`app/postgres_repository.py`).
- If `DATABASE_URL` is empty, app falls back to in-memory repository for quick flow tests.

## Required env

```env
TELEGRAM_BOT_TOKEN=...
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/texnik_tgbot
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/texnik_tgbot_test
```

## PostgreSQL integration tests

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/texnik_tgbot_test \
python -m unittest tests.test_postgres_repository_integration -v
```

If `TEST_DATABASE_URL` is missing (or `sqlalchemy` is unavailable), these tests are skipped automatically.

One-command Docker profile run:

```bash
./scripts/run_postgres_tests.sh
```

This script starts `postgres-test` via Docker Compose profile, applies `db/schema.sql`, runs repository integration tests, then tears down the container.
If Docker is unavailable, it prints a direct `TEST_DATABASE_URL` fallback command (and can run directly if `TEST_DATABASE_URL` is already set).


## Stage E outbox worker

Run outbox sync worker (current adapter writes to CSV journal):

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/texnik_tgbot python scripts/sheet_sync_worker.py
```

Optional env:
- `SHEET_JOURNAL_FILE` (default `sheet_journal.csv`)
- `SHEET_SYNC_BATCH_SIZE` (default `50`)

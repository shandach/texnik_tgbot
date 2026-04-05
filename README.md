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

On macOS where `python` alias may be missing, the script automatically falls back to `python3`.

If you still see `python: command not found`, your local copy is likely outdated. Update and verify:

```bash
git pull
sed -n '1,40p' scripts/run_api.sh
```

The updated script must contain a `python3` fallback block and print `Using Python interpreter: ...` on startup.

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

## Minimal Telegram bot runner (long polling)

This repository now includes a lightweight Telegram runner that bridges Telegram updates to backend API endpoint `/v1/bot/session/start`.

1) Start backend API:

```bash
./scripts/run_api.sh
```

2) In another terminal, run bot runner:

```bash
TELEGRAM_BOT_TOKEN=your_token \
BACKEND_BASE_URL=http://127.0.0.1:8000 \
python3 scripts/telegram_bot_runner.py
```

Alternative (recommended): put values into `.env` and run without inline env assignment:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
BACKEND_BASE_URL=http://127.0.0.1:8000
```

```bash
python3 scripts/telegram_bot_runner.py
```

Supported flow:
- `/start` -> bot asks for BXM code
- user sends 5-digit BXM
- bot calls backend session-start endpoint and returns localized backend message.

Troubleshooting:
- `RuntimeError: TELEGRAM_BOT_TOKEN is required`:
  - your env variable is not set in current shell session.
  - ensure `.env` is in project root (`texnik_tgbot/.env`) and has exact key `TELEGRAM_BOT_TOKEN=...` (also supports `export TELEGRAM_BOT_TOKEN=...`).
  - use one-line launch:
    `TELEGRAM_BOT_TOKEN=... BACKEND_BASE_URL=http://127.0.0.1:8000 python3 scripts/telegram_bot_runner.py`
- `SSL: CERTIFICATE_VERIFY_FAILED` to `api.telegram.org`:
  - set `SSL_CERT_FILE=/path/to/corporate-ca.pem`, or
  - for local debug only: `TELEGRAM_INSECURE_SKIP_VERIFY=1`.
- bot is running but does not answer:
  - on startup runner must print `Telegram bot connected as @...`; if not, token/network issue.
  - make sure you write to the exact bot from `@username` shown by runner.
  - send `/start` in private chat first (runner handles BXM flow only after `/start`).
  - stopping with `Ctrl+C` is normal and now exits with a short message (without traceback).

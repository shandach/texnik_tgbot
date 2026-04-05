# Stage E — Google Sheets outbox/retry

Implemented approach:

- Added `sheet_sync_outbox` table to persist sync tasks per request.
- Outbox row is upserted whenever request is created or reviewer updates request status.
- Worker script `scripts/sheet_sync_worker.py` processes pending/failed rows in batches.
- On success: marks row as `synced` and upserts one journal row by `request_id` (current implementation writes to CSV file as adapter placeholder).
- On failure: increments attempts, stores error and schedules retry (`next_retry_at +5 minutes`).

Current adapter:
- `sheet_journal.csv` local file (placeholder transport).
- Can be replaced with real Google Sheets API writer without changing outbox model.

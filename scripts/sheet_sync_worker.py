#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
OUTPUT_CSV = os.getenv("SHEET_JOURNAL_FILE", "sheet_journal.csv")
BATCH_SIZE = int(os.getenv("SHEET_SYNC_BATCH_SIZE", "50"))

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is required")

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)


def write_row(payload: dict) -> None:
    fieldnames = ["timestamp", "request_id", "request_number", "fio", "bxm_code", "request_type", "status", "final_decision"]
    rows: list[dict] = []
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            rows = list(reader)

    request_id = str(payload["request_id"])
    replaced = False
    for idx, row in enumerate(rows):
        if row.get("request_id") == request_id:
            rows[idx] = {k: str(payload.get(k, "")) for k in fieldnames}
            replaced = True
            break
    if not replaced:
        rows.append({k: str(payload.get(k, "")) for k in fieldnames})

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


with engine.begin() as conn:
    rows = conn.execute(
        text(
            """
            SELECT id, request_id, payload_json
            FROM sheet_sync_outbox
            WHERE status IN ('pending', 'failed')
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at ASC
            LIMIT :limit
            """
        ),
        {"limit": BATCH_SIZE},
    ).mappings().all()

for row in rows:
    outbox_id = row["id"]
    try:
        payload = row["payload_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        write_row(payload)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sheet_sync_outbox
                    SET status='synced', synced_at=NOW(), updated_at=NOW(), attempts=attempts+1, last_error=NULL
                    WHERE id=:id
                    """
                ),
                {"id": outbox_id},
            )
    except Exception as exc:  # noqa: BLE001
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sheet_sync_outbox
                    SET status='failed', updated_at=NOW(), attempts=attempts+1,
                        last_error=:err, next_retry_at=:retry
                    WHERE id=:id
                    """
                ),
                {
                    "id": outbox_id,
                    "err": str(exc)[:1000],
                    "retry": datetime.utcnow() + timedelta(minutes=5),
                },
            )

print(f"processed={len(rows)}")

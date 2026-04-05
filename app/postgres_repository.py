from __future__ import annotations

from datetime import datetime
import hashlib

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.repository import Branch, CommentRecord, Inventory, RequestRecord, SheetSyncRecord, TelegramAccount, UserRecord


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def get_or_create_telegram_account(self, telegram_user_id: int) -> TelegramAccount:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, telegram_user_id, first_seen_at, last_seen_at
                    FROM telegram_accounts
                    WHERE telegram_user_id = :telegram_user_id
                    """
                ),
                {"telegram_user_id": telegram_user_id},
            ).mappings().first()

            if row:
                conn.execute(
                    text(
                        """
                        UPDATE telegram_accounts
                        SET last_seen_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"id": row["id"]},
                )
                return TelegramAccount(
                    id=row["id"],
                    telegram_user_id=row["telegram_user_id"],
                    first_seen_at=row["first_seen_at"],
                    last_seen_at=datetime.utcnow(),
                )

            inserted = conn.execute(
                text(
                    """
                    INSERT INTO telegram_accounts (telegram_user_id)
                    VALUES (:telegram_user_id)
                    RETURNING id, telegram_user_id, first_seen_at, last_seen_at
                    """
                ),
                {"telegram_user_id": telegram_user_id},
            ).mappings().first()

            return TelegramAccount(
                id=inserted["id"],
                telegram_user_id=inserted["telegram_user_id"],
                first_seen_at=inserted["first_seen_at"],
                last_seen_at=inserted["last_seen_at"],
            )

    def get_branch_by_bhm(self, bxm_code: str) -> Branch | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, bhm_code, branch_name, region_name, city_name
                         , COALESCE(street_name, '') AS street_name
                    FROM bhm_branches
                    WHERE bhm_code = :bxm_code
                    """
                ),
                {"bxm_code": bxm_code},
            ).mappings().first()

            if not row:
                return None

            return Branch(
                id=row["id"],
                bhm_code=row["bhm_code"],
                branch_name=row["branch_name"],
                region_name=row["region_name"],
                city_name=row["city_name"],
                street_name=row["street_name"],
            )

    def get_branch_by_id(self, branch_id: int) -> Branch | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, bhm_code, branch_name, region_name, city_name, COALESCE(street_name, '') AS street_name
                    FROM bhm_branches
                    WHERE id = :branch_id
                    """
                ),
                {"branch_id": branch_id},
            ).mappings().first()
            if not row:
                return None
            return Branch(
                id=row["id"],
                bhm_code=row["bhm_code"],
                branch_name=row["branch_name"],
                region_name=row["region_name"],
                city_name=row["city_name"],
                street_name=row["street_name"],
            )

    def get_inventory(self, inventory_code: str) -> Inventory | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, inventory_code, branch_id, equipment_type, issue_year, status
                    FROM inventory
                    WHERE inventory_code = :inventory_code
                    """
                ),
                {"inventory_code": inventory_code},
            ).mappings().first()

            if not row:
                return None

            return Inventory(
                id=row["id"],
                inventory_code=row["inventory_code"],
                branch_id=row["branch_id"],
                equipment_type=row["equipment_type"],
                issue_year=row["issue_year"],
                status=row["status"],
            )

    def list_inventory(self, branch_id: int) -> list[Inventory]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, inventory_code, branch_id, equipment_type, issue_year, status
                    FROM inventory
                    WHERE branch_id = :branch_id
                    ORDER BY inventory_code ASC
                    """
                ),
                {"branch_id": branch_id},
            ).mappings().all()
            return [
                Inventory(
                    id=row["id"],
                    inventory_code=row["inventory_code"],
                    branch_id=row["branch_id"],
                    equipment_type=row["equipment_type"],
                    issue_year=row["issue_year"],
                    status=row["status"],
                )
                for row in rows
            ]

    def update_inventory_status(self, inventory_code: str, status: str) -> Inventory | None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE inventory SET status = :status WHERE inventory_code = :inventory_code"),
                {"inventory_code": inventory_code, "status": status},
            )
        return self.get_inventory(inventory_code)

    def has_open_request_for_inventory(self, inventory_code: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM requests
                    WHERE inventory_code_snapshot = :inventory_code
                      AND status IN ('new', 'in_progress')
                    LIMIT 1
                    """
                ),
                {"inventory_code": inventory_code},
            ).first()
            return row is not None

    def next_request_number(self) -> str:
        with self.engine.begin() as conn:
            next_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM requests")).scalar_one()
        year = datetime.utcnow().year
        return f"REQ-{year}-{int(next_id):06d}"

    def create_request(self, record: RequestRecord) -> RequestRecord:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO requests (
                        request_number,
                        telegram_account_id,
                        employee_fio_snapshot,
                        employee_fio_normalized_basic,
                        employee_fio_normalized_translit,
                        employee_position_snapshot,
                        branch_id,
                        bhm_code_snapshot,
                        branch_name_snapshot,
                        request_type,
                        equipment_type,
                        inventory_id,
                        inventory_code_snapshot,
                        reason_text,
                        problem_text,
                        status,
                        final_decision
                    )
                    VALUES (
                        :request_number,
                        :telegram_account_id,
                        :employee_fio_snapshot,
                        :employee_fio_normalized_basic,
                        :employee_fio_normalized_translit,
                        :employee_position_snapshot,
                        :branch_id,
                        :bhm_code_snapshot,
                        :branch_name_snapshot,
                        :request_type,
                        :equipment_type,
                        :inventory_id,
                        :inventory_code_snapshot,
                        :reason_text,
                        :problem_text,
                        :status,
                        :final_decision
                    )
                    RETURNING id, created_at
                    """
                ),
                {
                    "request_number": record.request_number,
                    "telegram_account_id": record.telegram_account_id,
                    "employee_fio_snapshot": record.employee_fio_snapshot,
                    "employee_fio_normalized_basic": record.employee_fio_normalized_basic,
                    "employee_fio_normalized_translit": record.employee_fio_normalized_translit,
                    "employee_position_snapshot": record.employee_position_snapshot,
                    "branch_id": record.branch_id,
                    "bhm_code_snapshot": record.bhm_code_snapshot,
                    "branch_name_snapshot": record.branch_name_snapshot,
                    "request_type": record.request_type,
                    "equipment_type": record.equipment_type,
                    "inventory_id": record.inventory_id,
                    "inventory_code_snapshot": record.inventory_code_snapshot,
                    "reason_text": record.reason_text,
                    "problem_text": record.problem_text,
                    "status": record.status,
                    "final_decision": record.final_decision,
                },
            ).mappings().first()

            record.id = row["id"]
            record.created_at = row["created_at"]
            record.updated_at = row["created_at"]
            return record

    def list_requests_by_tg(self, telegram_user_id: int) -> list[RequestRecord]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT r.*
                    FROM requests r
                    JOIN telegram_accounts ta ON ta.id = r.telegram_account_id
                    WHERE ta.telegram_user_id = :telegram_user_id
                    ORDER BY r.created_at DESC
                    """
                ),
                {"telegram_user_id": telegram_user_id},
            ).mappings().all()

            return [
                RequestRecord(
                    id=row["id"],
                    request_number=row["request_number"],
                    telegram_account_id=row["telegram_account_id"],
                    employee_fio_snapshot=row["employee_fio_snapshot"],
                    employee_fio_normalized_basic=row["employee_fio_normalized_basic"],
                    employee_fio_normalized_translit=row["employee_fio_normalized_translit"],
                    employee_position_snapshot=row["employee_position_snapshot"],
                    branch_id=row["branch_id"],
                    bhm_code_snapshot=row["bhm_code_snapshot"],
                    branch_name_snapshot=row["branch_name_snapshot"],
                    request_type=row["request_type"],
                    equipment_type=row["equipment_type"],
                    inventory_id=row["inventory_id"],
                    inventory_code_snapshot=row["inventory_code_snapshot"],
                    reason_text=row["reason_text"],
                    problem_text=row["problem_text"],
                    status=row["status"],
                    final_decision=row["final_decision"],
                    reject_reason=row["reject_reason"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    closed_at=row["closed_at"],
                )
                for row in rows
            ]

    def list_requests(self) -> list[RequestRecord]:
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT * FROM requests ORDER BY created_at DESC")).mappings().all()
            return [
                RequestRecord(
                    id=row["id"],
                    request_number=row["request_number"],
                    telegram_account_id=row["telegram_account_id"],
                    employee_fio_snapshot=row["employee_fio_snapshot"],
                    employee_fio_normalized_basic=row["employee_fio_normalized_basic"],
                    employee_fio_normalized_translit=row["employee_fio_normalized_translit"],
                    employee_position_snapshot=row["employee_position_snapshot"],
                    branch_id=row["branch_id"],
                    bhm_code_snapshot=row["bhm_code_snapshot"],
                    branch_name_snapshot=row["branch_name_snapshot"],
                    request_type=row["request_type"],
                    equipment_type=row["equipment_type"],
                    inventory_id=row["inventory_id"],
                    inventory_code_snapshot=row["inventory_code_snapshot"],
                    reason_text=row["reason_text"],
                    problem_text=row["problem_text"],
                    status=row["status"],
                    final_decision=row["final_decision"],
                    reject_reason=row["reject_reason"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    closed_at=row["closed_at"],
                )
                for row in rows
            ]

    def list_regions(self) -> list[str]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text("SELECT DISTINCT region_name FROM bhm_branches WHERE region_name IS NOT NULL ORDER BY region_name ASC")
            ).all()
            return [row[0] for row in rows]

    def list_streets(self, region_name: str) -> list[str]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT street_name
                    FROM bhm_branches
                    WHERE region_name = :region_name AND street_name IS NOT NULL AND street_name <> ''
                    ORDER BY street_name ASC
                    """
                ),
                {"region_name": region_name},
            ).all()
            return [row[0] for row in rows]

    def list_branches(self, region_name: str, street_name: str) -> list[Branch]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, bhm_code, branch_name, region_name, city_name, COALESCE(street_name, '') AS street_name
                    FROM bhm_branches
                    WHERE region_name = :region_name AND street_name = :street_name
                    ORDER BY bhm_code ASC
                    """
                ),
                {"region_name": region_name, "street_name": street_name},
            ).mappings().all()
            return [
                Branch(
                    id=row["id"],
                    bhm_code=row["bhm_code"],
                    branch_name=row["branch_name"],
                    region_name=row["region_name"],
                    city_name=row["city_name"],
                    street_name=row["street_name"],
                )
                for row in rows
            ]

    def get_request_by_id(self, request_id: int) -> RequestRecord | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM requests WHERE id = :request_id"),
                {"request_id": request_id},
            ).mappings().first()
            if not row:
                return None
            return RequestRecord(
                id=row["id"],
                request_number=row["request_number"],
                telegram_account_id=row["telegram_account_id"],
                employee_fio_snapshot=row["employee_fio_snapshot"],
                employee_fio_normalized_basic=row["employee_fio_normalized_basic"],
                employee_fio_normalized_translit=row["employee_fio_normalized_translit"],
                employee_position_snapshot=row["employee_position_snapshot"],
                branch_id=row["branch_id"],
                bhm_code_snapshot=row["bhm_code_snapshot"],
                branch_name_snapshot=row["branch_name_snapshot"],
                request_type=row["request_type"],
                equipment_type=row["equipment_type"],
                inventory_id=row["inventory_id"],
                inventory_code_snapshot=row["inventory_code_snapshot"],
                reason_text=row["reason_text"],
                problem_text=row["problem_text"],
                status=row["status"],
                final_decision=row["final_decision"],
                reject_reason=row["reject_reason"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                closed_at=row["closed_at"],
            )

    def update_request(self, request_id: int, **fields) -> RequestRecord | None:
        if not fields:
            return self.get_request_by_id(request_id)
        set_clause = ", ".join([f"{key} = :{key}" for key in fields.keys()])
        payload = {"request_id": request_id, **fields}
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE requests SET {set_clause}, updated_at = NOW() WHERE id = :request_id"),
                payload,
            )
        return self.get_request_by_id(request_id)

    def list_comments(self, request_id: int) -> list[CommentRecord]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text("SELECT * FROM request_comments WHERE request_id = :request_id ORDER BY created_at ASC"),
                {"request_id": request_id},
            ).mappings().all()
            return [
                CommentRecord(
                    id=row["id"],
                    request_id=row["request_id"],
                    author_name=row["author_name"],
                    comment_text=row["comment_text"],
                    is_edited=row["is_edited"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def create_comment(self, request_id: int, author_name: str, comment_text: str) -> CommentRecord:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO request_comments (request_id, author_name, comment_text)
                    VALUES (:request_id, :author_name, :comment_text)
                    RETURNING id, request_id, author_name, comment_text, is_edited, created_at, updated_at
                    """
                ),
                {"request_id": request_id, "author_name": author_name, "comment_text": comment_text},
            ).mappings().first()
            return CommentRecord(
                id=row["id"],
                request_id=row["request_id"],
                author_name=row["author_name"],
                comment_text=row["comment_text"],
                is_edited=row["is_edited"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def update_comment(self, comment_id: int, comment_text: str) -> CommentRecord | None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE request_comments
                    SET comment_text = :comment_text, is_edited = TRUE, updated_at = NOW()
                    WHERE id = :comment_id
                    """
                ),
                {"comment_id": comment_id, "comment_text": comment_text},
            )
        return self.get_comment_by_id(comment_id)

    def get_comment_by_id(self, comment_id: int) -> CommentRecord | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM request_comments WHERE id = :comment_id"),
                {"comment_id": comment_id},
            ).mappings().first()
            if not row:
                return None
            return CommentRecord(
                id=row["id"],
                request_id=row["request_id"],
                author_name=row["author_name"],
                comment_text=row["comment_text"],
                is_edited=row["is_edited"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def upsert_sheet_sync(self, request_id: int, payload_json: str) -> SheetSyncRecord:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO sheet_sync_outbox (request_id, payload_json, status, attempts)
                    VALUES (:request_id, CAST(:payload_json AS JSONB), 'pending', 0)
                    ON CONFLICT (request_id) DO UPDATE SET
                        payload_json = EXCLUDED.payload_json,
                        status = 'pending',
                        updated_at = NOW(),
                        last_error = NULL,
                        next_retry_at = NULL
                    RETURNING id, request_id, payload_json::text AS payload_json, status, attempts, last_error, next_retry_at, synced_at, created_at, updated_at
                    """
                ),
                {"request_id": request_id, "payload_json": payload_json},
            ).mappings().first()
            return SheetSyncRecord(
                id=row["id"],
                request_id=row["request_id"],
                payload_json=row["payload_json"],
                status=row["status"],
                attempts=row["attempts"],
                last_error=row["last_error"],
                next_retry_at=row["next_retry_at"],
                synced_at=row["synced_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def authenticate_user(self, login: str, password_plain: str) -> UserRecord | None:
        password_hash = hashlib.sha256(password_plain.encode()).hexdigest()
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, login, password_hash, role, full_name, is_active
                    FROM users
                    WHERE login = :login
                    """
                ),
                {"login": login},
            ).mappings().first()
            if not row or not row["is_active"]:
                return None
            if row["password_hash"] != password_hash:
                return None
            return UserRecord(
                id=row["id"],
                login=row["login"],
                password_hash=row["password_hash"],
                role=row["role"],
                full_name=row["full_name"],
                is_active=row["is_active"],
            )

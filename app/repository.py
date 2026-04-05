from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from itertools import count


@dataclass
class Branch:
    id: int
    bhm_code: str
    branch_name: str
    region_name: str
    city_name: str
    street_name: str = ""


@dataclass
class TelegramAccount:
    id: int
    telegram_user_id: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class Inventory:
    id: int
    inventory_code: str
    branch_id: int
    equipment_type: str
    issue_year: int
    status: str = "active"


@dataclass
class RequestRecord:
    id: int
    request_number: str
    telegram_account_id: int
    employee_fio_snapshot: str
    employee_fio_normalized_basic: str
    employee_fio_normalized_translit: str
    employee_position_snapshot: str
    branch_id: int
    bhm_code_snapshot: str
    branch_name_snapshot: str
    request_type: str
    equipment_type: str
    inventory_id: int | None
    inventory_code_snapshot: str | None
    reason_text: str | None
    problem_text: str | None
    status: str = "new"
    final_decision: str = "pending"
    reject_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None


@dataclass
class CommentRecord:
    id: int
    request_id: int
    author_name: str
    comment_text: str
    is_edited: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SheetSyncRecord:
    id: int
    request_id: int
    payload_json: str
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    next_retry_at: datetime | None = None
    synced_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserRecord:
    id: int
    login: str
    password_hash: str
    role: str
    full_name: str
    is_active: bool = True


class InMemoryRepository:
    def __init__(self) -> None:
        self._account_seq = count(1)
        self._request_seq = count(1)
        self._request_no_seq = count(1)
        self._comment_seq = count(1)
        self._sheet_sync_seq = count(1)

        self.branches: dict[str, Branch] = {
            "12345": Branch(
                id=1,
                bhm_code="12345",
                branch_name="Toshkent Markaz",
                region_name="Toshkent",
                city_name="Toshkent shahri",
                street_name="Amir Temur",
            ),
            "11673": Branch(
                id=2,
                bhm_code="11673",
                branch_name="Qatartol BXM",
                region_name="Ташкент",
                city_name="Ташкент",
                street_name="Чиланзар",
            ),
        }
        self.accounts_by_tg: dict[int, TelegramAccount] = {}
        self.inventory_by_code: dict[str, Inventory] = {
            "PC-0001": Inventory(id=1, inventory_code="PC-0001", branch_id=1, equipment_type="computer", issue_year=2021),
            "PR-0001": Inventory(id=2, inventory_code="PR-0001", branch_id=1, equipment_type="printer", issue_year=2025),
            "5050801": Inventory(id=3, inventory_code="5050801", branch_id=2, equipment_type="computer", issue_year=2023),
            "6050802": Inventory(id=4, inventory_code="6050802", branch_id=2, equipment_type="printer", issue_year=2024),
        }
        self.requests: list[RequestRecord] = []
        self.comments: list[CommentRecord] = []
        self.sheet_sync_queue: list[SheetSyncRecord] = []
        self.users: dict[str, UserRecord] = {
            "reviewer": UserRecord(
                id=1,
                login="reviewer",
                password_hash=hashlib.sha256("reviewer123".encode()).hexdigest(),
                role="reviewer",
                full_name="Default Reviewer",
                is_active=True,
            ),
            "developer": UserRecord(
                id=2,
                login="developer",
                password_hash=hashlib.sha256("developer123".encode()).hexdigest(),
                role="developer",
                full_name="Default Developer",
                is_active=True,
            ),
        }

    def get_or_create_telegram_account(self, telegram_user_id: int) -> TelegramAccount:
        account = self.accounts_by_tg.get(telegram_user_id)
        if account:
            account.last_seen_at = datetime.utcnow()
            return account
        account = TelegramAccount(
            id=next(self._account_seq),
            telegram_user_id=telegram_user_id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        self.accounts_by_tg[telegram_user_id] = account
        return account

    def get_branch_by_bhm(self, bxm_code: str) -> Branch | None:
        return self.branches.get(bxm_code)

    def get_branch_by_id(self, branch_id: int) -> Branch | None:
        for branch in self.branches.values():
            if branch.id == branch_id:
                return branch
        return None

    def get_inventory(self, inventory_code: str) -> Inventory | None:
        return self.inventory_by_code.get(inventory_code)

    def list_inventory(self, branch_id: int) -> list[Inventory]:
        return [inv for inv in self.inventory_by_code.values() if inv.branch_id == branch_id]

    def update_inventory_status(self, inventory_code: str, status: str) -> Inventory | None:
        inv = self.inventory_by_code.get(inventory_code)
        if not inv:
            return None
        inv.status = status
        return inv

    def has_open_request_for_inventory(self, inventory_code: str) -> bool:
        return any(
            req.inventory_code_snapshot == inventory_code and req.status in {"new", "in_progress"}
            for req in self.requests
        )

    def next_request_number(self) -> str:
        serial = next(self._request_no_seq)
        year = datetime.utcnow().year
        return f"REQ-{year}-{serial:06d}"

    def create_request(self, record: RequestRecord) -> RequestRecord:
        record.id = next(self._request_seq)
        self.requests.append(record)
        return record

    def list_requests_by_tg(self, telegram_user_id: int) -> list[RequestRecord]:
        account = self.accounts_by_tg.get(telegram_user_id)
        if not account:
            return []
        return [req for req in self.requests if req.telegram_account_id == account.id]

    def list_requests(self) -> list[RequestRecord]:
        return list(self.requests)

    def list_regions(self) -> list[str]:
        return sorted({b.region_name for b in self.branches.values()})

    def list_streets(self, region_name: str) -> list[str]:
        return sorted({b.street_name for b in self.branches.values() if b.region_name == region_name and b.street_name})

    def list_branches(self, region_name: str, street_name: str) -> list[Branch]:
        return [
            b
            for b in self.branches.values()
            if b.region_name == region_name and b.street_name == street_name
        ]

    def get_request_by_id(self, request_id: int) -> RequestRecord | None:
        for req in self.requests:
            if req.id == request_id:
                return req
        return None

    def update_request(self, request_id: int, **fields) -> RequestRecord | None:
        req = self.get_request_by_id(request_id)
        if not req:
            return None
        for key, value in fields.items():
            setattr(req, key, value)
        req.updated_at = datetime.utcnow()
        return req

    def list_comments(self, request_id: int) -> list[CommentRecord]:
        return [c for c in self.comments if c.request_id == request_id]

    def create_comment(self, request_id: int, author_name: str, comment_text: str) -> CommentRecord:
        comment = CommentRecord(
            id=next(self._comment_seq),
            request_id=request_id,
            author_name=author_name,
            comment_text=comment_text,
        )
        self.comments.append(comment)
        return comment

    def update_comment(self, comment_id: int, comment_text: str) -> CommentRecord | None:
        for comment in self.comments:
            if comment.id == comment_id:
                comment.comment_text = comment_text
                comment.is_edited = True
                comment.updated_at = datetime.utcnow()
                return comment
        return None

    def get_comment_by_id(self, comment_id: int) -> CommentRecord | None:
        for comment in self.comments:
            if comment.id == comment_id:
                return comment
        return None

    def upsert_sheet_sync(self, request_id: int, payload_json: str) -> SheetSyncRecord:
        existing = None
        for item in self.sheet_sync_queue:
            if item.request_id == request_id:
                existing = item
                break
        if existing:
            existing.payload_json = payload_json
            existing.status = "pending"
            existing.updated_at = datetime.utcnow()
            existing.last_error = None
            existing.next_retry_at = None
            return existing
        record = SheetSyncRecord(
            id=next(self._sheet_sync_seq),
            request_id=request_id,
            payload_json=payload_json,
        )
        self.sheet_sync_queue.append(record)
        return record

    def authenticate_user(self, login: str, password_plain: str) -> UserRecord | None:
        user = self.users.get(login)
        if not user or not user.is_active:
            return None
        hashed = hashlib.sha256(password_plain.encode()).hexdigest()
        if hashed != user.password_hash:
            return None
        return user


class RepositoryProtocol:
    def get_or_create_telegram_account(self, telegram_user_id: int) -> TelegramAccount: ...
    def get_branch_by_bhm(self, bxm_code: str) -> Branch | None: ...
    def get_branch_by_id(self, branch_id: int) -> Branch | None: ...
    def get_inventory(self, inventory_code: str) -> Inventory | None: ...
    def list_inventory(self, branch_id: int) -> list[Inventory]: ...
    def update_inventory_status(self, inventory_code: str, status: str) -> Inventory | None: ...
    def has_open_request_for_inventory(self, inventory_code: str) -> bool: ...
    def next_request_number(self) -> str: ...
    def create_request(self, record: RequestRecord) -> RequestRecord: ...
    def list_requests_by_tg(self, telegram_user_id: int) -> list[RequestRecord]: ...
    def list_requests(self) -> list[RequestRecord]: ...
    def list_regions(self) -> list[str]: ...
    def list_streets(self, region_name: str) -> list[str]: ...
    def list_branches(self, region_name: str, street_name: str) -> list[Branch]: ...
    def get_request_by_id(self, request_id: int) -> RequestRecord | None: ...
    def update_request(self, request_id: int, **fields) -> RequestRecord | None: ...
    def list_comments(self, request_id: int) -> list[CommentRecord]: ...
    def create_comment(self, request_id: int, author_name: str, comment_text: str) -> CommentRecord: ...
    def update_comment(self, comment_id: int, comment_text: str) -> CommentRecord | None: ...
    def get_comment_by_id(self, comment_id: int) -> CommentRecord | None: ...
    def upsert_sheet_sync(self, request_id: int, payload_json: str) -> SheetSyncRecord: ...
    def authenticate_user(self, login: str, password_plain: str) -> UserRecord | None: ...

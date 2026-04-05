from __future__ import annotations

import json
import re
from collections import defaultdict

from app.models import (
    BaseRequestPayload,
    FioOption,
    FioOptionsResponse,
    BranchCard,
    BranchListResponse,
    DashboardAnalyticsResponse,
    DashboardKPIResponse,
    DashboardStreamItem,
    DashboardStreamResponse,
    InventoryItemResponse,
    InventoryListResponse,
    RegionListResponse,
    ReviewerCommentDTO,
    ReviewerRequestDetailResponse,
    ReviewerRequestListItem,
    ReviewerRequestListResponse,
    RequestCreatedResponse,
    RequestType,
    StreetListResponse,
    StatusRequestItem,
    StatusRequestsResponse,
)
from app.repository import RepositoryProtocol, RequestRecord


class DomainError(Exception):
    def __init__(self, code: str, message_key: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message_key = message_key
        self.details = details or {}


class FioNormalizer:
    _space_re = re.compile(r"\s+")
    _latin_to_cyr = str.maketrans(
        {
            "a": "а",
            "b": "б",
            "d": "д",
            "e": "е",
            "f": "ф",
            "g": "г",
            "h": "ҳ",
            "i": "и",
            "j": "ж",
            "k": "к",
            "l": "л",
            "m": "м",
            "n": "н",
            "o": "о",
            "p": "п",
            "q": "қ",
            "r": "р",
            "s": "с",
            "t": "т",
            "u": "у",
            "v": "в",
            "x": "х",
            "y": "й",
            "z": "з",
        }
    )

    def normalize_basic(self, fio: str) -> str:
        return self._space_re.sub(" ", fio.strip()).lower()

    def normalize_translit(self, fio: str) -> str:
        text = self.normalize_basic(fio)
        for src, dst in (("o'", "ў"), ("g'", "ғ"), ("sh", "ш"), ("ch", "ч"), ("yo", "ё"), ("yu", "ю"), ("ya", "я")):
            text = text.replace(src, dst)
        return text.translate(self._latin_to_cyr)


class RequestService:
    def __init__(self, repo: RepositoryProtocol, normalizer: FioNormalizer) -> None:
        self.repo = repo
        self.normalizer = normalizer

    def start_session(self, telegram_user_id: int, bxm_code: str) -> tuple[int, dict]:
        if not re.match(r"^[0-9]{5}$", bxm_code):
            raise DomainError("INVALID_BXM_FORMAT", "invalid_bxm_format")

        account = self.repo.get_or_create_telegram_account(telegram_user_id)
        branch = self.repo.get_branch_by_bhm(bxm_code)
        if not branch:
            raise DomainError("BXM_NOT_FOUND", "bxm_not_found")

        return account.id, {
            "branch_id": branch.id,
            "bxm_code": branch.bhm_code,
            "branch_name": branch.branch_name,
            "region_name": branch.region_name,
            "city_name": branch.city_name,
        }

    def create_new_issue(self, payload: BaseRequestPayload, reason_text: str) -> RequestCreatedResponse:
        branch, account_id = self._base_validate(payload)
        request = RequestRecord(
            id=0,
            request_number=self.repo.next_request_number(),
            telegram_account_id=account_id,
            employee_fio_snapshot=payload.fio,
            employee_fio_normalized_basic=self.normalizer.normalize_basic(payload.fio),
            employee_fio_normalized_translit=self.normalizer.normalize_translit(payload.fio),
            employee_position_snapshot=payload.position,
            branch_id=branch.id,
            bhm_code_snapshot=branch.bhm_code,
            branch_name_snapshot=branch.branch_name,
            request_type=RequestType.new_issue.value,
            equipment_type=payload.equipment_type.value,
            inventory_id=None,
            inventory_code_snapshot=None,
            reason_text=reason_text,
            problem_text=None,
        )
        created = self.repo.create_request(request)
        self.repo.upsert_sheet_sync(created.id, self._sheet_payload_json(created))
        return RequestCreatedResponse(
            request_id=created.id,
            request_number=created.request_number,
            status_ui="processing",
            message_key="request_created",
            message_text="",
        )

    def create_replacement(self, payload: BaseRequestPayload, inventory_code: str, reason_text: str) -> RequestCreatedResponse:
        branch, account_id = self._base_validate(payload)
        inventory = self._validate_inventory(payload, branch.id, inventory_code)
        if inventory.issue_year >= 2024:
            raise DomainError("REPLACEMENT_YEAR_BLOCKED", "replacement_year_blocked")

        request = RequestRecord(
            id=0,
            request_number=self.repo.next_request_number(),
            telegram_account_id=account_id,
            employee_fio_snapshot=payload.fio,
            employee_fio_normalized_basic=self.normalizer.normalize_basic(payload.fio),
            employee_fio_normalized_translit=self.normalizer.normalize_translit(payload.fio),
            employee_position_snapshot=payload.position,
            branch_id=branch.id,
            bhm_code_snapshot=branch.bhm_code,
            branch_name_snapshot=branch.branch_name,
            request_type=RequestType.replacement.value,
            equipment_type=payload.equipment_type.value,
            inventory_id=inventory.id,
            inventory_code_snapshot=inventory.inventory_code,
            reason_text=reason_text,
            problem_text=None,
        )
        created = self.repo.create_request(request)
        self.repo.upsert_sheet_sync(created.id, self._sheet_payload_json(created))
        return RequestCreatedResponse(
            request_id=created.id,
            request_number=created.request_number,
            status_ui="processing",
            message_key="request_created",
            message_text="",
        )

    def create_repair(self, payload: BaseRequestPayload, inventory_code: str, problem_text: str) -> RequestCreatedResponse:
        branch, account_id = self._base_validate(payload)
        inventory = self._validate_inventory(payload, branch.id, inventory_code)

        request = RequestRecord(
            id=0,
            request_number=self.repo.next_request_number(),
            telegram_account_id=account_id,
            employee_fio_snapshot=payload.fio,
            employee_fio_normalized_basic=self.normalizer.normalize_basic(payload.fio),
            employee_fio_normalized_translit=self.normalizer.normalize_translit(payload.fio),
            employee_position_snapshot=payload.position,
            branch_id=branch.id,
            bhm_code_snapshot=branch.bhm_code,
            branch_name_snapshot=branch.branch_name,
            request_type=RequestType.repair.value,
            equipment_type=payload.equipment_type.value,
            inventory_id=inventory.id,
            inventory_code_snapshot=inventory.inventory_code,
            reason_text=None,
            problem_text=problem_text,
        )
        created = self.repo.create_request(request)
        self.repo.upsert_sheet_sync(created.id, self._sheet_payload_json(created))
        return RequestCreatedResponse(
            request_id=created.id,
            request_number=created.request_number,
            status_ui="processing",
            message_key="request_created",
            message_text="",
        )

    def get_fio_options(self, telegram_user_id: int) -> FioOptionsResponse:
        requests = self.repo.list_requests_by_tg(telegram_user_id)
        groups = defaultdict(list)
        for req in requests:
            groups[req.employee_fio_normalized_basic].append(req)

        options = [
            FioOption(
                fio_display=records[-1].employee_fio_snapshot,
                fio_normalized_basic=key,
                request_count=len(records),
            )
            for key, records in groups.items()
        ]

        return FioOptionsResponse(single_fio_mode=len(options) <= 1, options=options)

    def get_status_requests(self, telegram_user_id: int, fio_query: str | None, page: int, page_size: int) -> StatusRequestsResponse:
        requests = self.repo.list_requests_by_tg(telegram_user_id)
        if fio_query:
            fio_basic = self.normalizer.normalize_basic(fio_query)
            fio_tr = self.normalizer.normalize_translit(fio_query)
            requests = [
                req
                for req in requests
                if req.employee_fio_normalized_basic == fio_basic
                or req.employee_fio_normalized_translit == fio_tr
            ]

        if not requests:
            raise DomainError("FIO_NOT_FOUND", "fio_not_found")

        requests.sort(key=lambda x: x.created_at, reverse=True)
        total = len(requests)
        start = (page - 1) * page_size
        items = requests[start : start + page_size]

        return StatusRequestsResponse(
            items=[
                StatusRequestItem(
                    request_number=req.request_number,
                    fio=req.employee_fio_snapshot,
                    request_type=req.request_type,
                    equipment_type=req.equipment_type,
                    status_ui=self._map_ui_status(req.status, req.final_decision),
                    reject_reason=req.reject_reason,
                    created_at=req.created_at,
                )
                for req in items
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    def _base_validate(self, payload: BaseRequestPayload):
        if not re.match(r"^[0-9]{5}$", payload.bxm_code):
            raise DomainError("INVALID_BXM_FORMAT", "invalid_bxm_format")
        branch = self.repo.get_branch_by_bhm(payload.bxm_code)
        if not branch:
            raise DomainError("BXM_NOT_FOUND", "bxm_not_found")
        account = self.repo.get_or_create_telegram_account(payload.telegram_user_id)
        return branch, account.id

    def _validate_inventory(self, payload: BaseRequestPayload, branch_id: int, inventory_code: str):
        inventory = self.repo.get_inventory(inventory_code)
        if not inventory:
            raise DomainError("INVENTORY_NOT_FOUND", "inventory_not_found")
        if inventory.equipment_type != payload.equipment_type.value:
            raise DomainError("INVENTORY_WRONG_TYPE", "inventory_wrong_type")
        if inventory.branch_id != branch_id:
            raise DomainError("INVENTORY_WRONG_BRANCH", "inventory_wrong_branch")
        if self.repo.has_open_request_for_inventory(inventory_code):
            raise DomainError("INVENTORY_ALREADY_HAS_OPEN_REQUEST", "inventory_open_request_blocked")
        return inventory

    def list_reviewer_requests(
        self,
        status: str | None,
        request_type: str | None,
        branch_id: int | None,
        page: int,
        page_size: int,
    ) -> ReviewerRequestListResponse:
        items = self.repo.list_requests()
        if status:
            items = [x for x in items if x.status == status]
        if request_type:
            items = [x for x in items if x.request_type == request_type]
        if branch_id:
            items = [x for x in items if x.branch_id == branch_id]

        items.sort(key=lambda x: x.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start : start + page_size]
        return ReviewerRequestListResponse(
            items=[
                ReviewerRequestListItem(
                    id=r.id,
                    request_number=r.request_number,
                    fio=r.employee_fio_snapshot,
                    branch_name=r.branch_name_snapshot,
                    request_type=r.request_type,
                    equipment_type=r.equipment_type,
                    status=r.status,
                    final_decision=r.final_decision,
                    created_at=r.created_at,
                )
                for r in page_items
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_reviewer_request_detail(self, request_id: int) -> ReviewerRequestDetailResponse:
        req = self.repo.get_request_by_id(request_id)
        if not req:
            raise DomainError("REQUEST_NOT_FOUND", "validation_error")
        comments = self.repo.list_comments(request_id)
        others = [
            r
            for r in self.repo.list_requests()
            if r.telegram_account_id == req.telegram_account_id and r.id != req.id
        ]
        return ReviewerRequestDetailResponse(
            id=req.id,
            request_number=req.request_number,
            fio=req.employee_fio_snapshot,
            position=req.employee_position_snapshot,
            branch_name=req.branch_name_snapshot,
            request_type=req.request_type,
            equipment_type=req.equipment_type,
            reason_text=req.reason_text,
            problem_text=req.problem_text,
            status=req.status,
            final_decision=req.final_decision,
            reject_reason=req.reject_reason,
            comments=[
                ReviewerCommentDTO(
                    id=c.id,
                    author_name=c.author_name,
                    comment_text=c.comment_text,
                    is_edited=c.is_edited,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in comments
            ],
            other_requests_count=len(others),
            other_requests=[r.request_number for r in others],
        )

    def authenticate_reviewer(self, login: str, password: str):
        user = self.repo.authenticate_user(login, password)
        if not user:
            raise DomainError("INVALID_CREDENTIALS", "validation_error")
        return user

    def create_reviewer_comment(self, request_id: int, author_name: str, comment_text: str) -> ReviewerCommentDTO:
        req = self.repo.get_request_by_id(request_id)
        if not req:
            raise DomainError("REQUEST_NOT_FOUND", "validation_error")
        if req.status == "closed":
            raise DomainError("REQUEST_CLOSED", "validation_error")
        comment = self.repo.create_comment(request_id, author_name, comment_text)
        return ReviewerCommentDTO(
            id=comment.id,
            author_name=comment.author_name,
            comment_text=comment.comment_text,
            is_edited=comment.is_edited,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )

    def update_reviewer_comment(self, comment_id: int, comment_text: str) -> ReviewerCommentDTO:
        comment = self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise DomainError("COMMENT_NOT_FOUND", "validation_error")
        req = self.repo.get_request_by_id(comment.request_id)
        if req and req.status == "closed":
            raise DomainError("REQUEST_CLOSED", "validation_error")
        updated = self.repo.update_comment(comment_id, comment_text)
        return ReviewerCommentDTO(
            id=updated.id,
            author_name=updated.author_name,
            comment_text=updated.comment_text,
            is_edited=updated.is_edited,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    def update_reviewer_status(self, request_id: int, status: str, final_decision: str, reject_reason: str | None):
        req = self.repo.get_request_by_id(request_id)
        if not req:
            raise DomainError("REQUEST_NOT_FOUND", "validation_error")
        if req.status == "closed":
            raise DomainError("REQUEST_CLOSED", "validation_error")
        if status == "closed" and final_decision not in {"approved", "rejected"}:
            raise DomainError("INVALID_FINAL_DECISION", "validation_error")

        fields = {
            "status": status,
            "final_decision": final_decision,
            "reject_reason": reject_reason,
        }
        if status == "closed":
            from datetime import datetime

            fields["closed_at"] = datetime.utcnow()
        updated = self.repo.update_request(request_id, **fields)
        if (
            updated
            and updated.request_type == "repair"
            and updated.status == "closed"
            and updated.final_decision == "approved"
            and updated.inventory_code_snapshot
        ):
            self.repo.update_inventory_status(updated.inventory_code_snapshot, "repair")
        if updated:
            self.repo.upsert_sheet_sync(updated.id, self._sheet_payload_json(updated))
        return updated

    def list_inventory_regions(self) -> RegionListResponse:
        return RegionListResponse(regions=self.repo.list_regions())

    def list_inventory_streets(self, region_name: str) -> StreetListResponse:
        return StreetListResponse(region_name=region_name, streets=self.repo.list_streets(region_name))

    def list_inventory_branches(self, region_name: str, street_name: str) -> BranchListResponse:
        branches = self.repo.list_branches(region_name, street_name)
        return BranchListResponse(
            region_name=region_name,
            street_name=street_name,
            branches=[
                BranchCard(
                    id=b.id,
                    bhm_code=b.bhm_code,
                    branch_name=b.branch_name,
                    city_name=b.city_name,
                    street_name=b.street_name,
                )
                for b in branches
            ],
        )

    def list_branch_inventory(self, branch_id: int) -> InventoryListResponse:
        inventory = self.repo.list_inventory(branch_id)
        return InventoryListResponse(
            branch_id=branch_id,
            items=[
                InventoryItemResponse(
                    inventory_code=i.inventory_code,
                    equipment_type=i.equipment_type,
                    status=i.status,
                    issue_year=i.issue_year,
                )
                for i in inventory
            ],
        )

    def update_inventory_status(self, inventory_code: str, status: str):
        if status not in {"active", "repair", "replaced"}:
            raise DomainError("INVALID_INVENTORY_STATUS", "validation_error")
        updated = self.repo.update_inventory_status(inventory_code, status)
        if not updated:
            raise DomainError("INVENTORY_NOT_FOUND", "inventory_not_found")
        return updated

    def dashboard_kpi(self) -> DashboardKPIResponse:
        requests = self.repo.list_requests()
        active = sum(1 for r in requests if r.status in {"new", "in_progress"})
        approved = sum(1 for r in requests if r.status == "closed" and r.final_decision == "approved")
        rejected = sum(1 for r in requests if r.status == "closed" and r.final_decision == "rejected")
        return DashboardKPIResponse(
            active_requests=active,
            closed_approved=approved,
            closed_rejected=rejected,
            total_requests=len(requests),
        )

    def dashboard_stream(
        self,
        status: str | None,
        request_type: str | None,
        branch_id: int | None,
        page: int,
        page_size: int,
    ) -> DashboardStreamResponse:
        items = self.repo.list_requests()
        if status:
            items = [x for x in items if x.status == status]
        if request_type:
            items = [x for x in items if x.request_type == request_type]
        if branch_id:
            items = [x for x in items if x.branch_id == branch_id]
        items.sort(key=lambda x: x.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start : start + page_size]
        return DashboardStreamResponse(
            items=[
                DashboardStreamItem(
                    id=r.id,
                    request_number=r.request_number,
                    fio=r.employee_fio_snapshot,
                    branch_name=r.branch_name_snapshot,
                    request_type=r.request_type,
                    equipment_type=r.equipment_type,
                    status=r.status,
                    final_decision=r.final_decision,
                    created_at=r.created_at,
                )
                for r in page_items
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    def dashboard_analytics(self) -> DashboardAnalyticsResponse:
        requests = self.repo.list_requests()
        by_branch: dict[str, int] = {}
        by_request_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for req in requests:
            by_branch[req.branch_name_snapshot] = by_branch.get(req.branch_name_snapshot, 0) + 1
            by_request_type[req.request_type] = by_request_type.get(req.request_type, 0) + 1
            key = f"{req.status}:{req.final_decision}"
            by_status[key] = by_status.get(key, 0) + 1
        return DashboardAnalyticsResponse(
            by_branch=by_branch,
            by_request_type=by_request_type,
            by_status=by_status,
        )

    @staticmethod
    def _sheet_payload_json(request: RequestRecord) -> str:
        return json.dumps(
            {
                "timestamp": request.updated_at.isoformat(),
                "request_id": request.id,
                "request_number": request.request_number,
                "fio": request.employee_fio_snapshot,
                "bxm_code": request.bhm_code_snapshot,
                "request_type": request.request_type,
                "status": request.status,
                "final_decision": request.final_decision,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _map_ui_status(status: str, final_decision: str) -> str:
        if status in {"new", "in_progress"} and final_decision == "pending":
            return "processing"
        if status == "closed" and final_decision == "approved":
            return "approved"
        return "rejected"

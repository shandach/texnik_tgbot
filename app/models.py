from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Dumpable:
    def model_dump(self) -> dict:
        return asdict(self)


class Locale(str, Enum):
    uz = "uz"
    ru = "ru"


class EquipmentType(str, Enum):
    computer = "computer"
    printer = "printer"


class RequestType(str, Enum):
    new_issue = "new_issue"
    replacement = "replacement"
    repair = "repair"


class RequestStatus(str, Enum):
    new = "new"
    in_progress = "in_progress"
    closed = "closed"


class FinalDecision(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


@dataclass
class StartSessionRequest(Dumpable):
    telegram_user_id: int
    locale: Locale = Locale.uz
    fio_input: str = ""
    bxm_code: str = ""


@dataclass
class StartSessionResponse(Dumpable):
    telegram_account_id: int
    branch: dict
    message_key: str
    message_text: str


@dataclass
class BaseRequestPayload(Dumpable):
    telegram_user_id: int
    locale: Locale = Locale.uz
    bxm_code: str = ""
    fio: str = ""
    position: str = ""
    equipment_type: EquipmentType = EquipmentType.computer


@dataclass
class NewIssueCreateRequest(BaseRequestPayload):
    reason_text: str = ""


@dataclass
class ReplacementCreateRequest(BaseRequestPayload):
    inventory_code: str = ""
    reason_text: str = ""


@dataclass
class RepairCreateRequest(BaseRequestPayload):
    inventory_code: str = ""
    problem_text: str = ""


@dataclass
class RequestCreatedResponse(Dumpable):
    request_id: int
    request_number: str
    status_ui: str
    message_key: str
    message_text: str


@dataclass
class ErrorResponse(Dumpable):
    error_code: str
    message_key: str
    message_text: str
    details: Optional[dict] = None


@dataclass
class FioOption(Dumpable):
    fio_display: str
    fio_normalized_basic: str
    request_count: int


@dataclass
class FioOptionsResponse(Dumpable):
    single_fio_mode: bool
    options: list[FioOption]


@dataclass
class StatusRequestItem(Dumpable):
    request_number: str
    fio: str
    request_type: RequestType
    equipment_type: EquipmentType
    status_ui: str
    reject_reason: Optional[str]
    created_at: datetime


@dataclass
class StatusRequestsResponse(Dumpable):
    items: list[StatusRequestItem]
    page: int
    page_size: int
    total: int


@dataclass
class ReviewerRequestListItem(Dumpable):
    id: int
    request_number: str
    fio: str
    branch_name: str
    request_type: str
    equipment_type: str
    status: str
    final_decision: str
    created_at: datetime


@dataclass
class ReviewerRequestListResponse(Dumpable):
    items: list[ReviewerRequestListItem]
    page: int
    page_size: int
    total: int


@dataclass
class ReviewerCommentDTO(Dumpable):
    id: int
    author_name: str
    comment_text: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class ReviewerRequestDetailResponse(Dumpable):
    id: int
    request_number: str
    fio: str
    position: str
    branch_name: str
    request_type: str
    equipment_type: str
    reason_text: Optional[str]
    problem_text: Optional[str]
    status: str
    final_decision: str
    reject_reason: Optional[str]
    comments: list[ReviewerCommentDTO]
    other_requests_count: int
    other_requests: list[str]


@dataclass
class ReviewerCommentCreateRequest(Dumpable):
    author_name: str
    comment_text: str


@dataclass
class ReviewerCommentUpdateRequest(Dumpable):
    comment_text: str


@dataclass
class ReviewerStatusUpdateRequest(Dumpable):
    status: str
    final_decision: str
    reject_reason: Optional[str] = None


@dataclass
class RegionListResponse(Dumpable):
    regions: list[str]


@dataclass
class StreetListResponse(Dumpable):
    region_name: str
    streets: list[str]


@dataclass
class BranchCard(Dumpable):
    id: int
    bhm_code: str
    branch_name: str
    city_name: str
    street_name: str


@dataclass
class BranchListResponse(Dumpable):
    region_name: str
    street_name: str
    branches: list[BranchCard]


@dataclass
class InventoryItemResponse(Dumpable):
    inventory_code: str
    equipment_type: str
    status: str
    issue_year: int


@dataclass
class InventoryListResponse(Dumpable):
    branch_id: int
    items: list[InventoryItemResponse]


@dataclass
class DashboardKPIResponse(Dumpable):
    active_requests: int
    closed_approved: int
    closed_rejected: int
    total_requests: int


@dataclass
class DashboardStreamItem(Dumpable):
    id: int
    request_number: str
    fio: str
    branch_name: str
    request_type: str
    equipment_type: str
    status: str
    final_decision: str
    created_at: datetime


@dataclass
class DashboardStreamResponse(Dumpable):
    items: list[DashboardStreamItem]
    page: int
    page_size: int
    total: int


@dataclass
class DashboardAnalyticsResponse(Dumpable):
    by_branch: dict[str, int]
    by_request_type: dict[str, int]
    by_status: dict[str, int]


@dataclass
class ReviewerLoginRequest(Dumpable):
    login: str
    password: str


@dataclass
class ReviewerLoginResponse(Dumpable):
    access_token: str
    role: str
    full_name: str

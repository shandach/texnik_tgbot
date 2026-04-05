from __future__ import annotations

import os
import importlib
import importlib.util
import uuid

from app.i18n import I18NService
from app.models import (
    BranchListResponse,
    DashboardAnalyticsResponse,
    DashboardKPIResponse,
    DashboardStreamResponse,
    ErrorResponse,
    FioOptionsResponse,
    InventoryListResponse,
    Locale,
    NewIssueCreateRequest,
    RepairCreateRequest,
    ReviewerCommentCreateRequest,
    ReviewerCommentDTO,
    ReviewerCommentUpdateRequest,
    ReviewerLoginRequest,
    ReviewerLoginResponse,
    ReviewerRequestDetailResponse,
    ReviewerRequestListResponse,
    ReviewerStatusUpdateRequest,
    RegionListResponse,
    ReplacementCreateRequest,
    RequestCreatedResponse,
    StartSessionRequest,
    StartSessionResponse,
    StreetListResponse,
    StatusRequestsResponse,
)
from app.repository import InMemoryRepository
from app.services import DomainError, FioNormalizer, RequestService
from app.web import get_web_components

FastAPI, Query, JSONResponse = get_web_components()

app = FastAPI(title="Texnik TG Bot API", version="0.3.0")
database_url = os.getenv("DATABASE_URL", "").strip()
if database_url and importlib.util.find_spec("sqlalchemy"):
    postgres_repo_module = importlib.import_module("app.postgres_repository")
    repo = postgres_repo_module.PostgresRepository(database_url)
else:
    repo = InMemoryRepository()
i18n = I18NService()
service = RequestService(repo=repo, normalizer=FioNormalizer())
sessions: dict[str, dict] = {}


def _error_response(locale: Locale, exc: DomainError, status_code: int = 422) -> JSONResponse:
    payload = ErrorResponse(
        error_code=exc.code,
        message_key=exc.message_key,
        message_text=i18n.t(locale.value, exc.message_key, **exc.details),
        details=exc.details,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _ensure_reviewer_role(actor_role: str | None, locale: Locale) -> JSONResponse | None:
    if actor_role in {"reviewer", "developer"}:
        return None
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(
            error_code="FORBIDDEN",
            message_key="forbidden",
            message_text=i18n.t(locale.value, "forbidden"),
            details={"required_roles": ["reviewer", "developer"]},
        ).model_dump(),
    )


def _resolve_actor_role(actor_role: str | None, access_token: str | None) -> str | None:
    if access_token and access_token in sessions:
        return sessions[access_token]["role"]
    return actor_role


@app.post("/v1/reviewer/auth/login", response_model=ReviewerLoginResponse)
def reviewer_login(payload: ReviewerLoginRequest, locale: Locale = Locale.uz) -> ReviewerLoginResponse | JSONResponse:
    try:
        user = service.authenticate_reviewer(payload.login, payload.password)
    except DomainError as exc:
        return _error_response(locale, exc, status_code=401)
    token = uuid.uuid4().hex
    sessions[token] = {"user_id": user.id, "role": user.role, "full_name": user.full_name}
    return ReviewerLoginResponse(access_token=token, role=user.role, full_name=user.full_name)


@app.post("/v1/bot/session/start", response_model=StartSessionResponse)
def start_session(payload: StartSessionRequest) -> StartSessionResponse | JSONResponse:
    try:
        account_id, branch = service.start_session(payload.telegram_user_id, payload.bxm_code)
    except DomainError as exc:
        return _error_response(payload.locale, exc)

    return StartSessionResponse(
        telegram_account_id=account_id,
        branch=branch,
        message_key="session_bxm_confirmed",
        message_text=i18n.t(payload.locale.value, "session_bxm_confirmed", **branch),
    )


@app.post("/v1/bot/requests/new-issue", response_model=RequestCreatedResponse)
def create_new_issue(payload: NewIssueCreateRequest) -> RequestCreatedResponse | JSONResponse:
    try:
        created = service.create_new_issue(payload, payload.reason_text)
    except DomainError as exc:
        return _error_response(payload.locale, exc)

    created.message_text = i18n.t(payload.locale.value, created.message_key, request_number=created.request_number)
    return created


@app.post("/v1/bot/requests/replacement", response_model=RequestCreatedResponse)
def create_replacement(payload: ReplacementCreateRequest) -> RequestCreatedResponse | JSONResponse:
    try:
        created = service.create_replacement(payload, payload.inventory_code, payload.reason_text)
    except DomainError as exc:
        return _error_response(payload.locale, exc)

    created.message_text = i18n.t(payload.locale.value, created.message_key, request_number=created.request_number)
    return created


@app.post("/v1/bot/requests/repair", response_model=RequestCreatedResponse)
def create_repair(payload: RepairCreateRequest) -> RequestCreatedResponse | JSONResponse:
    try:
        created = service.create_repair(payload, payload.inventory_code, payload.problem_text)
    except DomainError as exc:
        return _error_response(payload.locale, exc)

    created.message_text = i18n.t(payload.locale.value, created.message_key, request_number=created.request_number)
    return created


@app.get("/v1/bot/status/fio-options", response_model=FioOptionsResponse)
def get_fio_options(
    telegram_user_id: int,
    locale: Locale = Locale.uz,
) -> FioOptionsResponse | JSONResponse:
    try:
        return service.get_fio_options(telegram_user_id)
    except DomainError as exc:
        return _error_response(locale, exc)


@app.get("/v1/bot/status/requests", response_model=StatusRequestsResponse)
def get_status_requests(
    telegram_user_id: int,
    fio_query: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    locale: Locale = Locale.uz,
) -> StatusRequestsResponse | JSONResponse:
    try:
        return service.get_status_requests(telegram_user_id, fio_query, page, page_size)
    except DomainError as exc:
        status_code = 404 if exc.code == "FIO_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)


@app.get("/v1/reviewer/requests", response_model=ReviewerRequestListResponse)
def reviewer_list_requests(
    status: str | None = None,
    request_type: str | None = None,
    branch_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
) -> ReviewerRequestListResponse | JSONResponse:
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        return service.list_reviewer_requests(status, request_type, branch_id, page, page_size)
    except DomainError as exc:
        return _error_response(locale, exc)


@app.get("/v1/reviewer/requests/{request_id}", response_model=ReviewerRequestDetailResponse)
def reviewer_request_detail(
    request_id: int,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
) -> ReviewerRequestDetailResponse | JSONResponse:
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        return service.get_reviewer_request_detail(request_id)
    except DomainError as exc:
        status_code = 404 if exc.code == "REQUEST_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)


@app.post("/v1/reviewer/requests/{request_id}/comments", response_model=ReviewerCommentDTO)
def reviewer_create_comment(
    request_id: int,
    payload: ReviewerCommentCreateRequest,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
) -> ReviewerCommentDTO | JSONResponse:
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        return service.create_reviewer_comment(request_id, payload.author_name, payload.comment_text)
    except DomainError as exc:
        status_code = 404 if exc.code == "REQUEST_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)


@app.put("/v1/reviewer/comments/{comment_id}", response_model=ReviewerCommentDTO)
def reviewer_update_comment(
    comment_id: int,
    payload: ReviewerCommentUpdateRequest,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
) -> ReviewerCommentDTO | JSONResponse:
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        return service.update_reviewer_comment(comment_id, payload.comment_text)
    except DomainError as exc:
        status_code = 404 if exc.code == "COMMENT_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)


@app.put("/v1/reviewer/requests/{request_id}/status")
def reviewer_update_status(
    request_id: int,
    payload: ReviewerStatusUpdateRequest,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        updated = service.update_reviewer_status(
            request_id=request_id,
            status=payload.status,
            final_decision=payload.final_decision,
            reject_reason=payload.reject_reason,
        )
        return {
            "id": updated.id,
            "status": updated.status,
            "final_decision": updated.final_decision,
            "reject_reason": updated.reject_reason,
        }
    except DomainError as exc:
        status_code = 404 if exc.code == "REQUEST_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)


@app.get("/v1/reviewer/inventory/regions", response_model=RegionListResponse)
def reviewer_inventory_regions(actor_role: str | None = None, access_token: str | None = None, locale: Locale = Locale.uz):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.list_inventory_regions()


@app.get("/v1/reviewer/inventory/streets", response_model=StreetListResponse)
def reviewer_inventory_streets(region_name: str, actor_role: str | None = None, access_token: str | None = None, locale: Locale = Locale.uz):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.list_inventory_streets(region_name)


@app.get("/v1/reviewer/inventory/branches", response_model=BranchListResponse)
def reviewer_inventory_branches(
    region_name: str,
    street_name: str,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.list_inventory_branches(region_name, street_name)


@app.get("/v1/reviewer/inventory", response_model=InventoryListResponse)
def reviewer_branch_inventory(branch_id: int, actor_role: str | None = None, access_token: str | None = None, locale: Locale = Locale.uz):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.list_branch_inventory(branch_id)


@app.put("/v1/reviewer/inventory/{inventory_code}/status")
def reviewer_update_inventory_status(
    inventory_code: str,
    status: str,
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    try:
        updated = service.update_inventory_status(inventory_code, status)
        return {
            "inventory_code": updated.inventory_code,
            "status": updated.status,
        }
    except DomainError as exc:
        status_code = 404 if exc.code == "INVENTORY_NOT_FOUND" else 422
        return _error_response(locale, exc, status_code=status_code)

@app.get("/v1/reviewer/dashboard/kpi", response_model=DashboardKPIResponse)
def reviewer_dashboard_kpi(actor_role: str | None = None, access_token: str | None = None, locale: Locale = Locale.uz):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.dashboard_kpi()


@app.get("/v1/reviewer/dashboard/stream", response_model=DashboardStreamResponse)
def reviewer_dashboard_stream(
    status: str | None = None,
    request_type: str | None = None,
    branch_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    actor_role: str | None = None,
    access_token: str | None = None,
    locale: Locale = Locale.uz,
):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.dashboard_stream(status, request_type, branch_id, page, page_size)


@app.get("/v1/reviewer/dashboard/analytics", response_model=DashboardAnalyticsResponse)
def reviewer_dashboard_analytics(actor_role: str | None = None, access_token: str | None = None, locale: Locale = Locale.uz):
    denied = _ensure_reviewer_role(_resolve_actor_role(actor_role, access_token), locale)
    if denied:
        return denied
    return service.dashboard_analytics()

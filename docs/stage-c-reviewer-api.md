# Stage C — Reviewer API

Implemented endpoints:

- `POST /v1/reviewer/auth/login`
  - login/password auth for reviewer panel, returns access token
- `GET /v1/reviewer/requests`
  - pagination + filters: `status`, `request_type`, `branch_id`
- `GET /v1/reviewer/requests/{request_id}`
  - request detail, comments, other requests count
- `POST /v1/reviewer/requests/{request_id}/comments`
  - add comment (only if request is not closed)
- `PUT /v1/reviewer/comments/{comment_id}`
  - edit existing comment (only if parent request is not closed)
- `PUT /v1/reviewer/requests/{request_id}/status`
  - update status and final decision

Business rules:
- Closed requests cannot be commented.
- Closed requests cannot be re-closed/updated again.
- `status=closed` requires `final_decision` in `approved/rejected`.
- Role-check: reviewer endpoints require reviewer role from access token (`reviewer`/`developer`).

This stage is implemented in:
- `app/main.py`
- `app/services.py`
- `app/repository.py`
- `app/postgres_repository.py`

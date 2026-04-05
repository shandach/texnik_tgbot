# Stage F — Dashboard KPI & analytics API

Implemented reviewer dashboard endpoints:

- `GET /v1/reviewer/dashboard/kpi`
  - `active_requests`
  - `closed_approved`
  - `closed_rejected`
  - `total_requests`
- `GET /v1/reviewer/dashboard/stream`
  - paginated request stream with optional filters (`status`, `request_type`, `branch_id`)
- `GET /v1/reviewer/dashboard/analytics`
  - grouped counters:
    - by branch
    - by request type
    - by status/final decision

All endpoints are role-protected (`reviewer`/`developer`).

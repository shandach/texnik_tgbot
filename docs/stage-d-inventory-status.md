# Stage D — Inventory status API

Implemented reviewer inventory endpoints:

- `GET /v1/reviewer/inventory/regions`
- `GET /v1/reviewer/inventory/streets?region_name=...`
- `GET /v1/reviewer/inventory/branches?region_name=...&street_name=...`
- `GET /v1/reviewer/inventory?branch_id=...`
- `PUT /v1/reviewer/inventory/{inventory_code}/status?status=active|repair|replaced`

Rules:
- Endpoints are role-protected (`reviewer`/`developer`).
- Inventory status can be changed manually by reviewer.
- When a `repair` request is closed with `approved`, inventory status auto-switches to `repair`.

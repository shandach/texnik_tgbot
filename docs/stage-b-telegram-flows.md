# Stage B — Telegram flows

## Scope
- Scenarios: `new_issue`, `replacement`, `repair`.
- Validation: BXM and inventory checks.
- Employee feature: "Status of my requests" with multiple FIO logic.
- Locale-aware messaging: default UZ, optional RU.

## Runtime implementation artifact
- FastAPI service entrypoint: `app/main.py`
- Core domain logic: `app/services.py`
- In-memory repository for flow prototyping: `app/repository.py`
- Message localization loader: `app/i18n.py`

## 1) Request creation flows

### 1.1 `new_issue`
1. Validate `bxm_code` format (`^[0-9]{5}$`) and existence.
2. Accept payload: `fio`, `position`, `reason_text`, `equipment_type`.
3. Create request with:
   - `request_type = new_issue`
   - `status = new`
   - `final_decision = pending`
   - `inventory_id = null`, `inventory_code_snapshot = null`

### 1.2 `replacement`
1. Validate `bxm_code` format and existence.
2. Validate inventory:
   - inventory exists
   - inventory type matches requested equipment type
   - inventory belongs to BXM branch
   - no open request exists for `inventory_code_snapshot`
3. Validate year rule:
   - allowed only if `issue_year < 2024`
4. Accept payload: `fio`, `position`, `reason_text`, `inventory_code`, `equipment_type`.
5. Create request with `request_type = replacement`.

### 1.3 `repair`
1. Validate `bxm_code` format and existence.
2. Validate inventory:
   - inventory exists
   - inventory type matches requested equipment type
   - inventory belongs to BXM branch
   - no open request exists for `inventory_code_snapshot`
3. No `issue_year` restriction.
4. Accept payload: `fio`, `position`, `problem_text`, `inventory_code`, `equipment_type`.
5. Create request with `request_type = repair`.

## 2) Validation error mapping
- `INVALID_BXM_FORMAT` -> i18n key `invalid_bxm_format`
- `BXM_NOT_FOUND` -> i18n key `bxm_not_found`
- `INVENTORY_NOT_FOUND` -> i18n key `inventory_not_found`
- `INVENTORY_WRONG_TYPE` -> i18n key `inventory_wrong_type`
- `INVENTORY_WRONG_BRANCH` -> i18n key `inventory_wrong_branch`
- `INVENTORY_ALREADY_HAS_OPEN_REQUEST` -> i18n key `inventory_open_request_blocked`
- `REPLACEMENT_YEAR_BLOCKED` -> i18n key `replacement_year_blocked`
- `FIO_NOT_FOUND` -> i18n key `fio_not_found`

## 3) "Status of my requests"

### 3.1 FIO selection logic by telegram account
- Query all request snapshots by `telegram_user_id`.
- Group by `employee_fio_normalized_basic`.
- If exactly one group exists -> immediately show requests list.
- If multiple groups exist:
  - show FIO cards and input search box
  - support free-text FIO filter (`fio_query`) with translit-aware matching

### 3.2 Status mapping for employee UI
- DB: `status in (new, in_progress)` + `final_decision = pending` -> UI `processing`
- DB: `status = closed` + `final_decision = approved` -> UI `approved`
- DB: `status = closed` + `final_decision = rejected` -> UI `rejected`
- If rejected and reason exists -> show `status_rejected_with_reason`

### 3.3 Pagination
- Endpoint returns paginated list (`page`, `page_size`, `total`).
- Default page size is 10, max 50.

## 4) Notification behavior
- After reviewer decision change, employee is notified in selected locale.
- Notification payload uses i18n key + params:
  - approved: `status_approved`
  - rejected with reason: `status_rejected_with_reason`
  - rejected without reason: `status_rejected`

## 5) Implementation notes for service layer
- Create `FioNormalizer` with two outputs:
  - `fio_normalized_basic`
  - `fio_normalized_translit`
- Create `InventoryValidationService` for shared checks in `replacement` and `repair`.
- Keep `request_number` generation in backend service layer to avoid client-side collisions.

# Stage A — Backend foundation (approved scope)

## 1) Core architectural decision
- Backend is implemented as code that exposes a REST API for:
  - Telegram bot (employee flows)
  - Internal dashboard (reviewers)
- Deployment target: Docker Compose.

## 2) Language and i18n baseline
- Default language: Uzbek (UZ).
- Russian (RU) is also supported.
- All bot-facing text must be localized:
  - menu labels
  - prompts
  - validation errors
  - status updates and notifications

## 2.1) Secrets policy
- Telegram bot token must be loaded from environment variable `TELEGRAM_BOT_TOKEN`.
- Real bot tokens must never be committed to the repository.
- Use `.env.example` as template; keep real `.env` local only.

## 3) Data model constraints introduced in Stage A
- `bhm_code` and request snapshots use 5-digit validation.
- Requests have strict lifecycle consistency:
  - `new` / `in_progress` => `final_decision = pending`, `closed_at = null`
  - `closed` => `final_decision in (approved, rejected)`, `closed_at != null`
- One open request per `inventory_code` across all request types:
  - If a request exists with status `new` or `in_progress`, a new request with same inventory code is blocked.

## 4) FIO normalization strategy
Each request and employee record stores:
- `fio_normalized_basic`
  - trim
  - collapse duplicated spaces
  - lower-case
- `fio_normalized_translit`
  - canonical transliterated representation for Latin/Cyrillic matching

Matching policy:
- If normalized + transliterated forms still do not match, treat as different persons.

## 5) Business rules confirmed in this stage
- `position` is free text; stored as snapshot in requests for reporting.
- `replacement` keeps issue-year rule (`issue_year < 2024`).
- `repair` has no issue-year restriction.
- Closed requests cannot receive new reviewer comments.
- Rejection reason is optional, but if provided it is visible to employee in request status view.
- `updated_at` for requests/comments is maintained automatically by database trigger.

## 6) Pending implementation in next stages
- Concrete API endpoints for bot + dashboard.
- Auth flow and role guards (`developer`, `reviewer`).
- Inventory status tab (Region -> Street -> BHM) with reviewer status controls.
- Google Sheets outbox/retry integration with one row per request.

-- Stage A foundation schema for texnik_tgbot
-- PostgreSQL 14+

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'equipment_type_enum') THEN
        CREATE TYPE equipment_type_enum AS ENUM ('computer', 'printer');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inventory_status_enum') THEN
        CREATE TYPE inventory_status_enum AS ENUM ('active', 'repair', 'replaced');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'request_type_enum') THEN
        CREATE TYPE request_type_enum AS ENUM ('replacement', 'new_issue', 'repair');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'request_status_enum') THEN
        CREATE TYPE request_status_enum AS ENUM ('new', 'in_progress', 'closed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'final_decision_enum') THEN
        CREATE TYPE final_decision_enum AS ENUM ('pending', 'approved', 'rejected');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reviewer_role_enum') THEN
        CREATE TYPE reviewer_role_enum AS ENUM ('developer', 'reviewer');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS bhm_branches (
    id BIGSERIAL PRIMARY KEY,
    bhm_code CHAR(5) NOT NULL UNIQUE,
    branch_name TEXT NOT NULL,
    region_name TEXT NOT NULL,
    city_name TEXT NOT NULL,
    street_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT bhm_code_numeric_chk CHECK (bhm_code ~ '^[0-9]{5}$')
);

CREATE TABLE IF NOT EXISTS telegram_accounts (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    fio_original TEXT NOT NULL,
    fio_normalized_basic TEXT NOT NULL,
    fio_normalized_translit TEXT NOT NULL,
    position TEXT,
    branch_id BIGINT NOT NULL REFERENCES bhm_branches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory (
    id BIGSERIAL PRIMARY KEY,
    inventory_code TEXT NOT NULL UNIQUE,
    branch_id BIGINT NOT NULL REFERENCES bhm_branches(id),
    equipment_type equipment_type_enum NOT NULL,
    issue_year INT NOT NULL,
    status inventory_status_enum NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT issue_year_reasonable_chk CHECK (issue_year >= 1990 AND issue_year <= 2100)
);

CREATE TABLE IF NOT EXISTS requests (
    id BIGSERIAL PRIMARY KEY,
    request_number TEXT NOT NULL UNIQUE,
    telegram_account_id BIGINT NOT NULL REFERENCES telegram_accounts(id),
    employee_id BIGINT REFERENCES employees(id),
    employee_fio_snapshot TEXT NOT NULL,
    employee_fio_normalized_basic TEXT NOT NULL,
    employee_fio_normalized_translit TEXT NOT NULL,
    employee_position_snapshot TEXT,
    branch_id BIGINT NOT NULL REFERENCES bhm_branches(id),
    bhm_code_snapshot CHAR(5) NOT NULL,
    branch_name_snapshot TEXT NOT NULL,
    request_type request_type_enum NOT NULL,
    equipment_type equipment_type_enum NOT NULL,
    inventory_id BIGINT REFERENCES inventory(id),
    inventory_code_snapshot TEXT,
    reason_text TEXT,
    problem_text TEXT,
    status request_status_enum NOT NULL DEFAULT 'new',
    final_decision final_decision_enum NOT NULL DEFAULT 'pending',
    reject_reason TEXT,
    reviewer_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    CONSTRAINT bhm_code_snapshot_numeric_chk CHECK (bhm_code_snapshot ~ '^[0-9]{5}$'),
    CONSTRAINT request_close_consistency_chk CHECK (
        (status = 'closed' AND final_decision IN ('approved', 'rejected') AND closed_at IS NOT NULL)
        OR
        (status IN ('new', 'in_progress') AND final_decision = 'pending' AND closed_at IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS request_comments (
    id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    author_name TEXT NOT NULL,
    comment_text TEXT NOT NULL,
    is_edited BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role reviewer_role_enum NOT NULL,
    full_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS sheet_sync_outbox (
    id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NOT NULL UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    payload_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sheet_sync_status_chk CHECK (status IN ('pending', 'processing', 'synced', 'failed'))
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_comment_on_closed_request()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM requests r
        WHERE r.id = NEW.request_id
          AND r.status = 'closed'
    ) THEN
        RAISE EXCEPTION 'Cannot add or edit comments for closed requests';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS requests_set_updated_at_tg ON requests;
CREATE TRIGGER requests_set_updated_at_tg
BEFORE UPDATE ON requests
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS request_comments_set_updated_at_tg ON request_comments;
CREATE TRIGGER request_comments_set_updated_at_tg
BEFORE UPDATE ON request_comments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS request_comments_block_on_closed_tg ON request_comments;
CREATE TRIGGER request_comments_block_on_closed_tg
BEFORE INSERT OR UPDATE ON request_comments
FOR EACH ROW
EXECUTE FUNCTION prevent_comment_on_closed_request();

-- Prevent duplicate active requests by same inventory_code across all request types.
-- If inventory_code is null (new_issue), this rule does not apply.
CREATE UNIQUE INDEX IF NOT EXISTS requests_open_inventory_unique_idx
    ON requests (inventory_code_snapshot)
    WHERE status IN ('new', 'in_progress') AND inventory_code_snapshot IS NOT NULL;

CREATE INDEX IF NOT EXISTS requests_tg_account_created_idx
    ON requests (telegram_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS requests_fio_basic_idx
    ON requests (employee_fio_normalized_basic);

CREATE INDEX IF NOT EXISTS requests_fio_translit_idx
    ON requests (employee_fio_normalized_translit);

CREATE INDEX IF NOT EXISTS requests_status_type_branch_created_idx
    ON requests (status, request_type, branch_id, created_at DESC);

CREATE INDEX IF NOT EXISTS branches_region_city_street_idx
    ON bhm_branches (region_name, city_name, street_name, bhm_code);

CREATE INDEX IF NOT EXISTS requests_fio_basic_trgm_idx
    ON requests USING GIN (employee_fio_normalized_basic gin_trgm_ops);

CREATE INDEX IF NOT EXISTS requests_fio_translit_trgm_idx
    ON requests USING GIN (employee_fio_normalized_translit gin_trgm_ops);

CREATE INDEX IF NOT EXISTS sheet_sync_status_next_retry_idx
    ON sheet_sync_outbox (status, next_retry_at, created_at);

COMMIT;

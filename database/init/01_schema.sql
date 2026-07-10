-- IT Helpdesk: schema
-- PostgreSQL 16+

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

CREATE TYPE urgency_level AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE user_role AS ENUM (
    'specialist',
    'admin'
);

CREATE TYPE account_status AS ENUM (
    'active',
    'blocked'
);

CREATE TYPE audit_action AS ENUM (
    'login',
    'logout',
    'status_change',
    'assign_specialist',
    'comment_added',
    'client_department_updated',
    'request_created',
    'category_created',
    'category_updated',
    'user_created',
    'user_blocked',
    'user_unblocked',
    'status_created',
    'status_updated',
    'request_deleted'
);

-- ---------------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------------

CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE statuses (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Clients
-- ---------------------------------------------------------------------------

CREATE TABLE clients (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(255) NOT NULL,
    department  VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_clients_full_name_normalized
    ON clients (LOWER(TRIM(full_name)));

CREATE INDEX idx_clients_full_name_trgm
    ON clients USING gin (full_name gin_trgm_ops);

CREATE INDEX idx_clients_department
    ON clients (department)
    WHERE department IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Support specialists / administrators
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    login           VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'specialist',
    account_status  account_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_account_status ON users (account_status);

-- ---------------------------------------------------------------------------
-- Service requests
-- ---------------------------------------------------------------------------

CREATE TABLE requests (
    id                      SERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_id               INTEGER NOT NULL REFERENCES clients (id) ON DELETE RESTRICT,
    cabinet                 VARCHAR(64) NOT NULL,
    category_id             INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    description             TEXT NOT NULL,
    urgency                 urgency_level NOT NULL DEFAULT 'medium',
    preferred_visit_time    VARCHAR(255),
    status_id               INTEGER NOT NULL REFERENCES statuses (id) ON DELETE RESTRICT,
    specialist_id           INTEGER REFERENCES users (id) ON DELETE SET NULL,
    accepted_at             TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    specialist_comment      TEXT,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_requests_completed_after_accepted
        CHECK (completed_at IS NULL OR accepted_at IS NULL OR completed_at >= accepted_at)
);

CREATE INDEX idx_requests_status_id ON requests (status_id);
CREATE INDEX idx_requests_category_id ON requests (category_id);
CREATE INDEX idx_requests_specialist_id ON requests (specialist_id);
CREATE INDEX idx_requests_urgency ON requests (urgency);
CREATE INDEX idx_requests_created_at ON requests (created_at DESC);
CREATE INDEX idx_requests_cabinet ON requests (cabinet);
CREATE INDEX idx_requests_client_id ON requests (client_id);

-- ---------------------------------------------------------------------------
-- Request status history (recommended)
-- ---------------------------------------------------------------------------

CREATE TABLE request_history (
    id              BIGSERIAL PRIMARY KEY,
    request_id      INTEGER NOT NULL REFERENCES requests (id) ON DELETE CASCADE,
    changed_by_id   INTEGER REFERENCES users (id) ON DELETE SET NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    old_status_id   INTEGER REFERENCES statuses (id) ON DELETE SET NULL,
    new_status_id   INTEGER NOT NULL REFERENCES statuses (id) ON DELETE RESTRICT,
    comment         TEXT
);

CREATE INDEX idx_request_history_request_id ON request_history (request_id, changed_at DESC);
CREATE INDEX idx_request_history_changed_by ON request_history (changed_by_id);

-- ---------------------------------------------------------------------------
-- Audit log (recommended)
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users (id) ON DELETE SET NULL,
    action          audit_action NOT NULL,
    entity_type     VARCHAR(64) NOT NULL,
    entity_id       INTEGER,
    details         JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log (user_id, created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log (action, created_at DESC);
CREATE INDEX idx_audit_log_entity ON audit_log (entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- Triggers: updated_at
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_requests_updated_at
    BEFORE UPDATE ON requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Trigger: initial history row on request creation
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION log_request_created_history()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO request_history (request_id, changed_by_id, old_status_id, new_status_id, comment)
    VALUES (NEW.id, NULL, NULL, NEW.status_id, 'Заявка создана');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_requests_created_history
    AFTER INSERT ON requests
    FOR EACH ROW EXECUTE FUNCTION log_request_created_history();

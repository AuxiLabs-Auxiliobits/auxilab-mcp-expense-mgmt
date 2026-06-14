-- First-cut identity schema (DbAuthProvider era).
-- Lives here as a design reference; the authoritative version ships as an Alembic
-- migration in api/ once the FastAPI project exists. See docs/identity-strategy.md.

-- Departments: profile metadata for now. See ADR-001 open question before using
-- department to restrict visibility.
CREATE TABLE departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    cost_center TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Role-based only (SCOPING §3): scope is derived from role (self | all), no team_id.
CREATE TYPE user_role AS ENUM ('employee', 'manager', 'finance', 'auditor', 'agent');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    role            user_role NOT NULL DEFAULT 'employee',
    department_id   UUID REFERENCES departments(id),

    -- DbAuthProvider columns (dropped after Entra migration)
    password_hash   TEXT,                 -- argon2id; NULL once federated
    is_active       BOOLEAN NOT NULL DEFAULT true,
    failed_logins   INT NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,

    -- EntraAuthProvider linkage (backfilled at migration time, matched on email)
    entra_object_id TEXT UNIQUE,          -- Entra `oid`; NULL until federated

    -- "many other columns" — extend freely as profile needs grow
    employee_code   TEXT UNIQUE,
    manager_email   TEXT,                 -- informational only; not an RBAC scope
    title           TEXT,
    phone           TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_department ON users(department_id);

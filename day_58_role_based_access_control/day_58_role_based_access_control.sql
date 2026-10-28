DROP SCHEMA IF EXISTS rbac_demo CASCADE;
CREATE SCHEMA rbac_demo;

SET search_path = rbac_demo, public;

-- RBAC separates principals, roles, permissions, and resource instances.
-- Resource ownership is represented separately because it is an
-- instance-level policy rather than a role permission.

CREATE TABLE app_users (
    user_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(username)) >= 3),
    CHECK (length(password_hash) >= 20)
);

CREATE TABLE roles (
    role_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name    TEXT NOT NULL UNIQUE,
    description  TEXT NOT NULL,
    CHECK (role_name ~ '^[a-z][a-z0-9_]{1,31}$')
);

CREATE TABLE permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_type TEXT NOT NULL,
    action        TEXT NOT NULL,
    UNIQUE (resource_type, action),
    CHECK (resource_type ~ '^[a-z][a-z0-9_]{1,63}$'),
    CHECK (
        action IN (
            'read',
            'create',
            'update',
            'delete',
            'approve',
            'admin'
        )
    )
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES app_users(user_id)
        ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(role_id)
        ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT REFERENCES app_users(user_id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permissions (
    role_id       BIGINT NOT NULL REFERENCES roles(role_id)
        ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(permission_id)
        ON DELETE CASCADE,
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE resources (
    resource_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_key TEXT NOT NULL UNIQUE,
    resource_type TEXT NOT NULL,
    owner_id     BIGINT NOT NULL REFERENCES app_users(user_id),
    sensitivity  TEXT NOT NULL DEFAULT 'normal',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        sensitivity IN ('normal', 'high', 'critical')
    )
);

CREATE TABLE authorization_requests (
    request_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES app_users(user_id),
    resource_id       BIGINT NOT NULL REFERENCES resources(resource_id),
    action            TEXT NOT NULL,
    requested_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decision          TEXT,
    decision_reason   TEXT,
    CHECK (
        action IN (
            'read',
            'create',
            'update',
            'delete',
            'approve',
            'admin'
        )
    ),
    CHECK (
        decision IS NULL
        OR decision IN ('allow', 'deny')
    )
);

CREATE TABLE authorization_decisions (
    decision_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id        BIGINT NOT NULL UNIQUE
        REFERENCES authorization_requests(request_id)
        ON DELETE CASCADE,
    decision          TEXT NOT NULL,
    reason            TEXT NOT NULL,
    matched_role      BIGINT REFERENCES roles(role_id),
    evaluated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (decision IN ('allow', 'deny'))
);

CREATE TABLE audit_events (
    audit_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT REFERENCES app_users(user_id)
        ON DELETE SET NULL,
    event_type    TEXT NOT NULL,
    event_detail  JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- These indexes support the authorization joins and audit reporting
-- without creating indexes on low-selectivity boolean columns.
CREATE INDEX idx_user_roles_role
    ON user_roles(role_id);

CREATE INDEX idx_role_permissions_permission
    ON role_permissions(permission_id);

CREATE INDEX idx_resources_owner_type
    ON resources(owner_id, resource_type);

CREATE INDEX idx_auth_requests_user_time
    ON authorization_requests(user_id, requested_at DESC);

CREATE INDEX idx_audit_user_time
    ON audit_events(user_id, occurred_at DESC);

CREATE INDEX idx_audit_event_type
    ON audit_events(event_type);

INSERT INTO roles (role_name, description) VALUES
    ('user', 'Standard application user'),
    ('support', 'Customer and ticket support operator'),
    ('manager', 'Operational manager with approval authority'),
    ('admin', 'Repository and system administrator');

INSERT INTO permissions (resource_type, action) VALUES
    ('profile', 'read'),
    ('profile', 'update'),
    ('ticket', 'read'),
    ('ticket', 'update'),
    ('ticket', 'approve'),
    ('report', 'read'),
    ('system', 'admin');

INSERT INTO app_users (username, password_hash) VALUES
    ('alice', 'pbkdf2_sha256$200000$demo_alice_hash'),
    ('bob', 'pbkdf2_sha256$200000$demo_bob_hash'),
    ('carol', 'pbkdf2_sha256$200000$demo_carol_hash'),
    ('david', 'pbkdf2_sha256$200000$demo_david_hash');

INSERT INTO user_roles (user_id, role_id, assigned_by)
SELECT u.user_id, r.role_id, u.user_id
FROM app_users u
JOIN roles r
  ON r.role_name =
     CASE u.username
         WHEN 'alice' THEN 'user'
         WHEN 'bob'   THEN 'support'
         WHEN 'carol' THEN 'manager'
         WHEN 'david' THEN 'admin'
     END;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p
  ON (
       r.role_name = 'user'
       AND (p.resource_type, p.action) IN (
           ('profile', 'read'),
           ('profile', 'update')
       )
     )
  OR (
       r.role_name = 'support'
       AND (p.resource_type, p.action) IN (
           ('profile', 'read'),
           ('ticket', 'read'),
           ('ticket', 'update')
       )
     )
  OR (
       r.role_name = 'manager'
       AND (p.resource_type, p.action) IN (
           ('profile', 'read'),
           ('ticket', 'read'),
           ('ticket', 'update'),
           ('ticket', 'approve'),
           ('report', 'read')
       )
     )
  OR (
       r.role_name = 'admin'
       AND (p.resource_type, p.action) IN (
           ('profile', 'read'),
           ('profile', 'update'),
           ('ticket', 'read'),
           ('ticket', 'update'),
           ('ticket', 'approve'),
           ('report', 'read'),
           ('system', 'admin')
       )
     );

INSERT INTO resources (
    resource_key,
    resource_type,
    owner_id,
    sensitivity
)
SELECT
    x.resource_key,
    x.resource_type,
    u.user_id,
    x.sensitivity
FROM (
    VALUES
        ('alice-profile', 'profile', 'alice', 'normal'),
        ('bob-ticket', 'ticket', 'bob', 'normal'),
        ('carol-report', 'report', 'carol', 'high'),
        ('system-config', 'system', 'david', 'critical')
) AS x(
    resource_key,
    resource_type,
    username,
    sensitivity
)
JOIN app_users u
  ON u.username = x.username;

-- Authorization function:
-- 1. rejects inactive users,
-- 2. requires admin role for system administration,
-- 3. evaluates explicit role permissions,
-- 4. applies a narrow ownership policy,
-- 5. returns the first applicable decision with a reason.
CREATE OR REPLACE FUNCTION evaluate_authorization(
    p_user_id BIGINT,
    p_resource_id BIGINT,
    p_action TEXT
)
RETURNS TABLE (
    decision TEXT,
    reason TEXT,
    matched_role TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_active BOOLEAN;
    v_resource_type TEXT;
    v_owner_id BIGINT;
    v_role_name TEXT;
BEGIN
    SELECT
        u.active,
        r.resource_type,
        r.owner_id
    INTO
        v_active,
        v_resource_type,
        v_owner_id
    FROM app_users u
    CROSS JOIN resources r
    WHERE u.user_id = p_user_id
      AND r.resource_id = p_resource_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            'deny',
            'Unknown user or resource',
            NULL::TEXT;
        RETURN;
    END IF;

    IF NOT v_active THEN
        RETURN QUERY
        SELECT
            'deny',
            'User account is inactive',
            NULL::TEXT;
        RETURN;
    END IF;

    IF p_action = 'admin' THEN
        SELECT r.role_name
        INTO v_role_name
        FROM user_roles ur
        JOIN roles r ON r.role_id = ur.role_id
        WHERE ur.user_id = p_user_id
          AND r.role_name = 'admin'
        LIMIT 1;

        IF v_role_name IS NULL THEN
            RETURN QUERY
            SELECT
                'deny',
                'Administrative action requires admin role',
                NULL::TEXT;
            RETURN;
        END IF;
    END IF;

    SELECT r.role_name
    INTO v_role_name
    FROM user_roles ur
    JOIN roles r
      ON r.role_id = ur.role_id
    JOIN role_permissions rp
      ON rp.role_id = r.role_id
    JOIN permissions p
      ON p.permission_id = rp.permission_id
    WHERE ur.user_id = p_user_id
      AND p.resource_type = v_resource_type
      AND p.action = p_action
    ORDER BY
        CASE r.role_name
            WHEN 'admin' THEN 1
            WHEN 'manager' THEN 2
            WHEN 'support' THEN 3
            ELSE 4
        END
    LIMIT 1;

    IF v_role_name IS NOT NULL THEN
        RETURN QUERY
        SELECT
            'allow',
            'Explicit role permission matched',
            v_role_name;
        RETURN;
    END IF;

    IF v_owner_id = p_user_id
       AND p_action IN ('read', 'update')
       AND v_resource_type IN ('profile', 'document') THEN
        RETURN QUERY
        SELECT
            'allow',
            'Ownership policy matched',
            NULL::TEXT;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        'deny',
        'No applicable role permission or ownership policy',
        NULL::TEXT;
END;
$$;

-- This trigger records authorization outcomes centrally.
CREATE OR REPLACE FUNCTION record_authorization_decision()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.decision IS NOT NULL THEN
        INSERT INTO audit_events (
            user_id,
            event_type,
            event_detail
        )
        VALUES (
            NEW.user_id,
            'authorization',
            jsonb_build_object(
                'request_id', NEW.request_id,
                'resource_id', NEW.resource_id,
                'action', NEW.action,
                'decision', NEW.decision,
                'reason', NEW.decision_reason
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_authorization_audit
AFTER INSERT OR UPDATE OF decision, decision_reason
ON authorization_requests
FOR EACH ROW
EXECUTE FUNCTION record_authorization_decision();

-- Prevent an authorization request from storing an invalid decision.
CREATE OR REPLACE FUNCTION validate_authorization_request()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.decision = 'allow' AND NEW.decision_reason IS NULL THEN
        RAISE EXCEPTION
            'Allowed authorization requests require a decision reason';
    END IF;

    IF NEW.decision = 'deny' AND NEW.decision_reason IS NULL THEN
        RAISE EXCEPTION
            'Denied authorization requests require a decision reason';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_authorization_request
BEFORE INSERT OR UPDATE
ON authorization_requests
FOR EACH ROW
EXECUTE FUNCTION validate_authorization_request();

-- View of effective permissions for operational reporting.
CREATE OR REPLACE VIEW effective_user_permissions AS
SELECT
    u.user_id,
    u.username,
    r.role_name,
    p.resource_type,
    p.action
FROM app_users u
JOIN user_roles ur
  ON ur.user_id = u.user_id
JOIN roles r
  ON r.role_id = ur.role_id
JOIN role_permissions rp
  ON rp.role_id = r.role_id
JOIN permissions p
  ON p.permission_id = rp.permission_id
WHERE u.active = TRUE;

-- View exposing resources and ownership without exposing passwords.
CREATE OR REPLACE VIEW resource_access_context AS
SELECT
    r.resource_id,
    r.resource_key,
    r.resource_type,
    r.sensitivity,
    r.owner_id,
    u.username AS owner_username
FROM resources r
JOIN app_users u
  ON u.user_id = r.owner_id;

-- Example 1: effective permissions.
SELECT
    username,
    role_name,
    resource_type,
    action
FROM effective_user_permissions
ORDER BY username, role_name, resource_type, action;

-- Example 2: aggregate permissions by user.
SELECT
    username,
    count(*) AS permission_count,
    array_agg(
        role_name || ':' || resource_type || ':' || action
        ORDER BY role_name, resource_type, action
    ) AS effective_permissions
FROM effective_user_permissions
GROUP BY username
ORDER BY username;

-- Example 3: direct authorization evaluations.
SELECT
    'alice profile update' AS scenario,
    *
FROM evaluate_authorization(
    (SELECT user_id FROM app_users WHERE username = 'alice'),
    (SELECT resource_id FROM resources WHERE resource_key = 'alice-profile'),
    'update'
);

SELECT
    'alice ticket update' AS scenario,
    *
FROM evaluate_authorization(
    (SELECT user_id FROM app_users WHERE username = 'alice'),
    (SELECT resource_id FROM resources WHERE resource_key = 'bob-ticket'),
    'update'
);

SELECT
    'bob ticket update' AS scenario,
    *
FROM evaluate_authorization(
    (SELECT user_id FROM app_users WHERE username = 'bob'),
    (SELECT resource_id FROM resources WHERE resource_key = 'bob-ticket'),
    'update'
);

SELECT
    'bob system admin' AS scenario,
    *
FROM evaluate_authorization(
    (SELECT user_id FROM app_users WHERE username = 'bob'),
    (SELECT resource_id FROM resources WHERE resource_key = 'system-config'),
    'admin'
);

SELECT
    'david system admin' AS scenario,
    *
FROM evaluate_authorization(
    (SELECT user_id FROM app_users WHERE username = 'david'),
    (SELECT resource_id FROM resources WHERE resource_key = 'system-config'),
    'admin'
);

-- Demonstrate a transactional authorization-recording workflow.
BEGIN;

WITH evaluation AS (
    SELECT *
    FROM evaluate_authorization(
        (SELECT user_id
         FROM app_users
         WHERE username = 'carol'),
        (SELECT resource_id
         FROM resources
         WHERE resource_key = 'bob-ticket'),
        'approve'
    )
),
created AS (
    INSERT INTO authorization_requests (
        user_id,
        resource_id,
        action,
        decision,
        decision_reason
    )
    SELECT
        (SELECT user_id
         FROM app_users
         WHERE username = 'carol'),
        (SELECT resource_id
         FROM resources
         WHERE resource_key = 'bob-ticket'),
        'approve',
        evaluation.decision,
        evaluation.reason
    FROM evaluation
    RETURNING *
)
INSERT INTO authorization_decisions (
    request_id,
    decision,
    reason,
    matched_role
)
SELECT
    created.request_id,
    created.decision,
    created.decision_reason,
    (
        SELECT r.role_id
        FROM roles r
        WHERE r.role_name = evaluation.matched_role
    )
FROM created
CROSS JOIN evaluation;

COMMIT;

-- Report authorization decisions by user and outcome.
SELECT
    u.username,
    ar.action,
    ar.decision,
    ar.decision_reason,
    ar.requested_at
FROM authorization_requests ar
JOIN app_users u
  ON u.user_id = ar.user_id
ORDER BY ar.requested_at DESC;

-- Report denial frequency by reason.
SELECT
    decision_reason,
    count(*) AS denial_count
FROM authorization_requests
WHERE decision = 'deny'
GROUP BY decision_reason
ORDER BY denial_count DESC, decision_reason;

-- Validate that every active user has at least one effective permission.
SELECT
    u.username,
    count(eup.permission_id) AS permission_count
FROM app_users u
LEFT JOIN (
    SELECT
        ur.user_id,
        rp.permission_id
    FROM user_roles ur
    JOIN role_permissions rp
      ON rp.role_id = ur.role_id
) eup
  ON eup.user_id = u.user_id
WHERE u.active
GROUP BY u.user_id, u.username
ORDER BY u.username;

-- Security check: application roles must not receive the system admin
-- permission unless the role itself is explicitly named admin.
SELECT
    r.role_name,
    p.resource_type,
    p.action
FROM roles r
JOIN role_permissions rp
  ON rp.role_id = r.role_id
JOIN permissions p
  ON p.permission_id = rp.permission_id
WHERE p.resource_type = 'system'
  AND p.action = 'admin'
  AND r.role_name <> 'admin';

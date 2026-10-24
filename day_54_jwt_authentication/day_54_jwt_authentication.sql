DROP SCHEMA IF EXISTS jwt_auth CASCADE;
CREATE SCHEMA jwt_auth;

SET search_path = jwt_auth, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_status AS ENUM ('active', 'disabled');
CREATE TYPE token_status AS ENUM ('active', 'revoked', 'expired');
CREATE TYPE token_type AS ENUM ('access');
CREATE TYPE auth_event_type AS ENUM (
    'login_success',
    'login_failure',
    'token_issued',
    'token_rejected',
    'access_granted',
    'access_denied'
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    status user_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
    role_id BIGSERIAL PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE
);

CREATE TABLE scopes (
    scope_id BIGSERIAL PRIMARY KEY,
    scope_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE user_scopes (
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    scope_id BIGINT NOT NULL REFERENCES scopes(scope_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, scope_id)
);

CREATE TABLE access_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_type token_type NOT NULL DEFAULT 'access',
    token_hash TEXT NOT NULL UNIQUE,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    status token_status NOT NULL DEFAULT 'active',
    CONSTRAINT valid_token_period
        CHECK (expires_at > issued_at),
    CONSTRAINT valid_revocation_time
        CHECK (
            revoked_at IS NULL
            OR revoked_at >= issued_at
        )
);

CREATE INDEX idx_access_tokens_user_status
    ON access_tokens(user_id, status);

CREATE INDEX idx_access_tokens_expiry
    ON access_tokens(expires_at);

CREATE TABLE protected_routes (
    route_id BIGSERIAL PRIMARY KEY,
    route_pattern TEXT NOT NULL UNIQUE,
    http_method TEXT NOT NULL,
    required_scope_id BIGINT REFERENCES scopes(scope_id),
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE authentication_events (
    event_id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type auth_event_type NOT NULL,
    token_id UUID REFERENCES access_tokens(token_id)
        ON DELETE SET NULL,
    route_id BIGINT REFERENCES protected_routes(route_id)
        ON DELETE SET NULL,
    reason TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_auth_events_user_time
    ON authentication_events(user_id, occurred_at DESC);

CREATE TABLE refresh_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT valid_refresh_period
        CHECK (expires_at > created_at)
);

CREATE OR REPLACE FUNCTION validate_access_token_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.token_type <> 'access' THEN
        RAISE EXCEPTION 'Only access tokens may be stored in this table';
    END IF;

    IF NEW.expires_at <= NEW.issued_at THEN
        RAISE EXCEPTION 'Token expiry must be after issuance';
    END IF;

    IF NEW.status = 'revoked' AND NEW.revoked_at IS NULL THEN
        RAISE EXCEPTION 'Revoked token must have revoked_at';
    END IF;

    IF NEW.status <> 'revoked' AND NEW.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'Only revoked tokens may have revoked_at';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_access_token
BEFORE INSERT OR UPDATE ON access_tokens
FOR EACH ROW
EXECUTE FUNCTION validate_access_token_row();

CREATE OR REPLACE FUNCTION expire_old_tokens()
RETURNS void
LANGUAGE sql
AS $$
    UPDATE access_tokens
       SET status = 'expired'
     WHERE status = 'active'
       AND expires_at <= now();
$$;

CREATE OR REPLACE FUNCTION has_user_scope(
    p_user_id UUID,
    p_scope_name TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM user_scopes us
        JOIN scopes s
          ON s.scope_id = us.scope_id
        WHERE us.user_id = p_user_id
          AND s.scope_name = p_scope_name
    );
$$;

CREATE OR REPLACE FUNCTION token_is_valid(
    p_token_hash TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM access_tokens t
        JOIN users u
          ON u.user_id = t.user_id
        WHERE t.token_hash = p_token_hash
          AND t.token_type = 'access'
          AND t.status = 'active'
          AND t.revoked_at IS NULL
          AND t.issued_at <= now()
          AND t.expires_at > now()
          AND u.status = 'active'
    );
$$;

CREATE OR REPLACE FUNCTION can_access_route(
    p_token_hash TEXT,
    p_route_pattern TEXT,
    p_http_method TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_user_id UUID;
    v_scope TEXT;
    v_route_enabled BOOLEAN;
BEGIN
    SELECT
        t.user_id,
        s.scope_name,
        r.enabled
    INTO
        v_user_id,
        v_scope,
        v_route_enabled
    FROM access_tokens t
    JOIN users u
      ON u.user_id = t.user_id
    JOIN protected_routes r
      ON r.route_pattern = p_route_pattern
     AND r.http_method = upper(p_http_method)
    LEFT JOIN scopes s
      ON s.scope_id = r.required_scope_id
    WHERE t.token_hash = p_token_hash
      AND t.status = 'active'
      AND t.revoked_at IS NULL
      AND t.issued_at <= now()
      AND t.expires_at > now()
      AND u.status = 'active';

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF NOT v_route_enabled THEN
        RETURN FALSE;
    END IF;

    IF v_scope IS NULL THEN
        RETURN TRUE;
    END IF;

    RETURN has_user_scope(v_user_id, v_scope);
END;
$$;

INSERT INTO roles(role_name)
VALUES
    ('customer'),
    ('admin'),
    ('support')
ON CONFLICT DO NOTHING;

INSERT INTO scopes(scope_name, description)
VALUES
    ('orders:read', 'Read customer orders'),
    ('orders:write', 'Create or modify orders'),
    ('profile:read', 'Read user profile'),
    ('admin:users', 'Manage users')
ON CONFLICT DO NOTHING;

INSERT INTO users(username, password_hash)
VALUES
    ('alice', 'pbkdf2-placeholder-for-demonstration-record'),
    ('bob', 'pbkdf2-placeholder-for-demonstration-record'),
    ('admin', 'pbkdf2-placeholder-for-demonstration-record');

UPDATE users
SET status = 'disabled'
WHERE username = 'bob';

INSERT INTO user_roles(user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_name = 'customer'
WHERE u.username = 'alice';

INSERT INTO user_roles(user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_name = 'admin'
WHERE u.username = 'admin';

INSERT INTO user_scopes(user_id, scope_id)
SELECT u.user_id, s.scope_id
FROM users u
JOIN scopes s
  ON s.scope_name IN ('orders:read', 'profile:read')
WHERE u.username = 'alice';

INSERT INTO user_scopes(user_id, scope_id)
SELECT u.user_id, s.scope_id
FROM users u
JOIN scopes s
  ON s.scope_name IN (
      'orders:read',
      'orders:write',
      'profile:read',
      'admin:users'
  )
WHERE u.username = 'admin';

INSERT INTO protected_routes(
    route_pattern,
    http_method,
    required_scope_id
)
SELECT '/orders',
       'GET',
       scope_id
FROM scopes
WHERE scope_name = 'orders:read';

INSERT INTO protected_routes(
    route_pattern,
    http_method,
    required_scope_id
)
SELECT '/orders',
       'POST',
       scope_id
FROM scopes
WHERE scope_name = 'orders:write';

INSERT INTO protected_routes(
    route_pattern,
    http_method,
    required_scope_id
)
SELECT '/profile',
       'GET',
       scope_id
FROM scopes
WHERE scope_name = 'profile:read';

INSERT INTO protected_routes(
    route_pattern,
    http_method,
    required_scope_id
)
SELECT '/admin/users',
       'GET',
       scope_id
FROM scopes
WHERE scope_name = 'admin:users';

DO $$
DECLARE
    alice_id UUID;
    admin_id UUID;
    read_token UUID := gen_random_uuid();
    expired_token UUID := gen_random_uuid();
    revoked_token UUID := gen_random_uuid();
BEGIN
    SELECT user_id
    INTO alice_id
    FROM users
    WHERE username = 'alice';

    SELECT user_id
    INTO admin_id
    FROM users
    WHERE username = 'admin';

    INSERT INTO access_tokens(
        token_id,
        user_id,
        token_hash,
        issued_at,
        expires_at,
        status
    )
    VALUES
    (
        read_token,
        alice_id,
        encode(digest(read_token::text, 'sha256'), 'hex'),
        now() - interval '2 minutes',
        now() + interval '13 minutes',
        'active'
    ),
    (
        expired_token,
        alice_id,
        encode(digest(expired_token::text, 'sha256'), 'hex'),
        now() - interval '2 hours',
        now() - interval '1 hour',
        'expired'
    ),
    (
        revoked_token,
        admin_id,
        encode(digest(revoked_token::text, 'sha256'), 'hex'),
        now() - interval '2 minutes',
        now() + interval '13 minutes',
        'revoked'
    );

    UPDATE access_tokens
    SET revoked_at = now()
    WHERE token_id = revoked_token;

    INSERT INTO authentication_events(
        user_id,
        event_type,
        token_id,
        reason
    )
    VALUES
    (
        alice_id,
        'login_success',
        read_token,
        'Valid credentials'
    ),
    (
        alice_id,
        'token_issued',
        read_token,
        'Access token created'
    ),
    (
        alice_id,
        'access_granted',
        read_token,
        'orders:read satisfied'
    ),
    (
        alice_id,
        'access_denied',
        expired_token,
        'Access token expired'
    ),
    (
        admin_id,
        'access_denied',
        revoked_token,
        'Access token revoked'
    );
END;
$$;

SELECT
    u.username,
    r.role_name
FROM users u
JOIN user_roles ur
  ON ur.user_id = u.user_id
JOIN roles r
  ON r.role_id = ur.role_id
ORDER BY u.username, r.role_name;

SELECT
    u.username,
    s.scope_name
FROM users u
JOIN user_scopes us
  ON us.user_id = u.user_id
JOIN scopes s
  ON s.scope_id = us.scope_id
ORDER BY u.username, s.scope_name;

SELECT
    route_pattern,
    http_method,
    s.scope_name AS required_scope
FROM protected_routes r
LEFT JOIN scopes s
  ON s.scope_id = r.required_scope_id
ORDER BY route_pattern, http_method;

SELECT expire_old_tokens();

SELECT
    t.token_id,
    u.username,
    t.status,
    t.issued_at,
    t.expires_at,
    t.revoked_at
FROM access_tokens t
JOIN users u
  ON u.user_id = t.user_id
ORDER BY t.expires_at;

SELECT
    u.username,
    COUNT(*) FILTER (
        WHERE e.event_type = 'access_granted'
    ) AS granted_requests,
    COUNT(*) FILTER (
        WHERE e.event_type = 'access_denied'
    ) AS denied_requests
FROM users u
LEFT JOIN authentication_events e
  ON e.user_id = u.user_id
GROUP BY u.username
ORDER BY u.username;

SELECT
    r.route_pattern,
    r.http_method,
    s.scope_name AS required_scope
FROM protected_routes r
LEFT JOIN scopes s
  ON s.scope_id = r.required_scope_id
WHERE r.enabled = TRUE;

SELECT
    token_is_valid(
        t.token_hash
    ) AS token_currently_valid,
    u.username,
    t.status,
    t.expires_at
FROM access_tokens t
JOIN users u
  ON u.user_id = t.user_id
ORDER BY u.username, t.expires_at;

SELECT
    can_access_route(
        t.token_hash,
        '/orders',
        'GET'
    ) AS alice_can_read_orders
FROM access_tokens t
JOIN users u
  ON u.user_id = t.user_id
WHERE u.username = 'alice'
  AND t.status = 'active';

BEGIN;

SELECT
    t.token_id,
    t.status,
    t.expires_at
FROM access_tokens t
JOIN users u
  ON u.user_id = t.user_id
WHERE u.username = 'alice'
FOR UPDATE;

INSERT INTO authentication_events(
    user_id,
    event_type,
    reason
)
SELECT
    user_id,
    'access_granted',
    'Transactional authorization audit'
FROM users
WHERE username = 'alice';

COMMIT;

DROP SCHEMA IF EXISTS authentication_fundamentals CASCADE;
CREATE SCHEMA authentication_fundamentals;
SET search_path TO authentication_fundamentals;

-- Identity is the account representation. Authentication records how
-- credentials are verified. Authorization roles are separate concerns.
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    account_status TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('active', 'locked', 'disabled')),
    failed_login_attempts INTEGER NOT NULL DEFAULT 0
        CHECK (failed_login_attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE credentials (
    credential_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE
        REFERENCES users(user_id) ON DELETE CASCADE,
    algorithm TEXT NOT NULL
        CHECK (algorithm IN ('PBKDF2-HMAC-SHA256', 'ARGON2ID')),
    password_salt TEXT NOT NULL,
    password_verifier TEXT NOT NULL,
    work_factor INTEGER NOT NULL
        CHECK (work_factor > 0),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE roles (
    role_id BIGSERIAL PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CHECK (expires_at > created_at),
    CHECK (
        (status = 'revoked' AND revoked_at IS NOT NULL)
        OR
        (status <> 'revoked' AND revoked_at IS NULL)
    )
);

CREATE TABLE login_events (
    login_event_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    username_attempted TEXT NOT NULL,
    succeeded BOOLEAN NOT NULL,
    failure_reason TEXT,
    source_ip INET,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        succeeded = TRUE
        OR failure_reason IS NOT NULL
    )
);

CREATE TABLE authorization_audit (
    authorization_event_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    session_id UUID REFERENCES sessions(session_id),
    required_role TEXT NOT NULL,
    allowed BOOLEAN NOT NULL,
    reason TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user_active
    ON sessions(user_id, status, expires_at);

CREATE INDEX idx_login_events_username_time
    ON login_events(username_attempted, occurred_at DESC);

CREATE INDEX idx_authorization_user_time
    ON authorization_audit(user_id, occurred_at DESC);

INSERT INTO roles (role_name, description) VALUES
    ('user', 'Standard authenticated application user'),
    ('administrator', 'Administrative application operator'),
    ('auditor', 'Read-only security and audit reviewer');

INSERT INTO users (
    username,
    email
) VALUES
    ('alice', 'alice@example.test'),
    ('bob', 'bob@example.test'),
    ('disabled-user', 'disabled@example.test');

INSERT INTO credentials (
    user_id,
    algorithm,
    password_salt,
    password_verifier,
    work_factor
)
SELECT
    user_id,
    'PBKDF2-HMAC-SHA256',
    'demo-salt-' || username,
    'demo-verifier-' || username,
    210000
FROM users;

UPDATE users
SET account_status = 'disabled'
WHERE username = 'disabled-user';

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_name = 'user'
WHERE u.username IN ('alice', 'bob');

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_name = 'administrator'
WHERE u.username = 'alice';

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_name = 'auditor'
WHERE u.username = 'bob';

-- A session is evidence of an authenticated state, not an authorization
-- decision. Role membership remains a separate relation.
INSERT INTO sessions (
    session_id,
    user_id,
    status,
    created_at,
    expires_at
)
SELECT
    '11111111-1111-1111-1111-111111111111',
    user_id,
    'active',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP + INTERVAL '30 minutes'
FROM users
WHERE username = 'alice';

INSERT INTO sessions (
    session_id,
    user_id,
    status,
    created_at,
    expires_at
)
SELECT
    '22222222-2222-2222-2222-222222222222',
    user_id,
    'revoked',
    CURRENT_TIMESTAMP - INTERVAL '2 hours',
    CURRENT_TIMESTAMP - INTERVAL '90 minutes'
FROM users
WHERE username = 'bob';

UPDATE sessions
SET revoked_at = CURRENT_TIMESTAMP - INTERVAL '90 minutes'
WHERE session_id =
    '22222222-2222-2222-2222-222222222222';

INSERT INTO login_events (
    user_id,
    username_attempted,
    succeeded,
    failure_reason,
    source_ip
)
SELECT
    user_id,
    'alice',
    TRUE,
    NULL,
    '192.0.2.10'
FROM users
WHERE username = 'alice';

INSERT INTO login_events (
    user_id,
    username_attempted,
    succeeded,
    failure_reason,
    source_ip
)
SELECT
    user_id,
    'alice',
    FALSE,
    'invalid_credentials',
    '192.0.2.10'
FROM users
WHERE username = 'alice';

INSERT INTO login_events (
    user_id,
    username_attempted,
    succeeded,
    failure_reason,
    source_ip
)
SELECT
    user_id,
    'unknown-user',
    FALSE,
    'unknown_identity',
    '192.0.2.20'
FROM users
WHERE username = 'alice';

CREATE OR REPLACE FUNCTION record_failed_login(
    attempted_username TEXT,
    attempted_ip INET,
    failure TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    matched_user_id BIGINT;
    new_failure_count INTEGER;
BEGIN
    SELECT user_id
    INTO matched_user_id
    FROM users
    WHERE username = LOWER(attempted_username);

    INSERT INTO login_events (
        user_id,
        username_attempted,
        succeeded,
        failure_reason,
        source_ip
    )
    VALUES (
        matched_user_id,
        LOWER(attempted_username),
        FALSE,
        failure,
        attempted_ip
    );

    IF matched_user_id IS NOT NULL THEN
        UPDATE users
        SET failed_login_attempts = failed_login_attempts + 1
        WHERE user_id = matched_user_id
        RETURNING failed_login_attempts INTO new_failure_count;

        IF new_failure_count >= 5 THEN
            UPDATE users
            SET account_status = 'locked'
            WHERE user_id = matched_user_id;
        END IF;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION authorize_session(
    requested_session UUID,
    required_role TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    authenticated_user BIGINT;
    has_role BOOLEAN;
BEGIN
    SELECT s.user_id
    INTO authenticated_user
    FROM sessions s
    JOIN users u ON u.user_id = s.user_id
    WHERE s.session_id = requested_session
      AND s.status = 'active'
      AND s.expires_at > CURRENT_TIMESTAMP
      AND u.account_status = 'active';

    IF authenticated_user IS NULL THEN
        RETURN FALSE;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM user_roles ur
        JOIN roles r ON r.role_id = ur.role_id
        WHERE ur.user_id = authenticated_user
          AND r.role_name = required_role
    )
    INTO has_role;

    INSERT INTO authorization_audit (
        user_id,
        session_id,
        required_role,
        allowed,
        reason
    )
    VALUES (
        authenticated_user,
        requested_session,
        required_role,
        has_role,
        CASE
            WHEN has_role THEN 'role_present'
            ELSE 'role_missing'
        END
    );

    RETURN has_role;
END;
$$;

CREATE OR REPLACE VIEW active_authenticated_sessions AS
SELECT
    s.session_id,
    u.username,
    u.account_status,
    s.created_at,
    s.expires_at
FROM sessions s
JOIN users u ON u.user_id = s.user_id
WHERE s.status = 'active'
  AND s.expires_at > CURRENT_TIMESTAMP
  AND u.account_status = 'active';

CREATE OR REPLACE VIEW user_authorization_matrix AS
SELECT
    u.username,
    r.role_name,
    u.account_status,
    CASE
        WHEN u.account_status = 'active' THEN TRUE
        ELSE FALSE
    END AS identity_active
FROM users u
LEFT JOIN user_roles ur ON ur.user_id = u.user_id
LEFT JOIN roles r ON r.role_id = ur.role_id;

-- Demonstrate transactional failure handling. The savepoint allows the
-- failed operation to be rolled back without losing the transaction.
BEGIN;

SAVEPOINT before_invalid_role;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM roles
        WHERE role_name = 'user'
    ) THEN
        RAISE EXCEPTION 'Required role does not exist';
    END IF;
END;
$$;

ROLLBACK TO SAVEPOINT before_invalid_role;

COMMIT;

-- Evaluate authentication state separately from authorization state.
SELECT
    username,
    account_status,
    failed_login_attempts
FROM users
ORDER BY username;

SELECT
    username,
    role_name,
    identity_active
FROM user_authorization_matrix
ORDER BY username, role_name;

SELECT
    session_id,
    username,
    created_at,
    expires_at
FROM active_authenticated_sessions
ORDER BY expires_at;

SELECT
    u.username,
    COUNT(*) FILTER (WHERE le.succeeded) AS successful_logins,
    COUNT(*) FILTER (WHERE NOT le.succeeded) AS failed_logins
FROM users u
LEFT JOIN login_events le
    ON le.user_id = u.user_id
GROUP BY u.user_id, u.username
ORDER BY u.username;

SELECT
    authorize_session(
        '11111111-1111-1111-1111-111111111111',
        'user'
    ) AS alice_user_access;

SELECT
    authorize_session(
        '11111111-1111-1111-1111-111111111111',
        'administrator'
    ) AS alice_admin_access;

SELECT
    authorize_session(
        '22222222-2222-2222-2222-222222222222',
        'auditor'
    ) AS revoked_session_access;

-- Lockout behavior is performed transactionally so the login event and
-- account-state change remain consistent.
BEGIN;

SELECT record_failed_login(
    'bob',
    '192.0.2.30',
    'invalid_credentials'
);

SELECT record_failed_login(
    'bob',
    '192.0.2.30',
    'invalid_credentials'
);

SELECT record_failed_login(
    'bob',
    '192.0.2.30',
    'invalid_credentials'
);

SELECT record_failed_login(
    'bob',
    '192.0.2.30',
    'invalid_credentials'
);

SELECT record_failed_login(
    'bob',
    '192.0.2.30',
    'invalid_credentials'
);

COMMIT;

SELECT
    username,
    account_status,
    failed_login_attempts
FROM users
WHERE username = 'bob';

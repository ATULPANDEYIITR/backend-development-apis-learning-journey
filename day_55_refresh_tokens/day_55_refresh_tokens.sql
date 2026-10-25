-- PostgreSQL 15+
-- Refresh-token lifecycle, rotation, revocation, and policy enforcement.
-- Run in a dedicated learning database. The script recreates its schema.

BEGIN;

DROP SCHEMA IF EXISTS token_governance CASCADE;
CREATE SCHEMA token_governance;
SET LOCAL search_path TO token_governance, public;

CREATE TYPE session_status AS ENUM ('active', 'revoked', 'expired');
CREATE TYPE token_status AS ENUM ('active', 'rotated', 'revoked', 'expired');
CREATE TYPE check_status AS ENUM ('passed', 'failed', 'pending');

CREATE TABLE app_users (
    user_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (email = lower(trim(email)) AND position('@' IN email) > 1)
);

CREATE TABLE auth_sessions (
    session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id bigint NOT NULL REFERENCES app_users(user_id),
    status session_status NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    generation integer NOT NULL DEFAULT 0,
    current_refresh_hash text,
    client_label text NOT NULL DEFAULT 'web',
    CHECK (expires_at > created_at),
    CHECK (generation >= 0),
    CHECK (
        (status = 'revoked' AND revoked_at IS NOT NULL)
        OR (status <> 'revoked' AND revoked_at IS NULL)
    ),
    CHECK (
        current_refresh_hash IS NULL
        OR current_refresh_hash ~ '^[0-9a-f]{64}$'
    )
);

CREATE TABLE refresh_tokens (
    token_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES auth_sessions(session_id),
    token_hash text NOT NULL UNIQUE,
    generation integer NOT NULL,
    status token_status NOT NULL DEFAULT 'active',
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    replaced_by bigint REFERENCES refresh_tokens(token_id),
    CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CHECK (generation > 0),
    CHECK (expires_at > issued_at),
    CHECK (
        (status = 'rotated' AND consumed_at IS NOT NULL)
        OR status <> 'rotated'
    ),
    CHECK (replaced_by IS NULL OR status = 'rotated')
);

-- At most one active refresh token exists per session.
CREATE UNIQUE INDEX one_active_refresh_per_session
    ON refresh_tokens(session_id)
    WHERE status = 'active';

CREATE INDEX refresh_tokens_session_generation
    ON refresh_tokens(session_id, generation DESC);

CREATE TABLE access_tokens (
    token_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES auth_sessions(session_id),
    token_hash text NOT NULL UNIQUE,
    generation integer NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CHECK (generation > 0),
    CHECK (expires_at > issued_at)
);

CREATE INDEX access_tokens_session_expiry
    ON access_tokens(session_id, expires_at);

CREATE TABLE token_audit (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid REFERENCES auth_sessions(session_id),
    event_type text NOT NULL,
    generation integer,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (event_type IN (
        'session_created', 'refresh_rotated', 'refresh_reuse_detected',
        'session_revoked', 'session_expired', 'refresh_rejected'
    ))
);

CREATE INDEX token_audit_session_time
    ON token_audit(session_id, occurred_at DESC);

CREATE TABLE token_policy (
    policy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name text NOT NULL UNIQUE,
    access_ttl interval NOT NULL,
    refresh_ttl interval NOT NULL,
    revoke_on_reuse boolean NOT NULL DEFAULT true,
    enabled boolean NOT NULL DEFAULT true,
    CHECK (access_ttl > interval '0 seconds'),
    CHECK (refresh_ttl > access_ttl)
);

INSERT INTO token_policy
    (policy_name, access_ttl, refresh_ttl, revoke_on_reuse)
VALUES
    ('standard_web', interval '5 minutes', interval '8 hours', true),
    ('restricted_service', interval '1 minute', interval '30 minutes', true);

INSERT INTO app_users (email, enabled)
VALUES
    ('alice@example.com', true),
    ('bob@example.com', true),
    ('disabled@example.com', false);

-- A transactionally enforced session-creation operation.
CREATE FUNCTION create_auth_session(
    p_user_id bigint,
    p_client_label text DEFAULT 'web',
    p_policy_name text DEFAULT 'standard_web'
)
RETURNS uuid
LANGUAGE plpgsql
SET search_path = token_governance, pg_temp
AS $$
DECLARE
    v_policy token_policy%ROWTYPE;
    v_session_id uuid;
BEGIN
    SELECT * INTO v_policy
    FROM token_policy
    WHERE policy_name = p_policy_name
      AND enabled
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown or disabled token policy';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM app_users
        WHERE user_id = p_user_id AND enabled
    ) THEN
        RAISE EXCEPTION 'User is unknown or disabled';
    END IF;

    IF p_client_label IS NULL OR trim(p_client_label) = '' THEN
        RAISE EXCEPTION 'Client label is required';
    END IF;

    INSERT INTO auth_sessions (user_id, expires_at, client_label)
    VALUES (
        p_user_id,
        clock_timestamp() + v_policy.refresh_ttl,
        trim(p_client_label)
    )
    RETURNING session_id INTO v_session_id;

    INSERT INTO token_audit (session_id, event_type)
    VALUES (v_session_id, 'session_created');

    RETURN v_session_id;
END;
$$;

-- Store only hashes of randomly generated opaque credentials.
-- The application generates credentials using a cryptographically secure
-- random generator and supplies SHA-256 hashes to these functions.
CREATE FUNCTION issue_token_pair(
    p_session_id uuid,
    p_access_hash text,
    p_refresh_hash text,
    p_policy_name text DEFAULT 'standard_web'
)
RETURNS TABLE (
    access_token_id bigint,
    refresh_token_id bigint,
    access_expiry timestamptz,
    refresh_expiry timestamptz,
    token_generation integer
)
LANGUAGE plpgsql
SET search_path = token_governance, pg_temp
AS $$
DECLARE
    v_session auth_sessions%ROWTYPE;
    v_policy token_policy%ROWTYPE;
    v_access_expiry timestamptz;
    v_refresh_expiry timestamptz;
    v_generation integer;
    v_access_id bigint;
    v_refresh_id bigint;
BEGIN
    IF p_access_hash IS NULL
       OR p_refresh_hash IS NULL
       OR p_access_hash !~ '^[0-9a-f]{64}$'
       OR p_refresh_hash !~ '^[0-9a-f]{64}$'
       OR p_access_hash = p_refresh_hash THEN
        RAISE EXCEPTION 'Token hashes must be distinct SHA-256 hex strings';
    END IF;

    SELECT * INTO v_session
    FROM auth_sessions
    WHERE session_id = p_session_id
    FOR UPDATE;

    IF NOT FOUND OR v_session.status <> 'active' THEN
        RAISE EXCEPTION 'Session is missing or inactive';
    END IF;

    IF clock_timestamp() >= v_session.expires_at THEN
        UPDATE auth_sessions
        SET status = 'expired'
        WHERE session_id = p_session_id;

        INSERT INTO token_audit(session_id, event_type)
        VALUES (p_session_id, 'session_expired');

        RAISE EXCEPTION 'Session has expired';
    END IF;

    SELECT * INTO v_policy
    FROM token_policy
    WHERE policy_name = p_policy_name AND enabled
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown or disabled policy';
    END IF;

    IF EXISTS (
        SELECT 1 FROM refresh_tokens
        WHERE session_id = p_session_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Active refresh token already exists';
    END IF;

    v_generation := v_session.generation + 1;
    v_refresh_expiry := v_session.expires_at;
    v_access_expiry := LEAST(
        clock_timestamp() + v_policy.access_ttl,
        v_session.expires_at
    );

    INSERT INTO access_tokens (
        session_id, token_hash, generation, expires_at
    )
    VALUES (
        p_session_id, p_access_hash, v_generation, v_access_expiry
    )
    RETURNING token_id INTO v_access_id;

    INSERT INTO refresh_tokens (
        session_id, token_hash, generation, expires_at
    )
    VALUES (
        p_session_id, p_refresh_hash, v_generation, v_refresh_expiry
    )
    RETURNING token_id INTO v_refresh_id;

    UPDATE auth_sessions
    SET generation = v_generation,
        current_refresh_hash = p_refresh_hash
    WHERE session_id = p_session_id;

    RETURN QUERY SELECT
        v_access_id, v_refresh_id, v_access_expiry,
        v_refresh_expiry, v_generation;
END;
$$;

-- Rotation accepts only the current refresh credential.
-- The row lock serializes concurrent rotations of the same session.
CREATE FUNCTION rotate_refresh_token(
    p_refresh_hash text,
    p_new_access_hash text,
    p_new_refresh_hash text,
    p_policy_name text DEFAULT 'standard_web'
)
RETURNS TABLE (
    access_token_id bigint,
    refresh_token_id bigint,
    access_expiry timestamptz,
    refresh_expiry timestamptz,
    token_generation integer
)
LANGUAGE plpgsql
SET search_path = token_governance, pg_temp
AS $$
DECLARE
    v_token refresh_tokens%ROWTYPE;
    v_session auth_sessions%ROWTYPE;
    v_policy token_policy%ROWTYPE;
    v_new_refresh_id bigint;
    v_new_access_id bigint;
    v_new_generation integer;
    v_now timestamptz := clock_timestamp();
    v_access_expiry timestamptz;
BEGIN
    IF p_refresh_hash IS NULL
       OR p_refresh_hash !~ '^[0-9a-f]{64}$'
       OR p_new_access_hash IS NULL
       OR p_new_access_hash !~ '^[0-9a-f]{64}$'
       OR p_new_refresh_hash IS NULL
       OR p_new_refresh_hash !~ '^[0-9a-f]{64}$'
       OR p_new_access_hash = p_new_refresh_hash THEN
        RAISE EXCEPTION 'Invalid token hash input';
    END IF;

    SELECT * INTO v_token
    FROM refresh_tokens
    WHERE token_hash = p_refresh_hash;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown refresh token';
    END IF;

    SELECT * INTO v_session
    FROM auth_sessions
    WHERE session_id = v_token.session_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Session does not exist';
    END IF;

    -- Re-read the credential after obtaining the session lock.
    SELECT * INTO v_token
    FROM refresh_tokens
    WHERE token_id = v_token.token_id
    FOR UPDATE;

    IF v_session.status <> 'active' THEN
        RAISE EXCEPTION 'Session is inactive';
    END IF;

    IF v_now >= v_session.expires_at OR v_now >= v_token.expires_at THEN
        UPDATE auth_sessions
        SET status = 'expired'
        WHERE session_id = v_session.session_id;

        UPDATE refresh_tokens
        SET status = 'expired'
        WHERE token_id = v_token.token_id AND status = 'active';

        INSERT INTO token_audit(session_id, event_type, generation)
        VALUES (v_session.session_id, 'session_expired', v_session.generation);

        RAISE EXCEPTION 'Refresh session or token has expired';
    END IF;

    IF v_token.status <> 'active'
       OR v_session.current_refresh_hash IS DISTINCT FROM p_refresh_hash
       OR v_token.generation <> v_session.generation THEN

        SELECT * INTO v_policy
        FROM token_policy
        WHERE policy_name = p_policy_name AND enabled
        FOR SHARE;

        INSERT INTO token_audit (
            session_id, event_type, generation
        )
        VALUES (
            v_session.session_id, 'refresh_reuse_detected',
            v_session.generation
        );

        IF FOUND AND v_policy.revoke_on_reuse THEN
            UPDATE auth_sessions
            SET status = 'revoked', revoked_at = v_now
            WHERE session_id = v_session.session_id
              AND status = 'active';

            UPDATE refresh_tokens
            SET status = 'revoked'
            WHERE session_id = v_session.session_id
              AND status = 'active';

            INSERT INTO token_audit (
                session_id, event_type, generation
            )
            VALUES (
                v_session.session_id, 'session_revoked',
                v_session.generation
            );
        END IF;

        RAISE EXCEPTION 'Refresh-token reuse or stale token detected';
    END IF;

    SELECT * INTO v_policy
    FROM token_policy
    WHERE policy_name = p_policy_name AND enabled
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown or disabled policy';
    END IF;

    v_new_generation := v_session.generation + 1;
    v_access_expiry := LEAST(
        v_now + v_policy.access_ttl, v_session.expires_at
    );

    UPDATE refresh_tokens
    SET status = 'rotated', consumed_at = v_now
    WHERE token_id = v_token.token_id;

    INSERT INTO access_tokens (
        session_id, token_hash, generation, expires_at
    )
    VALUES (
        v_session.session_id, p_new_access_hash,
        v_new_generation, v_access_expiry
    )
    RETURNING token_id INTO v_new_access_id;

    INSERT INTO refresh_tokens (
        session_id, token_hash, generation, expires_at
    )
    VALUES (
        v_session.session_id, p_new_refresh_hash,
        v_new_generation, v_session.expires_at
    )
    RETURNING token_id INTO v_new_refresh_id;

    UPDATE refresh_tokens
    SET replaced_by = v_new_refresh_id
    WHERE token_id = v_token.token_id;

    UPDATE auth_sessions
    SET generation = v_new_generation,
        current_refresh_hash = p_new_refresh_hash
    WHERE session_id = v_session.session_id;

    INSERT INTO token_audit (
        session_id, event_type, generation
    )
    VALUES (
        v_session.session_id, 'refresh_rotated', v_new_generation
    );

    RETURN QUERY SELECT
        v_new_access_id, v_new_refresh_id, v_access_expiry,
        v_session.expires_at, v_new_generation;
END;
$$;

CREATE FUNCTION revoke_auth_session(p_session_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SET search_path = token_governance, pg_temp
AS $$
DECLARE
    v_session auth_sessions%ROWTYPE;
BEGIN
    SELECT * INTO v_session
    FROM auth_sessions
    WHERE session_id = p_session_id
    FOR UPDATE;

    IF NOT FOUND OR v_session.status = 'revoked' THEN
        RETURN false;
    END IF;

    UPDATE auth_sessions
    SET status = 'revoked', revoked_at = clock_timestamp()
    WHERE session_id = p_session_id;

    UPDATE refresh_tokens
    SET status = 'revoked'
    WHERE session_id = p_session_id AND status = 'active';

    INSERT INTO token_audit(session_id, event_type, generation)
    VALUES (p_session_id, 'session_revoked', v_session.generation);

    RETURN true;
END;
$$;

CREATE FUNCTION authenticate_access(p_access_hash text)
RETURNS TABLE (user_id bigint, session_id uuid, expires_at timestamptz)
LANGUAGE sql
STABLE
SET search_path = token_governance, pg_temp
AS $$
    SELECT s.user_id, a.session_id, a.expires_at
    FROM access_tokens AS a
    JOIN auth_sessions AS s ON s.session_id = a.session_id
    JOIN app_users AS u ON u.user_id = s.user_id
    WHERE a.token_hash = p_access_hash
      AND a.expires_at > statement_timestamp()
      AND s.expires_at > statement_timestamp()
      AND s.status = 'active'
      AND u.enabled
$$;

CREATE VIEW active_session_report AS
SELECT
    s.session_id,
    s.user_id,
    u.email,
    s.client_label,
    s.created_at,
    s.expires_at,
    s.generation,
    count(DISTINCT r.token_id) FILTER (
        WHERE r.status = 'rotated'
    ) AS rotated_refresh_tokens,
    count(DISTINCT a.token_id) FILTER (
        WHERE a.expires_at > statement_timestamp()
    ) AS unexpired_access_tokens
FROM auth_sessions AS s
JOIN app_users AS u ON u.user_id = s.user_id
LEFT JOIN refresh_tokens AS r ON r.session_id = s.session_id
LEFT JOIN access_tokens AS a ON a.session_id = s.session_id
WHERE s.status = 'active'
GROUP BY s.session_id, s.user_id, u.email;

-- This trigger prevents changing immutable credential identity or history.
CREATE FUNCTION protect_refresh_token_history()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = token_governance, pg_temp
AS $$
BEGIN
    IF NEW.session_id <> OLD.session_id
       OR NEW.token_hash <> OLD.token_hash
       OR NEW.generation <> OLD.generation
       OR NEW.issued_at <> OLD.issued_at
       OR NEW.expires_at <> OLD.expires_at THEN
        RAISE EXCEPTION 'Refresh-token identity and lifetime are immutable';
    END IF;

    IF OLD.status <> 'active' AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION 'A finalized refresh-token state cannot be changed';
    END IF;

    IF OLD.status = 'active'
       AND NEW.status = 'rotated'
       AND NEW.consumed_at IS NULL THEN
        RAISE EXCEPTION 'Rotation requires a consumption timestamp';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER refresh_token_history_guard
BEFORE UPDATE ON refresh_tokens
FOR EACH ROW
EXECUTE FUNCTION protect_refresh_token_history();

-- Demonstration data uses deterministic-looking test hashes only.
-- Never use these sample values as real authentication credentials.
DO $$
DECLARE
    alice_id bigint;
    bob_id bigint;
    disabled_id bigint;
    alice_session uuid;
    bob_session uuid;
    expired_session uuid;
BEGIN
    SELECT user_id INTO alice_id FROM app_users
    WHERE email = 'alice@example.com';

    SELECT user_id INTO bob_id FROM app_users
    WHERE email = 'bob@example.com';

    SELECT user_id INTO disabled_id FROM app_users
    WHERE email = 'disabled@example.com';

    alice_session := create_auth_session(alice_id, 'alice-browser');
    PERFORM issue_token_pair(
        alice_session,
        repeat('1', 64),
        repeat('2', 64)
    );

    PERFORM rotate_refresh_token(
        repeat('2', 64),
        repeat('3', 64),
        repeat('4', 64)
    );

    bob_session := create_auth_session(bob_id, 'bob-mobile');
    PERFORM issue_token_pair(
        bob_session,
        repeat('5', 64),
        repeat('6', 64)
    );

    -- A disabled user cannot start a new session.
    BEGIN
        PERFORM create_auth_session(disabled_id, 'disabled-browser');
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'Disabled-user session creation rejected';
    END;

    -- Deliberately age a session to represent an expired lifecycle state.
    expired_session := create_auth_session(bob_id, 'expired-test');
    UPDATE auth_sessions
    SET expires_at = clock_timestamp() - interval '1 second'
    WHERE session_id = expired_session;

    UPDATE auth_sessions
    SET status = 'expired'
    WHERE session_id = expired_session;

    INSERT INTO token_audit(session_id, event_type)
    VALUES (expired_session, 'session_expired');

    -- A revoked session can no longer authenticate.
    PERFORM revoke_auth_session(bob_session);

    -- Attempt to reuse the original, rotated refresh token. The call is
    -- isolated in a subtransaction so the demonstration can continue.
    BEGIN
        PERFORM rotate_refresh_token(
            repeat('2', 64),
            repeat('7', 64),
            repeat('8', 64)
        );
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'Rotated refresh-token reuse rejected';
    END;
END;
$$;

-- Retrieval: active sessions and their rotation history.
SELECT * FROM active_session_report ORDER BY created_at;

-- Authentication check: returns a row only for a valid, active session.
SELECT * FROM authenticate_access(repeat('3', 64));

-- Lifecycle reporting: each session's state and generation.
SELECT
    session_id, user_id, status, generation, expires_at,
    (expires_at <= statement_timestamp()) AS time_expired
FROM auth_sessions
ORDER BY created_at;

-- Review token generations and replacement links.
SELECT
    s.session_id,
    r.generation,
    r.status,
    r.issued_at,
    r.consumed_at,
    r.replaced_by
FROM refresh_tokens AS r
JOIN auth_sessions AS s USING (session_id)
ORDER BY s.created_at, r.generation;

-- Aggregate audit events by type and date.
SELECT
    date_trunc('day', occurred_at) AS event_day,
    event_type,
    count(*) AS event_count
FROM token_audit
GROUP BY 1, 2
ORDER BY 1, 2;

-- Detect active sessions without a current active refresh token.
SELECT s.session_id, s.user_id, s.generation
FROM auth_sessions AS s
LEFT JOIN refresh_tokens AS r
    ON r.session_id = s.session_id
   AND r.status = 'active'
WHERE s.status = 'active'
GROUP BY s.session_id, s.user_id, s.generation
HAVING count(r.token_id) <> 1;

COMMIT;

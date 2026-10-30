-- ================================================================
-- API KEY MANAGEMENT
-- PostgreSQL 15+
--
-- Security boundary:
--   1. The application generates the random key secret.
--   2. The application computes HMAC-SHA-256 using an external pepper.
--   3. PostgreSQL stores only the 32-byte verifier.
--   4. The trusted application retrieves the verifier through a
--      restricted function and performs a constant-time comparison.
--   5. PostgreSQL evaluates lifecycle state, expiration, ownership,
--      and scope eligibility after successful cryptographic validation.
--
-- The database never receives or stores the plaintext API key.
-- ================================================================

DROP SCHEMA IF EXISTS api_key_mgmt CASCADE;
CREATE SCHEMA api_key_mgmt;

SET search_path = api_key_mgmt, public;

CREATE TYPE key_status AS ENUM (
    'active',
    'revoked'
);

CREATE TABLE principals (
    principal_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    principal_type TEXT NOT NULL
        CHECK (principal_type IN ('service', 'application', 'integration')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CHECK (length(principal_id) BETWEEN 1 AND 120),
    CHECK (length(display_name) BETWEEN 1 AND 160)
);

CREATE TABLE api_keys (
    key_pk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Public identifier. It is not sufficient to authenticate a request.
    key_id TEXT NOT NULL UNIQUE
        CHECK (key_id ~ '^ak_live_[a-f0-9]{16}$'),

    owner_id TEXT NOT NULL
        REFERENCES principals(principal_id),

    label TEXT NOT NULL
        CHECK (length(label) BETWEEN 1 AND 120),

    -- HMAC-SHA-256 verifier, not the original API key.
    verifier BYTEA NOT NULL
        CHECK (octet_length(verifier) = 32),

    status key_status NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,

    rotated_from BIGINT
        REFERENCES api_keys(key_pk),

    CONSTRAINT valid_key_expiration
        CHECK (expires_at IS NULL OR expires_at > created_at),

    CONSTRAINT valid_revocation_state
        CHECK (
            (status = 'active' AND revoked_at IS NULL)
            OR
            (status = 'revoked' AND revoked_at IS NOT NULL)
        )
);

CREATE TABLE api_key_scopes (
    key_pk BIGINT NOT NULL
        REFERENCES api_keys(key_pk),

    scope TEXT NOT NULL
        CHECK (scope ~ '^[a-z][a-z0-9:_-]{0,63}$'),

    PRIMARY KEY (key_pk, scope)
);

CREATE TABLE api_key_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    key_pk BIGINT NOT NULL
        REFERENCES api_keys(key_pk),

    event_type TEXT NOT NULL
        CHECK (
            event_type IN (
                'issued',
                'revoked',
                'rotated',
                'access_review'
            )
        ),

    actor_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CHECK (jsonb_typeof(details) = 'object')
);

-- Owner inventory and expiry scans.
CREATE INDEX idx_api_keys_owner_created
    ON api_keys(owner_id, created_at DESC);

CREATE INDEX idx_api_keys_active_expiration
    ON api_keys(expires_at)
    WHERE status = 'active';

-- Scope checks and permission reporting.
CREATE INDEX idx_api_key_scopes_scope
    ON api_key_scopes(scope, key_pk);

-- Audit retrieval by key and time.
CREATE INDEX idx_api_key_events_key_time
    ON api_key_events(key_pk, occurred_at DESC);

COMMENT ON TABLE api_keys IS
'Stores public key identifiers, HMAC verifiers, ownership, and lifecycle state. Never stores plaintext API keys.';

COMMENT ON COLUMN api_keys.verifier IS
'32-byte HMAC-SHA-256 verifier computed by the trusted application using an externally protected pepper.';

COMMENT ON TABLE api_key_scopes IS
'Stores normalized permissions granted to each API key.';

COMMENT ON TABLE api_key_events IS
'Append-only lifecycle audit records. Event details must never contain API key secrets or verifier values.';


-- ================================================================
-- DATABASE-LEVEL STATE AND AUDIT ENFORCEMENT
-- ================================================================

CREATE FUNCTION enforce_key_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Identity and verifier are immutable after issuance.
        IF NEW.key_id IS DISTINCT FROM OLD.key_id
           OR NEW.verifier IS DISTINCT FROM OLD.verifier
           OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.rotated_from IS DISTINCT FROM OLD.rotated_from
        THEN
            RAISE EXCEPTION
                'Key identity, verifier, owner, creation time, and rotation origin are immutable';
        END IF;

        -- Revocation is irreversible.
        IF OLD.status = 'revoked' AND NEW.status <> 'revoked' THEN
            RAISE EXCEPTION 'A revoked API key cannot be reactivated';
        END IF;

        IF OLD.status = 'active' AND NEW.status = 'revoked' THEN
            NEW.revoked_at := clock_timestamp();
        ELSIF NEW.status = 'active' THEN
            NEW.revoked_at := NULL;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_enforce_key_state
BEFORE UPDATE ON api_keys
FOR EACH ROW
EXECUTE FUNCTION enforce_key_state();


CREATE FUNCTION audit_key_lifecycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_type TEXT;
    v_actor TEXT;
    v_details JSONB;
BEGIN
    v_actor := COALESCE(
        NULLIF(current_setting('api_key.actor', TRUE), ''),
        session_user
    );

    IF TG_OP = 'INSERT' THEN
        v_event_type := 'issued';

        v_details := jsonb_build_object(
            'label', NEW.label,
            'owner_id', NEW.owner_id,
            'rotated_from', NEW.rotated_from
        );

        INSERT INTO api_key_events(
            key_pk,
            event_type,
            actor_id,
            details
        )
        VALUES (
            NEW.key_pk,
            v_event_type,
            v_actor,
            v_details
        );

    ELSIF TG_OP = 'UPDATE'
       AND OLD.status IS DISTINCT FROM NEW.status
       AND NEW.status = 'revoked'
    THEN
        v_event_type := 'revoked';

        v_details := jsonb_build_object(
            'label', NEW.label,
            'owner_id', NEW.owner_id
        );

        INSERT INTO api_key_events(
            key_pk,
            event_type,
            actor_id,
            details
        )
        VALUES (
            NEW.key_pk,
            v_event_type,
            v_actor,
            v_details
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_key_lifecycle
AFTER INSERT OR UPDATE ON api_keys
FOR EACH ROW
EXECUTE FUNCTION audit_key_lifecycle();


-- Prevent ordinary deletion of lifecycle and audit records.
CREATE FUNCTION prevent_key_history_deletion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'API key history cannot be deleted through ordinary application operations';
END;
$$;

CREATE TRIGGER trg_prevent_api_key_delete
BEFORE DELETE ON api_keys
FOR EACH ROW
EXECUTE FUNCTION prevent_key_history_deletion();

CREATE TRIGGER trg_prevent_key_event_delete
BEFORE DELETE ON api_key_events
FOR EACH ROW
EXECUTE FUNCTION prevent_key_history_deletion();


-- ================================================================
-- ISSUANCE
--
-- The application supplies:
--   key_id: public identifier generated from secure random bytes
--   verifier: HMAC-SHA-256 digest of the secret using an external pepper
--   scopes: normalized permissions
--
-- The plaintext token is returned to the application only once by
-- its own issuance layer. PostgreSQL does not construct it.
-- ================================================================

CREATE FUNCTION issue_api_key(
    p_owner_id TEXT,
    p_key_id TEXT,
    p_verifier BYTEA,
    p_label TEXT,
    p_scopes TEXT[],
    p_expires_at TIMESTAMPTZ,
    p_actor_id TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = api_key_mgmt, pg_temp
AS $$
DECLARE
    v_key_pk BIGINT;
    v_scope TEXT;
    v_scope_count INTEGER;
BEGIN
    IF p_owner_id IS NULL OR length(trim(p_owner_id)) NOT BETWEEN 1 AND 120 THEN
        RAISE EXCEPTION 'Invalid API key owner';
    END IF;

    IF p_label IS NULL OR length(trim(p_label)) NOT BETWEEN 1 AND 120 THEN
        RAISE EXCEPTION 'Invalid API key label';
    END IF;

    IF p_actor_id IS NULL OR length(trim(p_actor_id)) NOT BETWEEN 1 AND 120 THEN
        RAISE EXCEPTION 'Invalid actor';
    END IF;

    IF p_key_id !~ '^ak_live_[a-f0-9]{16}$' THEN
        RAISE EXCEPTION 'Invalid public API key identifier';
    END IF;

    IF p_verifier IS NULL OR octet_length(p_verifier) <> 32 THEN
        RAISE EXCEPTION 'The HMAC verifier must contain 32 bytes';
    END IF;

    IF p_expires_at IS NOT NULL AND p_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'Expiration must be in the future';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM principals
        WHERE principal_id = p_owner_id
          AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'API key owner does not exist or is inactive';
    END IF;

    IF p_scopes IS NULL OR cardinality(p_scopes) = 0 THEN
        RAISE EXCEPTION 'At least one API key scope is required';
    END IF;

    SELECT count(DISTINCT scope)
    INTO v_scope_count
    FROM unnest(p_scopes) AS scope
    WHERE scope ~ '^[a-z][a-z0-9:_-]{0,63}$';

    IF v_scope_count <> cardinality(p_scopes) THEN
        RAISE EXCEPTION 'Scopes must be valid and contain no duplicates';
    END IF;

    PERFORM set_config('api_key.actor', p_actor_id, TRUE);

    INSERT INTO api_keys (
        key_id,
        owner_id,
        label,
        verifier,
        status,
        expires_at
    )
    VALUES (
        p_key_id,
        p_owner_id,
        trim(p_label),
        p_verifier,
        'active',
        p_expires_at
    )
    RETURNING key_pk INTO v_key_pk;

    FOREACH v_scope IN ARRAY p_scopes LOOP
        INSERT INTO api_key_scopes(key_pk, scope)
        VALUES (v_key_pk, v_scope);
    END LOOP;

    RETURN v_key_pk;
END;
$$;


-- ================================================================
-- VERIFIER RETRIEVAL
--
-- This function is for a trusted authentication service only.
-- The caller must perform a constant-time comparison in application
-- code. It must never expose the verifier to an API client.
--
-- PUBLIC execution is revoked below. Production administrators
-- should grant execution only to the restricted authentication role.
-- ================================================================

CREATE FUNCTION get_api_key_verifier(p_key_id TEXT)
RETURNS BYTEA
LANGUAGE sql
SECURITY DEFINER
SET search_path = api_key_mgmt, pg_temp
AS $$
    SELECT verifier
    FROM api_keys
    WHERE key_id = p_key_id
      AND status = 'active';
$$;


-- ================================================================
-- ELIGIBILITY EVALUATION
--
-- This function evaluates repository state, not the cryptographic
-- secret. Call it only after the application has verified the secret.
-- ================================================================

CREATE FUNCTION evaluate_key_eligibility(
    p_key_id TEXT,
    p_required_scope TEXT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT,
    owner_id TEXT,
    granted_scopes TEXT[]
)
LANGUAGE plpgsql
STABLE
SET search_path = api_key_mgmt, pg_temp
AS $$
DECLARE
    v_key api_keys%ROWTYPE;
    v_scopes TEXT[];
BEGIN
    IF p_required_scope IS NULL
       OR p_required_scope !~ '^[a-z][a-z0-9:_-]{0,63}$'
    THEN
        RETURN QUERY
        SELECT FALSE, 'invalid_scope'::TEXT, NULL::TEXT, ARRAY[]::TEXT[];
        RETURN;
    END IF;

    SELECT *
    INTO v_key
    FROM api_keys
    WHERE key_id = p_key_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'unknown_key'::TEXT, NULL::TEXT, ARRAY[]::TEXT[];
        RETURN;
    END IF;

    SELECT COALESCE(array_agg(scope ORDER BY scope), ARRAY[]::TEXT[])
    INTO v_scopes
    FROM api_key_scopes
    WHERE key_pk = v_key.key_pk;

    IF v_key.status <> 'active' THEN
        RETURN QUERY
        SELECT FALSE, 'revoked'::TEXT, v_key.owner_id, v_scopes;
        RETURN;
    END IF;

    IF v_key.expires_at IS NOT NULL
       AND v_key.expires_at <= clock_timestamp()
    THEN
        RETURN QUERY
        SELECT FALSE, 'expired'::TEXT, v_key.owner_id, v_scopes;
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM principals
        WHERE principal_id = v_key.owner_id
          AND is_active = TRUE
    ) THEN
        RETURN QUERY
        SELECT FALSE, 'inactive_owner'::TEXT, v_key.owner_id, v_scopes;
        RETURN;
    END IF;

    IF NOT (
        p_required_scope = ANY(v_scopes)
        OR '*' = ANY(v_scopes)
    ) THEN
        RETURN QUERY
        SELECT FALSE, 'insufficient_scope'::TEXT, v_key.owner_id, v_scopes;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'accepted'::TEXT, v_key.owner_id, v_scopes;
END;
$$;


-- ================================================================
-- SUCCESSFUL USE RECORDING
--
-- Call only after the application has:
--   1. Parsed the supplied token.
--   2. Retrieved the verifier using the restricted function.
--   3. Recomputed HMAC-SHA-256 using its protected pepper.
--   4. Compared the values in constant time.
--
-- The conditional UPDATE rechecks lifecycle and scope conditions
-- while acquiring a row lock. It prevents a revoked key from being
-- recorded as a successful use after a concurrent revocation.
-- ================================================================

CREATE FUNCTION record_successful_key_use(
    p_key_id TEXT,
    p_required_scope TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = api_key_mgmt, pg_temp
AS $$
DECLARE
    v_updated BOOLEAN;
BEGIN
    UPDATE api_keys k
    SET last_used_at = clock_timestamp()
    WHERE k.key_id = p_key_id
      AND k.status = 'active'
      AND (
          k.expires_at IS NULL
          OR k.expires_at > clock_timestamp()
      )
      AND EXISTS (
          SELECT 1
          FROM principals p
          WHERE p.principal_id = k.owner_id
            AND p.is_active = TRUE
      )
      AND EXISTS (
          SELECT 1
          FROM api_key_scopes s
          WHERE s.key_pk = k.key_pk
            AND (
                s.scope = p_required_scope
                OR s.scope = '*'
            )
      );

    v_updated := FOUND;
    RETURN v_updated;
END;
$$;


-- ================================================================
-- REVOCATION
--
-- Revocation is idempotent. An already revoked key returns FALSE.
-- ================================================================

CREATE FUNCTION revoke_api_key(
    p_key_id TEXT,
    p_actor_id TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = api_key_mgmt, pg_temp
AS $$
DECLARE
    v_key_pk BIGINT;
BEGIN
    PERFORM set_config('api_key.actor', p_actor_id, TRUE);

    SELECT key_pk
    INTO v_key_pk
    FROM api_keys
    WHERE key_id = p_key_id
      AND status = 'active'
    FOR UPDATE;

    IF NOT FOUND THEN
        IF EXISTS (
            SELECT 1
            FROM api_keys
            WHERE key_id = p_key_id
        ) THEN
            RETURN FALSE;
        END IF;

        RAISE EXCEPTION 'API key does not exist';
    END IF;

    UPDATE api_keys
    SET status = 'revoked'
    WHERE key_pk = v_key_pk;

    RETURN TRUE;
END;
$$;


-- ================================================================
-- ROTATION
--
-- The application authenticates the old secret before calling this
-- function. This function locks the old row, creates a replacement
-- using a new application-generated verifier, copies the old scopes,
-- and revokes the previous key in the same database transaction.
-- ================================================================

CREATE FUNCTION rotate_api_key(
    p_old_key_id TEXT,
    p_new_key_id TEXT,
    p_new_verifier BYTEA,
    p_new_expires_at TIMESTAMPTZ,
    p_actor_id TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = api_key_mgmt, pg_temp
AS $$
DECLARE
    v_old api_keys%ROWTYPE;
    v_new_key_pk BIGINT;
    v_scopes TEXT[];
BEGIN
    PERFORM set_config('api_key.actor', p_actor_id, TRUE);

    SELECT *
    INTO v_old
    FROM api_keys
    WHERE key_id = p_old_key_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The old API key does not exist';
    END IF;

    IF v_old.status <> 'active' THEN
        RAISE EXCEPTION 'Only an active key can be rotated';
    END IF;

    IF v_old.expires_at IS NOT NULL
       AND v_old.expires_at <= clock_timestamp()
    THEN
        RAISE EXCEPTION 'An expired key cannot be rotated';
    END IF;

    IF p_new_key_id !~ '^ak_live_[a-f0-9]{16}$' THEN
        RAISE EXCEPTION 'Invalid replacement key identifier';
    END IF;

    IF p_new_verifier IS NULL
       OR octet_length(p_new_verifier) <> 32
    THEN
        RAISE EXCEPTION 'Invalid replacement verifier';
    END IF;

    IF p_new_expires_at IS NOT NULL
       AND p_new_expires_at <= clock_timestamp()
    THEN
        RAISE EXCEPTION 'Replacement expiration must be in the future';
    END IF;

    SELECT array_agg(scope ORDER BY scope)
    INTO v_scopes
    FROM api_key_scopes
    WHERE key_pk = v_old.key_pk;

    IF v_scopes IS NULL OR cardinality(v_scopes) = 0 THEN
        RAISE EXCEPTION 'The old key has no scopes to transfer';
    END IF;

    v_new_key_pk := issue_api_key(
        v_old.owner_id,
        p_new_key_id,
        p_new_verifier,
        v_old.label,
        v_scopes,
        p_new_expires_at,
        p_actor_id
    );

    UPDATE api_keys
    SET status = 'revoked'
    WHERE key_pk = v_old.key_pk;

    INSERT INTO api_key_events(
        key_pk,
        event_type,
        actor_id,
        details
    )
    VALUES (
        v_old.key_pk,
        'rotated',
        p_actor_id,
        jsonb_build_object(
            'replacement_key_id', p_new_key_id
        )
    );

    RETURN p_new_key_id;
END;
$$;


-- ================================================================
-- REPORTING
-- ================================================================

CREATE VIEW api_key_inventory AS
SELECT
    k.key_id,
    k.owner_id,
    p.display_name AS owner_name,
    p.principal_type,
    k.label,
    k.status,
    array_agg(s.scope ORDER BY s.scope) AS scopes,
    k.created_at,
    k.expires_at,
    k.last_used_at,
    k.revoked_at,
    previous.key_id AS rotated_from_key_id
FROM api_keys k
JOIN principals p
    ON p.principal_id = k.owner_id
LEFT JOIN api_key_scopes s
    ON s.key_pk = k.key_pk
LEFT JOIN api_keys previous
    ON previous.key_pk = k.rotated_from
GROUP BY
    k.key_pk,
    k.key_id,
    k.owner_id,
    p.display_name,
    p.principal_type,
    k.label,
    k.status,
    k.created_at,
    k.expires_at,
    k.last_used_at,
    k.revoked_at,
    previous.key_id;

CREATE VIEW api_key_usage_report AS
SELECT
    p.principal_id,
    p.display_name,
    count(k.key_pk) AS total_keys,
    count(k.key_pk) FILTER (
        WHERE k.status = 'active'
          AND (
              k.expires_at IS NULL
              OR k.expires_at > clock_timestamp()
          )
    ) AS currently_usable_keys,
    count(k.key_pk) FILTER (
        WHERE k.status = 'revoked'
    ) AS revoked_keys,
    count(k.key_pk) FILTER (
        WHERE k.status = 'active'
          AND k.expires_at IS NOT NULL
          AND k.expires_at <= clock_timestamp()
    ) AS expired_keys,
    max(k.last_used_at) AS latest_key_use
FROM principals p
LEFT JOIN api_keys k
    ON k.owner_id = p.principal_id
GROUP BY p.principal_id, p.display_name;


-- ================================================================
-- PERMISSIONS
--
-- PUBLIC receives no access to verifier retrieval or lifecycle
-- administration functions. Production deployment must grant only
-- the minimum required functions to specific database roles.
-- ================================================================

REVOKE ALL ON SCHEMA api_key_mgmt FROM PUBLIC;
GRANT USAGE ON SCHEMA api_key_mgmt TO PUBLIC;

REVOKE ALL ON FUNCTION get_api_key_verifier(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION issue_api_key(
    TEXT, TEXT, BYTEA, TEXT, TEXT[], TIMESTAMPTZ, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION revoke_api_key(TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION rotate_api_key(
    TEXT, TEXT, BYTEA, TIMESTAMPTZ, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION record_successful_key_use(TEXT, TEXT) FROM PUBLIC;

COMMENT ON FUNCTION get_api_key_verifier(TEXT) IS
'Restricted authentication-service function. Returned verifier bytes must never be exposed to an API client.';

COMMENT ON FUNCTION record_successful_key_use(TEXT, TEXT) IS
'Call only after successful constant-time HMAC verification in the trusted application.';


-- ================================================================
-- SAMPLE DATA
-- ================================================================

INSERT INTO principals(
    principal_id,
    display_name,
    principal_type,
    is_active
)
VALUES
    (
        'inventory-service',
        'Warehouse Inventory Service',
        'service',
        TRUE
    ),
    (
        'billing-service',
        'Billing Integration',
        'service',
        TRUE
    ),
    (
        'retired-integration',
        'Retired External Integration',
        'integration',
        FALSE
    );


-- Issue a key through the controlled issuance function.
-- The verifier values below are sample digests, not usable secrets.

SELECT issue_api_key(
    'inventory-service',
    'ak_live_0123456789abcdef',
    decode(repeat('ab', 32), 'hex'),
    'warehouse integration',
    ARRAY['inventory:read', 'inventory:update'],
    clock_timestamp() + INTERVAL '30 days',
    'platform-admin'
);

SELECT issue_api_key(
    'billing-service',
    'ak_live_1123456789abcdef',
    decode(repeat('cd', 32), 'hex'),
    'billing reporting',
    ARRAY['billing:read'],
    clock_timestamp() + INTERVAL '90 days',
    'platform-admin'
);


-- Demonstrate an expired key.
-- Historical records remain available for audit and investigation.

INSERT INTO api_keys(
    key_id,
    owner_id,
    label,
    verifier,
    status,
    created_at,
    expires_at
)
VALUES (
    'ak_live_2123456789abcdef',
    'inventory-service',
    'expired warehouse credential',
    decode(repeat('ef', 32), 'hex'),
    'active',
    clock_timestamp() - INTERVAL '10 days',
    clock_timestamp() - INTERVAL '1 day'
);

INSERT INTO api_key_scopes(key_pk, scope)
SELECT key_pk, 'inventory:read'
FROM api_keys
WHERE key_id = 'ak_live_2123456789abcdef';


-- Demonstrate a key issued to an inactive principal being rejected.
DO $$
BEGIN
    BEGIN
        PERFORM issue_api_key(
            'retired-integration',
            'ak_live_3123456789abcdef',
            decode(repeat('11', 32), 'hex'),
            'retired credential',
            ARRAY['inventory:read'],
            clock_timestamp() + INTERVAL '10 days',
            'platform-admin'
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected issuance rejection: %', SQLERRM;
    END;
END;
$$;


-- ================================================================
-- VALIDATION AND ELIGIBILITY QUERIES
-- ================================================================

-- The authentication service retrieves the verifier after parsing
-- a token and extracting its public key identifier.
-- It computes the candidate HMAC and compares it in constant time.

SELECT encode(
    get_api_key_verifier('ak_live_0123456789abcdef'),
    'hex'
) AS verifier_for_trusted_authentication_service;


-- Successful policy eligibility for a permitted scope.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_0123456789abcdef',
    'inventory:read'
);


-- Insufficient permission.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_0123456789abcdef',
    'billing:write'
);


-- Expiration failure.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_2123456789abcdef',
    'inventory:read'
);


-- Unknown public key identifier.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_9999999999999999',
    'inventory:read'
);


-- Simulate successful application-side cryptographic verification.
-- This function records usage and rechecks lifecycle policy.

SELECT record_successful_key_use(
    'ak_live_0123456789abcdef',
    'inventory:read'
) AS usage_recorded;


-- A scope not granted to the key cannot be recorded as successful use.
SELECT record_successful_key_use(
    'ak_live_0123456789abcdef',
    'billing:write'
) AS unauthorized_usage_recorded;


-- ================================================================
-- ROTATION AND REVOCATION
-- ================================================================

SELECT rotate_api_key(
    'ak_live_0123456789abcdef',
    'ak_live_4123456789abcdef',
    decode(repeat('42', 32), 'hex'),
    clock_timestamp() + INTERVAL '60 days',
    'security-admin'
) AS replacement_key_id;


-- The original key is revoked after the rotation transaction.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_0123456789abcdef',
    'inventory:read'
);


-- The replacement retains the old key's scopes.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_4123456789abcdef',
    'inventory:read'
);


-- Revocation is permanent and idempotent.
SELECT revoke_api_key(
    'ak_live_4123456789abcdef',
    'security-admin'
) AS first_revocation;

SELECT revoke_api_key(
    'ak_live_4123456789abcdef',
    'security-admin'
) AS repeated_revocation;


-- A revoked key cannot become eligible again.
SELECT *
FROM evaluate_key_eligibility(
    'ak_live_4123456789abcdef',
    'inventory:read'
);


-- ================================================================
-- INVENTORY, AGGREGATION, AND AUDIT REPORTING
-- ================================================================

SELECT *
FROM api_key_inventory
ORDER BY owner_id, created_at DESC;

SELECT *
FROM api_key_usage_report
ORDER BY principal_id;

SELECT
    event_type,
    actor_id,
    count(*) AS event_count
FROM api_key_events
GROUP BY event_type, actor_id
ORDER BY actor_id, event_type;

SELECT
    k.key_id,
    k.owner_id,
    k.label,
    e.event_type,
    e.actor_id,
    e.occurred_at,
    e.details
FROM api_keys k
JOIN api_key_events e
    ON e.key_pk = k.key_pk
ORDER BY k.key_id, e.occurred_at;


-- ================================================================
-- TRANSACTIONAL FAILURE HANDLING
-- ================================================================

-- A failed issuance rolls back all inserted rows and audit events.
DO $$
BEGIN
    BEGIN
        PERFORM issue_api_key(
            'inventory-service',
            'ak_live_5123456789abcdef',
            decode(repeat('51', 32), 'hex'),
            'invalid empty scope test',
            ARRAY[]::TEXT[],
            clock_timestamp() + INTERVAL '30 days',
            'security-admin'
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected issuance failure: %', SQLERRM;
    END;
END;
$$;

-- The resulting inventory remains consistent.
SELECT
    key_id,
    status,
    created_at,
    expires_at
FROM api_keys
ORDER BY created_at;


-- ================================================================
-- OPERATIONAL SECURITY NOTES
-- ================================================================
-- 1. Keep API_KEY_PEPPER in a secret manager, not in this database.
-- 2. Do not grant general table SELECT access to application clients.
-- 3. Grant get_api_key_verifier only to the authentication service.
-- 4. Perform HMAC comparison with a constant-time application API.
-- 5. Call record_successful_key_use only after secret verification.
-- 6. Use TLS for application-to-database connections.
-- 7. Restrict issuance, rotation, and revocation functions to operators.
-- 8. Protect audit tables from application modification.
-- 9. Back up the database and pepper independently.
-- 10. Apply a key-expiration and rotation policy to all service owners.
-- ================================================================

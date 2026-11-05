-- ============================================================
-- RATE LIMITING DATABASE
-- PostgreSQL 15+
--
-- Implements:
-- 1. Fixed window rate limiting
-- 2. Sliding window rate limiting
-- 3. Token bucket rate limiting
-- 4. Distributed rate limiting using shared database state
-- 5. API gateway policies
-- 6. Request auditing and reporting
--
-- The shared PostgreSQL database coordinates multiple
-- application instances through row-level locking.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS rate_limiting;

SET search_path TO rate_limiting, public;

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE algorithm_type AS ENUM (
    'FIXED_WINDOW',
    'SLIDING_WINDOW',
    'TOKEN_BUCKET'
);

CREATE TYPE decision_type AS ENUM (
    'ALLOWED',
    'BLOCKED'
);

CREATE TYPE endpoint_status AS ENUM (
    'ACTIVE',
    'DISABLED'
);

-- ============================================================
-- APPLICATION CLIENTS
-- ============================================================

CREATE TABLE clients (
    client_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_key VARCHAR(100) NOT NULL UNIQUE,
    client_name VARCHAR(150) NOT NULL,
    client_tier VARCHAR(30) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_client_tier
        CHECK (
            client_tier IN (
                'FREE',
                'STANDARD',
                'PREMIUM',
                'ENTERPRISE'
            )
        )
);

-- ============================================================
-- API ENDPOINTS
-- ============================================================

CREATE TABLE api_endpoints (
    endpoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    endpoint_path VARCHAR(200) NOT NULL UNIQUE,
    endpoint_name VARCHAR(100) NOT NULL,
    status endpoint_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- RATE LIMIT POLICIES
-- ============================================================

CREATE TABLE rate_limit_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(100) NOT NULL UNIQUE,

    endpoint_id BIGINT NOT NULL
        REFERENCES api_endpoints(endpoint_id),

    algorithm algorithm_type NOT NULL,

    request_limit INTEGER NOT NULL,

    window_seconds NUMERIC(12, 3) NOT NULL,

    bucket_capacity NUMERIC(12, 3),

    refill_rate NUMERIC(12, 6),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_request_limit
        CHECK (request_limit > 0),

    CONSTRAINT positive_window
        CHECK (window_seconds > 0),

    CONSTRAINT valid_bucket_configuration
        CHECK (
            (
                algorithm = 'TOKEN_BUCKET'
                AND bucket_capacity > 0
                AND refill_rate > 0
            )
            OR
            (
                algorithm <> 'TOKEN_BUCKET'
                AND bucket_capacity IS NULL
                AND refill_rate IS NULL
            )
        )
);

CREATE INDEX idx_policies_endpoint_enabled
    ON rate_limit_policies(endpoint_id, enabled);

-- ============================================================
-- CLIENT POLICY ASSIGNMENTS
-- ============================================================

CREATE TABLE client_policy_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    client_id BIGINT NOT NULL
        REFERENCES clients(client_id),

    policy_id BIGINT NOT NULL
        REFERENCES rate_limit_policies(policy_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(client_id, policy_id)
);

CREATE INDEX idx_assignments_client
    ON client_policy_assignments(client_id);

-- ============================================================
-- FIXED WINDOW STATE
-- ============================================================

CREATE TABLE fixed_window_state (
    policy_id BIGINT NOT NULL
        REFERENCES rate_limit_policies(policy_id),

    client_id BIGINT NOT NULL
        REFERENCES clients(client_id),

    window_start TIMESTAMPTZ NOT NULL,

    request_count INTEGER NOT NULL DEFAULT 0,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY(policy_id, client_id),

    CONSTRAINT nonnegative_fixed_count
        CHECK(request_count >= 0)
);

-- ============================================================
-- SLIDING WINDOW REQUEST LOG
-- ============================================================

CREATE TABLE sliding_window_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_id BIGINT NOT NULL
        REFERENCES rate_limit_policies(policy_id),

    client_id BIGINT NOT NULL
        REFERENCES clients(client_id),

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    request_cost INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT positive_event_cost
        CHECK(request_cost > 0)
);

CREATE INDEX idx_sliding_events_lookup
    ON sliding_window_events(
        policy_id,
        client_id,
        occurred_at
    );

-- ============================================================
-- TOKEN BUCKET STATE
-- ============================================================

CREATE TABLE token_bucket_state (
    policy_id BIGINT NOT NULL
        REFERENCES rate_limit_policies(policy_id),

    client_id BIGINT NOT NULL
        REFERENCES clients(client_id),

    tokens NUMERIC(18, 6) NOT NULL,

    last_refill_at TIMESTAMPTZ NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY(policy_id, client_id),

    CONSTRAINT nonnegative_tokens
        CHECK(tokens >= 0)
);

-- ============================================================
-- REQUEST AUDIT
-- ============================================================

CREATE TABLE request_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id UUID NOT NULL UNIQUE,

    client_id BIGINT NOT NULL
        REFERENCES clients(client_id),

    policy_id BIGINT NOT NULL
        REFERENCES rate_limit_policies(policy_id),

    algorithm algorithm_type NOT NULL,

    decision decision_type NOT NULL,

    request_cost INTEGER NOT NULL,

    remaining_quota NUMERIC(18, 6) NOT NULL,

    retry_after_seconds NUMERIC(18, 6) NOT NULL DEFAULT 0,

    application_instance VARCHAR(100) NOT NULL,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT positive_audit_cost
        CHECK(request_cost > 0),

    CONSTRAINT nonnegative_remaining
        CHECK(remaining_quota >= 0),

    CONSTRAINT nonnegative_retry
        CHECK(retry_after_seconds >= 0)
);

CREATE INDEX idx_audit_client_time
    ON request_audit(client_id, requested_at DESC);

CREATE INDEX idx_audit_decision_time
    ON request_audit(decision, requested_at DESC);

CREATE INDEX idx_audit_policy_time
    ON request_audit(policy_id, requested_at DESC);

-- ============================================================
-- AUDIT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION validate_request_audit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actual_algorithm algorithm_type;
BEGIN
    SELECT algorithm
    INTO actual_algorithm
    FROM rate_limit_policies
    WHERE policy_id = NEW.policy_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rate limit policy does not exist.';
    END IF;

    IF actual_algorithm <> NEW.algorithm THEN
        RAISE EXCEPTION
            'Audit algorithm does not match policy algorithm.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_request_audit
BEFORE INSERT ON request_audit
FOR EACH ROW
EXECUTE FUNCTION validate_request_audit();

-- ============================================================
-- SHARED RATE LIMITING EVALUATION FUNCTION
--
-- Each request runs in the caller's transaction.
-- State changes and audit insertion commit together.
-- Concurrent application instances coordinate through
-- INSERT ... ON CONFLICT and SELECT ... FOR UPDATE.
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_rate_limit(
    p_client_id BIGINT,
    p_policy_id BIGINT,
    p_cost INTEGER DEFAULT 1,
    p_instance VARCHAR DEFAULT 'api-server-1'
)
RETURNS TABLE (
    allowed BOOLEAN,
    algorithm algorithm_type,
    remaining NUMERIC,
    retry_after_seconds NUMERIC,
    decision decision_type
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_policy rate_limit_policies%ROWTYPE;

    v_now TIMESTAMPTZ := clock_timestamp();

    v_window_start TIMESTAMPTZ;
    v_cutoff TIMESTAMPTZ;

    v_count BIGINT;
    v_oldest TIMESTAMPTZ;

    v_tokens NUMERIC(18, 6);
    v_elapsed NUMERIC;
    v_retry NUMERIC;

    v_allowed BOOLEAN;
    v_remaining NUMERIC;

    v_request_id UUID := gen_random_uuid();
BEGIN

    IF p_cost IS NULL OR p_cost <= 0 THEN
        RAISE EXCEPTION 'Request cost must be positive.';
    END IF;

    IF p_client_id IS NULL OR p_policy_id IS NULL THEN
        RAISE EXCEPTION 'Client and policy are required.';
    END IF;

    IF p_instance IS NULL OR length(trim(p_instance)) = 0 THEN
        RAISE EXCEPTION 'Application instance is required.';
    END IF;

    SELECT p.*
    INTO v_policy
    FROM rate_limit_policies p
    JOIN api_endpoints e
        ON e.endpoint_id = p.endpoint_id
    WHERE p.policy_id = p_policy_id
      AND p.enabled = TRUE
      AND e.status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active rate limit policy not found.';
    END IF;

    PERFORM 1
    FROM clients c
    WHERE c.client_id = p_client_id
      AND c.active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Client is inactive or does not exist.';
    END IF;

    -- Ensure the client is assigned to the policy.
    PERFORM 1
    FROM client_policy_assignments a
    WHERE a.client_id = p_client_id
      AND a.policy_id = p_policy_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Client is not assigned to this policy.';
    END IF;

    -- ========================================================
    -- FIXED WINDOW
    -- ========================================================

    IF v_policy.algorithm = 'FIXED_WINDOW' THEN

        v_window_start :=
            to_timestamp(
                floor(
                    extract(epoch FROM v_now) /
                    v_policy.window_seconds
                ) * v_policy.window_seconds
            );

        INSERT INTO fixed_window_state (
            policy_id,
            client_id,
            window_start,
            request_count
        )
        VALUES (
            p_policy_id,
            p_client_id,
            v_window_start,
            0
        )
        ON CONFLICT (policy_id, client_id)
        DO NOTHING;

        -- Row-level lock prevents concurrent over-admission.
        SELECT f.request_count, f.window_start
        INTO v_count, v_cutoff
        FROM fixed_window_state f
        WHERE f.policy_id = p_policy_id
          AND f.client_id = p_client_id
        FOR UPDATE;

        IF v_cutoff <> v_window_start THEN
            UPDATE fixed_window_state
            SET
                window_start = v_window_start,
                request_count = 0,
                updated_at = v_now
            WHERE policy_id = p_policy_id
              AND client_id = p_client_id;

            v_count := 0;
        END IF;

        v_allowed :=
            p_cost <= v_policy.request_limit
            AND v_count + p_cost <= v_policy.request_limit;

        IF v_allowed THEN
            UPDATE fixed_window_state
            SET
                request_count = request_count + p_cost,
                updated_at = v_now
            WHERE policy_id = p_policy_id
              AND client_id = p_client_id;

            v_count := v_count + p_cost;
        END IF;

        v_remaining := GREATEST(
            0,
            v_policy.request_limit - v_count
        );

        v_retry := CASE
            WHEN v_allowed THEN 0
            ELSE GREATEST(
                0,
                extract(
                    epoch FROM
                    v_window_start
                    + make_interval(
                        secs => v_policy.window_seconds::DOUBLE PRECISION
                    )
                    - v_now
                )
            )
        END;

    -- ========================================================
    -- SLIDING WINDOW
    -- ========================================================

    ELSIF v_policy.algorithm = 'SLIDING_WINDOW' THEN

        v_cutoff :=
            v_now - make_interval(
                secs => v_policy.window_seconds::DOUBLE PRECISION
            );

        -- Serialize requests for this policy/client pair.
        -- The fixed state row acts as the coordination lock.
        INSERT INTO fixed_window_state (
            policy_id,
            client_id,
            window_start,
            request_count
        )
        VALUES (
            p_policy_id,
            p_client_id,
            v_now,
            0
        )
        ON CONFLICT (policy_id, client_id)
        DO NOTHING;

        PERFORM 1
        FROM fixed_window_state f
        WHERE f.policy_id = p_policy_id
          AND f.client_id = p_client_id
        FOR UPDATE;

        DELETE FROM sliding_window_events e
        WHERE e.policy_id = p_policy_id
          AND e.client_id = p_client_id
          AND e.occurred_at <= v_cutoff;

        SELECT COALESCE(SUM(e.request_cost), 0)
        INTO v_count
        FROM sliding_window_events e
        WHERE e.policy_id = p_policy_id
          AND e.client_id = p_client_id
          AND e.occurred_at > v_cutoff;

        v_allowed :=
            p_cost <= v_policy.request_limit
            AND v_count + p_cost <= v_policy.request_limit;

        IF v_allowed THEN
            INSERT INTO sliding_window_events (
                policy_id,
                client_id,
                occurred_at,
                request_cost
            )
            VALUES (
                p_policy_id,
                p_client_id,
                v_now,
                p_cost
            );

            v_count := v_count + p_cost;
        END IF;

        v_remaining := GREATEST(
            0,
            v_policy.request_limit - v_count
        );

        v_retry := 0;

        IF NOT v_allowed THEN

            SELECT e.occurred_at
            INTO v_oldest
            FROM sliding_window_events e
            WHERE e.policy_id = p_policy_id
              AND e.client_id = p_client_id
              AND e.occurred_at > v_cutoff
            ORDER BY e.occurred_at
            OFFSET GREATEST(
                0,
                v_count + p_cost - v_policy.request_limit - 1
            )
            LIMIT 1;

            IF v_oldest IS NOT NULL THEN
                v_retry := GREATEST(
                    0,
                    extract(
                        epoch FROM
                        v_oldest
                        + make_interval(
                            secs => v_policy.window_seconds::DOUBLE PRECISION
                        )
                        - v_now
                    )
                );
            END IF;
        END IF;

    -- ========================================================
    -- TOKEN BUCKET
    -- ========================================================

    ELSIF v_policy.algorithm = 'TOKEN_BUCKET' THEN

        INSERT INTO token_bucket_state (
            policy_id,
            client_id,
            tokens,
            last_refill_at
        )
        VALUES (
            p_policy_id,
            p_client_id,
            v_policy.bucket_capacity,
            v_now
        )
        ON CONFLICT (policy_id, client_id)
        DO NOTHING;

        SELECT t.tokens, t.last_refill_at
        INTO v_tokens, v_oldest
        FROM token_bucket_state t
        WHERE t.policy_id = p_policy_id
          AND t.client_id = p_client_id
        FOR UPDATE;

        v_elapsed := GREATEST(
            0,
            extract(epoch FROM v_now - v_oldest)
        );

        v_tokens := LEAST(
            v_policy.bucket_capacity,
            v_tokens + v_elapsed * v_policy.refill_rate
        );

        v_allowed :=
            p_cost <= v_policy.bucket_capacity
            AND v_tokens >= p_cost;

        IF v_allowed THEN
            v_tokens := v_tokens - p_cost;
        END IF;

        UPDATE token_bucket_state
        SET
            tokens = v_tokens,
            last_refill_at = GREATEST(last_refill_at, v_now),
            updated_at = v_now
        WHERE policy_id = p_policy_id
          AND client_id = p_client_id;

        v_remaining := FLOOR(v_tokens);

        v_retry := CASE
            WHEN NOT v_allowed
                 AND p_cost <= v_policy.bucket_capacity
            THEN
                (p_cost - v_tokens) / v_policy.refill_rate
            ELSE 0
        END;

    END IF;

    -- ========================================================
    -- REQUEST AUDIT
    -- ========================================================

    INSERT INTO request_audit (
        request_id,
        client_id,
        policy_id,
        algorithm,
        decision,
        request_cost,
        remaining_quota,
        retry_after_seconds,
        application_instance,
        requested_at
    )
    VALUES (
        v_request_id,
        p_client_id,
        p_policy_id,
        v_policy.algorithm,
        CASE
            WHEN v_allowed THEN 'ALLOWED'::decision_type
            ELSE 'BLOCKED'::decision_type
        END,
        p_cost,
        v_remaining,
        v_retry,
        p_instance,
        v_now
    );

    RETURN QUERY
    SELECT
        v_allowed,
        v_policy.algorithm,
        v_remaining,
        v_retry,
        CASE
            WHEN v_allowed THEN 'ALLOWED'::decision_type
            ELSE 'BLOCKED'::decision_type
        END;

END;
$$;

-- ============================================================
-- CLEANUP PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE cleanup_rate_limit_history(
    p_retention_days INTEGER DEFAULT 30
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_retention_days <= 0 THEN
        RAISE EXCEPTION 'Retention period must be positive.';
    END IF;

    DELETE FROM request_audit
    WHERE requested_at <
        NOW() - make_interval(days => p_retention_days);

    DELETE FROM sliding_window_events e
    USING rate_limit_policies p
    WHERE e.policy_id = p.policy_id
      AND e.occurred_at <
          NOW() - make_interval(
              secs => p.window_seconds::DOUBLE PRECISION
          ) * 2;

END;
$$;

-- ============================================================
-- REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW rate_limit_usage_report AS
SELECT
    c.client_id,
    c.client_key,
    c.client_name,
    c.client_tier,
    e.endpoint_path,
    p.policy_name,
    p.algorithm,

    COUNT(a.audit_id) AS total_requests,

    COUNT(a.audit_id) FILTER (
        WHERE a.decision = 'ALLOWED'
    ) AS accepted_requests,

    COUNT(a.audit_id) FILTER (
        WHERE a.decision = 'BLOCKED'
    ) AS rejected_requests,

    ROUND(
        100.0 *
        COUNT(a.audit_id) FILTER (
            WHERE a.decision = 'BLOCKED'
        ) /
        NULLIF(COUNT(a.audit_id), 0),
        2
    ) AS rejection_percentage,

    MAX(a.requested_at) AS last_request_at

FROM clients c

JOIN client_policy_assignments ca
    ON ca.client_id = c.client_id

JOIN rate_limit_policies p
    ON p.policy_id = ca.policy_id

JOIN api_endpoints e
    ON e.endpoint_id = p.endpoint_id

LEFT JOIN request_audit a
    ON a.client_id = c.client_id
   AND a.policy_id = p.policy_id

GROUP BY
    c.client_id,
    c.client_key,
    c.client_name,
    c.client_tier,
    e.endpoint_path,
    p.policy_name,
    p.algorithm;

-- ============================================================
-- SAMPLE CLIENTS
-- ============================================================

INSERT INTO clients (
    client_key,
    client_name,
    client_tier
)
VALUES
    ('client-free-001', 'Free Application', 'FREE'),
    ('client-standard-001', 'Standard Application', 'STANDARD'),
    ('client-premium-001', 'Premium Application', 'PREMIUM'),
    ('client-enterprise-001', 'Enterprise Application', 'ENTERPRISE');

-- ============================================================
-- SAMPLE ENDPOINTS
-- ============================================================

INSERT INTO api_endpoints (
    endpoint_path,
    endpoint_name
)
VALUES
    ('/api/login', 'Authentication'),
    ('/api/search', 'Search'),
    ('/api/upload', 'File Upload');

-- ============================================================
-- SAMPLE POLICIES
-- ============================================================

INSERT INTO rate_limit_policies (
    policy_name,
    endpoint_id,
    algorithm,
    request_limit,
    window_seconds,
    bucket_capacity,
    refill_rate
)
SELECT
    'login-fixed-window',
    endpoint_id,
    'FIXED_WINDOW',
    5,
    60,
    NULL,
    NULL
FROM api_endpoints
WHERE endpoint_path = '/api/login';

INSERT INTO rate_limit_policies (
    policy_name,
    endpoint_id,
    algorithm,
    request_limit,
    window_seconds,
    bucket_capacity,
    refill_rate
)
SELECT
    'search-sliding-window',
    endpoint_id,
    'SLIDING_WINDOW',
    10,
    60,
    NULL,
    NULL
FROM api_endpoints
WHERE endpoint_path = '/api/search';

INSERT INTO rate_limit_policies (
    policy_name,
    endpoint_id,
    algorithm,
    request_limit,
    window_seconds,
    bucket_capacity,
    refill_rate
)
SELECT
    'upload-token-bucket',
    endpoint_id,
    'TOKEN_BUCKET',
    5,
    60,
    5,
    0.1
FROM api_endpoints
WHERE endpoint_path = '/api/upload';

-- ============================================================
-- CLIENT POLICY ASSIGNMENTS
-- ============================================================

INSERT INTO client_policy_assignments (
    client_id,
    policy_id
)
SELECT
    c.client_id,
    p.policy_id
FROM clients c
CROSS JOIN rate_limit_policies p
WHERE c.active = TRUE;

-- ============================================================
-- TRANSACTIONAL REQUEST DEMONSTRATION
-- ============================================================

-- Five login requests are accepted.
-- The sixth request is blocked.

DO $$
DECLARE
    v_client BIGINT;
    v_policy BIGINT;
    v_result RECORD;
    i INTEGER;
BEGIN

    SELECT client_id
    INTO v_client
    FROM clients
    WHERE client_key = 'client-free-001';

    SELECT policy_id
    INTO v_policy
    FROM rate_limit_policies
    WHERE policy_name = 'login-fixed-window';

    FOR i IN 1..6 LOOP

        SELECT *
        INTO v_result
        FROM evaluate_rate_limit(
            v_client,
            v_policy,
            1,
            'application-server-1'
        );

        RAISE NOTICE
            'Login request %: allowed=%, remaining=%, retry=%',
            i,
            v_result.allowed,
            v_result.remaining,
            v_result.retry_after_seconds;

    END LOOP;

END;
$$;

-- ============================================================
-- SLIDING WINDOW DEMONSTRATION
-- ============================================================

DO $$
DECLARE
    v_client BIGINT;
    v_policy BIGINT;
    v_result RECORD;
    i INTEGER;
BEGIN

    SELECT client_id
    INTO v_client
    FROM clients
    WHERE client_key = 'client-standard-001';

    SELECT policy_id
    INTO v_policy
    FROM rate_limit_policies
    WHERE policy_name = 'search-sliding-window';

    FOR i IN 1..12 LOOP

        SELECT *
        INTO v_result
        FROM evaluate_rate_limit(
            v_client,
            v_policy,
            1,
            'application-server-2'
        );

        RAISE NOTICE
            'Search request %: %, remaining=%',
            i,
            v_result.decision,
            v_result.remaining;

    END LOOP;

END;
$$;

-- ============================================================
-- TOKEN BUCKET DEMONSTRATION
-- ============================================================

DO $$
DECLARE
    v_client BIGINT;
    v_policy BIGINT;
    v_result RECORD;
    i INTEGER;
BEGIN

    SELECT client_id
    INTO v_client
    FROM clients
    WHERE client_key = 'client-premium-001';

    SELECT policy_id
    INTO v_policy
    FROM rate_limit_policies
    WHERE policy_name = 'upload-token-bucket';

    FOR i IN 1..7 LOOP

        SELECT *
        INTO v_result
        FROM evaluate_rate_limit(
            v_client,
            v_policy,
            1,
            'application-server-3'
        );

        RAISE NOTICE
            'Upload request %: %, remaining=%, retry=%',
            i,
            v_result.decision,
            v_result.remaining,
            v_result.retry_after_seconds;

    END LOOP;

END;
$$;

-- ============================================================
-- RETRIEVAL QUERIES
-- ============================================================

-- 1. Retrieve active policies.

SELECT
    p.policy_name,
    e.endpoint_path,
    p.algorithm,
    p.request_limit,
    p.window_seconds,
    p.bucket_capacity,
    p.refill_rate
FROM rate_limit_policies p
JOIN api_endpoints e
    ON e.endpoint_id = p.endpoint_id
WHERE p.enabled = TRUE
  AND e.status = 'ACTIVE'
ORDER BY e.endpoint_path;

-- 2. Retrieve request history.

SELECT
    a.request_id,
    c.client_name,
    p.policy_name,
    a.algorithm,
    a.decision,
    a.remaining_quota,
    a.retry_after_seconds,
    a.application_instance,
    a.requested_at
FROM request_audit a
JOIN clients c
    ON c.client_id = a.client_id
JOIN rate_limit_policies p
    ON p.policy_id = a.policy_id
ORDER BY a.requested_at DESC
LIMIT 50;

-- ============================================================
-- VALIDATION QUERIES
-- ============================================================

-- 3. Clients without an assigned policy.

SELECT
    c.client_id,
    c.client_name
FROM clients c
LEFT JOIN client_policy_assignments a
    ON a.client_id = c.client_id
WHERE a.assignment_id IS NULL;

-- 4. Policies with invalid operational assignments.

SELECT
    p.policy_id,
    p.policy_name,
    e.endpoint_path
FROM rate_limit_policies p
JOIN api_endpoints e
    ON e.endpoint_id = p.endpoint_id
WHERE p.enabled = TRUE
  AND e.status <> 'ACTIVE';

-- ============================================================
-- AGGREGATION AND EVALUATION
-- ============================================================

-- 5. Requests accepted and blocked per algorithm.

SELECT
    algorithm,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (
        WHERE decision = 'ALLOWED'
    ) AS accepted,
    COUNT(*) FILTER (
        WHERE decision = 'BLOCKED'
    ) AS rejected
FROM request_audit
GROUP BY algorithm
ORDER BY algorithm;

-- 6. Client rejection analysis.

SELECT
    c.client_name,
    c.client_tier,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (
        WHERE a.decision = 'BLOCKED'
    ) AS rejected_requests
FROM request_audit a
JOIN clients c
    ON c.client_id = a.client_id
GROUP BY
    c.client_id,
    c.client_name,
    c.client_tier
ORDER BY rejected_requests DESC;

-- 7. Policy utilization report.

SELECT *
FROM rate_limit_usage_report
ORDER BY rejection_percentage DESC NULLS LAST;

-- ============================================================
-- WORKFLOW PROCESSING
-- ============================================================

-- 8. Determine whether a client is eligible for an endpoint.

SELECT
    c.client_name,
    e.endpoint_path,
    p.policy_name,
    CASE
        WHEN c.active
         AND e.status = 'ACTIVE'
         AND p.enabled
         AND a.assignment_id IS NOT NULL
        THEN 'ELIGIBLE'
        ELSE 'NOT ELIGIBLE'
    END AS eligibility
FROM clients c
CROSS JOIN api_endpoints e
JOIN rate_limit_policies p
    ON p.endpoint_id = e.endpoint_id
LEFT JOIN client_policy_assignments a
    ON a.client_id = c.client_id
   AND a.policy_id = p.policy_id
ORDER BY c.client_id, e.endpoint_id;

-- 9. Calculate the current fixed-window state.

SELECT
    c.client_name,
    p.policy_name,
    f.request_count,
    p.request_limit,
    GREATEST(
        0,
        p.request_limit - f.request_count
    ) AS remaining
FROM fixed_window_state f
JOIN clients c
    ON c.client_id = f.client_id
JOIN rate_limit_policies p
    ON p.policy_id = f.policy_id;

-- 10. Retrieve current token bucket balances.

SELECT
    c.client_name,
    p.policy_name,
    t.tokens,
    p.bucket_capacity,
    p.refill_rate,
    t.last_refill_at
FROM token_bucket_state t
JOIN clients c
    ON c.client_id = t.client_id
JOIN rate_limit_policies p
    ON p.policy_id = t.policy_id;

-- ============================================================
-- TRANSACTION AND FAILURE HANDLING EXAMPLE
-- ============================================================

-- This transaction demonstrates rollback when a request
-- evaluation fails. The failed request does not retain state
-- changes or audit records.

SAVEPOINT before_invalid_request;

DO $$
BEGIN
    PERFORM *
    FROM evaluate_rate_limit(
        999999,
        1,
        1,
        'invalid-client-server'
    );
END;
$$;

-- The example above raises an exception and must be handled
-- by a transaction boundary in the calling application.
-- The following statement is illustrative for an interactive
-- psql session after handling that error:
--
-- ROLLBACK TO SAVEPOINT before_invalid_request;

COMMIT;

-- ============================================================
-- END OF RATE LIMITING DATABASE
-- ============================================================

-- ============================================================
-- CORS GOVERNANCE AND REQUEST AUDIT DATABASE
-- PostgreSQL 14+
--
-- Models:
-- Applications, origins, policies, methods, headers,
-- preflight requests, actual requests, decisions and auditing.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS cors_governance;

SET search_path TO cors_governance, public;

-- ------------------------------------------------------------
-- 1. Domain types
-- ------------------------------------------------------------

CREATE TYPE policy_status AS ENUM (
    'DRAFT',
    'ACTIVE',
    'DISABLED',
    'RETIRED'
);

CREATE TYPE request_kind AS ENUM (
    'SIMPLE',
    'PREFLIGHT',
    'ACTUAL'
);

CREATE TYPE cors_decision AS ENUM (
    'ALLOWED',
    'ORIGIN_DENIED',
    'METHOD_DENIED',
    'HEADER_DENIED',
    'CREDENTIALS_DENIED',
    'PRIVATE_NETWORK_DENIED',
    'INVALID_REQUEST',
    'POLICY_DISABLED'
);

-- ------------------------------------------------------------
-- 2. Applications
-- ------------------------------------------------------------

CREATE TABLE applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    application_key VARCHAR(100) NOT NULL UNIQUE,

    application_name VARCHAR(200) NOT NULL,

    environment VARCHAR(30) NOT NULL
        CHECK (
            environment IN (
                'development',
                'staging',
                'production',
                'testing'
            )
        ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 3. Origin validation
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION normalize_origin(
    p_origin TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
DECLARE
    v_origin TEXT;
    v_scheme TEXT;
    v_authority TEXT;
    v_host TEXT;
    v_port TEXT;
    v_suffix TEXT;
    v_ipv6 BOOLEAN := FALSE;
BEGIN
    v_origin := p_origin;

    IF v_origin = ''
       OR v_origin <> BTRIM(v_origin)
       OR v_origin ~ '[[:space:][:cntrl:]]'
       OR v_origin = 'null' THEN
        RAISE EXCEPTION 'Invalid or opaque origin';
    END IF;

    IF v_origin !~ '^https?://' THEN
        RAISE EXCEPTION 'Only HTTP and HTTPS origins are supported';
    END IF;

    v_scheme := LOWER(
        SPLIT_PART(v_origin, '://', 1)
    );

    v_authority := SUBSTRING(
        v_origin FROM POSITION('://' IN v_origin) + 3
    );

    IF v_authority = ''
       OR v_authority ~ '[/@?#]' THEN
        RAISE EXCEPTION 'Invalid origin authority';
    END IF;

    IF v_authority LIKE '[%' THEN
        v_ipv6 := TRUE;

        IF v_authority !~ '^\[[0-9A-Fa-f:.]+\](:[0-9]+)?$' THEN
            RAISE EXCEPTION 'Invalid IPv6 origin';
        END IF;

        v_host := SPLIT_PART(v_authority, ']', 1) || ']';

        v_suffix := SUBSTRING(
            v_authority FROM POSITION(']' IN v_authority) + 1
        );

        IF v_suffix <> '' THEN
            v_port := SUBSTRING(v_suffix FROM 2);
        END IF;
    ELSE
        IF v_authority ~ ':' THEN
            IF v_authority !~ '^[^:]+:[0-9]+$' THEN
                RAISE EXCEPTION 'Invalid host or port';
            END IF;

            v_host := SPLIT_PART(v_authority, ':', 1);
            v_port := SPLIT_PART(v_authority, ':', 2);
        ELSE
            v_host := v_authority;
        END IF;

        IF v_host !~ '^[A-Za-z0-9.-]+$' THEN
            RAISE EXCEPTION 'Invalid hostname';
        END IF;
    END IF;

    v_host := LOWER(v_host);

    IF NOT v_ipv6 AND RIGHT(v_host, 1) = '.' THEN
        v_host := LEFT(v_host, LENGTH(v_host) - 1);
    END IF;

    IF v_host = '' THEN
        RAISE EXCEPTION 'Hostname cannot be empty';
    END IF;

    IF v_port IS NOT NULL THEN
        IF v_port::INTEGER < 1 OR v_port::INTEGER > 65535 THEN
            RAISE EXCEPTION 'Port out of range';
        END IF;

        IF (v_scheme = 'http' AND v_port::INTEGER = 80)
           OR (v_scheme = 'https' AND v_port::INTEGER = 443) THEN
            v_port := NULL;
        END IF;
    END IF;

    RETURN v_scheme || '://' || v_host ||
        CASE
            WHEN v_port IS NULL THEN ''
            ELSE ':' || v_port
        END;
END;
$$;

-- ------------------------------------------------------------
-- 4. CORS policies
-- ------------------------------------------------------------

CREATE TABLE cors_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id)
        ON DELETE CASCADE,

    policy_name VARCHAR(150) NOT NULL,

    policy_version INTEGER NOT NULL DEFAULT 1
        CHECK (policy_version > 0),

    status policy_status NOT NULL DEFAULT 'DRAFT',

    allow_credentials BOOLEAN NOT NULL DEFAULT FALSE,

    allow_private_network BOOLEAN NOT NULL DEFAULT FALSE,

    max_age INTEGER NOT NULL DEFAULT 600
        CHECK (max_age BETWEEN 0 AND 86400),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (application_id, policy_name, policy_version),

    UNIQUE (policy_id, application_id)
);

-- ------------------------------------------------------------
-- 5. Allowed origins
-- ------------------------------------------------------------

CREATE TABLE allowed_origins (
    origin_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    policy_id BIGINT NOT NULL
        REFERENCES cors_policies(policy_id)
        ON DELETE CASCADE,

    origin_value TEXT NOT NULL,

    wildcard BOOLEAN GENERATED ALWAYS AS (
        origin_value = '*'
    ) STORED,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (policy_id, origin_value),

    CHECK (
        origin_value = '*'
        OR origin_value = normalize_origin(origin_value)
    )
);

CREATE INDEX idx_allowed_origins_policy
    ON allowed_origins(policy_id);

-- ------------------------------------------------------------
-- 6. Allowed HTTP methods
-- ------------------------------------------------------------

CREATE TABLE allowed_methods (
    policy_id BIGINT NOT NULL
        REFERENCES cors_policies(policy_id)
        ON DELETE CASCADE,

    method VARCHAR(16) NOT NULL
        CHECK (method ~ '^[A-Z]+$'),

    PRIMARY KEY (policy_id, method)
);

-- ------------------------------------------------------------
-- 7. Allowed request headers
-- ------------------------------------------------------------

CREATE TABLE allowed_headers (
    policy_id BIGINT NOT NULL
        REFERENCES cors_policies(policy_id)
        ON DELETE CASCADE,

    header_name VARCHAR(128) NOT NULL
        CHECK (
            header_name = LOWER(header_name)
            AND header_name ~ '^[!#$%&''*+.^_`|~0-9a-z-]+$'
        ),

    PRIMARY KEY (policy_id, header_name)
);

-- ------------------------------------------------------------
-- 8. Exposed response headers
-- ------------------------------------------------------------

CREATE TABLE exposed_headers (
    policy_id BIGINT NOT NULL
        REFERENCES cors_policies(policy_id)
        ON DELETE CASCADE,

    header_name VARCHAR(128) NOT NULL
        CHECK (
            header_name = LOWER(header_name)
            AND header_name ~ '^[!#$%&''*+.^_`|~0-9a-z-]+$'
        ),

    PRIMARY KEY (policy_id, header_name)
);

-- ------------------------------------------------------------
-- 9. Policy integrity enforcement
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION enforce_cors_policy_integrity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_policy_id BIGINT;
    v_credentials BOOLEAN;
    v_status policy_status;
    v_wildcard BOOLEAN;
BEGIN
    v_policy_id := CASE
        WHEN TG_OP = 'DELETE' THEN OLD.policy_id
        ELSE NEW.policy_id
    END;

    SELECT
        allow_credentials,
        status
    INTO
        v_credentials,
        v_status
    FROM cors_policies
    WHERE policy_id = v_policy_id;

    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM allowed_origins
        WHERE policy_id = v_policy_id
          AND origin_value = '*'
    )
    INTO v_wildcard;

    IF v_wildcard AND v_credentials THEN
        RAISE EXCEPTION
            'Wildcard origin cannot be combined with credentials';
    END IF;

    IF v_status = 'ACTIVE' AND NOT EXISTS (
        SELECT 1
        FROM allowed_origins
        WHERE policy_id = v_policy_id
    ) THEN
        RAISE EXCEPTION
            'Active policy must have at least one allowed origin';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE CONSTRAINT TRIGGER trg_origin_policy_integrity
AFTER INSERT OR UPDATE OR DELETE ON allowed_origins
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_cors_policy_integrity();

CREATE CONSTRAINT TRIGGER trg_policy_origin_integrity
AFTER INSERT OR UPDATE ON cors_policies
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_cors_policy_integrity();

-- ------------------------------------------------------------
-- 10. Request records
-- ------------------------------------------------------------

CREATE TABLE cors_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    request_uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),

    policy_id BIGINT
        REFERENCES cors_policies(policy_id),

    origin TEXT,

    normalized_origin TEXT,

    http_method VARCHAR(16) NOT NULL
        CHECK (http_method ~ '^[A-Z]+$'),

    request_type request_kind NOT NULL,

    requested_method VARCHAR(16),

    credentials_requested BOOLEAN NOT NULL DEFAULT FALSE,

    private_network_requested BOOLEAN NOT NULL DEFAULT FALSE,

    decision cors_decision NOT NULL,

    response_status INTEGER NOT NULL
        CHECK (response_status BETWEEN 100 AND 599),

    decision_reason TEXT NOT NULL,

    duration_ms NUMERIC(12, 3)
        CHECK (duration_ms >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        request_type <> 'PREFLIGHT'
        OR http_method = 'OPTIONS'
    )
);

CREATE INDEX idx_requests_application_time
    ON cors_requests(application_id, created_at DESC);

CREATE INDEX idx_requests_policy_decision
    ON cors_requests(policy_id, decision);

CREATE INDEX idx_requests_origin
    ON cors_requests(normalized_origin);

CREATE INDEX idx_requests_preflight
    ON cors_requests(created_at DESC)
    WHERE request_type = 'PREFLIGHT';

-- ------------------------------------------------------------
-- 11. Requested headers
-- ------------------------------------------------------------

CREATE TABLE requested_headers (
    request_id BIGINT NOT NULL
        REFERENCES cors_requests(request_id)
        ON DELETE CASCADE,

    header_name VARCHAR(128) NOT NULL,

    PRIMARY KEY (request_id, header_name)
);

-- ------------------------------------------------------------
-- 12. Preflight cache records
-- ------------------------------------------------------------

CREATE TABLE preflight_cache (
    cache_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    policy_id BIGINT NOT NULL
        REFERENCES cors_policies(policy_id)
        ON DELETE CASCADE,

    normalized_origin TEXT NOT NULL,

    requested_method VARCHAR(16) NOT NULL,

    requested_headers JSONB NOT NULL DEFAULT '[]'::JSONB
        CHECK (jsonb_typeof(requested_headers) = 'array'),

    credentials_requested BOOLEAN NOT NULL DEFAULT FALSE,

    private_network_requested BOOLEAN NOT NULL DEFAULT FALSE,

    expires_at TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (expires_at > created_at),

    UNIQUE (
        policy_id,
        normalized_origin,
        requested_method,
        requested_headers,
        credentials_requested,
        private_network_requested
    )
);

CREATE INDEX idx_preflight_expiration
    ON preflight_cache(expires_at);

-- ------------------------------------------------------------
-- 13. CORS decision function
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_cors_request(
    p_application_id BIGINT,
    p_origin TEXT,
    p_method TEXT,
    p_request_type request_kind,
    p_requested_method TEXT DEFAULT NULL,
    p_requested_headers TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_credentials BOOLEAN DEFAULT FALSE,
    p_private_network BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    decision cors_decision,
    response_status INTEGER,
    allowed_origin TEXT,
    decision_reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_policy RECORD;
    v_normalized_origin TEXT;
    v_method TEXT;
    v_header TEXT;
    v_resolved_origin TEXT;
BEGIN
    v_method := UPPER(p_method);

    SELECT p.*
    INTO v_policy
    FROM cors_policies p
    WHERE p.application_id = p_application_id
      AND p.status = 'ACTIVE'
    ORDER BY p.policy_version DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN QUERY SELECT
            'POLICY_DISABLED'::cors_decision,
            403,
            NULL::TEXT,
            'No active CORS policy exists';
        RETURN;
    END IF;

    -- Requests without Origin do not require CORS authorization.
    IF p_origin IS NULL OR p_origin = '' THEN
        RETURN QUERY SELECT
            'ALLOWED'::cors_decision,
            200,
            NULL::TEXT,
            'No CORS processing required';
        RETURN;
    END IF;

    BEGIN
        v_normalized_origin := normalize_origin(p_origin);
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT
            'INVALID_REQUEST'::cors_decision,
            403,
            NULL::TEXT,
            'Invalid origin';
        RETURN;
    END;

    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM allowed_origins
            WHERE policy_id = v_policy.policy_id
              AND origin_value = '*'
              AND NOT v_policy.allow_credentials
        ) THEN '*'

        WHEN EXISTS (
            SELECT 1
            FROM allowed_origins
            WHERE policy_id = v_policy.policy_id
              AND origin_value = v_normalized_origin
        ) THEN v_normalized_origin

        ELSE NULL
    END
    INTO v_resolved_origin;

    IF v_resolved_origin IS NULL THEN
        RETURN QUERY SELECT
            'ORIGIN_DENIED'::cors_decision,
            403,
            NULL::TEXT,
            'Origin is not allowed';
        RETURN;
    END IF;

    IF p_credentials AND NOT v_policy.allow_credentials THEN
        RETURN QUERY SELECT
            'CREDENTIALS_DENIED'::cors_decision,
            403,
            NULL::TEXT,
            'Credentials are not allowed';
        RETURN;
    END IF;

    IF p_private_network AND NOT v_policy.allow_private_network THEN
        RETURN QUERY SELECT
            'PRIVATE_NETWORK_DENIED'::cors_decision,
            403,
            NULL::TEXT,
            'Private network access is not allowed';
        RETURN;
    END IF;

    IF p_request_type = 'PREFLIGHT' THEN

        IF v_method <> 'OPTIONS'
           OR p_requested_method IS NULL
           OR p_requested_method !~ '^[A-Za-z]+$' THEN
            RETURN QUERY SELECT
                'INVALID_REQUEST'::cors_decision,
                400,
                NULL::TEXT,
                'Invalid preflight request';
            RETURN;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM allowed_methods
            WHERE policy_id = v_policy.policy_id
              AND method = UPPER(p_requested_method)
        ) THEN
            RETURN QUERY SELECT
                'METHOD_DENIED'::cors_decision,
                403,
                NULL::TEXT,
                'Requested method is not allowed';
            RETURN;
        END IF;

        FOREACH v_header IN ARRAY p_requested_headers LOOP
            IF NOT EXISTS (
                SELECT 1
                FROM allowed_headers
                WHERE policy_id = v_policy.policy_id
                  AND header_name = LOWER(v_header)
            ) THEN
                RETURN QUERY SELECT
                    'HEADER_DENIED'::cors_decision,
                    403,
                    NULL::TEXT,
                    'Requested header is not allowed';
                RETURN;
            END IF;
        END LOOP;

        RETURN QUERY SELECT
            'ALLOWED'::cors_decision,
            204,
            v_resolved_origin,
            'Preflight accepted';
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM allowed_methods
        WHERE policy_id = v_policy.policy_id
          AND method = v_method
    ) THEN
        RETURN QUERY SELECT
            'METHOD_DENIED'::cors_decision,
            405,
            NULL::TEXT,
            'HTTP method is not allowed';
        RETURN;
    END IF;

    RETURN QUERY SELECT
        'ALLOWED'::cors_decision,
        200,
        v_resolved_origin,
        'CORS request accepted';
END;
$$;

-- ------------------------------------------------------------
-- 14. Request logging procedure
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE log_cors_request(
    p_application_id BIGINT,
    p_origin TEXT,
    p_method TEXT,
    p_request_type request_kind,
    p_requested_method TEXT,
    p_requested_headers TEXT[],
    p_credentials BOOLEAN,
    p_private_network BOOLEAN,
    p_duration_ms NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_result RECORD;
    v_policy_id BIGINT;
    v_normalized_origin TEXT;
    v_request_id BIGINT;
BEGIN
    SELECT policy_id
    INTO v_policy_id
    FROM cors_policies
    WHERE application_id = p_application_id
      AND status = 'ACTIVE'
    ORDER BY policy_version DESC
    LIMIT 1;

    BEGIN
        IF p_origin IS NOT NULL AND p_origin <> '' THEN
            v_normalized_origin := normalize_origin(p_origin);
        END IF;
    EXCEPTION WHEN OTHERS THEN
        v_normalized_origin := NULL;
    END;

    SELECT *
    INTO v_result
    FROM evaluate_cors_request(
        p_application_id,
        p_origin,
        p_method,
        p_request_type,
        p_requested_method,
        p_requested_headers,
        p_credentials,
        p_private_network
    );

    INSERT INTO cors_requests (
        application_id,
        policy_id,
        origin,
        normalized_origin,
        http_method,
        request_type,
        requested_method,
        credentials_requested,
        private_network_requested,
        decision,
        response_status,
        decision_reason,
        duration_ms
    )
    VALUES (
        p_application_id,
        v_policy_id,
        p_origin,
        v_normalized_origin,
        UPPER(p_method),
        p_request_type,
        UPPER(p_requested_method),
        p_credentials,
        p_private_network,
        v_result.decision,
        v_result.response_status,
        v_result.decision_reason,
        p_duration_ms
    )
    RETURNING request_id INTO v_request_id;

    INSERT INTO requested_headers (
        request_id,
        header_name
    )
    SELECT
        v_request_id,
        LOWER(header_name)
    FROM UNNEST(p_requested_headers) AS header_name
    ON CONFLICT DO NOTHING;
END;
$$;

-- ------------------------------------------------------------
-- 15. Reporting view
-- ------------------------------------------------------------

CREATE VIEW cors_request_report AS
SELECT
    a.application_key,
    a.application_name,
    a.environment,
    r.request_id,
    r.normalized_origin,
    r.http_method,
    r.request_type,
    r.requested_method,
    r.decision,
    r.response_status,
    r.decision_reason,
    r.duration_ms,
    r.created_at
FROM cors_requests r
JOIN applications a
    ON a.application_id = r.application_id;

-- ------------------------------------------------------------
-- 16. Policy eligibility report
-- ------------------------------------------------------------

CREATE VIEW cors_policy_eligibility AS
SELECT
    p.policy_id,
    a.application_key,
    p.policy_name,
    p.policy_version,
    p.status,
    p.allow_credentials,
    p.max_age,

    COUNT(DISTINCT o.origin_id) AS configured_origins,

    COUNT(DISTINCT m.method) AS configured_methods,

    COUNT(DISTINCT h.header_name) AS configured_headers,

    CASE
        WHEN p.status <> 'ACTIVE' THEN FALSE
        WHEN COUNT(DISTINCT o.origin_id) = 0 THEN FALSE
        WHEN p.allow_credentials AND BOOL_OR(o.wildcard) THEN FALSE
        ELSE TRUE
    END AS configuration_valid

FROM cors_policies p

JOIN applications a
    ON a.application_id = p.application_id

LEFT JOIN allowed_origins o
    ON o.policy_id = p.policy_id

LEFT JOIN allowed_methods m
    ON m.policy_id = p.policy_id

LEFT JOIN allowed_headers h
    ON h.policy_id = p.policy_id

GROUP BY
    p.policy_id,
    a.application_key,
    p.policy_name,
    p.policy_version,
    p.status,
    p.allow_credentials,
    p.max_age;

-- ------------------------------------------------------------
-- 17. Sample applications and policies
-- ------------------------------------------------------------

INSERT INTO applications (
    application_key,
    application_name,
    environment
)
VALUES
    ('customer-portal', 'Customer Portal API', 'production'),
    ('admin-console', 'Administration API', 'production'),
    ('development-api', 'Development API', 'development');

INSERT INTO cors_policies (
    application_id,
    policy_name,
    policy_version,
    status,
    allow_credentials,
    allow_private_network,
    max_age
)
SELECT
    application_id,
    'primary-web-policy',
    1,
    'ACTIVE',
    TRUE,
    FALSE,
    600
FROM applications
WHERE application_key IN (
    'customer-portal',
    'admin-console'
);

INSERT INTO cors_policies (
    application_id,
    policy_name,
    policy_version,
    status,
    allow_credentials,
    max_age
)
SELECT
    application_id,
    'development-wildcard-policy',
    1,
    'ACTIVE',
    FALSE,
    300
FROM applications
WHERE application_key = 'development-api';

-- Allowed origins.

INSERT INTO allowed_origins (
    policy_id,
    origin_value
)
SELECT
    p.policy_id,
    origins.origin_value
FROM cors_policies p
JOIN applications a
    ON a.application_id = p.application_id
CROSS JOIN LATERAL (
    SELECT UNNEST(
        CASE a.application_key
            WHEN 'customer-portal' THEN ARRAY[
                'https://app.example.com',
                'https://admin.example.com'
            ]
            WHEN 'admin-console' THEN ARRAY[
                'https://admin.example.com'
            ]
            ELSE ARRAY['*']
        END
    ) AS origin_value
) origins;

-- Allowed methods.

INSERT INTO allowed_methods (policy_id, method)
SELECT p.policy_id, methods.method
FROM cors_policies p
CROSS JOIN LATERAL (
    SELECT UNNEST(
        ARRAY['GET', 'POST', 'PUT', 'DELETE']
    ) AS method
) methods;

-- Allowed headers.

INSERT INTO allowed_headers (policy_id, header_name)
SELECT p.policy_id, headers.header_name
FROM cors_policies p
CROSS JOIN LATERAL (
    SELECT UNNEST(
        ARRAY['content-type', 'authorization', 'x-request-id']
    ) AS header_name
) headers;

-- Exposed headers.

INSERT INTO exposed_headers (policy_id, header_name)
SELECT
    policy_id,
    'x-request-id'
FROM cors_policies;

-- ------------------------------------------------------------
-- 18. Request workflow demonstration
-- ------------------------------------------------------------

DO $$
DECLARE
    v_customer BIGINT;
    v_admin BIGINT;
    v_development BIGINT;
BEGIN
    SELECT application_id INTO v_customer
    FROM applications
    WHERE application_key = 'customer-portal';

    SELECT application_id INTO v_admin
    FROM applications
    WHERE application_key = 'admin-console';

    SELECT application_id INTO v_development
    FROM applications
    WHERE application_key = 'development-api';

    -- Allowed simple request.
    CALL log_cors_request(
        v_customer,
        'https://app.example.com',
        'GET',
        'SIMPLE',
        NULL,
        ARRAY[]::TEXT[],
        FALSE,
        FALSE,
        12.5
    );

    -- Allowed credentialed preflight.
    CALL log_cors_request(
        v_customer,
        'https://app.example.com',
        'OPTIONS',
        'PREFLIGHT',
        'POST',
        ARRAY['authorization', 'content-type'],
        TRUE,
        FALSE,
        3.2
    );

    -- Rejected origin.
    CALL log_cors_request(
        v_customer,
        'https://attacker.example.net',
        'GET',
        'SIMPLE',
        NULL,
        ARRAY[]::TEXT[],
        FALSE,
        FALSE,
        2.1
    );

    -- Rejected method.
    CALL log_cors_request(
        v_customer,
        'https://app.example.com',
        'PATCH',
        'ACTUAL',
        NULL,
        ARRAY[]::TEXT[],
        FALSE,
        FALSE,
        1.8
    );

    -- Rejected request header.
    CALL log_cors_request(
        v_customer,
        'https://app.example.com',
        'OPTIONS',
        'PREFLIGHT',
        'POST',
        ARRAY['x-dangerous-header'],
        FALSE,
        FALSE,
        2.5
    );

    -- Rejected private network request.
    CALL log_cors_request(
        v_customer,
        'https://app.example.com',
        'OPTIONS',
        'PREFLIGHT',
        'POST',
        ARRAY['content-type'],
        FALSE,
        TRUE,
        2.7
    );

    -- Development wildcard origin.
    CALL log_cors_request(
        v_development,
        'https://temporary.example.net',
        'GET',
        'SIMPLE',
        NULL,
        ARRAY[]::TEXT[],
        FALSE,
        FALSE,
        4.1
    );

    -- Admin application allows its configured origin.
    CALL log_cors_request(
        v_admin,
        'https://admin.example.com',
        'GET',
        'SIMPLE',
        NULL,
        ARRAY[]::TEXT[],
        TRUE,
        FALSE,
        3.4
    );
END;
$$;

-- ------------------------------------------------------------
-- 19. Retrieval query
-- ------------------------------------------------------------

SELECT *
FROM cors_request_report
ORDER BY created_at DESC;

-- ------------------------------------------------------------
-- 20. Validation query
-- ------------------------------------------------------------

SELECT
    application_key,
    policy_name,
    policy_version,
    status,
    configuration_valid
FROM cors_policy_eligibility
ORDER BY application_key;

-- ------------------------------------------------------------
-- 21. Aggregation and rejection analysis
-- ------------------------------------------------------------

SELECT
    application_key,
    decision,
    COUNT(*) AS request_count,
    ROUND(AVG(duration_ms), 3) AS average_duration_ms
FROM cors_request_report
GROUP BY application_key, decision
ORDER BY application_key, decision;

-- ------------------------------------------------------------
-- 22. Preflight evaluation
-- ------------------------------------------------------------

SELECT *
FROM evaluate_cors_request(
    (
        SELECT application_id
        FROM applications
        WHERE application_key = 'customer-portal'
    ),
    'https://app.example.com',
    'OPTIONS',
    'PREFLIGHT',
    'POST',
    ARRAY['authorization', 'content-type'],
    TRUE,
    FALSE
);

-- ------------------------------------------------------------
-- 23. Origin denial analysis
-- ------------------------------------------------------------

SELECT
    normalized_origin,
    COUNT(*) AS rejected_requests
FROM cors_requests
WHERE decision = 'ORIGIN_DENIED'
GROUP BY normalized_origin
ORDER BY rejected_requests DESC;

-- ------------------------------------------------------------
-- 24. Expired preflight cache cleanup
-- ------------------------------------------------------------

DELETE FROM preflight_cache
WHERE expires_at <= CURRENT_TIMESTAMP;

COMMIT;

-- ============================================================
-- API CACHING MANAGEMENT SYSTEM
-- PostgreSQL 15+
--
-- Models:
-- HTTP resources, representations, Cache-Control directives,
-- ETags, conditional requests, cache entries, Vary headers,
-- cache invalidation, request telemetry and policy evaluation.
--
-- Run in a dedicated development database.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS api_cache;

SET search_path TO api_cache, public;

-- ------------------------------------------------------------
-- 1. Domain types
-- ------------------------------------------------------------

CREATE TYPE cache_scope AS ENUM (
    'PUBLIC',
    'PRIVATE'
);

CREATE TYPE cache_event_type AS ENUM (
    'HIT',
    'MISS',
    'REVALIDATED',
    'BYPASS',
    'INVALIDATION',
    'EVICTION'
);

CREATE TYPE http_method AS ENUM (
    'GET',
    'HEAD',
    'POST',
    'PUT',
    'PATCH',
    'DELETE'
);

CREATE TYPE resource_state AS ENUM (
    'ACTIVE',
    'DISABLED',
    'DELETED'
);

-- ------------------------------------------------------------
-- 2. API resources
-- ------------------------------------------------------------

CREATE TABLE api_resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_path TEXT NOT NULL UNIQUE,

    resource_name VARCHAR(200) NOT NULL,

    content_type VARCHAR(150) NOT NULL
        DEFAULT 'application/json',

    state resource_state NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_resource_path
        CHECK (
            resource_path LIKE '/%'
            AND resource_path NOT LIKE '%..%'
        ),

    CONSTRAINT valid_resource_name
        CHECK (LENGTH(TRIM(resource_name)) > 0)
);

-- ------------------------------------------------------------
-- 3. Resource representations
--
-- A representation is a particular version of a resource.
-- ETags identify representations, not resource paths alone.
-- ------------------------------------------------------------

CREATE TABLE representations (
    representation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT NOT NULL
        REFERENCES api_resources(resource_id),

    version_number INTEGER NOT NULL,

    response_body JSONB NOT NULL,

    etag VARCHAR(150) NOT NULL,

    last_modified TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    content_length BIGINT GENERATED ALWAYS AS (
        LENGTH(response_body::TEXT)
    ) STORED,

    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_version
        CHECK (version_number > 0),

    CONSTRAINT valid_etag
        CHECK (
            LENGTH(etag) > 2
            AND etag LIKE '"%'
            AND etag LIKE '%"'
        ),

    CONSTRAINT unique_resource_version
        UNIQUE (resource_id, version_number)
);

-- Only one current representation per resource.
CREATE UNIQUE INDEX one_current_representation
ON representations(resource_id)
WHERE is_current = TRUE;

CREATE INDEX representation_etag_idx
ON representations(etag);

CREATE INDEX representation_modified_idx
ON representations(last_modified DESC);

-- ------------------------------------------------------------
-- 4. Cache-Control policies
-- ------------------------------------------------------------

CREATE TABLE cache_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(120) NOT NULL UNIQUE,

    scope cache_scope NOT NULL,

    max_age INTEGER NOT NULL DEFAULT 0,

    s_maxage INTEGER,

    no_store BOOLEAN NOT NULL DEFAULT FALSE,

    no_cache BOOLEAN NOT NULL DEFAULT FALSE,

    must_revalidate BOOLEAN NOT NULL DEFAULT FALSE,

    immutable BOOLEAN NOT NULL DEFAULT FALSE,

    stale_while_revalidate INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_max_age
        CHECK (max_age >= 0),

    CONSTRAINT valid_s_maxage
        CHECK (s_maxage IS NULL OR s_maxage >= 0),

    CONSTRAINT valid_stale_window
        CHECK (stale_while_revalidate >= 0),

    CONSTRAINT no_store_conflict
        CHECK (NOT (no_store AND immutable))
);

CREATE TABLE resource_policy_assignments (
    resource_id BIGINT PRIMARY KEY
        REFERENCES api_resources(resource_id),

    policy_id BIGINT NOT NULL
        REFERENCES cache_policies(policy_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 5. Vary header definitions
-- ------------------------------------------------------------

CREATE TABLE vary_headers (
    vary_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT NOT NULL
        REFERENCES api_resources(resource_id),

    header_name VARCHAR(100) NOT NULL,

    CONSTRAINT normalized_header_name
        CHECK (
            header_name = LOWER(header_name)
            AND header_name ~ '^[a-z0-9-]+$'
        ),

    CONSTRAINT unique_resource_vary
        UNIQUE(resource_id, header_name)
);

-- ------------------------------------------------------------
-- 6. Cache entries
--
-- A cache entry stores one selected representation.
-- Vary values are part of the logical cache identity.
-- ------------------------------------------------------------

CREATE TABLE cache_entries (
    cache_entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT NOT NULL
        REFERENCES api_resources(resource_id),

    representation_id BIGINT NOT NULL
        REFERENCES representations(representation_id),

    policy_id BIGINT NOT NULL
        REFERENCES cache_policies(policy_id),

    cache_scope cache_scope NOT NULL,

    principal_id VARCHAR(150),

    vary_values JSONB NOT NULL DEFAULT '{}'::JSONB,

    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    initial_age INTEGER NOT NULL DEFAULT 0,

    expires_at TIMESTAMPTZ NOT NULL,

    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_initial_age
        CHECK (initial_age >= 0),

    CONSTRAINT valid_expiration
        CHECK (expires_at >= stored_at),

    CONSTRAINT private_principal_required
        CHECK (
            cache_scope <> 'PRIVATE'
            OR principal_id IS NOT NULL
        )
);

CREATE INDEX cache_resource_lookup_idx
ON cache_entries(resource_id, expires_at);

CREATE INDEX cache_expiration_idx
ON cache_entries(expires_at);

CREATE INDEX cache_principal_idx
ON cache_entries(principal_id)
WHERE principal_id IS NOT NULL;

CREATE INDEX cache_vary_values_idx
ON cache_entries USING GIN(vary_values);

-- ------------------------------------------------------------
-- 7. HTTP request telemetry
-- ------------------------------------------------------------

CREATE TABLE http_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT
        REFERENCES api_resources(resource_id),

    method http_method NOT NULL,

    principal_id VARCHAR(150),

    if_none_match TEXT,

    if_modified_since TIMESTAMPTZ,

    request_no_cache BOOLEAN NOT NULL DEFAULT FALSE,

    request_no_store BOOLEAN NOT NULL DEFAULT FALSE,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX request_resource_time_idx
ON http_requests(resource_id, requested_at DESC);

-- ------------------------------------------------------------
-- 8. Cache event history
-- ------------------------------------------------------------

CREATE TABLE cache_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id BIGINT
        REFERENCES http_requests(request_id),

    cache_entry_id BIGINT
        REFERENCES cache_entries(cache_entry_id)
        ON DELETE SET NULL,

    resource_id BIGINT
        REFERENCES api_resources(resource_id),

    event_type cache_event_type NOT NULL,

    http_status INTEGER,

    response_time_ms NUMERIC(12, 3),

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_http_status
        CHECK (
            http_status IS NULL
            OR http_status BETWEEN 100 AND 599
        ),

    CONSTRAINT valid_response_time
        CHECK (
            response_time_ms IS NULL
            OR response_time_ms >= 0
        )
);

CREATE INDEX cache_event_resource_idx
ON cache_events(resource_id, recorded_at DESC);

CREATE INDEX cache_event_type_idx
ON cache_events(event_type, recorded_at DESC);

-- ------------------------------------------------------------
-- 9. Cache policy eligibility
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_cache_eligibility(
    p_policy_id BIGINT,
    p_method http_method,
    p_authenticated BOOLEAN
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT
        p_method IN ('GET', 'HEAD')
        AND p_authenticated
        AND NOT p.no_store
        AND (
            p.scope = 'PUBLIC'
            OR p.scope = 'PRIVATE'
        )
    FROM cache_policies p
    WHERE p.policy_id = p_policy_id;
$$;

-- ------------------------------------------------------------
-- 10. Expiration calculation
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION calculate_expiration(
    p_policy_id BIGINT,
    p_shared BOOLEAN
)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_lifetime INTEGER;
BEGIN
    SELECT
        CASE
            WHEN p_shared AND s_maxage IS NOT NULL
                THEN s_maxage
            ELSE max_age
        END
    INTO v_lifetime
    FROM cache_policies
    WHERE policy_id = p_policy_id
      AND NOT no_store;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Invalid or non-storable cache policy: %',
            p_policy_id;
    END IF;

    RETURN NOW() + make_interval(secs => v_lifetime);
END;
$$;

-- ------------------------------------------------------------
-- 11. Cache entry insertion
--
-- Replaces an existing logical cache representation.
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE store_cache_entry(
    p_resource_id BIGINT,
    p_representation_id BIGINT,
    p_policy_id BIGINT,
    p_scope cache_scope,
    p_principal_id VARCHAR(150),
    p_vary_values JSONB DEFAULT '{}'::JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_expiration TIMESTAMPTZ;
    v_no_store BOOLEAN;
    v_policy_scope cache_scope;
BEGIN
    SELECT no_store, scope
    INTO v_no_store, v_policy_scope
    FROM cache_policies
    WHERE policy_id = p_policy_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cache policy does not exist';
    END IF;

    IF v_no_store THEN
        RAISE EXCEPTION 'no-store policy prohibits storage';
    END IF;

    IF p_scope <> v_policy_scope THEN
        RAISE EXCEPTION 'Cache scope conflicts with policy';
    END IF;

    IF p_scope = 'PRIVATE'
       AND p_principal_id IS NULL THEN
        RAISE EXCEPTION
            'Private cache requires principal identity';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM representations
        WHERE representation_id = p_representation_id
          AND resource_id = p_resource_id
    ) THEN
        RAISE EXCEPTION
            'Representation does not belong to resource';
    END IF;

    v_expiration := calculate_expiration(
        p_policy_id,
        p_scope = 'PUBLIC'
    );

    DELETE FROM cache_entries
    WHERE resource_id = p_resource_id
      AND cache_scope = p_scope
      AND principal_id IS NOT DISTINCT FROM p_principal_id
      AND vary_values = COALESCE(
          p_vary_values,
          '{}'::JSONB
      );

    INSERT INTO cache_entries (
        resource_id,
        representation_id,
        policy_id,
        cache_scope,
        principal_id,
        vary_values,
        expires_at
    )
    VALUES (
        p_resource_id,
        p_representation_id,
        p_policy_id,
        p_scope,
        p_principal_id,
        COALESCE(p_vary_values, '{}'::JSONB),
        v_expiration
    );
END;
$$;

-- ------------------------------------------------------------
-- 12. Conditional request evaluation
--
-- If-None-Match takes precedence over If-Modified-Since.
-- GET and HEAD can return 304 when the representation matches.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_conditional_request(
    p_representation_id BIGINT,
    p_method http_method,
    p_if_none_match TEXT,
    p_if_modified_since TIMESTAMPTZ
)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_etag TEXT;
    v_modified TIMESTAMPTZ;
    v_candidate TEXT;
BEGIN
    SELECT etag, last_modified
    INTO v_etag, v_modified
    FROM representations
    WHERE representation_id = p_representation_id;

    IF NOT FOUND THEN
        RETURN 404;
    END IF;

    IF p_method NOT IN ('GET', 'HEAD') THEN
        RETURN 200;
    END IF;

    IF p_if_none_match IS NOT NULL THEN

        FOREACH v_candidate IN ARRAY
            string_to_array(p_if_none_match, ',')
        LOOP
            v_candidate := TRIM(v_candidate);

            IF v_candidate = '*'
               OR regexp_replace(
                   v_candidate,
                   '^W/',
                   ''
               ) = regexp_replace(
                   v_etag,
                   '^W/',
                   ''
               ) THEN
                RETURN 304;
            END IF;
        END LOOP;

    ELSIF p_if_modified_since IS NOT NULL
       AND DATE_TRUNC('second', v_modified)
           <= DATE_TRUNC('second', p_if_modified_since) THEN

        RETURN 304;
    END IF;

    RETURN 200;
END;
$$;

-- ------------------------------------------------------------
-- 13. Cache lookup
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION find_cache_entry(
    p_resource_id BIGINT,
    p_scope cache_scope,
    p_principal_id VARCHAR(150),
    p_vary_values JSONB DEFAULT '{}'::JSONB
)
RETURNS TABLE (
    cache_entry_id BIGINT,
    representation_id BIGINT,
    etag VARCHAR(150),
    response_body JSONB,
    fresh BOOLEAN,
    expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.cache_entry_id,
        ce.representation_id,
        r.etag,
        r.response_body,
        (
            ce.expires_at > NOW()
            AND NOT cp.no_cache
        ) AS fresh,
        ce.expires_at
    FROM cache_entries ce
    JOIN representations r
        ON r.representation_id = ce.representation_id
    JOIN cache_policies cp
        ON cp.policy_id = ce.policy_id
    WHERE ce.resource_id = p_resource_id
      AND ce.cache_scope = p_scope
      AND ce.principal_id IS NOT DISTINCT FROM p_principal_id
      AND ce.vary_values = COALESCE(
          p_vary_values,
          '{}'::JSONB
      )
    ORDER BY ce.stored_at DESC
    LIMIT 1;
END;
$$;

-- ------------------------------------------------------------
-- 14. Invalidation procedure
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE invalidate_resource_cache(
    p_resource_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_removed INTEGER;
BEGIN
    DELETE FROM cache_entries
    WHERE resource_id = p_resource_id;

    GET DIAGNOSTICS v_removed = ROW_COUNT;

    INSERT INTO cache_events (
        resource_id,
        event_type
    )
    VALUES (
        p_resource_id,
        'INVALIDATION'
    );

    RAISE NOTICE
        'Invalidated % cache entries for resource %',
        v_removed,
        p_resource_id;
END;
$$;

-- ------------------------------------------------------------
-- 15. Automatic timestamp management
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_resource_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER resource_timestamp_trigger
BEFORE UPDATE ON api_resources
FOR EACH ROW
EXECUTE FUNCTION update_resource_timestamp();

-- ------------------------------------------------------------
-- 16. Monitoring view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW cache_performance_report AS
SELECT
    r.resource_id,
    r.resource_path,
    COUNT(e.event_id) AS total_requests,

    COUNT(*) FILTER (
        WHERE e.event_type = 'HIT'
    ) AS cache_hits,

    COUNT(*) FILTER (
        WHERE e.event_type = 'MISS'
    ) AS cache_misses,

    COUNT(*) FILTER (
        WHERE e.event_type = 'REVALIDATED'
    ) AS revalidations,

    COUNT(*) FILTER (
        WHERE e.event_type = 'BYPASS'
    ) AS bypasses,

    ROUND(
        100.0 *
        COUNT(*) FILTER (
            WHERE e.event_type = 'HIT'
        ) /
        NULLIF(COUNT(e.event_id), 0),
        2
    ) AS hit_ratio_percent,

    ROUND(
        AVG(e.response_time_ms),
        3
    ) AS average_response_time_ms

FROM api_resources r
LEFT JOIN cache_events e
    ON e.resource_id = r.resource_id
GROUP BY
    r.resource_id,
    r.resource_path;

-- ------------------------------------------------------------
-- 17. Sample policies
-- ------------------------------------------------------------

INSERT INTO cache_policies (
    policy_name,
    scope,
    max_age,
    s_maxage,
    must_revalidate
)
VALUES
(
    'public_catalog',
    'PUBLIC',
    60,
    300,
    TRUE
),
(
    'private_account',
    'PRIVATE',
    30,
    NULL,
    TRUE
),
(
    'uncacheable_sensitive',
    'PRIVATE',
    0,
    NULL,
    FALSE
),
(
    'public_immutable_assets',
    'PUBLIC',
    86400,
    86400,
    FALSE
);

-- ------------------------------------------------------------
-- 18. Sample resources
-- ------------------------------------------------------------

INSERT INTO api_resources (
    resource_path,
    resource_name
)
VALUES
(
    '/api/products/1001',
    'Industrial Sensor'
),
(
    '/api/products/1002',
    'Network Gateway'
),
(
    '/api/accounts/5001',
    'Customer Account'
),
(
    '/api/configuration/1',
    'System Configuration'
);

-- ------------------------------------------------------------
-- 19. Sample representations
-- ------------------------------------------------------------

INSERT INTO representations (
    resource_id,
    version_number,
    response_body,
    etag,
    is_current
)
SELECT
    resource_id,
    1,
    CASE resource_path
        WHEN '/api/products/1001' THEN
            '{"id":1001,"name":"Industrial Sensor","price":2500,"stock":40}'::JSONB
        WHEN '/api/products/1002' THEN
            '{"id":1002,"name":"Network Gateway","price":8500,"stock":12}'::JSONB
        WHEN '/api/accounts/5001' THEN
            '{"id":5001,"balance":50000,"currency":"INR"}'::JSONB
        ELSE
            '{"maintenance_mode":false,"version":"2.0"}'::JSONB
    END,
    '"initial-version-' || resource_id || '"',
    TRUE
FROM api_resources;

-- ------------------------------------------------------------
-- 20. Policy assignments
-- ------------------------------------------------------------

INSERT INTO resource_policy_assignments (
    resource_id,
    policy_id
)
SELECT
    r.resource_id,
    p.policy_id
FROM api_resources r
JOIN cache_policies p
    ON p.policy_name = CASE
        WHEN r.resource_path LIKE '/api/products/%'
            THEN 'public_catalog'
        WHEN r.resource_path LIKE '/api/accounts/%'
            THEN 'private_account'
        ELSE 'public_immutable_assets'
    END;

-- ------------------------------------------------------------
-- 21. Vary configuration
-- ------------------------------------------------------------

INSERT INTO vary_headers (
    resource_id,
    header_name
)
SELECT
    resource_id,
    'accept-encoding'
FROM api_resources
WHERE resource_path LIKE '/api/products/%';

INSERT INTO vary_headers (
    resource_id,
    header_name
)
SELECT
    resource_id,
    'accept-language'
FROM api_resources
WHERE resource_path LIKE '/api/products/%';

-- ------------------------------------------------------------
-- 22. Sample HTTP requests
-- ------------------------------------------------------------

INSERT INTO http_requests (
    resource_id,
    method,
    principal_id,
    if_none_match
)
SELECT
    resource_id,
    'GET',
    'catalog-service',
    NULL
FROM api_resources
WHERE resource_path = '/api/products/1001';

INSERT INTO http_requests (
    resource_id,
    method,
    principal_id,
    if_none_match
)
SELECT
    resource_id,
    'GET',
    'catalog-service',
    '"initial-version-' || resource_id || '"'
FROM api_resources
WHERE resource_path = '/api/products/1001';

INSERT INTO http_requests (
    resource_id,
    method,
    principal_id,
    request_no_store
)
SELECT
    resource_id,
    'GET',
    'account-service',
    TRUE
FROM api_resources
WHERE resource_path = '/api/accounts/5001';

-- ------------------------------------------------------------
-- 23. Store public cache entries
-- ------------------------------------------------------------

DO $$
DECLARE
    v_resource BIGINT;
    v_representation BIGINT;
    v_policy BIGINT;
BEGIN
    SELECT resource_id
    INTO v_resource
    FROM api_resources
    WHERE resource_path = '/api/products/1001';

    SELECT representation_id
    INTO v_representation
    FROM representations
    WHERE resource_id = v_resource
      AND is_current;

    SELECT policy_id
    INTO v_policy
    FROM cache_policies
    WHERE policy_name = 'public_catalog';

    CALL store_cache_entry(
        v_resource,
        v_representation,
        v_policy,
        'PUBLIC',
        NULL,
        '{"accept-encoding":"gzip","accept-language":"en"}'::JSONB
    );
END;
$$;

-- ------------------------------------------------------------
-- 24. Store private cache entry
-- ------------------------------------------------------------

DO $$
DECLARE
    v_resource BIGINT;
    v_representation BIGINT;
    v_policy BIGINT;
BEGIN
    SELECT resource_id
    INTO v_resource
    FROM api_resources
    WHERE resource_path = '/api/accounts/5001';

    SELECT representation_id
    INTO v_representation
    FROM representations
    WHERE resource_id = v_resource
      AND is_current;

    SELECT policy_id
    INTO v_policy
    FROM cache_policies
    WHERE policy_name = 'private_account';

    CALL store_cache_entry(
        v_resource,
        v_representation,
        v_policy,
        'PRIVATE',
        'account-service-5001',
        '{}'::JSONB
    );
END;
$$;

-- ------------------------------------------------------------
-- 25. Sample event history
-- ------------------------------------------------------------

INSERT INTO cache_events (
    request_id,
    resource_id,
    event_type,
    http_status,
    response_time_ms
)
SELECT
    request_id,
    resource_id,
    CASE
        WHEN if_none_match IS NULL THEN 'MISS'::cache_event_type
        ELSE 'REVALIDATED'::cache_event_type
    END,
    CASE
        WHEN if_none_match IS NULL THEN 200
        ELSE 304
    END,
    CASE
        WHEN if_none_match IS NULL THEN 85.500
        ELSE 12.200
    END
FROM http_requests
WHERE resource_id IS NOT NULL;

INSERT INTO cache_events (
    resource_id,
    event_type,
    http_status,
    response_time_ms
)
SELECT
    resource_id,
    'BYPASS',
    200,
    92.500
FROM api_resources
WHERE resource_path = '/api/accounts/5001';

-- ------------------------------------------------------------
-- 26. Retrieval queries
-- ------------------------------------------------------------

SELECT
    r.resource_path,
    rep.version_number,
    rep.etag,
    rep.last_modified,
    rep.response_body
FROM api_resources r
JOIN representations rep
    ON rep.resource_id = r.resource_id
WHERE rep.is_current = TRUE
ORDER BY r.resource_path;

-- ------------------------------------------------------------
-- 27. Conditional request evaluation
-- ------------------------------------------------------------

SELECT
    resource_path,
    evaluate_conditional_request(
        rep.representation_id,
        'GET',
        rep.etag,
        NULL
    ) AS conditional_http_status
FROM api_resources r
JOIN representations rep
    ON rep.resource_id = r.resource_id
WHERE rep.is_current;

-- ------------------------------------------------------------
-- 28. Cache eligibility validation
-- ------------------------------------------------------------

SELECT
    p.policy_name,
    evaluate_cache_eligibility(
        p.policy_id,
        'GET',
        TRUE
    ) AS authenticated_get_eligible,
    evaluate_cache_eligibility(
        p.policy_id,
        'POST',
        TRUE
    ) AS authenticated_post_eligible
FROM cache_policies p
ORDER BY p.policy_id;

-- ------------------------------------------------------------
-- 29. Cache lookup
-- ------------------------------------------------------------

SELECT *
FROM find_cache_entry(
    (
        SELECT resource_id
        FROM api_resources
        WHERE resource_path = '/api/products/1001'
    ),
    'PUBLIC',
    NULL,
    '{"accept-encoding":"gzip","accept-language":"en"}'::JSONB
);

-- ------------------------------------------------------------
-- 30. Aggregation and monitoring
-- ------------------------------------------------------------

SELECT *
FROM cache_performance_report
ORDER BY resource_path;

-- ------------------------------------------------------------
-- 31. Policy comparison
-- ------------------------------------------------------------

SELECT
    policy_name,
    scope,
    max_age,
    s_maxage,
    CASE
        WHEN s_maxage IS NOT NULL THEN s_maxage
        ELSE max_age
    END AS effective_shared_lifetime,
    no_store,
    no_cache,
    must_revalidate
FROM cache_policies
ORDER BY policy_name;

-- ------------------------------------------------------------
-- 32. Expired-entry inspection
-- ------------------------------------------------------------

SELECT
    cache_entry_id,
    resource_id,
    expires_at,
    expires_at <= NOW() AS expired
FROM cache_entries
ORDER BY expires_at;

-- ------------------------------------------------------------
-- 33. Transactional invalidation
-- ------------------------------------------------------------

SAVEPOINT before_cache_invalidation;

DO $$
DECLARE
    v_resource BIGINT;
BEGIN
    SELECT resource_id
    INTO v_resource
    FROM api_resources
    WHERE resource_path = '/api/products/1002';

    CALL invalidate_resource_cache(v_resource);
END;
$$;

-- Retain the invalidation.
RELEASE SAVEPOINT before_cache_invalidation;

-- ------------------------------------------------------------
-- 34. Database integrity checks
-- ------------------------------------------------------------

SELECT
    resource_id,
    COUNT(*) AS current_representation_count
FROM representations
WHERE is_current
GROUP BY resource_id
HAVING COUNT(*) > 1;

SELECT
    ce.cache_entry_id,
    ce.resource_id,
    ce.cache_scope,
    ce.principal_id
FROM cache_entries ce
WHERE ce.cache_scope = 'PRIVATE'
  AND ce.principal_id IS NULL;

-- ------------------------------------------------------------
-- 35. Operational cleanup
-- ------------------------------------------------------------

-- Expired entries may be removed periodically.
-- Expiration checks must occur before serving an entry.
DELETE FROM cache_entries
WHERE expires_at < NOW() - INTERVAL '1 day';

COMMIT;

-- ============================================================
-- PRODUCTION NOTES
--
-- 1. Keep credentials and authorization data outside cache keys
--    exposed to logs.
-- 2. Restrict access to private cache entries by principal.
-- 3. Use a transaction or advisory lock for concurrent writes.
-- 4. ETags must identify the selected representation.
-- 5. Vary dimensions must be included in cache identity.
-- 6. A 304 response retains the stored representation body.
-- 7. no-store prohibits storage.
-- 8. no-cache requires validation before reuse.
-- 9. s-maxage applies to shared caches.
-- 10. Use partitioning or retention policies for large event tables.
-- ============================================================

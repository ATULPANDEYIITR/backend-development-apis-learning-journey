/*
===============================================================================
REDIS CACHING: RELATIONAL CACHE MANAGEMENT AND CONSISTENCY MODEL
===============================================================================

PostgreSQL 15+ compatible.

Models:
    1. Authoritative source records
    2. Cache entries
    3. Cache expiration
    4. Cache-aside
    5. Write-through
    6. Cache invalidation
    7. Cache event auditing
    8. Cache policies
    9. Version-based stale-write prevention
   10. Cache performance reporting

The cache_entries table simulates Redis storage relationally.
PostgreSQL is the authoritative database in this demonstration.

Redis itself is an independent in-memory data store. A production
implementation would connect the application to Redis using a Redis client.

Execute the complete script in a PostgreSQL database.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS redis_learning;

SET search_path TO redis_learning, public;


-- ============================================================================
-- 1. ENUM TYPES
-- ============================================================================

CREATE TYPE cache_strategy AS ENUM (
    'CACHE_ASIDE',
    'WRITE_THROUGH'
);

CREATE TYPE cache_event_type AS ENUM (
    'HIT',
    'MISS',
    'WRITE',
    'INVALIDATE',
    'EXPIRE',
    'SOURCE_UPDATE',
    'SOURCE_DELETE',
    'CACHE_ERROR'
);


-- ============================================================================
-- 2. AUTHORITATIVE SOURCE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_name VARCHAR(200) NOT NULL,

    price NUMERIC(14, 2) NOT NULL
        CHECK (price >= 0),

    version BIGINT NOT NULL DEFAULT 1
        CHECK (version > 0),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_active
    ON products (product_id)
    WHERE is_active = TRUE;


-- ============================================================================
-- 3. CACHE POLICY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS cache_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(100) NOT NULL UNIQUE,

    strategy cache_strategy NOT NULL,

    ttl_seconds INTEGER NOT NULL
        CHECK (ttl_seconds > 0),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- 4. CACHE ENTRY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key VARCHAR(512) PRIMARY KEY,

    product_id BIGINT NOT NULL
        REFERENCES products(product_id)
        ON DELETE CASCADE,

    cached_payload JSONB NOT NULL
        CHECK (jsonb_typeof(cached_payload) = 'object'),

    source_version BIGINT NOT NULL
        CHECK (source_version > 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_cache_expiration
    ON cache_entries (expires_at);

CREATE INDEX IF NOT EXISTS idx_cache_product
    ON cache_entries (product_id);

CREATE INDEX IF NOT EXISTS idx_cache_source_version
    ON cache_entries (product_id, source_version);


-- ============================================================================
-- 5. CACHE EVENT AUDIT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS cache_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cache_key VARCHAR(512) NOT NULL,

    product_id BIGINT,

    event_type cache_event_type NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cache_events_time
    ON cache_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_cache_events_type
    ON cache_events (event_type, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_cache_events_product
    ON cache_events (product_id, occurred_at DESC);


-- ============================================================================
-- 6. EVENT AUDITING FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION log_cache_event(
    p_key VARCHAR,
    p_product_id BIGINT,
    p_event cache_event_type,
    p_details JSONB DEFAULT '{}'::JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id BIGINT;
BEGIN
    INSERT INTO cache_events (
        cache_key,
        product_id,
        event_type,
        event_details
    )
    VALUES (
        p_key,
        p_product_id,
        p_event,
        COALESCE(p_details, '{}'::JSONB)
    )
    RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$;


-- ============================================================================
-- 7. CACHE ENTRY EXPIRATION VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_cache_entry()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_version BIGINT;
BEGIN
    SELECT version
    INTO v_source_version
    FROM products
    WHERE product_id = NEW.product_id
      AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Cannot cache inactive or missing product %',
            NEW.product_id;
    END IF;

    IF NEW.source_version > v_source_version THEN
        RAISE EXCEPTION
            'Cache version cannot exceed source version';
    END IF;

    IF NEW.source_version < v_source_version THEN
        RAISE EXCEPTION
            'Stale cache publication rejected: source version %, cache version %',
            v_source_version,
            NEW.source_version;
    END IF;

    IF NEW.expires_at <= NOW() THEN
        RAISE EXCEPTION 'Cache expiration must be in the future';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_cache_entry
    ON cache_entries;

CREATE TRIGGER trg_validate_cache_entry
BEFORE INSERT OR UPDATE ON cache_entries
FOR EACH ROW
EXECUTE FUNCTION validate_cache_entry();


-- ============================================================================
-- 8. CACHE INVALIDATION AFTER SOURCE CHANGES
-- ============================================================================

CREATE OR REPLACE FUNCTION invalidate_product_cache()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_product_id BIGINT;
    v_cache_key VARCHAR(512);
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_product_id := OLD.product_id;
    ELSE
        v_product_id := NEW.product_id;
    END IF;

    v_cache_key := 'products:' || v_product_id;

    /*
       This trigger runs in the source transaction.

       If source modification and invalidation fail, the transaction
       rolls back. This avoids silently committing a source update while
       retaining an invalid cache record in this relational model.
    */

    DELETE FROM cache_entries
    WHERE product_id = v_product_id;

    PERFORM log_cache_event(
        v_cache_key,
        v_product_id,
        CASE
            WHEN TG_OP = 'DELETE'
                THEN 'SOURCE_DELETE'::cache_event_type
            ELSE 'SOURCE_UPDATE'::cache_event_type
        END,
        jsonb_build_object(
            'operation', TG_OP,
            'invalidated', TRUE
        )
    );

    RETURN CASE
        WHEN TG_OP = 'DELETE' THEN OLD
        ELSE NEW
    END;
END;
$$;

DROP TRIGGER IF EXISTS trg_product_cache_invalidation
    ON products;

CREATE TRIGGER trg_product_cache_invalidation
AFTER UPDATE OR DELETE ON products
FOR EACH ROW
EXECUTE FUNCTION invalidate_product_cache();


-- ============================================================================
-- 9. CACHE-ASIDE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION get_product_cached(
    p_product_id BIGINT,
    p_ttl_seconds INTEGER DEFAULT 30
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_key VARCHAR(512);
    v_payload JSONB;
    v_version BIGINT;
    v_expiration TIMESTAMPTZ;
BEGIN
    IF p_product_id <= 0 THEN
        RAISE EXCEPTION 'Product ID must be positive';
    END IF;

    IF p_ttl_seconds <= 0 THEN
        RAISE EXCEPTION 'TTL must be positive';
    END IF;

    v_key := 'products:' || p_product_id;

    /*
       Cache lookup.

       FOR UPDATE serializes access to an existing cache row.
       An application-level Redis implementation should use appropriate
       atomic operations or distributed locking where necessary.
    */

    SELECT cached_payload
    INTO v_payload
    FROM cache_entries
    WHERE cache_key = v_key
      AND expires_at > NOW();

    IF FOUND THEN
        PERFORM log_cache_event(
            v_key,
            p_product_id,
            'HIT',
            jsonb_build_object('strategy', 'CACHE_ASIDE')
        );

        RETURN v_payload;
    END IF;

    -- Remove an expired entry before loading the source.
    DELETE FROM cache_entries
    WHERE cache_key = v_key
      AND expires_at <= NOW();

    PERFORM log_cache_event(
        v_key,
        p_product_id,
        'MISS',
        jsonb_build_object('strategy', 'CACHE_ASIDE')
    );

    -- Load authoritative source data.
    SELECT jsonb_build_object(
        'product_id', product_id,
        'product_name', product_name,
        'price', price,
        'version', version,
        'updated_at', updated_at
    ), version
    INTO v_payload, v_version
    FROM products
    WHERE product_id = p_product_id
      AND is_active = TRUE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    v_expiration := NOW() + make_interval(
        secs => p_ttl_seconds
    );

    INSERT INTO cache_entries (
        cache_key,
        product_id,
        cached_payload,
        source_version,
        expires_at
    )
    VALUES (
        v_key,
        p_product_id,
        v_payload,
        v_version,
        v_expiration
    )
    ON CONFLICT (cache_key)
    DO UPDATE SET
        cached_payload = EXCLUDED.cached_payload,
        source_version = EXCLUDED.source_version,
        created_at = NOW(),
        expires_at = EXCLUDED.expires_at;

    PERFORM log_cache_event(
        v_key,
        p_product_id,
        'WRITE',
        jsonb_build_object(
            'strategy', 'CACHE_ASIDE',
            'ttl_seconds', p_ttl_seconds
        )
    );

    RETURN v_payload;
END;
$$;


-- ============================================================================
-- 10. WRITE-THROUGH PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE update_product_write_through(
    p_product_id BIGINT,
    p_product_name VARCHAR,
    p_price NUMERIC,
    p_ttl_seconds INTEGER DEFAULT 30
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_version BIGINT;
    v_payload JSONB;
    v_key VARCHAR(512);
BEGIN
    IF p_product_name IS NULL OR
       LENGTH(TRIM(p_product_name)) = 0 THEN
        RAISE EXCEPTION 'Product name is required';
    END IF;

    IF p_price < 0 THEN
        RAISE EXCEPTION 'Price cannot be negative';
    END IF;

    IF p_ttl_seconds <= 0 THEN
        RAISE EXCEPTION 'TTL must be positive';
    END IF;

    /*
       Source modification and cache publication occur in one database
       transaction. PostgreSQL commits both operations together.
    */

    UPDATE products
    SET
        product_name = p_product_name,
        price = p_price,
        version = version + 1,
        updated_at = NOW()
    WHERE product_id = p_product_id
      AND is_active = TRUE
    RETURNING version INTO v_version;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product % does not exist', p_product_id;
    END IF;

    v_key := 'products:' || p_product_id;

    v_payload := jsonb_build_object(
        'product_id', p_product_id,
        'product_name', p_product_name,
        'price', p_price,
        'version', v_version,
        'updated_at', NOW()
    );

    /*
       The source update trigger invalidates the previous cache row.
       This operation publishes the new version.
    */

    INSERT INTO cache_entries (
        cache_key,
        product_id,
        cached_payload,
        source_version,
        expires_at
    )
    VALUES (
        v_key,
        p_product_id,
        v_payload,
        v_version,
        NOW() + make_interval(secs => p_ttl_seconds)
    )
    ON CONFLICT (cache_key)
    DO UPDATE SET
        cached_payload = EXCLUDED.cached_payload,
        source_version = EXCLUDED.source_version,
        created_at = NOW(),
        expires_at = EXCLUDED.expires_at;

    PERFORM log_cache_event(
        v_key,
        p_product_id,
        'WRITE',
        jsonb_build_object(
            'strategy', 'WRITE_THROUGH',
            'version', v_version,
            'ttl_seconds', p_ttl_seconds
        )
    );
END;
$$;


-- ============================================================================
-- 11. EXPLICIT INVALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION invalidate_product_cache_by_id(
    p_product_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_key VARCHAR(512);
    v_deleted BOOLEAN;
BEGIN
    IF p_product_id <= 0 THEN
        RAISE EXCEPTION 'Product ID must be positive';
    END IF;

    v_key := 'products:' || p_product_id;

    DELETE FROM cache_entries
    WHERE product_id = p_product_id;

    v_deleted := FOUND;

    PERFORM log_cache_event(
        v_key,
        p_product_id,
        'INVALIDATE',
        jsonb_build_object('deleted', v_deleted)
    );

    RETURN v_deleted;
END;
$$;


-- ============================================================================
-- 12. EXPIRED ENTRY CLEANUP PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE cleanup_expired_cache()
LANGUAGE plpgsql
AS $$
DECLARE
    v_removed INTEGER;
BEGIN
    WITH expired AS (
        DELETE FROM cache_entries
        WHERE expires_at <= NOW()
        RETURNING cache_key, product_id
    )
    SELECT COUNT(*)
    INTO v_removed
    FROM expired;

    PERFORM log_cache_event(
        'cache:cleanup',
        NULL,
        'EXPIRE',
        jsonb_build_object('removed_entries', v_removed)
    );

    RAISE NOTICE 'Expired cache entries removed: %', v_removed;
END;
$$;


-- ============================================================================
-- 13. CACHE REPORTING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW cache_performance_report AS
SELECT
    COUNT(*) FILTER (
        WHERE event_type = 'HIT'
    ) AS cache_hits,

    COUNT(*) FILTER (
        WHERE event_type = 'MISS'
    ) AS cache_misses,

    COUNT(*) FILTER (
        WHERE event_type = 'WRITE'
    ) AS cache_writes,

    COUNT(*) FILTER (
        WHERE event_type = 'INVALIDATE'
    ) AS invalidations,

    COUNT(*) FILTER (
        WHERE event_type = 'EXPIRE'
    ) AS expiration_events,

    COUNT(*) FILTER (
        WHERE event_type = 'CACHE_ERROR'
    ) AS cache_errors,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE event_type IN ('HIT', 'MISS')
        ) = 0 THEN 0

        ELSE ROUND(
            COUNT(*) FILTER (
                WHERE event_type = 'HIT'
            )::NUMERIC
            /
            COUNT(*) FILTER (
                WHERE event_type IN ('HIT', 'MISS')
            ),
            4
        )
    END AS hit_rate

FROM cache_events;


-- ============================================================================
-- 14. PRODUCT CACHE STATUS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW product_cache_status AS
SELECT
    p.product_id,
    p.product_name,
    p.version AS source_version,

    c.source_version AS cached_version,

    CASE
        WHEN c.cache_key IS NULL THEN 'NOT_CACHED'
        WHEN c.expires_at <= NOW() THEN 'EXPIRED'
        WHEN c.source_version <> p.version THEN 'STALE'
        ELSE 'VALID'
    END AS cache_status,

    c.expires_at

FROM products p

LEFT JOIN cache_entries c
    ON c.product_id = p.product_id;


-- ============================================================================
-- 15. SAMPLE CACHE POLICIES
-- ============================================================================

INSERT INTO cache_policies (
    policy_name,
    strategy,
    ttl_seconds,
    description
)
VALUES
(
    'PRODUCT_CACHE_ASIDE',
    'CACHE_ASIDE',
    30,
    'Load source data on cache miss.'
),
(
    'PRODUCT_WRITE_THROUGH',
    'WRITE_THROUGH',
    60,
    'Publish updated source data to cache.'
)
ON CONFLICT (policy_name)
DO UPDATE SET
    strategy = EXCLUDED.strategy,
    ttl_seconds = EXCLUDED.ttl_seconds,
    description = EXCLUDED.description;


-- ============================================================================
-- 16. SAMPLE PRODUCTS
-- ============================================================================

INSERT INTO products (
    product_name,
    price
)
VALUES
    ('Enterprise Laptop', 85000),
    ('Database Server', 145000),
    ('Cloud Storage Appliance', 95000),
    ('Network Security Gateway', 65000),
    ('Backup Infrastructure', 0);


-- ============================================================================
-- 17. CACHE-ASIDE EXECUTION
-- ============================================================================

SELECT get_product_cached(1, 30);

-- Second request should produce a cache hit.
SELECT get_product_cached(1, 30);


-- ============================================================================
-- 18. WRITE-THROUGH EXECUTION
-- ============================================================================

CALL update_product_write_through(
    1,
    'Enterprise Laptop Pro',
    99000,
    60
);

SELECT get_product_cached(1, 60);


-- ============================================================================
-- 19. CACHE-ASIDE SOURCE UPDATE AND INVALIDATION
-- ============================================================================

UPDATE products
SET
    price = 105000,
    product_name = 'Enterprise Laptop Premium',
    version = version + 1,
    updated_at = NOW()
WHERE product_id = 1;

-- The trigger invalidates the old cache entry.
-- This request reloads the latest source version.
SELECT get_product_cached(1, 30);


-- ============================================================================
-- 20. EXPLICIT CACHE INVALIDATION
-- ============================================================================

SELECT invalidate_product_cache_by_id(2);

SELECT get_product_cached(2, 30);


-- ============================================================================
-- 21. NEGATIVE AND EDGE-CASE VALIDATION
-- ============================================================================

DO $$
BEGIN
    -- Negative price must be rejected by the source constraint.
    BEGIN
        INSERT INTO products (product_name, price)
        VALUES ('Invalid Product', -100);

        RAISE EXCEPTION 'Negative price validation failed';

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Negative price correctly rejected';
    END;

    -- Invalid TTL must be rejected by the cache function.
    BEGIN
        PERFORM get_product_cached(1, 0);

        RAISE EXCEPTION 'TTL validation failed';

    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'TTL validation failed' THEN
                RAISE;
            END IF;

            RAISE NOTICE 'Invalid TTL correctly rejected';
    END;

    -- A missing product returns NULL.
    IF get_product_cached(999999, 30) IS NOT NULL THEN
        RAISE EXCEPTION 'Missing product handling failed';
    END IF;
END;
$$;


-- ============================================================================
-- 22. CACHE ELIGIBILITY AND VERSION VALIDATION
-- ============================================================================

SELECT
    product_id,
    product_name,
    source_version,
    cached_version,
    cache_status
FROM product_cache_status
ORDER BY product_id;


-- ============================================================================
-- 23. CACHE AGGREGATION
-- ============================================================================

SELECT
    event_type,
    COUNT(*) AS total_events
FROM cache_events
GROUP BY event_type
ORDER BY total_events DESC;


-- ============================================================================
-- 24. CACHE PERFORMANCE REPORT
-- ============================================================================

SELECT *
FROM cache_performance_report;


-- ============================================================================
-- 25. PRODUCT CACHE RETRIEVAL REPORT
-- ============================================================================

SELECT
    p.product_id,
    p.product_name,
    p.price,
    p.version,
    c.source_version,
    c.expires_at
FROM products p
LEFT JOIN cache_entries c
    ON c.product_id = p.product_id
ORDER BY p.product_id;


-- ============================================================================
-- 26. EVENT AUDIT REPORT
-- ============================================================================

SELECT
    event_id,
    cache_key,
    product_id,
    event_type,
    event_details,
    occurred_at
FROM cache_events
ORDER BY occurred_at DESC
LIMIT 50;


-- ============================================================================
-- 27. CLEANUP DEMONSTRATION
-- ============================================================================

CALL cleanup_expired_cache();


-- ============================================================================
-- 28. TRANSACTIONAL FAILURE HANDLING
-- ============================================================================

/*
A failed source update and its cache invalidation must not leave a
partially committed database transaction.

Example:

BEGIN;
UPDATE products
SET price = -100
WHERE product_id = 1;
ROLLBACK;

The CHECK constraint rejects the invalid modification.
The transaction must be rolled back by the client.
*/


-- ============================================================================
-- 29. FINAL INTEGRITY CHECKS
-- ============================================================================

DO $$
DECLARE
    v_invalid_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO v_invalid_count
    FROM cache_entries c
    JOIN products p
        ON p.product_id = c.product_id
    WHERE c.source_version <> p.version
       OR c.expires_at <= NOW();

    IF v_invalid_count > 0 THEN
        RAISE WARNING
            'Invalid or expired cache entries detected: %',
            v_invalid_count;
    ELSE
        RAISE NOTICE
            'Cache integrity validation passed';
    END IF;
END;
$$;


COMMIT;


-- ============================================================================
-- 30. ADDITIONAL OPERATIONAL QUERIES
-- ============================================================================

-- Find active cached products.
SELECT *
FROM product_cache_status
WHERE cache_status = 'VALID';

-- Find products requiring cache refresh.
SELECT *
FROM product_cache_status
WHERE cache_status IN ('EXPIRED', 'STALE', 'NOT_CACHED');

-- Identify frequently accessed cache keys.
SELECT
    cache_key,
    COUNT(*) AS hit_count
FROM cache_events
WHERE event_type = 'HIT'
GROUP BY cache_key
ORDER BY hit_count DESC
LIMIT 20;

-- Calculate invalidation frequency.
SELECT
    DATE_TRUNC('hour', occurred_at) AS event_hour,
    COUNT(*) AS invalidation_count
FROM cache_events
WHERE event_type = 'INVALIDATE'
GROUP BY event_hour
ORDER BY event_hour DESC;

-- Review current cache policies.
SELECT *
FROM cache_policies
WHERE enabled = TRUE
ORDER BY policy_name;

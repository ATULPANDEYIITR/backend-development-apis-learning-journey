/*
================================================================
API PAGINATION DATABASE ENGINE
================================================================

Topic:
    Offset Pagination
    Cursor Pagination
    Keyset Pagination

Database:
    PostgreSQL 14+

Domain:
    Product catalog API

Features:
    - Relational product repository
    - Stable composite sorting
    - Offset-based page retrieval
    - Signed cursor storage and validation
    - Keyset pagination
    - Cursor expiration
    - Query filters
    - Dataset version tracking
    - Pagination policy enforcement
    - API pagination audit
    - SQL functions
    - Stored procedures
    - Triggers
    - Views
    - Transactions
    - Aggregation and reporting

The schema is recreated when this script is executed.
================================================================
*/

DROP SCHEMA IF EXISTS pagination CASCADE;

CREATE SCHEMA pagination;

SET search_path TO pagination, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE product_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'ARCHIVED'
);

CREATE TYPE pagination_strategy AS ENUM (
    'OFFSET',
    'CURSOR',
    'KEYSET'
);

CREATE TYPE pagination_event AS ENUM (
    'FIRST_PAGE',
    'NEXT_PAGE',
    'PREVIOUS_PAGE',
    'INVALID_CURSOR',
    'EXPIRED_CURSOR',
    'STALE_CURSOR',
    'QUERY_EXECUTED'
);

-- ============================================================
-- 2. REPOSITORY CONFIGURATION
-- ============================================================

CREATE TABLE repository_state (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    repository_name VARCHAR(150) NOT NULL UNIQUE,

    dataset_version BIGINT NOT NULL DEFAULT 1
        CHECK (dataset_version > 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO repository_state (repository_name)
VALUES ('enterprise_product_catalog');

-- ============================================================
-- 3. PRODUCTS
-- ============================================================

CREATE TABLE products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repository_state(repository_id),

    product_name VARCHAR(200) NOT NULL,

    category VARCHAR(100) NOT NULL,

    price NUMERIC(12, 2) NOT NULL
        CHECK (price >= 0),

    status product_status NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT product_name_not_empty
        CHECK (LENGTH(TRIM(product_name)) > 0),

    CONSTRAINT product_category_not_empty
        CHECK (LENGTH(TRIM(category)) > 0),

    CONSTRAINT product_repository_identity
        UNIQUE (repository_id, product_id)
);

-- Composite index supports keyset ordering.
CREATE INDEX idx_products_keyset
ON products (
    repository_id,
    created_at ASC,
    product_id ASC
)
WHERE status = 'ACTIVE';

CREATE INDEX idx_products_category_keyset
ON products (
    repository_id,
    category,
    created_at ASC,
    product_id ASC
)
WHERE status = 'ACTIVE';

CREATE INDEX idx_products_status
ON products (
    repository_id,
    status
);

-- ============================================================
-- 4. PAGINATION POLICIES
-- ============================================================

CREATE TABLE pagination_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repository_state(repository_id),

    strategy pagination_strategy NOT NULL,

    default_page_size INTEGER NOT NULL DEFAULT 10
        CHECK (default_page_size BETWEEN 1 AND 100),

    maximum_page_size INTEGER NOT NULL DEFAULT 50
        CHECK (maximum_page_size BETWEEN 1 AND 100),

    cursor_ttl_seconds INTEGER NOT NULL DEFAULT 1800
        CHECK (cursor_ttl_seconds BETWEEN 60 AND 86400),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    exact_count_allowed BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (repository_id, strategy),

    CHECK (default_page_size <= maximum_page_size)
);

INSERT INTO pagination_policies (
    repository_id,
    strategy,
    default_page_size,
    maximum_page_size,
    cursor_ttl_seconds,
    exact_count_allowed
)
SELECT
    repository_id,
    'OFFSET',
    10,
    100,
    1800,
    TRUE
FROM repository_state

UNION ALL

SELECT
    repository_id,
    'CURSOR',
    10,
    50,
    1800,
    FALSE
FROM repository_state

UNION ALL

SELECT
    repository_id,
    'KEYSET',
    10,
    100,
    1800,
    FALSE
FROM repository_state;

-- ============================================================
-- 5. CURSOR REGISTRY
-- ============================================================

CREATE TABLE pagination_cursors (
    cursor_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repository_state(repository_id),

    cursor_token_hash BYTEA NOT NULL UNIQUE,

    strategy pagination_strategy NOT NULL
        CHECK (strategy IN ('CURSOR', 'KEYSET')),

    boundary_created_at TIMESTAMPTZ NOT NULL,

    boundary_product_id BIGINT NOT NULL,

    filter_fingerprint TEXT NOT NULL DEFAULT '',

    dataset_version BIGINT NOT NULL,

    direction VARCHAR(10) NOT NULL DEFAULT 'FORWARD'
        CHECK (direction IN ('FORWARD', 'BACKWARD')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ,

    CHECK (boundary_product_id > 0),

    CHECK (expires_at > created_at)
);

CREATE INDEX idx_cursor_expiration
ON pagination_cursors (expires_at)
WHERE revoked_at IS NULL;

CREATE INDEX idx_cursor_repository
ON pagination_cursors (
    repository_id,
    dataset_version
);

-- ============================================================
-- 6. API REQUEST AUDIT
-- ============================================================

CREATE TABLE pagination_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repository_state(repository_id),

    strategy pagination_strategy NOT NULL,

    event pagination_event NOT NULL,

    page_size INTEGER NOT NULL
        CHECK (page_size > 0),

    offset_value BIGINT,

    returned_rows INTEGER NOT NULL DEFAULT 0
        CHECK (returned_rows >= 0),

    total_count BIGINT,

    execution_ms NUMERIC(12, 4),

    filter_category VARCHAR(100),

    request_identifier UUID NOT NULL DEFAULT gen_random_uuid(),

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        offset_value IS NULL OR offset_value >= 0
    ),

    CHECK (
        execution_ms IS NULL OR execution_ms >= 0
    )
);

CREATE INDEX idx_audit_repository_time
ON pagination_audit (
    repository_id,
    occurred_at DESC
);

CREATE INDEX idx_audit_strategy_time
ON pagination_audit (
    strategy,
    occurred_at DESC
);

-- ============================================================
-- 7. DATA VERSION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION increment_dataset_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    affected_repository BIGINT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        affected_repository := OLD.repository_id;
    ELSE
        affected_repository := NEW.repository_id;
    END IF;

    UPDATE repository_state
    SET
        dataset_version = dataset_version + 1,
        updated_at = NOW()
    WHERE repository_id = affected_repository;

    RETURN CASE
        WHEN TG_OP = 'DELETE' THEN OLD
        ELSE NEW
    END;
END;
$$;

CREATE TRIGGER trg_product_version
AFTER INSERT OR UPDATE OR DELETE
ON products
FOR EACH ROW
EXECUTE FUNCTION increment_dataset_version();

-- ============================================================
-- 8. POLICY VALIDATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_page_size(
    p_repository_id BIGINT,
    p_strategy pagination_strategy,
    p_page_size INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    policy_record pagination_policies%ROWTYPE;
BEGIN
    IF p_page_size IS NULL OR p_page_size < 1 THEN
        RETURN FALSE;
    END IF;

    SELECT *
    INTO policy_record
    FROM pagination_policies
    WHERE repository_id = p_repository_id
      AND strategy = p_strategy
      AND enabled = TRUE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    RETURN p_page_size <= policy_record.maximum_page_size;
END;
$$;

-- ============================================================
-- 9. OFFSET PAGINATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION get_products_offset(
    p_repository_id BIGINT,
    p_page INTEGER DEFAULT 1,
    p_page_size INTEGER DEFAULT 10,
    p_category VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    product_id BIGINT,
    product_name VARCHAR,
    category VARCHAR,
    price NUMERIC,
    created_at TIMESTAMPTZ,
    total_count BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    calculated_offset BIGINT;
    repository_version BIGINT;
    started_at TIMESTAMPTZ := CLOCK_TIMESTAMP();
BEGIN
    IF p_page IS NULL OR p_page < 1 THEN
        RAISE EXCEPTION 'Page must be positive.';
    END IF;

    IF NOT validate_page_size(
        p_repository_id,
        'OFFSET',
        p_page_size
    ) THEN
        RAISE EXCEPTION 'Invalid offset page size.';
    END IF;

    IF p_page::BIGINT - 1 >
       9223372036854775807::BIGINT / p_page_size THEN
        RAISE EXCEPTION 'Offset overflow.';
    END IF;

    calculated_offset :=
        (p_page::BIGINT - 1) * p_page_size;

    SELECT dataset_version
    INTO repository_version
    FROM repository_state
    WHERE repository_id = p_repository_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Repository not found.';
    END IF;

    RETURN QUERY
    WITH filtered AS (
        SELECT
            p.product_id,
            p.product_name,
            p.category,
            p.price,
            p.created_at
        FROM products p
        WHERE p.repository_id = p_repository_id
          AND p.status = 'ACTIVE'
          AND (
              p_category IS NULL
              OR p.category = p_category
          )
    ),
    totals AS (
        SELECT COUNT(*)::BIGINT AS total
        FROM filtered
    )
    SELECT
        f.product_id,
        f.product_name,
        f.category,
        f.price,
        f.created_at,
        t.total
    FROM filtered f
    CROSS JOIN totals t
    ORDER BY f.created_at, f.product_id
    LIMIT p_page_size
    OFFSET calculated_offset;

    INSERT INTO pagination_audit (
        repository_id,
        strategy,
        event,
        page_size,
        offset_value,
        returned_rows,
        total_count,
        execution_ms,
        filter_category
    )
    SELECT
        p_repository_id,
        'OFFSET',
        'QUERY_EXECUTED',
        p_page_size,
        calculated_offset,
        COUNT(*),
        (
            SELECT COUNT(*)
            FROM products
            WHERE repository_id = p_repository_id
              AND status = 'ACTIVE'
              AND (
                  p_category IS NULL
                  OR category = p_category
              )
        ),
        EXTRACT(
            EPOCH FROM CLOCK_TIMESTAMP() - started_at
        ) * 1000,
        p_category
    FROM products
    WHERE repository_id = p_repository_id
      AND status = 'ACTIVE'
      AND (
          p_category IS NULL
          OR category = p_category
      );

END;
$$;

-- ============================================================
-- 10. KEYSET PAGINATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION get_products_keyset(
    p_repository_id BIGINT,
    p_page_size INTEGER DEFAULT 10,
    p_last_created_at TIMESTAMPTZ DEFAULT NULL,
    p_last_product_id BIGINT DEFAULT NULL,
    p_category VARCHAR DEFAULT NULL,
    p_direction VARCHAR DEFAULT 'ASC'
)
RETURNS TABLE (
    product_id BIGINT,
    product_name VARCHAR,
    category VARCHAR,
    price NUMERIC,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF NOT validate_page_size(
        p_repository_id,
        'KEYSET',
        p_page_size
    ) THEN
        RAISE EXCEPTION 'Invalid keyset page size.';
    END IF;

    IF (
        p_last_created_at IS NULL
        AND p_last_product_id IS NOT NULL
    ) OR (
        p_last_created_at IS NOT NULL
        AND p_last_product_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Both keyset boundary values are required.';
    END IF;

    IF p_last_product_id IS NOT NULL
       AND p_last_product_id <= 0 THEN
        RAISE EXCEPTION 'Invalid keyset product ID.';
    END IF;

    IF p_direction NOT IN ('ASC', 'DESC') THEN
        RAISE EXCEPTION 'Invalid sort direction.';
    END IF;

    IF p_direction = 'ASC' THEN

        RETURN QUERY
        SELECT
            p.product_id,
            p.product_name,
            p.category,
            p.price,
            p.created_at
        FROM products p
        WHERE p.repository_id = p_repository_id
          AND p.status = 'ACTIVE'
          AND (
              p_category IS NULL
              OR p.category = p_category
          )
          AND (
              p_last_created_at IS NULL
              OR (
                  p.created_at,
                  p.product_id
              ) > (
                  p_last_created_at,
                  p_last_product_id
              )
          )
        ORDER BY
            p.created_at ASC,
            p.product_id ASC
        LIMIT p_page_size + 1;

    ELSE

        RETURN QUERY
        SELECT
            p.product_id,
            p.product_name,
            p.category,
            p.price,
            p.created_at
        FROM products p
        WHERE p.repository_id = p_repository_id
          AND p.status = 'ACTIVE'
          AND (
              p_category IS NULL
              OR p.category = p_category
          )
          AND (
              p_last_created_at IS NULL
              OR (
                  p.created_at,
                  p.product_id
              ) < (
                  p_last_created_at,
                  p_last_product_id
              )
          )
        ORDER BY
            p.created_at DESC,
            p.product_id DESC
        LIMIT p_page_size + 1;

    END IF;
END;
$$;

-- ============================================================
-- 11. CURSOR REGISTRATION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE register_cursor(
    IN p_repository_id BIGINT,
    IN p_token TEXT,
    IN p_strategy pagination_strategy,
    IN p_boundary_created_at TIMESTAMPTZ,
    IN p_boundary_product_id BIGINT,
    IN p_filter_fingerprint TEXT,
    IN p_direction VARCHAR DEFAULT 'FORWARD'
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_version BIGINT;
    ttl INTEGER;
BEGIN
    IF p_token IS NULL OR LENGTH(p_token) < 16 THEN
        RAISE EXCEPTION 'Invalid cursor token.';
    END IF;

    IF p_strategy NOT IN ('CURSOR', 'KEYSET') THEN
        RAISE EXCEPTION 'Invalid cursor strategy.';
    END IF;

    IF p_boundary_product_id <= 0 THEN
        RAISE EXCEPTION 'Invalid cursor boundary.';
    END IF;

    IF p_direction NOT IN ('FORWARD', 'BACKWARD') THEN
        RAISE EXCEPTION 'Invalid cursor direction.';
    END IF;

    SELECT
        r.dataset_version,
        p.cursor_ttl_seconds
    INTO
        current_version,
        ttl
    FROM repository_state r
    JOIN pagination_policies p
      ON p.repository_id = r.repository_id
    WHERE r.repository_id = p_repository_id
      AND p.strategy = p_strategy
      AND p.enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No enabled cursor policy.';
    END IF;

    INSERT INTO pagination_cursors (
        repository_id,
        cursor_token_hash,
        strategy,
        boundary_created_at,
        boundary_product_id,
        filter_fingerprint,
        dataset_version,
        direction,
        expires_at
    )
    VALUES (
        p_repository_id,
        digest(p_token, 'sha256'),
        p_strategy,
        p_boundary_created_at,
        p_boundary_product_id,
        COALESCE(p_filter_fingerprint, ''),
        current_version,
        p_direction,
        NOW() + MAKE_INTERVAL(secs => ttl)
    );
END;
$$;

-- ============================================================
-- 12. CURSOR VALIDATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_cursor(
    p_token TEXT,
    p_repository_id BIGINT,
    p_strategy pagination_strategy,
    p_filter_fingerprint TEXT DEFAULT ''
)
RETURNS TABLE (
    valid BOOLEAN,
    failure_reason TEXT,
    boundary_created_at TIMESTAMPTZ,
    boundary_product_id BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    cursor_record pagination_cursors%ROWTYPE;
    current_version BIGINT;
BEGIN
    SELECT *
    INTO cursor_record
    FROM pagination_cursors
    WHERE cursor_token_hash = digest(p_token, 'sha256')
      AND repository_id = p_repository_id
      AND strategy = p_strategy
      AND revoked_at IS NULL;

    IF NOT FOUND THEN
        RETURN QUERY SELECT
            FALSE,
            'CURSOR_NOT_FOUND'::TEXT,
            NULL::TIMESTAMPTZ,
            NULL::BIGINT;
        RETURN;
    END IF;

    IF cursor_record.expires_at < NOW() THEN
        RETURN QUERY SELECT
            FALSE,
            'CURSOR_EXPIRED'::TEXT,
            NULL::TIMESTAMPTZ,
            NULL::BIGINT;
        RETURN;
    END IF;

    IF cursor_record.filter_fingerprint <>
       COALESCE(p_filter_fingerprint, '') THEN
        RETURN QUERY SELECT
            FALSE,
            'FILTER_MISMATCH'::TEXT,
            NULL::TIMESTAMPTZ,
            NULL::BIGINT;
        RETURN;
    END IF;

    SELECT dataset_version
    INTO current_version
    FROM repository_state
    WHERE repository_id = p_repository_id;

    IF current_version <> cursor_record.dataset_version THEN
        RETURN QUERY SELECT
            FALSE,
            'STALE_CURSOR'::TEXT,
            NULL::TIMESTAMPTZ,
            NULL::BIGINT;
        RETURN;
    END IF;

    RETURN QUERY SELECT
        TRUE,
        NULL::TEXT,
        cursor_record.boundary_created_at,
        cursor_record.boundary_product_id;
END;
$$;

-- ============================================================
-- 13. CURSOR CLEANUP PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE cleanup_expired_cursors()
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM pagination_cursors
    WHERE expires_at < NOW()
       OR revoked_at IS NOT NULL;
END;
$$;

-- ============================================================
-- 14. PAGINATION REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW pagination_strategy_report AS
SELECT
    strategy,
    COUNT(*) AS request_count,
    SUM(returned_rows) AS returned_records,
    ROUND(
        AVG(execution_ms),
        4
    ) AS average_execution_ms,
    MAX(execution_ms) AS maximum_execution_ms,
    COUNT(*) FILTER (
        WHERE event = 'INVALID_CURSOR'
    ) AS invalid_cursor_count,
    COUNT(*) FILTER (
        WHERE event = 'STALE_CURSOR'
    ) AS stale_cursor_count
FROM pagination_audit
GROUP BY strategy;

-- ============================================================
-- 15. PRODUCT CATEGORY AGGREGATION VIEW
-- ============================================================

CREATE OR REPLACE VIEW product_category_statistics AS
SELECT
    repository_id,
    category,
    COUNT(*) AS active_products,
    ROUND(AVG(price), 2) AS average_price,
    MIN(price) AS minimum_price,
    MAX(price) AS maximum_price
FROM products
WHERE status = 'ACTIVE'
GROUP BY repository_id, category;

-- ============================================================
-- 16. SAMPLE DATA
-- ============================================================

INSERT INTO products (
    repository_id,
    product_name,
    category,
    price,
    status,
    created_at
)
SELECT
    r.repository_id,
    'Product ' || n,
    CASE
        WHEN n % 4 = 0 THEN 'Electronics'
        WHEN n % 4 = 1 THEN 'Books'
        WHEN n % 4 = 2 THEN 'Furniture'
        ELSE 'Software'
    END,
    100.00 + n * 25.50,
    CASE
        WHEN n % 13 = 0 THEN 'INACTIVE'::product_status
        WHEN n % 17 = 0 THEN 'ARCHIVED'::product_status
        ELSE 'ACTIVE'::product_status
    END,
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
        + (n / 2) * INTERVAL '1 minute'
FROM repository_state r
CROSS JOIN generate_series(1, 100) AS n;

-- ============================================================
-- 17. OFFSET PAGINATION EXAMPLE
-- ============================================================

SELECT *
FROM get_products_offset(
    1,
    2,
    10,
    NULL
);

-- Category-specific offset pagination.
SELECT *
FROM get_products_offset(
    1,
    1,
    5,
    'Electronics'
);

-- ============================================================
-- 18. KEYSET PAGINATION EXAMPLE
-- ============================================================

-- First keyset page.
SELECT *
FROM get_products_keyset(
    1,
    5,
    NULL,
    NULL,
    NULL,
    'ASC'
);

-- Next page using the last record's composite key.
SELECT *
FROM get_products_keyset(
    1,
    5,
    TIMESTAMPTZ '2026-01-01 00:02:00+00',
    3,
    NULL,
    'ASC'
);

-- Reverse keyset navigation.
SELECT *
FROM get_products_keyset(
    1,
    5,
    TIMESTAMPTZ '2026-01-01 00:10:00+00',
    20,
    NULL,
    'DESC'
);

-- ============================================================
-- 19. CURSOR REGISTRATION EXAMPLE
-- ============================================================

-- The token is represented by an application-generated,
-- authenticated value. The database stores only its SHA-256 hash.

CALL register_cursor(
    1,
    'sample-cursor-token-2026-000001',
    'CURSOR',
    TIMESTAMPTZ '2026-01-01 00:02:00+00',
    3,
    '',
    'FORWARD'
);

-- ============================================================
-- 20. CURSOR VALIDATION EXAMPLE
-- ============================================================

SELECT *
FROM validate_cursor(
    'sample-cursor-token-2026-000001',
    1,
    'CURSOR',
    ''
);

-- ============================================================
-- 21. CTE-BASED PAGE ELIGIBILITY
-- ============================================================

WITH repository_snapshot AS (
    SELECT
        repository_id,
        dataset_version
    FROM repository_state
    WHERE repository_id = 1
),
eligible_products AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        p.price,
        p.created_at,
        ROW_NUMBER() OVER (
            ORDER BY p.created_at, p.product_id
        ) AS sequence_number
    FROM products p
    JOIN repository_snapshot r
      ON r.repository_id = p.repository_id
    WHERE p.status = 'ACTIVE'
),
page_window AS (
    SELECT *
    FROM eligible_products
    WHERE sequence_number BETWEEN 6 AND 10
)
SELECT
    r.dataset_version,
    p.*
FROM page_window p
CROSS JOIN repository_snapshot r;

-- ============================================================
-- 22. PAGINATION PERFORMANCE COMPARISON
-- ============================================================

-- Offset pagination may require scanning and discarding
-- earlier records.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    product_id,
    product_name,
    created_at
FROM products
WHERE repository_id = 1
  AND status = 'ACTIVE'
ORDER BY created_at, product_id
LIMIT 10 OFFSET 500;

-- Keyset pagination uses a composite boundary.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    product_id,
    product_name,
    created_at
FROM products
WHERE repository_id = 1
  AND status = 'ACTIVE'
  AND (
      created_at,
      product_id
  ) > (
      TIMESTAMPTZ '2026-01-01 00:05:00+00',
      20
  )
ORDER BY created_at, product_id
LIMIT 11;

-- ============================================================
-- 23. VALIDATION AND FAILURE CASES
-- ============================================================

-- Invalid page size.
SELECT validate_page_size(1, 'OFFSET', 1000);

-- Disabled policy check.
UPDATE pagination_policies
SET enabled = FALSE
WHERE repository_id = 1
  AND strategy = 'CURSOR';

SELECT validate_page_size(1, 'CURSOR', 10);

UPDATE pagination_policies
SET enabled = TRUE
WHERE repository_id = 1
  AND strategy = 'CURSOR';

-- Invalid cursor lookup.
SELECT *
FROM validate_cursor(
    'unknown-cursor-token-000000000000',
    1,
    'CURSOR',
    ''
);

-- ============================================================
-- 24. AUDIT AND REPORTING
-- ============================================================

SELECT *
FROM pagination_strategy_report
ORDER BY request_count DESC;

SELECT *
FROM product_category_statistics
ORDER BY active_products DESC;

SELECT
    strategy,
    DATE_TRUNC('hour', occurred_at) AS request_hour,
    COUNT(*) AS total_requests,
    AVG(execution_ms) AS average_latency
FROM pagination_audit
GROUP BY strategy, DATE_TRUNC('hour', occurred_at)
ORDER BY request_hour DESC;

-- ============================================================
-- 25. DATASET VERSION REPORT
-- ============================================================

SELECT
    repository_name,
    dataset_version,
    updated_at
FROM repository_state;

-- ============================================================
-- 26. TRANSACTIONAL CURSOR REVOCATION
-- ============================================================

BEGIN;

UPDATE pagination_cursors
SET revoked_at = NOW()
WHERE repository_id = 1
  AND expires_at > NOW()
  AND revoked_at IS NULL;

COMMIT;

-- ============================================================
-- 27. CURSOR MAINTENANCE
-- ============================================================

CALL cleanup_expired_cursors();

-- ============================================================
-- 28. FINAL DATABASE VALIDATION
-- ============================================================

DO $$
DECLARE
    product_count BIGINT;
    repository_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO product_count
    FROM products
    WHERE repository_id = 1;

    SELECT COUNT(*)
    INTO repository_count
    FROM repository_state;

    IF repository_count <> 1 THEN
        RAISE EXCEPTION
            'Repository initialization failed.';
    END IF;

    IF product_count < 1 THEN
        RAISE EXCEPTION
            'Product initialization failed.';
    END IF;

    RAISE NOTICE
        'Pagination database initialized. Products: %',
        product_count;
END;
$$;

-- ============================================================
-- END OF SCRIPT
-- ============================================================

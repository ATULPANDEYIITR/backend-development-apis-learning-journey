-- ============================================================
-- API RESPONSE DESIGN
-- Envelopes, metadata, consistency, and error schemas
-- PostgreSQL 15+
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS api_design;

SET search_path TO api_design, public;

-- ------------------------------------------------------------
-- 1. Domain types
-- ------------------------------------------------------------

CREATE TYPE response_status AS ENUM (
    'SUCCESS',
    'FAILURE'
);

CREATE TYPE consistency_level AS ENUM (
    'STRONG',
    'EVENTUAL'
);

CREATE TYPE error_severity AS ENUM (
    'CLIENT',
    'SERVER',
    'TRANSIENT'
);

-- ------------------------------------------------------------
-- 2. API versions
-- ------------------------------------------------------------

CREATE TABLE api_versions (
    version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_name VARCHAR(20) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    introduced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (version_name ~ '^v[1-9][0-9]*$')
);

INSERT INTO api_versions (version_name)
VALUES ('v1'), ('v2');

-- ------------------------------------------------------------
-- 3. API clients and request identity
-- ------------------------------------------------------------

CREATE TABLE api_clients (
    client_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_name VARCHAR(120) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO api_clients (client_name)
VALUES
    ('Inventory Portal'),
    ('Mobile Procurement'),
    ('Analytics Service');

CREATE TABLE api_requests (
    request_id UUID PRIMARY KEY,
    client_id BIGINT REFERENCES api_clients(client_id),
    version_id BIGINT NOT NULL REFERENCES api_versions(version_id),
    http_method VARCHAR(10) NOT NULL,
    endpoint TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms NUMERIC(12,3),
    correlation_id UUID,
    consistency consistency_level NOT NULL DEFAULT 'STRONG',
    CHECK (
        http_method IN (
            'GET', 'POST', 'PUT', 'PATCH', 'DELETE'
        )
    ),
    CHECK (endpoint LIKE '/api/%'),
    CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CHECK (
        completed_at IS NULL OR completed_at >= requested_at
    )
);

CREATE INDEX idx_api_requests_requested_at
ON api_requests(requested_at DESC);

CREATE INDEX idx_api_requests_correlation
ON api_requests(correlation_id)
WHERE correlation_id IS NOT NULL;

CREATE INDEX idx_api_requests_endpoint_time
ON api_requests(endpoint, requested_at DESC);

-- ------------------------------------------------------------
-- 4. Standardized error catalogue
-- ------------------------------------------------------------

CREATE TABLE error_catalog (
    error_code VARCHAR(60) PRIMARY KEY,
    http_status SMALLINT NOT NULL,
    severity error_severity NOT NULL,
    default_message TEXT NOT NULL,
    retryable BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (http_status BETWEEN 400 AND 599),
    CHECK (error_code ~ '^[A-Z][A-Z0-9_]+$')
);

INSERT INTO error_catalog (
    error_code,
    http_status,
    severity,
    default_message,
    retryable
)
VALUES
(
    'VALIDATION_ERROR',
    400,
    'CLIENT',
    'Request validation failed.',
    FALSE
),
(
    'UNAUTHORIZED',
    401,
    'CLIENT',
    'Authentication is required.',
    FALSE
),
(
    'FORBIDDEN',
    403,
    'CLIENT',
    'Access is denied.',
    FALSE
),
(
    'RESOURCE_NOT_FOUND',
    404,
    'CLIENT',
    'Requested resource does not exist.',
    FALSE
),
(
    'CONFLICT',
    409,
    'CLIENT',
    'Resource state conflict.',
    FALSE
),
(
    'RATE_LIMITED',
    429,
    'TRANSIENT',
    'Request rate limit exceeded.',
    TRUE
),
(
    'INTERNAL_ERROR',
    500,
    'SERVER',
    'An unexpected server error occurred.',
    FALSE
),
(
    'SERVICE_UNAVAILABLE',
    503,
    'TRANSIENT',
    'Service is temporarily unavailable.',
    TRUE
);

-- ------------------------------------------------------------
-- 5. Response envelope records
-- ------------------------------------------------------------

CREATE TABLE api_responses (
    response_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE
        REFERENCES api_requests(request_id),
    status response_status NOT NULL,
    http_status SMALLINT NOT NULL,
    data JSONB,
    error_code VARCHAR(60)
        REFERENCES error_catalog(error_code),
    response_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (http_status BETWEEN 100 AND 599),

    CHECK (
        (
            status = 'SUCCESS'
            AND http_status BETWEEN 200 AND 299
            AND error_code IS NULL
        )
        OR
        (
            status = 'FAILURE'
            AND http_status BETWEEN 400 AND 599
            AND error_code IS NOT NULL
            AND data IS NULL
        )
    ),

    CHECK (jsonb_typeof(response_metadata) = 'object')
);

CREATE INDEX idx_api_responses_status
ON api_responses(status, created_at DESC);

CREATE INDEX idx_api_responses_error
ON api_responses(error_code)
WHERE error_code IS NOT NULL;

CREATE INDEX idx_api_responses_metadata
ON api_responses USING GIN(response_metadata);

-- ------------------------------------------------------------
-- 6. Field-level error details
-- ------------------------------------------------------------

CREATE TABLE response_error_details (
    detail_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id BIGINT NOT NULL
        REFERENCES api_responses(response_id)
        ON DELETE CASCADE,
    field_name VARCHAR(120) NOT NULL,
    reason TEXT NOT NULL,
    rejected_value JSONB,
    CHECK (length(trim(field_name)) > 0),
    CHECK (length(trim(reason)) > 0)
);

CREATE INDEX idx_error_details_response
ON response_error_details(response_id);

-- ------------------------------------------------------------
-- 7. Pagination metadata
-- ------------------------------------------------------------

CREATE TABLE response_pagination (
    response_id BIGINT PRIMARY KEY
        REFERENCES api_responses(response_id)
        ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    page_size INTEGER NOT NULL,
    total_items BIGINT NOT NULL,
    total_pages INTEGER NOT NULL,
    has_next BOOLEAN NOT NULL,
    has_previous BOOLEAN NOT NULL,

    CHECK (page_number >= 1),
    CHECK (page_size BETWEEN 1 AND 100),
    CHECK (total_items >= 0),
    CHECK (total_pages >= 0)
);

-- ------------------------------------------------------------
-- 8. Response links
-- ------------------------------------------------------------

CREATE TABLE response_links (
    link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id BIGINT NOT NULL
        REFERENCES api_responses(response_id)
        ON DELETE CASCADE,
    relation VARCHAR(30) NOT NULL,
    target_url TEXT NOT NULL,
    UNIQUE (response_id, relation),
    CHECK (
        relation IN (
            'self', 'first', 'previous',
            'next', 'last', 'related'
        )
    ),
    CHECK (
        target_url ~ '^/'
        AND target_url !~ '^//'
    )
);

-- ------------------------------------------------------------
-- 9. Product resources and version tracking
-- ------------------------------------------------------------

CREATE TABLE products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(160) NOT NULL,
    price NUMERIC(14,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    version BIGINT NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (price > 0),
    CHECK (currency ~ '^[A-Z]{3}$'),
    CHECK (version >= 1),
    CHECK (length(trim(product_name)) > 0)
);

INSERT INTO products (
    product_id,
    product_name,
    price,
    currency
)
OVERRIDING SYSTEM VALUE
VALUES
    (101, 'Enterprise Laptop', 85000.00, 'INR'),
    (102, 'Network Firewall', 125000.00, 'INR'),
    (103, 'Secure Storage', 45000.00, 'INR');

SELECT setval(
    pg_get_serial_sequence(
        'api_design.products',
        'product_id'
    ),
    103,
    TRUE
);

-- ------------------------------------------------------------
-- 10. Product update audit and optimistic concurrency
-- ------------------------------------------------------------

CREATE TABLE product_update_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(product_id),
    old_price NUMERIC(14,2) NOT NULL,
    new_price NUMERIC(14,2) NOT NULL,
    old_version BIGINT NOT NULL,
    new_version BIGINT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (old_price > 0 AND new_price > 0),
    CHECK (new_version = old_version + 1)
);

CREATE OR REPLACE FUNCTION audit_product_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.price IS DISTINCT FROM OLD.price THEN
        NEW.version := OLD.version + 1;
        NEW.updated_at := NOW();

        INSERT INTO product_update_audit (
            product_id,
            old_price,
            new_price,
            old_version,
            new_version
        )
        VALUES (
            OLD.product_id,
            OLD.price,
            NEW.price,
            OLD.version,
            NEW.version
        );
    ELSE
        NEW.version := OLD.version;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_product_update_audit
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION audit_product_update();

-- ------------------------------------------------------------
-- 11. Request completion procedure
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE complete_api_request(
    p_request_id UUID,
    p_status response_status,
    p_http_status SMALLINT,
    p_data JSONB,
    p_error_code VARCHAR(60),
    p_metadata JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_existing BIGINT;
BEGIN
    IF p_metadata IS NULL
       OR jsonb_typeof(p_metadata) <> 'object' THEN
        RAISE EXCEPTION 'Metadata must be a JSON object';
    END IF;

    IF p_status = 'SUCCESS' THEN
        IF p_http_status NOT BETWEEN 200 AND 299
           OR p_error_code IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid success response combination';
        END IF;
    ELSE
        IF p_http_status NOT BETWEEN 400 AND 599
           OR p_error_code IS NULL
           OR p_data IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid failure response combination';
        END IF;
    END IF;

    SELECT response_id
    INTO v_existing
    FROM api_responses
    WHERE request_id = p_request_id
    FOR UPDATE;

    IF FOUND THEN
        RAISE EXCEPTION 'Request already has a response';
    END IF;

    INSERT INTO api_responses (
        request_id,
        status,
        http_status,
        data,
        error_code,
        response_metadata
    )
    VALUES (
        p_request_id,
        p_status,
        p_http_status,
        p_data,
        p_error_code,
        p_metadata
    );

    UPDATE api_requests
    SET
        completed_at = NOW(),
        duration_ms = GREATEST(
            0,
            EXTRACT(
                EPOCH FROM (NOW() - requested_at)
            ) * 1000
        )
    WHERE request_id = p_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Request does not exist';
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- 12. Atomic optimistic-concurrency update function
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_product_price(
    p_product_id BIGINT,
    p_new_price NUMERIC(14,2),
    p_expected_version BIGINT
)
RETURNS products
LANGUAGE plpgsql
AS $$
DECLARE
    v_product products%ROWTYPE;
BEGIN
    IF p_new_price IS NULL OR p_new_price <= 0 THEN
        RAISE EXCEPTION 'Price must be positive'
            USING ERRCODE = '22023';
    END IF;

    UPDATE products
    SET price = p_new_price
    WHERE product_id = p_product_id
      AND version = p_expected_version
    RETURNING * INTO v_product;

    IF NOT FOUND THEN
        IF NOT EXISTS (
            SELECT 1
            FROM products
            WHERE product_id = p_product_id
        ) THEN
            RAISE EXCEPTION 'Product not found'
                USING ERRCODE = 'P0002';
        END IF;

        RAISE EXCEPTION 'Version conflict'
            USING ERRCODE = '40001';
    END IF;

    RETURN v_product;
END;
$$;

-- ------------------------------------------------------------
-- 13. Reusable response-envelope view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW response_envelope_view AS
SELECT
    r.response_id,
    r.request_id,
    r.status,
    r.http_status,
    r.data,
    CASE
        WHEN r.error_code IS NULL THEN NULL
        ELSE jsonb_build_object(
            'code', e.error_code,
            'message', e.default_message,
            'severity', e.severity,
            'retryable', e.retryable
        )
    END AS error,
    jsonb_build_object(
        'request_id', q.request_id,
        'timestamp', r.created_at,
        'api_version', v.version_name,
        'duration_ms', q.duration_ms,
        'correlation_id', q.correlation_id,
        'consistency', q.consistency,
        'custom', r.response_metadata
    ) AS metadata
FROM api_responses r
JOIN api_requests q
    ON q.request_id = r.request_id
JOIN api_versions v
    ON v.version_id = q.version_id
LEFT JOIN error_catalog e
    ON e.error_code = r.error_code;

-- ------------------------------------------------------------
-- 14. Operational reporting view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW api_response_metrics AS
SELECT
    q.endpoint,
    r.status,
    r.http_status,
    COUNT(*) AS response_count,
    ROUND(AVG(q.duration_ms), 3) AS average_duration_ms,
    ROUND(
        PERCENTILE_CONT(0.95)
        WITHIN GROUP (ORDER BY q.duration_ms)::NUMERIC,
        3
    ) AS p95_duration_ms
FROM api_requests q
JOIN api_responses r
    ON r.request_id = q.request_id
GROUP BY
    q.endpoint,
    r.status,
    r.http_status;

-- ------------------------------------------------------------
-- 15. Sample request and response records
-- ------------------------------------------------------------

DO $$
DECLARE
    v_version_id BIGINT;
    v_client_id BIGINT;
    v_request_id UUID;
    v_response_id BIGINT;
BEGIN
    SELECT version_id INTO v_version_id
    FROM api_versions
    WHERE version_name = 'v1';

    SELECT client_id INTO v_client_id
    FROM api_clients
    WHERE client_name = 'Inventory Portal';

    -- Successful product retrieval.
    v_request_id := '11111111-1111-4111-8111-111111111111';

    INSERT INTO api_requests (
        request_id,
        client_id,
        version_id,
        http_method,
        endpoint,
        correlation_id,
        consistency
    )
    VALUES (
        v_request_id,
        v_client_id,
        v_version_id,
        'GET',
        '/api/v1/products/101',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'STRONG'
    );

    CALL complete_api_request(
        v_request_id,
        'SUCCESS',
        200,
        '{
            "id": 101,
            "name": "Enterprise Laptop",
            "price": 85000.00,
            "currency": "INR",
            "version": 1
        }'::JSONB,
        NULL,
        '{
            "cache": "MISS",
            "source": "primary"
        }'::JSONB
    );

    SELECT response_id INTO v_response_id
    FROM api_responses
    WHERE request_id = v_request_id;

    INSERT INTO response_links (
        response_id,
        relation,
        target_url
    )
    VALUES (
        v_response_id,
        'self',
        '/api/v1/products/101'
    );

    -- Failed validation request.
    v_request_id := '22222222-2222-4222-8222-222222222222';

    INSERT INTO api_requests (
        request_id,
        client_id,
        version_id,
        http_method,
        endpoint
    )
    VALUES (
        v_request_id,
        v_client_id,
        v_version_id,
        'POST',
        '/api/v1/products'
    );

    CALL complete_api_request(
        v_request_id,
        'FAILURE',
        400,
        NULL,
        'VALIDATION_ERROR',
        '{"source": "request-validation"}'::JSONB
    );

    SELECT response_id INTO v_response_id
    FROM api_responses
    WHERE request_id = v_request_id;

    INSERT INTO response_error_details (
        response_id,
        field_name,
        reason,
        rejected_value
    )
    VALUES (
        v_response_id,
        'price',
        'Price must be greater than zero',
        '-500'::JSONB
    );

    -- Failed resource lookup.
    v_request_id := '33333333-3333-4333-8333-333333333333';

    INSERT INTO api_requests (
        request_id,
        client_id,
        version_id,
        http_method,
        endpoint
    )
    VALUES (
        v_request_id,
        v_client_id,
        v_version_id,
        'GET',
        '/api/v1/products/999'
    );

    CALL complete_api_request(
        v_request_id,
        'FAILURE',
        404,
        NULL,
        'RESOURCE_NOT_FOUND',
        '{"resource_type": "product"}'::JSONB
    );

    -- Transient service failure.
    v_request_id := '44444444-4444-4444-8444-444444444444';

    INSERT INTO api_requests (
        request_id,
        client_id,
        version_id,
        http_method,
        endpoint,
        consistency
    )
    VALUES (
        v_request_id,
        v_client_id,
        v_version_id,
        'GET',
        '/api/v1/reports',
        'EVENTUAL'
    );

    CALL complete_api_request(
        v_request_id,
        'FAILURE',
        503,
        NULL,
        'SERVICE_UNAVAILABLE',
        '{"retry_after_seconds": 30}'::JSONB
    );

    -- Paginated collection response.
    v_request_id := '55555555-5555-4555-8555-555555555555';

    INSERT INTO api_requests (
        request_id,
        client_id,
        version_id,
        http_method,
        endpoint
    )
    VALUES (
        v_request_id,
        v_client_id,
        v_version_id,
        'GET',
        '/api/v1/products'
    );

    CALL complete_api_request(
        v_request_id,
        'SUCCESS',
        200,
        '[
            {"id": 101, "name": "Enterprise Laptop"},
            {"id": 102, "name": "Network Firewall"}
        ]'::JSONB,
        NULL,
        '{"result_source": "primary"}'::JSONB
    );

    SELECT response_id INTO v_response_id
    FROM api_responses
    WHERE request_id = v_request_id;

    INSERT INTO response_pagination (
        response_id,
        page_number,
        page_size,
        total_items,
        total_pages,
        has_next,
        has_previous
    )
    VALUES (
        v_response_id,
        1,
        2,
        3,
        2,
        TRUE,
        FALSE
    );

    INSERT INTO response_links (
        response_id,
        relation,
        target_url
    )
    VALUES
    (
        v_response_id,
        'self',
        '/api/v1/products?page=1'
    ),
    (
        v_response_id,
        'next',
        '/api/v1/products?page=2'
    ),
    (
        v_response_id,
        'last',
        '/api/v1/products?page=2'
    );
END;
$$;

-- ------------------------------------------------------------
-- 16. Retrieval queries
-- ------------------------------------------------------------

SELECT *
FROM response_envelope_view
ORDER BY response_id;

SELECT
    r.request_id,
    r.status,
    d.field_name,
    d.reason,
    d.rejected_value
FROM api_responses r
JOIN response_error_details d
    ON d.response_id = r.response_id;

SELECT
    r.request_id,
    p.page_number,
    p.page_size,
    p.total_items,
    p.total_pages,
    p.has_next,
    p.has_previous
FROM api_responses r
JOIN response_pagination p
    ON p.response_id = r.response_id;

-- ------------------------------------------------------------
-- 17. Validation queries
-- ------------------------------------------------------------

-- Detect requests without completed responses.
SELECT
    q.request_id,
    q.endpoint,
    q.requested_at
FROM api_requests q
LEFT JOIN api_responses r
    ON r.request_id = q.request_id
WHERE r.response_id IS NULL;

-- Detect responses with an invalid envelope relationship.
SELECT
    response_id,
    status,
    http_status,
    error_code,
    data
FROM api_responses
WHERE
    (
        status = 'SUCCESS'
        AND (
            http_status NOT BETWEEN 200 AND 299
            OR error_code IS NOT NULL
        )
    )
    OR
    (
        status = 'FAILURE'
        AND (
            http_status NOT BETWEEN 400 AND 599
            OR error_code IS NULL
            OR data IS NOT NULL
        )
    );

-- Verify pagination calculations.
SELECT
    response_id,
    page_number,
    total_pages,
    CEIL(total_items::NUMERIC / page_size) AS expected_pages
FROM response_pagination
WHERE total_pages <>
    CEIL(total_items::NUMERIC / page_size)::INTEGER;

-- ------------------------------------------------------------
-- 18. Aggregation and reporting
-- ------------------------------------------------------------

SELECT
    status,
    COUNT(*) AS total_responses,
    ROUND(
        100.0 * COUNT(*) /
        SUM(COUNT(*)) OVER (),
        2
    ) AS percentage
FROM api_responses
GROUP BY status;

SELECT
    error_code,
    COUNT(*) AS error_count
FROM api_responses
WHERE error_code IS NOT NULL
GROUP BY error_code
ORDER BY error_count DESC;

SELECT *
FROM api_response_metrics
ORDER BY response_count DESC;

-- ------------------------------------------------------------
-- 19. CTE-based error analysis
-- ------------------------------------------------------------

WITH error_summary AS (
    SELECT
        e.error_code,
        e.http_status,
        e.severity,
        e.retryable,
        COUNT(r.response_id) AS occurrences
    FROM error_catalog e
    LEFT JOIN api_responses r
        ON r.error_code = e.error_code
    GROUP BY
        e.error_code,
        e.http_status,
        e.severity,
        e.retryable
),
ranked_errors AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            ORDER BY occurrences DESC
        ) AS error_rank
    FROM error_summary
)
SELECT *
FROM ranked_errors
ORDER BY error_rank, error_code;

-- ------------------------------------------------------------
-- 20. Consistency analysis
-- ------------------------------------------------------------

SELECT
    q.consistency,
    r.status,
    COUNT(*) AS request_count,
    ROUND(AVG(q.duration_ms), 3) AS average_latency_ms
FROM api_requests q
JOIN api_responses r
    ON r.request_id = q.request_id
GROUP BY
    q.consistency,
    r.status
ORDER BY
    q.consistency,
    r.status;

-- ------------------------------------------------------------
-- 21. Transactional product update
-- ------------------------------------------------------------

BEGIN;

SELECT *
FROM update_product_price(
    101,
    89000.00,
    1
);

COMMIT;

-- The following stale-version operation intentionally fails.
-- Run separately if testing conflict behavior.
--
-- SELECT * FROM update_product_price(101, 92000.00, 1);
--
-- The expected result is SQLSTATE 40001.

-- ------------------------------------------------------------
-- 22. Audit retrieval
-- ------------------------------------------------------------

SELECT
    audit_id,
    product_id,
    old_price,
    new_price,
    old_version,
    new_version,
    changed_at
FROM product_update_audit
ORDER BY changed_at DESC;

-- ------------------------------------------------------------
-- 23. Error retry policy report
-- ------------------------------------------------------------

SELECT
    error_code,
    http_status,
    severity,
    retryable,
    default_message
FROM error_catalog
WHERE retryable = TRUE
ORDER BY http_status;

COMMIT;

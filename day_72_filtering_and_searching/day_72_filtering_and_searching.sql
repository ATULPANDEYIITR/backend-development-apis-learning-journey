-- ============================================================
-- CATALOG FILTERING AND SEARCH MANAGEMENT
-- PostgreSQL 14+
--
-- Features:
-- Dynamic filters, parameterized searching, sorting,
-- pagination, validation, aggregation, reporting and indexing.
-- ============================================================

BEGIN;

DROP SCHEMA IF EXISTS catalog_search CASCADE;

CREATE SCHEMA catalog_search;

SET search_path TO catalog_search, public;

-- ============================================================
-- 1. DOMAIN TABLES
-- ============================================================

CREATE TABLE categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name VARCHAR(80) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category_id BIGINT NOT NULL
        REFERENCES categories(category_id),
    description TEXT NOT NULL DEFAULT '',
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    rating NUMERIC(3, 2) NOT NULL
        CHECK (rating BETWEEN 0 AND 5),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE search_requests (
    search_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    keyword VARCHAR(100),
    category_id BIGINT REFERENCES categories(category_id),
    min_price NUMERIC(12, 2),
    max_price NUMERIC(12, 2),
    min_rating NUMERIC(3, 2),
    sort_field VARCHAR(30) NOT NULL DEFAULT 'product_name',
    sort_direction VARCHAR(4) NOT NULL DEFAULT 'ASC',
    page_limit INTEGER NOT NULL DEFAULT 10
        CHECK (page_limit BETWEEN 1 AND 100),
    page_offset INTEGER NOT NULL DEFAULT 0
        CHECK (page_offset >= 0),
    requested_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        min_price IS NULL OR min_price >= 0
    ),

    CHECK (
        max_price IS NULL OR max_price >= 0
    ),

    CHECK (
        min_rating IS NULL OR min_rating BETWEEN 0 AND 5
    ),

    CHECK (
        min_price IS NULL OR max_price IS NULL
        OR min_price <= max_price
    ),

    CHECK (
        sort_field IN (
            'product_id',
            'product_name',
            'price',
            'rating',
            'created_at'
        )
    ),

    CHECK (sort_direction IN ('ASC', 'DESC'))
);

CREATE TABLE search_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    search_id BIGINT NOT NULL
        REFERENCES search_requests(search_id),
    matched_count BIGINT NOT NULL CHECK (matched_count >= 0),
    returned_count INTEGER NOT NULL CHECK (returned_count >= 0),
    execution_status VARCHAR(20) NOT NULL
        CHECK (execution_status IN ('SUCCESS', 'EMPTY', 'FAILED')),
    execution_time_ms NUMERIC(12, 3),
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX idx_products_category
    ON products(category_id);

CREATE INDEX idx_products_active_category
    ON products(active, category_id);

CREATE INDEX idx_products_price
    ON products(price);

CREATE INDEX idx_products_rating
    ON products(rating);

CREATE INDEX idx_products_created
    ON products(created_at DESC);

CREATE INDEX idx_products_tags
    ON products USING GIN(tags);

-- Trigram indexes support substring searches.
-- pg_trgm must be installed by a database administrator.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_products_name_trgm
    ON products USING GIN(product_name gin_trgm_ops);

CREATE INDEX idx_products_description_trgm
    ON products USING GIN(description gin_trgm_ops);

CREATE INDEX idx_search_requests_created
    ON search_requests(created_at DESC);

CREATE INDEX idx_search_audit_search
    ON search_audit(search_id, executed_at DESC);

-- ============================================================
-- 3. UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION update_product_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_product_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION update_product_timestamp();

-- ============================================================
-- 4. SAMPLE DATA
-- ============================================================

INSERT INTO categories(category_name)
VALUES
    ('Electronics'),
    ('Furniture'),
    ('Stationery');

INSERT INTO products (
    product_name,
    category_id,
    description,
    price,
    rating,
    active,
    tags
)
SELECT
    data.product_name,
    categories.category_id,
    data.description,
    data.price,
    data.rating,
    data.active,
    data.tags
FROM (
    VALUES
        ('Laptop Pro', 'Electronics',
         'Professional computing laptop',
         95000, 4.8, TRUE,
         ARRAY['computer', 'work', 'premium']::TEXT[]),

        ('Wireless Mouse', 'Electronics',
         'Wireless computer mouse',
         1200, 4.2, TRUE,
         ARRAY['computer', 'wireless']::TEXT[]),

        ('Mechanical Keyboard', 'Electronics',
         'Mechanical typing keyboard',
         4500, 4.6, TRUE,
         ARRAY['computer', 'typing']::TEXT[]),

        ('Office Chair', 'Furniture',
         'Ergonomic office chair',
         12500, 4.3, TRUE,
         ARRAY['office', 'ergonomic']::TEXT[]),

        ('Standing Desk', 'Furniture',
         'Adjustable standing desk',
         22000, 4.7, TRUE,
         ARRAY['office', 'desk']::TEXT[]),

        ('Old Monitor', 'Electronics',
         'Discontinued computer monitor',
         8000, 3.5, FALSE,
         ARRAY['computer', 'display']::TEXT[]),

        ('Notebook', 'Stationery',
         'Paper notebook',
         100, 4.0, TRUE,
         ARRAY['paper', 'writing']::TEXT[]),

        ('Premium Headphones', 'Electronics',
         'Noise isolation headphones',
         6500, 4.9, TRUE,
         ARRAY['audio', 'wireless']::TEXT[]),

        ('Desk Lamp', 'Furniture',
         'Adjustable office desk lamp',
         1800, 3.9, TRUE,
         ARRAY['office', 'lighting']::TEXT[]),

        ('USB Hub', 'Electronics',
         'Multi-port USB connection hub',
         1500, 4.1, TRUE,
         ARRAY['computer', 'accessory']::TEXT[])
) AS data(
    product_name,
    category_name,
    description,
    price,
    rating,
    active,
    tags
)
JOIN categories
    ON categories.category_name = data.category_name;

-- ============================================================
-- 5. SEARCH FUNCTION
--
-- Values use EXECUTE ... USING.
-- Column names and sort direction come exclusively from
-- allowlisted values.
-- ============================================================

CREATE OR REPLACE FUNCTION search_products(
    p_keyword VARCHAR DEFAULT NULL,
    p_category_id BIGINT DEFAULT NULL,
    p_min_price NUMERIC DEFAULT NULL,
    p_max_price NUMERIC DEFAULT NULL,
    p_min_rating NUMERIC DEFAULT NULL,
    p_sort_field VARCHAR DEFAULT 'product_name',
    p_sort_direction VARCHAR DEFAULT 'ASC',
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    product_id BIGINT,
    product_name VARCHAR,
    category_name VARCHAR,
    price NUMERIC,
    rating NUMERIC,
    active BOOLEAN,
    created_at TIMESTAMPTZ,
    total_count BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_sql TEXT;
    v_conditions TEXT[] := ARRAY['p.active = TRUE'];
    v_where TEXT;
    v_sort_column TEXT;
    v_sort_direction TEXT;
BEGIN
    IF p_keyword IS NOT NULL AND length(p_keyword) > 100 THEN
        RAISE EXCEPTION 'Keyword exceeds 100 characters.';
    END IF;

    IF p_min_price IS NOT NULL AND p_min_price < 0 THEN
        RAISE EXCEPTION 'Minimum price cannot be negative.';
    END IF;

    IF p_max_price IS NOT NULL AND p_max_price < 0 THEN
        RAISE EXCEPTION 'Maximum price cannot be negative.';
    END IF;

    IF p_min_price IS NOT NULL
       AND p_max_price IS NOT NULL
       AND p_min_price > p_max_price THEN
        RAISE EXCEPTION 'Minimum price exceeds maximum price.';
    END IF;

    IF p_min_rating IS NOT NULL
       AND p_min_rating NOT BETWEEN 0 AND 5 THEN
        RAISE EXCEPTION 'Rating must be between 0 and 5.';
    END IF;

    IF p_limit NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'Limit must be between 1 and 100.';
    END IF;

    IF p_offset < 0 THEN
        RAISE EXCEPTION 'Offset cannot be negative.';
    END IF;

    CASE p_sort_field
        WHEN 'product_id' THEN
            v_sort_column := 'p.product_id';
        WHEN 'product_name' THEN
            v_sort_column := 'p.product_name';
        WHEN 'price' THEN
            v_sort_column := 'p.price';
        WHEN 'rating' THEN
            v_sort_column := 'p.rating';
        WHEN 'created_at' THEN
            v_sort_column := 'p.created_at';
        ELSE
            RAISE EXCEPTION 'Unsupported sorting field.';
    END CASE;

    CASE UPPER(p_sort_direction)
        WHEN 'ASC' THEN
            v_sort_direction := 'ASC';
        WHEN 'DESC' THEN
            v_sort_direction := 'DESC';
        ELSE
            RAISE EXCEPTION 'Unsupported sorting direction.';
    END CASE;

    IF p_keyword IS NOT NULL AND btrim(p_keyword) <> '' THEN
        v_conditions := array_append(
            v_conditions,
            '(p.product_name ILIKE $1 OR p.description ILIKE $1)'
        );
    END IF;

    IF p_category_id IS NOT NULL THEN
        v_conditions := array_append(
            v_conditions,
            'p.category_id = $2'
        );
    END IF;

    IF p_min_price IS NOT NULL THEN
        v_conditions := array_append(
            v_conditions,
            'p.price >= $3'
        );
    END IF;

    IF p_max_price IS NOT NULL THEN
        v_conditions := array_append(
            v_conditions,
            'p.price <= $4'
        );
    END IF;

    IF p_min_rating IS NOT NULL THEN
        v_conditions := array_append(
            v_conditions,
            'p.rating >= $5'
        );
    END IF;

    v_where := array_to_string(v_conditions, ' AND ');

    v_sql := format(
        $query$
        SELECT
            p.product_id,
            p.product_name,
            c.category_name,
            p.price,
            p.rating,
            p.active,
            p.created_at,
            COUNT(*) OVER() AS total_count
        FROM products p
        JOIN categories c
            ON c.category_id = p.category_id
        WHERE %s
        ORDER BY %s %s, p.product_id ASC
        LIMIT $6 OFFSET $7
        $query$,
        v_where,
        v_sort_column,
        v_sort_direction
    );

    RETURN QUERY EXECUTE v_sql
    USING
        CASE
            WHEN p_keyword IS NULL OR btrim(p_keyword) = ''
            THEN NULL
            ELSE '%' || btrim(p_keyword) || '%'
        END,
        p_category_id,
        p_min_price,
        p_max_price,
        p_min_rating,
        p_limit,
        p_offset;
END;
$$;

-- ============================================================
-- 6. SEARCH REQUEST REGISTRATION
-- ============================================================

CREATE OR REPLACE FUNCTION register_search_request(
    p_keyword VARCHAR,
    p_category_id BIGINT,
    p_min_price NUMERIC,
    p_max_price NUMERIC,
    p_min_rating NUMERIC,
    p_sort_field VARCHAR,
    p_sort_direction VARCHAR,
    p_limit INTEGER,
    p_offset INTEGER,
    p_requested_by VARCHAR
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_search_id BIGINT;
BEGIN
    INSERT INTO search_requests (
        keyword,
        category_id,
        min_price,
        max_price,
        min_rating,
        sort_field,
        sort_direction,
        page_limit,
        page_offset,
        requested_by
    )
    VALUES (
        p_keyword,
        p_category_id,
        p_min_price,
        p_max_price,
        p_min_rating,
        p_sort_field,
        UPPER(p_sort_direction),
        p_limit,
        p_offset,
        p_requested_by
    )
    RETURNING search_id INTO v_search_id;

    RETURN v_search_id;
END;
$$;

-- ============================================================
-- 7. SEARCH EXECUTION PROCEDURE
--
-- Records search parameters and execution metrics.
-- The request and audit entry are committed together.
-- ============================================================

CREATE OR REPLACE PROCEDURE execute_catalog_search(
    p_keyword VARCHAR,
    p_category_id BIGINT,
    p_min_price NUMERIC,
    p_max_price NUMERIC,
    p_min_rating NUMERIC,
    p_sort_field VARCHAR,
    p_sort_direction VARCHAR,
    p_limit INTEGER,
    p_offset INTEGER,
    p_requested_by VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_search_id BIGINT;
    v_started TIMESTAMPTZ;
    v_matched BIGINT;
    v_returned INTEGER;
    v_status VARCHAR(20);
BEGIN
    v_started := clock_timestamp();

    v_search_id := register_search_request(
        p_keyword,
        p_category_id,
        p_min_price,
        p_max_price,
        p_min_rating,
        p_sort_field,
        p_sort_direction,
        p_limit,
        p_offset,
        p_requested_by
    );

    SELECT COUNT(*)
    INTO v_matched
    FROM search_products(
        p_keyword,
        p_category_id,
        p_min_price,
        p_max_price,
        p_min_rating,
        p_sort_field,
        p_sort_direction,
        100,
        0
    );

    SELECT COUNT(*)
    INTO v_returned
    FROM search_products(
        p_keyword,
        p_category_id,
        p_min_price,
        p_max_price,
        p_min_rating,
        p_sort_field,
        p_sort_direction,
        p_limit,
        p_offset
    );

    v_status := CASE
        WHEN v_returned = 0 THEN 'EMPTY'
        ELSE 'SUCCESS'
    END;

    INSERT INTO search_audit (
        search_id,
        matched_count,
        returned_count,
        execution_status,
        execution_time_ms
    )
    VALUES (
        v_search_id,
        v_matched,
        v_returned,
        v_status,
        EXTRACT(
            EPOCH FROM clock_timestamp() - v_started
        ) * 1000
    );

    RAISE NOTICE
        'Search ID: %, matched: %, returned: %, status: %',
        v_search_id,
        v_matched,
        v_returned,
        v_status;
END;
$$;

-- ============================================================
-- 8. REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW product_search_report AS
SELECT
    c.category_name,
    COUNT(p.product_id) AS total_products,
    COUNT(p.product_id) FILTER (
        WHERE p.active
    ) AS active_products,
    ROUND(AVG(p.price), 2) AS average_price,
    ROUND(AVG(p.rating), 2) AS average_rating,
    MIN(p.price) AS minimum_price,
    MAX(p.price) AS maximum_price
FROM categories c
LEFT JOIN products p
    ON p.category_id = c.category_id
GROUP BY c.category_id, c.category_name;

-- ============================================================
-- 9. SAMPLE SEARCH REQUESTS
-- ============================================================

INSERT INTO search_requests (
    keyword,
    category_id,
    min_price,
    max_price,
    min_rating,
    sort_field,
    sort_direction,
    page_limit,
    page_offset,
    requested_by
)
SELECT
    'computer',
    category_id,
    1000,
    10000,
    4.0,
    'price',
    'ASC',
    5,
    0,
    'analyst'
FROM categories
WHERE category_name = 'Electronics';

INSERT INTO search_requests (
    keyword,
    sort_field,
    sort_direction,
    page_limit,
    page_offset,
    requested_by
)
VALUES
    ('desk', 'rating', 'DESC', 5, 0, 'manager'),
    ('keyboard', 'product_name', 'ASC', 10, 0, 'developer'),
    ('missing-item', 'price', 'ASC', 10, 0, 'analyst');

-- ============================================================
-- 10. SEARCH RETRIEVAL
-- ============================================================

SELECT *
FROM search_products(
    p_keyword => 'keyboard',
    p_sort_field => 'price',
    p_sort_direction => 'ASC',
    p_limit => 10,
    p_offset => 0
);

SELECT *
FROM search_products(
    p_keyword => NULL,
    p_category_id => (
        SELECT category_id
        FROM categories
        WHERE category_name = 'Electronics'
    ),
    p_min_price => 1000,
    p_max_price => 10000,
    p_min_rating => 4.0,
    p_sort_field => 'rating',
    p_sort_direction => 'DESC',
    p_limit => 5,
    p_offset => 0
);

-- ============================================================
-- 11. VALIDATION AND FILTER EVALUATION
-- ============================================================

SELECT
    product_name,
    price,
    rating,
    price BETWEEN 1000 AND 7000 AS price_valid,
    rating >= 4.0 AS rating_valid
FROM products
WHERE active = TRUE
  AND price BETWEEN 1000 AND 7000
  AND rating >= 4.0;

-- ============================================================
-- 12. AGGREGATION AND REPORTING
-- ============================================================

SELECT *
FROM product_search_report
ORDER BY total_products DESC;

-- Search activity report.
SELECT
    r.requested_by,
    COUNT(*) AS total_searches,
    SUM(a.matched_count) AS total_matches,
    SUM(a.returned_count) AS total_returned,
    ROUND(AVG(a.execution_time_ms), 3) AS avg_execution_ms
FROM search_requests r
JOIN search_audit a
    ON a.search_id = r.search_id
GROUP BY r.requested_by
ORDER BY total_searches DESC;

-- ============================================================
-- 13. COMMON TABLE EXPRESSION
-- ============================================================

WITH eligible_products AS (
    SELECT
        p.product_id,
        p.product_name,
        c.category_name,
        p.price,
        p.rating
    FROM products p
    JOIN categories c
        ON c.category_id = p.category_id
    WHERE p.active = TRUE
      AND p.rating >= 4.0
),
ranked_products AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY category_name
            ORDER BY rating DESC, product_id ASC
        ) AS category_rank
    FROM eligible_products
)
SELECT *
FROM ranked_products
WHERE category_rank <= 3
ORDER BY category_name, category_rank;

-- ============================================================
-- 14. SEARCH HISTORY
-- ============================================================

SELECT
    r.search_id,
    r.keyword,
    r.requested_by,
    r.sort_field,
    r.sort_direction,
    a.matched_count,
    a.returned_count,
    a.execution_status,
    a.execution_time_ms
FROM search_requests r
LEFT JOIN search_audit a
    ON a.search_id = r.search_id
ORDER BY r.created_at DESC;

-- ============================================================
-- 15. PROCEDURE EXECUTION
-- ============================================================

CALL execute_catalog_search(
    'desk',
    NULL,
    NULL,
    NULL,
    3.5,
    'rating',
    'DESC',
    5,
    0,
    'manager'
);

-- ============================================================
-- 16. FAILURE CASES
--
-- These examples are commented because each intentionally
-- raises an exception.
-- ============================================================

-- Invalid sorting field:
-- SELECT * FROM search_products(
--     p_sort_field => 'untrusted_column'
-- );

-- Invalid sorting direction:
-- SELECT * FROM search_products(
--     p_sort_direction => 'SIDEWAYS'
-- );

-- Invalid price range:
-- SELECT * FROM search_products(
--     p_min_price => 10000,
--     p_max_price => 100
-- );

-- Invalid rating:
-- SELECT * FROM search_products(
--     p_min_rating => 8
-- );

-- Invalid page size:
-- SELECT * FROM search_products(
--     p_limit => 1000
-- );

-- ============================================================
-- 17. QUERY PERFORMANCE INSPECTION
-- ============================================================

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    product_id,
    product_name,
    price,
    rating
FROM products
WHERE active = TRUE
  AND category_id = 1
  AND price BETWEEN 1000 AND 10000
ORDER BY rating DESC, product_id ASC
LIMIT 10;

-- ============================================================
-- 18. TRANSACTION EXAMPLE
-- ============================================================

SAVEPOINT before_product_update;

UPDATE products
SET price = price * 1.05
WHERE product_id = 2;

-- Demonstrate rollback to a savepoint.
ROLLBACK TO SAVEPOINT before_product_update;

-- The sample catalog remains unchanged.
RELEASE SAVEPOINT before_product_update;

COMMIT;

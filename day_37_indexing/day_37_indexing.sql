-- PostgreSQL 16+ compatible indexing laboratory.
--
-- The schema represents a commerce workload with customers, orders, and
-- operational events. The script demonstrates:
--   * B-tree indexes for equality, ranges, and ordering
--   * hash indexes for equality-only access
--   * composite indexes and column-order effects
--   * partial indexes for stable subsets
--   * selectivity and data distribution
--   * constraints and indexes as integrity mechanisms
--   * EXPLAIN plans
--   * transactional behavior
--
-- Run in a disposable PostgreSQL database because the script creates and
-- replaces an indexing_lab schema.

DROP SCHEMA IF EXISTS indexing_lab CASCADE;
CREATE SCHEMA indexing_lab;
SET search_path TO indexing_lab;

CREATE TABLE customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL,
    customer_tier TEXT NOT NULL
        CHECK (customer_tier IN ('standard', 'premium', 'enterprise'))
);

CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    order_number TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL
        CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    region TEXT NOT NULL
        CHECK (region IN ('north', 'south', 'east', 'west')),
    order_date DATE NOT NULL,
    total_cents BIGINT NOT NULL
        CHECK (total_cents >= 0)
);

CREATE TABLE support_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);

INSERT INTO customers (
    email,
    country_code,
    customer_tier
)
SELECT
    'customer' || n || '@example.test',
    CASE
        WHEN n % 20 < 8 THEN 'IN'
        WHEN n % 20 < 12 THEN 'US'
        WHEN n % 20 < 15 THEN 'DE'
        WHEN n % 20 < 17 THEN 'GB'
        WHEN n % 20 < 18 THEN 'SG'
        WHEN n % 20 < 19 THEN 'AU'
        ELSE 'CA'
    END,
    CASE
        WHEN n % 100 < 3 THEN 'enterprise'
        WHEN n % 100 < 25 THEN 'premium'
        ELSE 'standard'
    END
FROM generate_series(1, 20000) AS n;

INSERT INTO orders (
    customer_id,
    order_number,
    status,
    region,
    order_date,
    total_cents
)
SELECT
    1 + floor(random() * 20000)::BIGINT,
    'ORD-' || lpad(n::TEXT, 8, '0'),
    CASE
        WHEN n % 100 < 8 THEN 'pending'
        WHEN n % 100 < 36 THEN 'paid'
        WHEN n % 100 < 81 THEN 'shipped'
        ELSE 'cancelled'
    END,
    CASE n % 4
        WHEN 0 THEN 'north'
        WHEN 1 THEN 'south'
        WHEN 2 THEN 'east'
        ELSE 'west'
    END,
    DATE '2024-01-01'
        + floor(random() * 1096)::INTEGER,
    500 + floor(random() * 499501)::BIGINT
FROM generate_series(1, 100000) AS n;

INSERT INTO support_events (
    customer_id,
    event_type,
    created_at,
    payload
)
SELECT
    1 + floor(random() * 20000)::BIGINT,
    CASE n % 5
        WHEN 0 THEN 'login'
        WHEN 1 THEN 'password_reset'
        WHEN 2 THEN 'invoice'
        WHEN 3 THEN 'shipment'
        ELSE 'support'
    END,
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
        + (floor(random() * 31536000) || ' seconds')::INTERVAL,
    jsonb_build_object(
        'source', 'indexing-lab',
        'sequence', n
    )
FROM generate_series(1, 50000) AS n;

ANALYZE customers;
ANALYZE orders;
ANALYZE support_events;

-- PostgreSQL's default B-tree is the general-purpose ordered index.
-- It supports equality, ranges, and many ORDER BY access patterns.
CREATE INDEX idx_orders_order_date_btree
    ON orders USING btree (order_date);

-- Hash indexes are specialized for equality predicates.
-- They should not be selected when range or ordering behavior is required.
CREATE INDEX idx_orders_customer_hash
    ON orders USING hash (customer_id);

-- A composite B-tree expresses an access path beginning with region,
-- followed by status, followed by order_date.
--
-- Column order matters. The optimizer can use the leading portion of the
-- index more directly than an isolated predicate on a suffix column.
CREATE INDEX idx_orders_region_status_date
    ON orders USING btree (region, status, order_date);

-- This partial index contains only operationally pending orders.
-- It is useful because pending orders are a small, stable subset and the
-- recurring workload asks for pending orders by date.
CREATE INDEX idx_orders_pending_date
    ON orders USING btree (order_date)
    WHERE status = 'pending';

-- This index supports customer history ordered by date.
-- INCLUDE keeps total_cents available from the index for eligible index-only
-- scans without making total_cents part of the search-key ordering.
CREATE INDEX idx_orders_customer_date_covering
    ON orders USING btree (customer_id, order_date)
    INCLUDE (total_cents, status);

-- Foreign-key and join workloads commonly benefit from an index on the
-- referencing column.
CREATE INDEX idx_support_events_customer
    ON support_events USING btree (customer_id);

-- A unique constraint already created a unique B-tree index for email.
-- PostgreSQL also created indexes for the primary keys and order_number.
--
-- Show the actual index catalog.
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'indexing_lab'
ORDER BY tablename, indexname;

-- -------------------------------------------------------------------------
-- B-tree equality and range access
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, order_date, total_cents
FROM orders
WHERE order_date = DATE '2026-06-15';

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, order_date, total_cents
FROM orders
WHERE order_date >= DATE '2026-06-01'
  AND order_date < DATE '2026-07-01'
ORDER BY order_date;

-- A range is naturally aligned with the ordered key space of a B-tree.
-- The query uses a half-open interval so the upper boundary is unambiguous.

-- -------------------------------------------------------------------------
-- Hash equality access
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, customer_id, total_cents
FROM orders
WHERE customer_id = 17000;

-- Hash indexes target equality. This query does not require ordering or a
-- range, so it is an appropriate conceptual workload for the hash index.
--
-- Do not assume PostgreSQL will always choose a hash index. The optimizer
-- compares available paths using statistics, costs, table size, caching, and
-- the exact query shape.

-- -------------------------------------------------------------------------
-- Composite index
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, order_date, total_cents
FROM orders
WHERE region = 'south'
  AND status = 'paid'
ORDER BY order_date
LIMIT 50;

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, order_date, total_cents
FROM orders
WHERE region = 'south'
  AND status = 'paid'
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

-- The second query constrains all three index columns.
--
-- This query intentionally demonstrates a suffix-only predicate.
-- It may require a different plan because status is not the leading column.
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, region, status
FROM orders
WHERE status = 'paid';

-- -------------------------------------------------------------------------
-- Partial index
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, customer_id, order_date
FROM orders
WHERE status = 'pending'
  AND order_date >= DATE '2026-10-01'
ORDER BY order_date;

-- The query predicate contains status = 'pending', matching the partial
-- index predicate exactly. That makes the partial index applicable.

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_id, customer_id, order_date
FROM orders
WHERE status = 'shipped'
  AND order_date >= DATE '2026-10-01'
ORDER BY order_date;

-- The second query cannot use the pending-only partial index as its logical
-- source because shipped rows are not members of that indexed subset.

-- -------------------------------------------------------------------------
-- Selectivity and cardinality
-- -------------------------------------------------------------------------

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT status) AS distinct_statuses,
    COUNT(DISTINCT region) AS distinct_regions,
    COUNT(DISTINCT customer_id) AS distinct_customers,
    COUNT(DISTINCT order_date) AS distinct_dates,
    ROUND(
        COUNT(DISTINCT status)::NUMERIC / COUNT(*),
        6
    ) AS status_distinct_ratio,
    ROUND(
        COUNT(DISTINCT region)::NUMERIC / COUNT(*),
        6
    ) AS region_distinct_ratio,
    ROUND(
        COUNT(DISTINCT customer_id)::NUMERIC / COUNT(*),
        6
    ) AS customer_distinct_ratio,
    ROUND(
        COUNT(DISTINCT order_date)::NUMERIC / COUNT(*),
        6
    ) AS date_distinct_ratio
FROM orders;

-- Frequency distribution is more informative than distinct-count ratio alone.
SELECT
    status,
    COUNT(*) AS row_count,
    ROUND(
        COUNT(*)::NUMERIC
        / SUM(COUNT(*)) OVER (),
        4
    ) AS fraction_of_table
FROM orders
GROUP BY status
ORDER BY row_count DESC;

SELECT
    region,
    COUNT(*) AS row_count,
    ROUND(
        COUNT(*)::NUMERIC
        / SUM(COUNT(*)) OVER (),
        4
    ) AS fraction_of_table
FROM orders
GROUP BY region
ORDER BY row_count DESC;

-- A high-cardinality customer_id predicate normally narrows this workload
-- more strongly than a low-cardinality status predicate.
SELECT
    customer_id,
    COUNT(*) AS orders_for_customer
FROM orders
GROUP BY customer_id
ORDER BY orders_for_customer DESC
LIMIT 10;

-- -------------------------------------------------------------------------
-- Composite-index workload analysis
-- -------------------------------------------------------------------------

SELECT
    region,
    status,
    COUNT(*) AS row_count
FROM orders
GROUP BY region, status
ORDER BY region, status;

-- This result helps determine whether (region, status) is a meaningful
-- grouping for the actual workload instead of selecting the index order
-- merely from the table definition.

-- -------------------------------------------------------------------------
-- Partial-index size and predicate population
-- -------------------------------------------------------------------------

SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE status = 'pending') AS pending_orders,
    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE status = 'pending')
        / COUNT(*),
        2
    ) AS pending_percentage
FROM orders;

-- A partial index becomes more attractive when its indexed population is
-- substantially smaller than the base relation and the query workload
-- repeatedly targets that subset.

-- -------------------------------------------------------------------------
-- Covering-index workload
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT order_date, total_cents, status
FROM orders
WHERE customer_id = 17000
ORDER BY order_date DESC
LIMIT 25;

-- INCLUDE columns are payload columns, not additional search-key columns.
-- Their usefulness depends on visibility-map state, table changes, and the
-- optimizer's cost model.

-- -------------------------------------------------------------------------
-- Expression predicate and sargability consideration
-- -------------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT COUNT(*)
FROM orders
WHERE EXTRACT(YEAR FROM order_date) = 2026;

-- The ordinary order_date index is not necessarily the best access path for
-- this expression. If this expression becomes a dominant production query,
-- a deliberately designed expression index may be appropriate:
--
-- CREATE INDEX idx_orders_order_year
-- ON orders ((EXTRACT(YEAR FROM order_date)));
--
-- It is intentionally not created here because indexing every observed
-- expression can increase write and storage costs without a measured need.

-- -------------------------------------------------------------------------
-- Database-level integrity
-- -------------------------------------------------------------------------

DO $$
BEGIN
    BEGIN
        INSERT INTO customers (
            email,
            country_code,
            customer_tier
        )
        VALUES (
            'customer1@example.test',
            'IN',
            'standard'
        );
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE
                'Duplicate email rejected by the unique constraint/index.';
    END;
END
$$;

-- -------------------------------------------------------------------------
-- Transactional index maintenance
-- -------------------------------------------------------------------------

BEGIN;

INSERT INTO orders (
    customer_id,
    order_number,
    status,
    region,
    order_date,
    total_cents
)
VALUES (
    17000,
    'ORD-TRANSACTION-INDEX-DEMO',
    'pending',
    'south',
    DATE '2026-10-07',
    129900
);

-- The newly inserted row participates in applicable index maintenance as
-- part of the transaction. It is visible to this transaction before commit.
SELECT
    order_id,
    customer_id,
    status,
    order_date
FROM orders
WHERE order_number = 'ORD-TRANSACTION-INDEX-DEMO';

ROLLBACK;

-- The rollback removes both the row and the corresponding transactional
-- index changes.

-- -------------------------------------------------------------------------
-- Demonstrate invalid-state protection
-- -------------------------------------------------------------------------

DO $$
BEGIN
    BEGIN
        INSERT INTO orders (
            customer_id,
            order_number,
            status,
            region,
            order_date,
            total_cents
        )
        VALUES (
            17000,
            'ORD-INVALID-STATUS',
            'unknown',
            'south',
            DATE '2026-10-07',
            5000
        );
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Invalid status rejected by CHECK constraint.';
    END;
END
$$;

-- -------------------------------------------------------------------------
-- Statistics maintenance
-- -------------------------------------------------------------------------

ANALYZE orders;

SELECT
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'indexing_lab'
  AND tablename = 'orders'
  AND attname IN (
      'customer_id',
      'status',
      'region',
      'order_date'
  )
ORDER BY attname;

-- PostgreSQL's optimizer uses statistics such as distinct-value estimates
-- and correlation when estimating cardinality and comparing access paths.
--
-- Index design is therefore a feedback loop:
-- workload -> schema/index -> statistics -> execution plan -> measurement.

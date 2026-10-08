-- PostgreSQL Query Optimization Laboratory
--
-- This script demonstrates:
--   * EXPLAIN
--   * EXPLAIN ANALYZE
--   * sequential scans
--   * index scans
--   * bitmap access
--   * index-only scans
--   * composite indexes
--   * covering indexes using INCLUDE
--   * query planning
--   * cardinality estimates
--   * statistics
--   * sargable predicates
--   * sorting and aggregation
--   * join planning
--   * plan diagnostics
--
-- PostgreSQL is the target dialect.
--
-- The ANALYZE statements are intentional: PostgreSQL's planner uses
-- statistics about table and column distributions when estimating cardinality.

DROP SCHEMA IF EXISTS query_optimization_lab CASCADE;
CREATE SCHEMA query_optimization_lab;
SET search_path = query_optimization_lab;

CREATE TABLE customers (
    customer_id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL,
    customer_tier TEXT NOT NULL
        CHECK (customer_tier IN ('STANDARD', 'PREMIUM', 'ENTERPRISE')),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('PENDING', 'SHIPPED', 'DELIVERED', 'CANCELLED')),
    total_amount NUMERIC(12, 2) NOT NULL
        CHECK (total_amount >= 0),
    sales_channel TEXT NOT NULL
        CHECK (sales_channel IN ('WEB', 'MOBILE', 'STORE', 'PARTNER'))
);

-- A deterministic customer population gives the planner enough rows to make
-- access-path decisions meaningful while keeping the script reproducible.
INSERT INTO customers (
    customer_name,
    region,
    customer_tier,
    active
)
SELECT
    'Customer ' || gs,
    CASE (gs % 4)
        WHEN 0 THEN 'North'
        WHEN 1 THEN 'South'
        WHEN 2 THEN 'East'
        ELSE 'West'
    END,
    CASE (gs % 3)
        WHEN 0 THEN 'STANDARD'
        WHEN 1 THEN 'PREMIUM'
        ELSE 'ENTERPRISE'
    END,
    (gs % 19 <> 0)
FROM generate_series(1, 5000) AS gs;

-- Generate a substantial fact table. The planner can then demonstrate why
-- selectivity and estimated cardinality influence scan selection.
INSERT INTO orders (
    customer_id,
    order_date,
    status,
    total_amount,
    sales_channel
)
SELECT
    ((gs * 37) % 5000) + 1,
    DATE '2024-01-01'
        + ((gs * 17) % 1095),
    CASE (gs % 4)
        WHEN 0 THEN 'PENDING'
        WHEN 1 THEN 'SHIPPED'
        WHEN 2 THEN 'DELIVERED'
        ELSE 'CANCELLED'
    END,
    round((25 + ((gs * 7919) % 250000) / 100.0)::numeric, 2),
    CASE (gs % 4)
        WHEN 0 THEN 'WEB'
        WHEN 1 THEN 'MOBILE'
        WHEN 2 THEN 'STORE'
        ELSE 'PARTNER'
    END
FROM generate_series(1, 500000) AS gs;

-- ---------------------------------------------------------------------------
-- Baseline statistics
-- ---------------------------------------------------------------------------

ANALYZE customers;
ANALYZE orders;

-- With no useful secondary index, a broad predicate can naturally result in
-- a sequential scan. A sequential scan is not automatically a bad plan.
-- When a large fraction of the table is needed, reading the relation directly
-- can be cheaper than many index-driven heap visits.
EXPLAIN
SELECT order_id, customer_id, total_amount
FROM orders
WHERE status = 'DELIVERED';

EXPLAIN ANALYZE
SELECT order_id, customer_id, total_amount
FROM orders
WHERE status = 'DELIVERED';

-- ---------------------------------------------------------------------------
-- Basic index access
-- ---------------------------------------------------------------------------

CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

ANALYZE orders;

-- A selective equality predicate gives the planner a strong reason to consider
-- an index scan. The actual choice still depends on estimated cardinality and
-- cost parameters.
EXPLAIN
SELECT order_id, order_date, total_amount
FROM orders
WHERE customer_id = 42;

EXPLAIN ANALYZE
SELECT order_id, order_date, total_amount
FROM orders
WHERE customer_id = 42;

-- ---------------------------------------------------------------------------
-- Composite index
-- ---------------------------------------------------------------------------

CREATE INDEX idx_orders_customer_date
    ON orders(customer_id, order_date);

ANALYZE orders;

-- The leading customer_id equality narrows the index range, while order_date
-- supplies a range condition inside that customer-specific portion.
EXPLAIN
SELECT order_id, order_date, total_amount
FROM orders
WHERE customer_id = 42
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

EXPLAIN ANALYZE
SELECT order_id, order_date, total_amount
FROM orders
WHERE customer_id = 42
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

-- The order of columns matters. A query filtering only on the second key
-- does not receive the same benefit as a query constrained by the leading key.
EXPLAIN
SELECT order_id, customer_id, order_date
FROM orders
WHERE order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01';

-- ---------------------------------------------------------------------------
-- Covering index and Index Only Scan
-- ---------------------------------------------------------------------------

-- INCLUDE stores non-key columns in index tuples without changing the B-tree
-- ordering. This can make index-only access possible for queries that need
-- total_amount but do not use it as a search key.
CREATE INDEX idx_orders_customer_date_covering
    ON orders(customer_id, order_date)
    INCLUDE (total_amount, status);

ANALYZE orders;

EXPLAIN
SELECT order_date, total_amount, status
FROM orders
WHERE customer_id = 42
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

EXPLAIN ANALYZE
SELECT order_date, total_amount, status
FROM orders
WHERE customer_id = 42
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

-- PostgreSQL may use an Index Only Scan when the index contains the required
-- columns and visibility-map information allows heap access to be avoided.
-- Index-only does not mean that the base table is logically irrelevant:
-- PostgreSQL still needs visibility information for MVCC correctness.

-- ---------------------------------------------------------------------------
-- Bitmap access
-- ---------------------------------------------------------------------------

CREATE INDEX idx_orders_status
    ON orders(status);

ANALYZE orders;

-- A predicate that returns many rows can lead PostgreSQL to combine an index
-- with a bitmap heap scan. The bitmap collects qualifying heap locations and
-- then visits table pages in a more locality-friendly order.
EXPLAIN
SELECT order_id, customer_id, total_amount
FROM orders
WHERE status = 'DELIVERED'
  AND total_amount >= 1500;

EXPLAIN ANALYZE
SELECT order_id, customer_id, total_amount
FROM orders
WHERE status = 'DELIVERED'
  AND total_amount >= 1500;

-- ---------------------------------------------------------------------------
-- Sargability
-- ---------------------------------------------------------------------------

CREATE INDEX idx_orders_sales_channel
    ON orders(sales_channel);

CREATE INDEX idx_orders_order_date
    ON orders(order_date);

ANALYZE orders;

-- This range predicate exposes the indexed column directly and can be
-- converted into an index range condition.
EXPLAIN
SELECT COUNT(*)
FROM orders
WHERE order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01';

-- Applying a function to the indexed column changes the expression being
-- searched. A normal index on order_date does not automatically become an
-- index on EXTRACT(YEAR FROM order_date).
EXPLAIN
SELECT COUNT(*)
FROM orders
WHERE EXTRACT(YEAR FROM order_date) = 2026;

-- A half-open range preserves direct ordering on the stored DATE value.
EXPLAIN
SELECT COUNT(*)
FROM orders
WHERE order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01';

-- ---------------------------------------------------------------------------
-- Sorting and aggregation
-- ---------------------------------------------------------------------------

EXPLAIN
SELECT customer_id,
       COUNT(*) AS order_count,
       ROUND(SUM(total_amount), 2) AS revenue
FROM orders
WHERE order_date >= DATE '2026-01-01'
GROUP BY customer_id
ORDER BY revenue DESC
LIMIT 20;

EXPLAIN ANALYZE
SELECT customer_id,
       COUNT(*) AS order_count,
       ROUND(SUM(total_amount), 2) AS revenue
FROM orders
WHERE order_date >= DATE '2026-01-01'
GROUP BY customer_id
ORDER BY revenue DESC
LIMIT 20;

-- The plan can contain aggregation and sorting work even when an index
-- efficiently identifies the input rows. Optimizing only the scan node does
-- not guarantee that the complete query becomes inexpensive.

-- ---------------------------------------------------------------------------
-- Join planning
-- ---------------------------------------------------------------------------

-- The foreign-key lookup column is indexed so a selective customer-side
-- predicate can efficiently locate matching orders.
EXPLAIN
SELECT c.customer_id,
       c.customer_name,
       COUNT(o.order_id) AS order_count,
       ROUND(SUM(o.total_amount), 2) AS revenue
FROM customers AS c
JOIN orders AS o
  ON o.customer_id = c.customer_id
WHERE c.region = 'North'
  AND c.active = TRUE
GROUP BY c.customer_id, c.customer_name
ORDER BY revenue DESC
LIMIT 20;

EXPLAIN ANALYZE
SELECT c.customer_id,
       c.customer_name,
       COUNT(o.order_id) AS order_count,
       ROUND(SUM(o.total_amount), 2) AS revenue
FROM customers AS c
JOIN orders AS o
  ON o.customer_id = c.customer_id
WHERE c.region = 'North'
  AND c.active = TRUE
GROUP BY c.customer_id, c.customer_name
ORDER BY revenue DESC
LIMIT 20;

-- PostgreSQL may select Nested Loop, Hash Join, or another strategy based on
-- estimated cardinality, available indexes, memory, and cost settings.

-- ---------------------------------------------------------------------------
-- Cardinality estimation diagnostics
-- ---------------------------------------------------------------------------

-- PostgreSQL exposes planner statistics through pg_stats. Inspecting these
-- values helps explain why a plan was chosen.
SELECT
    tablename,
    attname,
    n_distinct,
    most_common_vals,
    most_common_freqs,
    histogram_bounds
FROM pg_stats
WHERE schemaname = 'query_optimization_lab'
  AND tablename = 'orders'
  AND attname IN ('customer_id', 'status', 'order_date');

-- Compare actual cardinality with a planner estimate through EXPLAIN ANALYZE.
-- Look for "rows=" versus "actual rows=". Large differences can propagate
-- upward and cause poor join order or access-path decisions.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT order_id, customer_id, total_amount
FROM orders
WHERE customer_id = 42
  AND status = 'DELIVERED';

-- ---------------------------------------------------------------------------
-- Query rewrite
-- ---------------------------------------------------------------------------

-- Non-sargable expression:
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM orders
WHERE EXTRACT(YEAR FROM order_date) = 2026;

-- Sargable range equivalent:
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM orders
WHERE order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01';

-- The rewrite preserves the logical date interval while exposing an ordered
-- range that a B-tree index can search directly.

-- ---------------------------------------------------------------------------
-- Multi-column filtering
-- ---------------------------------------------------------------------------

CREATE INDEX idx_orders_customer_status_date
    ON orders(customer_id, status, order_date);

ANALYZE orders;

EXPLAIN ANALYZE
SELECT order_id,
       order_date,
       total_amount
FROM orders
WHERE customer_id = 42
  AND status = 'DELIVERED'
  AND order_date >= DATE '2026-01-01'
  AND order_date < DATE '2027-01-01'
ORDER BY order_date;

-- The composite key follows the query's equality predicates before the range
-- dimension. This ordering is workload-specific rather than a universal rule.

-- ---------------------------------------------------------------------------
-- Prepared statement and parameterized planning
-- ---------------------------------------------------------------------------

PREPARE customer_orders(bigint) AS
SELECT order_id,
       order_date,
       total_amount
FROM orders
WHERE customer_id = $1
ORDER BY order_date;

EXPLAIN EXECUTE customer_orders(42);

EXPLAIN ANALYZE EXECUTE customer_orders(42);

DEALLOCATE customer_orders;

-- Parameterized statements are important in applications because the planner
-- may use either custom or generic planning behavior depending on PostgreSQL's
-- planning decisions and workload. A parameterized query should therefore be
-- evaluated using representative values rather than only one convenient case.

-- ---------------------------------------------------------------------------
-- Statistics refresh
-- ---------------------------------------------------------------------------

-- ANALYZE refreshes planner statistics after substantial data changes.
ANALYZE orders;

-- Higher statistics targets can improve estimates for columns with complex
-- distributions, at the cost of additional statistics collection/storage.
ALTER TABLE orders
    ALTER COLUMN customer_id SET STATISTICS 500;

ANALYZE orders;

EXPLAIN ANALYZE
SELECT COUNT(*)
FROM orders
WHERE customer_id = 42;

-- Restore a moderate target after the demonstration.
ALTER TABLE orders
    ALTER COLUMN customer_id SET STATISTICS -1;

ANALYZE orders;

-- ---------------------------------------------------------------------------
-- Useful production diagnostic query
-- ---------------------------------------------------------------------------

-- This query identifies columns with unusually high distinct-value counts
-- or frequent values from the planner's statistics catalog. It does not
-- replace plan inspection, but it helps connect plan behavior to data shape.
SELECT
    tablename,
    attname,
    n_distinct,
    most_common_freqs
FROM pg_stats
WHERE schemaname = 'query_optimization_lab'
ORDER BY tablename, attname;

-- The central optimization workflow demonstrated by this script is:
-- inspect the SQL,
-- inspect EXPLAIN,
-- inspect EXPLAIN ANALYZE,
-- compare estimated and actual rows,
-- inspect scan and join choices,
-- examine statistics,
-- change SQL or indexes only when evidence identifies a real cost problem,
-- and then measure the resulting plan again.

DROP SCHEMA IF EXISTS migration_demo CASCADE;

CREATE SCHEMA migration_demo;

SET search_path TO migration_demo;

-- The migration history table is the durable record of schema evolution.
-- An applied migration must never be silently rewritten in place.
CREATE TABLE schema_migrations (
    version BIGINT PRIMARY KEY,
    migration_name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_ms INTEGER,
    UNIQUE (migration_name),
    CHECK (version > 0),
    CHECK (length(trim(migration_name)) > 0),
    CHECK (length(checksum) >= 16)
);

-- Version 1: initial customer schema.
CREATE TABLE customers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT customers_email_not_blank
        CHECK (length(trim(email)) > 0),
    CONSTRAINT customers_name_not_blank
        CHECK (length(trim(full_name)) > 0)
);

CREATE UNIQUE INDEX ux_customers_email
    ON customers (lower(email));

INSERT INTO schema_migrations (
    version,
    migration_name,
    checksum,
    execution_ms
)
VALUES (
    1,
    'create_customers',
    'sha256:create_customers_v1',
    12
);

-- Business data existing before the next schema version.
INSERT INTO customers (email, full_name)
VALUES
    ('ada@example.com', 'Ada Lovelace'),
    ('grace@example.com', 'Grace Hopper');

-- Version 2: schema evolution through a backward-compatible additive change.
-- The default makes the new column immediately valid for existing rows.
ALTER TABLE customers
    ADD COLUMN status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE customers
    ADD CONSTRAINT customers_status_valid
    CHECK (status IN ('active', 'suspended', 'closed'));

INSERT INTO schema_migrations (
    version,
    migration_name,
    checksum,
    execution_ms
)
VALUES (
    2,
    'add_customer_status',
    'sha256:add_customer_status_v2',
    8
);

-- Version 3: introduce a dependent table and enforce referential integrity.
CREATE TABLE orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    amount_cents BIGINT NOT NULL,
    order_state TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT orders_customer_fk
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON DELETE RESTRICT,

    CONSTRAINT orders_amount_nonnegative
        CHECK (amount_cents >= 0),

    CONSTRAINT orders_state_valid
        CHECK (
            order_state IN (
                'pending',
                'paid',
                'cancelled',
                'refunded'
            )
        )
);

CREATE INDEX ix_orders_customer_id
    ON orders(customer_id);

CREATE INDEX ix_orders_state_created_at
    ON orders(order_state, created_at);

INSERT INTO orders (
    customer_id,
    amount_cents,
    order_state
)
VALUES
    (1, 12999, 'paid'),
    (2, 8500, 'pending');

INSERT INTO schema_migrations (
    version,
    migration_name,
    checksum,
    execution_ms
)
VALUES (
    3,
    'create_orders',
    'sha256:create_orders_v3',
    21
);

-- Version 4: data migration followed by a schema convention.
-- This operation is intentionally separate from structural changes because
-- data transformation has its own validation and rollback considerations.
BEGIN;

UPDATE customers
SET full_name = regexp_replace(trim(full_name), '\s+', ' ', 'g');

ALTER TABLE customers
    ADD COLUMN external_id TEXT;

CREATE UNIQUE INDEX ux_customers_external_id
    ON customers(external_id)
    WHERE external_id IS NOT NULL;

UPDATE customers
SET external_id =
    'CRM-' || lpad(id::text, 8, '0')
WHERE external_id IS NULL;

ALTER TABLE customers
    ALTER COLUMN external_id SET NOT NULL;

INSERT INTO schema_migrations (
    version,
    migration_name,
    checksum,
    execution_ms
)
VALUES (
    4,
    'normalize_names_and_add_external_id',
    'sha256:normalize_names_and_add_external_id_v4',
    37
);

COMMIT;

-- Migration history can be used to audit exactly which versions exist.
SELECT
    version,
    migration_name,
    checksum,
    applied_at,
    execution_ms
FROM schema_migrations
ORDER BY version;

-- The current schema state can be inspected through PostgreSQL catalogs.
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'migration_demo'
ORDER BY table_name, ordinal_position;

-- The application can distinguish migrations from business data.
SELECT
    c.id,
    c.email,
    c.full_name,
    c.status,
    c.external_id,
    COUNT(o.id) AS order_count,
    COALESCE(SUM(o.amount_cents), 0) AS order_value_cents
FROM customers AS c
LEFT JOIN orders AS o
    ON o.customer_id = c.id
GROUP BY
    c.id,
    c.email,
    c.full_name,
    c.status,
    c.external_id
ORDER BY c.id;

-- Migration validation: versions should form a continuous history in this
-- example. A gap indicates a deployment or migration packaging problem.
WITH expected AS (
    SELECT generate_series(
        1,
        (SELECT COALESCE(MAX(version), 0) FROM schema_migrations)
    ) AS version
)
SELECT expected.version AS missing_version
FROM expected
LEFT JOIN schema_migrations AS applied
    ON applied.version = expected.version
WHERE applied.version IS NULL;

-- PostgreSQL transaction semantics protect a migration from partial DDL/DML
-- execution. The following example intentionally fails and is rolled back.
BEGIN;

ALTER TABLE customers
    ADD COLUMN temporary_deployment_marker TEXT;

DO $$
BEGIN
    RAISE EXCEPTION
        'Simulated deployment failure: validation did not pass';
END
$$;

COMMIT;

-- The previous transaction does not reach COMMIT because the exception aborts
-- the transaction. In a deployment runner, the failure must be followed by
-- ROLLBACK before another transaction is attempted.
ROLLBACK;

-- Verify that the failed migration did not leave the marker behind.
SELECT
    column_name
FROM information_schema.columns
WHERE table_schema = 'migration_demo'
  AND table_name = 'customers'
  AND column_name = 'temporary_deployment_marker';

-- Demonstrate database-level protection against invalid data.
-- The statements below are intentionally commented out because they would
-- fail the constraints:
--
-- INSERT INTO orders (customer_id, amount_cents, order_state)
-- VALUES (999999, 1000, 'paid');
--
-- INSERT INTO orders (customer_id, amount_cents, order_state)
-- VALUES (1, -1, 'paid');
--
-- UPDATE customers
-- SET status = 'unknown'
-- WHERE id = 1;

-- A safe migration policy query can identify expensive or long-running
-- migrations for deployment review.
SELECT
    version,
    migration_name,
    execution_ms
FROM schema_migrations
WHERE execution_ms >= 30
ORDER BY execution_ms DESC;

-- Schema evolution query showing dependencies between customers and orders.
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS referenced_table,
    ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
   AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
   AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'migration_demo'
  AND tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, tc.constraint_name;

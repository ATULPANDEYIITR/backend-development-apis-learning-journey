-- PostgreSQL implementation of the Repository Pattern domain.
-- The repository boundary is represented by SQL-facing structures and views:
-- application code can treat the database as a persistence implementation
-- while domain services remain responsible for business orchestration.

DROP VIEW IF EXISTS active_customer_repository;
DROP TABLE IF EXISTS customer_audit;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT customers_name_not_blank
        CHECK (length(trim(name)) >= 2),

    CONSTRAINT customers_email_not_blank
        CHECK (length(trim(email)) >= 5),

    CONSTRAINT customers_status_valid
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DELETED'))
);

CREATE UNIQUE INDEX customers_email_unique_idx
    ON customers (lower(email));

CREATE INDEX customers_status_idx
    ON customers (status);

CREATE TABLE customer_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT customer_audit_customer_fk
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
        ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION update_customer_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER customers_updated_at_trigger
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION update_customer_timestamp();

CREATE OR REPLACE FUNCTION audit_customer_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO customer_audit (
            customer_id,
            old_status,
            new_status
        )
        VALUES (
            NEW.customer_id,
            OLD.status,
            NEW.status
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER customers_status_audit_trigger
AFTER UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION audit_customer_status();

INSERT INTO customers (name, email, status)
VALUES
    ('Ananya Kapoor', 'ananya@example.com', 'ACTIVE'),
    ('Vikram Joshi', 'vikram@example.com', 'ACTIVE'),
    ('Meera Nair', 'meera@example.com', 'SUSPENDED'),
    ('Rohan Das', 'rohan@example.com', 'DELETED');

-- This view acts as a database-side read repository for an important
-- application query. The service does not need to know how the active-user
-- query is physically implemented.
CREATE VIEW active_customer_repository AS
SELECT
    customer_id,
    name,
    email,
    status,
    created_at,
    updated_at
FROM customers
WHERE status = 'ACTIVE';

-- Repository-style lookup by identity.
SELECT
    customer_id,
    name,
    email,
    status
FROM customers
WHERE customer_id = 1;

-- Repository-style lookup by a normalized business key.
SELECT
    customer_id,
    name,
    email,
    status
FROM customers
WHERE lower(email) = lower('ANANYA@example.com');

-- Query through the read-oriented repository view.
SELECT
    customer_id,
    name,
    email
FROM active_customer_repository
ORDER BY customer_id;

-- The following transaction represents an application service operation.
-- Both the state transition and audit record are committed atomically.
BEGIN;

UPDATE customers
SET status = 'SUSPENDED'
WHERE customer_id = 1
  AND status = 'ACTIVE';

COMMIT;

SELECT
    customer_id,
    name,
    status,
    updated_at
FROM customers
WHERE customer_id = 1;

SELECT
    customer_id,
    old_status,
    new_status,
    changed_at
FROM customer_audit
WHERE customer_id = 1
ORDER BY changed_at DESC;

-- Database constraints reject duplicate normalized email values.
-- The statement is intentionally not executed because it would abort the
-- demonstration transaction/session when the unique index is violated.
-- INSERT INTO customers (name, email) VALUES ('Duplicate', 'ANANYA@example.com');

-- Invalid states are also rejected by the status CHECK constraint.
-- UPDATE customers SET status = 'UNKNOWN' WHERE customer_id = 2;

-- The repository abstraction can expose aggregate queries without forcing
-- callers to understand the physical table representation.
SELECT
    status,
    COUNT(*) AS customer_count
FROM customers
GROUP BY status
ORDER BY status;

-- PostgreSQL's index can support case-insensitive email lookup because the
-- unique index is built on lower(email).
EXPLAIN
SELECT customer_id, name, email
FROM customers
WHERE lower(email) = lower('vikram@example.com');

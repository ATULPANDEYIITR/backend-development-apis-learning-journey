-- PostgreSQL transaction isolation laboratory
--
-- PostgreSQL supports READ UNCOMMITTED syntax but implements it with
-- READ COMMITTED semantics. The demonstrations below therefore distinguish
-- the SQL standard's conceptual levels from PostgreSQL's actual behavior.
--
-- Run the DDL and sample data first. Concurrency demonstrations that require
-- two simultaneous sessions are documented as psql session scripts in comments.

DROP SCHEMA IF EXISTS isolation_lab CASCADE;
CREATE SCHEMA isolation_lab;

SET search_path TO isolation_lab;

CREATE TABLE account (
    account_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_code    TEXT NOT NULL UNIQUE,
    owner_name      TEXT NOT NULL,
    balance         NUMERIC(14, 2) NOT NULL,
    CONSTRAINT account_balance_nonnegative CHECK (balance >= 0)
);

CREATE TABLE transaction_audit (
    audit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id      BIGINT NOT NULL REFERENCES account(account_id),
    operation       TEXT NOT NULL,
    old_balance     NUMERIC(14, 2),
    new_balance     NUMERIC(14, 2),
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT valid_audit_operation
        CHECK (operation IN ('UPDATE', 'INSERT', 'TRANSFER'))
);

CREATE TABLE transfer (
    transfer_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_account_id   BIGINT NOT NULL REFERENCES account(account_id),
    destination_account_id BIGINT NOT NULL REFERENCES account(account_id),
    amount              NUMERIC(14, 2) NOT NULL,
    status              TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT transfer_positive CHECK (amount > 0),
    CONSTRAINT transfer_distinct_accounts
        CHECK (source_account_id <> destination_account_id),
    CONSTRAINT transfer_valid_status
        CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_account_owner
    ON account(owner_name);

CREATE INDEX idx_transfer_source_created
    ON transfer(source_account_id, created_at DESC);

CREATE INDEX idx_transfer_destination_created
    ON transfer(destination_account_id, created_at DESC);

CREATE OR REPLACE FUNCTION audit_account_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO transaction_audit (
            account_id,
            operation,
            old_balance,
            new_balance
        )
        VALUES (
            NEW.account_id,
            'UPDATE',
            OLD.balance,
            NEW.balance
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER account_balance_audit
AFTER UPDATE OF balance ON account
FOR EACH ROW
EXECUTE FUNCTION audit_account_change();

INSERT INTO account (account_code, owner_name, balance)
VALUES
    ('A-100', 'Asha', 1000.00),
    ('B-100', 'Bharat', 1000.00),
    ('C-100', 'Chitra', 500.00);

-- A view exposes current committed account state. It does not bypass
-- transaction isolation because PostgreSQL evaluates the underlying query
-- using the current transaction's visibility rules.
CREATE OR REPLACE VIEW current_account_balances AS
SELECT
    account_id,
    account_code,
    owner_name,
    balance
FROM account;

SELECT *
FROM current_account_balances
ORDER BY account_id;

-- PostgreSQL exposes the active transaction's isolation level through
-- transaction_isolation.
SELECT current_setting('transaction_isolation') AS default_isolation_level;

-- READ UNCOMMITTED
--
-- PostgreSQL accepts this syntax, but the effective behavior is READ COMMITTED.
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

SELECT
    current_setting('transaction_isolation') AS requested_level,
    account_code,
    balance
FROM account
WHERE account_code = 'A-100';

COMMIT;

-- READ COMMITTED
--
-- Each statement receives a fresh visibility snapshot. A second SELECT in
-- the same transaction can therefore observe a value committed by another
-- transaction after the first SELECT.
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

SELECT balance AS first_read
FROM account
WHERE account_code = 'A-100';

-- In a second PostgreSQL session, run:
--
-- BEGIN;
-- UPDATE isolation_lab.account
-- SET balance = 1200.00
-- WHERE account_code = 'A-100';
-- COMMIT;
--
-- Then return to this transaction:

SELECT balance AS second_read
FROM account
WHERE account_code = 'A-100';

COMMIT;

-- REPEATABLE READ
--
-- PostgreSQL creates a transaction-level snapshot. A concurrent committed
-- change is not visible to subsequent reads in the same transaction.
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

SELECT balance AS first_snapshot_read
FROM account
WHERE account_code = 'A-100';

-- In a second PostgreSQL session:
--
-- BEGIN;
-- UPDATE isolation_lab.account
-- SET balance = 1350.00
-- WHERE account_code = 'A-100';
-- COMMIT;
--
-- Back in this transaction, the following query continues to use the
-- original transaction snapshot:

SELECT balance AS second_snapshot_read
FROM account
WHERE account_code = 'A-100';

COMMIT;

-- SERIALIZABLE
--
-- PostgreSQL's SERIALIZABLE mode prevents execution histories that cannot
-- be represented as a serial order. A transaction may therefore fail with
-- SQLSTATE 40001 and must be retried by the application.
BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

SELECT
    account_code,
    balance
FROM account
WHERE account_code IN ('A-100', 'B-100')
ORDER BY account_code;

-- A concurrent session can perform a conflicting operation. Depending on
-- the exact read/write dependency graph, PostgreSQL may allow one transaction
-- to commit and abort another with a serialization failure.
--
-- Example second session:
--
-- BEGIN;
-- SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- UPDATE isolation_lab.account
-- SET balance = balance + 100
-- WHERE account_code = 'A-100';
-- COMMIT;
--
-- The first transaction may receive SQLSTATE 40001 when it later performs
-- a conflicting operation or commits.

UPDATE account
SET balance = balance + 50.00
WHERE account_code = 'B-100';

COMMIT;

-- Atomic transfer workflow.
--
-- Row-level UPDATE locking prevents two concurrent successful updates from
-- silently writing the same account balance. The transaction either commits
-- both account changes or rolls both back.
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

WITH source AS (
    SELECT account_id, balance
    FROM account
    WHERE account_code = 'A-100'
    FOR UPDATE
),
destination AS (
    SELECT account_id, balance
    FROM account
    WHERE account_code = 'B-100'
    FOR UPDATE
)
SELECT
    source.account_id AS source_id,
    destination.account_id AS destination_id,
    source.balance AS source_balance,
    destination.balance AS destination_balance
FROM source
CROSS JOIN destination;

UPDATE account
SET balance = balance - 100.00
WHERE account_code = 'A-100'
  AND balance >= 100.00;

-- The row count should be checked by application code. If zero rows are
-- updated, the source account did not have sufficient funds.
UPDATE account
SET balance = balance + 100.00
WHERE account_code = 'B-100';

INSERT INTO transfer (
    source_account_id,
    destination_account_id,
    amount,
    status
)
SELECT
    source.account_id,
    destination.account_id,
    100.00,
    'COMPLETED'
FROM account AS source
CROSS JOIN account AS destination
WHERE source.account_code = 'A-100'
  AND destination.account_code = 'B-100';

COMMIT;

-- Verify the transfer and audit records.
SELECT
    t.transfer_id,
    source.account_code AS source_account,
    destination.account_code AS destination_account,
    t.amount,
    t.status,
    t.created_at
FROM transfer AS t
JOIN account AS source
    ON source.account_id = t.source_account_id
JOIN account AS destination
    ON destination.account_id = t.destination_account_id
ORDER BY t.transfer_id;

SELECT
    account_code,
    owner_name,
    balance
FROM account
ORDER BY account_code;

SELECT
    audit_id,
    account_id,
    operation,
    old_balance,
    new_balance,
    changed_at
FROM transaction_audit
ORDER BY audit_id;

-- Constraint demonstration.
--
-- The following statement is intentionally invalid and should be rejected
-- by the account_balance_nonnegative CHECK constraint.
--
-- UPDATE account
-- SET balance = -1.00
-- WHERE account_code = 'A-100';

-- Aggregate workload for investigating committed state.
SELECT
    COUNT(*) AS account_count,
    SUM(balance) AS total_balance,
    MIN(balance) AS minimum_balance,
    MAX(balance) AS maximum_balance,
    AVG(balance) AS average_balance
FROM account;

-- A CTE can evaluate an invariant inside the transaction itself.
WITH balances AS (
    SELECT
        SUM(balance) AS total_balance,
        COUNT(*) AS account_count
    FROM account
)
SELECT
    total_balance,
    account_count,
    CASE
        WHEN total_balance >= 0 THEN 'VALID'
        ELSE 'INVALID'
    END AS invariant_status
FROM balances;

-- Inspect PostgreSQL's transaction isolation documentation through the
-- server's own configuration interface.
SHOW default_transaction_isolation;

-- A production application should treat serialization failure as transient.
-- The database statement below is illustrative metadata rather than a retry
-- implementation. Client code should catch SQLSTATE 40001 and retry the
-- complete transaction, not only the final failed statement.

SELECT
    '40001' AS serialization_failure_sqlstate,
    'retry the complete transaction' AS application_action;

-- Isolation levels control visibility and serialization guarantees.
-- Constraints, row locks, and transactions enforce different correctness
-- properties. They should not be treated as interchangeable mechanisms.

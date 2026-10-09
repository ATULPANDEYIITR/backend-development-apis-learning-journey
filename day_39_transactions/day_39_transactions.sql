/*
    transactions_acid.sql

    PostgreSQL-compatible transaction laboratory.

    The schema models a banking transfer because a transfer makes transaction
    boundaries visible: one account is debited, another is credited, and
    ledger records must agree with the resulting state.

    Demonstrated mechanisms:
    BEGIN
    COMMIT
    ROLLBACK
    SAVEPOINT
    ROLLBACK TO SAVEPOINT
    ACID-related constraints
    Row-level locking
    CHECK constraints
    Foreign keys
    Unique transaction references
    Indexes
    Views
    Transactional functions
    Isolation behavior
*/

DROP SCHEMA IF EXISTS acid_demo CASCADE;

CREATE SCHEMA acid_demo;

SET search_path TO acid_demo;

CREATE TABLE accounts (
    account_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_name      TEXT NOT NULL,
    balance_cents   BIGINT NOT NULL DEFAULT 0,
    active          BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT accounts_owner_not_blank
        CHECK (btrim(owner_name) <> ''),

    CONSTRAINT accounts_non_negative_balance
        CHECK (balance_cents >= 0)
);

CREATE TABLE transfer_transactions (
    transaction_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference       TEXT NOT NULL UNIQUE,
    source_account  BIGINT NOT NULL REFERENCES accounts(account_id),
    target_account  BIGINT NOT NULL REFERENCES accounts(account_id),
    amount_cents    BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'COMMITTED',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT transfer_positive_amount
        CHECK (amount_cents > 0),

    CONSTRAINT transfer_distinct_accounts
        CHECK (source_account <> target_account),

    CONSTRAINT transfer_valid_status
        CHECK (status IN ('COMMITTED', 'FAILED'))
);

CREATE TABLE ledger_entries (
    ledger_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id   BIGINT NOT NULL
        REFERENCES transfer_transactions(transaction_id),
    account_id       BIGINT NOT NULL
        REFERENCES accounts(account_id),
    entry_type       TEXT NOT NULL,
    amount_cents     BIGINT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT ledger_positive_amount
        CHECK (amount_cents > 0),

    CONSTRAINT ledger_valid_type
        CHECK (
            entry_type IN (
                'TRANSFER_OUT',
                'TRANSFER_IN',
                'DEPOSIT',
                'WITHDRAWAL'
            )
        )
);

CREATE INDEX idx_ledger_account
    ON ledger_entries(account_id);

CREATE INDEX idx_ledger_transaction
    ON ledger_entries(transaction_id);

CREATE INDEX idx_transfer_source
    ON transfer_transactions(source_account);

CREATE INDEX idx_transfer_target
    ON transfer_transactions(target_account);

INSERT INTO accounts (owner_name, balance_cents)
VALUES
    ('Asha', 100000),
    ('Ravi', 50000),
    ('Meera', 0);

CREATE VIEW account_balances AS
SELECT
    account_id,
    owner_name,
    balance_cents,
    balance_cents / 100.0 AS balance_amount,
    active
FROM accounts;

CREATE VIEW transfer_audit AS
SELECT
    t.reference,
    t.source_account,
    source.owner_name AS source_owner,
    t.target_account,
    target.owner_name AS target_owner,
    t.amount_cents / 100.0 AS amount,
    t.status,
    t.created_at
FROM transfer_transactions t
JOIN accounts source
    ON source.account_id = t.source_account
JOIN accounts target
    ON target.account_id = t.target_account;


/*
    Successful transaction.

    The debit, credit, transfer record, and ledger entries are committed
    together. If any statement raises an error, the transaction remains
    uncommitted until the caller decides to ROLLBACK.
*/

BEGIN;

WITH debit AS (
    UPDATE accounts
    SET balance_cents = balance_cents - 12550
    WHERE account_id = 1
      AND active
      AND balance_cents >= 12550
    RETURNING account_id
),
credit AS (
    UPDATE accounts
    SET balance_cents = balance_cents + 12550
    WHERE account_id = 2
      AND active
      AND EXISTS (SELECT 1 FROM debit)
    RETURNING account_id
)
INSERT INTO transfer_transactions (
    reference,
    source_account,
    target_account,
    amount_cents,
    status
)
SELECT
    'TRF-001',
    1,
    2,
    12550,
    'COMMITTED'
WHERE EXISTS (SELECT 1 FROM debit)
  AND EXISTS (SELECT 1 FROM credit);

INSERT INTO ledger_entries (
    transaction_id,
    account_id,
    entry_type,
    amount_cents
)
SELECT
    t.transaction_id,
    1,
    'TRANSFER_OUT',
    12550
FROM transfer_transactions t
WHERE t.reference = 'TRF-001';

INSERT INTO ledger_entries (
    transaction_id,
    account_id,
    entry_type,
    amount_cents
)
SELECT
    t.transaction_id,
    2,
    'TRANSFER_IN',
    12550
FROM transfer_transactions t
WHERE t.reference = 'TRF-001';

COMMIT;


/*
    Atomicity failure.

    The source debit occurs before a deliberately invalid ledger insert.
    PostgreSQL raises an error. ROLLBACK removes the debit as well as all
    other uncommitted work in the transaction.
*/

BEGIN;

UPDATE accounts
SET balance_cents = balance_cents - 5000
WHERE account_id = 1
  AND balance_cents >= 5000;

INSERT INTO ledger_entries (
    transaction_id,
    account_id,
    entry_type,
    amount_cents
)
VALUES (
    999999,
    1,
    'TRANSFER_OUT',
    5000
);

/*
    The foreign-key violation above causes the transaction to enter the
    aborted state. The following ROLLBACK restores the account balance.
*/
ROLLBACK;


/*
    Consistency enforcement.

    A direct attempt to make a balance negative violates the CHECK constraint.
    PostgreSQL rejects the statement, and the transaction is rolled back.
*/

BEGIN;

UPDATE accounts
SET balance_cents = -1
WHERE account_id = 2;

ROLLBACK;


/*
    Insufficient-funds transfer.

    The conditional UPDATE affects zero rows. The application can detect
    that result and explicitly roll back rather than creating a partial
    transfer.
*/

BEGIN;

SELECT pg_advisory_xact_lock(7001);

UPDATE accounts
SET balance_cents = balance_cents - 999999999
WHERE account_id = 1
  AND active
  AND balance_cents >= 999999999;

ROLLBACK;


/*
    SAVEPOINT.

    A savepoint allows part of an otherwise valid transaction to be undone
    without discarding work that occurred before the savepoint.
*/

BEGIN;

INSERT INTO accounts (owner_name, balance_cents)
VALUES ('Temporary Customer', 10000);

SAVEPOINT optional_work;

UPDATE accounts
SET balance_cents = balance_cents - 5000
WHERE owner_name = 'Temporary Customer';

ROLLBACK TO SAVEPOINT optional_work;

UPDATE accounts
SET balance_cents = balance_cents + 2500
WHERE owner_name = 'Temporary Customer';

RELEASE SAVEPOINT optional_work;

COMMIT;


/*
    Transactional function.

    The function performs the entire transfer while using row locks.
    SELECT ... FOR UPDATE serializes concurrent changes to the two accounts
    involved in the transfer.
*/

CREATE OR REPLACE FUNCTION perform_transfer(
    p_reference TEXT,
    p_source BIGINT,
    p_target BIGINT,
    p_amount_cents BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
    v_source_balance BIGINT;
BEGIN
    IF p_amount_cents <= 0 THEN
        RAISE EXCEPTION
            'Transfer amount must be positive';
    END IF;

    IF p_source = p_target THEN
        RAISE EXCEPTION
            'Source and target accounts must differ';
    END IF;

    /*
        Lock both rows in deterministic account-id order. Deterministic lock
        ordering reduces deadlock risk when two transactions touch the same
        pair of accounts in opposite logical directions.
    */
    IF p_source < p_target THEN
        PERFORM 1
        FROM accounts
        WHERE account_id = p_source
        FOR UPDATE;

        PERFORM 1
        FROM accounts
        WHERE account_id = p_target
        FOR UPDATE;
    ELSE
        PERFORM 1
        FROM accounts
        WHERE account_id = p_target
        FOR UPDATE;

        PERFORM 1
        FROM accounts
        WHERE account_id = p_source
        FOR UPDATE;
    END IF;

    SELECT balance_cents
    INTO v_source_balance
    FROM accounts
    WHERE account_id = p_source
      AND active;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Source account is missing or inactive';
    END IF;

    IF v_source_balance < p_amount_cents THEN
        RAISE EXCEPTION
            'Insufficient funds: available %, requested %',
            v_source_balance,
            p_amount_cents;
    END IF;

    UPDATE accounts
    SET balance_cents = balance_cents - p_amount_cents
    WHERE account_id = p_source;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Source account update failed';
    END IF;

    UPDATE accounts
    SET balance_cents = balance_cents + p_amount_cents
    WHERE account_id = p_target
      AND active;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Target account is missing or inactive';
    END IF;

    INSERT INTO transfer_transactions (
        reference,
        source_account,
        target_account,
        amount_cents,
        status
    )
    VALUES (
        p_reference,
        p_source,
        p_target,
        p_amount_cents,
        'COMMITTED'
    )
    RETURNING transaction_id
    INTO v_transaction_id;

    INSERT INTO ledger_entries (
        transaction_id,
        account_id,
        entry_type,
        amount_cents
    )
    VALUES
        (
            v_transaction_id,
            p_source,
            'TRANSFER_OUT',
            p_amount_cents
        ),
        (
            v_transaction_id,
            p_target,
            'TRANSFER_IN',
            p_amount_cents
        );

    RETURN v_transaction_id;
END;
$$;


/*
    The function participates in the caller's transaction. The caller still
    controls the final COMMIT or ROLLBACK.
*/

BEGIN;

SELECT perform_transfer(
    'TRF-FUNCTION-001',
    1,
    3,
    7500
);

COMMIT;


/*
    Demonstrate transaction-level rollback after a function call.
*/

BEGIN;

SELECT perform_transfer(
    'TRF-WILL-ROLLBACK',
    2,
    3,
    2500
);

ROLLBACK;


/*
    Consistency verification query.

    For every committed transfer, the source and target ledger entries should
    exist with matching amounts and opposite entry types.
*/

SELECT
    t.reference,
    t.amount_cents,
    COUNT(*) FILTER (
        WHERE l.entry_type = 'TRANSFER_OUT'
    ) AS outgoing_entries,
    COUNT(*) FILTER (
        WHERE l.entry_type = 'TRANSFER_IN'
    ) AS incoming_entries,
    COUNT(*) FILTER (
        WHERE l.amount_cents = t.amount_cents
    ) AS correctly_sized_entries
FROM transfer_transactions t
LEFT JOIN ledger_entries l
    ON l.transaction_id = t.transaction_id
WHERE t.status = 'COMMITTED'
GROUP BY
    t.reference,
    t.amount_cents
ORDER BY t.reference;


/*
    Account-level reconciliation.

    Net ledger movement should correspond to the difference between the
    original balance and the current balance when all transaction types are
    modeled consistently.
*/

SELECT
    a.account_id,
    a.owner_name,
    a.balance_cents,
    COALESCE(
        SUM(
            CASE
                WHEN l.entry_type IN ('TRANSFER_IN', 'DEPOSIT')
                    THEN l.amount_cents
                WHEN l.entry_type IN ('TRANSFER_OUT', 'WITHDRAWAL')
                    THEN -l.amount_cents
                ELSE 0
            END
        ),
        0
    ) AS net_ledger_movement
FROM accounts a
LEFT JOIN ledger_entries l
    ON l.account_id = a.account_id
GROUP BY
    a.account_id,
    a.owner_name,
    a.balance_cents
ORDER BY a.account_id;


/*
    Useful transaction inspection queries.
*/

SELECT *
FROM account_balances
ORDER BY account_id;

SELECT *
FROM transfer_audit
ORDER BY created_at;

SELECT
    transaction_id,
    reference,
    source_account,
    target_account,
    amount_cents / 100.0 AS amount,
    status,
    created_at
FROM transfer_transactions
ORDER BY transaction_id;


/*
    Isolation demonstration.

    Run the following sequence in two PostgreSQL sessions against the same
    database.

    Session A:
        BEGIN;
        SELECT balance_cents
        FROM accounts
        WHERE account_id = 1
        FOR UPDATE;

        UPDATE accounts
        SET balance_cents = balance_cents - 1000
        WHERE account_id = 1;

    Session B:
        BEGIN;
        SELECT balance_cents
        FROM accounts
        WHERE account_id = 1
        FOR UPDATE;

    Session B waits because Session A owns the row lock.

    When Session A executes COMMIT, Session B can continue and observe the
    serialized row state.

    A production application should choose an isolation level based on the
    anomaly it needs to prevent and should keep transactions short.
*/


/*
    Durable transaction boundary example.

    COMMIT is the point at which PostgreSQL makes the successful transaction
    eligible for durable persistence according to its configured WAL and
    durability settings. Application code must not report success before the
    commit has succeeded.
*/

BEGIN;

SELECT perform_transfer(
    'TRF-DURABILITY-001',
    1,
    2,
    1000
);

COMMIT;


/*
    Final state query.
*/

SELECT
    account_id,
    owner_name,
    balance_cents / 100.0 AS balance,
    active
FROM accounts
ORDER BY account_id;

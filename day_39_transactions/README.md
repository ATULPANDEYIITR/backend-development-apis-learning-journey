# Database Transactions and ACID

## Scope

This learning set focuses on database transactions as a mechanism for grouping related database operations into a controlled unit of work.

The implementations use a banking transfer scenario because a transfer has a strong transactional requirement: a source account must be debited and a target account must be credited without allowing a partial result.

The central distinction is:

- **Atomicity** determines whether the transaction's changes are treated as one indivisible unit.
- **Consistency** determines whether committed data satisfies the database and domain rules.
- **Isolation** determines how concurrent transactions interact while work is in progress.
- **Durability** concerns the persistence of successfully committed changes.

`BEGIN`, `COMMIT`, `ROLLBACK`, and `SAVEPOINT` are transaction-control mechanisms used to manage this work.

---

## Transaction Boundaries

A transaction begins when a database session establishes a transactional unit of work. In PostgreSQL, an explicit transaction commonly has the form `BEGIN`, followed by SQL statements, and then either `COMMIT` or `ROLLBACK`.

`COMMIT` makes the successful transaction permanent from the application's perspective.

`ROLLBACK` abandons the uncommitted changes made by the transaction.

A transaction is not simply a collection of SQL statements. The important property is that the database gives those statements a controlled relationship to one another. A debit followed by a credit can therefore be treated as one business operation rather than two independent updates.

The Python, C++, and Java implementations model this boundary explicitly through transaction objects and service methods. The SQL implementation uses PostgreSQL's actual transaction-control statements.

---

## ACID Properties

| Property | Meaning in the transaction model | Demonstrated by |
|---|---|---|
| Atomicity | Related changes succeed together or are rolled back together | Transfers and failure simulations |
| Consistency | Constraints and business invariants prevent invalid committed states | Non-negative balances and valid ledger references |
| Isolation | Concurrent work is controlled so transactions do not corrupt one another | Locks, transaction serialization, and PostgreSQL row locking |
| Durability | A committed transaction survives beyond the transaction's execution | PostgreSQL `COMMIT` and the persistence discussion in the implementations |

These properties are related but they are not interchangeable.

A transaction can be atomic without automatically proving that the business rules are correct. A database can enforce consistency constraints while still allowing concurrency anomalies if its isolation configuration is unsuitable. Durability is also distinct from atomicity: rolling back a transaction is about abandoning uncommitted work, while durability concerns what happens to work after successful commitment.

---

## Atomicity: Transfer as One Unit

The strongest demonstration of atomicity is a transfer.

Suppose account A has 1,000 units and account B has 500 units. A transfer of 100 requires:

`A = A - 100`

and

`B = B + 100`

If the first statement succeeds but the second fails and the first change remains, money has effectively disappeared.

A transaction prevents that partial outcome.

The implementations deliberately create failures after an initial debit. The transaction is then rolled back. The source balance returns to its previous value and the incomplete ledger work disappears.

This is different from merely writing defensive application code. The transaction boundary gives the database a mechanism for undoing the uncommitted changes.

The SQL implementation makes the behavior especially explicit. The transfer statements execute between `BEGIN` and `COMMIT`. A constraint or foreign-key failure causes the transaction to require rollback before another normal statement can proceed.

---

## Consistency: Valid State Before and After Commitment

Consistency means that a transaction moves the database from one valid state to another valid state according to the rules enforced by the database and application.

The examples use several rules:

- An account identifier must be valid.
- An account owner cannot be blank.
- An account balance cannot be negative.
- A ledger amount must be positive.
- A ledger entry must reference an existing account.
- A transfer amount must be positive.
- A transfer cannot use the same source and target account.
- A transfer record must reference valid accounts.

The SQL schema places several of these rules directly into the database through `CHECK`, `PRIMARY KEY`, `FOREIGN KEY`, and `UNIQUE` constraints.

For example, `CHECK (balance_cents >= 0)` prevents an invalid negative balance from being stored through an ordinary SQL operation.

The important design principle is that rules that define data integrity should not exist only in application code. Database constraints provide another enforcement layer.

---

## `BEGIN`, `COMMIT`, and `ROLLBACK`

The three basic transaction commands have different responsibilities.

### `BEGIN`

`BEGIN` starts an explicit PostgreSQL transaction block.

Operations executed after `BEGIN` are part of the same transaction until the transaction is committed or rolled back.

### `COMMIT`

`COMMIT` completes the transaction successfully.

Application code should only report a transactional operation as successfully persisted after the commit has succeeded.

### `ROLLBACK`

`ROLLBACK` abandons the uncommitted changes made by the current transaction.

This is the mechanism used by the examples when validation fails, an operation raises an exception, or a downstream operation makes the overall business operation impossible to complete.

The distinction matters in application architecture. A function that changes rows should not casually commit independently if a higher-level business operation needs to combine several changes into one atomic transaction.

---

## Savepoints

A savepoint creates an intermediate rollback position inside an active transaction.

The SQL implementation uses:

`SAVEPOINT optional_work`

followed by:

`ROLLBACK TO SAVEPOINT optional_work`

This is different from a full `ROLLBACK`.

A full rollback discards the entire transaction.

A rollback to a savepoint discards work performed after that savepoint while retaining earlier work.

The Python, JavaScript, C++, Java, and SQL examples demonstrate this through an optional operation. The optional operation can fail while the transaction remains capable of completing valid work performed before the savepoint.

A savepoint does not independently commit data. The outer transaction still needs a final `COMMIT`.

---

## Python Implementation

The Python program uses SQLite from the standard library, so it can run without an external database package.

The `accounts` table stores balances as integer cents rather than floating-point monetary values. This avoids binary floating-point rounding problems in the database representation.

The `ledger` table records the individual financial effects.

The `transfer()` function deliberately performs both sides of a transfer while leaving transaction ownership to the caller. The caller executes `BEGIN`, invokes the operation, and decides whether to `commit()` or `rollback()`.

This separation is important because the function performing database work does not necessarily know whether its work is the entire business transaction.

The program also demonstrates SQLite's connection context manager, which commits a successful block and rolls back when an exception escapes the block.

The consistency example deliberately violates the database's non-negative balance rule. SQLite rejects the invalid state through the table's `CHECK` constraint.

The concurrency example uses separate database connections and SQLite's write-lock behavior to illustrate that transaction isolation is a database concern rather than merely a convention between application functions.

---

## JavaScript Implementation

The JavaScript implementation builds an in-memory transaction engine rather than wrapping the same database operations used by Python.

The `Database` class owns account state and controls whether a write transaction is active.

The `Transaction` class stores an original snapshot. A successful `commit()` validates the resulting state, while `rollback()` restores the original snapshot.

This implementation makes atomicity visible as a state-management operation.

The JavaScript implementation also uses asynchronous functions to show an important production concern: asynchronous work can extend the lifetime of a transaction. Holding a real database transaction open while waiting for a slow external network operation can increase lock contention and reduce throughput.

The example therefore provides a useful architectural distinction between transaction work that belongs inside the database and slow external operations that should generally be handled outside a database transaction when the business design permits it.

---

## C++ Case Study

The C++ program models a transaction engine with explicit ownership and RAII.

The `Database` maintains accounts and ledger entries. `Database::Transaction` captures the state required for rollback and owns the active transaction boundary.

The transfer operation modifies both accounts and creates two ledger entries:

- `TRANSFER_OUT` for the source account
- `TRANSFER_IN` for the target account

A transaction is considered valid only after the database's consistency checks pass.

The C++ implementation uses an RAII destructor as a defensive rollback mechanism. If a transaction object leaves scope while still active, its destructor restores the original database state.

This design reflects an important C++ resource-management principle: transaction state can be treated as a resource whose lifetime should have a clear ownership model.

The program also demonstrates deterministic transaction locking. Only one write transaction is allowed by the simplified engine. This is intentionally simpler than a production database lock manager, but it makes the relationship between concurrent writers and transaction ownership explicit.

---

## Java Enterprise-Oriented Implementation

The Java implementation models a payment service using explicit domain types.

`TransactionState` represents the lifecycle:

`ACTIVE` → `COMMITTED`

or:

`ACTIVE` → `ROLLED_BACK`

The `LedgerType` enum prevents arbitrary strings from being used for transaction categories.

The `LedgerEntry` record provides an immutable representation of a ledger event.

The `Database` class manages the transactional state and validates consistency.

`PaymentService` is the application-level service that owns the transaction boundary. This is important because transaction management is generally a service concern rather than something scattered throughout individual domain methods.

The `Transaction` class supports deposits, withdrawals, transfers, savepoints, commit, rollback, and automatic cleanup through `AutoCloseable`.

The Java implementation therefore emphasizes explicit domain modeling, exception-based failure handling, transaction lifecycle state, and service-layer transaction ownership.

---

## SQL Data Model

The PostgreSQL schema contains four principal structures.

### `accounts`

This table represents account state.

`balance_cents` uses integer cents to avoid monetary floating-point representation problems.

The non-negative balance rule is enforced through a `CHECK` constraint.

### `transfer_transactions`

This table represents the business-level transfer.

It records the reference, source account, target account, amount, status, and creation timestamp.

The unique reference prevents accidental reuse of the same transaction reference.

### `ledger_entries`

This table represents the accounting effects produced by a transfer.

Foreign keys ensure that ledger entries cannot reference accounts that do not exist.

The transaction identifier links ledger entries to their originating transfer.

### Views

`account_balances` exposes account information in a convenient reporting form.

`transfer_audit` joins transfer information with source and target account names so that a transfer can be inspected without repeatedly writing the same join.

---

## Database-Level Integrity

Database constraints are especially important for transaction processing because application validation alone can be bypassed by another application, administrative query, migration, or integration.

The schema therefore uses:

- `PRIMARY KEY` for row identity.
- `FOREIGN KEY` for relationships between transfers, accounts, and ledger entries.
- `UNIQUE` for transfer references.
- `CHECK` constraints for positive amounts and non-negative balances.
- Indexes for account-based ledger searches and transfer lookups.

The constraints do not replace transactions.

A transaction determines how a group of changes is handled as a unit. Constraints determine whether individual database states satisfy specific integrity rules.

These mechanisms work together.

---

## Row Locking and Isolation

The PostgreSQL function uses `SELECT ... FOR UPDATE` before modifying the two accounts involved in a transfer.

A row lock prevents another transaction from simultaneously modifying the same locked rows in an incompatible way.

The function locks the two account IDs in deterministic order. This reduces the possibility of deadlocks when two transactions operate on the same accounts in opposite business directions.

For example, without deterministic ordering:

- Transaction A could lock account 1 and wait for account 2.
- Transaction B could lock account 2 and wait for account 1.

Neither transaction can progress.

Consistent lock ordering reduces this particular deadlock pattern.

Isolation is broader than row locking. PostgreSQL provides configurable transaction isolation levels, and the appropriate level depends on which concurrent anomalies an application must prevent.

---

## Isolation Is Not Atomicity

These properties are often confused.

Atomicity answers:

> What happens if part of my transaction fails?

Isolation answers:

> What can another transaction observe or change while my transaction is executing?

A transfer can be perfectly atomic while still requiring an appropriate isolation strategy for concurrent transfers.

For example, an application could correctly roll back a failed transaction while still suffering from a race condition if two transactions independently read a value and make decisions based on stale observations.

That is why transaction design must consider both the unit of work and the concurrency model.

---

## Durability

Durability applies after successful commitment.

Once PostgreSQL successfully commits a transaction, the database's configured persistence mechanisms are responsible for preserving the committed state.

The application should therefore distinguish:

`operation prepared`

from:

`transaction committed`

A service should not report a successful durable operation merely because its SQL statements executed without an immediate error. The transaction must successfully reach its commit point.

Durability also depends on the database's configuration, storage behavior, write-ahead logging, replication architecture, and failure model. The exact guarantees available in production depend on those settings.

---

## Failure Handling

A robust transactional implementation treats failures as part of normal control flow.

Important failure cases represented by the implementations include:

- insufficient funds;
- nonexistent accounts;
- inactive accounts;
- negative balances;
- invalid transaction amounts;
- duplicate transaction references;
- invalid foreign-key references;
- a failure after a partial debit;
- concurrent writer conflicts;
- invalid state at commit time;
- abandoned active transactions.

A common mistake is to catch an exception without rolling back the transaction.

In PostgreSQL, after many statement errors inside an explicit transaction, the transaction enters an aborted state and requires `ROLLBACK` before normal statements can continue.

Application frameworks often provide transaction abstractions that automate this pattern, but the underlying principle remains the same.

---

## Transaction Scope

Transaction scope should match the business operation that must be atomic.

A transaction that is too small may allow partial business operations.

A transaction that is unnecessarily large can hold locks for too long, increase contention, consume database resources, and make concurrency problems more likely.

The JavaScript asynchronous example highlights this issue. Waiting for an external service while holding a database transaction can unnecessarily extend transaction duration.

A better design often performs external preparation first, then opens a short database transaction for the changes that genuinely require atomicity.

The exact solution depends on the business operation and failure model.

---

## Common Transaction Design Mistakes

### Committing individual steps of one business operation

If a transfer commits the debit and later performs the credit in another transaction, the system can produce a partial transfer.

The debit and credit should belong to the same transaction when the business rule requires atomicity.

### Using floating-point values for monetary storage

Binary floating-point values are not a suitable representation for exact monetary amounts.

The examples use integer cents instead.

### Validating only in application code

An application can validate a balance before an update, but another connection can modify the same row before the original operation commits.

Database constraints, locking, and transaction isolation provide stronger enforcement mechanisms.

### Keeping transactions open unnecessarily

Long transactions can retain locks and increase contention.

Database work should normally be performed as a short, clearly bounded unit.

### Ignoring rollback after an exception

An application must know the transaction's state after failure.

A transaction that has failed should not be treated as if it were still a clean transaction ready for arbitrary SQL.

### Assuming `COMMIT` and `ROLLBACK` are interchangeable with savepoints

A savepoint only establishes a rollback position inside an existing transaction.

`ROLLBACK TO SAVEPOINT` does not commit earlier work.

The outer transaction remains active until `COMMIT` or full `ROLLBACK`.

---

## Performance Considerations

Transaction correctness comes first, but transaction design affects performance.

Short transactions generally reduce lock duration.

Appropriate indexes reduce the time required to locate rows involved in transactional operations.

The SQL implementation indexes account identifiers in ledger entries and source and target accounts in transfer records because those columns participate in common lookup and reporting operations.

Locking only the rows that need protection is generally preferable to unnecessarily broad locking.

Deterministic lock ordering can reduce deadlock risk.

Batching logically related writes into one transaction can reduce commit overhead, but excessively large transactions can increase memory use, lock duration, recovery cost, and contention.

---

## Security and Integrity Considerations

Transaction boundaries do not automatically provide authorization.

A production transfer service should authenticate the caller, authorize the requested operation, validate account ownership or permitted roles, and protect sensitive data.

The database should still enforce structural integrity independently of application authorization.

Audit records should use stable transaction references so that a completed operation can be traced across application logs and database records.

Financial systems also need careful treatment of duplicate requests. A unique transaction reference can provide an important idempotency mechanism, although complete idempotency design requires considering request retries, client behavior, and the exact transaction lifecycle.

---

## Debugging Transaction Failures

A useful debugging approach is to identify the exact transaction boundary first.

Determine:

- where the transaction starts;
- which statements modify state;
- which validation rules apply;
- where an exception occurs;
- whether the transaction is still active or already aborted;
- whether rollback was executed;
- whether the final commit succeeded.

The SQL implementation makes these boundaries visible through explicit `BEGIN`, `COMMIT`, and `ROLLBACK`.

The Python, C++, and Java implementations expose the same ideas through transaction objects and service methods.

When debugging concurrency issues, the investigation must also consider lock ownership, transaction duration, isolation level, and the order in which resources are acquired.

---

## Practical Relationship Between the Mechanisms

A useful mental model is:

**Business operation → transaction boundary → database operations → integrity validation → commit or rollback**

For a transfer:

**Request → BEGIN → lock required rows → validate balances → debit source → credit target → write ledger entries → validate constraints → COMMIT**

If any required step fails before commit:

**failure → ROLLBACK → previous committed state remains**

A savepoint provides an additional internal boundary:

**BEGIN → required work → SAVEPOINT → optional work → ROLLBACK TO SAVEPOINT → remaining transaction → COMMIT**

This structure explains why transaction management is more than issuing SQL updates. The transaction defines the unit within which database changes receive coordinated success or failure semantics.

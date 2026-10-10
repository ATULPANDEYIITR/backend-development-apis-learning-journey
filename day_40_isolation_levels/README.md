# Transaction Isolation Levels: Read Uncommitted, Read Committed, Repeatable Read, and Serializable

## Scope

Transaction isolation defines what one database transaction is allowed to observe while other transactions are executing concurrently. The four levels considered here are:

| Isolation level | Central visibility property | Main concurrency concern |
|---|---|---|
| Read Uncommitted | Weakest requested visibility guarantee | Dirty reads in systems that genuinely implement the level |
| Read Committed | Statements observe committed data available at statement start | A later statement can observe a newer committed value |
| Repeatable Read | A transaction works from a stable snapshot | Concurrent write conflicts and database-specific behavior |
| Serializable | The result must be equivalent to some serial execution | Transactions can fail and require retry |

Isolation is not the same as atomicity, durability, constraints, or locking. A transaction can be atomic without being serializable, and a database can enforce a non-negative balance constraint without preventing every concurrency anomaly.

The implementations in this artifact use the same subject from different technical perspectives:

- Python provides an executable MVCC-style teaching simulator with explicit transaction state, snapshots, read/write sets, rollback, validation, and concurrent scheduling.
- JavaScript models isolation as an event-driven transaction system and uses asynchronous scheduling to make transaction timing visible.
- C++ builds a database-style case study around transaction snapshots, conflict detection, synchronization, and a payment service.
- Java models isolation as explicit enterprise domain policies and separates transaction orchestration from isolation-specific behavior.
- PostgreSQL SQL models actual relational data, constraints, audit behavior, transaction isolation statements, row locking, and transactional workflows.

The simulators are intentionally educational models. They expose the logical mechanisms that matter for understanding isolation, while PostgreSQL implements substantially more machinery internally, including MVCC, WAL, locking, snapshots, predicate-related serialization mechanisms, recovery, and transaction visibility rules.

## Why Isolation Exists

A database rarely executes only one transaction at a time. Consider two operations against the same account:

`Transaction A: read balance -> calculate new balance -> write balance`

`Transaction B: read balance -> calculate new balance -> write balance`

If both transactions are allowed to observe and modify data without concurrency controls, the final result can depend on timing rather than business rules.

Isolation establishes boundaries around what concurrent transactions may see and which interleavings are considered valid.

The important distinction is that increasing isolation does not simply mean "making reads faster" or "locking everything." Different database engines implement isolation using different combinations of snapshots, locks, conflict detection, and serialization mechanisms.

## Transactional Anomalies

### Dirty read

A dirty read occurs when transaction A reads a value written by transaction B before B commits.

Suppose an account starts with a balance of `1000`.

Transaction B temporarily changes it to `250`.

Transaction A reads `250`.

Transaction B then rolls back.

The database has never committed `250`, but transaction A has already used that value.

A genuine READ UNCOMMITTED implementation can permit this behavior. PostgreSQL does not. PostgreSQL accepts the `READ UNCOMMITTED` syntax but provides READ COMMITTED semantics.

The Python, JavaScript, C++, and Java simulators deliberately expose an uncommitted write for their READ UNCOMMITTED demonstrations so that the anomaly can be observed explicitly.

### Non-repeatable read

A non-repeatable read occurs when the same transaction reads a row twice and receives different committed values.

A typical sequence is:

`Transaction A reads 1000`

`Transaction B changes the value to 1400 and commits`

`Transaction A reads the same row again and receives 1400`

The second read is not a repeat of the first observation.

PostgreSQL READ COMMITTED uses a new visibility snapshot for each statement, so this behavior is possible across separate statements in the same transaction.

### Repeatable read behavior

At REPEATABLE READ, the transaction uses a stable snapshot in PostgreSQL.

If transaction A establishes a snapshot showing an account at `1000`, a concurrent transaction changing the account to `1500` and committing does not cause an ordinary later read in transaction A to suddenly see `1500`.

This gives the transaction a coherent historical view of the data.

Repeatable read does not mean that every possible concurrency interaction becomes harmless. A transaction that attempts conflicting writes can still fail, and application logic must account for database-specific behavior.

### Serialization anomalies

The strongest level in this set is SERIALIZABLE.

The goal is not merely that each individual read be stable. The goal is that the final committed history be equivalent to some serial ordering of the transactions.

If the database cannot safely produce such an ordering, it can reject one transaction.

This is why SERIALIZABLE applications must treat serialization failures as expected transient failures rather than permanent business errors.

A correct retry repeats the complete transaction because the transaction's earlier reads and writes were part of the serialization decision.

## READ COMMITTED

READ COMMITTED is often a practical default for transactional applications.

In PostgreSQL, each statement obtains a snapshot that determines which committed rows are visible to that statement. Consequently, two separate SELECT statements within one transaction can see different committed versions if another transaction commits between them.

This makes READ COMMITTED different from REPEATABLE READ even though both prevent dirty reads.

The distinction matters for workflows that perform a read, wait for another operation, and then rely on the earlier value still being current.

The Python `demonstrate_read_committed_non_repeatable_read()` function explicitly performs this pattern. The JavaScript `readCommittedDemo()` uses an asynchronous delay to represent the period in which another transaction can commit. The Java model represents the rule through `ReadCommittedPolicy`, whose read operation consults current committed state rather than the transaction's original snapshot.

## REPEATABLE READ

REPEATABLE READ provides a stable transaction-level view in PostgreSQL.

This is useful when several queries must reason about the same logical database state. For example, a transaction calculating an account portfolio total should not unexpectedly combine values from different committed states merely because another transaction commits during processing.

The PostgreSQL implementation demonstrates this by beginning a REPEATABLE READ transaction, reading an account, allowing another session to update the account, and then reading the same account again.

The second read remains based on the original snapshot.

The application must still handle write conflicts correctly. A stable read view does not remove the possibility that another transaction has changed a row that the current transaction later attempts to modify.

## SERIALIZABLE

SERIALIZABLE is appropriate when correctness depends on preventing concurrency histories that cannot be represented as a serial execution.

Typical examples include workflows where several rows jointly form an invariant.

Suppose an operation reads accounts A and B and then makes a decision based on their combined state. Concurrent transactions modifying those accounts can create a result that would not be possible if the transactions had executed one after another.

A serializable database can detect the dangerous dependency and abort a transaction.

PostgreSQL reports serialization failures using SQLSTATE `40001`.

The application pattern is therefore:

`BEGIN`

`perform complete business operation`

`COMMIT`

If the transaction receives a serialization failure, restart the complete transaction.

Retrying only the final UPDATE is incorrect because the decision that led to the UPDATE was based on the transaction's earlier reads.

## PostgreSQL Interpretation of the Four Levels

The SQL implementation is explicitly PostgreSQL-oriented.

### READ UNCOMMITTED

PostgreSQL accepts:

`SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED`

but internally provides READ COMMITTED behavior.

Therefore PostgreSQL does not expose another transaction's uncommitted row version merely because READ UNCOMMITTED was requested.

The simulator implementations distinguish this from the ANSI conceptual model by intentionally exposing an uncommitted value in their READ UNCOMMITTED examples.

### READ COMMITTED

PostgreSQL's default isolation level is normally READ COMMITTED.

Each statement receives its own visibility snapshot.

A transaction can therefore observe a different committed value in a later statement.

### REPEATABLE READ

PostgreSQL provides a transaction-level snapshot.

Ordinary reads remain consistent with the snapshot established for the transaction.

Concurrent modifications can still result in transaction failure when conflicting writes occur.

### SERIALIZABLE

PostgreSQL adds serialization guarantees on top of its snapshot-based concurrency system.

A transaction can be aborted when its execution cannot be safely serialized.

Applications using this level need retry handling.

## Python Implementation

The Python program uses several structures to make transaction behavior explicit.

`Transaction` stores:

- `isolation`
- `state`
- `snapshot`
- `writes`
- `read_set`
- `write_set`

The snapshot records the committed values visible when the transaction begins.

The write set records modifications that have not yet been committed.

The read set becomes important at SERIALIZABLE because the transaction's serialization decision depends not only on rows it writes but also on data that influenced its decision.

`BankDatabase._read_value()` contains the visibility rules. READ UNCOMMITTED searches active transactions for uncommitted writes. READ COMMITTED reads current committed values. REPEATABLE READ and SERIALIZABLE use the transaction snapshot.

The simulator's `commit()` method performs isolation-specific validation before publishing writes.

`_validate_repeatable_read()` detects a write/write conflict against the transaction's original snapshot.

`_validate_serializable()` checks all observed rows for concurrent changes. This is a deliberately simplified serialization model, not a reimplementation of PostgreSQL's complete Serializable Snapshot Isolation machinery.

The Python transfer function demonstrates why isolation matters to business operations. It reads both accounts, validates available funds, prepares both writes, and commits them as one transaction.

Rollback removes pending writes without publishing them.

The threaded demonstration uses `threading.Barrier` and a small delay to create an actual concurrent scheduling point. Its output can vary because operating-system thread scheduling is nondeterministic.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven transaction scheduling.

The `TransactionDatabase` maintains:

- current committed values
- active transactions
- transaction snapshots
- pending writes
- read sets
- write sets
- transaction states

The `delay()` function returns a Promise so the READ COMMITTED demonstration can yield control before another transaction commits.

This is useful because JavaScript concurrency is commonly structured around an event loop and asynchronous operations rather than traditional shared-memory worker threads.

`readCommittedDemo()` therefore models a realistic application situation in which an asynchronous operation separates two database reads.

`RepositoryTransactionService` adds a domain-service layer. It performs a serializable transfer, validates the business operation, rolls back on failure, and returns the transaction result.

The implementation also demonstrates a critical distinction: asynchronous application code does not automatically provide database isolation. A Promise, callback, or event loop does not make database operations atomic. The database transaction still has to define the visibility and commit behavior.

## C++ Case Study

The C++ program treats the database as a concurrent payment platform.

`GovernanceAwareDatabase` maintains committed state, physical state, transaction metadata, and a mutex protecting shared structures.

`Transaction` contains a snapshot and explicit read and write sets.

The database distinguishes:

- visibility
- transaction state
- business validation
- conflict detection
- commit publication

This separation is useful for understanding that isolation is a database concurrency property, while validation such as "balance cannot be negative" is a business or integrity rule.

`PaymentService` builds a realistic transfer workflow over the database abstraction.

The source account is read, the destination account is read, sufficient funds are checked, both writes are staged, and the transaction is committed.

The concurrent serializable workload uses two `std::thread` workers. The sleep interval creates a scheduling window in which both transactions can develop from related snapshots. One transaction can then encounter a serialization conflict.

The C++ model uses `std::mutex` to protect simulator state. That mutex should not be confused with database isolation. A real database coordinates many processes and connections, not just threads inside one C++ process.

## Java Enterprise Model

The Java implementation models isolation through explicit domain policies.

`IsolationPolicy` defines two responsibilities:

`read(...)`

and

`validateCommit(...)`

Each isolation level then supplies a separate implementation.

This is more expressive than placing every rule in a single large conditional block because the policy itself becomes a domain abstraction.

`ReadCommittedPolicy` obtains current committed state for each read.

`RepeatableReadPolicy` reads from the transaction snapshot and validates modified rows before commit.

`SerializablePolicy` validates every row in the transaction's read/write footprint.

`TransactionManager` coordinates transaction lifecycle while delegating isolation-specific behavior to the selected policy.

`PaymentService` is intentionally separate from the transaction manager. The service contains the business operation, while the manager owns transaction state and isolation mechanics.

This separation mirrors enterprise application architecture where a service layer defines business behavior and the persistence layer controls transactional execution.

The use of Java records for `Account` also makes account state immutable from the domain object's perspective. Updating a balance produces a new `Account` record rather than mutating an existing object.

## SQL Data Model

The PostgreSQL schema represents a small financial domain.

`account` stores account identity, ownership, and balance.

The database-level constraint:

`CHECK (balance >= 0)`

prevents negative balances regardless of whether the invalid value originates from an application, administrative script, or another SQL client.

`transfer` records movement between accounts and enforces:

- positive transfer amounts
- different source and destination accounts
- a controlled status vocabulary

Foreign keys ensure that transfers refer to real accounts.

The indexes support common account and transfer lookup patterns. The transfer indexes place account identifiers before creation time so queries that retrieve recent transfers for one account can use the index efficiently.

## Database-Level Audit Behavior

The `transaction_audit` table records account balance updates.

The `account_balance_audit` trigger executes after an account balance changes.

This demonstrates an important distinction from isolation:

A trigger answers the question:

"Which database operation should automatically create an audit record?"

Isolation answers a different question:

"What data may a concurrent transaction observe, and which concurrent execution histories are allowed?"

Neither mechanism replaces the other.

## Row Locking in the Transfer Workflow

The SQL transfer example uses `FOR UPDATE`.

The selected account rows are locked for update while the transaction is active.

This is different from isolation level itself.

Isolation determines visibility and concurrency guarantees at the transaction level.

`FOR UPDATE` explicitly requests row-level locking for the selected rows.

A transaction can therefore use READ COMMITTED while still using row locks for a particular critical operation.

The transfer operation then deducts from the source and adds to the destination inside one transaction.

If the transaction fails before COMMIT, PostgreSQL rolls back both changes.

## Isolation Versus Constraints

A common design mistake is expecting isolation to enforce every business invariant.

Consider:

`balance >= 0`

A CHECK constraint is the appropriate database-level mechanism for this rule.

Consider instead:

"Two concurrent transactions must not both make a decision based on the same limited capacity."

That is a concurrency problem and may require appropriate transaction isolation, row locking, or another concurrency-control mechanism.

The mechanisms work together rather than replacing one another.

## Isolation Versus Atomicity

Atomicity means a transaction's changes are committed together or rolled back together.

Isolation concerns interaction between concurrent transactions.

A transaction can be atomic at READ COMMITTED.

A transaction can also be atomic at SERIALIZABLE.

The stronger isolation level changes the concurrency guarantees, not the basic meaning of COMMIT and ROLLBACK.

## Isolation Versus Durability

Durability concerns what happens after a successful commit, including recovery from failures.

Isolation concerns concurrent visibility and execution ordering.

The PostgreSQL implementation uses write-ahead logging and recovery mechanisms internally, but those mechanisms are separate from the conceptual isolation levels represented by the SQL commands in this artifact.

## Common Engineering Errors

### Treating READ UNCOMMITTED as identical across databases

The name does not guarantee identical behavior.

PostgreSQL accepts the syntax but provides READ COMMITTED semantics.

Application design should therefore be based on the actual database engine's documented behavior rather than only the SQL standard name.

### Assuming READ COMMITTED means a transaction sees one permanent snapshot

It does not mean that in PostgreSQL.

Separate statements can observe different committed states.

### Assuming REPEATABLE READ prevents every concurrent conflict

A stable snapshot prevents certain visibility anomalies, but a transaction can still encounter conflicting writes.

### Treating SERIALIZABLE failure as a permanent application error

Serialization failures are normally transient concurrency failures.

A safe design retries the complete transaction within bounded limits.

### Retrying only the failed statement

This is unsafe for serialization failures because earlier reads contributed to the transaction's dependency graph and business decision.

The complete transaction should be retried.

### Making transactions unnecessarily long

Long transactions can retain snapshots, increase contention, increase the probability of conflicts, and complicate operational behavior.

Transactions should contain the smallest complete unit of work that must be atomic.

### Relying only on application-side validation

Two application servers can execute the same validation concurrently.

Database constraints and appropriate concurrency controls should enforce invariants at the persistence boundary where necessary.

## Performance Considerations

Higher isolation can increase contention or transaction failure rates.

READ COMMITTED is often efficient because statements can use current committed visibility without requiring one transaction-wide snapshot.

REPEATABLE READ retains a consistent transaction view, which is useful for analytical or multi-query transactional decisions but can create longer-lived snapshot effects.

SERIALIZABLE adds stronger conflict detection and can increase abort/retry rates under high contention.

The correct performance decision is therefore workload-dependent.

A transaction processing system with frequent conflicting writes may experience many serialization failures under SERIALIZABLE. That does not automatically mean SERIALIZABLE is incorrect. It means the workload and retry strategy must be designed together.

Useful production measurements include transaction duration, lock wait time, deadlock rate, serialization failures, rollback rate, retry count, and query latency.

## Retry Design for Serializable Transactions

A robust retry loop should:

- retry only transient serialization or deadlock conditions
- repeat the entire transaction
- use a bounded number of attempts
- use backoff when contention is high
- avoid duplicating external side effects
- preserve idempotency where an external operation is involved

For example, an application should not send an external payment notification before a serializable database transaction is known to have committed unless it has an explicit mechanism for handling duplicate notifications.

The database transaction and external side effect have different failure boundaries.

## Debugging Isolation Problems

Isolation bugs are often timing-dependent.

Useful debugging information includes:

- transaction identifiers
- isolation level
- statement timestamps
- transaction start time
- commit or rollback time
- lock waits
- serialization failures
- deadlocks
- affected row counts
- application retry counts

A failing concurrency test should preserve the transaction schedule that produced the failure when possible.

The demonstrations in this artifact deliberately make the transaction schedule visible because the order of reads, writes, commits, and rollbacks is the key to understanding isolation anomalies.

## Practical Relationship Between the Four Levels

The levels can be understood as progressively stronger concurrency guarantees, but they should not be treated as a simple performance ladder.

READ UNCOMMITTED prioritizes weak visibility guarantees and is not a dirty-read mode in PostgreSQL.

READ COMMITTED provides committed statement-level visibility and is suitable for many ordinary transactional workloads.

REPEATABLE READ provides a stable transaction-level snapshot and is useful when several reads need a coherent view.

SERIALIZABLE protects the strongest correctness requirement by rejecting executions that cannot be represented as a serial order.

The correct choice depends on the invariant being protected, the database implementation, the transaction workload, contention, acceptable retry behavior, and performance requirements.

## Production Boundary

The simulators in this artifact intentionally simplify real database internals.

They do not reproduce PostgreSQL's complete MVCC storage engine, tuple visibility rules, vacuum behavior, lock manager, predicate-lock behavior, WAL, crash recovery, deadlock detection, or Serializable Snapshot Isolation implementation.

Their purpose is to expose the essential reasoning:

`concurrent transactions -> visibility rules -> reads and writes -> conflicts -> commit or rollback`

PostgreSQL then applies substantially more sophisticated machinery to make those rules work across multiple connections, processes, queries, failures, and durable storage.

The SQL implementation is therefore the authoritative database-specific part of this artifact when PostgreSQL behavior matters, while the Python, JavaScript, C++, and Java programs provide executable models for understanding the underlying transaction-isolation concepts.

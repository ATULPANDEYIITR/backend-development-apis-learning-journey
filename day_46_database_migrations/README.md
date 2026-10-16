# Database Migrations: Migration Concepts, Schema Evolution, and Migration History

## Scope

Database migrations provide a controlled way to move a database from one schema state to another while keeping the change reproducible, reviewable, and auditable.

A migration is normally a versioned unit of database change. It can create a table, add or remove a column, introduce an index, change a constraint, transform existing data, or perform another controlled schema operation. A migration system records which versions have already been applied so that the same deployment does not execute the same change repeatedly.

The central relationship is:

`migration definition -> database change -> migration history -> reproducible schema state`

The six artifacts in this repository examine that relationship from different technical perspectives. The Python implementation provides a practical migration runner over SQLite. The JavaScript implementation models an event-driven migration lifecycle without requiring an external database package. The C++ implementation presents a repository-style schema deployment engine. The Java implementation models migration execution as an enterprise service with explicit domain types. The PostgreSQL script demonstrates the same principles using actual relational DDL, constraints, indexes, transactions, and catalog queries.

## Migration Concepts

A migration has at least three important identities:

| Property | Purpose |
|---|---|
| Version | Establishes ordering and identifies a specific schema change |
| Name | Makes the change understandable to developers and operators |
| Checksum | Detects modification of a migration that has already been executed |

A migration commonly has an `up` operation and, where safe, a `down` operation. The `up` operation moves the schema forward. The `down` operation attempts to reverse that specific migration.

A migration history table is separate from ordinary business tables. It answers questions such as:

- Which schema versions have reached this database?
- When was each migration applied?
- Which migration definition was used?
- Can the current migration source still be reconciled with the deployed history?

A migration is not simply a SQL file. It is part of a deployment protocol. The migration definition, execution order, transaction behavior, database state, and history record must be considered together.

## Schema Evolution

Schema evolution describes the controlled transition from an existing database design to a new design.

Consider the progression represented by the artifacts:

`customers`

becomes

`customers + status`

then

`customers + status + orders`

then

`customers + status + orders + external_id`

Each state depends on the previous state. A deployment cannot safely assume that the database is empty.

The Python example begins with a `customers` table, adds a `status` column, creates an `orders` table, normalizes customer names, and finally introduces an external identity. The order is important because later migrations depend on objects created earlier.

The JavaScript model represents the same kind of evolution through an in-memory schema catalog. Its purpose is not to imitate a relational database completely. It isolates the migration mechanics so that version ordering, transaction snapshots, migration history, rollback, and checksum verification can be observed without requiring an npm database dependency.

The C++ implementation treats schema evolution as a technical deployment case study. Tables and columns are represented as explicit domain objects. The migration engine creates a snapshot before applying a migration so a failed change can restore the previous schema representation.

The Java implementation uses `DatabaseSchema`, `TableDefinition`, `Column`, `MigrationDefinition`, `MigrationRepository`, and `MigrationService`. This makes the schema state and migration lifecycle explicit domain concepts rather than treating migration behavior as a collection of unrelated procedures.

## Migration Ordering

Migration ordering is significant because migrations form a dependency chain.

A migration such as `create_orders` depends on the existence of `customers` when `orders.customer_id` references `customers.id`.

The migration versions in the examples are therefore ordered:

`1 -> 2 -> 3 -> 4`

Version 3 cannot safely execute against a database that has not executed version 1. A production migration system must not rely only on filenames or accidental filesystem ordering. Version numbers or another explicit ordering mechanism should determine execution order.

The Python runner sorts migration definitions by version before applying them. The JavaScript runner does the same. The Java service creates an ordered copy of the migration definitions before execution.

The PostgreSQL history table stores the version as a primary key. This prevents two history records from claiming the same migration version.

## Migration History

Migration history is the database's deployment record.

The PostgreSQL table `schema_migrations` contains:

- `version`
- `migration_name`
- `checksum`
- `applied_at`
- `execution_ms`

The version identifies the migration. The name provides human-readable context. The checksum provides protection against modifying an already-applied migration. The timestamp records when the migration reached the database. The execution duration provides an operational signal for identifying expensive migrations.

A history row should normally be written only when the corresponding migration succeeds.

The Python implementation enforces this relationship by applying the schema change and inserting the history record inside the same transaction. If the migration fails, the transaction is rolled back and the history row is not inserted.

The JavaScript implementation takes a snapshot of both schema state and migration history before applying a migration. The snapshot is restored if execution fails.

The Java implementation snapshots the schema and only records a `MigrationRecord` after the `up` operation completes successfully.

The C++ case study applies the same principle by preserving the previous schema representation when a migration throws an exception.

## Checksums and Migration Drift

An applied migration should normally be treated as immutable.

Suppose version 2 originally means:

`add_customer_status`

After version 2 has been deployed to production, changing its implementation to perform a different operation creates ambiguity. A newly initialized database would execute the modified version, while an existing production database already contains the original version.

The Python migration runner stores a checksum derived from migration identity and implementation information. It compares the current definition against stored history before proceeding.

The JavaScript runner hashes migration metadata and implementation identifiers with SHA-256. Its drift demonstration deliberately changes the implementation identifier of an existing migration and shows that history validation detects the mismatch.

This mechanism does not prove that a migration is semantically safe. It provides a strong signal that the deployed migration definition differs from the definition currently presented to the migration engine.

The preferred production response to an already-applied migration that needs correction is normally a new migration rather than rewriting the historical one.

## Transactional Migration Execution

A migration can involve several operations.

For example, a migration might:

- add a column;
- transform existing records;
- create an index;
- insert its migration-history record.

If an error occurs after only some operations have succeeded, the database could be left in a partially migrated state.

Transactions provide atomicity when the database engine and operations involved support transactional execution.

The Python implementation uses `BEGIN`, `COMMIT`, and `ROLLBACK` through SQLite. The deliberately failing migration creates an object and then raises an exception. The transaction rollback removes the object and prevents a history entry from being retained.

The PostgreSQL implementation explicitly demonstrates transaction boundaries around a data transformation and schema change. PostgreSQL transactional DDL makes it possible to roll back many schema operations together with associated data modifications.

Transaction support must not be assumed blindly. Some database engines or particular operations have restrictions around transactional DDL. Production migration design must account for the actual database engine and the exact operations being executed.

## Additive Schema Changes

Adding a nullable column or a column with an appropriate default is often easier to deploy safely than removing or changing an existing structure.

The PostgreSQL example adds `status` as a non-null column with the default value `active`. Existing customer rows therefore receive a valid value when the schema changes.

This is a schema compatibility decision rather than merely a syntax choice.

A migration that adds a required field to a table with millions of existing rows needs to answer:

- What value will existing rows receive?
- Will the database rewrite the entire table?
- Can the application deploy before the column exists?
- Can the old application continue operating during rollout?
- Does the new constraint remain compatible with existing data?

The examples emphasize these questions without pretending that every additive migration is automatically low risk.

## Data Migrations

Structural migration and data transformation are related but distinct.

Version 4 in the Python implementation normalizes existing customer names. This is not simply a new table or column. It modifies existing records.

The PostgreSQL implementation performs a data transformation using:

`regexp_replace(trim(full_name), '\s+', ' ', 'g')`

It then introduces `external_id` and populates values based on customer identifiers.

Data migrations require special care because the original data may not be reconstructable. Normalizing whitespace, converting formats, merging records, or deriving identifiers can destroy information.

For this reason, a `down` migration is not always capable of restoring the exact original data.

The Python migration explicitly treats name normalization as irreversible. Its rollback function does not attempt to invent the original whitespace.

## Rollback

Rollback is useful when a migration must be reversed and the previous state can be reconstructed safely.

A structural operation such as creating a table can normally have a corresponding drop operation.

A data transformation may not have a meaningful inverse.

The examples therefore distinguish:

`reversible structural change`

from

`potentially irreversible data transformation`

A rollback implementation should not claim reversibility when information has already been destroyed.

The Python runner rolls back the latest applied migration and removes its history record. The JavaScript and Java implementations follow the same lifecycle model.

Rollback also has operational risks. Dropping a table or column can destroy data. Removing an index can affect query performance. Reversing a constraint can create states that newer application code no longer expects.

Production rollback decisions therefore depend on both schema state and application compatibility.

## Expand-and-Contract Schema Evolution

A common production strategy is to separate a breaking schema change into compatible stages.

For example, changing:

`full_name`

into:

`first_name + last_name`

can be dangerous if the application and database are deployed independently.

An expand-and-contract approach can instead:

- add the new columns;
- deploy application code that can read the old and new representation;
- backfill existing rows;
- switch application writes to the new representation;
- validate the new data;
- remove the old representation only after compatibility is no longer required.

This strategy reduces the period during which application code and database schema disagree.

The examples in the repository focus on the migration engine itself, but the additive `status` and `external_id` changes illustrate why compatibility should be considered when designing individual migrations.

## Python Implementation

The Python program uses the standard-library `sqlite3` module, so it does not require an external package.

`Migration` is a dataclass containing a version, name, and forward and reverse functions.

`MigrationRunner` owns the migration lifecycle. It creates `schema_migrations`, reads applied versions, validates checksums, applies pending migrations, and rolls back the latest migration.

The runner applies each migration inside a database transaction. The migration-history insertion is performed in the same transaction as the schema change.

The program contains several meaningful migration types:

- `create_customers` establishes the initial relational structure.
- `add_customer_status` demonstrates an additive schema change.
- `create_orders` introduces a foreign-key relationship and an index.
- `normalize_customer_names` demonstrates a data migration.
- `add_customer_external_id` introduces a nullable identity field and a unique partial index.

The failure demonstration intentionally raises an exception after creating a table. The output verifies that the failed table does not remain and that migration history is unchanged.

The checksum demonstration simulates modification of an already-applied migration and shows why migration history should protect against drift.

The Python implementation also demonstrates a practical SQLite limitation through the rollback implementation of a column operation. Modern SQLite versions support `DROP COLUMN`, but migration compatibility still depends on the actual SQLite version deployed by an application.

## JavaScript Implementation

The JavaScript program uses Node.js standard-library facilities rather than an external database package.

`InMemoryDatabase` represents tables, columns, rows, indexes, and migration history. Its purpose is to isolate migration lifecycle behavior from database-driver details.

`MigrationRunner` extends `EventEmitter`. This provides a JavaScript-specific event-driven model for deployment observability.

The runner emits events such as:

`migrationApplied`

`migrationFailed`

`migrationRolledBack`

This pattern is useful in a larger Node.js migration system where deployment telemetry could listen for migration lifecycle events and send them to logs or monitoring infrastructure.

The migration objects contain explicit `up` and `down` functions. The runner takes a structural snapshot before execution. A failed migration restores both schema and history.

The JavaScript implementation also demonstrates unique-index validation and checksum-based drift detection.

Its main distinction from the Python program is architectural. It focuses on event-driven migration orchestration rather than relying on a real SQL engine for schema behavior.

## C++ Case Study

The C++ program models a schema deployment engine using explicit system components.

`SchemaCatalog` represents the current schema. It manages tables and columns and validates duplicate table and column creation.

`MigrationHistory` represents the persistent record of applied migration versions.

`MigrationEngine` coordinates migration execution and rollback.

The case study evolves a customer system through:

`customer_accounts`

then:

`customer_accounts + status`

then:

`customer_accounts + orders`

The `orders` structure contains a `customer_id` relationship and order-specific fields such as `amount_cents` and `state`.

The C++ implementation uses schema snapshots to represent transactional behavior. Before executing a migration, the previous schema state can be restored if the operation throws an exception.

The failed migration demonstrates an important deployment property: a migration may perform a valid structural operation and still fail later because existing data cannot satisfy the new requirement. The schema therefore must not be treated as successfully migrated merely because the first DDL operation succeeded.

The program also treats migration checksums as part of deployment identity. A changed migration definition should be represented by a new migration version rather than silently replacing the historical implementation.

## Java Enterprise Implementation

The Java implementation represents migration behavior through explicit domain types.

`Column` is a record describing a database column.

`TableDefinition` manages the columns belonging to one table.

`DatabaseSchema` manages the complete schema.

`MigrationDefinition` describes a versioned migration and contains `up` and `down` actions.

`MigrationRecord` represents durable migration history.

`MigrationRepository` isolates history storage from migration orchestration.

`MigrationService` performs validation, ordering, execution, rollback, and checksum verification.

This separation reflects an enterprise-oriented service design. Migration definitions describe changes, the repository represents history, the schema object models current state, and the service coordinates the workflow.

The failed migration adds `billing_profile_id` and then raises an exception because existing records cannot satisfy the new required field. The service restores the previous schema representation rather than leaving the system in an intermediate state.

The Java implementation uses Java 17-compatible records, immutable collection views, `Optional`, enums, lambdas, and standard collection types where they improve the domain model.

## PostgreSQL Implementation

The SQL script uses PostgreSQL syntax and creates a dedicated `migration_demo` schema.

The central table is `schema_migrations`.

The business schema evolves through several versions:

`customers`

then `customers.status`

then `orders`

then `customers.external_id`

The `customers` table demonstrates primary-key identity, non-null constraints, validation checks, and a case-insensitive unique index for email addresses.

The `orders` table demonstrates a foreign key, an amount constraint, an order-state constraint, and indexes designed around customer and state queries.

The fourth migration combines data normalization with structural evolution. Existing customer names are normalized before external identifiers are populated.

PostgreSQL catalog queries demonstrate how the resulting schema can be inspected through `information_schema`.

The script also demonstrates migration validation by checking for missing versions in the history sequence.

## Database-Level Integrity

Application code should not be the only enforcement layer for rules that are fundamentally relational.

The PostgreSQL schema places important constraints directly in the database:

`PRIMARY KEY` prevents duplicate identifiers.

`UNIQUE` and unique indexes prevent duplicate business identities.

`FOREIGN KEY` prevents references to nonexistent customers.

`CHECK` constraints prevent invalid states such as negative order amounts.

`NOT NULL` prevents required fields from being omitted.

This distinction matters during migrations because a schema change can expose invalid historical data. A migration that introduces a new constraint must validate existing records before assuming the constraint is safe.

## Migration Failure Modes

Migration systems can fail in several different ways.

A migration may fail because a referenced table does not exist. This is an ordering problem.

A migration may fail because a new non-null field has no valid value for existing rows. This is a data compatibility problem.

A migration may fail because an index cannot be created due to duplicate existing values. This is an integrity problem.

A migration may fail because a deployment process interrupted execution. This is an operational failure.

A migration may be rejected because its checksum no longer matches recorded history. This is migration drift.

A migration may succeed structurally but make an older application incompatible with the database. This is an application-schema compatibility problem.

These failures require different responses. A single generic retry strategy is not sufficient.

## Common Migration Mistakes

### Editing an applied migration

Changing a migration that has already reached production creates divergent histories. The safer approach is to create a new migration representing the correction.

### Combining unrelated changes into an opaque migration

A migration that changes many unrelated structures becomes difficult to review and diagnose. Versioned changes should have a clear purpose and a predictable dependency relationship.

### Ignoring existing data

A new constraint must be evaluated against records that already exist. Schema design cannot be separated from data state.

### Assuming every rollback is safe

Dropping a column, deleting data, or reversing a transformation may be irreversible. A rollback function should reflect actual recoverability.

### Running migrations without history

Without durable history, the deployment process cannot reliably distinguish an already-applied migration from a pending one.

### Treating migration success as equivalent to application compatibility

A database can successfully execute a migration while an older application version still expects the previous schema. Deployment sequencing must account for both sides.

## Performance Considerations

Migration performance depends on the database engine, table size, indexes, constraints, locks, and amount of data affected.

Adding a column can be inexpensive in one database configuration and expensive in another.

Creating an index over a large table can consume substantial CPU, memory, and I/O and may affect concurrent workloads.

A data migration that updates millions of rows can hold locks or generate significant write activity.

The PostgreSQL history table records `execution_ms` so operational queries can identify migrations that take longer than expected.

For large production systems, migration design should consider lock duration, transaction size, index construction behavior, backfill strategy, replication effects, and maintenance windows.

## Production Considerations

A production migration process should establish a clear contract between migration source and database history.

Migration versions should be unique.

Applied migrations should be immutable.

Migration execution should be observable.

Failed migrations should leave the database in a known state whenever transactional behavior permits.

Destructive operations should receive stronger review than additive changes.

Long-running data transformations should be evaluated separately from small structural changes.

Schema compatibility should be considered across application deployment boundaries.

A migration history table should be protected from casual application writes because it is part of the deployment control plane.

Migration files should be version controlled alongside the application code that depends on the resulting schema.

## Relationship Between the Six Implementations

The implementations deliberately use different perspectives.

| Implementation | Primary technical perspective |
|---|---|
| Python | Practical migration runner using real SQLite transactions |
| JavaScript | Event-driven migration orchestration and lifecycle events |
| C++ | Schema deployment engine with explicit schema snapshots |
| Java | Enterprise domain model and migration service architecture |
| SQL | PostgreSQL schema evolution, constraints, indexes, transactions, and history |
| README | Technical interpretation of the mechanisms represented by the implementations |

The implementations share the migration lifecycle without becoming identical translations.

The Python program is closest to a usable small migration framework. The JavaScript program emphasizes Node.js event behavior. The C++ program models deployment state and schema snapshots explicitly. The Java program expresses the domain through enterprise-oriented abstractions. The SQL script demonstrates the actual database mechanisms that a migration engine ultimately controls.

The common principle is that schema evolution should be explicit, ordered, validated, and recorded rather than being an undocumented sequence of manual database edits.

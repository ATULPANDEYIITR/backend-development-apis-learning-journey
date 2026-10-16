"use strict";

/*
 * Database migration concepts represented as an event-driven Node.js model.
 *
 * The file deliberately uses an in-memory database abstraction so it can run
 * without third-party packages. The migration engine still models the
 * important production concerns: ordered versions, checksums, transactions,
 * schema evolution, migration history, rollback, drift detection, and
 * idempotent execution.
 */

const crypto = require("crypto");
const EventEmitter = require("events");

class MigrationError extends Error {
  constructor(message) {
    super(message);
    this.name = "MigrationError";
  }
}

class InMemoryDatabase {
  constructor() {
    this.tables = new Map();
    this.history = [];
    this.transactionSnapshot = null;
  }

  begin() {
    if (this.transactionSnapshot !== null) {
      throw new MigrationError("A transaction is already active.");
    }

    this.transactionSnapshot = {
      tables: structuredClone([...this.tables.entries()]),
      history: structuredClone(this.history),
    };
  }

  commit() {
    if (this.transactionSnapshot === null) {
      throw new MigrationError("No transaction is active.");
    }
    this.transactionSnapshot = null;
  }

  rollback() {
    if (this.transactionSnapshot === null) {
      throw new MigrationError("No transaction is active.");
    }

    this.tables = new Map(this.transactionSnapshot.tables);
    this.history = this.transactionSnapshot.history;
    this.transactionSnapshot = null;
  }

  createTable(name, columns) {
    if (this.tables.has(name)) {
      throw new MigrationError(`Table '${name}' already exists.`);
    }

    this.tables.set(name, {
      columns: [...columns],
      rows: [],
      indexes: [],
    });
  }

  dropTable(name) {
    if (!this.tables.has(name)) {
      throw new MigrationError(`Table '${name}' does not exist.`);
    }
    this.tables.delete(name);
  }

  addColumn(tableName, columnName, defaultValue = null) {
    const table = this.getTable(tableName);

    if (table.columns.includes(columnName)) {
      throw new MigrationError(
        `Column '${columnName}' already exists on '${tableName}'.`
      );
    }

    table.columns.push(columnName);

    for (const row of table.rows) {
      row[columnName] =
        typeof defaultValue === "function" ? defaultValue(row) : defaultValue;
    }
  }

  createIndex(tableName, indexName, columns, unique = false) {
    const table = this.getTable(tableName);

    if (table.indexes.some((index) => index.name === indexName)) {
      throw new MigrationError(`Index '${indexName}' already exists.`);
    }

    table.indexes.push({
      name: indexName,
      columns: [...columns],
      unique,
    });
  }

  insert(tableName, row) {
    const table = this.getTable(tableName);

    for (const column of table.columns) {
      if (!(column in row)) {
        row[column] = null;
      }
    }

    for (const index of table.indexes) {
      if (!index.unique) continue;

      const duplicate = table.rows.some((existing) =>
        index.columns.every(
          (column) => existing[column] === row[column]
        )
      );

      if (duplicate) {
        throw new MigrationError(
          `Unique index '${index.name}' rejected the inserted row.`
        );
      }
    }

    table.rows.push({ ...row });
  }

  update(tableName, predicate, updater) {
    const table = this.getTable(tableName);

    for (const row of table.rows) {
      if (predicate(row)) {
        updater(row);
      }
    }
  }

  getTable(name) {
    const table = this.tables.get(name);
    if (!table) {
      throw new MigrationError(`Table '${name}' does not exist.`);
    }
    return table;
  }

  describe() {
    return [...this.tables.entries()].map(([name, table]) => ({
      name,
      columns: [...table.columns],
      rows: table.rows.map((row) => ({ ...row })),
      indexes: table.indexes.map((index) => ({ ...index })),
    }));
  }
}

function migrationChecksum(migration) {
  return crypto
    .createHash("sha256")
    .update(
      JSON.stringify({
        version: migration.version,
        name: migration.name,
        implementation: migration.implementation,
      })
    )
    .digest("hex");
}

class MigrationRunner extends EventEmitter {
  constructor(database) {
    super();
    this.database = database;
  }

  validateHistory(migrations) {
    const definitions = new Map(
      migrations.map((migration) => [migration.version, migration])
    );

    for (const record of this.database.history) {
      const definition = definitions.get(record.version);

      if (!definition) {
        throw new MigrationError(
          `Migration ${record.version} exists in history but not in code.`
        );
      }

      const checksum = migrationChecksum(definition);

      if (record.checksum !== checksum) {
        throw new MigrationError(
          `Migration ${record.version} checksum differs from history.`
        );
      }
    }
  }

  migrate(migrations, target = Infinity) {
    const ordered = [...migrations].sort((a, b) => a.version - b.version);
    this.validateHistory(ordered);

    const applied = new Set(
      this.database.history.map((record) => record.version)
    );

    for (const migration of ordered) {
      if (migration.version > target || applied.has(migration.version)) {
        continue;
      }

      this.apply(migration);
    }
  }

  apply(migration) {
    this.database.begin();

    try {
      migration.up(this.database);

      this.database.history.push({
        version: migration.version,
        name: migration.name,
        checksum: migrationChecksum(migration),
        appliedAt: new Date().toISOString(),
      });

      this.database.commit();

      this.emit("migrationApplied", {
        version: migration.version,
        name: migration.name,
      });
    } catch (error) {
      this.database.rollback();

      this.emit("migrationFailed", {
        version: migration.version,
        name: migration.name,
        error,
      });

      throw new MigrationError(
        `Migration ${migration.version} failed and was rolled back: ${error.message}`
      );
    }
  }

  rollbackLast(migrations) {
    const last = this.database.history.at(-1);

    if (!last) {
      throw new MigrationError("There is no migration to roll back.");
    }

    const definition = migrations.find(
      (migration) => migration.version === last.version
    );

    if (!definition) {
      throw new MigrationError(
        `Rollback implementation for v${last.version} is unavailable.`
      );
    }

    this.database.begin();

    try {
      definition.down(this.database);

      this.database.history.pop();
      this.database.commit();

      this.emit("migrationRolledBack", {
        version: definition.version,
        name: definition.name,
      });
    } catch (error) {
      this.database.rollback();
      throw new MigrationError(
        `Rollback of v${definition.version} failed: ${error.message}`
      );
    }
  }
}

const migrations = [
  {
    version: 1,
    name: "create_accounts",
    implementation: "create_accounts_v1",
    up(db) {
      db.createTable("accounts", ["id", "email", "displayName"]);
      db.createIndex("accounts", "ux_accounts_email", ["email"], true);
    },
    down(db) {
      db.dropTable("accounts");
    },
  },
  {
    version: 2,
    name: "add_account_status",
    implementation: "add_account_status_v2",
    up(db) {
      db.addColumn("accounts", "status", "active");
    },
    down(db) {
      const table = db.getTable("accounts");
      table.columns = table.columns.filter((column) => column !== "status");

      for (const row of table.rows) {
        delete row.status;
      }
    },
  },
  {
    version: 3,
    name: "create_audit_events",
    implementation: "create_audit_events_v3",
    up(db) {
      db.createTable("audit_events", [
        "id",
        "accountId",
        "eventType",
        "occurredAt",
      ]);
      db.createIndex(
        "audit_events",
        "ix_audit_account",
        ["accountId"],
        false
      );
    },
    down(db) {
      db.dropTable("audit_events");
    },
  },
  {
    version: 4,
    name: "normalize_display_names",
    implementation: "normalize_display_names_v4",
    up(db) {
      db.update("accounts", () => true, (account) => {
        account.displayName = account.displayName.trim().replace(/\s+/g, " ");
      });
    },
    down(db) {
      // Normalization is irreversible because original whitespace is lost.
    },
  },
  {
    version: 5,
    name: "add_external_identity",
    implementation: "add_external_identity_v5",
    up(db) {
      db.addColumn("accounts", "externalId", null);
      db.createIndex(
        "accounts",
        "ux_accounts_external_id",
        ["externalId"],
        true
      );
    },
    down(db) {
      const table = db.getTable("accounts");
      table.columns = table.columns.filter((column) => column !== "externalId");

      for (const row of table.rows) {
        delete row.externalId;
      }

      table.indexes = table.indexes.filter(
        (index) => index.name !== "ux_accounts_external_id"
      );
    },
  },
];

function seedData(db) {
  db.insert("accounts", {
    id: 1,
    email: "ada@example.com",
    displayName: "  Ada   Lovelace ",
    status: "active",
    externalId: "EXT-001",
  });

  db.insert("accounts", {
    id: 2,
    email: "grace@example.com",
    displayName: "Grace Hopper",
    status: "active",
    externalId: "EXT-002",
  });

  db.insert("audit_events", {
    id: 100,
    accountId: 1,
    eventType: "account_created",
    occurredAt: "2026-10-16T08:00:00Z",
  });
}

function demonstrateFailure(runner, db) {
  const failingMigration = {
    version: 99,
    name: "simulate_deployment_failure",
    implementation: "failure_v99",
    up(database) {
      database.createTable("temporary_table", ["id"]);
      throw new Error("Application validation failed after DDL.");
    },
    down(database) {
      database.dropTable("temporary_table");
    },
  };

  const historyBefore = structuredClone(db.history);

  try {
    runner.migrate([...migrations, failingMigration]);
  } catch (error) {
    console.log(`Expected failure: ${error.message}`);
  }

  const historyUnchanged =
    JSON.stringify(historyBefore) === JSON.stringify(db.history);

  console.log(`History unchanged: ${historyUnchanged}`);
  console.log(
    `Temporary table exists: ${db.tables.has("temporary_table")}`
  );
}

function demonstrateDriftDetection(runner) {
  const modified = migrations.map((migration) => ({ ...migration }));

  modified[1] = {
    ...modified[1],
    implementation: "modified_after_production_deployment",
  };

  try {
    runner.validateHistory(modified);
  } catch (error) {
    console.log(`Drift detected: ${error.message}`);
  }
}

function main() {
  const db = new InMemoryDatabase();
  const runner = new MigrationRunner(db);

  runner.on("migrationApplied", ({ version, name }) => {
    console.log(`Applied v${version}: ${name}`);
  });

  runner.on("migrationFailed", ({ version, error }) => {
    console.log(`Migration v${version} failed: ${error.message}`);
  });

  runner.on("migrationRolledBack", ({ version, name }) => {
    console.log(`Rolled back v${version}: ${name}`);
  });

  console.log("Applying migrations...");
  runner.migrate(migrations);

  console.log("\nSeeding evolved schema...");
  seedData(db);

  console.log("\nMigration history:");
  console.table(db.history);

  console.log("\nSchema:");
  console.dir(db.describe(), { depth: null });

  demonstrateFailure(runner, db);
  demonstrateDriftDetection(runner);

  console.log("\nRolling back the latest migration...");
  runner.rollbackLast(migrations);
  console.table(db.history);

  console.log("\nRe-applying the migration...");
  runner.migrate(migrations);
  console.table(db.history);
}

main();

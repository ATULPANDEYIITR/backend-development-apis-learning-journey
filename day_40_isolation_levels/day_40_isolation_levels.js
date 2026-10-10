"use strict";

/*
 * Transaction Isolation Laboratory
 *
 * This Node.js program uses an event-driven transaction scheduler to show
 * why isolation level is a concurrency policy rather than merely a label.
 *
 * The simulator intentionally models dirty reads for READ UNCOMMITTED so that
 * the ANSI anomaly can be observed. PostgreSQL itself treats READ UNCOMMITTED
 * as READ COMMITTED.
 */

const IsolationLevel = Object.freeze({
    READ_UNCOMMITTED: "READ UNCOMMITTED",
    READ_COMMITTED: "READ COMMITTED",
    REPEATABLE_READ: "REPEATABLE READ",
    SERIALIZABLE: "SERIALIZABLE"
});

const TransactionState = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

class SerializationFailure extends Error {
    constructor(message) {
        super(message);
        this.name = "SerializationFailure";
    }
}

class Transaction {
    constructor(id, isolation, snapshot) {
        this.id = id;
        this.isolation = isolation;
        this.snapshot = new Map(snapshot);
        this.writes = new Map();
        this.readSet = new Set();
        this.writeSet = new Set();
        this.state = TransactionState.ACTIVE;
    }
}

class TransactionDatabase {
    constructor(initialRows) {
        this.rows = new Map(initialRows);
        this.committed = new Map(initialRows);
        this.transactions = new Map();
        this.nextTransactionId = 1;
    }

    begin(isolation) {
        const transaction = new Transaction(
            this.nextTransactionId++,
            isolation,
            this.committed
        );

        this.transactions.set(transaction.id, transaction);
        return transaction;
    }

    requireActive(transaction) {
        if (transaction.state !== TransactionState.ACTIVE) {
            throw new Error(
                `Transaction ${transaction.id} is ${transaction.state}`
            );
        }
    }

    read(transaction, key) {
        this.requireActive(transaction);

        if (!this.rows.has(key)) {
            throw new Error(`Unknown row: ${key}`);
        }

        transaction.readSet.add(key);

        if (transaction.writes.has(key)) {
            return transaction.writes.get(key);
        }

        if (transaction.isolation === IsolationLevel.READ_UNCOMMITTED) {
            for (const other of this.transactions.values()) {
                if (
                    other.id !== transaction.id &&
                    other.state === TransactionState.ACTIVE &&
                    other.writes.has(key)
                ) {
                    return other.writes.get(key);
                }
            }
        }

        if (transaction.isolation === IsolationLevel.READ_COMMITTED) {
            return this.committed.get(key);
        }

        return transaction.snapshot.get(key);
    }

    write(transaction, key, value) {
        this.requireActive(transaction);

        if (!this.rows.has(key)) {
            throw new Error(`Unknown row: ${key}`);
        }

        if (!Number.isInteger(value) || value < 0) {
            throw new Error("Balance must be a non-negative integer");
        }

        transaction.writes.set(key, value);
        transaction.writeSet.add(key);
    }

    increment(transaction, key, amount) {
        if (!Number.isInteger(amount)) {
            throw new TypeError("Increment must be an integer");
        }

        const current = this.read(transaction, key);
        this.write(transaction, key, current + amount);
    }

    commit(transaction) {
        this.requireActive(transaction);

        if (
            transaction.isolation === IsolationLevel.REPEATABLE_READ ||
            transaction.isolation === IsolationLevel.SERIALIZABLE
        ) {
            this.validateSnapshot(transaction);
        }

        for (const [key, value] of transaction.writes) {
            this.committed.set(key, value);
            this.rows.set(key, value);
        }

        transaction.state = TransactionState.COMMITTED;
    }

    validateSnapshot(transaction) {
        const keys =
            transaction.isolation === IsolationLevel.SERIALIZABLE
                ? new Set([
                    ...transaction.readSet,
                    ...transaction.writeSet
                ])
                : transaction.writeSet;

        for (const key of keys) {
            const original = transaction.snapshot.get(key);
            const current = this.committed.get(key);

            if (original !== current) {
                throw new SerializationFailure(
                    `Concurrent modification detected for ${key}: ` +
                    `snapshot=${original}, current=${current}`
                );
            }
        }
    }

    rollback(transaction) {
        this.requireActive(transaction);
        transaction.writes.clear();
        transaction.state = TransactionState.ABORTED;
    }

    state() {
        return Object.fromEntries(this.committed.entries());
    }
}

function delay(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function dirtyReadDemo() {
    console.log("\n=== Dirty Read ===");

    const db = new TransactionDatabase([
        ["account:Asha", 1000]
    ]);

    const writer = db.begin(IsolationLevel.READ_COMMITTED);
    const reader = db.begin(IsolationLevel.READ_UNCOMMITTED);

    db.write(writer, "account:Asha", 250);

    const uncommitted = db.read(reader, "account:Asha");
    console.log(`Reader sees uncommitted value: ${uncommitted}`);

    db.rollback(writer);

    const afterRollback = db.read(reader, "account:Asha");
    console.log(`Reader sees after rollback: ${afterRollback}`);

    db.rollback(reader);
}

async function readCommittedDemo() {
    console.log("\n=== READ COMMITTED ===");

    const db = new TransactionDatabase([
        ["account:Asha", 1000]
    ]);

    const reader = db.begin(IsolationLevel.READ_COMMITTED);
    const writer = db.begin(IsolationLevel.READ_COMMITTED);

    const firstRead = db.read(reader, "account:Asha");

    await delay(10);

    db.write(writer, "account:Asha", 1400);
    db.commit(writer);

    const secondRead = db.read(reader, "account:Asha");

    console.log({
        isolation: reader.isolation,
        firstRead,
        secondRead,
        nonRepeatableRead: firstRead !== secondRead
    });

    db.rollback(reader);
}

async function repeatableReadDemo() {
    console.log("\n=== REPEATABLE READ ===");

    const db = new TransactionDatabase([
        ["account:Asha", 1000]
    ]);

    const reader = db.begin(IsolationLevel.REPEATABLE_READ);
    const writer = db.begin(IsolationLevel.READ_COMMITTED);

    const firstRead = db.read(reader, "account:Asha");

    db.write(writer, "account:Asha", 1700);
    db.commit(writer);

    const secondRead = db.read(reader, "account:Asha");

    console.log({
        isolation: reader.isolation,
        firstRead,
        secondRead,
        stableSnapshot: firstRead === secondRead
    });

    db.rollback(reader);
}

async function serializableDemo() {
    console.log("\n=== SERIALIZABLE ===");

    const db = new TransactionDatabase([
        ["account:Asha", 1000],
        ["account:Bharat", 1000]
    ]);

    const transactionA = db.begin(IsolationLevel.SERIALIZABLE);
    const transactionB = db.begin(IsolationLevel.SERIALIZABLE);

    const observedTotal =
        db.read(transactionA, "account:Asha") +
        db.read(transactionA, "account:Bharat");

    db.increment(transactionB, "account:Asha", 500);
    db.commit(transactionB);

    db.write(transactionA, "account:Bharat", 2000);

    try {
        db.commit(transactionA);
    } catch (error) {
        if (error instanceof SerializationFailure) {
            transactionA.state = TransactionState.ABORTED;
            console.log(`Serialization failure: ${error.message}`);
        } else {
            throw error;
        }
    }

    console.log({
        observedTotal,
        finalState: db.state()
    });
}

class RepositoryTransactionService {
    constructor(database) {
        this.database = database;
    }

    async transfer(source, destination, amount) {
        if (!Number.isInteger(amount) || amount <= 0) {
            throw new RangeError("Transfer amount must be positive");
        }

        if (source === destination) {
            throw new Error("Source and destination must differ");
        }

        const transaction = this.database.begin(
            IsolationLevel.SERIALIZABLE
        );

        try {
            const sourceBalance = this.database.read(
                transaction,
                source
            );

            const destinationBalance = this.database.read(
                transaction,
                destination
            );

            if (sourceBalance < amount) {
                throw new Error("Insufficient funds");
            }

            this.database.write(
                transaction,
                source,
                sourceBalance - amount
            );

            this.database.write(
                transaction,
                destination,
                destinationBalance + amount
            );

            this.database.commit(transaction);

            return {
                transactionId: transaction.id,
                state: transaction.state
            };
        } catch (error) {
            if (transaction.state === TransactionState.ACTIVE) {
                this.database.rollback(transaction);
            }

            throw error;
        }
    }
}

async function concurrentTransferDemo() {
    console.log("\n=== Event-Driven Serializable Service ===");

    const db = new TransactionDatabase([
        ["account:Asha", 1000],
        ["account:Bharat", 500]
    ]);

    const service = new RepositoryTransactionService(db);

    const result = await service.transfer(
        "account:Asha",
        "account:Bharat",
        250
    );

    console.log(result);
    console.log("Balances:", db.state());
}

function explainPostgresqlBehavior() {
    console.log("\n=== PostgreSQL Semantics ===");
    console.log(
        "READ UNCOMMITTED is accepted by PostgreSQL but behaves as READ COMMITTED."
    );
    console.log(
        "READ COMMITTED uses a fresh statement snapshot for each statement."
    );
    console.log(
        "REPEATABLE READ maintains a transaction-level consistent snapshot."
    );
    console.log(
        "SERIALIZABLE may abort a transaction when concurrent execution "
        + "cannot be represented by a serial order."
    );
}

async function main() {
    console.log("Transaction Isolation Level Laboratory");

    explainPostgresqlBehavior();

    await dirtyReadDemo();
    await readCommittedDemo();
    await repeatableReadDemo();
    await serializableDemo();
    await concurrentTransferDemo();

    console.log("\n=== Production Considerations ===");
    console.log(
        "Keep transactions short to reduce lock contention and snapshot lifetime."
    );
    console.log(
        "Retry transient serialization failures with bounded backoff."
    );
    console.log(
        "Do not confuse application validation with database isolation: "
        + "both are required when concurrent writes can violate invariants."
    );
}

main().catch(error => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});

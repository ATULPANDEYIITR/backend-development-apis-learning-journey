"use strict";

/*
 * transactions_acid.js
 *
 * A transaction-focused JavaScript implementation using Node.js and the
 * built-in in-memory domain model. The program demonstrates transaction
 * boundaries, atomicity, consistency, rollback behavior, savepoints,
 * asynchronous transaction execution, and concurrent transaction reasoning.
 *
 * No npm dependencies are required.
 */

class TransactionError extends Error {
    constructor(message) {
        super(message);
        this.name = "TransactionError";
    }
}

class ConstraintError extends TransactionError {
    constructor(message) {
        super(message);
        this.name = "ConstraintError";
    }
}

class Account {
    constructor(id, owner, balanceCents) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new ConstraintError("Account ID must be a positive integer.");
        }

        if (!Number.isInteger(balanceCents) || balanceCents < 0) {
            throw new ConstraintError("Account balance cannot be negative.");
        }

        this.id = id;
        this.owner = owner;
        this.balanceCents = balanceCents;
        this.active = true;
    }

    clone() {
        const copy = new Account(this.id, this.owner, this.balanceCents);
        copy.active = this.active;
        return copy;
    }
}

class Transaction {
    constructor(database, reference) {
        this.database = database;
        this.reference = reference;
        this.snapshot = database.snapshot();
        this.active = true;
        this.savepoints = new Map();
    }

    assertActive() {
        if (!this.active) {
            throw new TransactionError(
                `Transaction ${this.reference} is no longer active.`
            );
        }
    }

    account(id) {
        this.assertActive();

        const account = this.database.accounts.get(id);

        if (!account) {
            throw new ConstraintError(`Account ${id} does not exist.`);
        }

        if (!account.active) {
            throw new ConstraintError(`Account ${id} is inactive.`);
        }

        return account;
    }

    deposit(id, amountCents) {
        this.assertActive();

        if (!Number.isSafeInteger(amountCents) || amountCents <= 0) {
            throw new ConstraintError("Deposit amount must be a positive integer number of cents.");
        }

        const account = this.account(id);
        account.balanceCents += amountCents;

        this.database.ledger.push({
            accountId: id,
            type: "DEPOSIT",
            amountCents,
            reference: this.reference
        });
    }

    withdraw(id, amountCents) {
        this.assertActive();

        if (!Number.isSafeInteger(amountCents) || amountCents <= 0) {
            throw new ConstraintError("Withdrawal amount must be positive.");
        }

        const account = this.account(id);

        if (account.balanceCents < amountCents) {
            throw new ConstraintError(
                `Insufficient funds in account ${id}.`
            );
        }

        account.balanceCents -= amountCents;

        this.database.ledger.push({
            accountId: id,
            type: "WITHDRAWAL",
            amountCents,
            reference: this.reference
        });
    }

    transfer(sourceId, targetId, amountCents) {
        this.assertActive();

        if (sourceId === targetId) {
            throw new ConstraintError(
                "Source and target accounts must differ."
            );
        }

        if (!Number.isSafeInteger(amountCents) || amountCents <= 0) {
            throw new ConstraintError("Transfer amount must be positive.");
        }

        const source = this.account(sourceId);
        const target = this.account(targetId);

        if (source.balanceCents < amountCents) {
            throw new ConstraintError("Transfer would overdraw the source account.");
        }

        source.balanceCents -= amountCents;
        target.balanceCents += amountCents;

        this.database.ledger.push(
            {
                accountId: sourceId,
                type: "TRANSFER_OUT",
                amountCents,
                reference: this.reference
            },
            {
                accountId: targetId,
                type: "TRANSFER_IN",
                amountCents,
                reference: this.reference
            }
        );
    }

    savepoint(name) {
        this.assertActive();
        this.savepoints.set(name, this.database.snapshot());
    }

    rollbackToSavepoint(name) {
        this.assertActive();

        if (!this.savepoints.has(name)) {
            throw new TransactionError(`Unknown savepoint: ${name}`);
        }

        this.database.restore(this.savepoints.get(name));

        // Savepoints created after this one are no longer valid.
        for (const savepointName of this.savepoints.keys()) {
            if (savepointName !== name) {
                this.savepoints.delete(savepointName);
            }
        }
    }

    releaseSavepoint(name) {
        this.assertActive();
        this.savepoints.delete(name);
    }

    commit() {
        this.assertActive();

        this.database.validateConsistency();
        this.active = false;

        return {
            reference: this.reference,
            status: "COMMITTED"
        };
    }

    rollback() {
        this.assertActive();

        this.database.restore(this.snapshot);
        this.active = false;

        return {
            reference: this.reference,
            status: "ROLLED_BACK"
        };
    }
}

class Database {
    constructor() {
        this.accounts = new Map();
        this.ledger = [];
        this.locked = false;
    }

    addAccount(id, owner, balanceCents) {
        if (this.accounts.has(id)) {
            throw new ConstraintError(`Account ${id} already exists.`);
        }

        this.accounts.set(id, new Account(id, owner, balanceCents));
    }

    snapshot() {
        return {
            accounts: new Map(
                [...this.accounts.entries()].map(
                    ([id, account]) => [id, account.clone()]
                )
            ),
            ledger: this.ledger.map(entry => ({ ...entry }))
        };
    }

    restore(snapshot) {
        this.accounts = new Map(
            [...snapshot.accounts.entries()].map(
                ([id, account]) => [id, account.clone()]
            )
        );

        this.ledger = snapshot.ledger.map(entry => ({ ...entry }));
    }

    validateConsistency() {
        for (const account of this.accounts.values()) {
            if (account.balanceCents < 0) {
                throw new ConstraintError(
                    `Consistency violation: account ${account.id} has negative balance.`
                );
            }
        }

        for (const entry of this.ledger) {
            if (!this.accounts.has(entry.accountId)) {
                throw new ConstraintError(
                    `Ledger entry references missing account ${entry.accountId}.`
                );
            }

            if (entry.amountCents <= 0) {
                throw new ConstraintError(
                    "Ledger amount must be positive."
                );
            }
        }
    }

    begin(reference) {
        if (this.locked) {
            throw new TransactionError(
                "A write transaction is already active."
            );
        }

        this.locked = true;

        const transaction = new Transaction(this, reference);

        const originalCommit = transaction.commit.bind(transaction);
        const originalRollback = transaction.rollback.bind(transaction);

        transaction.commit = () => {
            try {
                return originalCommit();
            } finally {
                this.locked = false;
            }
        };

        transaction.rollback = () => {
            try {
                return originalRollback();
            } finally {
                this.locked = false;
            }
        };

        return transaction;
    }

    printAccounts(title) {
        console.log(`\n--- ${title} ---`);

        for (const account of this.accounts.values()) {
            console.log(
                `${account.id} ${account.owner.padEnd(8)} ` +
                `${(account.balanceCents / 100).toFixed(2)} ` +
                `active=${account.active}`
            );
        }
    }

    printLedger() {
        console.log("\n--- Ledger ---");

        for (const entry of this.ledger) {
            console.log(
                `${entry.reference} ${entry.type} ` +
                `account=${entry.accountId} amount=${entry.amountCents / 100}`
            );
        }
    }
}

function runTransaction(database, reference, operation) {
    const transaction = database.begin(reference);

    try {
        operation(transaction);
        return transaction.commit();
    } catch (error) {
        transaction.rollback();
        return {
            reference,
            status: "ROLLED_BACK",
            reason: error.message
        };
    }
}

async function runAsyncTransaction(database, reference, operation) {
    const transaction = database.begin(reference);

    try {
        await operation(transaction);
        return transaction.commit();
    } catch (error) {
        transaction.rollback();

        return {
            reference,
            status: "ROLLED_BACK",
            reason: error.message
        };
    }
}

function demonstrateAtomicity(database) {
    console.log("\nAtomicity demonstration");

    const before = database.accounts.get(101).balanceCents;

    const result = runTransaction(
        database,
        "ATOMICITY-001",
        transaction => {
            transaction.withdraw(101, 10000);

            // The second operation fails. The first operation must disappear
            // because both operations belong to the same transaction.
            transaction.withdraw(101, 999999999);
        }
    );

    const after = database.accounts.get(101).balanceCents;

    console.log(result);
    console.log(`Balance before: ${before / 100}`);
    console.log(`Balance after : ${after / 100}`);
}

function demonstrateConsistency(database) {
    console.log("\nConsistency demonstration");

    const result = runTransaction(
        database,
        "CONSISTENCY-001",
        transaction => {
            transaction.withdraw(101, 5000);

            // The transaction itself still contains valid data. The explicit
            // validation before commit verifies the invariant.
            database.validateConsistency();
        }
    );

    console.log(result);

    try {
        const account = database.accounts.get(102);
        account.balanceCents = -1;
        database.validateConsistency();
    } catch (error) {
        console.log(`Expected consistency failure: ${error.message}`);
        database.accounts.get(102).balanceCents = 50000;
    }
}

function demonstrateSavepoint(database) {
    console.log("\nSavepoint demonstration");

    const result = runTransaction(
        database,
        "SAVEPOINT-001",
        transaction => {
            transaction.deposit(103, 5000);

            transaction.savepoint("optional-work");

            try {
                transaction.withdraw(101, 999999999);
            } catch (error) {
                console.log(`Optional operation failed: ${error.message}`);
                transaction.rollbackToSavepoint("optional-work");
            }

            transaction.releaseSavepoint("optional-work");

            // The valid deposit remains part of the outer transaction.
        }
    );

    console.log(result);
}

function demonstrateFailedTransfer(database) {
    console.log("\nFailed transfer demonstration");

    const sourceBefore = database.accounts.get(101).balanceCents;
    const targetBefore = database.accounts.get(102).balanceCents;

    const result = runTransaction(
        database,
        "TRANSFER-FAILED",
        transaction => {
            transaction.withdraw(101, 10000);

            // Simulate a failure before the corresponding credit.
            throw new TransactionError(
                "Destination service became unavailable."
            );
        }
    );

    console.log(result);

    const sourceAfter = database.accounts.get(101).balanceCents;
    const targetAfter = database.accounts.get(102).balanceCents;

    console.log(
        `Source restored: ${sourceBefore === sourceAfter}`
    );
    console.log(
        `Target unchanged: ${targetBefore === targetAfter}`
    );
}

async function demonstrateAsyncWorkflow(database) {
    console.log("\nAsynchronous transaction demonstration");

    const result = await runAsyncTransaction(
        database,
        "ASYNC-001",
        async transaction => {
            transaction.transfer(101, 102, 7500);

            // An awaited operation represents work such as an external
            // validation call. A production system should avoid holding
            // database locks during slow network calls.
            await new Promise(resolve => setTimeout(resolve, 20));
        }
    );

    console.log(result);
}

async function demonstrateConcurrentWriters(database) {
    console.log("\nConcurrent writer demonstration");

    const first = runAsyncTransaction(
        database,
        "CONCURRENT-A",
        async transaction => {
            transaction.transfer(101, 103, 1000);
            await new Promise(resolve => setTimeout(resolve, 50));
        }
    );

    let second;

    try {
        second = runAsyncTransaction(
            database,
            "CONCURRENT-B",
            async transaction => {
                transaction.transfer(102, 103, 1000);
            }
        );
    } catch (error) {
        second = Promise.resolve({
            status: "REJECTED",
            reason: error.message
        });
    }

    console.log(await Promise.all([first, second]));
}

async function main() {
    const database = new Database();

    database.addAccount(101, "Asha", 100000);
    database.addAccount(102, "Ravi", 50000);
    database.addAccount(103, "Meera", 0);

    database.printAccounts("Initial state");

    const successfulTransfer = runTransaction(
        database,
        "TRANSFER-001",
        transaction => {
            transaction.transfer(101, 102, 12550);
        }
    );

    console.log("\nSuccessful transaction:");
    console.log(successfulTransfer);

    demonstrateAtomicity(database);
    demonstrateConsistency(database);
    demonstrateSavepoint(database);
    demonstrateFailedTransfer(database);
    await demonstrateAsyncWorkflow(database);
    await demonstrateConcurrentWriters(database);

    database.printAccounts("Final state");
    database.printLedger();

    console.log("\nACID interpretation:");
    console.log("Atomicity: a transaction is committed as one unit or rolled back.");
    console.log("Consistency: domain invariants are validated before commit.");
    console.log("Isolation: active write transactions are serialized by the model.");
    console.log("Durability: a real database must persist committed state to stable storage.");
}

main().catch(error => {
    console.error("Fatal transaction-system error:", error);
    process.exitCode = 1;
});

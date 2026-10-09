/*
 * transactions_acid.cpp
 *
 * C++17 technical case study:
 * A repository-independent banking transaction engine used to demonstrate
 * transaction boundaries and the four ACID properties.
 *
 * The case study models:
 * - BEGIN
 * - COMMIT
 * - ROLLBACK
 * - SAVEPOINT-style partial rollback
 * - Atomic transfers
 * - Consistency invariants
 * - Transaction locking
 * - Failure recovery
 * - Audit records
 * - Merge-like state validation before durable commitment
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic transactions_acid.cpp -o transactions_acid
 */

#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using Cents = std::int64_t;

class TransactionError : public std::runtime_error {
public:
    explicit TransactionError(const std::string& message)
        : std::runtime_error(message) {}
};

class ConsistencyError : public TransactionError {
public:
    explicit ConsistencyError(const std::string& message)
        : TransactionError(message) {}
};

struct Account {
    int id;
    std::string owner;
    Cents balance;
    bool active;

    Account(int id_, std::string owner_, Cents balance_)
        : id(id_), owner(std::move(owner_)), balance(balance_), active(true) {
        if (id <= 0) {
            throw ConsistencyError("Account ID must be positive.");
        }

        if (balance < 0) {
            throw ConsistencyError("Initial account balance cannot be negative.");
        }
    }
};

struct LedgerEntry {
    std::string reference;
    int accountId;
    std::string type;
    Cents amount;
};

struct DatabaseState {
    std::map<int, Account> accounts;
    std::vector<LedgerEntry> ledger;
};

class Database {
private:
    DatabaseState state_;
    bool writeTransactionActive_{false};

public:
    Database() = default;

    void addAccount(int id, const std::string& owner, Cents balance) {
        if (state_.accounts.contains(id)) {
            throw ConsistencyError("Duplicate account ID: " + std::to_string(id));
        }

        state_.accounts.emplace(id, Account(id, owner, balance));
    }

    Account& account(int id) {
        auto it = state_.accounts.find(id);

        if (it == state_.accounts.end()) {
            throw ConsistencyError("Account does not exist: " + std::to_string(id));
        }

        if (!it->second.active) {
            throw ConsistencyError("Account is inactive: " + std::to_string(id));
        }

        return it->second;
    }

    const Account& account(int id) const {
        auto it = state_.accounts.find(id);

        if (it == state_.accounts.end()) {
            throw ConsistencyError("Account does not exist: " + std::to_string(id));
        }

        return it->second;
    }

    DatabaseState snapshot() const {
        return state_;
    }

    void restore(const DatabaseState& snapshot) {
        state_ = snapshot;
    }

    void validateConsistency() const {
        for (const auto& [id, account] : state_.accounts) {
            if (id <= 0) {
                throw ConsistencyError("Account identifier invariant violated.");
            }

            if (account.balance < 0) {
                throw ConsistencyError(
                    "Negative balance detected for account " +
                    std::to_string(id)
                );
            }
        }

        for (const auto& entry : state_.ledger) {
            if (!state_.accounts.contains(entry.accountId)) {
                throw ConsistencyError("Ledger references an unknown account.");
            }

            if (entry.amount <= 0) {
                throw ConsistencyError("Ledger amount must be positive.");
            }
        }
    }

    bool transactionActive() const {
        return writeTransactionActive_;
    }

    void lockTransaction() {
        if (writeTransactionActive_) {
            throw TransactionError("Another write transaction is already active.");
        }

        writeTransactionActive_ = true;
    }

    void unlockTransaction() {
        writeTransactionActive_ = false;
    }

    void printAccounts(const std::string& title) const {
        std::cout << "\n--- " << title << " ---\n";

        for (const auto& [id, account] : state_.accounts) {
            std::cout << id
                      << " " << std::left << std::setw(8) << account.owner
                      << " balance=" << std::fixed << std::setprecision(2)
                      << static_cast<double>(account.balance) / 100.0
                      << " active=" << std::boolalpha << account.active
                      << '\n';
        }
    }

    void printLedger() const {
        std::cout << "\n--- Ledger ---\n";

        for (const auto& entry : state_.ledger) {
            std::cout << entry.reference
                      << " account=" << entry.accountId
                      << " type=" << entry.type
                      << " amount=" << std::fixed << std::setprecision(2)
                      << static_cast<double>(entry.amount) / 100.0
                      << '\n';
        }
    }

    class Transaction;

    Transaction begin(const std::string& reference);
};

class Database::Transaction {
private:
    Database& database_;
    DatabaseState original_;
    std::string reference_;
    bool active_{true};
    std::map<std::string, DatabaseState> savepoints_;

    void requireActive() const {
        if (!active_) {
            throw TransactionError("Transaction is no longer active.");
        }
    }

public:
    Transaction(
        Database& database,
        DatabaseState original,
        std::string reference
    )
        : database_(database),
          original_(std::move(original)),
          reference_(std::move(reference)) {}

    Transaction(const Transaction&) = delete;
    Transaction& operator=(const Transaction&) = delete;

    Transaction(Transaction&& other) noexcept
        : database_(other.database_),
          original_(std::move(other.original_)),
          reference_(std::move(other.reference_)),
          active_(other.active_),
          savepoints_(std::move(other.savepoints_)) {
        other.active_ = false;
    }

    ~Transaction() {
        /*
         * RAII provides a safety net: if application code leaves scope without
         * explicitly committing, an active transaction is rolled back.
         */
        if (active_) {
            database_.restore(original_);
            database_.unlockTransaction();
        }
    }

    Account& account(int id) {
        requireActive();
        return database_.account(id);
    }

    void deposit(int id, Cents amount) {
        requireActive();

        if (amount <= 0) {
            throw ConsistencyError("Deposit amount must be positive.");
        }

        Account& target = account(id);
        target.balance += amount;

        database_.state_.ledger.push_back(
            {reference_, id, "DEPOSIT", amount}
        );
    }

    void withdraw(int id, Cents amount) {
        requireActive();

        if (amount <= 0) {
            throw ConsistencyError("Withdrawal amount must be positive.");
        }

        Account& source = account(id);

        if (source.balance < amount) {
            throw TransactionError(
                "Insufficient funds in account " + std::to_string(id)
            );
        }

        source.balance -= amount;

        database_.state_.ledger.push_back(
            {reference_, id, "WITHDRAWAL", amount}
        );
    }

    void transfer(int sourceId, int targetId, Cents amount) {
        requireActive();

        if (sourceId == targetId) {
            throw ConsistencyError(
                "A transfer cannot use the same source and target."
            );
        }

        if (amount <= 0) {
            throw ConsistencyError("Transfer amount must be positive.");
        }

        Account& source = account(sourceId);
        Account& target = account(targetId);

        if (source.balance < amount) {
            throw TransactionError("Insufficient funds for transfer.");
        }

        source.balance -= amount;
        target.balance += amount;

        database_.state_.ledger.push_back(
            {reference_, sourceId, "TRANSFER_OUT", amount}
        );

        database_.state_.ledger.push_back(
            {reference_, targetId, "TRANSFER_IN", amount}
        );
    }

    void savepoint(const std::string& name) {
        requireActive();

        if (name.empty()) {
            throw TransactionError("Savepoint name cannot be empty.");
        }

        savepoints_[name] = database_.snapshot();
    }

    void rollbackToSavepoint(const std::string& name) {
        requireActive();

        auto it = savepoints_.find(name);

        if (it == savepoints_.end()) {
            throw TransactionError("Savepoint does not exist: " + name);
        }

        database_.restore(it->second);
    }

    void releaseSavepoint(const std::string& name) {
        requireActive();
        savepoints_.erase(name);
    }

    void commit() {
        requireActive();

        database_.validateConsistency();

        active_ = false;
        database_.unlockTransaction();
    }

    void rollback() {
        requireActive();

        database_.restore(original_);
        active_ = false;
        database_.unlockTransaction();
    }
};

Database::Transaction Database::begin(const std::string& reference) {
    lockTransaction();

    try {
        return Transaction(*this, snapshot(), reference);
    } catch (...) {
        unlockTransaction();
        throw;
    }
}

template <typename Operation>
bool executeTransaction(
    Database& database,
    const std::string& reference,
    Operation operation
) {
    auto transaction = database.begin(reference);

    try {
        operation(transaction);
        transaction.commit();

        std::cout << "COMMIT: " << reference << '\n';
        return true;
    } catch (const std::exception& error) {
        transaction.rollback();

        std::cout << "ROLLBACK: " << reference
                  << " reason=" << error.what() << '\n';

        return false;
    }
}

void demonstrateAtomicTransfer(Database& database) {
    std::cout << "\nAtomic transfer case study\n";

    const Cents sourceBefore = database.account(101).balance;
    const Cents targetBefore = database.account(102).balance;

    executeTransaction(
        database,
        "TRF-001",
        [](Database::Transaction& transaction) {
            transaction.transfer(101, 102, 12550);
        }
    );

    const Cents sourceAfter = database.account(101).balance;
    const Cents targetAfter = database.account(102).balance;

    if (sourceAfter != sourceBefore - 12550 ||
        targetAfter != targetBefore + 12550) {
        throw ConsistencyError("Committed transfer invariant failed.");
    }
}

void demonstrateRollback(Database& database) {
    std::cout << "\nRollback case study\n";

    const Cents before = database.account(101).balance;

    executeTransaction(
        database,
        "TRF-FAILED",
        [](Database::Transaction& transaction) {
            transaction.withdraw(101, 5000);

            // Simulate a downstream failure after the debit.
            throw TransactionError(
                "Destination ledger service failed before credit."
            );
        }
    );

    const Cents after = database.account(101).balance;

    if (before != after) {
        throw ConsistencyError(
            "Rollback failed to restore the source account."
        );
    }
}

void demonstrateSavepoint(Database& database) {
    std::cout << "\nSavepoint case study\n";

    executeTransaction(
        database,
        "SAVEPOINT-001",
        [](Database::Transaction& transaction) {
            transaction.deposit(103, 2500);

            transaction.savepoint("optional");

            try {
                transaction.withdraw(101, 999999999);
            } catch (const TransactionError& error) {
                std::cout << "Optional operation failed: "
                          << error.what() << '\n';

                transaction.rollbackToSavepoint("optional");
            }

            transaction.releaseSavepoint("optional");

            // The outer transaction remains valid, so the deposit can commit.
        }
    );
}

void demonstrateConsistencyFailure(Database& database) {
    std::cout << "\nConsistency constraint case study\n";

    const Cents before = database.account(102).balance;

    executeTransaction(
        database,
        "CONSISTENCY-001",
        [](Database::Transaction& transaction) {
            Account& account = transaction.account(102);

            // Attempt to construct an invalid state.
            account.balance = -1;

            // Commit validates the invariant and must fail.
            transaction.commit();
        }
    );

    /*
     * The transaction's rollback restores the state that existed before the
     * invalid update.
     */
    if (database.account(102).balance != before) {
        throw ConsistencyError(
            "Consistency failure was not rolled back."
        );
    }
}

void demonstrateConcurrentWriterPolicy(Database& database) {
    std::cout << "\nConcurrent writer policy\n";

    auto transaction = database.begin("LOCK-001");

    try {
        try {
            auto secondTransaction = database.begin("LOCK-002");
            (void)secondTransaction;
        } catch (const TransactionError& error) {
            std::cout << "Second writer rejected: "
                      << error.what() << '\n';
        }

        transaction.rollback();
    } catch (...) {
        transaction.rollback();
        throw;
    }
}

int main() {
    try {
        Database database;

        database.addAccount(101, "Asha", 100000);
        database.addAccount(102, "Ravi", 50000);
        database.addAccount(103, "Meera", 0);

        database.printAccounts("Initial state");

        demonstrateAtomicTransfer(database);
        demonstrateRollback(database);
        demonstrateSavepoint(database);
        demonstrateConsistencyFailure(database);
        demonstrateConcurrentWriterPolicy(database);

        database.printAccounts("Final state");
        database.printLedger();

        std::cout << "\nACID interpretation\n";
        std::cout << "Atomicity: a transfer changes both accounts as one unit.\n";
        std::cout << "Consistency: invariants are checked before commitment.\n";
        std::cout << "Isolation: only one write transaction is active in this engine.\n";
        std::cout << "Durability: a production implementation must persist committed state.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}

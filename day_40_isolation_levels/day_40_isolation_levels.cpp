#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

enum class IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable
};

enum class TransactionState {
    Active,
    Committed,
    Aborted
};

std::string toString(IsolationLevel level) {
    switch (level) {
        case IsolationLevel::ReadUncommitted:
            return "READ UNCOMMITTED";
        case IsolationLevel::ReadCommitted:
            return "READ COMMITTED";
        case IsolationLevel::RepeatableRead:
            return "REPEATABLE READ";
        case IsolationLevel::Serializable:
            return "SERIALIZABLE";
    }
    return "UNKNOWN";
}

std::string toString(TransactionState state) {
    switch (state) {
        case TransactionState::Active:
            return "ACTIVE";
        case TransactionState::Committed:
            return "COMMITTED";
        case TransactionState::Aborted:
            return "ABORTED";
    }
    return "UNKNOWN";
}

class SerializationFailure : public std::runtime_error {
public:
    explicit SerializationFailure(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationFailure : public std::runtime_error {
public:
    explicit ValidationFailure(const std::string& message)
        : std::runtime_error(message) {}
};

struct Transaction {
    int id;
    IsolationLevel isolation;
    TransactionState state{TransactionState::Active};
    std::map<int, long long> snapshot;
    std::map<int, long long> writes;
    std::set<int> readSet;
    std::set<int> writeSet;
};

class GovernanceAwareDatabase {
private:
    std::map<int, long long> committedValues;
    std::map<int, long long> physicalValues;
    std::map<int, Transaction> transactions;
    int nextTransactionId{1};
    mutable std::mutex databaseMutex;

    long long currentCommitted(int accountId) const {
        auto iterator = committedValues.find(accountId);

        if (iterator == committedValues.end()) {
            throw ValidationFailure("Unknown account");
        }

        return iterator->second;
    }

    void requireActive(const Transaction& transaction) const {
        if (transaction.state != TransactionState::Active) {
            throw ValidationFailure(
                "Transaction is not active: " +
                toString(transaction.state)
            );
        }
    }

    void validateSerializable(Transaction& transaction) {
        std::set<int> observedKeys = transaction.readSet;

        observedKeys.insert(
            transaction.writeSet.begin(),
            transaction.writeSet.end()
        );

        for (int accountId : observedKeys) {
            long long snapshotValue = transaction.snapshot.at(accountId);
            long long currentValue = currentCommitted(accountId);

            if (snapshotValue != currentValue) {
                throw SerializationFailure(
                    "Serializable conflict on account " +
                    std::to_string(accountId) +
                    ": snapshot=" +
                    std::to_string(snapshotValue) +
                    ", current=" +
                    std::to_string(currentValue)
                );
            }
        }
    }

    void validateRepeatableRead(Transaction& transaction) {
        for (int accountId : transaction.writeSet) {
            long long snapshotValue = transaction.snapshot.at(accountId);
            long long currentValue = currentCommitted(accountId);

            if (snapshotValue != currentValue) {
                throw SerializationFailure(
                    "Repeatable-read write conflict on account " +
                    std::to_string(accountId)
                );
            }
        }
    }

public:
    explicit GovernanceAwareDatabase(
        const std::map<int, long long>& initialBalances
    )
        : committedValues(initialBalances),
          physicalValues(initialBalances) {}

    Transaction begin(IsolationLevel isolation) {
        std::lock_guard<std::mutex> lock(databaseMutex);

        Transaction transaction;
        transaction.id = nextTransactionId++;
        transaction.isolation = isolation;
        transaction.snapshot = committedValues;

        transactions.emplace(transaction.id, transaction);

        return transaction;
    }

    long long read(Transaction& transaction, int accountId) {
        std::lock_guard<std::mutex> lock(databaseMutex);

        requireActive(transaction);

        if (!physicalValues.contains(accountId)) {
            throw ValidationFailure("Unknown account");
        }

        transaction.readSet.insert(accountId);

        if (transaction.writes.contains(accountId)) {
            return transaction.writes.at(accountId);
        }

        if (transaction.isolation == IsolationLevel::ReadUncommitted) {
            /*
             * This branch intentionally exposes another active transaction's
             * uncommitted write so the ANSI dirty-read anomaly can be studied.
             * PostgreSQL does not actually expose such data and maps this
             * isolation request to READ COMMITTED.
             */
            for (const auto& [id, other] : transactions) {
                if (
                    id != transaction.id &&
                    other.state == TransactionState::Active &&
                    other.writes.contains(accountId)
                ) {
                    return other.writes.at(accountId);
                }
            }
        }

        if (transaction.isolation == IsolationLevel::ReadCommitted) {
            return currentCommitted(accountId);
        }

        return transaction.snapshot.at(accountId);
    }

    void write(
        Transaction& transaction,
        int accountId,
        long long newBalance
    ) {
        std::lock_guard<std::mutex> lock(databaseMutex);

        requireActive(transaction);

        if (!physicalValues.contains(accountId)) {
            throw ValidationFailure("Unknown account");
        }

        if (newBalance < 0) {
            throw ValidationFailure(
                "Negative account balances are not permitted"
            );
        }

        transaction.writes[accountId] = newBalance;
        transaction.writeSet.insert(accountId);
    }

    void commit(Transaction& transaction) {
        std::lock_guard<std::mutex> lock(databaseMutex);

        requireActive(transaction);

        if (transaction.isolation == IsolationLevel::Serializable) {
            validateSerializable(transaction);
        } else if (
            transaction.isolation == IsolationLevel::RepeatableRead
        ) {
            validateRepeatableRead(transaction);
        }

        for (const auto& [accountId, value] : transaction.writes) {
            committedValues[accountId] = value;
            physicalValues[accountId] = value;
        }

        transaction.state = TransactionState::Committed;
        transactions.at(transaction.id).state =
            TransactionState::Committed;
    }

    void rollback(Transaction& transaction) {
        std::lock_guard<std::mutex> lock(databaseMutex);

        requireActive(transaction);

        transaction.writes.clear();
        transaction.state = TransactionState::Aborted;
        transactions.at(transaction.id).state =
            TransactionState::Aborted;
    }

    std::map<int, long long> balances() const {
        std::lock_guard<std::mutex> lock(databaseMutex);
        return committedValues;
    }
};

class PaymentService {
private:
    GovernanceAwareDatabase& database;

public:
    explicit PaymentService(GovernanceAwareDatabase& database)
        : database(database) {}

    void transfer(
        int source,
        int destination,
        long long amount
    ) {
        if (source == destination) {
            throw ValidationFailure(
                "Source and destination accounts must differ"
            );
        }

        if (amount <= 0) {
            throw ValidationFailure(
                "Transfer amount must be positive"
            );
        }

        Transaction transaction =
            database.begin(IsolationLevel::Serializable);

        try {
            const long long sourceBalance =
                database.read(transaction, source);

            const long long destinationBalance =
                database.read(transaction, destination);

            if (sourceBalance < amount) {
                throw ValidationFailure("Insufficient funds");
            }

            database.write(
                transaction,
                source,
                sourceBalance - amount
            );

            database.write(
                transaction,
                destination,
                destinationBalance + amount
            );

            database.commit(transaction);

            std::cout
                << "Transfer committed in transaction "
                << transaction.id
                << '\n';
        } catch (...) {
            if (transaction.state == TransactionState::Active) {
                database.rollback(transaction);
            }
            throw;
        }
    }
};

void printBalances(
    const std::map<int, long long>& balances
) {
    std::cout << "Committed balances:\n";

    for (const auto& [account, balance] : balances) {
        std::cout
            << "  account " << account
            << " -> " << balance << '\n';
    }
}

void dirtyReadCaseStudy() {
    std::cout << "\n=== Dirty Read ===\n";

    GovernanceAwareDatabase database({
        {1, 1000}
    });

    Transaction writer =
        database.begin(IsolationLevel::ReadCommitted);

    Transaction reader =
        database.begin(IsolationLevel::ReadUncommitted);

    database.write(writer, 1, 250);

    std::cout
        << "Reader sees active writer value: "
        << database.read(reader, 1)
        << '\n';

    database.rollback(writer);

    std::cout
        << "After rollback, committed value: "
        << database.read(reader, 1)
        << '\n';

    database.rollback(reader);
}

void nonRepeatableReadCaseStudy() {
    std::cout << "\n=== Non-Repeatable Read ===\n";

    GovernanceAwareDatabase database({
        {1, 1000}
    });

    Transaction reader =
        database.begin(IsolationLevel::ReadCommitted);

    Transaction writer =
        database.begin(IsolationLevel::ReadCommitted);

    const long long first =
        database.read(reader, 1);

    database.write(writer, 1, 1250);
    database.commit(writer);

    const long long second =
        database.read(reader, 1);

    std::cout
        << "READ COMMITTED observations: "
        << first << " -> " << second
        << '\n';

    database.rollback(reader);
}

void repeatableReadCaseStudy() {
    std::cout << "\n=== Repeatable Read ===\n";

    GovernanceAwareDatabase database({
        {1, 1000}
    });

    Transaction reader =
        database.begin(IsolationLevel::RepeatableRead);

    Transaction writer =
        database.begin(IsolationLevel::ReadCommitted);

    const long long first =
        database.read(reader, 1);

    database.write(writer, 1, 1500);
    database.commit(writer);

    const long long second =
        database.read(reader, 1);

    std::cout
        << "REPEATABLE READ observations: "
        << first << " -> " << second
        << '\n';

    database.rollback(reader);
}

void serializableCaseStudy() {
    std::cout << "\n=== Serializable Conflict ===\n";

    GovernanceAwareDatabase database({
        {1, 1000},
        {2, 1000}
    });

    Transaction transactionA =
        database.begin(IsolationLevel::Serializable);

    Transaction transactionB =
        database.begin(IsolationLevel::Serializable);

    const long long observedTotal =
        database.read(transactionA, 1) +
        database.read(transactionA, 2);

    database.write(transactionB, 1, 1500);
    database.commit(transactionB);

    database.write(transactionA, 2, 2000);

    std::cout
        << "Transaction A observed total: "
        << observedTotal << '\n';

    try {
        database.commit(transactionA);
    } catch (const SerializationFailure& error) {
        std::cout
            << "Transaction A aborted: "
            << error.what()
            << '\n';
    }

    printBalances(database.balances());
}

void concurrentSerializableCaseStudy() {
    std::cout << "\n=== Concurrent Serializable Workload ===\n";

    GovernanceAwareDatabase database({
        {1, 1000},
        {2, 1000}
    });

    std::mutex outputMutex;

    auto worker = [&](int workerId, int source, int destination) {
        Transaction transaction =
            database.begin(IsolationLevel::Serializable);

        try {
            const long long sourceBalance =
                database.read(transaction, source);

            const long long destinationBalance =
                database.read(transaction, destination);

            database.write(
                transaction,
                source,
                sourceBalance - 100
            );

            std::this_thread::sleep_for(
                std::chrono::milliseconds(20)
            );

            database.write(
                transaction,
                destination,
                destinationBalance + 100
            );

            database.commit(transaction);

            std::lock_guard<std::mutex> lock(outputMutex);

            std::cout
                << "Worker " << workerId
                << " committed transaction "
                << transaction.id << '\n';
        } catch (const SerializationFailure& error) {
            std::lock_guard<std::mutex> lock(outputMutex);

            std::cout
                << "Worker " << workerId
                << " received serialization failure: "
                << error.what()
                << '\n';
        } catch (const std::exception& error) {
            std::lock_guard<std::mutex> lock(outputMutex);

            std::cout
                << "Worker " << workerId
                << " failed: "
                << error.what()
                << '\n';
        }
    };

    std::thread first(worker, 1, 1, 2);
    std::thread second(worker, 2, 2, 1);

    first.join();
    second.join();

    printBalances(database.balances());
}

void isolationComparison() {
    std::cout << "\n=== Isolation Comparison ===\n";

    struct Row {
        IsolationLevel level;
        std::string principalProperty;
        std::string typicalRisk;
    };

    const std::vector<Row> rows{
        {
            IsolationLevel::ReadUncommitted,
            "Allows the weakest visibility guarantees.",
            "Dirty reads can occur in systems that truly implement this level."
        },
        {
            IsolationLevel::ReadCommitted,
            "Statements see committed data available at statement start.",
            "A later statement may observe a newly committed value."
        },
        {
            IsolationLevel::RepeatableRead,
            "A transaction reads from a stable snapshot.",
            "Write conflicts and database-specific phantom behavior require care."
        },
        {
            IsolationLevel::Serializable,
            "Execution must be equivalent to some serial order.",
            "Transactions may fail and need safe retry handling."
        }
    };

    for (const Row& row : rows) {
        std::cout
            << std::left
            << std::setw(20)
            << toString(row.level)
            << row.principalProperty
            << " Risk: "
            << row.typicalRisk
            << '\n';
    }
}

int main() {
    try {
        std::cout
            << "Database Transaction Isolation Case Study\n"
            << "C++17\n";

        isolationComparison();
        dirtyReadCaseStudy();
        nonRepeatableReadCaseStudy();
        repeatableReadCaseStudy();
        serializableCaseStudy();
        concurrentSerializableCaseStudy();

        std::cout << "\n=== Enterprise Payment Scenario ===\n";

        GovernanceAwareDatabase database({
            {101, 5000},
            {102, 1500}
        });

        PaymentService paymentService(database);

        paymentService.transfer(101, 102, 750);

        printBalances(database.balances());

        std::cout
            << "\nThe simulator separates visibility, transaction state, "
            << "conflict detection, and business validation. "
            << "A production database additionally implements its own "
            << "MVCC, locking, predicate handling, WAL, and recovery machinery.\n";
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}

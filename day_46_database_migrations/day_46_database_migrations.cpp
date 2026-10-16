#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace std;

enum class MigrationState {
    Pending,
    Applied,
    Failed
};

struct Column {
    string name;
    string type;
    bool nullable;
};

struct Table {
    string name;
    vector<Column> columns;
};

struct Migration {
    int version;
    string name;
    string checksum;
    function<void()> up;
    function<void()> down;
};

class MigrationException : public runtime_error {
public:
    explicit MigrationException(const string& message)
        : runtime_error(message) {}
};

class SchemaCatalog {
private:
    map<string, Table> tables_;

public:
    void createTable(const string& name, vector<Column> columns) {
        if (tables_.contains(name)) {
            throw MigrationException(
                "Table already exists: " + name
            );
        }

        tables_.emplace(
            name,
            Table{name, move(columns)}
        );
    }

    void dropTable(const string& name) {
        if (!tables_.contains(name)) {
            throw MigrationException(
                "Table does not exist: " + name
            );
        }

        tables_.erase(name);
    }

    void addColumn(
        const string& tableName,
        const Column& column
    ) {
        auto iterator = tables_.find(tableName);

        if (iterator == tables_.end()) {
            throw MigrationException(
                "Cannot add column to missing table: " + tableName
            );
        }

        auto& columns = iterator->second.columns;

        auto duplicate = find_if(
            columns.begin(),
            columns.end(),
            [&](const Column& existing) {
                return existing.name == column.name;
            }
        );

        if (duplicate != columns.end()) {
            throw MigrationException(
                "Column already exists: " + column.name
            );
        }

        columns.push_back(column);
    }

    bool hasTable(const string& name) const {
        return tables_.contains(name);
    }

    void print() const {
        cout << "\nSchema catalog\n";

        for (const auto& [name, table] : tables_) {
            cout << "TABLE " << name << '\n';

            for (const auto& column : table.columns) {
                cout << "  " << column.name
                     << " " << column.type
                     << (column.nullable ? " NULL" : " NOT NULL")
                     << '\n';
            }
        }
    }
};

struct MigrationRecord {
    int version;
    string name;
    string checksum;
    string appliedAt;
};

class MigrationHistory {
private:
    vector<MigrationRecord> records_;

public:
    bool isApplied(int version) const {
        return any_of(
            records_.begin(),
            records_.end(),
            [version](const MigrationRecord& record) {
                return record.version == version;
            }
        );
    }

    void record(MigrationRecord record) {
        if (isApplied(record.version)) {
            throw MigrationException(
                "Migration already recorded: " +
                to_string(record.version)
            );
        }

        records_.push_back(move(record));
        sort(
            records_.begin(),
            records_.end(),
            [](const auto& left, const auto& right) {
                return left.version < right.version;
            }
        );
    }

    optional<MigrationRecord> latest() const {
        if (records_.empty()) {
            return nullopt;
        }

        return records_.back();
    }

    void remove(int version) {
        auto iterator = remove_if(
            records_.begin(),
            records_.end(),
            [version](const MigrationRecord& record) {
                return record.version == version;
            }
        );

        if (iterator == records_.end()) {
            throw MigrationException(
                "Migration history entry not found."
            );
        }

        records_.erase(iterator, records_.end());
    }

    void print() const {
        cout << "\nMigration history\n";

        for (const auto& record : records_) {
            cout << "v" << record.version
                 << " | " << record.name
                 << " | checksum=" << record.checksum
                 << " | " << record.appliedAt
                 << '\n';
        }
    }
};

class MigrationTransaction {
private:
    SchemaCatalog& catalog_;
    SchemaCatalog schemaBackup_;
    MigrationHistory& history_;
    vector<MigrationRecord> historyBackup_;
    bool committed_{false};

public:
    MigrationTransaction(
        SchemaCatalog& catalog,
        MigrationHistory& history
    )
        : catalog_(catalog),
          schemaBackup_(catalog),
          history_(history),
          historyBackup_() {}

    void commit() {
        committed_ = true;
    }

    ~MigrationTransaction() {
        if (!committed_) {
            catalog_ = schemaBackup_;

            // History is restored by the migration runner because its
            // public API intentionally exposes controlled mutation only.
        }
    }
};

static string utcTimestamp() {
    const auto now = chrono::system_clock::now();
    const time_t timeValue = chrono::system_clock::to_time_t(now);

    tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &timeValue);
#else
    gmtime_r(&timeValue, &utc);
#endif

    ostringstream stream;
    stream << put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return stream.str();
}

class MigrationEngine {
private:
    SchemaCatalog catalog_;
    MigrationHistory history_;

public:
    void apply(Migration migration) {
        if (history_.isApplied(migration.version)) {
            return;
        }

        SchemaCatalog schemaBackup = catalog_;
        const auto historyBefore = history_.latest();

        try {
            migration.up();

            history_.record({
                migration.version,
                migration.name,
                migration.checksum,
                utcTimestamp()
            });

            cout << "Applied v"
                 << migration.version
                 << ": "
                 << migration.name
                 << '\n';
        } catch (const exception& error) {
            catalog_ = move(schemaBackup);

            if (history_.latest().has_value()) {
                const auto latest = history_.latest().value();

                if (!historyBefore.has_value() ||
                    latest.version != historyBefore->version) {
                    history_.remove(latest.version);
                }
            }

            throw MigrationException(
                "Migration v" +
                to_string(migration.version) +
                " rolled back: " +
                error.what()
            );
        }
    }

    void applyAll(vector<Migration>& migrations) {
        sort(
            migrations.begin(),
            migrations.end(),
            [](const Migration& left, const Migration& right) {
                return left.version < right.version;
            }
        );

        for (auto& migration : migrations) {
            apply(migration);
        }
    }

    void rollbackLast(const vector<Migration>& migrations) {
        const auto latest = history_.latest();

        if (!latest.has_value()) {
            throw MigrationException(
                "No migration is available for rollback."
            );
        }

        auto iterator = find_if(
            migrations.begin(),
            migrations.end(),
            [&](const Migration& migration) {
                return migration.version == latest->version;
            }
        );

        if (iterator == migrations.end()) {
            throw MigrationException(
                "Rollback definition is missing."
            );
        }

        SchemaCatalog schemaBackup = catalog_;

        try {
            iterator->down();
            history_.remove(iterator->version);

            cout << "Rolled back v"
                 << iterator->version
                 << ": "
                 << iterator->name
                 << '\n';
        } catch (const exception& error) {
            catalog_ = move(schemaBackup);

            throw MigrationException(
                "Rollback failed: " +
                string(error.what())
            );
        }
    }

    void printState() const {
        catalog_.print();
        history_.print();
    }

    const SchemaCatalog& catalog() const {
        return catalog_;
    }
};

int main() {
    MigrationEngine engine;

    vector<Migration> migrations;

    migrations.push_back({
        1,
        "create_customer_accounts",
        "sha256:create_customer_accounts_v1",
        [&engine]() {
            engine.catalog().hasTable("unused");
        },
        []() {}
    });

    /*
     * The first migration needs controlled access to the mutable catalog.
     * A separate set of migrations below uses a helper object so that the
     * case study keeps the actual schema operations explicit.
     */
    SchemaCatalog deploymentCatalog;
    MigrationHistory deploymentHistory;

    auto createAccounts = [&deploymentCatalog]() {
        deploymentCatalog.createTable(
            "customer_accounts",
            {
                {"id", "BIGINT", false},
                {"email", "VARCHAR(320)", false},
                {"display_name", "VARCHAR(200)", false}
            }
        );
    };

    auto dropAccounts = [&deploymentCatalog]() {
        deploymentCatalog.dropTable("customer_accounts");
    };

    auto addStatus = [&deploymentCatalog]() {
        deploymentCatalog.addColumn(
            "customer_accounts",
            {"status", "VARCHAR(20)", false}
        );
    };

    auto removeStatus = [&deploymentCatalog]() {
        // A real database migration would use ALTER TABLE DROP COLUMN.
        // The catalog models the same schema transition explicitly.
        auto backup = deploymentCatalog;
        deploymentCatalog = SchemaCatalog{};

        try {
            deploymentCatalog.createTable(
                "customer_accounts",
                {
                    {"id", "BIGINT", false},
                    {"email", "VARCHAR(320)", false},
                    {"display_name", "VARCHAR(200)", false}
                }
            );
        } catch (...) {
            deploymentCatalog = move(backup);
            throw;
        }
    };

    auto createOrders = [&deploymentCatalog]() {
        deploymentCatalog.createTable(
            "orders",
            {
                {"id", "BIGINT", false},
                {"customer_id", "BIGINT", false},
                {"amount_cents", "BIGINT", false},
                {"state", "VARCHAR(20)", false}
            }
        );
    };

    auto dropOrders = [&deploymentCatalog]() {
        deploymentCatalog.dropTable("orders");
    };

    vector<Migration> deploymentPlan = {
        {
            1,
            "create_customer_accounts",
            "sha256:create_customer_accounts_v1",
            createAccounts,
            dropAccounts
        },
        {
            2,
            "add_customer_status",
            "sha256:add_customer_status_v2",
            addStatus,
            removeStatus
        },
        {
            3,
            "create_orders",
            "sha256:create_orders_v3",
            createOrders,
            dropOrders
        }
    };

    cout << "Database migration case study\n";

    for (auto& migration : deploymentPlan) {
        if (deploymentHistory.isApplied(migration.version)) {
            continue;
        }

        try {
            SchemaCatalog schemaBackup = deploymentCatalog;

            migration.up();

            deploymentHistory.record({
                migration.version,
                migration.name,
                migration.checksum,
                utcTimestamp()
            });

            cout << "Applied v"
                 << migration.version
                 << ": "
                 << migration.name
                 << '\n';
        } catch (const exception& error) {
            cout << "Deployment failed for v"
                 << migration.version
                 << ": "
                 << error.what()
                 << '\n';
            break;
        }
    }

    cout << "\nEvolved schema after successful deployment:\n";
    deploymentCatalog.print();

    cout << "\nMigration history:\n";
    deploymentHistory.print();

    /*
     * Demonstrate a failed migration. Schema state is copied before the
     * migration. If any operation fails, that snapshot is restored and no
     * history entry is retained.
     */
    Migration failingMigration{
        4,
        "add_payment_reference",
        "sha256:add_payment_reference_v4",
        [&deploymentCatalog]() {
            deploymentCatalog.addColumn(
                "orders",
                {"payment_reference", "VARCHAR(100)", false}
            );

            throw MigrationException(
                "Backfill validation rejected an existing order."
            );
        },
        [&deploymentCatalog]() {}
    };

    cout << "\nTesting transactional failure handling:\n";

    SchemaCatalog beforeFailure = deploymentCatalog;

    try {
        failingMigration.up();
    } catch (const exception& error) {
        deploymentCatalog = move(beforeFailure);

        cout << "Expected failure: "
             << error.what()
             << '\n';
        cout << "Schema restored after failure.\n";
    }

    /*
     * Migration history must be immutable evidence of what was actually
     * deployed. Changing the implementation or checksum of an already
     * applied migration is schema drift, not a harmless source-code edit.
     */
    cout << "\nProduction rule: applied migration definitions must not be edited.\n";
    cout << "A new migration should represent every subsequent schema change.\n";

    return 0;
}

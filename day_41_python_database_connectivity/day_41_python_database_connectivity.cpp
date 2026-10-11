#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <libpq-fe.h>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Repository Governance Database Case Study
 *
 * This program uses PostgreSQL's libpq C API. It demonstrates a lower-level
 * database-driver model than the Python and JavaScript examples:
 *
 *   PGconn -> PQexecParams -> PGresult -> inspect -> PQclear -> PQfinish
 *
 * Compile on a system with PostgreSQL client development files:
 *
 *   g++ -std=c++17 repository_governance.cpp -lpq -o repository_governance
 *
 * The database connection string can be supplied through DATABASE_URL.
 */

class DatabaseException : public std::runtime_error {
public:
    explicit DatabaseException(const std::string& message)
        : std::runtime_error(message) {}
};

class PostgreSQLConnection {
private:
    PGconn* connection_;

public:
    explicit PostgreSQLConnection(const std::string& connectionString)
        : connection_(PQconnectdb(connectionString.c_str())) {
        if (!connection_) {
            throw DatabaseException("PostgreSQL driver could not allocate connection");
        }

        if (PQstatus(connection_) != CONNECTION_OK) {
            std::string error = PQerrorMessage(connection_);
            PQfinish(connection_);
            connection_ = nullptr;
            throw DatabaseException("Connection failed: " + error);
        }
    }

    PostgreSQLConnection(const PostgreSQLConnection&) = delete;
    PostgreSQLConnection& operator=(const PostgreSQLConnection&) = delete;

    ~PostgreSQLConnection() {
        if (connection_) {
            PQfinish(connection_);
        }
    }

    PGconn* get() {
        if (!connection_) {
            throw DatabaseException("Connection is closed");
        }
        return connection_;
    }

    void execute(const std::string& sql) {
        PGresult* result = PQexec(get(), sql.c_str());

        if (!result) {
            throw DatabaseException(
                "Driver returned no result: " +
                std::string(PQerrorMessage(get()))
            );
        }

        ExecStatusType status = PQresultStatus(result);

        if (status != PGRES_COMMAND_OK && status != PGRES_TUPLES_OK) {
            std::string error = PQresultErrorMessage(result);
            PQclear(result);
            throw DatabaseException("SQL execution failed: " + error);
        }

        PQclear(result);
    }

    std::vector<std::vector<std::string>> query(
        const std::string& sql,
        const std::vector<std::string>& parameters = {}
    ) {
        std::vector<const char*> values;
        values.reserve(parameters.size());

        for (const auto& parameter : parameters) {
            values.push_back(parameter.c_str());
        }

        PGresult* result = PQexecParams(
            get(),
            sql.c_str(),
            static_cast<int>(values.size()),
            nullptr,
            values.empty() ? nullptr : values.data(),
            nullptr,
            nullptr,
            0
        );

        if (!result) {
            throw DatabaseException(
                "Parameterized query returned no result: " +
                std::string(PQerrorMessage(get()))
            );
        }

        if (PQresultStatus(result) != PGRES_TUPLES_OK) {
            std::string error = PQresultErrorMessage(result);
            PQclear(result);
            throw DatabaseException("Query failed: " + error);
        }

        std::vector<std::vector<std::string>> rows;

        for (int row = 0; row < PQntuples(result); ++row) {
            std::vector<std::string> valuesForRow;

            for (int column = 0; column < PQnfields(result); ++column) {
                if (PQgetisnull(result, row, column)) {
                    valuesForRow.emplace_back("");
                } else {
                    valuesForRow.emplace_back(
                        PQgetvalue(result, row, column)
                    );
                }
            }

            rows.push_back(std::move(valuesForRow));
        }

        PQclear(result);
        return rows;
    }

    void begin() {
        execute("BEGIN");
    }

    void commit() {
        execute("COMMIT");
    }

    void rollback() noexcept {
        try {
            execute("ROLLBACK");
        } catch (...) {
            // A rollback is best-effort during error recovery.
        }
    }
};

class RepositoryGovernanceService {
private:
    PostgreSQLConnection& database_;

public:
    explicit RepositoryGovernanceService(PostgreSQLConnection& database)
        : database_(database) {}

    void createSchema() {
        database_.execute(R"SQL(
            CREATE TABLE IF NOT EXISTS repositories (
                repository_id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS branches (
                branch_id BIGSERIAL PRIMARY KEY,
                repository_id BIGINT NOT NULL
                    REFERENCES repositories(repository_id),
                name TEXT NOT NULL,
                protected BOOLEAN NOT NULL DEFAULT FALSE,
                UNIQUE(repository_id, name)
            );

            CREATE TABLE IF NOT EXISTS pull_requests (
                pull_request_id BIGSERIAL PRIMARY KEY,
                repository_id BIGINT NOT NULL
                    REFERENCES repositories(repository_id),
                source_branch_id BIGINT NOT NULL
                    REFERENCES branches(branch_id),
                target_branch_id BIGINT NOT NULL
                    REFERENCES branches(branch_id),
                title TEXT NOT NULL,
                state TEXT NOT NULL
                    CHECK (state IN ('draft', 'open', 'closed', 'merged')),
                head_sha TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviewers (
                reviewer_id BIGSERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                active BOOLEAN NOT NULL DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id BIGSERIAL PRIMARY KEY,
                pull_request_id BIGINT NOT NULL
                    REFERENCES pull_requests(pull_request_id)
                    ON DELETE CASCADE,
                reviewer_id BIGINT NOT NULL
                    REFERENCES reviewers(reviewer_id),
                state TEXT NOT NULL
                    CHECK (state IN ('commented', 'changes_requested', 'approved')),
                commit_sha TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS status_checks (
                status_check_id BIGSERIAL PRIMARY KEY,
                pull_request_id BIGINT NOT NULL
                    REFERENCES pull_requests(pull_request_id)
                    ON DELETE CASCADE,
                check_name TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('pending', 'passed', 'failed')),
                UNIQUE(pull_request_id, check_name)
            );

            CREATE TABLE IF NOT EXISTS branch_protection (
                branch_id BIGINT PRIMARY KEY
                    REFERENCES branches(branch_id)
                    ON DELETE CASCADE,
                required_approvals INTEGER NOT NULL
                    CHECK (required_approvals >= 0),
                required_status_checks BOOLEAN NOT NULL,
                restrict_direct_push BOOLEAN NOT NULL,
                allow_force_push BOOLEAN NOT NULL DEFAULT FALSE
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_pr
                ON reviews(pull_request_id);

            CREATE INDEX IF NOT EXISTS idx_status_checks_pr
                ON status_checks(pull_request_id);
        )SQL");
    }

    long long ensureRepository() {
        auto rows = database_.query(
            R"SQL(
                INSERT INTO repositories(name)
                VALUES ($1)
                ON CONFLICT (name)
                DO UPDATE SET name = EXCLUDED.name
                RETURNING repository_id
            )SQL",
            {"inventory-service"}
        );

        if (rows.empty()) {
            throw DatabaseException("Repository ID was not returned");
        }

        return std::stoll(rows[0][0]);
    }

    long long ensureBranch(
        long long repositoryId,
        const std::string& branchName,
        bool protectedBranch
    ) {
        auto rows = database_.query(
            R"SQL(
                INSERT INTO branches(repository_id, name, protected)
                VALUES ($1, $2, $3)
                ON CONFLICT (repository_id, name)
                DO UPDATE SET protected = EXCLUDED.protected
                RETURNING branch_id
            )SQL",
            {
                std::to_string(repositoryId),
                branchName,
                protectedBranch ? "true" : "false"
            }
        );

        return std::stoll(rows.at(0).at(0));
    }

    long long createPullRequest(
        long long repositoryId,
        long long sourceBranch,
        long long targetBranch
    ) {
        auto rows = database_.query(
            R"SQL(
                INSERT INTO pull_requests(
                    repository_id,
                    source_branch_id,
                    target_branch_id,
                    title,
                    state,
                    head_sha
                )
                VALUES ($1, $2, $3, $4, 'open', $5)
                RETURNING pull_request_id
            )SQL",
            {
                std::to_string(repositoryId),
                std::to_string(sourceBranch),
                std::to_string(targetBranch),
                "Harden inventory reservation validation",
                "9f8e7d6c5b4a"
            }
        );

        return std::stoll(rows.at(0).at(0));
    }

    void configureProtection(long long branchId) {
        database_.query(
            R"SQL(
                INSERT INTO branch_protection(
                    branch_id,
                    required_approvals,
                    required_status_checks,
                    restrict_direct_push,
                    allow_force_push
                )
                VALUES ($1, 2, TRUE, TRUE, FALSE)
                ON CONFLICT (branch_id)
                DO UPDATE SET
                    required_approvals = EXCLUDED.required_approvals,
                    required_status_checks = EXCLUDED.required_status_checks,
                    restrict_direct_push = EXCLUDED.restrict_direct_push,
                    allow_force_push = EXCLUDED.allow_force_push
            )SQL",
            {std::to_string(branchId)}
        );
    }

    void configureReviewers(long long pullRequestId) {
        database_.query(
            R"SQL(
                INSERT INTO reviewers(username)
                VALUES ('architect'), ('security-reviewer')
                ON CONFLICT (username)
                DO UPDATE SET active = TRUE
            )SQL"
        );

        auto reviewers = database_.query(
            R"SQL(
                SELECT reviewer_id, username
                FROM reviewers
                WHERE username IN ('architect', 'security-reviewer')
                ORDER BY username
            )SQL"
        );

        for (const auto& reviewer : reviewers) {
            database_.query(
                R"SQL(
                    INSERT INTO reviews(
                        pull_request_id,
                        reviewer_id,
                        state,
                        commit_sha
                    )
                    VALUES ($1, $2, 'approved', $3)
                )SQL",
                {
                    std::to_string(pullRequestId),
                    reviewer[0],
                    "9f8e7d6c5b4a"
                }
            );
        }

        database_.query(
            R"SQL(
                INSERT INTO status_checks(
                    pull_request_id,
                    check_name,
                    status
                )
                VALUES
                    ($1, 'unit-tests', 'passed'),
                    ($1, 'security-analysis', 'passed')
            )SQL",
            {std::to_string(pullRequestId)}
        );
    }

    void printMergeEligibility(long long pullRequestId) {
        auto rows = database_.query(
            R"SQL(
                WITH policy AS (
                    SELECT
                        bp.required_approvals,
                        bp.required_status_checks
                    FROM pull_requests p
                    JOIN branch_protection bp
                      ON bp.branch_id = p.target_branch_id
                    WHERE p.pull_request_id = $1
                ),
                approval_count AS (
                    SELECT COUNT(DISTINCT reviewer_id) AS count
                    FROM reviews
                    WHERE pull_request_id = $1
                      AND state = 'approved'
                ),
                checks AS (
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (
                            WHERE status = 'passed'
                        ) AS passed
                    FROM status_checks
                    WHERE pull_request_id = $1
                )
                SELECT
                    policy.required_approvals,
                    approval_count.count,
                    checks.total,
                    checks.passed,
                    (
                        approval_count.count >= policy.required_approvals
                        AND (
                            policy.required_status_checks = FALSE
                            OR (
                                checks.total > 0
                                AND checks.total = checks.passed
                            )
                        )
                    ) AS merge_allowed
                FROM policy
                CROSS JOIN approval_count
                CROSS JOIN checks
            )SQL",
            {std::to_string(pullRequestId)}
        );

        if (rows.empty()) {
            throw DatabaseException("Merge policy could not be evaluated");
        }

        const auto& row = rows.front();

        std::cout << "\nMerge eligibility engine\n";
        std::cout << "Required approvals: " << row[0] << '\n';
        std::cout << "Current approvals:  " << row[1] << '\n';
        std::cout << "Checks passed:      "
                  << row[3] << "/" << row[2] << '\n';
        std::cout << "Merge allowed:      " << row[4] << '\n';
    }
};

int main() {
    const char* environmentConnection =
        std::getenv("DATABASE_URL");

    const std::string connectionString =
        environmentConnection
            ? environmentConnection
            : "host=localhost port=5432 dbname=repository_governance "
              "user=postgres password=postgres";

    try {
        PostgreSQLConnection database(connectionString);

        std::cout << "PostgreSQL connection established.\n";

        RepositoryGovernanceService governance(database);

        governance.createSchema();

        database.begin();

        try {
            const long long repository =
                governance.ensureRepository();

            const long long mainBranch =
                governance.ensureBranch(
                    repository,
                    "main",
                    true
                );

            const long long featureBranch =
                governance.ensureBranch(
                    repository,
                    "feature/inventory-validation",
                    false
                );

            governance.configureProtection(mainBranch);

            const long long pullRequest =
                governance.createPullRequest(
                    repository,
                    featureBranch,
                    mainBranch
                );

            governance.configureReviewers(pullRequest);

            database.commit();

            governance.printMergeEligibility(pullRequest);

            /*
             * The query above uses driver parameter binding instead of string
             * concatenation. This matters because repository titles, branch
             * names, usernames, and other database values can originate from
             * untrusted input.
             */
        } catch (...) {
            database.rollback();
            throw;
        }

        /*
         * RAII closes the physical connection automatically when `database`
         * leaves scope. This prevents leaked connections on normal returns
         * and exception paths.
         */
        std::cout << "\nDatabase lifecycle completed safely.\n";
    } catch (const DatabaseException& error) {
        std::cerr << "Database error: " << error.what() << '\n';
        return 1;
    } catch (const std::exception& error) {
        std::cerr << "Unexpected error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}

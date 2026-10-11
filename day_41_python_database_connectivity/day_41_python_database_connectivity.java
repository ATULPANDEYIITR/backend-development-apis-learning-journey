import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/*
 * Enterprise-oriented JDBC example.
 *
 * Runtime requires a PostgreSQL JDBC driver, for example:
 * org.postgresql:postgresql
 *
 * JDBC separates application code from the concrete database driver through
 * interfaces such as Connection, PreparedStatement and ResultSet.
 *
 * Java 17+ is required.
 */

public class RepositoryGovernanceJdbc {

    private static final String JDBC_URL =
            System.getenv().getOrDefault(
                    "JDBC_URL",
                    "jdbc:postgresql://localhost:5432/repository_governance"
            );

    private static final String DB_USER =
            System.getenv().getOrDefault("DB_USER", "postgres");

    private static final String DB_PASSWORD =
            System.getenv().getOrDefault("DB_PASSWORD", "postgres");

    enum PullRequestState {
        DRAFT,
        OPEN,
        CLOSED,
        MERGED
    }

    enum ReviewState {
        COMMENTED,
        CHANGES_REQUESTED,
        APPROVED
    }

    record Repository(long id, String name) {}

    record Branch(long id, String name, boolean protectedBranch) {}

    record PullRequest(
            long id,
            String title,
            PullRequestState state,
            String headSha
    ) {}

    record MergePolicy(
            int requiredApprovals,
            boolean requireStatusChecks,
            boolean restrictDirectPush,
            boolean allowForcePush
    ) {}

    record MergeDecision(
            boolean allowed,
            String reason
    ) {}

    static class RepositoryException extends RuntimeException {
        RepositoryException(String message, Throwable cause) {
            super(message, cause);
        }

        RepositoryException(String message) {
            super(message);
        }
    }

    static final class Database implements AutoCloseable {
        private final Connection connection;

        Database() {
            try {
                /*
                 * DriverManager delegates connection creation to the
                 * PostgreSQL JDBC driver registered on the classpath.
                 */
                this.connection = DriverManager.getConnection(
                        JDBC_URL,
                        DB_USER,
                        DB_PASSWORD
                );

                // Explicit transaction management is useful when several
                // repository records must become visible atomically.
                this.connection.setAutoCommit(false);

            } catch (SQLException error) {
                throw new RepositoryException(
                        "Unable to establish JDBC connection",
                        error
                );
            }
        }

        Connection connection() {
            return connection;
        }

        void commit() {
            try {
                connection.commit();
            } catch (SQLException error) {
                throw new RepositoryException(
                        "Commit failed",
                        error
                );
            }
        }

        void rollback() {
            try {
                connection.rollback();
            } catch (SQLException error) {
                throw new RepositoryException(
                        "Rollback failed",
                        error
                );
            }
        }

        @Override
        public void close() {
            try {
                if (!connection.isClosed()) {
                    connection.close();
                }
            } catch (SQLException error) {
                throw new RepositoryException(
                        "Connection close failed",
                        error
                );
            }
        }
    }

    static final class GovernanceService {
        private final Connection connection;

        GovernanceService(Connection connection) {
            this.connection = Objects.requireNonNull(connection);
        }

        void createSchema() throws SQLException {
            String sql = """
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
                        state TEXT NOT NULL,
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
                        state TEXT NOT NULL,
                        commit_sha TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS status_checks (
                        status_check_id BIGSERIAL PRIMARY KEY,
                        pull_request_id BIGINT NOT NULL
                            REFERENCES pull_requests(pull_request_id)
                            ON DELETE CASCADE,
                        check_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        UNIQUE(pull_request_id, check_name)
                    );

                    CREATE TABLE IF NOT EXISTS branch_protection (
                        branch_id BIGINT PRIMARY KEY
                            REFERENCES branches(branch_id)
                            ON DELETE CASCADE,
                        required_approvals INTEGER NOT NULL,
                        require_status_checks BOOLEAN NOT NULL,
                        restrict_direct_push BOOLEAN NOT NULL,
                        allow_force_push BOOLEAN NOT NULL DEFAULT FALSE
                    )
                    """;

            /*
             * PostgreSQL accepts multiple statements through Statement.
             * Production migrations should normally be versioned separately.
             */
            try (Statement statement = connection.createStatement()) {
                for (String command : sql.split(";")) {
                    if (!command.isBlank()) {
                        statement.execute(command);
                    }
                }
            }
        }

        Repository createRepository(String name) throws SQLException {
            String sql = """
                    INSERT INTO repositories(name)
                    VALUES (?)
                    ON CONFLICT (name)
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING repository_id, name
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setString(1, name);

                try (ResultSet result = statement.executeQuery()) {
                    if (!result.next()) {
                        throw new SQLException(
                                "Repository identifier was not returned"
                        );
                    }

                    return new Repository(
                            result.getLong("repository_id"),
                            result.getString("name")
                    );
                }
            }
        }

        Branch createBranch(
                long repositoryId,
                String name,
                boolean protectedBranch
        ) throws SQLException {

            String sql = """
                    INSERT INTO branches(repository_id, name, protected)
                    VALUES (?, ?, ?)
                    ON CONFLICT (repository_id, name)
                    DO UPDATE SET protected = EXCLUDED.protected
                    RETURNING branch_id, name, protected
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setLong(1, repositoryId);
                statement.setString(2, name);
                statement.setBoolean(3, protectedBranch);

                try (ResultSet result = statement.executeQuery()) {
                    result.next();

                    return new Branch(
                            result.getLong("branch_id"),
                            result.getString("name"),
                            result.getBoolean("protected")
                    );
                }
            }
        }

        PullRequest createPullRequest(
                long repositoryId,
                Branch source,
                Branch target,
                String title,
                String headSha
        ) throws SQLException {

            if (source.id() == target.id()) {
                throw new IllegalArgumentException(
                        "A pull request requires different source and target branches"
                );
            }

            String sql = """
                    INSERT INTO pull_requests(
                        repository_id,
                        source_branch_id,
                        target_branch_id,
                        title,
                        state,
                        head_sha
                    )
                    VALUES (?, ?, ?, ?, 'OPEN', ?)
                    RETURNING pull_request_id, title, state, head_sha
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setLong(1, repositoryId);
                statement.setLong(2, source.id());
                statement.setLong(3, target.id());
                statement.setString(4, title);
                statement.setString(5, headSha);

                try (ResultSet result = statement.executeQuery()) {
                    result.next();

                    return new PullRequest(
                            result.getLong("pull_request_id"),
                            result.getString("title"),
                            PullRequestState.valueOf(
                                    result.getString("state")
                            ),
                            result.getString("head_sha")
                    );
                }
            }
        }

        void configureBranchProtection(
                Branch branch,
                MergePolicy policy
        ) throws SQLException {

            String sql = """
                    INSERT INTO branch_protection(
                        branch_id,
                        required_approvals,
                        require_status_checks,
                        restrict_direct_push,
                        allow_force_push
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (branch_id)
                    DO UPDATE SET
                        required_approvals = EXCLUDED.required_approvals,
                        require_status_checks =
                            EXCLUDED.require_status_checks,
                        restrict_direct_push =
                            EXCLUDED.restrict_direct_push,
                        allow_force_push =
                            EXCLUDED.allow_force_push
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setLong(1, branch.id());
                statement.setInt(2, policy.requiredApprovals());
                statement.setBoolean(
                        3,
                        policy.requireStatusChecks()
                );
                statement.setBoolean(
                        4,
                        policy.restrictDirectPush()
                );
                statement.setBoolean(
                        5,
                        policy.allowForcePush()
                );

                statement.executeUpdate();
            }
        }

        void createReviewer(String username) throws SQLException {
            String sql = """
                    INSERT INTO reviewers(username)
                    VALUES (?)
                    ON CONFLICT (username)
                    DO UPDATE SET active = TRUE
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setString(1, username);
                statement.executeUpdate();
            }
        }

        long reviewerId(String username) throws SQLException {
            String sql = """
                    SELECT reviewer_id
                    FROM reviewers
                    WHERE username = ?
                      AND active = TRUE
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setString(1, username);

                try (ResultSet result = statement.executeQuery()) {
                    if (!result.next()) {
                        throw new SQLException(
                                "Active reviewer not found: " + username
                        );
                    }

                    return result.getLong(1);
                }
            }
        }

        void recordReview(
                PullRequest pullRequest,
                String username,
                ReviewState state
        ) throws SQLException {

            long reviewerId = reviewerId(username);

            String sql = """
                    INSERT INTO reviews(
                        pull_request_id,
                        reviewer_id,
                        state,
                        commit_sha
                    )
                    VALUES (?, ?, ?, ?)
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setLong(1, pullRequest.id());
                statement.setLong(2, reviewerId);
                statement.setString(3, state.name());
                statement.setString(4, pullRequest.headSha());
                statement.executeUpdate();
            }
        }

        void recordStatusCheck(
                PullRequest pullRequest,
                String checkName,
                String status
        ) throws SQLException {

            String sql = """
                    INSERT INTO status_checks(
                        pull_request_id,
                        check_name,
                        status
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT (pull_request_id, check_name)
                    DO UPDATE SET status = EXCLUDED.status
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setLong(1, pullRequest.id());
                statement.setString(2, checkName);
                statement.setString(3, status);
                statement.executeUpdate();
            }
        }

        MergeDecision evaluateMergeEligibility(
                PullRequest pullRequest,
                MergePolicy policy
        ) throws SQLException {

            String sql = """
                    SELECT
                        COUNT(DISTINCT r.reviewer_id)
                            FILTER (
                                WHERE r.state = 'APPROVED'
                                  AND r.commit_sha = ?
                            ) AS approvals,
                        COUNT(sc.status_check_id) AS total_checks,
                        COUNT(sc.status_check_id)
                            FILTER (
                                WHERE sc.status = 'passed'
                            ) AS passed_checks
                    FROM reviews r
                    FULL OUTER JOIN status_checks sc
                        ON sc.pull_request_id = r.pull_request_id
                    WHERE r.pull_request_id = ?
                       OR sc.pull_request_id = ?
                    """;

            try (PreparedStatement statement =
                         connection.prepareStatement(sql)) {

                statement.setString(1, pullRequest.headSha());
                statement.setLong(2, pullRequest.id());
                statement.setLong(3, pullRequest.id());

                try (ResultSet result = statement.executeQuery()) {
                    result.next();

                    int approvals = result.getInt("approvals");
                    int totalChecks = result.getInt("total_checks");
                    int passedChecks = result.getInt("passed_checks");

                    if (pullRequest.state() != PullRequestState.OPEN) {
                        return new MergeDecision(
                                false,
                                "Pull request is not open"
                        );
                    }

                    if (approvals < policy.requiredApprovals()) {
                        return new MergeDecision(
                                false,
                                "Required approval count has not been reached"
                        );
                    }

                    if (policy.requireStatusChecks()
                            && (
                                totalChecks == 0
                                || passedChecks != totalChecks
                            )) {
                        return new MergeDecision(
                                false,
                                "Required status checks are not all passing"
                        );
                    }

                    return new MergeDecision(
                            true,
                            "All configured merge conditions are satisfied"
                    );
                }
            }
        }
    }

    public static void main(String[] args) {
        try (Database database = new Database()) {
            GovernanceService service =
                    new GovernanceService(database.connection());

            service.createSchema();

            try {
                Repository repository =
                        service.createRepository("billing-platform");

                Branch main =
                        service.createBranch(
                                repository.id(),
                                "main",
                                true
                        );

                Branch feature =
                        service.createBranch(
                                repository.id(),
                                "feature/tax-validation",
                                false
                        );

                MergePolicy policy =
                        new MergePolicy(
                                2,
                                true,
                                true,
                                false
                        );

                service.configureBranchProtection(main, policy);

                PullRequest pullRequest =
                        service.createPullRequest(
                                repository.id(),
                                feature,
                                main,
                                "Validate tax calculations",
                                "abc123456789"
                        );

                service.createReviewer("platform-reviewer");
                service.createReviewer("security-reviewer");

                service.recordReview(
                        pullRequest,
                        "platform-reviewer",
                        ReviewState.APPROVED
                );

                service.recordReview(
                        pullRequest,
                        "security-reviewer",
                        ReviewState.APPROVED
                );

                service.recordStatusCheck(
                        pullRequest,
                        "unit-tests",
                        "passed"
                );

                service.recordStatusCheck(
                        pullRequest,
                        "security-scan",
                        "passed"
                );

                MergeDecision decision =
                        service.evaluateMergeEligibility(
                                pullRequest,
                                policy
                        );

                database.commit();

                System.out.println(
                        "Repository: " + repository.name()
                );
                System.out.println(
                        "Pull request: #" + pullRequest.id()
                );
                System.out.println(
                        "Merge allowed: " + decision.allowed()
                );
                System.out.println(
                        "Decision: " + decision.reason()
                );

            } catch (SQLException | IllegalArgumentException error) {
                database.rollback();
                throw error;
            }

        } catch (SQLException | RepositoryException error) {
            System.err.println(
                    "Database operation failed: " + error.getMessage()
            );
        }
    }
}

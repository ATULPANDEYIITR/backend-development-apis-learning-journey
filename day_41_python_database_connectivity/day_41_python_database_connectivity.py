import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DATABASE = Path("repository_governance.db")


@dataclass(frozen=True)
class Repository:
    name: str
    default_branch: str


class DatabaseError(RuntimeError):
    """Application-level database error."""


class RepositoryDatabase:
    """
    Demonstrates the complete lifecycle of a Python DB-API connection:

    connect -> configure -> create cursor -> execute -> fetch -> commit/rollback
    -> close cursor -> close connection.

    SQLite is used because sqlite3 is included in Python's standard library.
    The same lifecycle concepts apply to drivers such as psycopg for PostgreSQL.
    """

    def __init__(self, database: str):
        self.database = database
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        if self.connection is not None:
            return

        self.connection = sqlite3.connect(
            self.database,
            timeout=5,
            isolation_level=None,
        )
        self.connection.row_factory = sqlite3.Row

        # Foreign-key enforcement is a connection-level SQLite setting.
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise DatabaseError("Database connection is not open")
        return self.connection

    def create_schema(self) -> None:
        connection = self.require_connection()

        schema = """
        CREATE TABLE IF NOT EXISTS repositories (
            repository_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            default_branch TEXT NOT NULL
                CHECK (length(default_branch) > 0)
        );

        CREATE TABLE IF NOT EXISTS branches (
            branch_id INTEGER PRIMARY KEY,
            repository_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            protected INTEGER NOT NULL DEFAULT 0
                CHECK (protected IN (0, 1)),
            FOREIGN KEY (repository_id)
                REFERENCES repositories(repository_id)
                ON DELETE CASCADE,
            UNIQUE(repository_id, name)
        );

        CREATE TABLE IF NOT EXISTS pull_requests (
            pull_request_id INTEGER PRIMARY KEY,
            repository_id INTEGER NOT NULL,
            source_branch_id INTEGER NOT NULL,
            target_branch_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            state TEXT NOT NULL
                CHECK (state IN ('draft', 'open', 'closed', 'merged')),
            merge_status TEXT NOT NULL DEFAULT 'blocked'
                CHECK (merge_status IN ('ready', 'blocked')),
            FOREIGN KEY (repository_id)
                REFERENCES repositories(repository_id),
            FOREIGN KEY (source_branch_id)
                REFERENCES branches(branch_id),
            FOREIGN KEY (target_branch_id)
                REFERENCES branches(branch_id)
        );

        CREATE TABLE IF NOT EXISTS commits (
            commit_id INTEGER PRIMARY KEY,
            pull_request_id INTEGER NOT NULL,
            sha TEXT NOT NULL UNIQUE,
            message TEXT NOT NULL,
            FOREIGN KEY (pull_request_id)
                REFERENCES pull_requests(pull_request_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reviewers (
            reviewer_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1
                CHECK (active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY,
            pull_request_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            state TEXT NOT NULL
                CHECK (state IN ('commented', 'changes_requested', 'approved')),
            commit_sha TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pull_request_id)
                REFERENCES pull_requests(pull_request_id)
                ON DELETE CASCADE,
            FOREIGN KEY (reviewer_id)
                REFERENCES reviewers(reviewer_id),
            UNIQUE(pull_request_id, reviewer_id, commit_sha)
        );

        CREATE TABLE IF NOT EXISTS review_comments (
            comment_id INTEGER PRIMARY KEY,
            review_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            line_number INTEGER NOT NULL CHECK (line_number > 0),
            body TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
                CHECK (resolved IN (0, 1)),
            FOREIGN KEY (review_id)
                REFERENCES reviews(review_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS status_checks (
            status_check_id INTEGER PRIMARY KEY,
            pull_request_id INTEGER NOT NULL,
            check_name TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'passed', 'failed')),
            FOREIGN KEY (pull_request_id)
                REFERENCES pull_requests(pull_request_id)
                ON DELETE CASCADE,
            UNIQUE(pull_request_id, check_name)
        );

        CREATE TABLE IF NOT EXISTS branch_protection (
            branch_protection_id INTEGER PRIMARY KEY,
            branch_id INTEGER NOT NULL UNIQUE,
            required_approvals INTEGER NOT NULL
                CHECK (required_approvals >= 0),
            require_status_checks INTEGER NOT NULL
                CHECK (require_status_checks IN (0, 1)),
            restrict_direct_push INTEGER NOT NULL
                CHECK (restrict_direct_push IN (0, 1)),
            allow_force_push INTEGER NOT NULL DEFAULT 0
                CHECK (allow_force_push IN (0, 1)),
            require_conversation_resolution INTEGER NOT NULL DEFAULT 1
                CHECK (require_conversation_resolution IN (0, 1)),
            FOREIGN KEY (branch_id)
                REFERENCES branches(branch_id)
                ON DELETE CASCADE
        );
        """

        with closing(connection.cursor()) as cursor:
            cursor.executescript(schema)

    def seed_data(self) -> None:
        connection = self.require_connection()

        connection.execute("BEGIN")
        try:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO repositories(name, default_branch)
                    VALUES (?, ?)
                    """,
                    ("payments-service", "main"),
                )

                repository = cursor.execute(
                    """
                    SELECT repository_id
                    FROM repositories
                    WHERE name = ?
                    """,
                    ("payments-service",),
                ).fetchone()

                if repository is None:
                    raise DatabaseError("Repository creation failed")

                repository_id = repository["repository_id"]

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO branches(repository_id, name, protected)
                    VALUES (?, ?, ?)
                    """,
                    (repository_id, "main", 1),
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO branches(repository_id, name, protected)
                    VALUES (?, ?, ?)
                    """,
                    (repository_id, "feature/payment-timeout", 0),
                )

                branches = cursor.execute(
                    """
                    SELECT branch_id, name
                    FROM branches
                    WHERE repository_id = ?
                    """,
                    (repository_id,),
                ).fetchall()

                branch_map = {row["name"]: row["branch_id"] for row in branches}

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO branch_protection(
                        branch_id,
                        required_approvals,
                        require_status_checks,
                        restrict_direct_push,
                        allow_force_push,
                        require_conversation_resolution
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        branch_map["main"],
                        2,
                        1,
                        1,
                        0,
                        1,
                    ),
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO pull_requests(
                        repository_id,
                        source_branch_id,
                        target_branch_id,
                        title,
                        state,
                        merge_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repository_id,
                        branch_map["feature/payment-timeout"],
                        branch_map["main"],
                        "Increase payment gateway timeout",
                        "open",
                        "blocked",
                    ),
                )

                pull_request = cursor.execute(
                    """
                    SELECT pull_request_id
                    FROM pull_requests
                    WHERE repository_id = ?
                      AND title = ?
                    """,
                    (
                        repository_id,
                        "Increase payment gateway timeout",
                    ),
                ).fetchone()

                if pull_request is None:
                    raise DatabaseError("Pull request creation failed")

                pr_id = pull_request["pull_request_id"]

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO commits(
                        pull_request_id,
                        sha,
                        message
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        pr_id,
                        "a1b2c3d4",
                        "Increase gateway timeout from 10s to 30s",
                    ),
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO reviewers(username, active)
                    VALUES (?, ?)
                    """,
                    ("reviewer.alice", 1),
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO reviewers(username, active)
                    VALUES (?, ?)
                    """,
                    ("reviewer.bob", 1),
                )

                reviewers = cursor.execute(
                    """
                    SELECT reviewer_id, username
                    FROM reviewers
                    WHERE username IN (?, ?)
                    """,
                    ("reviewer.alice", "reviewer.bob"),
                ).fetchall()

                reviewer_map = {
                    row["username"]: row["reviewer_id"]
                    for row in reviewers
                }

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO reviews(
                        pull_request_id,
                        reviewer_id,
                        state,
                        commit_sha
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        pr_id,
                        reviewer_map["reviewer.alice"],
                        "approved",
                        "a1b2c3d4",
                    ),
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO reviews(
                        pull_request_id,
                        reviewer_id,
                        state,
                        commit_sha
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        pr_id,
                        reviewer_map["reviewer.bob"],
                        "approved",
                        "a1b2c3d4",
                    ),
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO status_checks(
                        pull_request_id,
                        check_name,
                        status
                    )
                    VALUES (?, ?, ?)
                    """,
                    (pr_id, "unit-tests", "passed"),
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO status_checks(
                        pull_request_id,
                        check_name,
                        status
                    )
                    VALUES (?, ?, ?)
                    """,
                    (pr_id, "security-scan", "passed"),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def add_review_comment(
        self,
        pull_request_id: int,
        reviewer_username: str,
        commit_sha: str,
        file_path: str,
        line_number: int,
        body: str,
    ) -> int:
        connection = self.require_connection()

        if line_number <= 0:
            raise ValueError("Line number must be positive")
        if not body.strip():
            raise ValueError("Comment body cannot be empty")

        connection.execute("BEGIN")
        try:
            with closing(connection.cursor()) as cursor:
                reviewer = cursor.execute(
                    """
                    SELECT reviewer_id
                    FROM reviewers
                    WHERE username = ?
                      AND active = 1
                    """,
                    (reviewer_username,),
                ).fetchone()

                if reviewer is None:
                    raise DatabaseError("Reviewer is not active")

                review = cursor.execute(
                    """
                    SELECT review_id
                    FROM reviews
                    WHERE pull_request_id = ?
                      AND reviewer_id = ?
                      AND commit_sha = ?
                    """,
                    (
                        pull_request_id,
                        reviewer["reviewer_id"],
                        commit_sha,
                    ),
                ).fetchone()

                if review is None:
                    raise DatabaseError(
                        "A review for this commit is required before "
                        "adding an inline comment"
                    )

                cursor.execute(
                    """
                    INSERT INTO review_comments(
                        review_id,
                        file_path,
                        line_number,
                        body
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        review["review_id"],
                        file_path,
                        line_number,
                        body,
                    ),
                )

                comment_id = cursor.lastrowid

            connection.commit()
            return int(comment_id)
        except Exception:
            connection.rollback()
            raise

    def merge_eligibility(self, pull_request_id: int) -> dict:
        connection = self.require_connection()

        query = """
        WITH pr AS (
            SELECT
                p.pull_request_id,
                p.state,
                p.target_branch_id,
                bp.required_approvals,
                bp.require_status_checks,
                bp.require_conversation_resolution
            FROM pull_requests p
            JOIN branch_protection bp
              ON bp.branch_id = p.target_branch_id
            WHERE p.pull_request_id = ?
        ),
        approvals AS (
            SELECT COUNT(DISTINCT reviewer_id) AS approved_count
            FROM reviews
            WHERE pull_request_id = ?
              AND state = 'approved'
              AND commit_sha = (
                  SELECT c.sha
                  FROM commits c
                  WHERE c.pull_request_id = ?
                  ORDER BY c.commit_id DESC
                  LIMIT 1
              )
        ),
        checks AS (
            SELECT
                COUNT(*) AS total_checks,
                COUNT(*) FILTER (WHERE status = 'passed') AS passed_checks
            FROM status_checks
            WHERE pull_request_id = ?
        ),
        unresolved AS (
            SELECT COUNT(*) AS unresolved_comments
            FROM review_comments rc
            JOIN reviews r ON r.review_id = rc.review_id
            WHERE r.pull_request_id = ?
              AND rc.resolved = 0
        )
        SELECT
            pr.state,
            pr.required_approvals,
            approvals.approved_count,
            checks.total_checks,
            checks.passed_checks,
            unresolved.unresolved_comments,
            CASE
                WHEN pr.state <> 'open' THEN 0
                WHEN approvals.approved_count < pr.required_approvals THEN 0
                WHEN pr.require_status_checks = 1
                     AND (
                         checks.total_checks = 0
                         OR checks.total_checks <> checks.passed_checks
                     ) THEN 0
                WHEN pr.require_conversation_resolution = 1
                     AND unresolved.unresolved_comments > 0 THEN 0
                ELSE 1
            END AS merge_allowed
        FROM pr
        CROSS JOIN approvals
        CROSS JOIN checks
        CROSS JOIN unresolved
        """

        with closing(connection.cursor()) as cursor:
            row = cursor.execute(
                query,
                (
                    pull_request_id,
                    pull_request_id,
                    pull_request_id,
                    pull_request_id,
                    pull_request_id,
                ),
            ).fetchone()

        if row is None:
            raise DatabaseError("Pull request or branch policy not found")

        return dict(row)

    def list_open_pull_requests(self) -> list[sqlite3.Row]:
        connection = self.require_connection()

        with closing(connection.cursor()) as cursor:
            return cursor.execute(
                """
                SELECT
                    p.pull_request_id,
                    p.title,
                    source.name AS source_branch,
                    target.name AS target_branch,
                    p.state,
                    p.merge_status
                FROM pull_requests p
                JOIN branches source
                  ON source.branch_id = p.source_branch_id
                JOIN branches target
                  ON target.branch_id = p.target_branch_id
                WHERE p.state = 'open'
                ORDER BY p.pull_request_id
                """
            ).fetchall()

    def demonstrate_parameterized_query(self, title: str) -> Optional[dict]:
        """
        Parameters are bound by the database driver rather than concatenated
        into SQL. This prevents a user-controlled title from changing SQL
        syntax and is the standard approach for application queries.
        """
        connection = self.require_connection()

        with closing(connection.cursor()) as cursor:
            row = cursor.execute(
                """
                SELECT pull_request_id, title, state
                FROM pull_requests
                WHERE title = ?
                """,
                (title,),
            ).fetchone()

        return dict(row) if row else None


def demonstrate_transaction_rollback(database: RepositoryDatabase) -> None:
    connection = database.require_connection()

    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO reviewers(username, active)
            VALUES (?, ?)
            """,
            ("transaction-demo", 1),
        )

        # This deliberately violates the UNIQUE constraint. The entire
        # transaction is rolled back, including the preceding insert.
        connection.execute(
            """
            INSERT INTO reviewers(username, active)
            VALUES (?, ?)
            """,
            ("transaction-demo", 1),
        )

        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"Transaction rolled back after integrity error: {exc}")


def main() -> None:
    database = RepositoryDatabase(str(DATABASE))

    try:
        database.connect()
        print("Connection opened")

        database.create_schema()
        print("Schema created or already present")

        database.seed_data()
        print("Sample repository workflow loaded")

        print("\nOpen pull requests:")
        for pull_request in database.list_open_pull_requests():
            print(
                f"PR #{pull_request['pull_request_id']}: "
                f"{pull_request['source_branch']} -> "
                f"{pull_request['target_branch']} | "
                f"{pull_request['title']}"
            )

        eligibility = database.merge_eligibility(1)
        print("\nMerge eligibility:")
        for key, value in eligibility.items():
            print(f"{key}: {value}")

        safe_lookup = database.demonstrate_parameterized_query(
            "Increase payment gateway timeout"
        )
        print("\nParameterized query result:")
        print(safe_lookup)

        comment_id = database.add_review_comment(
            pull_request_id=1,
            reviewer_username="reviewer.alice",
            commit_sha="a1b2c3d4",
            file_path="src/payment_gateway.py",
            line_number=42,
            body="The timeout should remain configurable rather than hard-coded.",
        )
        print(f"\nReview comment created with ID {comment_id}")

        # The unresolved comment now blocks merging because the branch policy
        # requires all review conversations to be resolved.
        blocked = database.merge_eligibility(1)
        print("\nEligibility after unresolved review comment:")
        print(blocked)

        connection = database.require_connection()
        connection.execute(
            """
            UPDATE review_comments
            SET resolved = 1
            WHERE comment_id = ?
            """,
            (comment_id,),
        )
        connection.commit()

        ready = database.merge_eligibility(1)
        print("\nEligibility after resolving the conversation:")
        print(ready)

        demonstrate_transaction_rollback(database)

        print("\nDatabase connection remains open while work is active.")

    except (sqlite3.Error, DatabaseError, ValueError) as exc:
        print(f"Database workflow failed: {exc}")
    finally:
        database.close()
        print("Connection closed")


if __name__ == "__main__":
    main()

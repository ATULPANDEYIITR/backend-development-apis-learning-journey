-- PostgreSQL database-connectivity case study:
-- repository workflow data with explicit relational integrity.
--
-- The script demonstrates database connectivity at the SQL layer through:
-- schemas, constraints, indexes, transactions, CTEs, views, functions,
-- parameter-oriented query design, and integrity failures.
--
-- Run this script against a PostgreSQL database.

BEGIN;

DROP VIEW IF EXISTS merge_eligibility;
DROP TABLE IF EXISTS review_comments CASCADE;
DROP TABLE IF EXISTS status_checks CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS reviewers CASCADE;
DROP TABLE IF EXISTS commits CASCADE;
DROP TABLE IF EXISTS pull_requests CASCADE;
DROP TABLE IF EXISTS branch_protection CASCADE;
DROP TABLE IF EXISTS branches CASCADE;
DROP TABLE IF EXISTS repositories CASCADE;

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    default_branch TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(name)) > 0),
    CHECK (length(trim(default_branch)) > 0)
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repository_id, name),
    CHECK (length(trim(name)) > 0)
);

CREATE TABLE branch_protection (
    branch_id BIGINT PRIMARY KEY
        REFERENCES branches(branch_id)
        ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 0,
    require_status_checks BOOLEAN NOT NULL DEFAULT FALSE,
    restrict_direct_push BOOLEAN NOT NULL DEFAULT TRUE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_approvals >= 0)
);

CREATE TABLE pull_requests (
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
    head_sha TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_at TIMESTAMPTZ,
    CHECK (length(head_sha) >= 7),
    CHECK (length(base_sha) >= 7),
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    sha TEXT NOT NULL UNIQUE,
    message TEXT NOT NULL,
    authored_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(sha) >= 7),
    CHECK (length(trim(message)) > 0)
);

CREATE TABLE reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (length(trim(username)) > 0)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    state TEXT NOT NULL
        CHECK (state IN ('commented', 'changes_requested', 'approved')),
    commit_sha TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES reviews(review_id)
        ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (line_number > 0),
    CHECK (length(trim(body)) > 0)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('pending', 'passed', 'failed')),
    completed_at TIMESTAMPTZ,
    UNIQUE(pull_request_id, check_name)
);

CREATE INDEX idx_branches_repository
    ON branches(repository_id);

CREATE INDEX idx_pull_requests_target_branch
    ON pull_requests(target_branch_id);

CREATE INDEX idx_pull_requests_state
    ON pull_requests(state);

CREATE INDEX idx_reviews_pull_request
    ON reviews(pull_request_id);

CREATE INDEX idx_review_comments_review
    ON review_comments(review_id);

CREATE INDEX idx_status_checks_pull_request
    ON status_checks(pull_request_id);

INSERT INTO repositories(name, default_branch)
VALUES ('payments-platform', 'main');

INSERT INTO branches(repository_id, name, protected)
SELECT repository_id, 'main', TRUE
FROM repositories
WHERE name = 'payments-platform';

INSERT INTO branches(repository_id, name, protected)
SELECT repository_id, 'feature/payment-timeout', FALSE
FROM repositories
WHERE name = 'payments-platform';

INSERT INTO branch_protection(
    branch_id,
    required_approvals,
    require_status_checks,
    restrict_direct_push,
    allow_force_push,
    require_conversation_resolution,
    require_linear_history
)
SELECT
    b.branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    TRUE,
    TRUE
FROM branches b
JOIN repositories r
  ON r.repository_id = b.repository_id
WHERE r.name = 'payments-platform'
  AND b.name = 'main';

INSERT INTO pull_requests(
    repository_id,
    source_branch_id,
    target_branch_id,
    title,
    state,
    head_sha,
    base_sha
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    'Increase payment gateway timeout',
    'open',
    'a1b2c3d4e5f6',
    '001122334455'
FROM repositories r
JOIN branches source
  ON source.repository_id = r.repository_id
 AND source.name = 'feature/payment-timeout'
JOIN branches target
  ON target.repository_id = r.repository_id
 AND target.name = 'main'
WHERE r.name = 'payments-platform';

INSERT INTO commits(
    pull_request_id,
    sha,
    message
)
SELECT
    pull_request_id,
    'a1b2c3d4e5f6',
    'Increase payment gateway timeout to 30 seconds'
FROM pull_requests
WHERE title = 'Increase payment gateway timeout';

INSERT INTO reviewers(username)
VALUES
    ('alice'),
    ('bob'),
    ('security-reviewer');

INSERT INTO reviews(
    pull_request_id,
    reviewer_id,
    state,
    commit_sha
)
SELECT
    p.pull_request_id,
    r.reviewer_id,
    'approved',
    p.head_sha
FROM pull_requests p
CROSS JOIN reviewers r
WHERE p.title = 'Increase payment gateway timeout'
  AND r.username IN ('alice', 'bob');

INSERT INTO reviews(
    pull_request_id,
    reviewer_id,
    state,
    commit_sha
)
SELECT
    p.pull_request_id,
    r.reviewer_id,
    'commented',
    p.head_sha
FROM pull_requests p
JOIN reviewers r
  ON r.username = 'security-reviewer'
WHERE p.title = 'Increase payment gateway timeout';

INSERT INTO review_comments(
    review_id,
    file_path,
    line_number,
    body,
    resolved
)
SELECT
    review_id,
    'src/payment_gateway.py',
    42,
    'The timeout should be configurable by deployment environment.',
    FALSE
FROM reviews
WHERE state = 'commented'
  AND reviewer_id = (
      SELECT reviewer_id
      FROM reviewers
      WHERE username = 'security-reviewer'
  );

INSERT INTO status_checks(
    pull_request_id,
    check_name,
    status,
    completed_at
)
SELECT
    pull_request_id,
    'unit-tests',
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests
WHERE title = 'Increase payment gateway timeout';

INSERT INTO status_checks(
    pull_request_id,
    check_name,
    status,
    completed_at
)
SELECT
    pull_request_id,
    'security-scan',
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests
WHERE title = 'Increase payment gateway timeout';

CREATE VIEW merge_eligibility AS
WITH current_pr AS (
    SELECT
        p.pull_request_id,
        p.title,
        p.state,
        p.head_sha,
        bp.required_approvals,
        bp.require_status_checks,
        bp.require_conversation_resolution,
        bp.require_linear_history
    FROM pull_requests p
    JOIN branch_protection bp
      ON bp.branch_id = p.target_branch_id
),
approval_summary AS (
    SELECT
        p.pull_request_id,
        COUNT(DISTINCT r.reviewer_id) FILTER (
            WHERE r.state = 'approved'
              AND r.commit_sha = p.head_sha
        ) AS approvals
    FROM pull_requests p
    LEFT JOIN reviews r
      ON r.pull_request_id = p.pull_request_id
    GROUP BY p.pull_request_id, p.head_sha
),
check_summary AS (
    SELECT
        pull_request_id,
        COUNT(*) AS total_checks,
        COUNT(*) FILTER (
            WHERE status = 'passed'
        ) AS passed_checks
    FROM status_checks
    GROUP BY pull_request_id
),
conversation_summary AS (
    SELECT
        r.pull_request_id,
        COUNT(*) FILTER (
            WHERE rc.resolved = FALSE
        ) AS unresolved_comments
    FROM reviews r
    LEFT JOIN review_comments rc
      ON rc.review_id = r.review_id
    GROUP BY r.pull_request_id
)
SELECT
    p.pull_request_id,
    p.title,
    p.state,
    a.approvals,
    p.required_approvals,
    COALESCE(c.total_checks, 0) AS total_checks,
    COALESCE(c.passed_checks, 0) AS passed_checks,
    COALESCE(v.unresolved_comments, 0) AS unresolved_comments,
    (
        p.state = 'open'
        AND a.approvals >= p.required_approvals
        AND (
            p.require_status_checks = FALSE
            OR (
                COALESCE(c.total_checks, 0) > 0
                AND c.total_checks = c.passed_checks
            )
        )
        AND (
            p.require_conversation_resolution = FALSE
            OR COALESCE(v.unresolved_comments, 0) = 0
        )
    ) AS merge_allowed
FROM current_pr p
JOIN approval_summary a
  ON a.pull_request_id = p.pull_request_id
LEFT JOIN check_summary c
  ON c.pull_request_id = p.pull_request_id
LEFT JOIN conversation_summary v
  ON v.pull_request_id = p.pull_request_id;

SELECT *
FROM merge_eligibility
ORDER BY pull_request_id;

UPDATE review_comments
SET resolved = TRUE
WHERE comment_id = (
    SELECT rc.comment_id
    FROM review_comments rc
    JOIN reviews r
      ON r.review_id = rc.review_id
    JOIN pull_requests p
      ON p.pull_request_id = r.pull_request_id
    WHERE p.title = 'Increase payment gateway timeout'
      AND rc.resolved = FALSE
    ORDER BY rc.comment_id
    LIMIT 1
);

SELECT *
FROM merge_eligibility
WHERE title = 'Increase payment gateway timeout';

BEGIN;

UPDATE status_checks
SET status = 'failed',
    completed_at = CURRENT_TIMESTAMP
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE title = 'Increase payment gateway timeout'
)
AND check_name = 'security-scan';

SELECT
    pull_request_id,
    title,
    approvals,
    total_checks,
    passed_checks,
    unresolved_comments,
    merge_allowed
FROM merge_eligibility
WHERE title = 'Increase payment gateway timeout';

ROLLBACK;

BEGIN;

UPDATE status_checks
SET status = 'passed',
    completed_at = CURRENT_TIMESTAMP
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE title = 'Increase payment gateway timeout'
)
AND check_name = 'security-scan';

COMMIT;

-- Parameter values should be bound by the application driver rather than
-- interpolated into SQL. The following query illustrates the SQL shape that
-- a prepared statement should execute.
PREPARE find_pull_request(TEXT) AS
    SELECT
        pull_request_id,
        title,
        state,
        head_sha
    FROM pull_requests
    WHERE title = $1;

EXECUTE find_pull_request(
    'Increase payment gateway timeout'
);

DEALLOCATE find_pull_request;

-- Database-level integrity demonstration:
-- the following statement is intentionally invalid because a foreign key
-- references a non-existent repository. It is left commented so that the
-- complete script remains executable.
--
-- INSERT INTO branches(repository_id, name)
-- VALUES (999999999, 'invalid-branch');

COMMIT;

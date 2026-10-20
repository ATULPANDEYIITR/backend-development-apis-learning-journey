CREATE SCHEMA IF NOT EXISTS repository_governance;

CREATE TYPE repository_governance.pull_request_state AS ENUM
    ('draft', 'open', 'closed', 'merged');

CREATE TYPE repository_governance.review_state AS ENUM
    ('commented', 'approved', 'changes_requested', 'dismissed');

CREATE TYPE repository_governance.merge_strategy AS ENUM
    ('merge', 'squash', 'rebase');

CREATE TABLE repository_governance.repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    default_branch VARCHAR(100) NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(name)) > 0),
    CHECK (length(trim(default_branch)) > 0)
);

CREATE TABLE repository_governance.branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository_governance.repositories(repository_id)
        ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, name),
    CHECK (length(trim(name)) > 0)
);

CREATE TABLE repository_governance.reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    eligible BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (length(trim(username)) > 0)
);

CREATE TABLE repository_governance.pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository_governance.repositories(repository_id)
        ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    source_branch VARCHAR(100) NOT NULL,
    target_branch VARCHAR(100) NOT NULL,
    state repository_governance.pull_request_state NOT NULL DEFAULT 'open',
    merge_strategy repository_governance.merge_strategy NOT NULL DEFAULT 'squash',
    commit_count INTEGER NOT NULL DEFAULT 1,
    base_commit_sha VARCHAR(64),
    head_commit_sha VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(title)) >= 5),
    CHECK (source_branch <> target_branch),
    CHECK (commit_count >= 1)
);

CREATE TABLE repository_governance.reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES repository_governance.pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_governance.reviewers(reviewer_id)
        ON DELETE RESTRICT,
    state repository_governance.review_state NOT NULL,
    body TEXT,
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE repository_governance.review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES repository_governance.reviews(review_id)
        ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (line_number > 0),
    CHECK (length(trim(body)) > 0)
);

CREATE TABLE repository_governance.status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES repository_governance.pull_requests(pull_request_id)
        ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    passed BOOLEAN NOT NULL,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, name)
);

CREATE TABLE repository_governance.branch_protection (
    protection_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL UNIQUE
        REFERENCES repository_governance.repositories(repository_id)
        ON DELETE CASCADE,
    required_reviews INTEGER NOT NULL DEFAULT 1,
    require_status_checks BOOLEAN NOT NULL DEFAULT TRUE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_direct_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_force_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_deletion BOOLEAN NOT NULL DEFAULT TRUE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_administrator_bypass BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_reviews BETWEEN 0 AND 20)
);

CREATE TABLE repository_governance.commits (
    commit_sha VARCHAR(64) PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository_governance.repositories(repository_id)
        ON DELETE CASCADE,
    branch_id BIGINT
        REFERENCES repository_governance.branches(branch_id)
        ON DELETE SET NULL,
    message TEXT NOT NULL,
    author VARCHAR(100) NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(message)) > 0),
    CHECK (length(trim(author)) > 0)
);

CREATE INDEX idx_pr_repository_state
    ON repository_governance.pull_requests(repository_id, state);

CREATE INDEX idx_review_pr_state
    ON repository_governance.reviews(pull_request_id, state);

CREATE INDEX idx_status_check_pr
    ON repository_governance.status_checks(pull_request_id);

CREATE INDEX idx_comment_review_resolution
    ON repository_governance.review_comments(review_id, resolved);

INSERT INTO repository_governance.repositories (name, default_branch)
VALUES ('payments-service', 'main')
ON CONFLICT (name) DO NOTHING;

INSERT INTO repository_governance.branches (repository_id, name, protected)
SELECT repository_id, branch_name, branch_name = 'main'
FROM repository_governance.repositories
CROSS JOIN (VALUES ('main'), ('develop'), ('feature/idempotency')) AS b(branch_name)
WHERE name = 'payments-service'
ON CONFLICT (repository_id, name) DO NOTHING;

INSERT INTO repository_governance.reviewers (username, eligible)
VALUES
    ('alice', TRUE),
    ('bob', TRUE),
    ('contractor', FALSE)
ON CONFLICT (username) DO NOTHING;

INSERT INTO repository_governance.branch_protection (
    repository_id,
    required_reviews,
    require_status_checks,
    require_conversation_resolution,
    restrict_direct_push,
    restrict_force_push,
    restrict_deletion,
    require_linear_history,
    allow_administrator_bypass
)
SELECT repository_id, 2, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE
FROM repository_governance.repositories
WHERE name = 'payments-service'
ON CONFLICT (repository_id)
DO UPDATE SET
    required_reviews = EXCLUDED.required_reviews,
    require_status_checks = EXCLUDED.require_status_checks,
    require_conversation_resolution = EXCLUDED.require_conversation_resolution,
    restrict_direct_push = EXCLUDED.restrict_direct_push,
    restrict_force_push = EXCLUDED.restrict_force_push,
    restrict_deletion = EXCLUDED.restrict_deletion,
    require_linear_history = EXCLUDED.require_linear_history,
    allow_administrator_bypass = EXCLUDED.allow_administrator_bypass;

INSERT INTO repository_governance.pull_requests (
    repository_id,
    title,
    source_branch,
    target_branch,
    state,
    merge_strategy,
    commit_count
)
SELECT repository_id,
       'Add transaction idempotency',
       'feature/idempotency',
       'main',
       'open',
       'squash',
       3
FROM repository_governance.repositories
WHERE name = 'payments-service';

INSERT INTO repository_governance.status_checks (
    pull_request_id,
    name,
    passed,
    completed_at
)
SELECT pull_request_id, check_name, TRUE, CURRENT_TIMESTAMP
FROM repository_governance.pull_requests
CROSS JOIN (
    VALUES ('build'), ('unit-tests'), ('security-scan')
) AS checks(check_name)
WHERE title = 'Add transaction idempotency';

INSERT INTO repository_governance.reviews (
    pull_request_id,
    reviewer_id,
    state,
    stale
)
SELECT pr.pull_request_id, r.reviewer_id, 'approved', FALSE
FROM repository_governance.pull_requests pr
JOIN repository_governance.reviewers r
  ON r.username IN ('alice', 'bob')
WHERE pr.title = 'Add transaction idempotency';

INSERT INTO repository_governance.review_comments (
    review_id,
    file_path,
    line_number,
    body,
    resolved
)
SELECT review_id,
       'src/payment.py',
       42,
       'Explain the retry boundary.',
       FALSE
FROM repository_governance.reviews
WHERE review_id = (
    SELECT min(review_id)
    FROM repository_governance.reviews
    WHERE state = 'approved'
);

CREATE OR REPLACE FUNCTION repository_governance.touch_pull_request()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_touch_pull_request
BEFORE UPDATE ON repository_governance.pull_requests
FOR EACH ROW
EXECUTE FUNCTION repository_governance.touch_pull_request();

CREATE OR REPLACE FUNCTION repository_governance.merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE sql
AS $$
WITH pr AS (
    SELECT
        p.pull_request_id,
        p.state,
        p.target_branch,
        p.merge_strategy,
        p.repository_id
    FROM repository_governance.pull_requests p
    WHERE p.pull_request_id = p_pull_request_id
),
policy AS (
    SELECT bp.*
    FROM repository_governance.branch_protection bp
    JOIN pr ON pr.repository_id = bp.repository_id
),
approval_count AS (
    SELECT COUNT(DISTINCT r.reviewer_id) AS count
    FROM repository_governance.reviews r
    JOIN repository_governance.reviewers rv
      ON rv.reviewer_id = r.reviewer_id
    WHERE r.pull_request_id = p_pull_request_id
      AND r.state = 'approved'
      AND r.stale = FALSE
      AND rv.eligible = TRUE
),
failed_checks AS (
    SELECT COUNT(*) AS count
    FROM repository_governance.status_checks sc
    WHERE sc.pull_request_id = p_pull_request_id
      AND sc.passed = FALSE
),
unresolved_comments AS (
    SELECT COUNT(*) AS count
    FROM repository_governance.review_comments rc
    JOIN repository_governance.reviews r
      ON r.review_id = rc.review_id
    WHERE r.pull_request_id = p_pull_request_id
      AND r.stale = FALSE
      AND rc.resolved = FALSE
),
requested_changes AS (
    SELECT COUNT(*) AS count
    FROM repository_governance.reviews r
    WHERE r.pull_request_id = p_pull_request_id
      AND r.state = 'changes_requested'
      AND r.stale = FALSE
)
SELECT
    FALSE,
    CASE
        WHEN pr.state <> 'open'
            THEN 'Pull Request is not open'
        WHEN COALESCE(approval_count.count, 0) < policy.required_reviews
            THEN 'Insufficient eligible approvals'
        WHEN policy.require_status_checks
             AND NOT EXISTS (
                 SELECT 1
                 FROM repository_governance.status_checks sc
                 WHERE sc.pull_request_id = p_pull_request_id
             )
            THEN 'Required status checks have not run'
        WHEN failed_checks.count > 0
            THEN 'One or more status checks failed'
        WHEN requested_changes.count > 0
            THEN 'An active reviewer requested changes'
        WHEN policy.require_conversation_resolution
             AND unresolved_comments.count > 0
            THEN 'Unresolved review conversations remain'
        WHEN policy.require_linear_history
             AND pr.merge_strategy = 'merge'
            THEN 'Merge strategy violates linear-history policy'
        ELSE NULL
    END
FROM pr
JOIN policy ON TRUE
CROSS JOIN approval_count
CROSS JOIN failed_checks
CROSS JOIN unresolved_comments
CROSS JOIN requested_changes
WHERE
    pr.state <> 'open'
    OR approval_count.count < policy.required_reviews
    OR (
        policy.require_status_checks
        AND NOT EXISTS (
            SELECT 1
            FROM repository_governance.status_checks sc
            WHERE sc.pull_request_id = p_pull_request_id
        )
    )
    OR failed_checks.count > 0
    OR requested_changes.count > 0
    OR (
        policy.require_conversation_resolution
        AND unresolved_comments.count > 0
    )
    OR (
        policy.require_linear_history
        AND pr.merge_strategy = 'merge'
    )

UNION ALL

SELECT TRUE, 'Pull Request satisfies merge policy'
FROM pr
JOIN policy ON TRUE
CROSS JOIN approval_count
CROSS JOIN failed_checks
CROSS JOIN unresolved_comments
CROSS JOIN requested_changes
WHERE
    pr.state = 'open'
    AND approval_count.count >= policy.required_reviews
    AND (
        NOT policy.require_status_checks
        OR (
            EXISTS (
                SELECT 1
                FROM repository_governance.status_checks sc
                WHERE sc.pull_request_id = p_pull_request_id
            )
            AND failed_checks.count = 0
        )
    )
    AND requested_changes.count = 0
    AND (
        NOT policy.require_conversation_resolution
        OR unresolved_comments.count = 0
    )
    AND (
        NOT policy.require_linear_history
        OR pr.merge_strategy <> 'merge'
    );
$$;

-- Pull Request lifecycle query.
SELECT
    pull_request_id,
    title,
    source_branch,
    target_branch,
    state,
    merge_strategy,
    commit_count
FROM repository_governance.pull_requests
WHERE repository_id = (
    SELECT repository_id
    FROM repository_governance.repositories
    WHERE name = 'payments-service'
)
ORDER BY created_at DESC;

-- Review and approval audit.
SELECT
    pr.pull_request_id,
    pr.title,
    rv.username,
    r.state,
    r.stale,
    rv.eligible
FROM repository_governance.pull_requests pr
JOIN repository_governance.reviews r
  ON r.pull_request_id = pr.pull_request_id
JOIN repository_governance.reviewers rv
  ON rv.reviewer_id = r.reviewer_id
ORDER BY pr.pull_request_id, r.submitted_at;

-- Status-check report.
SELECT
    pr.pull_request_id,
    pr.title,
    sc.name,
    sc.passed
FROM repository_governance.pull_requests pr
JOIN repository_governance.status_checks sc
  ON sc.pull_request_id = pr.pull_request_id
ORDER BY pr.pull_request_id, sc.name;

-- Merge-eligibility report.
SELECT *
FROM repository_governance.merge_eligibility(
    (
        SELECT pull_request_id
        FROM repository_governance.pull_requests
        WHERE title = 'Add transaction idempotency'
        ORDER BY pull_request_id DESC
        LIMIT 1
    )
);

-- Demonstrate transactionally changing an approval to stale after new changes.
BEGIN;

UPDATE repository_governance.reviews
SET stale = TRUE
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM repository_governance.pull_requests
    WHERE title = 'Add transaction idempotency'
    ORDER BY pull_request_id DESC
    LIMIT 1
)
AND state = 'approved';

UPDATE repository_governance.pull_requests
SET updated_at = CURRENT_TIMESTAMP
WHERE title = 'Add transaction idempotency';

COMMIT;

-- The updated decision now reflects stale approvals.
SELECT *
FROM repository_governance.merge_eligibility(
    (
        SELECT pull_request_id
        FROM repository_governance.pull_requests
        WHERE title = 'Add transaction idempotency'
        ORDER BY pull_request_id DESC
        LIMIT 1
    )
);

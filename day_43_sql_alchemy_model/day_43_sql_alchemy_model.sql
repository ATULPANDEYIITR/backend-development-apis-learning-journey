DROP SCHEMA IF EXISTS repository_governance CASCADE;

CREATE SCHEMA repository_governance;

SET search_path TO repository_governance;

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    branch_name VARCHAR(150) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (repository_id, branch_name)
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branches(branch_id)
        ON DELETE CASCADE,

    required_approvals INTEGER NOT NULL DEFAULT 1
        CHECK (required_approvals >= 0),

    require_status_checks BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_direct_pushes BOOLEAN NOT NULL DEFAULT TRUE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,

    author_id BIGINT NOT NULL
        REFERENCES users(user_id),

    source_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),

    target_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),

    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    state VARCHAR(30) NOT NULL DEFAULT 'open'
        CHECK (state IN ('draft', 'open', 'closed', 'merged')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,

    commit_sha CHAR(40) NOT NULL UNIQUE,
    commit_message VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (commit_sha ~ '^[0-9a-fA-F]{40}$')
);

CREATE TABLE pull_request_reviewers (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,

    reviewer_id BIGINT NOT NULL
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (pull_request_id, reviewer_id)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,

    reviewer_id BIGINT NOT NULL
        REFERENCES users(user_id),

    review_state VARCHAR(30) NOT NULL
        CHECK (
            review_state IN (
                'pending',
                'commented',
                'approved',
                'changes_requested',
                'dismissed'
            )
        ),

    review_body TEXT NOT NULL DEFAULT '',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES reviews(review_id)
        ON DELETE CASCADE,

    file_path VARCHAR(500) NOT NULL,
    line_number INTEGER,
    comment_body TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (line_number IS NULL OR line_number > 0)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,

    check_name VARCHAR(150) NOT NULL,
    check_state VARCHAR(30) NOT NULL
        CHECK (
            check_state IN (
                'pending',
                'passed',
                'failed'
            )
        ),

    completed_at TIMESTAMPTZ,

    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE merge_events (
    merge_event_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL UNIQUE
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,

    merged_by BIGINT NOT NULL
        REFERENCES users(user_id),

    merge_strategy VARCHAR(30) NOT NULL
        CHECK (
            merge_strategy IN (
                'merge_commit',
                'squash',
                'rebase'
            )
        ),

    merged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Prevent the most obvious invalid Pull Request reviewer relationship:
-- an author should not appear as an assigned reviewer.
CREATE OR REPLACE FUNCTION prevent_author_reviewer_assignment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    pr_author BIGINT;
BEGIN
    SELECT author_id
    INTO pr_author
    FROM pull_requests
    WHERE pull_request_id = NEW.pull_request_id;

    IF pr_author = NEW.reviewer_id THEN
        RAISE EXCEPTION
            'Pull Request author cannot be assigned as reviewer';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_author_reviewer_assignment
BEFORE INSERT OR UPDATE
ON pull_request_reviewers
FOR EACH ROW
EXECUTE FUNCTION prevent_author_reviewer_assignment();


-- The trigger also prevents a user who was never assigned as a reviewer
-- from inserting an approval. This places an important governance rule at
-- the database boundary instead of relying only on application validation.
CREATE OR REPLACE FUNCTION validate_review_reviewer()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pull_request_reviewers
        WHERE pull_request_id = NEW.pull_request_id
          AND reviewer_id = NEW.reviewer_id
    ) THEN
        RAISE EXCEPTION
            'Reviewer is not assigned to this Pull Request';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pull_requests
        WHERE pull_request_id = NEW.pull_request_id
          AND author_id = NEW.reviewer_id
    ) THEN
        RAISE EXCEPTION
            'Pull Request author cannot submit an approval';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_review_reviewer
BEFORE INSERT OR UPDATE
ON reviews
FOR EACH ROW
EXECUTE FUNCTION validate_review_reviewer();


CREATE INDEX idx_pull_requests_repository_state
    ON pull_requests(repository_id, state);

CREATE INDEX idx_reviews_pull_request_state
    ON reviews(pull_request_id, review_state);

CREATE INDEX idx_status_checks_pull_request_state
    ON status_checks(pull_request_id, check_state);

CREATE INDEX idx_commits_pull_request
    ON commits(pull_request_id);

CREATE INDEX idx_review_comments_review_resolution
    ON review_comments(review_id, is_resolved);


INSERT INTO users (username, email)
VALUES
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com'),
    ('carol', 'carol@example.com'),
    ('david', 'david@example.com');

INSERT INTO repositories (repository_name)
VALUES ('payment-service');

INSERT INTO branches (
    repository_id,
    branch_name,
    is_default
)
SELECT
    repository_id,
    branch_name,
    is_default
FROM (
    SELECT
        repository_id,
        'main'::VARCHAR(150) AS branch_name,
        TRUE AS is_default
    FROM repositories
    WHERE repository_name = 'payment-service'

    UNION ALL

    SELECT
        repository_id,
        'feature/payment-validation'::VARCHAR(150),
        FALSE
    FROM repositories
    WHERE repository_name = 'payment-service'
) AS branch_data;


INSERT INTO branch_protection_policies (
    branch_id,
    required_approvals,
    require_status_checks,
    restrict_direct_pushes,
    allow_force_push,
    allow_branch_deletion,
    require_linear_history,
    require_conversation_resolution
)
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    TRUE,
    TRUE
FROM branches
WHERE branch_name = 'main';


INSERT INTO pull_requests (
    repository_id,
    author_id,
    source_branch_id,
    target_branch_id,
    title,
    description
)
SELECT
    r.repository_id,
    author.user_id,
    source.branch_id,
    target.branch_id,
    'Add payment validation',
    'Validates payment requests before processing.'
FROM repositories r
JOIN users author
    ON author.username = 'alice'
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payment-validation'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payment-service';


INSERT INTO commits (
    pull_request_id,
    commit_sha,
    commit_message
)
SELECT
    pull_request_id,
    '0123456789abcdef0123456789abcdef01234567',
    'Implement payment validation'
FROM pull_requests
WHERE title = 'Add payment validation';


INSERT INTO pull_request_reviewers (
    pull_request_id,
    reviewer_id
)
SELECT
    pr.pull_request_id,
    u.user_id
FROM pull_requests pr
CROSS JOIN users u
WHERE pr.title = 'Add payment validation'
  AND u.username IN ('bob', 'carol');


INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    review_state,
    review_body
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    CASE
        WHEN u.username = 'bob'
            THEN 'Validation logic is correct.'
        ELSE 'Security requirements are covered.'
    END
FROM pull_requests pr
JOIN users u
    ON u.username IN ('bob', 'carol')
WHERE pr.title = 'Add payment validation';


INSERT INTO review_comments (
    review_id,
    file_path,
    line_number,
    comment_body,
    is_resolved
)
SELECT
    review_id,
    'src/payment_validator.py',
    42,
    'Validation error is handled before the payment reaches the gateway.',
    TRUE
FROM reviews
WHERE review_state = 'approved'
LIMIT 1;


INSERT INTO status_checks (
    pull_request_id,
    check_name,
    check_state,
    completed_at
)
SELECT
    pull_request_id,
    checks.check_name,
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('security-scan')
) AS checks(check_name)
WHERE title = 'Add payment validation';


-- This view evaluates the current database state against the protected
-- target branch. It separates repository policy from the application code.
CREATE OR REPLACE VIEW merge_eligibility AS
WITH approval_counts AS (
    SELECT
        pr.pull_request_id,
        COUNT(DISTINCT r.reviewer_id) FILTER (
            WHERE r.review_state = 'approved'
        ) AS approval_count,
        BOOL_OR(
            r.review_state = 'changes_requested'
        ) AS has_requested_changes
    FROM pull_requests pr
    LEFT JOIN reviews r
        ON r.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
),
status_summary AS (
    SELECT
        pr.pull_request_id,
        COUNT(*) FILTER (
            WHERE sc.check_state = 'passed'
        ) AS passed_checks,
        COUNT(*) FILTER (
            WHERE sc.check_state <> 'passed'
        ) AS incomplete_or_failed_checks
    FROM pull_requests pr
    LEFT JOIN status_checks sc
        ON sc.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
),
commit_summary AS (
    SELECT
        pull_request_id,
        COUNT(*) AS commit_count
    FROM commits
    GROUP BY pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    pr.state,
    target.branch_name AS target_branch,
    policy.required_approvals,
    COALESCE(approval_counts.approval_count, 0) AS approval_count,
    COALESCE(approval_counts.has_requested_changes, FALSE)
        AS has_requested_changes,
    COALESCE(commit_summary.commit_count, 0)
        AS commit_count,
    COALESCE(status_summary.passed_checks, 0)
        AS passed_checks,
    COALESCE(status_summary.incomplete_or_failed_checks, 0)
        AS incomplete_or_failed_checks,
    (
        pr.state = 'open'
        AND COALESCE(commit_summary.commit_count, 0) > 0
        AND COALESCE(approval_counts.approval_count, 0)
            >= policy.required_approvals
        AND NOT COALESCE(
            approval_counts.has_requested_changes,
            FALSE
        )
        AND (
            NOT policy.require_status_checks
            OR COALESCE(status_summary.incomplete_or_failed_checks, 0) = 0
        )
    ) AS merge_eligible
FROM pull_requests pr
JOIN branches target
    ON target.branch_id = pr.target_branch_id
JOIN branch_protection_policies policy
    ON policy.branch_id = target.branch_id
LEFT JOIN approval_counts
    ON approval_counts.pull_request_id = pr.pull_request_id
LEFT JOIN status_summary
    ON status_summary.pull_request_id = pr.pull_request_id
LEFT JOIN commit_summary
    ON commit_summary.pull_request_id = pr.pull_request_id;


SELECT *
FROM merge_eligibility
ORDER BY pull_request_id;


-- Show the actual reviewer decisions attached to the Pull Request.
SELECT
    pr.pull_request_id,
    pr.title,
    u.username AS reviewer,
    r.review_state,
    r.review_body
FROM pull_requests pr
JOIN reviews r
    ON r.pull_request_id = pr.pull_request_id
JOIN users u
    ON u.user_id = r.reviewer_id
ORDER BY pr.pull_request_id, r.submitted_at;


-- Show the protection policy applied to the target branch.
SELECT
    r.repository_name,
    b.branch_name,
    p.required_approvals,
    p.require_status_checks,
    p.restrict_direct_pushes,
    p.allow_force_push,
    p.allow_branch_deletion,
    p.require_linear_history,
    p.require_conversation_resolution
FROM repositories r
JOIN branches b
    ON b.repository_id = r.repository_id
JOIN branch_protection_policies p
    ON p.branch_id = b.branch_id
WHERE r.repository_name = 'payment-service';


-- A transaction demonstrates atomic repository-state changes.
BEGIN;

UPDATE pull_requests
SET state = 'merged',
    updated_at = CURRENT_TIMESTAMP
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM merge_eligibility
    WHERE merge_eligible = TRUE
    LIMIT 1
)
AND EXISTS (
    SELECT 1
    FROM merge_eligibility
    WHERE merge_eligibility.pull_request_id =
          pull_requests.pull_request_id
      AND merge_eligibility.merge_eligible = TRUE
);

INSERT INTO merge_events (
    pull_request_id,
    merged_by,
    merge_strategy
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'squash'
FROM pull_requests pr
JOIN users u
    ON u.username = 'alice'
WHERE pr.state = 'merged'
  AND NOT EXISTS (
      SELECT 1
      FROM merge_events me
      WHERE me.pull_request_id = pr.pull_request_id
  );

COMMIT;


SELECT
    pull_request_id,
    state
FROM pull_requests
ORDER BY pull_request_id;

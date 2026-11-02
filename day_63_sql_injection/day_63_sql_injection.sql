DROP SCHEMA IF EXISTS sql_security_demo CASCADE;

CREATE SCHEMA sql_security_demo;

SET search_path = sql_security_demo, public;

CREATE TABLE app_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_name TEXT NOT NULL
        CHECK (role_name IN ('developer', 'reviewer', 'security', 'admin')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repository (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    visibility TEXT NOT NULL
        CHECK (visibility IN ('private', 'internal', 'public')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE branch (
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, branch_name)
);

CREATE TABLE pull_request (
    pull_request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id),
    author_id BIGINT NOT NULL
        REFERENCES app_user(user_id),
    title TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('draft', 'open', 'closed', 'merged')),
    merge_conflict BOOLEAN NOT NULL DEFAULT FALSE,
    source_synchronized BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE pull_request_commit (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    commit_hash TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pull_request_id, commit_hash)
);

CREATE TABLE review (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES app_user(user_id),
    state TEXT NOT NULL
        CHECK (state IN (
            'pending',
            'approved',
            'changes_requested',
            'dismissed'
        )),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dismissed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, reviewer_id)
);

CREATE TABLE review_comment (
    comment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES app_user(user_id),
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE status_check (
    status_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('pending', 'passed', 'failed')),
    required BOOLEAN NOT NULL DEFAULT TRUE,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE branch_protection_policy (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 1
        CHECK (required_approvals >= 0),
    require_pull_request BOOLEAN NOT NULL DEFAULT TRUE,
    require_resolved_conversations BOOLEAN NOT NULL DEFAULT TRUE,
    require_passing_checks BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_direct_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_force_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_branch_deletion BOOLEAN NOT NULL DEFAULT TRUE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE merge_record (
    merge_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL UNIQUE
        REFERENCES pull_request(pull_request_id),
    merged_by BIGINT NOT NULL
        REFERENCES app_user(user_id),
    merge_strategy TEXT NOT NULL
        CHECK (merge_strategy IN ('merge_commit', 'squash', 'rebase')),
    merged_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE security_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL,
    pull_request_id BIGINT REFERENCES pull_request(pull_request_id),
    actor_id BIGINT REFERENCES app_user(user_id),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pull_request_target
    ON pull_request(target_branch_id, state);

CREATE INDEX idx_review_pull_request
    ON review(pull_request_id, state);

CREATE INDEX idx_review_comment_unresolved
    ON review_comment(pull_request_id)
    WHERE resolved = FALSE;

CREATE INDEX idx_status_check_required
    ON status_check(pull_request_id, state)
    WHERE required = TRUE;

INSERT INTO app_user(username, password_hash, role_name)
VALUES
    ('alice', 'PBKDF2_HASH_ALICE', 'developer'),
    ('security-reviewer', 'PBKDF2_HASH_SECURITY', 'security'),
    ('database-reviewer', 'PBKDF2_HASH_DATABASE', 'reviewer'),
    ('external-reviewer', 'PBKDF2_HASH_EXTERNAL', 'developer'),
    ('admin', 'PBKDF2_HASH_ADMIN', 'admin');

INSERT INTO repository(repository_name, visibility)
VALUES ('secure-data-service', 'private');

INSERT INTO branch(repository_id, branch_name, protected)
SELECT repository_id, 'main', TRUE
FROM repository
WHERE repository_name = 'secure-data-service';

INSERT INTO branch(repository_id, branch_name, protected)
SELECT repository_id, 'feature/parameterized-queries', FALSE
FROM repository
WHERE repository_name = 'secure-data-service';

INSERT INTO branch_protection_policy(
    branch_id,
    required_approvals,
    require_pull_request,
    require_resolved_conversations,
    require_passing_checks,
    restrict_direct_push,
    restrict_force_push,
    restrict_branch_deletion,
    require_linear_history
)
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    FALSE
FROM branch
WHERE branch_name = 'main';

INSERT INTO pull_request(
    repository_id,
    source_branch_id,
    target_branch_id,
    author_id,
    title,
    state,
    merge_conflict,
    source_synchronized
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    u.user_id,
    'Replace concatenated SQL with parameterized queries',
    'open',
    FALSE,
    TRUE
FROM repository r
JOIN branch source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/parameterized-queries'
JOIN branch target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
JOIN app_user u
    ON u.username = 'alice'
WHERE r.repository_name = 'secure-data-service';

INSERT INTO pull_request_commit(pull_request_id, commit_hash)
SELECT pull_request_id, commit_hash
FROM pull_request
CROSS JOIN (
    VALUES
        ('a18f2c1'),
        ('b91d7aa'),
        ('c72e031')
) AS commits(commit_hash)
WHERE title = 'Replace concatenated SQL with parameterized queries';

INSERT INTO review(
    pull_request_id,
    reviewer_id,
    state
)
SELECT
    p.pull_request_id,
    u.user_id,
    'approved'
FROM pull_request p
JOIN app_user u
    ON u.username IN ('security-reviewer', 'database-reviewer')
WHERE p.title = 'Replace concatenated SQL with parameterized queries';

INSERT INTO review(
    pull_request_id,
    reviewer_id,
    state
)
SELECT
    p.pull_request_id,
    u.user_id,
    'approved'
FROM pull_request p
JOIN app_user u
    ON u.username = 'external-reviewer'
WHERE p.title = 'Replace concatenated SQL with parameterized queries';

INSERT INTO review_comment(
    pull_request_id,
    reviewer_id,
    body,
    resolved
)
SELECT
    p.pull_request_id,
    u.user_id,
    'Use a bound parameter instead of concatenating the username.',
    TRUE
FROM pull_request p
JOIN app_user u
    ON u.username = 'security-reviewer'
WHERE p.title = 'Replace concatenated SQL with parameterized queries';

INSERT INTO review_comment(
    pull_request_id,
    reviewer_id,
    body,
    resolved
)
SELECT
    p.pull_request_id,
    u.user_id,
    'The repository must not expose raw database errors to clients.',
    FALSE
FROM pull_request p
JOIN app_user u
    ON u.username = 'security-reviewer'
WHERE p.title = 'Replace concatenated SQL with parameterized queries';

INSERT INTO status_check(
    pull_request_id,
    check_name,
    state,
    required,
    completed_at
)
SELECT
    p.pull_request_id,
    checks.check_name,
    checks.state,
    checks.required,
    CASE
        WHEN checks.state <> 'pending' THEN now()
        ELSE NULL
    END
FROM pull_request p
CROSS JOIN (
    VALUES
        ('unit-tests', 'passed', TRUE),
        ('static-analysis', 'passed', TRUE),
        ('sql-injection-regression', 'passed', TRUE),
        ('documentation', 'pending', FALSE)
) AS checks(check_name, state, required)
WHERE p.title = 'Replace concatenated SQL with parameterized queries';

CREATE OR REPLACE FUNCTION validate_pull_request_repository()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    source_repository BIGINT;
    target_repository BIGINT;
BEGIN
    SELECT repository_id
    INTO source_repository
    FROM branch
    WHERE branch_id = NEW.source_branch_id;

    SELECT repository_id
    INTO target_repository
    FROM branch
    WHERE branch_id = NEW.target_branch_id;

    IF source_repository IS NULL
       OR target_repository IS NULL
       OR source_repository <> target_repository THEN
        RAISE EXCEPTION
            'Pull request branches must belong to the same repository';
    END IF;

    IF NEW.repository_id <> source_repository THEN
        RAISE EXCEPTION
            'Pull request repository does not match its branches';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_pull_request_repository
BEFORE INSERT OR UPDATE
ON pull_request
FOR EACH ROW
EXECUTE FUNCTION validate_pull_request_repository();

CREATE OR REPLACE FUNCTION unresolved_review_count(
    requested_pull_request BIGINT
)
RETURNS INTEGER
LANGUAGE SQL
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM review_comment
    WHERE pull_request_id = requested_pull_request
      AND resolved = FALSE;
$$;

CREATE OR REPLACE FUNCTION merge_eligibility(
    requested_pull_request BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    blocker TEXT
)
LANGUAGE SQL
STABLE
AS $$
    WITH pr AS (
        SELECT
            p.pull_request_id,
            p.state,
            p.merge_conflict,
            p.source_synchronized,
            p.target_branch_id,
            bp.required_approvals,
            bp.require_pull_request,
            bp.require_resolved_conversations,
            bp.require_passing_checks
        FROM pull_request p
        JOIN branch_protection_policy bp
          ON bp.branch_id = p.target_branch_id
        WHERE p.pull_request_id = requested_pull_request
    ),
    approval_count AS (
        SELECT
            r.pull_request_id,
            COUNT(DISTINCT r.reviewer_id)::INTEGER AS approvals
        FROM review r
        JOIN app_user u
          ON u.user_id = r.reviewer_id
        WHERE r.state = 'approved'
          AND u.active = TRUE
          AND u.role_name IN ('reviewer', 'security', 'admin')
        GROUP BY r.pull_request_id
    ),
    required_check_failures AS (
        SELECT
            s.pull_request_id,
            COUNT(*)::INTEGER AS failures
        FROM status_check s
        WHERE s.required = TRUE
          AND s.state <> 'passed'
        GROUP BY s.pull_request_id
    )
    SELECT TRUE, 'eligible'
    FROM pr
    LEFT JOIN approval_count a
      ON a.pull_request_id = pr.pull_request_id
    LEFT JOIN required_check_failures f
      ON f.pull_request_id = pr.pull_request_id
    WHERE pr.state = 'open'
      AND NOT pr.merge_conflict
      AND pr.source_synchronized
      AND (
          NOT pr.require_resolved_conversations
          OR unresolved_review_count(pr.pull_request_id) = 0
      )
      AND (
          NOT pr.require_pull_request
          OR pr.pull_request_id > 0
      )
      AND COALESCE(a.approvals, 0) >= pr.required_approvals
      AND (
          NOT pr.require_passing_checks
          OR COALESCE(f.failures, 0) = 0
      )

    UNION ALL

    SELECT FALSE, 'merge blocked by one or more governance conditions'
    FROM pr
    LEFT JOIN approval_count a
      ON a.pull_request_id = pr.pull_request_id
    LEFT JOIN required_check_failures f
      ON f.pull_request_id = pr.pull_request_id
    WHERE NOT (
        pr.state = 'open'
        AND NOT pr.merge_conflict
        AND pr.source_synchronized
        AND (
            NOT pr.require_resolved_conversations
            OR unresolved_review_count(pr.pull_request_id) = 0
        )
        AND COALESCE(a.approvals, 0) >= pr.required_approvals
        AND (
            NOT pr.require_passing_checks
            OR COALESCE(f.failures, 0) = 0
        )
    );
$$;

CREATE OR REPLACE FUNCTION record_merge(
    requested_pull_request BIGINT,
    merger BIGINT,
    strategy TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    decision BOOLEAN;
BEGIN
    IF strategy NOT IN ('merge_commit', 'squash', 'rebase') THEN
        RAISE EXCEPTION 'Unsupported merge strategy: %', strategy;
    END IF;

    SELECT eligible
    INTO decision
    FROM merge_eligibility(requested_pull_request)
    LIMIT 1;

    IF COALESCE(decision, FALSE) = FALSE THEN
        RAISE EXCEPTION
            'Pull request % is not eligible for merge',
            requested_pull_request;
    END IF;

    INSERT INTO merge_record(
        pull_request_id,
        merged_by,
        merge_strategy
    )
    VALUES (
        requested_pull_request,
        merger,
        strategy
    );

    UPDATE pull_request
    SET state = 'merged'
    WHERE pull_request_id = requested_pull_request;

    INSERT INTO security_audit(
        event_type,
        pull_request_id,
        actor_id,
        details
    )
    VALUES (
        'pull_request.merged',
        requested_pull_request,
        merger,
        jsonb_build_object(
            'strategy', strategy
        )
    );
END;
$$;

CREATE VIEW pull_request_security_report AS
WITH approvals AS (
    SELECT
        pull_request_id,
        COUNT(DISTINCT reviewer_id) FILTER (
            WHERE state = 'approved'
        ) AS approvals
    FROM review
    GROUP BY pull_request_id
),
checks AS (
    SELECT
        pull_request_id,
        COUNT(*) FILTER (
            WHERE required AND state = 'passed'
        ) AS passed_required_checks,
        COUNT(*) FILTER (
            WHERE required AND state <> 'passed'
        ) AS failed_or_pending_required_checks
    FROM status_check
    GROUP BY pull_request_id
)
SELECT
    p.pull_request_id,
    p.title,
    p.state,
    p.source_synchronized,
    p.merge_conflict,
    COALESCE(a.approvals, 0) AS approvals,
    COALESCE(c.passed_required_checks, 0) AS passed_required_checks,
    COALESCE(c.failed_or_pending_required_checks, 0)
        AS failed_or_pending_required_checks,
    unresolved_review_count(p.pull_request_id)
        AS unresolved_conversations
FROM pull_request p
LEFT JOIN approvals a
    ON a.pull_request_id = p.pull_request_id
LEFT JOIN checks c
    ON c.pull_request_id = p.pull_request_id;

-- Safe lookup: the username is a data value, not SQL syntax.
PREPARE find_user(text) AS
SELECT user_id, username, role_name
FROM app_user
WHERE username = $1;

EXECUTE find_user('alice');

-- An injection-like string remains a literal value.
EXECUTE find_user(''' OR ''1''=''1');

DEALLOCATE find_user;

-- Validation and reporting.
SELECT *
FROM pull_request_security_report
ORDER BY pull_request_id;

SELECT
    p.pull_request_id,
    p.title,
    u.username AS author,
    b.branch_name AS target_branch,
    p.state,
    merge_eligibility(p.pull_request_id)
FROM pull_request p
JOIN app_user u
    ON u.user_id = p.author_id
JOIN branch b
    ON b.branch_id = p.target_branch_id
ORDER BY p.pull_request_id;

SELECT
    r.repository_name,
    b.branch_name,
    bp.required_approvals,
    bp.require_passing_checks,
    bp.restrict_direct_push,
    bp.restrict_force_push
FROM repository r
JOIN branch b
    ON b.repository_id = r.repository_id
JOIN branch_protection_policy bp
    ON bp.branch_id = b.branch_id
WHERE b.protected = TRUE;

-- This transaction demonstrates that merge recording and state transition
-- occur atomically.
BEGIN;

SELECT record_merge(
    (
        SELECT pull_request_id
        FROM pull_request
        WHERE title = 'Replace concatenated SQL with parameterized queries'
    ),
    (
        SELECT user_id
        FROM app_user
        WHERE username = 'admin'
    ),
    'squash'
);

COMMIT;

SELECT
    pull_request_id,
    state
FROM pull_request
ORDER BY pull_request_id;

SELECT
    event_type,
    pull_request_id,
    actor_id,
    details,
    created_at
FROM security_audit
ORDER BY audit_id;

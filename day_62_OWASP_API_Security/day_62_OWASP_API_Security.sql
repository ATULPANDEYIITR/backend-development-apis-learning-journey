DROP SCHEMA IF EXISTS api_security_governance CASCADE;

CREATE SCHEMA api_security_governance;

SET search_path = api_security_governance, public;

CREATE TYPE pull_request_state AS ENUM (
    'draft',
    'open',
    'closed',
    'merged'
);

CREATE TYPE review_state AS ENUM (
    'commented',
    'approved',
    'changes_requested',
    'dismissed'
);

CREATE TYPE check_state AS ENUM (
    'pending',
    'passed',
    'failed'
);

CREATE TYPE security_severity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE security_category AS ENUM (
    'broken_authorization',
    'excessive_data_exposure',
    'injection',
    'ssrf',
    'security_misconfiguration'
);

CREATE TABLE repository (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    default_branch TEXT NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repository_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    team_name TEXT NOT NULL,
    is_administrator BOOLEAN NOT NULL DEFAULT false,
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE branch (
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    is_protected BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMPTZ,
    UNIQUE (repository_id, branch_name),
    CHECK (length(trim(branch_name)) > 0),
    CHECK (length(head_sha) >= 7)
);

CREATE TABLE commit (
    commit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    sha TEXT NOT NULL,
    author_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    message TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, sha),
    CHECK (length(trim(message)) > 0)
);

CREATE TABLE commit_file (
    commit_id BIGINT NOT NULL
        REFERENCES commit(commit_id)
        ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    PRIMARY KEY (commit_id, file_path),
    CHECK (length(trim(file_path)) > 0)
);

CREATE TABLE pull_request (
    pull_request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    source_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id),
    base_sha TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    state pull_request_state NOT NULL DEFAULT 'open',
    is_draft BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    merge_commit_sha TEXT,
    UNIQUE (repository_id, number),
    CHECK (source_branch_id <> target_branch_id),
    CHECK (length(trim(title)) > 0),
    CHECK (
        (state = 'merged' AND merge_commit_sha IS NOT NULL)
        OR state <> 'merged'
    )
);

CREATE TABLE pull_request_commit (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    commit_id BIGINT NOT NULL
        REFERENCES commit(commit_id)
        ON DELETE RESTRICT,
    sequence_number INTEGER NOT NULL,
    PRIMARY KEY (pull_request_id, commit_id),
    UNIQUE (pull_request_id, sequence_number),
    CHECK (sequence_number > 0)
);

CREATE TABLE review (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    state review_state NOT NULL,
    reviewed_head_sha TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dismissed_at TIMESTAMPTZ
);

CREATE TABLE review_comment (
    comment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES review(review_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    body TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CHECK (line_number > 0),
    CHECK (length(trim(body)) > 0)
);

CREATE TABLE status_check (
    status_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    state check_state NOT NULL,
    details TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE security_finding (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    category security_category NOT NULL,
    severity security_severity NOT NULL,
    endpoint TEXT NOT NULL,
    description TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(endpoint)) > 0),
    CHECK (length(trim(description)) > 0)
);

CREATE TABLE branch_protection_policy (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 2,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT true,
    require_code_owner_review BOOLEAN NOT NULL DEFAULT true,
    require_linear_history BOOLEAN NOT NULL DEFAULT true,
    allow_force_push BOOLEAN NOT NULL DEFAULT false,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT false,
    administrators_can_bypass BOOLEAN NOT NULL DEFAULT false,
    CHECK (required_approvals >= 1)
);

CREATE TABLE required_status_check (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policy(policy_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    PRIMARY KEY (policy_id, check_name),
    CHECK (length(trim(check_name)) > 0)
);

CREATE TABLE code_owner_rule (
    code_owner_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    path_prefix TEXT NOT NULL,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    UNIQUE (repository_id, path_prefix, reviewer_id),
    CHECK (length(trim(path_prefix)) > 0)
);

CREATE TABLE approval_requirement (
    requirement_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policy(policy_id)
        ON DELETE CASCADE,
    requirement_name TEXT NOT NULL,
    minimum_approvals INTEGER NOT NULL,
    required_team TEXT,
    UNIQUE (policy_id, requirement_name),
    CHECK (minimum_approvals >= 1)
);

CREATE INDEX idx_branch_repository
    ON branch(repository_id);

CREATE INDEX idx_commit_repository_sha
    ON commit(repository_id, sha);

CREATE INDEX idx_pr_repository_state
    ON pull_request(repository_id, state);

CREATE INDEX idx_review_pr_reviewer
    ON review(pull_request_id, reviewer_id);

CREATE INDEX idx_status_check_pr
    ON status_check(pull_request_id, check_name, state);

CREATE INDEX idx_security_finding_pr
    ON security_finding(pull_request_id, severity, resolved);

CREATE INDEX idx_review_comment_unresolved
    ON review_comment(review_id)
    WHERE is_resolved = false;

CREATE OR REPLACE FUNCTION prevent_self_approval()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pr_author BIGINT;
BEGIN
    SELECT author_id
    INTO pr_author
    FROM pull_request
    WHERE pull_request_id = NEW.pull_request_id;

    IF pr_author = NEW.reviewer_id
       AND NEW.state = 'approved' THEN
        RAISE EXCEPTION
            'Self-approval is not permitted for pull request %',
            NEW.pull_request_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_self_approval
BEFORE INSERT OR UPDATE ON review
FOR EACH ROW
EXECUTE FUNCTION prevent_self_approval();

CREATE OR REPLACE FUNCTION prevent_unsafe_merge_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state = 'merged'
       AND NEW.merge_commit_sha IS NULL THEN
        RAISE EXCEPTION
            'Merged Pull Requests require a merge commit SHA';
    END IF;

    IF NEW.state <> 'merged'
       AND NEW.merge_commit_sha IS NOT NULL THEN
        RAISE EXCEPTION
            'Only merged Pull Requests may contain a merge commit SHA';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_unsafe_merge_state
BEFORE INSERT OR UPDATE ON pull_request
FOR EACH ROW
EXECUTE FUNCTION prevent_unsafe_merge_state();

CREATE OR REPLACE FUNCTION resolve_review_comment(
    p_comment_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE review_comment
    SET is_resolved = true,
        resolved_at = now()
    WHERE comment_id = p_comment_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Review comment % does not exist',
            p_comment_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_target_branch BIGINT;
    v_policy_id BIGINT;
    v_required_approvals INTEGER;
    v_actual_approvals INTEGER;
    v_base_sha TEXT;
    v_target_sha TEXT;
    v_author BIGINT;
    v_unresolved INTEGER;
    v_required_checks INTEGER;
    v_passing_checks INTEGER;
    v_blocking_findings INTEGER;
    v_code_owner_required BOOLEAN;
    v_code_owner_approved BOOLEAN;
BEGIN
    SELECT
        pr.target_branch_id,
        pr.base_sha,
        pr.author_id
    INTO
        v_target_branch,
        v_base_sha,
        v_author
    FROM pull_request pr
    WHERE pr.pull_request_id = p_pull_request_id
      AND pr.state = 'open';

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT false, 'Pull Request does not exist or is not open';
        RETURN;
    END IF;

    SELECT b.head_sha
    INTO v_target_sha
    FROM branch b
    WHERE b.branch_id = v_target_branch;

    IF v_base_sha <> v_target_sha THEN
        RETURN QUERY
        SELECT false, 'Pull Request base branch is stale';
    END IF;

    SELECT
        bpp.policy_id,
        bpp.required_approvals,
        bpp.require_conversation_resolution,
        bpp.require_code_owner_review
    INTO
        v_policy_id,
        v_required_approvals,
        v_code_owner_required,
        v_code_owner_required
    FROM branch_protection_policy bpp
    WHERE bpp.branch_id = v_target_branch;

    IF v_policy_id IS NULL THEN
        RETURN QUERY
        SELECT true, 'Target branch has no additional protection policy';
        RETURN;
    END IF;

    SELECT count(*)
    INTO v_required_checks
    FROM required_status_check
    WHERE policy_id = v_policy_id;

    SELECT count(*)
    INTO v_passing_checks
    FROM required_status_check rsc
    JOIN status_check sc
      ON sc.check_name = rsc.check_name
     AND sc.pull_request_id = p_pull_request_id
    WHERE rsc.policy_id = v_policy_id
      AND sc.state = 'passed';

    IF v_passing_checks < v_required_checks THEN
        RETURN QUERY
        SELECT false,
               format(
                   'Only %s of %s required status checks are passing',
                   v_passing_checks,
                   v_required_checks
               );
    END IF;

    IF v_code_owner_required THEN
        SELECT EXISTS (
            SELECT 1
            FROM code_owner_rule cor
            JOIN review r
              ON r.reviewer_id = cor.reviewer_id
             AND r.pull_request_id = p_pull_request_id
            JOIN pull_request_commit prc
              ON prc.pull_request_id = p_pull_request_id
            JOIN commit_file cf
              ON cf.commit_id = prc.commit_id
            WHERE cor.repository_id = (
                SELECT repository_id
                FROM pull_request
                WHERE pull_request_id = p_pull_request_id
            )
              AND cf.file_path LIKE cor.path_prefix || '%'
              AND r.state = 'approved'
              AND r.reviewed_head_sha = (
                  SELECT head_sha
                  FROM pull_request
                  WHERE pull_request_id = p_pull_request_id
              )
        )
        INTO v_code_owner_approved;

        IF NOT v_code_owner_approved THEN
            RETURN QUERY
            SELECT false,
                   'Required API security code-owner approval is missing';
        END IF;
    END IF;

    SELECT count(*)
    INTO v_unresolved
    FROM review_comment rc
    JOIN review r ON r.review_id = rc.review_id
    WHERE r.pull_request_id = p_pull_request_id
      AND rc.is_resolved = false;

    IF v_unresolved > 0 THEN
        RETURN QUERY
        SELECT false,
               format(
                   '%s unresolved review conversation(s)',
                   v_unresolved
               );
    END IF;

    SELECT count(*)
    INTO v_actual_approvals
    FROM (
        SELECT DISTINCT ON (reviewer_id)
            reviewer_id,
            state,
            reviewed_head_sha
        FROM review
        WHERE pull_request_id = p_pull_request_id
          AND reviewer_id <> v_author
        ORDER BY reviewer_id, submitted_at DESC
    ) latest
    WHERE latest.state = 'approved'
      AND latest.reviewed_head_sha = (
          SELECT head_sha
          FROM pull_request
          WHERE pull_request_id = p_pull_request_id
      );

    IF v_actual_approvals < v_required_approvals THEN
        RETURN QUERY
        SELECT false,
               format(
                   '%s current approvals; %s required',
                   v_actual_approvals,
                   v_required_approvals
               );
    END IF;

    SELECT count(*)
    INTO v_blocking_findings
    FROM security_finding
    WHERE pull_request_id = p_pull_request_id
      AND resolved = false
      AND severity IN ('high', 'critical');

    IF v_blocking_findings > 0 THEN
        RETURN QUERY
        SELECT false,
               format(
                   '%s unresolved high or critical security finding(s)',
                   v_blocking_findings
               );
    END IF;

    RETURN QUERY
    SELECT true, 'Pull Request satisfies merge eligibility rules';
END;
$$;

CREATE VIEW v_pull_request_security_report AS
SELECT
    r.repository_name,
    pr.number AS pull_request_number,
    pr.title,
    pr.state,
    pr.source_branch_id,
    pr.target_branch_id,
    u.username AS author,
    count(sf.finding_id) AS security_findings,
    count(sf.finding_id) FILTER (
        WHERE sf.severity IN ('high', 'critical')
          AND NOT sf.resolved
    ) AS blocking_findings,
    count(DISTINCT rv.review_id) FILTER (
        WHERE rv.state = 'approved'
          AND rv.reviewed_head_sha = pr.head_sha
    ) AS current_approvals,
    count(rc.comment_id) FILTER (
        WHERE NOT rc.is_resolved
    ) AS unresolved_conversations
FROM pull_request pr
JOIN repository r
  ON r.repository_id = pr.repository_id
JOIN repository_user u
  ON u.user_id = pr.author_id
LEFT JOIN security_finding sf
  ON sf.pull_request_id = pr.pull_request_id
LEFT JOIN review rv
  ON rv.pull_request_id = pr.pull_request_id
LEFT JOIN review_comment rc
  ON rc.review_id = rv.review_id
GROUP BY
    r.repository_name,
    pr.number,
    pr.title,
    pr.state,
    pr.source_branch_id,
    pr.target_branch_id,
    u.username,
    pr.head_sha;

INSERT INTO repository (
    repository_name,
    default_branch
)
VALUES (
    'payments-api',
    'main'
);

INSERT INTO repository_user (
    username,
    team,
    is_administrator
)
VALUES
    ('developer', 'backend', false),
    ('backend-reviewer', 'backend', false),
    ('security-lead', 'security', false),
    ('release-admin', 'platform', true);

INSERT INTO branch (
    repository_id,
    branch_name,
    head_sha,
    is_protected
)
SELECT
    repository_id,
    'main',
    'main-001',
    true
FROM repository
WHERE repository_name = 'payments-api';

INSERT INTO branch (
    repository_id,
    branch_name,
    head_sha,
    is_protected
)
SELECT
    repository_id,
    'feature/api-authorization',
    'feature-001',
    false
FROM repository
WHERE repository_name = 'payments-api';

INSERT INTO branch_protection_policy (
    branch_id,
    required_approvals,
    require_conversation_resolution,
    require_code_owner_review,
    require_linear_history,
    allow_force_push,
    allow_branch_deletion,
    administrators_can_bypass
)
SELECT
    branch_id,
    2,
    true,
    true,
    true,
    false,
    false,
    false
FROM branch
WHERE branch_name = 'main';

INSERT INTO required_status_check (
    policy_id,
    check_name
)
SELECT
    policy_id,
    check_name
FROM branch_protection_policy
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('api-security-scan'),
        ('authorization-tests')
) AS checks(check_name);

INSERT INTO approval_requirement (
    policy_id,
    requirement_name,
    minimum_approvals,
    required_team
)
SELECT
    policy_id,
    'standard-api-review',
    2,
    NULL
FROM branch_protection_policy;

INSERT INTO code_owner_rule (
    repository_id,
    path_prefix,
    reviewer_id
)
SELECT
    r.repository_id,
    'api/',
    u.user_id
FROM repository r
JOIN repository_user u
  ON u.username = 'security-lead'
WHERE r.repository_name = 'payments-api';

INSERT INTO code_owner_rule (
    repository_id,
    path_prefix,
    reviewer_id
)
SELECT
    r.repository_id,
    'auth/',
    u.user_id
FROM repository r
JOIN repository_user u
  ON u.username = 'security-lead'
WHERE r.repository_name = 'payments-api';

INSERT INTO commit (
    repository_id,
    sha,
    author_id,
    message
)
SELECT
    r.repository_id,
    'commit-001',
    u.user_id,
    'Enforce tenant ownership for API objects'
FROM repository r
JOIN repository_user u
  ON u.username = 'developer'
WHERE r.repository_name = 'payments-api';

INSERT INTO commit_file (
    commit_id,
    file_path
)
SELECT
    commit_id,
    file_path
FROM commit
CROSS JOIN (
    VALUES
        ('api/orders.sql'),
        ('auth/authorization.sql')
) AS files(file_path)
WHERE sha = 'commit-001';

INSERT INTO pull_request (
    repository_id,
    number,
    title,
    author_id,
    source_branch_id,
    target_branch_id,
    base_sha,
    head_sha,
    state,
    is_draft
)
SELECT
    r.repository_id,
    1,
    'Enforce object-level authorization',
    author.user_id,
    source.branch_id,
    target.branch_id,
    target.head_sha,
    'commit-001',
    'open',
    false
FROM repository r
JOIN repository_user author
  ON author.username = 'developer'
JOIN branch source
  ON source.repository_id = r.repository_id
 AND source.branch_name = 'feature/api-authorization'
JOIN branch target
  ON target.repository_id = r.repository_id
 AND target.branch_name = 'main'
WHERE r.repository_name = 'payments-api';

INSERT INTO pull_request_commit (
    pull_request_id,
    commit_id,
    sequence_number
)
SELECT
    pr.pull_request_id,
    c.commit_id,
    1
FROM pull_request pr
JOIN commit c
  ON c.sha = 'commit-001'
WHERE pr.number = 1;

INSERT INTO security_finding (
    pull_request_id,
    category,
    severity,
    endpoint,
    description,
    resolved
)
SELECT
    pull_request_id,
    'broken_authorization',
    'low',
    'GET /api/orders/{id}',
    'Object ownership is checked before serialization.',
    false
FROM pull_request
WHERE number = 1;

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    state,
    reviewed_head_sha
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    pr.head_sha
FROM pull_request pr
JOIN repository_user u
  ON u.username = 'backend-reviewer'
WHERE pr.number = 1;

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    state,
    reviewed_head_sha
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    pr.head_sha
FROM pull_request pr
JOIN repository_user u
  ON u.username = 'security-lead'
WHERE pr.number = 1;

INSERT INTO status_check (
    pull_request_id,
    check_name,
    state,
    details,
    completed_at
)
SELECT
    pr.pull_request_id,
    checks.check_name,
    'passed',
    'Passed security and correctness validation.',
    now()
FROM pull_request pr
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('api-security-scan'),
        ('authorization-tests')
) AS checks(check_name)
WHERE pr.number = 1;

INSERT INTO review_comment (
    review_id,
    reviewer_id,
    file_path,
    line_number,
    body,
    is_resolved
)
SELECT
    rv.review_id,
    rv.reviewer_id,
    'api/orders.sql',
    42,
    'Verify tenant identity comes from the authenticated principal.',
    true
FROM review rv
JOIN pull_request pr
  ON pr.pull_request_id = rv.pull_request_id
WHERE pr.number = 1
  AND rv.reviewer_id = (
      SELECT user_id
      FROM repository_user
      WHERE username = 'security-lead'
  );

SELECT *
FROM merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_request
        WHERE number = 1
    )
);

SELECT *
FROM v_pull_request_security_report
ORDER BY pull_request_number;

WITH security_counts AS (
    SELECT
        category,
        severity,
        count(*) AS finding_count
    FROM security_finding
    GROUP BY category, severity
)
SELECT
    category,
    severity,
    finding_count
FROM security_counts
ORDER BY
    category,
    severity;

WITH latest_reviews AS (
    SELECT DISTINCT ON (
        pull_request_id,
        reviewer_id
    )
        pull_request_id,
        reviewer_id,
        state,
        reviewed_head_sha,
        submitted_at
    FROM review
    ORDER BY
        pull_request_id,
        reviewer_id,
        submitted_at DESC
)
SELECT
    pr.number,
    ru.username AS reviewer,
    lr.state,
    lr.reviewed_head_sha = pr.head_sha
        AS is_current_review
FROM latest_reviews lr
JOIN pull_request pr
  ON pr.pull_request_id = lr.pull_request_id
JOIN repository_user ru
  ON ru.user_id = lr.reviewer_id
ORDER BY pr.number, ru.username;

BEGIN;

UPDATE pull_request
SET state = 'merged',
    merged_at = now(),
    merge_commit_sha = 'merge-001'
WHERE number = 1
  AND EXISTS (
      SELECT 1
      FROM merge_eligibility(pull_request.pull_request_id)
      WHERE eligible
  );

UPDATE branch
SET head_sha = 'merge-001'
WHERE branch_name = 'main'
  AND repository_id = (
      SELECT repository_id
      FROM repository
      WHERE repository_name = 'payments-api'
  );

COMMIT;

SELECT
    pr.number,
    pr.state,
    pr.merge_commit_sha,
    b.head_sha AS target_branch_head
FROM pull_request pr
JOIN branch b
  ON b.branch_id = pr.target_branch_id
WHERE pr.number = 1;

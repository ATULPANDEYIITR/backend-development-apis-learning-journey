DROP SCHEMA IF EXISTS web_security CASCADE;
CREATE SCHEMA web_security;

SET search_path TO web_security, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE security_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE threat_category AS ENUM (
    'SPOOFING',
    'TAMPERING',
    'REPUDIATION',
    'INFORMATION_DISCLOSURE',
    'DENIAL_OF_SERVICE',
    'ELEVATION_OF_PRIVILEGE'
);

CREATE TYPE asset_type AS ENUM (
    'CREDENTIAL',
    'SESSION',
    'APPLICATION',
    'DATABASE',
    'API',
    'LOG',
    'INFRASTRUCTURE'
);

CREATE TYPE user_role AS ENUM (
    'DEVELOPER',
    'SECURITY_REVIEWER',
    'ADMINISTRATOR',
    'AUDITOR'
);

CREATE TYPE pull_request_state AS ENUM (
    'DRAFT',
    'OPEN',
    'MERGED',
    'CLOSED'
);

CREATE TYPE review_decision AS ENUM (
    'APPROVED',
    'CHANGES_REQUESTED',
    'COMMENTED'
);

CREATE TYPE finding_status AS ENUM (
    'OPEN',
    'RESOLVED',
    'ACCEPTED_RISK'
);

CREATE TABLE repository (
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    is_private BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT repository_name_ck
        CHECK (name ~ '^[A-Za-z0-9_.-]{1,100}$')
);

CREATE TABLE repository_user (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT username_ck
        CHECK (username ~ '^[A-Za-z0-9_.-]{3,32}$')
);

CREATE TABLE repository_user_role (
    user_id BIGINT NOT NULL REFERENCES repository_user(user_id)
        ON DELETE CASCADE,
    role user_role NOT NULL,
    PRIMARY KEY (user_id, role)
);

CREATE TABLE branch (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    commit_sha TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, name),
    CONSTRAINT branch_name_ck CHECK (
        name <> ''
        AND name NOT LIKE '%..%'
        AND name NOT LIKE '%~%'
        AND name NOT LIKE '%^%'
        AND name NOT LIKE '%:%'
        AND name NOT LIKE '%\%'
    ),
    CONSTRAINT commit_sha_ck
        CHECK (commit_sha ~ '^[0-9a-f]{7,64}$')
);

CREATE UNIQUE INDEX one_default_branch_per_repository
ON branch(repository_id)
WHERE is_default = TRUE;

CREATE TABLE commit_record (
    commit_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    sha TEXT NOT NULL UNIQUE,
    author_user_id BIGINT REFERENCES repository_user(user_id),
    parent_sha TEXT,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT commit_sha_ck
        CHECK (sha ~ '^[0-9a-f]{7,64}$'),
    CONSTRAINT commit_message_ck
        CHECK (length(trim(message)) > 0)
);

CREATE TABLE pull_request (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL REFERENCES branch(branch_id),
    target_branch_id BIGINT NOT NULL REFERENCES branch(branch_id),
    author_user_id BIGINT NOT NULL REFERENCES repository_user(user_id),
    state pull_request_state NOT NULL DEFAULT 'OPEN',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_commit_sha TEXT NOT NULL,
    target_commit_sha TEXT NOT NULL,
    branch_up_to_date BOOLEAN NOT NULL DEFAULT TRUE,
    merge_conflict BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at TIMESTAMPTZ,
    CONSTRAINT pull_request_branch_ck
        CHECK (source_branch_id <> target_branch_id),
    CONSTRAINT pull_request_title_ck
        CHECK (length(trim(title)) BETWEEN 3 AND 300)
);

CREATE INDEX pull_request_repository_state_idx
ON pull_request(repository_id, state);

CREATE INDEX pull_request_target_idx
ON pull_request(target_branch_id, state);

CREATE TABLE pull_request_commit (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    commit_id BIGINT NOT NULL
        REFERENCES commit_record(commit_id)
        ON DELETE RESTRICT,
    PRIMARY KEY (pull_request_id, commit_id)
);

CREATE TABLE pull_request_file (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    path TEXT NOT NULL,
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pull_request_id, path),
    CONSTRAINT file_path_ck CHECK (
        path <> ''
        AND path NOT LIKE '%/../%'
        AND path NOT LIKE '../%'
        AND path NOT LIKE '%\0%'
    ),
    CONSTRAINT file_change_ck
        CHECK (additions >= 0 AND deletions >= 0)
);

CREATE TABLE review (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_user_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    decision review_decision NOT NULL,
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, reviewer_user_id, submitted_at)
);

CREATE INDEX review_current_decisions_idx
ON review(pull_request_id, reviewer_user_id, decision, stale, dismissed);

CREATE TABLE review_comment (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL REFERENCES review(review_id)
        ON DELETE CASCADE,
    author_user_id BIGINT NOT NULL
        REFERENCES repository_user(user_id),
    file_path TEXT,
    line_number INTEGER,
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT comment_body_ck
        CHECK (length(trim(body)) BETWEEN 1 AND 10000),
    CONSTRAINT comment_line_ck
        CHECK (line_number IS NULL OR line_number > 0)
);

CREATE INDEX unresolved_review_comments_idx
ON review_comment(review_id, resolved)
WHERE resolved = FALSE;

CREATE TABLE status_check (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    passed BOOLEAN NOT NULL DEFAULT FALSE,
    details TEXT NOT NULL DEFAULT '',
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, name)
);

CREATE TABLE branch_protection_policy (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    require_status_checks BOOLEAN NOT NULL DEFAULT TRUE,
    require_reviews BOOLEAN NOT NULL DEFAULT TRUE,
    required_approvals INTEGER NOT NULL DEFAULT 1,
    dismiss_stale_approvals BOOLEAN NOT NULL DEFAULT TRUE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE,
    require_up_to_date_branch BOOLEAN NOT NULL DEFAULT TRUE,
    allow_direct_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_administrator_bypass BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT approval_count_ck
        CHECK (required_approvals BETWEEN 0 AND 20)
);

CREATE TABLE approval_requirement (
    requirement_id BIGSERIAL PRIMARY KEY,
    policy_id BIGINT NOT NULL REFERENCES branch_protection_policy(policy_id)
        ON DELETE CASCADE,
    role user_role NOT NULL,
    required_count INTEGER NOT NULL,
    UNIQUE (policy_id, role),
    CONSTRAINT requirement_count_ck
        CHECK (required_count > 0 AND required_count <= 20)
);

CREATE TABLE asset (
    asset_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    type asset_type NOT NULL,
    confidentiality security_level NOT NULL,
    integrity security_level NOT NULL,
    availability security_level NOT NULL,
    owner_team TEXT NOT NULL,
    UNIQUE (repository_id, name)
);

CREATE TABLE threat (
    threat_id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES asset(asset_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    category threat_category NOT NULL,
    likelihood security_level NOT NULL,
    impact security_level NOT NULL,
    mitigation TEXT NOT NULL,
    UNIQUE (asset_id, name)
);

CREATE TABLE security_finding (
    finding_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    identifier TEXT NOT NULL,
    severity security_level NOT NULL,
    status finding_status NOT NULL DEFAULT 'OPEN',
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, identifier)
);

CREATE TABLE audit_event (
    audit_event_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT REFERENCES repository(repository_id)
        ON DELETE SET NULL,
    actor_user_id BIGINT REFERENCES repository_user(user_id)
        ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_repository_time_idx
ON audit_event(repository_id, created_at DESC);

CREATE INDEX security_finding_open_idx
ON security_finding(pull_request_id, status)
WHERE status = 'OPEN';

CREATE OR REPLACE FUNCTION prevent_invalid_branch_target()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM branch
        WHERE branch_id = NEW.target_branch_id
          AND repository_id = NEW.repository_id
    ) THEN
        RAISE EXCEPTION
            'Target branch does not belong to Pull Request repository';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM branch
        WHERE branch_id = NEW.source_branch_id
          AND repository_id = NEW.repository_id
    ) THEN
        RAISE EXCEPTION
            'Source branch does not belong to Pull Request repository';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER pull_request_branch_repository_guard
BEFORE INSERT OR UPDATE ON pull_request
FOR EACH ROW
EXECUTE FUNCTION prevent_invalid_branch_target();

CREATE OR REPLACE FUNCTION prevent_protected_direct_merge()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    protected_policy branch_protection_policy;
BEGIN
    IF NEW.state = 'MERGED'
       AND OLD.state <> 'MERGED' THEN

        SELECT p.*
        INTO protected_policy
        FROM branch_protection_policy p
        WHERE p.branch_id = NEW.target_branch_id;

        IF protected_policy.policy_id IS NULL THEN
            RETURN NEW;
        END IF;

        IF protected_policy.require_up_to_date_branch
           AND NOT NEW.branch_up_to_date THEN
            RAISE EXCEPTION
                'Protected branch requires an up-to-date source branch';
        END IF;

        IF NEW.merge_conflict THEN
            RAISE EXCEPTION
                'Pull Request has unresolved merge conflicts';
        END IF;

        IF protected_policy.require_status_checks
           AND EXISTS (
               SELECT 1
               FROM status_check sc
               WHERE sc.pull_request_id = NEW.pull_request_id
                 AND sc.required
                 AND NOT sc.passed
           ) THEN
            RAISE EXCEPTION
                'Required status check has failed';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM security_finding sf
            WHERE sf.pull_request_id = NEW.pull_request_id
              AND sf.status = 'OPEN'
        ) THEN
            RAISE EXCEPTION
                'Open security finding blocks merge';
        END IF;

        IF protected_policy.require_reviews
           AND (
               SELECT count(DISTINCT r.reviewer_user_id)
               FROM review r
               JOIN repository_user_role rur
                 ON rur.user_id = r.reviewer_user_id
               WHERE r.pull_request_id = NEW.pull_request_id
                 AND r.decision = 'APPROVED'
                 AND NOT r.stale
                 AND NOT r.dismissed
                 AND rur.role = 'SECURITY_REVIEWER'
           ) < protected_policy.required_approvals THEN
            RAISE EXCEPTION
                'Required security approvals are missing';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER protected_merge_guard
BEFORE UPDATE OF state ON pull_request
FOR EACH ROW
EXECUTE FUNCTION prevent_protected_direct_merge();

CREATE OR REPLACE FUNCTION log_pull_request_state_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state IS DISTINCT FROM NEW.state THEN
        INSERT INTO audit_event (
            repository_id,
            actor_user_id,
            event_type,
            event_data
        )
        VALUES (
            NEW.repository_id,
            NEW.author_user_id,
            'PULL_REQUEST_STATE_CHANGED',
            jsonb_build_object(
                'pull_request_id', NEW.pull_request_id,
                'old_state', OLD.state,
                'new_state', NEW.state
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER pull_request_audit_trigger
AFTER UPDATE OF state ON pull_request
FOR EACH ROW
EXECUTE FUNCTION log_pull_request_state_change();

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
    pr RECORD;
    policy RECORD;
    approval_count INTEGER;
    failed_checks INTEGER;
    unresolved_findings INTEGER;
    unresolved_conversations INTEGER;
BEGIN
    SELECT *
    INTO pr
    FROM pull_request
    WHERE pull_request_id = p_pull_request_id;

    IF pr.pull_request_id IS NULL THEN
        RETURN QUERY
        SELECT FALSE, 'Pull Request does not exist';
        RETURN;
    END IF;

    IF pr.state <> 'OPEN' THEN
        RETURN QUERY
        SELECT FALSE, 'Pull Request is not open';
        RETURN;
    END IF;

    SELECT *
    INTO policy
    FROM branch_protection_policy
    WHERE branch_id = pr.target_branch_id;

    IF policy.policy_id IS NULL THEN
        RETURN QUERY
        SELECT TRUE, 'No branch protection policy applies';
        RETURN;
    END IF;

    IF policy.require_up_to_date_branch
       AND NOT pr.branch_up_to_date THEN
        RETURN QUERY
        SELECT FALSE, 'Source branch is not up to date';
        RETURN;
    END IF;

    IF pr.merge_conflict THEN
        RETURN QUERY
        SELECT FALSE, 'Merge conflict exists';
        RETURN;
    END IF;

    SELECT count(*)
    INTO failed_checks
    FROM status_check
    WHERE pull_request_id = p_pull_request_id
      AND required
      AND NOT passed;

    IF policy.require_status_checks
       AND failed_checks > 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Required status check failed';
        RETURN;
    END IF;

    SELECT count(*)
    INTO unresolved_findings
    FROM security_finding
    WHERE pull_request_id = p_pull_request_id
      AND status = 'OPEN';

    IF unresolved_findings > 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Unresolved security finding exists';
        RETURN;
    END IF;

    SELECT count(*)
    INTO unresolved_conversations
    FROM review_comment rc
    JOIN review r
      ON r.review_id = rc.review_id
    WHERE r.pull_request_id = p_pull_request_id
      AND NOT rc.resolved;

    IF policy.require_conversation_resolution
       AND unresolved_conversations > 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Unresolved review conversation exists';
        RETURN;
    END IF;

    SELECT count(DISTINCT r.reviewer_user_id)
    INTO approval_count
    FROM review r
    JOIN repository_user_role rur
      ON rur.user_id = r.reviewer_user_id
    WHERE r.pull_request_id = p_pull_request_id
      AND r.decision = 'APPROVED'
      AND NOT r.stale
      AND NOT r.dismissed
      AND rur.role = 'SECURITY_REVIEWER';

    IF policy.require_reviews
       AND approval_count < policy.required_approvals THEN
        RETURN QUERY
        SELECT FALSE, 'Required approvals are missing or stale';
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'All merge eligibility conditions satisfied';
END;
$$;

CREATE OR REPLACE VIEW v_pull_request_security_status AS
SELECT
    pr.pull_request_id,
    r.name AS repository,
    source.name AS source_branch,
    target.name AS target_branch,
    pr.state,
    pr.branch_up_to_date,
    pr.merge_conflict,
    count(DISTINCT CASE
        WHEN rvw.decision = 'APPROVED'
         AND NOT rvw.stale
         AND NOT rvw.dismissed
         AND rur.role = 'SECURITY_REVIEWER'
        THEN rvw.reviewer_user_id
    END) AS active_security_approvals,
    count(DISTINCT CASE
        WHEN sc.required AND sc.passed
        THEN sc.status_check_id
    END) AS passed_required_checks,
    count(DISTINCT CASE
        WHEN sc.required AND NOT sc.passed
        THEN sc.status_check_id
    END) AS failed_required_checks,
    count(DISTINCT CASE
        WHEN sf.status = 'OPEN'
        THEN sf.finding_id
    END) AS open_security_findings,
    count(DISTINCT CASE
        WHEN NOT rc.resolved
        THEN rc.comment_id
    END) AS unresolved_comments
FROM pull_request pr
JOIN repository r
  ON r.repository_id = pr.repository_id
JOIN branch source
  ON source.branch_id = pr.source_branch_id
JOIN branch target
  ON target.branch_id = pr.target_branch_id
LEFT JOIN review rvw
  ON rvw.pull_request_id = pr.pull_request_id
LEFT JOIN repository_user_role rur
  ON rur.user_id = rvw.reviewer_user_id
LEFT JOIN status_check sc
  ON sc.pull_request_id = pr.pull_request_id
LEFT JOIN security_finding sf
  ON sf.pull_request_id = pr.pull_request_id
LEFT JOIN review_comment rc
  ON rc.review_id = rvw.review_id
GROUP BY
    pr.pull_request_id,
    r.name,
    source.name,
    target.name,
    pr.state,
    pr.branch_up_to_date,
    pr.merge_conflict;

INSERT INTO repository (
    name,
    owner_team,
    is_private
)
VALUES (
    'secure-web-platform',
    'application-security',
    TRUE
);

INSERT INTO repository_user (
    username,
    email
)
VALUES
    (
        'application-owner',
        'application-owner@example.com'
    ),
    (
        'security-analyst',
        'security-analyst@example.com'
    ),
    (
        'security-lead',
        'security-lead@example.com'
    ),
    (
        'developer-one',
        'developer-one@example.com'
    );

INSERT INTO repository_user_role (user_id, role)
SELECT user_id, 'DEVELOPER'
FROM repository_user
WHERE username IN ('application-owner', 'developer-one');

INSERT INTO repository_user_role (user_id, role)
SELECT user_id, 'SECURITY_REVIEWER'
FROM repository_user
WHERE username IN ('security-analyst', 'security-lead');

INSERT INTO repository_user_role (user_id, role)
SELECT user_id, 'ADMINISTRATOR'
FROM repository_user
WHERE username = 'application-owner';

INSERT INTO branch (
    repository_id,
    name,
    is_default,
    commit_sha
)
SELECT
    repository_id,
    'main',
    TRUE,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO branch (
    repository_id,
    name,
    is_default,
    commit_sha
)
SELECT
    repository_id,
    'feature/input-validation',
    FALSE,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO commit_record (
    repository_id,
    sha,
    author_user_id,
    message
)
SELECT
    r.repository_id,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    u.user_id,
    'Establish protected production branch'
FROM repository r
JOIN repository_user u
  ON u.username = 'application-owner'
WHERE r.name = 'secure-web-platform';

INSERT INTO commit_record (
    repository_id,
    sha,
    author_user_id,
    parent_sha,
    message
)
SELECT
    r.repository_id,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    u.user_id,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'Add secure request validation'
FROM repository r
JOIN repository_user u
  ON u.username = 'developer-one'
WHERE r.name = 'secure-web-platform';

INSERT INTO pull_request (
    repository_id,
    source_branch_id,
    target_branch_id,
    author_user_id,
    title,
    description,
    source_commit_sha,
    target_commit_sha
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    author.user_id,
    'Harden web request validation',
    'Reject unsafe paths, oversized requests, and insecure request states.',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
FROM repository r
JOIN branch source
  ON source.repository_id = r.repository_id
 AND source.name = 'feature/input-validation'
JOIN branch target
  ON target.repository_id = r.repository_id
 AND target.name = 'main'
JOIN repository_user author
  ON author.username = 'application-owner'
WHERE r.name = 'secure-web-platform';

INSERT INTO pull_request_file (
    pull_request_id,
    path,
    additions,
    deletions
)
SELECT
    pull_request_id,
    'src/security/RequestValidator.java',
    85,
    12
FROM pull_request
WHERE title = 'Harden web request validation';

INSERT INTO pull_request_file (
    pull_request_id,
    path,
    additions,
    deletions
)
SELECT
    pull_request_id,
    'src/security/SecurityHeaders.java',
    60,
    4
FROM pull_request
WHERE title = 'Harden web request validation';

INSERT INTO pull_request_commit (
    pull_request_id,
    commit_id
)
SELECT
    pr.pull_request_id,
    c.commit_id
FROM pull_request pr
JOIN commit_record c
  ON c.sha = pr.source_commit_sha
WHERE pr.title = 'Harden web request validation';

INSERT INTO review (
    pull_request_id,
    reviewer_user_id,
    decision
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'APPROVED'
FROM pull_request pr
JOIN repository_user u
  ON u.username = 'security-analyst'
WHERE pr.title = 'Harden web request validation';

INSERT INTO review (
    pull_request_id,
    reviewer_user_id,
    decision
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'APPROVED'
FROM pull_request pr
JOIN repository_user u
  ON u.username = 'security-lead'
WHERE pr.title = 'Harden web request validation';

INSERT INTO status_check (
    pull_request_id,
    name,
    required,
    passed,
    details,
    completed_at
)
SELECT
    pull_request_id,
    'unit-tests',
    TRUE,
    TRUE,
    'Security validation tests passed.',
    now()
FROM pull_request
WHERE title = 'Harden web request validation';

INSERT INTO status_check (
    pull_request_id,
    name,
    required,
    passed,
    details,
    completed_at
)
SELECT
    pull_request_id,
    'static-security-analysis',
    TRUE,
    TRUE,
    'No blocking findings detected.',
    now()
FROM pull_request
WHERE title = 'Harden web request validation';

INSERT INTO status_check (
    pull_request_id,
    name,
    required,
    passed,
    details,
    completed_at
)
SELECT
    pull_request_id,
    'dependency-audit',
    TRUE,
    TRUE,
    'Dependency audit passed.',
    now()
FROM pull_request
WHERE title = 'Harden web request validation';

INSERT INTO branch_protection_policy (
    branch_id,
    require_status_checks,
    require_reviews,
    required_approvals,
    dismiss_stale_approvals,
    require_conversation_resolution,
    require_up_to_date_branch,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion,
    require_linear_history,
    allow_administrator_bypass
)
SELECT
    branch_id,
    TRUE,
    TRUE,
    2,
    TRUE,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    TRUE,
    FALSE
FROM branch
WHERE name = 'main';

INSERT INTO approval_requirement (
    policy_id,
    role,
    required_count
)
SELECT
    policy_id,
    'SECURITY_REVIEWER',
    2
FROM branch_protection_policy
JOIN branch
  ON branch.branch_id = branch_protection_policy.branch_id
WHERE branch.name = 'main';

INSERT INTO asset (
    repository_id,
    name,
    type,
    confidentiality,
    integrity,
    availability,
    owner_team
)
SELECT
    repository_id,
    'credential-store',
    'CREDENTIAL',
    'CRITICAL',
    'HIGH',
    'MEDIUM',
    'identity-service'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO asset (
    repository_id,
    name,
    type,
    confidentiality,
    integrity,
    availability,
    owner_team
)
SELECT
    repository_id,
    'session-store',
    'SESSION',
    'CRITICAL',
    'CRITICAL',
    'HIGH',
    'web-platform'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO asset (
    repository_id,
    name,
    type,
    confidentiality,
    integrity,
    availability,
    owner_team
)
SELECT
    repository_id,
    'customer-data',
    'DATABASE',
    'HIGH',
    'HIGH',
    'HIGH',
    'data-platform'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO asset (
    repository_id,
    name,
    type,
    confidentiality,
    integrity,
    availability,
    owner_team
)
SELECT
    repository_id,
    'public-api',
    'API',
    'MEDIUM',
    'HIGH',
    'CRITICAL',
    'platform-team'
FROM repository
WHERE name = 'secure-web-platform';

INSERT INTO threat (
    asset_id,
    name,
    category,
    likelihood,
    impact,
    mitigation
)
SELECT
    a.asset_id,
    'Credential stuffing',
    'SPOOFING',
    'HIGH',
    'CRITICAL',
    'Rate limiting, strong password hashing and MFA.'
FROM asset a
WHERE a.name = 'credential-store';

INSERT INTO threat (
    asset_id,
    name,
    category,
    likelihood,
    impact,
    mitigation
)
SELECT
    a.asset_id,
    'Session theft',
    'SPOOFING',
    'HIGH',
    'CRITICAL',
    'TLS, Secure cookies and session rotation.'
FROM asset a
WHERE a.name = 'session-store';

INSERT INTO threat (
    asset_id,
    name,
    category,
    likelihood,
    impact,
    mitigation
)
SELECT
    a.asset_id,
    'SQL injection',
    'TAMPERING',
    'HIGH',
    'CRITICAL',
    'Parameterized queries and least-privilege database access.'
FROM asset a
WHERE a.name = 'customer-data';

INSERT INTO threat (
    asset_id,
    name,
    category,
    likelihood,
    impact,
    mitigation
)
SELECT
    a.asset_id,
    'Cross-site scripting',
    'INFORMATION_DISCLOSURE',
    'HIGH',
    'HIGH',
    'Output encoding and restrictive Content Security Policy.'
FROM asset a
WHERE a.name = 'customer-data';

INSERT INTO threat (
    asset_id,
    name,
    category,
    likelihood,
    impact,
    mitigation
)
SELECT
    a.asset_id,
    'API resource exhaustion',
    'DENIAL_OF_SERVICE',
    'MEDIUM',
    'CRITICAL',
    'Rate limits, request-size limits and bounded work.'
FROM asset a
WHERE a.name = 'public-api';

INSERT INTO security_finding (
    pull_request_id,
    identifier,
    severity,
    status,
    description
)
SELECT
    pull_request_id,
    'SEC-001',
    'MEDIUM',
    'RESOLVED',
    'Unsafe request-path validation was corrected.'
FROM pull_request
WHERE title = 'Harden web request validation';

BEGIN;

WITH target AS (
    SELECT pull_request_id
    FROM pull_request
    WHERE title = 'Harden web request validation'
)
UPDATE pull_request
SET updated_at = now()
WHERE pull_request_id IN (
    SELECT pull_request_id FROM target
);

COMMIT;

SELECT
    t.name AS threat,
    t.category,
    (
        CASE t.likelihood
            WHEN 'LOW' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'CRITICAL' THEN 4
        END
        *
        CASE t.impact
            WHEN 'LOW' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'CRITICAL' THEN 4
        END
    ) AS risk_score,
    a.name AS asset,
    t.mitigation
FROM threat t
JOIN asset a ON a.asset_id = t.asset_id
ORDER BY risk_score DESC, t.name;

SELECT *
FROM v_pull_request_security_status
ORDER BY pull_request_id;

SELECT *
FROM merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_request
        WHERE title = 'Harden web request validation'
    )
);

SELECT
    r.name AS repository,
    b.name AS protected_branch,
    p.required_approvals,
    p.require_status_checks,
    p.require_conversation_resolution,
    p.allow_direct_push,
    p.allow_force_push,
    p.allow_branch_deletion,
    p.require_linear_history
FROM branch_protection_policy p
JOIN branch b
  ON b.branch_id = p.branch_id
JOIN repository r
  ON r.repository_id = b.repository_id;

WITH required_checks AS (
    SELECT
        pr.pull_request_id,
        count(*) FILTER (
            WHERE sc.required
        ) AS required_count,
        count(*) FILTER (
            WHERE sc.required AND sc.passed
        ) AS passed_count
    FROM pull_request pr
    LEFT JOIN status_check sc
      ON sc.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    required_checks.required_count,
    required_checks.passed_count,
    CASE
        WHEN required_checks.required_count =
             required_checks.passed_count
        THEN 'PASS'
        ELSE 'BLOCKED'
    END AS status_check_state
FROM pull_request pr
JOIN required_checks
  ON required_checks.pull_request_id = pr.pull_request_id;

SELECT
    r.name AS repository,
    count(DISTINCT pr.pull_request_id) AS pull_requests,
    count(DISTINCT sf.finding_id)
        FILTER (WHERE sf.status = 'OPEN') AS open_findings,
    count(DISTINCT rc.comment_id)
        FILTER (WHERE NOT rc.resolved) AS unresolved_comments
FROM repository r
LEFT JOIN pull_request pr
  ON pr.repository_id = r.repository_id
LEFT JOIN security_finding sf
  ON sf.pull_request_id = pr.pull_request_id
LEFT JOIN review rv
  ON rv.pull_request_id = pr.pull_request_id
LEFT JOIN review_comment rc
  ON rc.review_id = rv.review_id
GROUP BY r.repository_id, r.name;

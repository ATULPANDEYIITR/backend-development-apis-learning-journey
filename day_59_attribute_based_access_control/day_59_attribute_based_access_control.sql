DROP SCHEMA IF EXISTS abac CASCADE;
CREATE SCHEMA abac;

SET search_path TO abac, public;

CREATE TYPE user_status AS ENUM ('active', 'suspended', 'disabled');
CREATE TYPE policy_effect AS ENUM ('allow', 'deny');
CREATE TYPE request_decision AS ENUM ('allow', 'deny');
CREATE TYPE review_state AS ENUM (
    'commented',
    'approved',
    'changes_requested',
    'dismissed'
);

CREATE TABLE users (
    user_id              BIGSERIAL PRIMARY KEY,
    username             TEXT NOT NULL UNIQUE,
    department           TEXT NOT NULL,
    clearance_level      INTEGER NOT NULL CHECK (clearance_level BETWEEN 0 AND 5),
    status               user_status NOT NULL DEFAULT 'active',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
    role_id              BIGSERIAL PRIMARY KEY,
    role_name            TEXT NOT NULL UNIQUE
);

CREATE TABLE user_roles (
    user_id              BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id              BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE resources (
    resource_id          BIGSERIAL PRIMARY KEY,
    resource_name        TEXT NOT NULL UNIQUE,
    resource_type        TEXT NOT NULL,
    owner_department     TEXT NOT NULL,
    classification_level INTEGER NOT NULL CHECK (classification_level BETWEEN 0 AND 5),
    active               BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE actions (
    action_id            BIGSERIAL PRIMARY KEY,
    action_name          TEXT NOT NULL UNIQUE
);

CREATE TABLE policies (
    policy_id            BIGSERIAL PRIMARY KEY,
    policy_name          TEXT NOT NULL UNIQUE,
    effect               policy_effect NOT NULL,
    priority             INTEGER NOT NULL CHECK (priority >= 0),
    enabled              BOOLEAN NOT NULL DEFAULT true,
    description          TEXT NOT NULL
);

CREATE TABLE policy_actions (
    policy_id            BIGINT NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,
    action_id            BIGINT NOT NULL REFERENCES actions(action_id) ON DELETE CASCADE,
    PRIMARY KEY (policy_id, action_id)
);

CREATE TABLE policy_conditions (
    condition_id         BIGSERIAL PRIMARY KEY,
    policy_id            BIGINT NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,
    attribute_name       TEXT NOT NULL,
    operator_name        TEXT NOT NULL CHECK (
        operator_name IN (
            'equals',
            'not_equals',
            'in',
            'gte',
            'lte',
            'contains',
            'cidr'
        )
    ),
    expected_value       TEXT NOT NULL,
    condition_order      INTEGER NOT NULL CHECK (condition_order >= 1),
    UNIQUE (policy_id, condition_order)
);

CREATE TABLE repositories (
    repository_id        BIGSERIAL PRIMARY KEY,
    repository_name      TEXT NOT NULL UNIQUE,
    owner_team           TEXT NOT NULL
);

CREATE TABLE branches (
    branch_id            BIGSERIAL PRIMARY KEY,
    repository_id        BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    branch_name          TEXT NOT NULL,
    is_protected         BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (repository_id, branch_name)
);

CREATE TABLE branch_protection_policies (
    protection_id                    BIGSERIAL PRIMARY KEY,
    branch_id                        BIGINT NOT NULL UNIQUE REFERENCES branches(branch_id) ON DELETE CASCADE,
    required_approvals               INTEGER NOT NULL DEFAULT 0 CHECK (required_approvals >= 0),
    require_conversation_resolution  BOOLEAN NOT NULL DEFAULT true,
    restrict_direct_push             BOOLEAN NOT NULL DEFAULT true,
    restrict_force_push              BOOLEAN NOT NULL DEFAULT true,
    require_linear_history           BOOLEAN NOT NULL DEFAULT false,
    allow_administrator_bypass       BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE commits (
    commit_id           BIGSERIAL PRIMARY KEY,
    repository_id       BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    commit_sha          CHAR(40) NOT NULL,
    author_user_id      BIGINT NOT NULL REFERENCES users(user_id),
    committed_at        TIMESTAMPTZ NOT NULL,
    message             TEXT NOT NULL,
    UNIQUE (repository_id, commit_sha)
);

CREATE TABLE pull_requests (
    pull_request_id       BIGSERIAL PRIMARY KEY,
    repository_id         BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    source_branch_id      BIGINT NOT NULL REFERENCES branches(branch_id),
    target_branch_id      BIGINT NOT NULL REFERENCES branches(branch_id),
    author_user_id        BIGINT NOT NULL REFERENCES users(user_id),
    title                 TEXT NOT NULL,
    state                 TEXT NOT NULL CHECK (state IN ('open', 'closed', 'merged')),
    is_draft              BOOLEAN NOT NULL DEFAULT false,
    mergeable             BOOLEAN NOT NULL DEFAULT true,
    conversations_resolved BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at             TIMESTAMPTZ,
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE pull_request_commits (
    pull_request_id      BIGINT NOT NULL REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    commit_id            BIGINT NOT NULL REFERENCES commits(commit_id),
    position             INTEGER NOT NULL CHECK (position >= 1),
    PRIMARY KEY (pull_request_id, commit_id),
    UNIQUE (pull_request_id, position)
);

CREATE TABLE reviewers (
    reviewer_id          BIGSERIAL PRIMARY KEY,
    user_id              BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    team_name            TEXT NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (user_id, team_name)
);

CREATE TABLE pull_request_reviews (
    review_id            BIGSERIAL PRIMARY KEY,
    pull_request_id      BIGINT NOT NULL REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_id          BIGINT NOT NULL REFERENCES reviewers(reviewer_id),
    state                 review_state NOT NULL,
    submitted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale                 BOOLEAN NOT NULL DEFAULT false,
    body                  TEXT
);

CREATE TABLE review_comments (
    comment_id            BIGSERIAL PRIMARY KEY,
    review_id             BIGINT NOT NULL REFERENCES pull_request_reviews(review_id) ON DELETE CASCADE,
    file_path             TEXT NOT NULL,
    line_number           INTEGER CHECK (line_number > 0),
    body                  TEXT NOT NULL,
    resolved               BOOLEAN NOT NULL DEFAULT false,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE status_checks (
    status_check_id       BIGSERIAL PRIMARY KEY,
    pull_request_id       BIGINT NOT NULL REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    check_name            TEXT NOT NULL,
    required              BOOLEAN NOT NULL DEFAULT false,
    passed                BOOLEAN NOT NULL DEFAULT false,
    completed_at          TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE required_status_checks (
    protection_id         BIGINT NOT NULL REFERENCES branch_protection_policies(protection_id) ON DELETE CASCADE,
    check_name            TEXT NOT NULL,
    PRIMARY KEY (protection_id, check_name)
);

CREATE TABLE authorization_requests (
    request_id            BIGSERIAL PRIMARY KEY,
    user_id               BIGINT NOT NULL REFERENCES users(user_id),
    resource_id           BIGINT NOT NULL REFERENCES resources(resource_id),
    action_id              BIGINT NOT NULL REFERENCES actions(action_id),
    source_ip              INET NOT NULL,
    country_code           CHAR(2) NOT NULL,
    trusted_device         BOOLEAN NOT NULL,
    mfa_verified           BOOLEAN NOT NULL,
    environment_name      TEXT NOT NULL,
    emergency_ticket      TEXT,
    requested_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE authorization_decisions (
    decision_id            BIGSERIAL PRIMARY KEY,
    request_id             BIGINT NOT NULL REFERENCES authorization_requests(request_id) ON DELETE CASCADE,
    decision                request_decision NOT NULL,
    reason                  TEXT NOT NULL,
    decided_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE policy_decision_matches (
    decision_id            BIGINT NOT NULL REFERENCES authorization_decisions(decision_id) ON DELETE CASCADE,
    policy_id              BIGINT NOT NULL REFERENCES policies(policy_id),
    PRIMARY KEY (decision_id, policy_id)
);

CREATE INDEX idx_user_roles_role
    ON user_roles(role_id);

CREATE INDEX idx_resources_type_classification
    ON resources(resource_type, classification_level);

CREATE INDEX idx_policies_priority_enabled
    ON policies(enabled, priority DESC);

CREATE INDEX idx_pr_reviews_pr_state
    ON pull_request_reviews(pull_request_id, state, stale);

CREATE INDEX idx_status_checks_pr_required
    ON status_checks(pull_request_id, required, passed);

CREATE INDEX idx_auth_requests_user_time
    ON authorization_requests(user_id, requested_at DESC);

CREATE INDEX idx_auth_decisions_request
    ON authorization_decisions(request_id);

CREATE OR REPLACE FUNCTION prevent_invalid_review()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pr_author BIGINT;
    reviewer_user BIGINT;
BEGIN
    SELECT author_user_id
    INTO pr_author
    FROM pull_requests
    WHERE pull_request_id = NEW.pull_request_id;

    SELECT user_id
    INTO reviewer_user
    FROM reviewers
    WHERE reviewer_id = NEW.reviewer_id
      AND active = true;

    IF reviewer_user IS NULL THEN
        RAISE EXCEPTION 'Reviewer is inactive or does not exist';
    END IF;

    IF reviewer_user = pr_author AND NEW.state = 'approved' THEN
        RAISE EXCEPTION 'Pull Request author cannot approve own Pull Request';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_review
BEFORE INSERT OR UPDATE ON pull_request_reviews
FOR EACH ROW
EXECUTE FUNCTION prevent_invalid_review();

CREATE OR REPLACE FUNCTION protect_branch_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_protected BOOLEAN;
BEGIN
    SELECT is_protected
    INTO target_protected
    FROM branches
    WHERE branch_id = NEW.target_branch_id;

    IF target_protected AND NEW.state = 'merged' THEN
        IF NEW.is_draft THEN
            RAISE EXCEPTION 'Draft Pull Request cannot be merged';
        END IF;

        IF NOT NEW.mergeable THEN
            RAISE EXCEPTION 'Pull Request has merge conflicts';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_merge_state
BEFORE UPDATE OF state ON pull_requests
FOR EACH ROW
EXECUTE FUNCTION protect_branch_update();

CREATE OR REPLACE FUNCTION has_required_approvals(
    p_pull_request_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    WITH target_policy AS (
        SELECT bpp.required_approvals
        FROM pull_requests pr
        JOIN branch_protection_policies bpp
          ON bpp.branch_id = pr.target_branch_id
        WHERE pr.pull_request_id = p_pull_request_id
    ),
    eligible_approvals AS (
        SELECT DISTINCT rpr.reviewer_id
        FROM pull_request_reviews rpr
        JOIN reviewers r
          ON r.reviewer_id = rpr.reviewer_id
        WHERE rpr.pull_request_id = p_pull_request_id
          AND rpr.state = 'approved'
          AND rpr.stale = false
          AND r.active = true
          AND r.user_id <> (
              SELECT author_user_id
              FROM pull_requests
              WHERE pull_request_id = p_pull_request_id
          )
    )
    SELECT
        COALESCE(
            (SELECT COUNT(*) FROM eligible_approvals),
            0
        ) >= COALESCE(
            (SELECT required_approvals FROM target_policy),
            0
        );
$$;

CREATE OR REPLACE FUNCTION required_checks_pass(
    p_pull_request_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT NOT EXISTS (
        SELECT 1
        FROM required_status_checks rsc
        JOIN branch_protection_policies bpp
          ON bpp.protection_id = rsc.protection_id
        JOIN pull_requests pr
          ON pr.target_branch_id = bpp.branch_id
        LEFT JOIN status_checks sc
          ON sc.pull_request_id = pr.pull_request_id
         AND sc.check_name = rsc.check_name
        WHERE pr.pull_request_id = p_pull_request_id
          AND (sc.status_check_id IS NULL OR sc.passed = false)
    );
$$;

CREATE OR REPLACE FUNCTION merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    pr pull_requests%ROWTYPE;
    protected BOOLEAN;
    required_conversations BOOLEAN;
BEGIN
    SELECT *
    INTO pr
    FROM pull_requests
    WHERE pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Pull Request does not exist';
        RETURN;
    END IF;

    IF pr.state <> 'open' THEN
        RETURN QUERY SELECT false, 'Pull Request is not open';
        RETURN;
    END IF;

    IF pr.is_draft THEN
        RETURN QUERY SELECT false, 'Pull Request is a draft';
        RETURN;
    END IF;

    IF NOT pr.mergeable THEN
        RETURN QUERY SELECT false, 'Merge conflict exists';
        RETURN;
    END IF;

    SELECT
        b.is_protected,
        COALESCE(
            bpp.require_conversation_resolution,
            false
        )
    INTO protected, required_conversations
    FROM branches b
    LEFT JOIN branch_protection_policies bpp
      ON bpp.branch_id = b.branch_id
    WHERE b.branch_id = pr.target_branch_id;

    IF protected THEN
        IF required_conversations AND NOT pr.conversations_resolved THEN
            RETURN QUERY SELECT false, 'Unresolved review conversations';
            RETURN;
        END IF;

        IF NOT has_required_approvals(p_pull_request_id) THEN
            RETURN QUERY SELECT false, 'Required approvals are not satisfied';
            RETURN;
        END IF;

        IF NOT required_checks_pass(p_pull_request_id) THEN
            RETURN QUERY SELECT false, 'Required status checks are not passing';
            RETURN;
        END IF;
    END IF;

    RETURN QUERY SELECT true, 'All merge conditions are satisfied';
END;
$$;

INSERT INTO roles (role_name)
VALUES
    ('analyst'),
    ('manager'),
    ('administrator'),
    ('incident_responder'),
    ('developer'),
    ('security_reviewer');

INSERT INTO actions (action_name)
VALUES
    ('read'),
    ('write'),
    ('delete');

INSERT INTO users (
    username,
    department,
    clearance_level
)
VALUES
    ('alice', 'analytics', 2),
    ('bob', 'operations', 4),
    ('carol', 'security', 5),
    ('dave', 'security', 5),
    ('eve', 'analytics', 1);

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r
  ON (u.username, r.role_name) IN (
      ('alice', 'analyst'),
      ('bob', 'manager'),
      ('carol', 'administrator'),
      ('dave', 'incident_responder'),
      ('dave', 'security_reviewer'),
      ('alice', 'developer')
  );

UPDATE users
SET status = 'suspended'
WHERE username = 'eve';

INSERT INTO resources (
    resource_name,
    resource_type,
    owner_department,
    classification_level
)
VALUES
    ('analytics-report', 'report', 'analytics', 2),
    ('security-report', 'report', 'security', 4),
    ('production-db', 'database', 'security', 5);

INSERT INTO policies (
    policy_name,
    effect,
    priority,
    description
)
VALUES
    (
        'Trusted analysts read internal reports',
        'allow',
        50,
        'Allows analysts to read low-classification reports from trusted devices'
    ),
    (
        'Managers read confidential reports',
        'allow',
        70,
        'Allows managers to read confidential reports when MFA is verified'
    ),
    (
        'Block restricted access from untrusted devices',
        'deny',
        100,
        'Blocks restricted resources from untrusted devices'
    ),
    (
        'Security administrators manage databases',
        'allow',
        90,
        'Allows security administrators to manage production databases'
    ),
    (
        'Incident response emergency read',
        'allow',
        80,
        'Allows incident responders with valid emergency tickets to read reports'
    );

INSERT INTO policy_actions (policy_id, action_id)
SELECT p.policy_id, a.action_id
FROM policies p
JOIN actions a
  ON (
      (p.policy_name = 'Trusted analysts read internal reports' AND a.action_name = 'read')
      OR
      (p.policy_name = 'Managers read confidential reports' AND a.action_name = 'read')
      OR
      (
          p.policy_name = 'Block restricted access from untrusted devices'
          AND a.action_name IN ('read', 'write', 'delete')
      )
      OR
      (
          p.policy_name = 'Security administrators manage databases'
          AND a.action_name IN ('read', 'write', 'delete')
      )
      OR
      (
          p.policy_name = 'Incident response emergency read'
          AND a.action_name = 'read'
      )
  );

INSERT INTO policy_conditions (
    policy_id,
    attribute_name,
    operator_name,
    expected_value,
    condition_order
)
SELECT p.policy_id, v.attribute_name, v.operator_name,
       v.expected_value, v.condition_order
FROM policies p
JOIN (
    VALUES
        (
            'Trusted analysts read internal reports',
            'user.role',
            'equals',
            'analyst',
            1
        ),
        (
            'Trusted analysts read internal reports',
            'resource.classification',
            'lte',
            '2',
            2
        ),
        (
            'Trusted analysts read internal reports',
            'request.trusted_device',
            'equals',
            'true',
            3
        ),
        (
            'Managers read confidential reports',
            'user.role',
            'equals',
            'manager',
            1
        ),
        (
            'Managers read confidential reports',
            'resource.classification',
            'lte',
            '4',
            2
        ),
        (
            'Managers read confidential reports',
            'request.mfa_verified',
            'equals',
            'true',
            3
        ),
        (
            'Block restricted access from untrusted devices',
            'resource.classification',
            'gte',
            '4',
            1
        ),
        (
            'Block restricted access from untrusted devices',
            'request.trusted_device',
            'equals',
            'false',
            2
        ),
        (
            'Security administrators manage databases',
            'user.department',
            'equals',
            'security',
            1
        ),
        (
            'Security administrators manage databases',
            'user.role',
            'equals',
            'administrator',
            2
        ),
        (
            'Security administrators manage databases',
            'request.mfa_verified',
            'equals',
            'true',
            3
        ),
        (
            'Incident response emergency read',
            'user.role',
            'equals',
            'incident_responder',
            1
        ),
        (
            'Incident response emergency read',
            'request.mfa_verified',
            'equals',
            'true',
            2
        )
) AS v(
    policy_name,
    attribute_name,
    operator_name,
    expected_value,
    condition_order
)
ON p.policy_name = v.policy_name;

INSERT INTO repositories (
    repository_name,
    owner_team
)
VALUES
    ('security-platform', 'security-engineering');

INSERT INTO branches (
    repository_id,
    branch_name,
    is_protected
)
SELECT repository_id, branch_name, protected
FROM (
    SELECT repository_id, 'main' AS branch_name, true AS protected
    FROM repositories
    WHERE repository_name = 'security-platform'

    UNION ALL

    SELECT repository_id, 'feature/abac', false
    FROM repositories
    WHERE repository_name = 'security-platform'
) x;

INSERT INTO branch_protection_policies (
    branch_id,
    required_approvals,
    require_conversation_resolution,
    restrict_direct_push,
    restrict_force_push,
    require_linear_history,
    allow_administrator_bypass
)
SELECT
    branch_id,
    2,
    true,
    true,
    true,
    true,
    false
FROM branches
WHERE branch_name = 'main';

INSERT INTO required_status_checks (
    protection_id,
    check_name
)
SELECT protection_id, check_name
FROM branch_protection_policies
CROSS JOIN (
    VALUES
        ('ci/build'),
        ('security/scan')
) AS checks(check_name);

INSERT INTO commits (
    repository_id,
    commit_sha,
    author_user_id,
    committed_at,
    message
)
SELECT
    r.repository_id,
    x.sha,
    u.user_id,
    now(),
    x.message
FROM repositories r
JOIN users u
  ON u.username = 'alice'
CROSS JOIN (
    VALUES
        (
            '0123456789abcdef0123456789abcdef01234567',
            'Add ABAC policy evaluator'
        ),
        (
            '89abcdef0123456789abcdef0123456789abcdef',
            'Add authorization audit events'
        )
) AS x(sha, message)
WHERE r.repository_name = 'security-platform';

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    author_user_id,
    title,
    state,
    is_draft,
    mergeable,
    conversations_resolved
)
SELECT
    r.repository_id,
    source_branch.branch_id,
    target_branch.branch_id,
    u.user_id,
    'Implement contextual authorization',
    'open',
    false,
    true,
    true
FROM repositories r
JOIN branches source_branch
  ON source_branch.repository_id = r.repository_id
 AND source_branch.branch_name = 'feature/abac'
JOIN branches target_branch
  ON target_branch.repository_id = r.repository_id
 AND target_branch.branch_name = 'main'
JOIN users u
  ON u.username = 'alice'
WHERE r.repository_name = 'security-platform';

INSERT INTO pull_request_commits (
    pull_request_id,
    commit_id,
    position
)
SELECT
    pr.pull_request_id,
    c.commit_id,
    row_number() OVER (ORDER BY c.commit_id)
FROM pull_requests pr
JOIN commits c
  ON c.repository_id = pr.repository_id
WHERE pr.title = 'Implement contextual authorization';

INSERT INTO reviewers (user_id, team_name)
SELECT user_id, 'security-review'
FROM users
WHERE username IN ('bob', 'carol');

INSERT INTO pull_request_reviews (
    pull_request_id,
    reviewer_id,
    state,
    stale,
    body
)
SELECT
    pr.pull_request_id,
    r.reviewer_id,
    'approved',
    false,
    CASE
        WHEN u.username = 'bob'
        THEN 'Business policy review passed'
        ELSE 'Security review passed'
    END
FROM pull_requests pr
JOIN reviewers r
  ON true
JOIN users u
  ON u.user_id = r.user_id
WHERE pr.title = 'Implement contextual authorization'
  AND u.username IN ('bob', 'carol');

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    required,
    passed,
    completed_at
)
SELECT
    pr.pull_request_id,
    checks.check_name,
    true,
    true,
    now()
FROM pull_requests pr
CROSS JOIN (
    VALUES ('ci/build'), ('security/scan')
) AS checks(check_name)
WHERE pr.title = 'Implement contextual authorization';

CREATE OR REPLACE VIEW pull_request_review_status AS
SELECT
    pr.pull_request_id,
    pr.title,
    pr.state,
    pr.is_draft,
    pr.mergeable,
    COUNT(DISTINCT rpr.review_id)
        FILTER (WHERE rpr.state = 'approved' AND NOT rpr.stale)
        AS current_approvals,
    COUNT(DISTINCT rc.comment_id)
        FILTER (WHERE rc.resolved = false)
        AS unresolved_comments,
    COUNT(DISTINCT sc.status_check_id)
        FILTER (WHERE sc.required AND sc.passed)
        AS passing_required_checks
FROM pull_requests pr
LEFT JOIN pull_request_reviews rpr
  ON rpr.pull_request_id = pr.pull_request_id
LEFT JOIN review_comments rc
  ON rc.review_id = rpr.review_id
LEFT JOIN status_checks sc
  ON sc.pull_request_id = pr.pull_request_id
GROUP BY
    pr.pull_request_id,
    pr.title,
    pr.state,
    pr.is_draft,
    pr.mergeable;

CREATE OR REPLACE VIEW protected_branch_report AS
SELECT
    r.repository_name,
    b.branch_name,
    bpp.required_approvals,
    bpp.require_conversation_resolution,
    bpp.restrict_direct_push,
    bpp.restrict_force_push,
    bpp.require_linear_history,
    bpp.allow_administrator_bypass
FROM repositories r
JOIN branches b
  ON b.repository_id = r.repository_id
JOIN branch_protection_policies bpp
  ON bpp.branch_id = b.branch_id
WHERE b.is_protected;

CREATE OR REPLACE FUNCTION evaluate_authorization(
    p_user_id BIGINT,
    p_resource_id BIGINT,
    p_action_name TEXT,
    p_source_ip INET,
    p_country_code CHAR(2),
    p_trusted_device BOOLEAN,
    p_mfa_verified BOOLEAN,
    p_environment TEXT,
    p_emergency_ticket TEXT DEFAULT NULL
)
RETURNS TABLE (
    decision request_decision,
    reason TEXT,
    matched_policy_ids BIGINT[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user users%ROWTYPE;
    v_resource resources%ROWTYPE;
    v_action_id BIGINT;
    v_decision request_decision := 'deny';
    v_reason TEXT := 'Default deny';
    v_matched BIGINT[] := '{}';
BEGIN
    SELECT *
    INTO v_user
    FROM users
    WHERE user_id = p_user_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'deny'::request_decision,
            'User does not exist',
            '{}'::BIGINT[];
        RETURN;
    END IF;

    SELECT *
    INTO v_resource
    FROM resources
    WHERE resource_id = p_resource_id
      AND active = true;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'deny'::request_decision,
            'Resource does not exist or is inactive',
            '{}'::BIGINT[];
        RETURN;
    END IF;

    SELECT action_id
    INTO v_action_id
    FROM actions
    WHERE action_name = p_action_name;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'deny'::request_decision,
            'Action is not registered',
            '{}'::BIGINT[];
        RETURN;
    END IF;

    IF v_user.status <> 'active' THEN
        RETURN QUERY SELECT 'deny'::request_decision,
            'User is not active',
            '{}'::BIGINT[];
        RETURN;
    END IF;

    IF v_user.clearance_level < v_resource.classification_level THEN
        RETURN QUERY SELECT 'deny'::request_decision,
            'User clearance is below resource classification',
            '{}'::BIGINT[];
        RETURN;
    END IF;

    WITH matching AS (
        SELECT DISTINCT
            p.policy_id,
            p.effect,
            p.priority
        FROM policies p
        JOIN policy_actions pa
          ON pa.policy_id = p.policy_id
        JOIN policy_conditions pc
          ON pc.policy_id = p.policy_id
        WHERE p.enabled
          AND pa.action_id = v_action_id
        GROUP BY p.policy_id, p.effect, p.priority
        HAVING COUNT(*) = (
            SELECT COUNT(*)
            FROM policy_conditions required
            WHERE required.policy_id = p.policy_id
        )
        AND bool_and(
            CASE pc.attribute_name
                WHEN 'user.role'
                    THEN EXISTS (
                        SELECT 1
                        FROM user_roles ur
                        JOIN roles r ON r.role_id = ur.role_id
                        WHERE ur.user_id = v_user.user_id
                          AND r.role_name = pc.expected_value
                    )
                WHEN 'user.department'
                    THEN (
                        v_user.department = pc.expected_value
                    )
                WHEN 'resource.classification'
                    THEN CASE pc.operator_name
                        WHEN 'lte'
                            THEN v_resource.classification_level
                                 <= pc.expected_value::INTEGER
                        WHEN 'gte'
                            THEN v_resource.classification_level
                                 >= pc.expected_value::INTEGER
                        ELSE false
                    END
                WHEN 'request.trusted_device'
                    THEN (
                        p_trusted_device::TEXT = pc.expected_value
                    )
                WHEN 'request.mfa_verified'
                    THEN (
                        p_mfa_verified::TEXT = pc.expected_value
                    )
                ELSE false
            END
        )
    ),
    ordered AS (
        SELECT *
        FROM matching
        ORDER BY priority DESC, policy_id
    )
    SELECT
        COALESCE(
            array_agg(policy_id),
            '{}'
        ),
        CASE
            WHEN bool_or(effect = 'deny') THEN 'deny'
            WHEN bool_or(effect = 'allow') THEN 'allow'
            ELSE 'deny'
        END::request_decision
    INTO v_matched, v_decision
    FROM ordered;

    IF v_decision = 'allow' THEN
        v_reason := 'Applicable allow policy matched';
    ELSE
        v_reason := 'No applicable allow policy or explicit deny';
    END IF;

    RETURN QUERY
    SELECT v_decision, v_reason, v_matched;
END;
$$;

-- Pull Request merge eligibility.
SELECT *
FROM merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Implement contextual authorization'
    )
);

-- Review, approval, and status-check reporting.
SELECT *
FROM pull_request_review_status;

-- Repository branch-protection configuration.
SELECT *
FROM protected_branch_report;

-- Authorization reporting by user and decision.
WITH sample_requests AS (
    SELECT
        u.user_id,
        r.resource_id,
        a.action_id,
        u.username,
        r.resource_name,
        a.action_name
    FROM users u
    CROSS JOIN resources r
    CROSS JOIN actions a
    WHERE u.username IN ('alice', 'bob', 'carol')
      AND r.resource_name IN (
          'analytics-report',
          'security-report',
          'production-db'
      )
      AND a.action_name IN ('read', 'write')
)
SELECT
    username,
    resource_name,
    action_name,
    CASE
        WHEN clearance_level >= classification_level
        THEN 'clearance-sufficient'
        ELSE 'clearance-insufficient'
    END AS clearance_evaluation
FROM sample_requests sr
JOIN users u
  ON u.user_id = sr.user_id
JOIN resources r
  ON r.resource_id = sr.resource_id
ORDER BY username, resource_name, action_name;

-- Transactional example: record an authorization request and its decision atomically.
BEGIN;

WITH inserted_request AS (
    INSERT INTO authorization_requests (
        user_id,
        resource_id,
        action_id,
        source_ip,
        country_code,
        trusted_device,
        mfa_verified,
        environment_name
    )
    SELECT
        u.user_id,
        r.resource_id,
        a.action_id,
        '10.20.30.40'::inet,
        'IN',
        true,
        true,
        'production'
    FROM users u
    JOIN resources r
      ON r.resource_name = 'analytics-report'
    JOIN actions a
      ON a.action_name = 'read'
    WHERE u.username = 'alice'
    RETURNING *
)
INSERT INTO authorization_decisions (
    request_id,
    decision,
    reason
)
SELECT
    request_id,
    'allow',
    'Trusted analyst access policy satisfied'
FROM inserted_request;

COMMIT;

-- Demonstrate the authorization audit trail.
SELECT
    ar.request_id,
    u.username,
    r.resource_name,
    a.action_name,
    ar.source_ip,
    ar.trusted_device,
    ar.mfa_verified,
    ad.decision,
    ad.reason,
    ad.decided_at
FROM authorization_requests ar
JOIN users u
  ON u.user_id = ar.user_id
JOIN resources r
  ON r.resource_id = ar.resource_id
JOIN actions a
  ON a.action_id = ar.action_id
JOIN authorization_decisions ad
  ON ad.request_id = ar.request_id
ORDER BY ad.decided_at DESC;

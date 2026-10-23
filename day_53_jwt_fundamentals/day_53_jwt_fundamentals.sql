DROP SCHEMA IF EXISTS jwt_fundamentals CASCADE;
CREATE SCHEMA jwt_fundamentals;
SET search_path TO jwt_fundamentals;

-- A JWT is represented relationally as an issued security credential.
-- The token itself remains compact serialization at the application edge,
-- while claims and security state are stored in queryable form here.

CREATE TYPE token_status AS ENUM (
    'active',
    'revoked',
    'expired'
);

CREATE TYPE review_scope AS ENUM (
    'repository:read',
    'repository:write',
    'repository:admin'
);

CREATE TABLE applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_name TEXT NOT NULL UNIQUE,
    issuer TEXT NOT NULL UNIQUE,
    audience TEXT NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'HS256',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT applications_algorithm_chk
        CHECK (algorithm = 'HS256'),
    CONSTRAINT applications_name_chk
        CHECK (length(trim(application_name)) >= 3),
    CONSTRAINT applications_issuer_chk
        CHECK (length(trim(issuer)) >= 3),
    CONSTRAINT applications_audience_chk
        CHECK (length(trim(audience)) >= 3)
);

CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_username_chk
        CHECK (length(trim(username)) >= 3),
    CONSTRAINT users_email_chk
        CHECK (position('@' IN email) > 1)
);

CREATE TABLE roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE jwt_tokens (
    token_id UUID PRIMARY KEY,
    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),
    user_id BIGINT NOT NULL
        REFERENCES users(user_id),
    status token_status NOT NULL DEFAULT 'active',
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    token_hash BYTEA NOT NULL UNIQUE,
    CONSTRAINT jwt_token_time_chk
        CHECK (expires_at > issued_at),
    CONSTRAINT jwt_revocation_chk
        CHECK (
            (status = 'revoked' AND revoked_at IS NOT NULL)
            OR
            (status <> 'revoked' AND revoked_at IS NULL)
        )
);

CREATE TABLE token_scopes (
    token_id UUID NOT NULL REFERENCES jwt_tokens(token_id)
        ON DELETE CASCADE,
    scope review_scope NOT NULL,
    PRIMARY KEY (token_id, scope)
);

CREATE TABLE jwt_claims (
    token_id UUID NOT NULL REFERENCES jwt_tokens(token_id)
        ON DELETE CASCADE,
    claim_name TEXT NOT NULL,
    claim_value TEXT NOT NULL,
    PRIMARY KEY (token_id, claim_name),
    CONSTRAINT jwt_claim_name_chk
        CHECK (claim_name NOT IN ('alg', 'typ'))
);

CREATE TABLE required_claim_policies (
    application_id BIGINT NOT NULL
        REFERENCES applications(application_id) ON DELETE CASCADE,
    claim_name TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (application_id, claim_name)
);

CREATE TABLE authorization_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id BIGINT NOT NULL
        REFERENCES applications(application_id) ON DELETE CASCADE,
    required_role TEXT NOT NULL,
    required_scope review_scope NOT NULL,
    UNIQUE (application_id, required_role, required_scope)
);

CREATE INDEX jwt_tokens_user_status_idx
    ON jwt_tokens (user_id, status);

CREATE INDEX jwt_tokens_expiration_idx
    ON jwt_tokens (expires_at)
    WHERE status = 'active';

CREATE INDEX jwt_claims_name_value_idx
    ON jwt_claims (claim_name, claim_value);

CREATE INDEX token_scopes_scope_idx
    ON token_scopes (scope);

CREATE OR REPLACE FUNCTION validate_token_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.expires_at <= NEW.issued_at THEN
        RAISE EXCEPTION
            'JWT expiration must be after issuance';
    END IF;

    IF NEW.status = 'revoked' AND NEW.revoked_at IS NULL THEN
        RAISE EXCEPTION
            'Revoked JWT must have revoked_at';
    END IF;

    IF NEW.status <> 'revoked' AND NEW.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION
            'Only revoked JWTs may have revoked_at';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER jwt_token_state_trigger
BEFORE INSERT OR UPDATE ON jwt_tokens
FOR EACH ROW
EXECUTE FUNCTION validate_token_state();

CREATE OR REPLACE FUNCTION mark_expired_tokens()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    changed_count INTEGER;
BEGIN
    UPDATE jwt_tokens
    SET status = 'expired'
    WHERE status = 'active'
      AND expires_at <= CURRENT_TIMESTAMP;

    GET DIAGNOSTICS changed_count = ROW_COUNT;
    RETURN changed_count;
END;
$$;

CREATE OR REPLACE FUNCTION revoke_jwt(
    requested_token_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE jwt_tokens
    SET status = 'revoked',
        revoked_at = CURRENT_TIMESTAMP
    WHERE token_id = requested_token_id
      AND status = 'active';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active JWT % was not found',
            requested_token_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION jwt_is_merge_authorized(
    requested_token_id UUID,
    requested_scope review_scope
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        t.status = 'active'
        AND t.expires_at > CURRENT_TIMESTAMP
        AND EXISTS (
            SELECT 1
            FROM token_scopes ts
            WHERE ts.token_id = t.token_id
              AND ts.scope = requested_scope
        )
        AND EXISTS (
            SELECT 1
            FROM users u
            WHERE u.user_id = t.user_id
              AND u.active
        )
    FROM jwt_tokens t
    WHERE t.token_id = requested_token_id;
$$;

INSERT INTO applications (
    application_name,
    issuer,
    audience
)
VALUES (
    'Repository API',
    'repository-api',
    'repository-client'
);

INSERT INTO users (
    username,
    email
)
VALUES
    ('atul', 'atul@example.org'),
    ('reviewer01', 'reviewer01@example.org'),
    ('readonly01', 'readonly01@example.org');

INSERT INTO roles (role_name)
VALUES
    ('developer'),
    ('reviewer'),
    ('administrator');

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r
  ON r.role_name = CASE u.username
        WHEN 'atul' THEN 'developer'
        WHEN 'reviewer01' THEN 'reviewer'
        ELSE 'developer'
     END;

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r
  ON r.role_name = 'reviewer'
WHERE u.username = 'atul';

INSERT INTO required_claim_policies (
    application_id,
    claim_name
)
SELECT application_id, claim_name
FROM applications
CROSS JOIN (
    VALUES
        ('iss'),
        ('sub'),
        ('aud'),
        ('iat'),
        ('exp'),
        ('jti')
) AS required(claim_name);

INSERT INTO authorization_policies (
    application_id,
    required_role,
    required_scope
)
SELECT
    application_id,
    'reviewer',
    'repository:write'
FROM applications;

-- The UUID values are fixed only for deterministic SQL examples.
INSERT INTO jwt_tokens (
    token_id,
    application_id,
    user_id,
    status,
    issued_at,
    expires_at,
    token_hash
)
SELECT
    '11111111-1111-1111-1111-111111111111',
    a.application_id,
    u.user_id,
    'active',
    CURRENT_TIMESTAMP - INTERVAL '5 minutes',
    CURRENT_TIMESTAMP + INTERVAL '55 minutes',
    decode(
        md5('token-11111111-1111-1111-1111-111111111111'),
        'hex'
    )
FROM applications a
JOIN users u ON u.username = 'atul';

INSERT INTO jwt_tokens (
    token_id,
    application_id,
    user_id,
    status,
    issued_at,
    expires_at,
    token_hash
)
SELECT
    '22222222-2222-2222-2222-222222222222',
    a.application_id,
    u.user_id,
    'active',
    CURRENT_TIMESTAMP - INTERVAL '2 hours',
    CURRENT_TIMESTAMP - INTERVAL '1 hour',
    decode(
        md5('token-22222222-2222-2222-2222-222222222222'),
        'hex'
    )
FROM applications a
JOIN users u ON u.username = 'reviewer01';

INSERT INTO jwt_tokens (
    token_id,
    application_id,
    user_id,
    status,
    issued_at,
    expires_at,
    token_hash,
    revoked_at
)
SELECT
    '33333333-3333-3333-3333-333333333333',
    a.application_id,
    u.user_id,
    'revoked',
    CURRENT_TIMESTAMP - INTERVAL '30 minutes',
    CURRENT_TIMESTAMP + INTERVAL '30 minutes',
    decode(
        md5('token-33333333-3333-3333-3333-333333333333'),
        'hex'
    ),
    CURRENT_TIMESTAMP - INTERVAL '10 minutes'
FROM applications a
JOIN users u ON u.username = 'atul';

INSERT INTO token_scopes (token_id, scope)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'repository:read'),
    ('11111111-1111-1111-1111-111111111111', 'repository:write'),
    ('33333333-3333-3333-3333-333333333333', 'repository:read');

INSERT INTO jwt_claims (
    token_id,
    claim_name,
    claim_value
)
VALUES
    (
        '11111111-1111-1111-1111-111111111111',
        'iss',
        'repository-api'
    ),
    (
        '11111111-1111-1111-1111-111111111111',
        'sub',
        'atul'
    ),
    (
        '11111111-1111-1111-1111-111111111111',
        'aud',
        'repository-client'
    ),
    (
        '11111111-1111-1111-1111-111111111111',
        'jti',
        '11111111-1111-1111-1111-111111111111'
    ),
    (
        '33333333-3333-3333-3333-333333333333',
        'iss',
        'repository-api'
    ),
    (
        '33333333-3333-3333-3333-333333333333',
        'sub',
        'atul'
    ),
    (
        '33333333-3333-3333-3333-333333333333',
        'aud',
        'repository-client'
    ),
    (
        '33333333-3333-3333-3333-333333333333',
        'jti',
        '33333333-3333-3333-3333-333333333333'
    );

CREATE VIEW active_jwt_credentials AS
SELECT
    t.token_id,
    a.application_name,
    a.issuer,
    a.audience,
    u.username,
    t.issued_at,
    t.expires_at,
    array_agg(ts.scope ORDER BY ts.scope) AS scopes
FROM jwt_tokens t
JOIN applications a
  ON a.application_id = t.application_id
JOIN users u
  ON u.user_id = t.user_id
LEFT JOIN token_scopes ts
  ON ts.token_id = t.token_id
WHERE t.status = 'active'
  AND t.expires_at > CURRENT_TIMESTAMP
GROUP BY
    t.token_id,
    a.application_name,
    a.issuer,
    a.audience,
    u.username,
    t.issued_at,
    t.expires_at;

-- Retrieve valid tokens and their scopes.
SELECT *
FROM active_jwt_credentials
ORDER BY expires_at;

-- Evaluate whether the active token can perform a write operation.
SELECT jwt_is_merge_authorized(
    '11111111-1111-1111-1111-111111111111',
    'repository:write'
) AS can_write;

-- Expired credentials cannot remain active.
SELECT mark_expired_tokens();

-- A transaction makes revocation atomic with related authorization changes.
BEGIN;

SELECT revoke_jwt(
    '11111111-1111-1111-1111-111111111111'
);

COMMIT;

-- The same token is now denied even though its original cryptographic
-- signature could still be valid. Cryptographic validity and current
-- authorization state are separate concerns.
SELECT jwt_is_merge_authorized(
    '11111111-1111-1111-1111-111111111111',
    'repository:write'
) AS can_write_after_revocation;

-- Required claims can be audited with conditional aggregation.
SELECT
    t.token_id,
    COUNT(*) FILTER (WHERE c.claim_name = 'iss') AS issuer_claims,
    COUNT(*) FILTER (WHERE c.claim_name = 'sub') AS subject_claims,
    COUNT(*) FILTER (WHERE c.claim_name = 'aud') AS audience_claims,
    COUNT(*) FILTER (WHERE c.claim_name = 'iat') AS issued_at_claims,
    COUNT(*) FILTER (WHERE c.claim_name = 'exp') AS expiration_claims,
    COUNT(*) FILTER (WHERE c.claim_name = 'jti') AS token_id_claims
FROM jwt_tokens t
LEFT JOIN jwt_claims c
  ON c.token_id = t.token_id
GROUP BY t.token_id
ORDER BY t.token_id;

-- CTE-based security report showing each user's active and revoked tokens.
WITH token_summary AS (
    SELECT
        u.username,
        t.status,
        COUNT(*) AS token_count,
        MIN(t.issued_at) AS earliest_issue,
        MAX(t.expires_at) AS latest_expiration
    FROM users u
    JOIN jwt_tokens t
      ON t.user_id = u.user_id
    GROUP BY u.username, t.status
)
SELECT
    username,
    status,
    token_count,
    earliest_issue,
    latest_expiration
FROM token_summary
ORDER BY username, status;

-- Failure case: the database rejects inconsistent revoked state.
-- Uncommenting the following statement should raise an integrity error.
--
-- INSERT INTO jwt_tokens (
--     token_id,
--     application_id,
--     user_id,
--     status,
--     issued_at,
--     expires_at,
--     token_hash
-- )
-- SELECT
--     '44444444-4444-4444-4444-444444444444',
--     application_id,
--     (SELECT user_id FROM users WHERE username = 'atul'),
--     'revoked',
--     CURRENT_TIMESTAMP,
--     CURRENT_TIMESTAMP + INTERVAL '1 hour',
--     decode(md5('invalid'), 'hex')
-- FROM applications
-- LIMIT 1;

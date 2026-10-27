DROP SCHEMA IF EXISTS oidc_demo CASCADE;
CREATE SCHEMA oidc_demo;

SET search_path = oidc_demo, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE provider_status AS ENUM (
    'ACTIVE',
    'DISABLED'
);

CREATE TYPE client_type AS ENUM (
    'CONFIDENTIAL',
    'PUBLIC'
);

CREATE TYPE authorization_code_status AS ENUM (
    'ISSUED',
    'CONSUMED',
    'EXPIRED',
    'REVOKED'
);

CREATE TYPE authentication_event_status AS ENUM (
    'STARTED',
    'SUCCESS',
    'FAILED'
);

CREATE TYPE token_status AS ENUM (
    'ACTIVE',
    'REVOKED',
    'EXPIRED'
);

CREATE TABLE oidc_providers (
    provider_id BIGSERIAL PRIMARY KEY,
    issuer TEXT NOT NULL UNIQUE,
    authorization_endpoint TEXT NOT NULL,
    token_endpoint TEXT NOT NULL,
    userinfo_endpoint TEXT NOT NULL,
    jwks_uri TEXT NOT NULL,
    status provider_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT issuer_must_use_https
        CHECK (issuer LIKE 'https://%'),
    CONSTRAINT authorization_endpoint_https
        CHECK (authorization_endpoint LIKE 'https://%'),
    CONSTRAINT token_endpoint_https
        CHECK (token_endpoint LIKE 'https://%'),
    CONSTRAINT userinfo_endpoint_https
        CHECK (userinfo_endpoint LIKE 'https://%'),
    CONSTRAINT jwks_uri_https
        CHECK (jwks_uri LIKE 'https://%')
);

CREATE TABLE oidc_clients (
    client_id TEXT PRIMARY KEY,
    provider_id BIGINT NOT NULL
        REFERENCES oidc_providers(provider_id),
    client_type client_type NOT NULL,
    client_secret_hash TEXT,
    application_name TEXT NOT NULL,
    status provider_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT confidential_clients_need_secret
        CHECK (
            client_type = 'PUBLIC'
            OR client_secret_hash IS NOT NULL
        )
);

CREATE TABLE redirect_uris (
    redirect_uri_id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id)
        ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    UNIQUE (client_id, redirect_uri),
    CONSTRAINT redirect_uri_must_use_https
        CHECK (redirect_uri LIKE 'https://%')
);

CREATE TABLE oidc_users (
    user_id BIGSERIAL PRIMARY KEY,
    provider_id BIGINT NOT NULL
        REFERENCES oidc_providers(provider_id),
    subject TEXT NOT NULL,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, subject),
    UNIQUE (provider_id, email)
);

CREATE TABLE oidc_scopes (
    scope_name TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE client_scopes (
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id)
        ON DELETE CASCADE,
    scope_name TEXT NOT NULL
        REFERENCES oidc_scopes(scope_name),
    PRIMARY KEY (client_id, scope_name)
);

CREATE TABLE authentication_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id),
    user_id BIGINT
        REFERENCES oidc_users(user_id),
    state_value TEXT NOT NULL UNIQUE,
    nonce_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status authentication_event_status NOT NULL DEFAULT 'STARTED',
    CONSTRAINT session_expiry_after_creation
        CHECK (expires_at > created_at)
);

CREATE TABLE authorization_codes (
    authorization_code_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash TEXT NOT NULL UNIQUE,
    session_id UUID NOT NULL
        REFERENCES authentication_sessions(session_id)
        ON DELETE CASCADE,
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id),
    user_id BIGINT NOT NULL
        REFERENCES oidc_users(user_id),
    redirect_uri_id BIGINT NOT NULL
        REFERENCES redirect_uris(redirect_uri_id),
    nonce_value TEXT NOT NULL,
    code_challenge TEXT,
    code_challenge_method TEXT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    status authorization_code_status NOT NULL DEFAULT 'ISSUED',
    CONSTRAINT code_expiry_after_issue
        CHECK (expires_at > issued_at),
    CONSTRAINT pkce_method_requires_challenge
        CHECK (
            code_challenge_method IS NULL
            OR (
                code_challenge IS NOT NULL
                AND code_challenge_method = 'S256'
            )
        )
);

CREATE TABLE access_tokens (
    access_token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id),
    user_id BIGINT NOT NULL
        REFERENCES oidc_users(user_id),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    status token_status NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT access_token_expiry
        CHECK (expires_at > issued_at)
);

CREATE TABLE id_token_events (
    id_token_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL
        REFERENCES oidc_clients(client_id),
    user_id BIGINT NOT NULL
        REFERENCES oidc_users(user_id),
    issuer TEXT NOT NULL,
    audience TEXT NOT NULL,
    subject TEXT NOT NULL,
    nonce_value TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    algorithm TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT id_token_expiry
        CHECK (expires_at > issued_at),
    CONSTRAINT supported_algorithm
        CHECK (algorithm IN ('RS256', 'ES256', 'HS256'))
);

CREATE TABLE userinfo_requests (
    userinfo_request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    access_token_id UUID NOT NULL
        REFERENCES access_tokens(access_token_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    successful BOOLEAN NOT NULL,
    failure_reason TEXT
);

CREATE INDEX idx_users_provider_email
    ON oidc_users(provider_id, email);

CREATE INDEX idx_auth_sessions_client_status
    ON authentication_sessions(client_id, status);

CREATE INDEX idx_codes_client_status_expiry
    ON authorization_codes(client_id, status, expires_at);

CREATE INDEX idx_access_tokens_user_status_expiry
    ON access_tokens(user_id, status, expires_at);

CREATE INDEX idx_id_token_events_subject
    ON id_token_events(subject);

INSERT INTO oidc_providers (
    issuer,
    authorization_endpoint,
    token_endpoint,
    userinfo_endpoint,
    jwks_uri
)
VALUES (
    'https://identity.example.com',
    'https://identity.example.com/authorize',
    'https://identity.example.com/token',
    'https://identity.example.com/userinfo',
    'https://identity.example.com/.well-known/jwks.json'
);

INSERT INTO oidc_clients (
    client_id,
    provider_id,
    client_type,
    client_secret_hash,
    application_name
)
SELECT
    'enterprise-portal',
    provider_id,
    'CONFIDENTIAL',
    encode(
        digest('client-secret', 'sha256'),
        'hex'
    ),
    'Enterprise Operations Portal'
FROM oidc_providers
WHERE issuer = 'https://identity.example.com';

INSERT INTO redirect_uris (
    client_id,
    redirect_uri
)
VALUES (
    'enterprise-portal',
    'https://portal.example.com/oidc/callback'
);

INSERT INTO oidc_scopes (
    scope_name,
    description
)
VALUES
    ('openid', 'Required OpenID Connect identity scope'),
    ('profile', 'Basic profile claims'),
    ('email', 'Email and email verification claims');

INSERT INTO client_scopes (
    client_id,
    scope_name
)
VALUES
    ('enterprise-portal', 'openid'),
    ('enterprise-portal', 'profile'),
    ('enterprise-portal', 'email');

INSERT INTO oidc_users (
    provider_id,
    subject,
    username,
    email,
    display_name,
    email_verified
)
SELECT
    provider_id,
    'user-100',
    'atul',
    'atul@example.com',
    'Atul Pandey',
    true
FROM oidc_providers
WHERE issuer = 'https://identity.example.com';

INSERT INTO oidc_users (
    provider_id,
    subject,
    username,
    email,
    display_name,
    email_verified
)
SELECT
    provider_id,
    'user-101',
    'unverified',
    'unverified@example.com',
    'Unverified User',
    false
FROM oidc_providers
WHERE issuer = 'https://identity.example.com';

CREATE OR REPLACE FUNCTION validate_authentication_session()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    matching_redirect BOOLEAN;
BEGIN
    IF NEW.expires_at <= NEW.created_at THEN
        RAISE EXCEPTION
            'OIDC session expiration must be after creation';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM oidc_clients c
        JOIN redirect_uris r
          ON r.client_id = c.client_id
        WHERE c.client_id = NEW.client_id
          AND c.status = 'ACTIVE'
    )
    INTO matching_redirect;

    IF NOT matching_redirect THEN
        RAISE EXCEPTION
            'OIDC client has no active redirect URI';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_authentication_session
BEFORE INSERT OR UPDATE
ON authentication_sessions
FOR EACH ROW
EXECUTE FUNCTION validate_authentication_session();

CREATE OR REPLACE FUNCTION consume_authorization_code(
    p_code_hash TEXT,
    p_client_id TEXT,
    p_redirect_uri TEXT
)
RETURNS TABLE (
    authorization_code_id UUID,
    user_id BIGINT,
    nonce_value TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    UPDATE authorization_codes ac
    SET
        status = 'CONSUMED',
        consumed_at = now()
    FROM redirect_uris ru
    WHERE ac.code_hash = p_code_hash
      AND ac.client_id = p_client_id
      AND ac.redirect_uri_id = ru.redirect_uri_id
      AND ru.redirect_uri = p_redirect_uri
      AND ac.status = 'ISSUED'
      AND ac.expires_at > now()
    RETURNING
        ac.authorization_code_id,
        ac.user_id,
        ac.nonce_value;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Authorization code invalid, expired, consumed, or redirect URI mismatched';
    END IF;
END;
$$;

CREATE OR REPLACE VIEW v_oidc_client_configuration AS
SELECT
    c.client_id,
    c.application_name,
    c.client_type,
    c.status,
    p.issuer,
    p.authorization_endpoint,
    p.token_endpoint,
    p.userinfo_endpoint,
    p.jwks_uri,
    array_agg(DISTINCT cs.scope_name ORDER BY cs.scope_name)
        AS allowed_scopes,
    array_agg(DISTINCT ru.redirect_uri ORDER BY ru.redirect_uri)
        AS redirect_uris
FROM oidc_clients c
JOIN oidc_providers p
  ON p.provider_id = c.provider_id
LEFT JOIN client_scopes cs
  ON cs.client_id = c.client_id
LEFT JOIN redirect_uris ru
  ON ru.client_id = c.client_id
GROUP BY
    c.client_id,
    c.application_name,
    c.client_type,
    c.status,
    p.issuer,
    p.authorization_endpoint,
    p.token_endpoint,
    p.userinfo_endpoint,
    p.jwks_uri;

CREATE OR REPLACE VIEW v_merge_style_authentication_report AS
SELECT
    c.client_id,
    c.application_name,
    s.status AS authentication_status,
    u.subject,
    u.email,
    u.email_verified,
    s.created_at,
    s.completed_at
FROM authentication_sessions s
JOIN oidc_clients c
  ON c.client_id = s.client_id
LEFT JOIN oidc_users u
  ON u.user_id = s.user_id;

CREATE OR REPLACE FUNCTION oidc_authentication_report()
RETURNS TABLE (
    client_id TEXT,
    total_sessions BIGINT,
    successful_sessions BIGINT,
    failed_sessions BIGINT,
    success_rate NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        c.client_id,
        COUNT(s.session_id),
        COUNT(*) FILTER (
            WHERE s.status = 'SUCCESS'
        ),
        COUNT(*) FILTER (
            WHERE s.status = 'FAILED'
        ),
        ROUND(
            100.0 *
            COUNT(*) FILTER (
                WHERE s.status = 'SUCCESS'
            )
            / NULLIF(COUNT(s.session_id), 0),
            2
        )
    FROM oidc_clients c
    LEFT JOIN authentication_sessions s
      ON s.client_id = c.client_id
    GROUP BY c.client_id
    ORDER BY c.client_id;
$$;

BEGIN;

INSERT INTO authentication_sessions (
    client_id,
    user_id,
    state_value,
    nonce_value,
    expires_at,
    status
)
SELECT
    'enterprise-portal',
    u.user_id,
    'state-success-001',
    'nonce-success-001',
    now() + interval '10 minutes',
    'SUCCESS'
FROM oidc_users u
JOIN oidc_providers p
  ON p.provider_id = u.provider_id
WHERE p.issuer = 'https://identity.example.com'
  AND u.subject = 'user-100';

UPDATE authentication_sessions
SET completed_at = now()
WHERE state_value = 'state-success-001';

COMMIT;

BEGIN;

INSERT INTO authentication_sessions (
    client_id,
    user_id,
    state_value,
    nonce_value,
    expires_at,
    status
)
SELECT
    'enterprise-portal',
    u.user_id,
    'state-failed-001',
    'nonce-failed-001',
    now() + interval '10 minutes',
    'FAILED'
FROM oidc_users u
WHERE u.subject = 'user-101';

COMMIT;

INSERT INTO id_token_events (
    client_id,
    user_id,
    issuer,
    audience,
    subject,
    nonce_value,
    issued_at,
    expires_at,
    algorithm
)
SELECT
    'enterprise-portal',
    user_id,
    'https://identity.example.com',
    'enterprise-portal',
    subject,
    'nonce-success-001',
    now() - interval '5 minutes',
    now() + interval '55 minutes',
    'RS256'
FROM oidc_users
WHERE subject = 'user-100';

INSERT INTO access_tokens (
    token_hash,
    client_id,
    user_id,
    expires_at
)
SELECT
    encode(
        digest('access-token-user-100', 'sha256'),
        'hex'
    ),
    'enterprise-portal',
    user_id,
    now() + interval '1 hour'
FROM oidc_users
WHERE subject = 'user-100';

INSERT INTO userinfo_requests (
    access_token_id,
    successful
)
SELECT
    access_token_id,
    true
FROM access_tokens
WHERE token_hash = encode(
    digest('access-token-user-100', 'sha256'),
    'hex'
);

-- Configuration retrieval.
SELECT *
FROM v_oidc_client_configuration;

-- Distinguish verified and unverified identities.
SELECT
    subject,
    username,
    email,
    email_verified
FROM oidc_users
ORDER BY subject;

-- Authentication workflow reporting.
SELECT *
FROM v_merge_style_authentication_report
ORDER BY created_at;

-- Aggregate authentication outcomes.
SELECT *
FROM oidc_authentication_report();

-- Validate that only registered redirect URIs exist.
SELECT
    c.client_id,
    r.redirect_uri
FROM oidc_clients c
JOIN redirect_uris r
  ON r.client_id = c.client_id
ORDER BY c.client_id, r.redirect_uri;

-- Check currently usable access tokens.
SELECT
    c.client_id,
    u.subject,
    t.issued_at,
    t.expires_at,
    t.status
FROM access_tokens t
JOIN oidc_clients c
  ON c.client_id = t.client_id
JOIN oidc_users u
  ON u.user_id = t.user_id
WHERE t.status = 'ACTIVE'
  AND t.expires_at > now();

-- Demonstrate transactional authorization-code consumption.
BEGIN;

INSERT INTO authentication_sessions (
    client_id,
    user_id,
    state_value,
    nonce_value,
    expires_at
)
SELECT
    'enterprise-portal',
    user_id,
    'state-code-demo',
    'nonce-code-demo',
    now() + interval '10 minutes'
FROM oidc_users
WHERE subject = 'user-100';

INSERT INTO authorization_codes (
    code_hash,
    session_id,
    client_id,
    user_id,
    redirect_uri_id,
    nonce_value,
    expires_at
)
SELECT
    encode(
        digest('temporary-code-value', 'sha256'),
        'hex'
    ),
    s.session_id,
    s.client_id,
    s.user_id,
    r.redirect_uri_id,
    s.nonce_value,
    now() + interval '2 minutes'
FROM authentication_sessions s
JOIN redirect_uris r
  ON r.client_id = s.client_id
WHERE s.state_value = 'state-code-demo'
  AND r.redirect_uri =
      'https://portal.example.com/oidc/callback';

SELECT *
FROM consume_authorization_code(
    encode(
        digest('temporary-code-value', 'sha256'),
        'hex'
    ),
    'enterprise-portal',
    'https://portal.example.com/oidc/callback'
);

COMMIT;

-- The following query is intentionally read-only and identifies
-- sessions whose user has not verified the email claim.
SELECT
    s.session_id,
    s.status,
    u.subject,
    u.email,
    u.email_verified
FROM authentication_sessions s
JOIN oidc_users u
  ON u.user_id = s.user_id
WHERE u.email_verified = false;

-- Provider metadata is part of discovery/configuration,
-- while ID-token validation remains a client-side security step.
SELECT
    issuer,
    authorization_endpoint,
    token_endpoint,
    userinfo_endpoint,
    jwks_uri
FROM oidc_providers
WHERE status = 'ACTIVE';

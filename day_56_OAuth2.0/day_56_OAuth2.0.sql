DROP SCHEMA IF EXISTS oauth_demo CASCADE;
CREATE SCHEMA oauth_demo;

SET search_path = oauth_demo, public;

-- OAuth roles are intentionally represented separately from repository,
-- application, and database identities.

CREATE TYPE client_type AS ENUM (
    'public',
    'confidential'
);

CREATE TYPE token_state AS ENUM (
    'active',
    'revoked'
);

CREATE TYPE review_state AS ENUM (
    'pending',
    'approved',
    'denied',
    'dismissed'
);

CREATE TABLE oauth_client (
    client_id            text PRIMARY KEY,
    client_name          text NOT NULL,
    client_type          client_type NOT NULL,
    client_secret_hash   text,
    active               boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT confidential_client_secret_ck
        CHECK (
            client_type = 'public'
            OR client_secret_hash IS NOT NULL
        )
);

CREATE TABLE redirect_uri (
    client_id       text NOT NULL REFERENCES oauth_client(client_id)
                    ON DELETE CASCADE,
    redirect_uri    text NOT NULL,
    PRIMARY KEY (client_id, redirect_uri)
);

CREATE TABLE resource_owner (
    owner_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       text NOT NULL UNIQUE,
    active         boolean NOT NULL DEFAULT true
);

CREATE TABLE oauth_scope (
    scope_name      text PRIMARY KEY,
    description     text NOT NULL,
    sensitive       boolean NOT NULL DEFAULT false
);

CREATE TABLE client_scope (
    client_id       text NOT NULL REFERENCES oauth_client(client_id)
                    ON DELETE CASCADE,
    scope_name      text NOT NULL REFERENCES oauth_scope(scope_name),
    PRIMARY KEY (client_id, scope_name)
);

CREATE TABLE authorization_code (
    code_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code_value          text NOT NULL UNIQUE,
    client_id           text NOT NULL REFERENCES oauth_client(client_id),
    owner_id            bigint NOT NULL REFERENCES resource_owner(owner_id),
    redirect_uri        text NOT NULL,
    pkce_challenge      text NOT NULL,
    expires_at          timestamptz NOT NULL,
    consumed_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT code_expiry_ck CHECK (expires_at > created_at)
);

CREATE TABLE authorization_code_scope (
    code_id         bigint NOT NULL REFERENCES authorization_code(code_id)
                    ON DELETE CASCADE,
    scope_name      text NOT NULL REFERENCES oauth_scope(scope_name),
    PRIMARY KEY (code_id, scope_name)
);

CREATE TABLE access_token (
    token_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash        text NOT NULL UNIQUE,
    client_id         text NOT NULL REFERENCES oauth_client(client_id),
    owner_id          bigint NOT NULL REFERENCES resource_owner(owner_id),
    state             token_state NOT NULL DEFAULT 'active',
    expires_at        timestamptz NOT NULL,
    issued_at         timestamptz NOT NULL DEFAULT now(),
    revoked_at        timestamptz
);

CREATE TABLE access_token_scope (
    token_id        bigint NOT NULL REFERENCES access_token(token_id)
                    ON DELETE CASCADE,
    scope_name      text NOT NULL REFERENCES oauth_scope(scope_name),
    PRIMARY KEY (token_id, scope_name)
);

CREATE TABLE refresh_token (
    refresh_token_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash        text NOT NULL UNIQUE,
    client_id         text NOT NULL REFERENCES oauth_client(client_id),
    owner_id          bigint NOT NULL REFERENCES resource_owner(owner_id),
    state             token_state NOT NULL DEFAULT 'active',
    expires_at        timestamptz NOT NULL,
    issued_at         timestamptz NOT NULL DEFAULT now(),
    revoked_at        timestamptz
);

CREATE TABLE refresh_token_scope (
    refresh_token_id bigint NOT NULL
        REFERENCES refresh_token(refresh_token_id)
        ON DELETE CASCADE,
    scope_name       text NOT NULL REFERENCES oauth_scope(scope_name),
    PRIMARY KEY (refresh_token_id, scope_name)
);

CREATE TABLE protected_resource (
    resource_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_name     text NOT NULL UNIQUE,
    owner_id          bigint NOT NULL REFERENCES resource_owner(owner_id),
    required_scope    text NOT NULL REFERENCES oauth_scope(scope_name),
    payload           jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE status_check (
    status_check_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id         text NOT NULL REFERENCES oauth_client(client_id),
    check_name        text NOT NULL,
    status            text NOT NULL,
    checked_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT status_check_state_ck
        CHECK (status IN ('success', 'failure', 'pending'))
);

CREATE TABLE oauth_audit_event (
    audit_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type        text NOT NULL,
    client_id         text REFERENCES oauth_client(client_id),
    owner_id          bigint REFERENCES resource_owner(owner_id),
    event_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX access_token_client_state_idx
    ON access_token (client_id, state);

CREATE INDEX refresh_token_client_state_idx
    ON refresh_token (client_id, state);

CREATE INDEX authorization_code_expiry_idx
    ON authorization_code (expires_at);

CREATE INDEX protected_resource_scope_idx
    ON protected_resource (required_scope);

CREATE INDEX audit_client_time_idx
    ON oauth_audit_event (client_id, occurred_at DESC);

INSERT INTO resource_owner (username)
VALUES
    ('alice'),
    ('bob'),
    ('carol');

INSERT INTO oauth_scope (scope_name, description, sensitive)
VALUES
    ('profile:read', 'Read basic profile information', false),
    ('orders:read', 'Read order information', false),
    ('account:read', 'Read financial account information', true),
    ('transaction:read', 'Read transaction information', true),
    ('admin:write', 'Administrative write access', true);

INSERT INTO oauth_client (
    client_id,
    client_name,
    client_type,
    client_secret_hash
)
VALUES
    (
        'web-portal',
        'Enterprise Web Portal',
        'confidential',
        'hash-of-managed-server-secret'
    ),
    (
        'mobile-app',
        'Enterprise Mobile Application',
        'public',
        NULL
    );

INSERT INTO redirect_uri (client_id, redirect_uri)
VALUES
    (
        'web-portal',
        'https://portal.example.test/oauth/callback'
    ),
    (
        'mobile-app',
        'https://mobile.example.test/oauth/callback'
    );

INSERT INTO client_scope (client_id, scope_name)
VALUES
    ('web-portal', 'profile:read'),
    ('web-portal', 'orders:read'),
    ('web-portal', 'account:read'),
    ('mobile-app', 'profile:read'),
    ('mobile-app', 'orders:read');

INSERT INTO protected_resource (
    resource_name,
    owner_id,
    required_scope,
    payload
)
SELECT
    'alice-profile',
    owner_id,
    'profile:read',
    '{"name":"Alice","department":"Engineering"}'::jsonb
FROM resource_owner
WHERE username = 'alice';

INSERT INTO protected_resource (
    resource_name,
    owner_id,
    required_scope,
    payload
)
SELECT
    'alice-account',
    owner_id,
    'account:read',
    '{"currency":"INR","status":"ACTIVE","account_suffix":"4821"}'::jsonb
FROM resource_owner
WHERE username = 'alice';

INSERT INTO protected_resource (
    resource_name,
    owner_id,
    required_scope,
    payload
)
SELECT
    'bob-orders',
    owner_id,
    'orders:read',
    '{"orders":3,"latest":"ORD-2003"}'::jsonb
FROM resource_owner
WHERE username = 'bob';

-- Authorization code created for a valid PKCE request.
INSERT INTO authorization_code (
    code_value,
    client_id,
    owner_id,
    redirect_uri,
    pkce_challenge,
    expires_at
)
SELECT
    'AUTH-CODE-ALICE-001',
    'web-portal',
    owner_id,
    'https://portal.example.test/oauth/callback',
    'S256-example-code-challenge',
    now() + interval '2 minutes'
FROM resource_owner
WHERE username = 'alice';

INSERT INTO authorization_code_scope (code_id, scope_name)
SELECT
    ac.code_id,
    'profile:read'
FROM authorization_code ac
WHERE ac.code_value = 'AUTH-CODE-ALICE-001';

-- A deliberately consumed code models a replay/failure condition.
INSERT INTO authorization_code (
    code_value,
    client_id,
    owner_id,
    redirect_uri,
    pkce_challenge,
    expires_at,
    consumed_at
)
SELECT
    'AUTH-CODE-CONSUMED',
    'web-portal',
    owner_id,
    'https://portal.example.test/oauth/callback',
    'S256-example-code-challenge',
    now() + interval '2 minutes',
    now()
FROM resource_owner
WHERE username = 'alice';

INSERT INTO access_token (
    token_hash,
    client_id,
    owner_id,
    state,
    expires_at
)
SELECT
    'sha256-access-token-alice-001',
    'web-portal',
    owner_id,
    'active',
    now() + interval '15 minutes'
FROM resource_owner
WHERE username = 'alice';

INSERT INTO access_token_scope (token_id, scope_name)
SELECT
    at.token_id,
    'profile:read'
FROM access_token at
WHERE at.token_hash = 'sha256-access-token-alice-001';

INSERT INTO access_token (
    token_hash,
    client_id,
    owner_id,
    state,
    expires_at,
    revoked_at
)
SELECT
    'sha256-access-token-revoked',
    'web-portal',
    owner_id,
    'revoked',
    now() + interval '15 minutes',
    now()
FROM resource_owner
WHERE username = 'alice';

INSERT INTO access_token_scope (token_id, scope_name)
SELECT
    at.token_id,
    'profile:read'
FROM access_token at
WHERE at.token_hash = 'sha256-access-token-revoked';

INSERT INTO refresh_token (
    token_hash,
    client_id,
    owner_id,
    state,
    expires_at
)
SELECT
    'sha256-refresh-token-alice-001',
    'web-portal',
    owner_id,
    'active',
    now() + interval '1 day'
FROM resource_owner
WHERE username = 'alice';

INSERT INTO refresh_token_scope (refresh_token_id, scope_name)
SELECT
    rt.refresh_token_id,
    'profile:read'
FROM refresh_token rt
WHERE rt.token_hash = 'sha256-refresh-token-alice-001';

INSERT INTO status_check (client_id, check_name, status)
VALUES
    ('web-portal', 'authorization-policy-check', 'success'),
    ('web-portal', 'redirect-uri-validation', 'success'),
    ('mobile-app', 'scope-policy-check', 'success');

CREATE OR REPLACE FUNCTION validate_authorization_code_redirect_uri()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM redirect_uri ru
        WHERE ru.client_id = NEW.client_id
          AND ru.redirect_uri = NEW.redirect_uri
    ) THEN
        RAISE EXCEPTION
            'redirect URI is not registered for client %',
            NEW.client_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM oauth_client c
        WHERE c.client_id = NEW.client_id
          AND c.active
    ) THEN
        RAISE EXCEPTION
            'client % is not active',
            NEW.client_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER authorization_code_redirect_validation
BEFORE INSERT OR UPDATE ON authorization_code
FOR EACH ROW
EXECUTE FUNCTION validate_authorization_code_redirect_uri();

CREATE OR REPLACE FUNCTION validate_code_scopes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM authorization_code ac
        JOIN client_scope cs
          ON cs.client_id = ac.client_id
         AND cs.scope_name = NEW.scope_name
        WHERE ac.code_id = NEW.code_id
    ) THEN
        RAISE EXCEPTION
            'scope % is not permitted for authorization code client',
            NEW.scope_name;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER authorization_code_scope_validation
BEFORE INSERT OR UPDATE ON authorization_code_scope
FOR EACH ROW
EXECUTE FUNCTION validate_code_scopes();

CREATE OR REPLACE FUNCTION prevent_revoked_token_reactivation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'revoked'
       AND NEW.state = 'active' THEN
        RAISE EXCEPTION
            'revoked token cannot be reactivated';
    END IF;

    IF NEW.state = 'revoked'
       AND NEW.revoked_at IS NULL THEN
        NEW.revoked_at := now();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER access_token_state_guard
BEFORE UPDATE ON access_token
FOR EACH ROW
EXECUTE FUNCTION prevent_revoked_token_reactivation();

CREATE TRIGGER refresh_token_state_guard
BEFORE UPDATE ON refresh_token
FOR EACH ROW
EXECUTE FUNCTION prevent_revoked_token_reactivation();

CREATE OR REPLACE FUNCTION consume_authorization_code(
    p_code_value text,
    p_client_id text,
    p_redirect_uri text
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    v_code_id bigint;
BEGIN
    /*
     * FOR UPDATE makes code consumption atomic for concurrent token
     * requests. Only one transaction can consume the same authorization
     * code successfully.
     */
    SELECT ac.code_id
    INTO v_code_id
    FROM authorization_code ac
    WHERE ac.code_value = p_code_value
      AND ac.client_id = p_client_id
      AND ac.redirect_uri = p_redirect_uri
      AND ac.consumed_at IS NULL
      AND ac.expires_at > now()
    FOR UPDATE;

    IF v_code_id IS NULL THEN
        RAISE EXCEPTION
            'authorization code is invalid, expired, or already consumed';
    END IF;

    UPDATE authorization_code
    SET consumed_at = now()
    WHERE code_id = v_code_id;

    INSERT INTO oauth_audit_event (
        event_type,
        client_id,
        event_data
    )
    VALUES (
        'authorization_code_consumed',
        p_client_id,
        jsonb_build_object(
            'code_id',
            v_code_id
        )
    );

    RETURN v_code_id;
END;
$$;

CREATE OR REPLACE FUNCTION evaluate_access_token(
    p_token_hash text,
    p_required_scope text,
    p_owner_id bigint
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_valid boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM access_token at
        JOIN access_token_scope ats
          ON ats.token_id = at.token_id
        WHERE at.token_hash = p_token_hash
          AND at.state = 'active'
          AND at.expires_at > now()
          AND at.owner_id = p_owner_id
          AND ats.scope_name = p_required_scope
    )
    INTO v_valid;

    RETURN v_valid;
END;
$$;

CREATE OR REPLACE VIEW active_token_inventory AS
SELECT
    at.token_id,
    at.client_id,
    ro.username AS resource_owner,
    at.expires_at,
    array_agg(ats.scope_name ORDER BY ats.scope_name) AS scopes
FROM access_token at
JOIN resource_owner ro
  ON ro.owner_id = at.owner_id
JOIN access_token_scope ats
  ON ats.token_id = at.token_id
WHERE at.state = 'active'
  AND at.expires_at > now()
GROUP BY
    at.token_id,
    at.client_id,
    ro.username,
    at.expires_at;

CREATE OR REPLACE VIEW client_authorization_summary AS
SELECT
    c.client_id,
    c.client_name,
    c.client_type,
    count(DISTINCT ac.code_id) AS authorization_codes,
    count(DISTINCT at.token_id) FILTER (
        WHERE at.state = 'active'
          AND at.expires_at > now()
    ) AS active_access_tokens,
    count(DISTINCT rt.refresh_token_id) FILTER (
        WHERE rt.state = 'active'
          AND rt.expires_at > now()
    ) AS active_refresh_tokens
FROM oauth_client c
LEFT JOIN authorization_code ac
    ON ac.client_id = c.client_id
LEFT JOIN access_token at
    ON at.client_id = c.client_id
LEFT JOIN refresh_token rt
    ON rt.client_id = c.client_id
GROUP BY
    c.client_id,
    c.client_name,
    c.client_type;

-- Query 1: clients and permitted scopes.
SELECT
    c.client_id,
    c.client_name,
    c.client_type,
    array_agg(cs.scope_name ORDER BY cs.scope_name) AS permitted_scopes
FROM oauth_client c
LEFT JOIN client_scope cs
    ON cs.client_id = c.client_id
GROUP BY
    c.client_id,
    c.client_name,
    c.client_type
ORDER BY c.client_id;

-- Query 2: verify that an active token has a specific scope.
SELECT evaluate_access_token(
    'sha256-access-token-alice-001',
    'profile:read',
    (
        SELECT owner_id
        FROM resource_owner
        WHERE username = 'alice'
    )
) AS token_can_read_profile;

-- Query 3: intentionally insufficient-scope evaluation.
SELECT evaluate_access_token(
    'sha256-access-token-alice-001',
    'account:read',
    (
        SELECT owner_id
        FROM resource_owner
        WHERE username = 'alice'
    )
) AS token_can_read_account;

-- Query 4: active token inventory.
SELECT *
FROM active_token_inventory
ORDER BY client_id, token_id;

-- Query 5: authorization and token lifecycle reporting.
SELECT *
FROM client_authorization_summary
ORDER BY client_id;

-- Query 6: resource-server decision.
SELECT
    pr.resource_name,
    ro.username AS owner,
    pr.required_scope,
    evaluate_access_token(
        'sha256-access-token-alice-001',
        pr.required_scope,
        pr.owner_id
    ) AS merge_like_authorization_decision
FROM protected_resource pr
JOIN resource_owner ro
  ON ro.owner_id = pr.owner_id
ORDER BY pr.resource_name;

-- Query 7: status and policy health.
SELECT
    client_id,
    count(*) AS checks,
    count(*) FILTER (WHERE status = 'success') AS successful_checks,
    count(*) FILTER (WHERE status = 'failure') AS failed_checks,
    count(*) FILTER (WHERE status = 'pending') AS pending_checks
FROM status_check
GROUP BY client_id
ORDER BY client_id;

-- Transactional authorization-code consumption.
BEGIN;

SELECT consume_authorization_code(
    'AUTH-CODE-ALICE-001',
    'web-portal',
    'https://portal.example.test/oauth/callback'
);

COMMIT;

-- The same code now fails because consumption is persistent and atomic.
DO $$
BEGIN
    BEGIN
        PERFORM consume_authorization_code(
            'AUTH-CODE-ALICE-001',
            'web-portal',
            'https://portal.example.test/oauth/callback'
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected replay rejection: %',
                SQLERRM;
    END;
END;
$$;

-- Invalid redirect URI demonstrates the trigger-level policy.
DO $$
BEGIN
    BEGIN
        INSERT INTO authorization_code (
            code_value,
            client_id,
            owner_id,
            redirect_uri,
            pkce_challenge,
            expires_at
        )
        SELECT
            'AUTH-CODE-EVIL',
            'web-portal',
            owner_id,
            'https://evil.example.test/callback',
            'S256-invalid',
            now() + interval '2 minutes'
        FROM resource_owner
        WHERE username = 'alice';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected redirect URI rejection: %',
                SQLERRM;
    END;
END;
$$;

-- Expired-token reporting is kept separate from active-token reporting.
SELECT
    client_id,
    count(*) AS expired_tokens
FROM access_token
WHERE expires_at <= now()
GROUP BY client_id
ORDER BY client_id;

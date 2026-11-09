SECURE API PROJECT
PostgreSQL 15+

Authentication, authorization, role management, token lifecycle,
resource ownership, API security policies, rate limiting, audit logging,
and access eligibility.

Execution:
Run the complete script using a PostgreSQL database account authorized
to create schemas, functions, triggers, and extensions used below.

The script is designed for repeatable execution.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS secure_api;

SET search_path TO secure_api, public;

-- =============================================================================
-- 1. DOMAIN TYPES
-- =============================================================================

DO $$
BEGIN
    CREATE TYPE account_status AS ENUM (
        'ACTIVE',
        'SUSPENDED',
        'DISABLED'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE token_status AS ENUM (
        'ACTIVE',
        'REVOKED',
        'EXPIRED'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE security_decision AS ENUM (
        'ALLOW',
        'DENY'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE audit_severity AS ENUM (
        'INFO',
        'WARNING',
        'CRITICAL'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- 2. USERS
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    username VARCHAR(64) NOT NULL UNIQUE,

    email VARCHAR(254) NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    password_salt TEXT NOT NULL,

    account_status account_status NOT NULL DEFAULT 'ACTIVE',

    failed_login_attempts INTEGER NOT NULL DEFAULT 0,

    locked_until TIMESTAMPTZ,

    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT username_format CHECK (
        username ~ '^[A-Za-z0-9_-]{3,64}$'
    ),

    CONSTRAINT email_format CHECK (
        email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
    ),

    CONSTRAINT password_hash_nonempty CHECK (
        LENGTH(password_hash) >= 32
    ),

    CONSTRAINT salt_nonempty CHECK (
        LENGTH(password_salt) >= 16
    ),

    CONSTRAINT failed_attempts_nonnegative CHECK (
        failed_login_attempts >= 0
    )
);

-- =============================================================================
-- 3. ROLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS roles (
    role_id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    role_name VARCHAR(32) NOT NULL UNIQUE,

    description TEXT NOT NULL,

    CONSTRAINT role_name_format CHECK (
        role_name ~ '^[a-z_]{2,32}$'
    )
);

-- =============================================================================
-- 4. PERMISSIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS permissions (
    permission_id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    permission_code VARCHAR(64) NOT NULL UNIQUE,

    description TEXT NOT NULL,

    CONSTRAINT permission_code_format CHECK (
        permission_code ~ '^[a-z_]+:[a-z_]+$'
    )
);

-- =============================================================================
-- 5. ROLE-PERMISSION RELATIONSHIP
-- =============================================================================

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id SMALLINT NOT NULL REFERENCES roles(role_id)
        ON DELETE CASCADE,

    permission_id SMALLINT NOT NULL REFERENCES permissions(permission_id)
        ON DELETE CASCADE,

    PRIMARY KEY (role_id, permission_id)
);

-- =============================================================================
-- 6. USER-ROLE RELATIONSHIP
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL REFERENCES users(user_id)
        ON DELETE CASCADE,

    role_id SMALLINT NOT NULL REFERENCES roles(role_id)
        ON DELETE RESTRICT,

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    assigned_by UUID REFERENCES users(user_id)
        ON DELETE SET NULL,

    PRIMARY KEY (user_id, role_id)
);

-- =============================================================================
-- 7. ACCESS TOKENS
-- =============================================================================

CREATE TABLE IF NOT EXISTS access_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id)
        ON DELETE CASCADE,

    token_hash TEXT NOT NULL UNIQUE,

    token_status token_status NOT NULL DEFAULT 'ACTIVE',

    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ,

    client_identifier VARCHAR(128),

    CONSTRAINT valid_token_lifetime CHECK (
        expires_at > issued_at
        AND expires_at <= issued_at + INTERVAL '24 hours'
    ),

    CONSTRAINT revocation_consistency CHECK (
        (token_status = 'REVOKED' AND revoked_at IS NOT NULL)
        OR
        (token_status <> 'REVOKED' AND revoked_at IS NULL)
    )
);

-- =============================================================================
-- 8. API RESOURCES
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_resources (
    resource_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    owner_id UUID NOT NULL REFERENCES users(user_id)
        ON DELETE RESTRICT,

    resource_name VARCHAR(128) NOT NULL,

    resource_type VARCHAR(64) NOT NULL,

    content JSONB NOT NULL DEFAULT '{}'::JSONB,

    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT resource_name_nonempty CHECK (
        LENGTH(TRIM(resource_name)) > 0
    ),

    CONSTRAINT resource_content_object CHECK (
        JSONB_TYPEOF(content) = 'object'
    )
);

-- =============================================================================
-- 9. API ENDPOINTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_endpoints (
    endpoint_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    http_method VARCHAR(10) NOT NULL,

    route_pattern VARCHAR(255) NOT NULL,

    required_permission_id SMALLINT
        REFERENCES permissions(permission_id)
        ON DELETE RESTRICT,

    authentication_required BOOLEAN NOT NULL DEFAULT TRUE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    description TEXT NOT NULL,

    UNIQUE (http_method, route_pattern),

    CONSTRAINT valid_http_method CHECK (
        http_method IN (
            'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'
        )
    )
);

-- =============================================================================
-- 10. RATE LIMIT POLICIES
-- =============================================================================

CREATE TABLE IF NOT EXISTS rate_limit_policies (
    policy_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(100) NOT NULL UNIQUE,

    maximum_requests INTEGER NOT NULL,

    window_seconds INTEGER NOT NULL,

    applies_to VARCHAR(32) NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT positive_rate_limit CHECK (
        maximum_requests > 0
        AND window_seconds > 0
    ),

    CONSTRAINT valid_rate_scope CHECK (
        applies_to IN ('IP', 'USER', 'API_KEY', 'ENDPOINT')
    )
);

-- =============================================================================
-- 11. RATE LIMIT COUNTERS
-- =============================================================================

CREATE TABLE IF NOT EXISTS rate_limit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_id INTEGER NOT NULL
        REFERENCES rate_limit_policies(policy_id)
        ON DELETE CASCADE,

    subject_identifier VARCHAR(128) NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    request_allowed BOOLEAN NOT NULL,

    endpoint VARCHAR(255)
);

-- =============================================================================
-- 12. SECURITY AUDIT LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS security_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id UUID REFERENCES users(user_id)
        ON DELETE SET NULL,

    event_type VARCHAR(64) NOT NULL,

    resource_identifier VARCHAR(255),

    decision security_decision NOT NULL,

    severity audit_severity NOT NULL DEFAULT 'INFO',

    source_ip INET,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT audit_details_object CHECK (
        JSONB_TYPEOF(details) = 'object'
    )
);

-- =============================================================================
-- 13. INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_users_status
    ON users(account_status);

CREATE INDEX IF NOT EXISTS idx_user_roles_user
    ON user_roles(user_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_role
    ON user_roles(role_id);

CREATE INDEX IF NOT EXISTS idx_role_permissions_permission
    ON role_permissions(permission_id);

CREATE INDEX IF NOT EXISTS idx_active_tokens_user
    ON access_tokens(user_id, expires_at)
    WHERE token_status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_resources_owner
    ON api_resources(owner_id);

CREATE INDEX IF NOT EXISTS idx_resources_type
    ON api_resources(resource_type);

CREATE INDEX IF NOT EXISTS idx_audit_user_time
    ON security_audit(user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_decision_time
    ON security_audit(decision, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_rate_subject_time
    ON rate_limit_events(policy_id, subject_identifier, occurred_at DESC);

-- =============================================================================
-- 14. UPDATED_AT TRIGGER
-- =============================================================================

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trg_resources_updated_at ON api_resources;

CREATE TRIGGER trg_resources_updated_at
BEFORE UPDATE ON api_resources
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- 15. TOKEN REVOCATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION revoke_access_token(
    p_token_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    affected INTEGER;
BEGIN
    UPDATE access_tokens
    SET
        token_status = 'REVOKED',
        revoked_at = NOW()
    WHERE token_id = p_token_id
      AND token_status = 'ACTIVE';

    GET DIAGNOSTICS affected = ROW_COUNT;

    RETURN affected = 1;
END;
$$;

-- =============================================================================
-- 16. TOKEN VALIDATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_access_token(
    p_token_hash TEXT
)
RETURNS TABLE (
    authenticated_user_id UUID,
    authentication_valid BOOLEAN,
    failure_reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.user_id,

        (
            t.token_status = 'ACTIVE'
            AND t.expires_at > NOW()
            AND u.account_status = 'ACTIVE'
            AND (
                u.locked_until IS NULL
                OR u.locked_until <= NOW()
            )
        ),

        CASE
            WHEN u.user_id IS NULL
                THEN 'USER_NOT_FOUND'

            WHEN u.account_status <> 'ACTIVE'
                THEN 'ACCOUNT_INACTIVE'

            WHEN u.locked_until > NOW()
                THEN 'ACCOUNT_LOCKED'

            WHEN t.token_status = 'REVOKED'
                THEN 'TOKEN_REVOKED'

            WHEN t.expires_at <= NOW()
                THEN 'TOKEN_EXPIRED'

            ELSE 'VALID'
        END

    FROM access_tokens t
    JOIN users u ON u.user_id = t.user_id
    WHERE t.token_hash = p_token_hash;
END;
$$;

-- =============================================================================
-- 17. AUTHORIZATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION has_permission(
    p_user_id UUID,
    p_permission_code VARCHAR(64)
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY INVOKER
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM users u
        JOIN user_roles ur
            ON ur.user_id = u.user_id
        JOIN role_permissions rp
            ON rp.role_id = ur.role_id
        JOIN permissions p
            ON p.permission_id = rp.permission_id
        WHERE u.user_id = p_user_id
          AND u.account_status = 'ACTIVE'
          AND (
              u.locked_until IS NULL
              OR u.locked_until <= NOW()
          )
          AND p.permission_code = p_permission_code
    );
$$;

-- =============================================================================
-- 18. RESOURCE OWNERSHIP FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION can_access_resource(
    p_user_id UUID,
    p_resource_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM api_resources r
        JOIN users u ON u.user_id = p_user_id
        WHERE r.resource_id = p_resource_id
          AND u.account_status = 'ACTIVE'
          AND (
              r.owner_id = p_user_id
              OR has_permission(p_user_id, 'system:manage')
          )
    );
$$;

-- =============================================================================
-- 19. ENDPOINT ELIGIBILITY FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION evaluate_endpoint_access(
    p_user_id UUID,
    p_method VARCHAR(10),
    p_route VARCHAR(255)
)
RETURNS TABLE (
    eligible BOOLEAN,
    explanation TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    required_permission VARCHAR(64);
    authentication_required BOOLEAN;
    endpoint_enabled BOOLEAN;
BEGIN
    SELECT
        p.permission_code,
        e.authentication_required,
        e.enabled

    INTO
        required_permission,
        authentication_required,
        endpoint_enabled

    FROM api_endpoints e
    LEFT JOIN permissions p
        ON p.permission_id = e.required_permission_id

    WHERE e.http_method = p_method
      AND e.route_pattern = p_route;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'ENDPOINT_NOT_FOUND';
        RETURN;
    END IF;

    IF NOT endpoint_enabled THEN
        RETURN QUERY SELECT FALSE, 'ENDPOINT_DISABLED';
        RETURN;
    END IF;

    IF NOT authentication_required THEN
        RETURN QUERY SELECT TRUE, 'PUBLIC_ENDPOINT';
        RETURN;
    END IF;

    IF p_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'AUTHENTICATION_REQUIRED';
        RETURN;
    END IF;

    IF required_permission IS NULL THEN
        RETURN QUERY SELECT TRUE, 'AUTHENTICATED_ACCESS';
        RETURN;
    END IF;

    IF has_permission(p_user_id, required_permission) THEN
        RETURN QUERY SELECT TRUE, 'PERMISSION_GRANTED';
    ELSE
        RETURN QUERY SELECT FALSE, 'PERMISSION_DENIED';
    END IF;
END;
$$;

-- =============================================================================
-- 20. RATE LIMIT EVALUATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION check_rate_limit(
    p_policy_id INTEGER,
    p_subject VARCHAR(128)
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    request_limit INTEGER;
    duration_seconds INTEGER;
    current_count INTEGER;
    allowed BOOLEAN;
BEGIN
    SELECT
        maximum_requests,
        window_seconds

    INTO
        request_limit,
        duration_seconds

    FROM rate_limit_policies
    WHERE policy_id = p_policy_id
      AND enabled = TRUE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Serialize requests for the same subject and policy.
    PERFORM pg_advisory_xact_lock(
        hashtext(p_subject),
        p_policy_id
    );

    SELECT COUNT(*)::INTEGER
    INTO current_count

    FROM rate_limit_events
    WHERE policy_id = p_policy_id
      AND subject_identifier = p_subject
      AND occurred_at >=
          NOW() - make_interval(secs => duration_seconds)
      AND request_allowed = TRUE;

    allowed := current_count < request_limit;

    INSERT INTO rate_limit_events (
        policy_id,
        subject_identifier,
        request_allowed
    )
    VALUES (
        p_policy_id,
        p_subject,
        allowed
    );

    RETURN allowed;
END;
$$;

-- =============================================================================
-- 21. SECURITY AUDIT INSERT FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION write_security_audit(
    p_user_id UUID,
    p_event_type VARCHAR(64),
    p_resource VARCHAR(255),
    p_decision security_decision,
    p_severity audit_severity,
    p_details JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    generated_id BIGINT;
BEGIN
    INSERT INTO security_audit (
        user_id,
        event_type,
        resource_identifier,
        decision,
        severity,
        details
    )
    VALUES (
        p_user_id,
        p_event_type,
        p_resource,
        p_decision,
        p_severity,
        COALESCE(p_details, '{}'::JSONB)
    )
    RETURNING audit_id INTO generated_id;

    RETURN generated_id;
END;
$$;

-- =============================================================================
-- 22. ADMINISTRATIVE PROCEDURE
-- =============================================================================

CREATE OR REPLACE PROCEDURE deactivate_user(
    p_user_id UUID,
    p_actor_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT has_permission(p_actor_id, 'system:manage') THEN
        RAISE EXCEPTION 'Administrative permission required.'
            USING ERRCODE = '42501';
    END IF;

    IF p_actor_id = p_user_id THEN
        RAISE EXCEPTION 'Self-deactivation is not permitted.'
            USING ERRCODE = '42501';
    END IF;

    UPDATE users
    SET account_status = 'DISABLED'
    WHERE user_id = p_user_id
      AND account_status <> 'DISABLED';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User not found or already disabled.';
    END IF;

    UPDATE access_tokens
    SET
        token_status = 'REVOKED',
        revoked_at = NOW()
    WHERE user_id = p_user_id
      AND token_status = 'ACTIVE';

    PERFORM write_security_audit(
        p_actor_id,
        'USER_DEACTIVATION',
        p_user_id::TEXT,
        'ALLOW',
        'WARNING',
        jsonb_build_object(
            'target_user', p_user_id,
            'operation', 'DEACTIVATE'
        )
    );
END;
$$;

-- =============================================================================
-- 23. AUDIT VIEW
-- =============================================================================

CREATE OR REPLACE VIEW security_audit_report AS
SELECT
    a.audit_id,
    u.username,
    a.event_type,
    a.resource_identifier,
    a.decision,
    a.severity,
    a.source_ip,
    a.details,
    a.occurred_at

FROM security_audit a
LEFT JOIN users u
    ON u.user_id = a.user_id;

-- =============================================================================
-- 24. USER PERMISSION VIEW
-- =============================================================================

CREATE OR REPLACE VIEW user_permission_report AS
SELECT DISTINCT
    u.user_id,
    u.username,
    u.account_status,
    r.role_name,
    p.permission_code,
    p.description AS permission_description

FROM users u

JOIN user_roles ur
    ON ur.user_id = u.user_id

JOIN roles r
    ON r.role_id = ur.role_id

JOIN role_permissions rp
    ON rp.role_id = r.role_id

JOIN permissions p
    ON p.permission_id = rp.permission_id;

-- =============================================================================
-- 25. SEED ROLES
-- =============================================================================

INSERT INTO roles (
    role_name,
    description
)
VALUES
    ('admin', 'Full administrative access'),
    ('editor', 'Limited modification privileges'),
    ('viewer', 'Read-only access')

ON CONFLICT (role_name) DO NOTHING;

-- =============================================================================
-- 26. SEED PERMISSIONS
-- =============================================================================

INSERT INTO permissions (
    permission_code,
    description
)
VALUES
    ('users:read', 'Read user records'),
    ('users:create', 'Create user records'),
    ('users:update', 'Update user records'),
    ('users:delete', 'Delete user records'),
    ('reports:read', 'Read analytical reports'),
    ('system:manage', 'Manage administrative resources')

ON CONFLICT (permission_code) DO NOTHING;

-- =============================================================================
-- 27. ROLE PERMISSION MAPPING
-- =============================================================================

INSERT INTO role_permissions (
    role_id,
    permission_id
)
SELECT
    r.role_id,
    p.permission_id

FROM roles r

CROSS JOIN permissions p

WHERE
    (
        r.role_name = 'admin'
    )
    OR
    (
        r.role_name = 'editor'
        AND p.permission_code IN (
            'users:read',
            'users:update',
            'reports:read'
        )
    )
    OR
    (
        r.role_name = 'viewer'
        AND p.permission_code IN (
            'users:read',
            'reports:read'
        )
    )

ON CONFLICT DO NOTHING;

-- =============================================================================
-- 28. ENDPOINT REGISTRATION
-- =============================================================================

INSERT INTO api_endpoints (
    http_method,
    route_pattern,
    required_permission_id,
    authentication_required,
    description
)
SELECT
    endpoint.method,
    endpoint.route,
    permission.permission_id,
    endpoint.auth_required,
    endpoint.description

FROM (
    VALUES
        (
            'GET',
            '/health',
            NULL::VARCHAR,
            FALSE,
            'Public health check'
        ),
        (
            'GET',
            '/api/users',
            'users:read',
            TRUE,
            'Retrieve user records'
        ),
        (
            'POST',
            '/api/users',
            'users:create',
            TRUE,
            'Create user records'
        ),
        (
            'GET',
            '/api/admin',
            'system:manage',
            TRUE,
            'Administrative endpoint'
        ),
        (
            'GET',
            '/api/reports',
            'reports:read',
            TRUE,
            'Retrieve analytical reports'
        )
) AS endpoint(
    method,
    route,
    permission_code,
    auth_required,
    description
)

LEFT JOIN permissions permission
    ON permission.permission_code = endpoint.permission_code

ON CONFLICT (http_method, route_pattern) DO NOTHING;

-- =============================================================================
-- 29. RATE LIMIT CONFIGURATION
-- =============================================================================

INSERT INTO rate_limit_policies (
    policy_name,
    maximum_requests,
    window_seconds,
    applies_to
)
VALUES
    ('default_ip_policy', 100, 60, 'IP'),
    ('authenticated_user_policy', 200, 60, 'USER'),
    ('sensitive_endpoint_policy', 10, 60, 'ENDPOINT')

ON CONFLICT (policy_name) DO NOTHING;

-- =============================================================================
-- 30. SAMPLE USERS
-- Password hashes are precomputed PBKDF2-style sample values.
-- Production registration must generate unique salts and derive hashes
-- in the application authentication service.
-- =============================================================================

INSERT INTO users (
    user_id,
    username,
    email,
    password_hash,
    password_salt,
    account_status
)
VALUES
(
    '10000000-0000-4000-8000-000000000001',
    'administrator',
    'admin@example.com',
    REPEAT('a', 64),
    REPEAT('b', 32),
    'ACTIVE'
),
(
    '10000000-0000-4000-8000-000000000002',
    'content_editor',
    'editor@example.com',
    REPEAT('c', 64),
    REPEAT('d', 32),
    'ACTIVE'
),
(
    '10000000-0000-4000-8000-000000000003',
    'analyst',
    'analyst@example.com',
    REPEAT('e', 64),
    REPEAT('f', 32),
    'ACTIVE'
),
(
    '10000000-0000-4000-8000-000000000004',
    'suspended_user',
    'suspended@example.com',
    REPEAT('1', 64),
    REPEAT('2', 32),
    'SUSPENDED'
)

ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- 31. SAMPLE USER ROLE ASSIGNMENTS
-- =============================================================================

INSERT INTO user_roles (
    user_id,
    role_id,
    assigned_by
)
SELECT
    u.user_id,
    r.role_id,
    (
        SELECT admin.user_id
        FROM users admin
        WHERE admin.username = 'administrator'
    )

FROM (
    VALUES
        ('administrator', 'admin'),
        ('content_editor', 'editor'),
        ('analyst', 'viewer'),
        ('suspended_user', 'viewer')
) AS assignments(username, role_name)

JOIN users u
    ON u.username = assignments.username

JOIN roles r
    ON r.role_name = assignments.role_name

ON CONFLICT DO NOTHING;

-- =============================================================================
-- 32. SAMPLE TOKENS
-- Token hashes are demonstration identifiers, not usable bearer tokens.
-- Real tokens must be cryptographically issued and hashed by the application.
-- =============================================================================

INSERT INTO access_tokens (
    token_id,
    user_id,
    token_hash,
    token_status,
    issued_at,
    expires_at
)
VALUES
(
    '20000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000001',
    'DEMO_HASH_ADMIN',
    'ACTIVE',
    NOW(),
    NOW() + INTERVAL '15 minutes'
),
(
    '20000000-0000-4000-8000-000000000002',
    '10000000-0000-4000-8000-000000000002',
    'DEMO_HASH_EDITOR',
    'ACTIVE',
    NOW(),
    NOW() + INTERVAL '15 minutes'
),
(
    '20000000-0000-4000-8000-000000000003',
    '10000000-0000-4000-8000-000000000003',
    'DEMO_HASH_VIEWER',
    'ACTIVE',
    NOW(),
    NOW() + INTERVAL '15 minutes'
),
(
    '20000000-0000-4000-8000-000000000004',
    '10000000-0000-4000-8000-000000000003',
    'DEMO_HASH_REVOKED',
    'REVOKED',
    NOW() - INTERVAL '1 hour',
    NOW() + INTERVAL '15 minutes',
    NOW() - INTERVAL '30 minutes'
)

ON CONFLICT (token_id) DO NOTHING;

-- =============================================================================
-- 33. SAMPLE RESOURCES
-- =============================================================================

INSERT INTO api_resources (
    resource_id,
    owner_id,
    resource_name,
    resource_type,
    content,
    is_sensitive
)
VALUES
(
    '30000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000002',
    'Project specification',
    'DOCUMENT',
    '{"classification":"internal","version":1}',
    FALSE
),
(
    '30000000-0000-4000-8000-000000000002',
    '10000000-0000-4000-8000-000000000001',
    'Security administration record',
    'SECURITY_RECORD',
    '{"classification":"restricted","version":2}',
    TRUE
)

ON CONFLICT (resource_id) DO NOTHING;

-- =============================================================================
-- 34. SAMPLE SECURITY AUDIT EVENTS
-- =============================================================================

INSERT INTO security_audit (
    user_id,
    event_type,
    resource_identifier,
    decision,
    severity,
    details
)
VALUES
(
    '10000000-0000-4000-8000-000000000001',
    'ADMIN_LOGIN',
    '/api/login',
    'ALLOW',
    'INFO',
    '{"authentication":"successful"}'
),
(
    '10000000-0000-4000-8000-000000000003',
    'ADMIN_ENDPOINT_ACCESS',
    '/api/admin',
    'DENY',
    'WARNING',
    '{"reason":"insufficient_permissions"}'
),
(
    '10000000-0000-4000-8000-000000000004',
    'ACCOUNT_ACCESS',
    '/api/users',
    'DENY',
    'CRITICAL',
    '{"reason":"account_suspended"}'
);

-- =============================================================================
-- 35. RETRIEVAL: USERS AND ROLES
-- =============================================================================

SELECT
    u.user_id,
    u.username,
    u.account_status,
    r.role_name,
    ur.assigned_at

FROM users u

LEFT JOIN user_roles ur
    ON ur.user_id = u.user_id

LEFT JOIN roles r
    ON r.role_id = ur.role_id

ORDER BY u.username, r.role_name;

-- =============================================================================
-- 36. RETRIEVAL: ROLE PERMISSIONS
-- =============================================================================

SELECT
    r.role_name,
    p.permission_code,
    p.description

FROM role_permissions rp

JOIN roles r
    ON r.role_id = rp.role_id

JOIN permissions p
    ON p.permission_id = rp.permission_id

ORDER BY r.role_name, p.permission_code;

-- =============================================================================
-- 37. VALIDATION: TOKEN STATUS
-- =============================================================================

SELECT *
FROM validate_access_token('DEMO_HASH_ADMIN');

SELECT *
FROM validate_access_token('DEMO_HASH_REVOKED');

SELECT *
FROM validate_access_token('UNKNOWN_TOKEN');

-- =============================================================================
-- 38. VALIDATION: PERMISSION EVALUATION
-- =============================================================================

SELECT
    u.username,
    has_permission(
        u.user_id,
        'system:manage'
    ) AS can_manage_system

FROM users u

ORDER BY u.username;

-- =============================================================================
-- 39. VALIDATION: RESOURCE OWNERSHIP
-- =============================================================================

SELECT
    u.username,
    r.resource_name,
    can_access_resource(
        u.user_id,
        r.resource_id
    ) AS can_access

FROM users u

CROSS JOIN api_resources r

ORDER BY u.username, r.resource_name;

-- =============================================================================
-- 40. ENDPOINT ELIGIBILITY
-- =============================================================================

SELECT
    u.username,
    access_result.eligible,
    access_result.explanation

FROM users u

CROSS JOIN LATERAL evaluate_endpoint_access(
    u.user_id,
    'GET',
    '/api/admin'
) AS access_result

ORDER BY u.username;

-- =============================================================================
-- 41. CTE: EFFECTIVE PERMISSION COUNTS
-- =============================================================================

WITH effective_permissions AS (
    SELECT DISTINCT
        u.user_id,
        u.username,
        p.permission_code

    FROM users u

    JOIN user_roles ur
        ON ur.user_id = u.user_id

    JOIN role_permissions rp
        ON rp.role_id = ur.role_id

    JOIN permissions p
        ON p.permission_id = rp.permission_id

    WHERE u.account_status = 'ACTIVE'
)

SELECT
    username,
    COUNT(permission_code) AS permission_count,
    ARRAY_AGG(
        permission_code
        ORDER BY permission_code
    ) AS granted_permissions

FROM effective_permissions

GROUP BY username

ORDER BY permission_count DESC;

-- =============================================================================
-- 42. AGGREGATION: SECURITY DECISIONS
-- =============================================================================

SELECT
    decision,
    severity,
    COUNT(*) AS event_count

FROM security_audit

GROUP BY decision, severity

ORDER BY decision, severity;

-- =============================================================================
-- 43. REPORTING: SECURITY EVENTS BY USER
-- =============================================================================

SELECT
    COALESCE(username, 'Unknown or deleted user') AS username,
    COUNT(*) AS total_events,

    COUNT(*) FILTER (
        WHERE decision = 'ALLOW'
    ) AS allowed_events,

    COUNT(*) FILTER (
        WHERE decision = 'DENY'
    ) AS denied_events

FROM security_audit_report

GROUP BY username

ORDER BY total_events DESC;

-- =============================================================================
-- 44. WORKFLOW: RECORD A RATE-LIMITED REQUEST
-- =============================================================================

SELECT check_rate_limit(
    (
        SELECT policy_id
        FROM rate_limit_policies
        WHERE policy_name = 'default_ip_policy'
    ),
    '192.0.2.10'
) AS request_allowed;

-- =============================================================================
-- 45. WORKFLOW: RECORD A SECURITY EVENT
-- =============================================================================

SELECT write_security_audit(
    '10000000-0000-4000-8000-000000000001',
    'RESOURCE_ACCESS',
    '30000000-0000-4000-8000-000000000001',
    'ALLOW',
    'INFO',
    '{"operation":"READ","source":"API"}'::JSONB
) AS audit_identifier;

-- =============================================================================
-- 46. REPORTING: RECENT DENIED ACCESS
-- =============================================================================

SELECT
    audit_id,
    username,
    event_type,
    resource_identifier,
    severity,
    details,
    occurred_at

FROM security_audit_report

WHERE decision = 'DENY'

ORDER BY occurred_at DESC

LIMIT 100;

-- =============================================================================
-- 47. WORKFLOW: REVOKE A TOKEN
-- =============================================================================

SELECT revoke_access_token(
    '20000000-0000-4000-8000-000000000003'
) AS token_revoked;

-- =============================================================================
-- 48. FAILURE CASE: DISABLED ACCOUNT
-- =============================================================================

SELECT
    user_id,
    username,
    account_status,
    (
        account_status = 'ACTIVE'
        AND (
            locked_until IS NULL
            OR locked_until <= NOW()
        )
    ) AS account_eligible

FROM users

WHERE account_status <> 'ACTIVE';

-- =============================================================================
-- 49. FAILURE CASE: EXPIRED OR REVOKED TOKENS
-- =============================================================================

SELECT
    token_id,
    user_id,
    token_status,
    expires_at,
    revoked_at

FROM access_tokens

WHERE token_status <> 'ACTIVE'
   OR expires_at <= NOW()

ORDER BY expires_at;

-- =============================================================================
-- 50. TRANSACTIONAL ADMINISTRATIVE WORKFLOW
-- =============================================================================

-- This transaction is deliberately rolled back to keep the demonstration
-- users unchanged. It demonstrates atomic account deactivation and token
-- revocation.

BEGIN;

CALL deactivate_user(
    '10000000-0000-4000-8000-000000000003',
    '10000000-0000-4000-8000-000000000001'
);

SELECT
    username,
    account_status

FROM users

WHERE username = 'analyst';

ROLLBACK;

-- =============================================================================
-- 51. PERFORMANCE: INDEX USAGE INSPECTION
-- =============================================================================

EXPLAIN
SELECT
    token_id,
    user_id,
    expires_at

FROM access_tokens

WHERE user_id =
    '10000000-0000-4000-8000-000000000001'
  AND token_status = 'ACTIVE'
  AND expires_at > NOW();

EXPLAIN
SELECT
    audit_id,
    event_type,
    decision,
    occurred_at

FROM security_audit

WHERE decision = 'DENY'

ORDER BY occurred_at DESC;

-- =============================================================================
-- 52. DATA INTEGRITY VALIDATION
-- =============================================================================

SELECT
    'Users without roles' AS validation,
    COUNT(*) AS failure_count

FROM users u

LEFT JOIN user_roles ur
    ON ur.user_id = u.user_id

WHERE ur.user_id IS NULL

UNION ALL

SELECT
    'Tokens belonging to inactive users',
    COUNT(*)

FROM access_tokens t

JOIN users u
    ON u.user_id = t.user_id

WHERE u.account_status <> 'ACTIVE'
  AND t.token_status = 'ACTIVE'

UNION ALL

SELECT
    'Expired tokens still marked active',
    COUNT(*)

FROM access_tokens

WHERE token_status = 'ACTIVE'
  AND expires_at <= NOW();

-- =============================================================================
-- 53. SECURITY OPERATIONS
-- =============================================================================

-- Expired tokens can be marked inactive using a scheduled maintenance job.
UPDATE access_tokens
SET token_status = 'EXPIRED'
WHERE token_status = 'ACTIVE'
  AND expires_at <= NOW();

-- Remove old rate-limit history after the operational retention period.
DELETE FROM rate_limit_events
WHERE occurred_at < NOW() - INTERVAL '7 days';

-- =============================================================================
-- 54. COMMIT
-- =============================================================================

COMMIT;

-- =============================================================================
-- 55. OPERATIONAL SECURITY NOTES
-- =============================================================================

1. PostgreSQL stores password hashes and salts but does not authenticate
   plaintext passwords. The application must perform PBKDF2, Argon2id,
   or another approved password-hashing operation.

2. Token hashes are stored instead of raw bearer tokens. A secure
   application should hash tokens before persistence.

3. Database functions evaluate authorization state but do not replace
   authorization enforcement in the API gateway.

4. SECURITY INVOKER functions execute using the caller's privileges.
   Production deployments must establish narrowly scoped database roles.

5. The rate limiter uses transaction-scoped advisory locks to serialize
   competing requests for a subject and policy. Hash collisions can cause
   unnecessary serialization but do not grant additional requests.

6. Application-level rate limiting or a dedicated distributed limiter
   is appropriate for high-volume deployments.

7. Audit tables should be protected against unauthorized UPDATE and DELETE.
   Production systems should export security events to protected storage.

8. The demonstration password hashes and token identifiers are synthetic.
   They cannot be used as production credentials.

9. Database credentials, signing keys, connection strings, and passwords
   must not be committed to source control.

10. Production API connections must use TLS, database least privilege,
    secret rotation, monitoring, and backup procedures.
*/

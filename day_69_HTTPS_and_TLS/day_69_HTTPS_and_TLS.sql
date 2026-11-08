-- ============================================================
-- HTTPS AND TLS SECURITY MANAGEMENT
-- PostgreSQL 18 compatible
--
-- Domain:
--   TLS endpoints
--   X.509 certificate inventory
--   Certificate lifecycle
--   TLS handshake audit records
--   Cipher suite inventory
--   HTTPS termination architecture
--   Backend encryption requirements
--   Security policy evaluation
--   Certificate expiration monitoring
--
-- Database stores audit metadata.
-- It does not perform cryptographic TLS handshakes.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS tls_security;

SET search_path TO tls_security, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE tls_protocol AS ENUM (
    'TLS_1_2',
    'TLS_1_3'
);

CREATE TYPE certificate_status AS ENUM (
    'VALID',
    'EXPIRING',
    'EXPIRED',
    'REVOKED',
    'INVALID',
    'PENDING'
);

CREATE TYPE termination_mode AS ENUM (
    'EDGE',
    'REVERSE_PROXY',
    'PASSTHROUGH'
);

CREATE TYPE handshake_status AS ENUM (
    'SUCCESS',
    'FAILED',
    'TIMEOUT',
    'REJECTED'
);

CREATE TYPE certificate_type AS ENUM (
    'SERVER',
    'CLIENT',
    'INTERMEDIATE_CA',
    'ROOT_CA'
);

CREATE TYPE policy_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

-- ============================================================
-- 2. ORGANIZATIONS AND SECURITY TEAMS
-- ============================================================

CREATE TABLE organizations (
    organization_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    organization_name VARCHAR(150) NOT NULL UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE security_teams (
    team_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),

    team_name VARCHAR(120) NOT NULL,

    UNIQUE (organization_id, team_name)
);

CREATE TABLE security_operators (
    operator_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    team_id BIGINT NOT NULL
        REFERENCES security_teams(team_id),

    operator_name VARCHAR(120) NOT NULL,

    email VARCHAR(255) NOT NULL UNIQUE,

    role_name VARCHAR(40) NOT NULL
        CHECK (
            role_name IN (
                'ADMIN',
                'SECURITY_ENGINEER',
                'AUDITOR',
                'READ_ONLY'
            )
        ),

    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 3. TLS ENDPOINT INVENTORY
-- ============================================================

CREATE TABLE tls_endpoints (
    endpoint_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),

    endpoint_name VARCHAR(150) NOT NULL,

    hostname VARCHAR(253) NOT NULL,

    port INTEGER NOT NULL DEFAULT 443
        CHECK (port BETWEEN 1 AND 65535),

    environment VARCHAR(20) NOT NULL
        CHECK (
            environment IN (
                'DEVELOPMENT',
                'TEST',
                'STAGING',
                'PRODUCTION'
            )
        ),

    minimum_tls_version tls_protocol NOT NULL
        DEFAULT 'TLS_1_2',

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        organization_id,
        hostname,
        port
    ),

    UNIQUE (
        organization_id,
        endpoint_name
    )
);

CREATE INDEX idx_tls_endpoints_hostname
    ON tls_endpoints(hostname);

CREATE INDEX idx_tls_endpoints_environment
    ON tls_endpoints(environment, enabled);

-- ============================================================
-- 4. CERTIFICATE AUTHORITIES
-- ============================================================

CREATE TABLE certificate_authorities (
    ca_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),

    ca_name VARCHAR(150) NOT NULL,

    issuer_common_name VARCHAR(255) NOT NULL,

    trusted BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        organization_id,
        ca_name
    )
);

-- ============================================================
-- 5. X.509 CERTIFICATE INVENTORY
-- ============================================================

CREATE TABLE certificates (
    certificate_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    endpoint_id BIGINT
        REFERENCES tls_endpoints(endpoint_id),

    ca_id BIGINT
        REFERENCES certificate_authorities(ca_id),

    certificate_type certificate_type NOT NULL
        DEFAULT 'SERVER',

    common_name VARCHAR(255) NOT NULL,

    serial_number VARCHAR(150) NOT NULL UNIQUE,

    fingerprint_sha256 VARCHAR(95) NOT NULL UNIQUE
        CHECK (
            fingerprint_sha256 ~
            '^([A-Fa-f0-9]{2}:){31}[A-Fa-f0-9]{2}$'
        ),

    public_key_algorithm VARCHAR(40) NOT NULL,

    signature_algorithm VARCHAR(80) NOT NULL,

    valid_from TIMESTAMPTZ NOT NULL,

    valid_until TIMESTAMPTZ NOT NULL,

    status certificate_status NOT NULL
        DEFAULT 'PENDING',

    subject_alternative_names TEXT[] NOT NULL
        DEFAULT ARRAY[]::TEXT[],

    last_checked_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (valid_until > valid_from),

    CHECK (
        certificate_type <> 'SERVER'
        OR endpoint_id IS NOT NULL
    ),

    CHECK (
        cardinality(subject_alternative_names) <= 100
    )
);

CREATE INDEX idx_certificates_endpoint
    ON certificates(endpoint_id);

CREATE INDEX idx_certificates_expiration
    ON certificates(valid_until)
    WHERE status IN ('VALID', 'EXPIRING');

CREATE INDEX idx_certificates_status
    ON certificates(status);

CREATE INDEX idx_certificates_san
    ON certificates USING GIN(subject_alternative_names);

-- ============================================================
-- 6. CIPHER SUITE INVENTORY
-- ============================================================

CREATE TABLE cipher_suites (
    cipher_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    cipher_name VARCHAR(150) NOT NULL UNIQUE,

    protocol tls_protocol NOT NULL,

    encryption_algorithm VARCHAR(80) NOT NULL,

    authentication_algorithm VARCHAR(80) NOT NULL,

    key_exchange VARCHAR(80) NOT NULL,

    approved BOOLEAN NOT NULL DEFAULT TRUE,

    description TEXT
);

CREATE TABLE endpoint_cipher_support (
    endpoint_id BIGINT NOT NULL
        REFERENCES tls_endpoints(endpoint_id)
        ON DELETE CASCADE,

    cipher_id BIGINT NOT NULL
        REFERENCES cipher_suites(cipher_id),

    PRIMARY KEY (
        endpoint_id,
        cipher_id
    )
);

-- ============================================================
-- 7. HTTPS TERMINATION CONFIGURATION
-- ============================================================

CREATE TABLE termination_configurations (
    termination_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    endpoint_id BIGINT NOT NULL UNIQUE
        REFERENCES tls_endpoints(endpoint_id),

    mode termination_mode NOT NULL,

    frontend_tls_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    backend_tls_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    backend_certificate_verification BOOLEAN NOT NULL
        DEFAULT TRUE,

    trusted_proxy_headers BOOLEAN NOT NULL DEFAULT TRUE,

    secure_cookies_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    hsts_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    hsts_max_age_seconds INTEGER NOT NULL DEFAULT 31536000
        CHECK (
            hsts_max_age_seconds BETWEEN 0 AND 63072000
        ),

    configuration_version INTEGER NOT NULL DEFAULT 1
        CHECK (configuration_version > 0),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 8. TLS SECURITY POLICIES
-- ============================================================

CREATE TABLE tls_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),

    policy_name VARCHAR(150) NOT NULL,

    minimum_protocol tls_protocol NOT NULL,

    certificate_warning_days INTEGER NOT NULL DEFAULT 30
        CHECK (
            certificate_warning_days BETWEEN 0 AND 365
        ),

    require_backend_tls BOOLEAN NOT NULL DEFAULT TRUE,

    require_secure_cookies BOOLEAN NOT NULL DEFAULT TRUE,

    require_hsts BOOLEAN NOT NULL DEFAULT TRUE,

    require_trusted_ca BOOLEAN NOT NULL DEFAULT TRUE,

    require_hostname_match BOOLEAN NOT NULL DEFAULT TRUE,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        organization_id,
        policy_name
    )
);

CREATE TABLE policy_cipher_rules (
    policy_id BIGINT NOT NULL
        REFERENCES tls_policies(policy_id)
        ON DELETE CASCADE,

    cipher_id BIGINT NOT NULL
        REFERENCES cipher_suites(cipher_id),

    PRIMARY KEY (policy_id, cipher_id)
);

-- ============================================================
-- 9. TLS HANDSHAKE AUDIT
-- ============================================================

CREATE TABLE handshake_audits (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    endpoint_id BIGINT NOT NULL
        REFERENCES tls_endpoints(endpoint_id),

    certificate_id BIGINT
        REFERENCES certificates(certificate_id),

    cipher_id BIGINT
        REFERENCES cipher_suites(cipher_id),

    negotiated_protocol tls_protocol,

    status handshake_status NOT NULL,

    duration_ms INTEGER
        CHECK (
            duration_ms IS NULL OR duration_ms >= 0
        ),

    peer_verified BOOLEAN,

    hostname_verified BOOLEAN,

    error_code VARCHAR(100),

    error_message TEXT,

    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        status <> 'SUCCESS'
        OR (
            negotiated_protocol IS NOT NULL
            AND cipher_id IS NOT NULL
            AND certificate_id IS NOT NULL
            AND peer_verified IS TRUE
            AND hostname_verified IS TRUE
        )
    ),

    CHECK (
        status = 'SUCCESS'
        OR error_message IS NOT NULL
    )
);

CREATE INDEX idx_handshake_endpoint_time
    ON handshake_audits(
        endpoint_id,
        observed_at DESC
    );

CREATE INDEX idx_handshake_failures
    ON handshake_audits(observed_at DESC)
    WHERE status <> 'SUCCESS';

-- ============================================================
-- 10. POLICY VIOLATIONS
-- ============================================================

CREATE TABLE policy_violations (
    violation_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    policy_id BIGINT NOT NULL
        REFERENCES tls_policies(policy_id),

    endpoint_id BIGINT NOT NULL
        REFERENCES tls_endpoints(endpoint_id),

    audit_id BIGINT
        REFERENCES handshake_audits(audit_id),

    violation_code VARCHAR(100) NOT NULL,

    description TEXT NOT NULL,

    severity policy_severity NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    CHECK (
        resolved_at IS NULL OR resolved_at >= detected_at
    )
);

CREATE INDEX idx_open_policy_violations
    ON policy_violations(
        severity,
        detected_at DESC
    )
    WHERE resolved_at IS NULL;

-- ============================================================
-- 11. CERTIFICATE LIFECYCLE HISTORY
-- ============================================================

CREATE TABLE certificate_status_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    certificate_id BIGINT NOT NULL
        REFERENCES certificates(certificate_id),

    previous_status certificate_status,

    new_status certificate_status NOT NULL,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION record_certificate_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO certificate_status_history (
            certificate_id,
            previous_status,
            new_status
        )
        VALUES (
            NEW.certificate_id,
            OLD.status,
            NEW.status
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_certificate_status_history
AFTER UPDATE OF status ON certificates
FOR EACH ROW
EXECUTE FUNCTION record_certificate_status();

-- ============================================================
-- 12. AUTOMATIC CERTIFICATE STATUS EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_certificate_status(
    p_valid_until TIMESTAMPTZ,
    p_warning_days INTEGER
)
RETURNS certificate_status
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_warning_days < 0 THEN
        RAISE EXCEPTION
            'Warning days cannot be negative';
    END IF;

    IF p_valid_until <= NOW() THEN
        RETURN 'EXPIRED';
    END IF;

    IF p_valid_until <=
        NOW() + make_interval(days => p_warning_days)
    THEN
        RETURN 'EXPIRING';
    END IF;

    RETURN 'VALID';
END;
$$;

CREATE OR REPLACE PROCEDURE refresh_certificate_statuses(
    p_warning_days INTEGER DEFAULT 30
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_warning_days < 0 THEN
        RAISE EXCEPTION
            'Warning days cannot be negative';
    END IF;

    UPDATE certificates
    SET
        status = calculate_certificate_status(
            valid_until,
            p_warning_days
        ),
        last_checked_at = NOW()
    WHERE status NOT IN ('REVOKED', 'INVALID');
END;
$$;

-- ============================================================
-- 13. TERMINATION POLICY EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_termination(
    p_endpoint_id BIGINT
)
RETURNS TABLE (
    violation_code TEXT,
    violation_description TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    configuration termination_configurations%ROWTYPE;
BEGIN
    SELECT *
    INTO configuration
    FROM termination_configurations
    WHERE endpoint_id = p_endpoint_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            'MISSING_CONFIGURATION'::TEXT,
            'No termination configuration exists'::TEXT;

        RETURN;
    END IF;

    IF NOT configuration.frontend_tls_enabled THEN
        RETURN QUERY
        SELECT
            'FRONTEND_TLS_DISABLED'::TEXT,
            'Public traffic must use HTTPS'::TEXT;
    END IF;

    IF configuration.mode IN ('EDGE', 'REVERSE_PROXY') THEN
        IF NOT configuration.backend_tls_enabled THEN
            RETURN QUERY
            SELECT
                'BACKEND_TLS_DISABLED'::TEXT,
                'Proxy-to-application traffic is unencrypted'::TEXT;
        END IF;

        IF (
            configuration.backend_tls_enabled
            AND NOT configuration.backend_certificate_verification
        ) THEN
            RETURN QUERY
            SELECT
                'BACKEND_CERTIFICATE_UNVERIFIED'::TEXT,
                'Backend server certificate is not verified'::TEXT;
        END IF;

        IF NOT configuration.trusted_proxy_headers THEN
            RETURN QUERY
            SELECT
                'UNTRUSTED_PROXY_HEADERS'::TEXT,
                'Forwarded protocol headers are not trusted'::TEXT;
        END IF;
    END IF;

    IF NOT configuration.secure_cookies_enabled THEN
        RETURN QUERY
        SELECT
            'INSECURE_COOKIES'::TEXT,
            'Session cookies require Secure protection'::TEXT;
    END IF;

    IF NOT configuration.hsts_enabled THEN
        RETURN QUERY
        SELECT
            'HSTS_DISABLED'::TEXT,
            'HTTP Strict Transport Security is disabled'::TEXT;
    END IF;
END;
$$;

-- ============================================================
-- 14. ENDPOINT ELIGIBILITY
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_endpoint(
    p_endpoint_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    violation_count BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(v.violation_code) = 0,
        COUNT(v.violation_code)
    FROM evaluate_termination(p_endpoint_id) v;
$$;

-- ============================================================
-- 15. SAMPLE ORGANIZATION DATA
-- ============================================================

INSERT INTO organizations (organization_name)
VALUES
    ('Enterprise Technology Division'),
    ('Financial Services Division');

INSERT INTO security_teams (
    organization_id,
    team_name
)
SELECT organization_id, 'Infrastructure Security'
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

INSERT INTO security_teams (
    organization_id,
    team_name
)
SELECT organization_id, 'Application Security'
FROM organizations
WHERE organization_name = 'Financial Services Division';

INSERT INTO security_operators (
    team_id,
    operator_name,
    email,
    role_name
)
SELECT
    team_id,
    'Security Administrator',
    'security.admin@example.com',
    'ADMIN'
FROM security_teams
WHERE team_name = 'Infrastructure Security';

INSERT INTO security_operators (
    team_id,
    operator_name,
    email,
    role_name
)
SELECT
    team_id,
    'TLS Auditor',
    'tls.auditor@example.com',
    'AUDITOR'
FROM security_teams
WHERE team_name = 'Application Security';

-- ============================================================
-- 16. ENDPOINT DATA
-- ============================================================

INSERT INTO tls_endpoints (
    organization_id,
    endpoint_name,
    hostname,
    port,
    environment,
    minimum_tls_version
)
SELECT
    organization_id,
    'Public API Gateway',
    'api.example.com',
    443,
    'PRODUCTION',
    'TLS_1_2'
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

INSERT INTO tls_endpoints (
    organization_id,
    endpoint_name,
    hostname,
    port,
    environment,
    minimum_tls_version
)
SELECT
    organization_id,
    'Legacy Application Gateway',
    'legacy.example.com',
    443,
    'PRODUCTION',
    'TLS_1_2'
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

-- ============================================================
-- 17. CERTIFICATE AUTHORITIES
-- ============================================================

INSERT INTO certificate_authorities (
    organization_id,
    ca_name,
    issuer_common_name,
    trusted
)
SELECT
    organization_id,
    'Enterprise Root CA',
    'Enterprise Root Certificate Authority',
    TRUE
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

INSERT INTO certificate_authorities (
    organization_id,
    ca_name,
    issuer_common_name,
    trusted
)
SELECT
    organization_id,
    'Untrusted Test CA',
    'Unknown Certificate Authority',
    FALSE
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

-- ============================================================
-- 18. CERTIFICATE RECORDS
-- Fingerprints are synthetic, structurally valid sample values.
-- ============================================================

INSERT INTO certificates (
    endpoint_id,
    ca_id,
    common_name,
    serial_number,
    fingerprint_sha256,
    public_key_algorithm,
    signature_algorithm,
    valid_from,
    valid_until,
    status,
    subject_alternative_names
)
SELECT
    e.endpoint_id,
    ca.ca_id,
    'api.example.com',
    'CERT-2026-001',
    '01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01:01',
    'RSA-3072',
    'SHA256withRSA',
    NOW() - INTERVAL '30 days',
    NOW() + INTERVAL '180 days',
    'VALID',
    ARRAY['api.example.com', 'www.example.com']
FROM tls_endpoints e
JOIN certificate_authorities ca
    ON ca.ca_name = 'Enterprise Root CA'
WHERE e.hostname = 'api.example.com';

INSERT INTO certificates (
    endpoint_id,
    ca_id,
    common_name,
    serial_number,
    fingerprint_sha256,
    public_key_algorithm,
    signature_algorithm,
    valid_from,
    valid_until,
    status,
    subject_alternative_names
)
SELECT
    e.endpoint_id,
    ca.ca_id,
    'legacy.example.com',
    'CERT-2026-002',
    '02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02:02',
    'RSA-2048',
    'SHA256withRSA',
    NOW() - INTERVAL '300 days',
    NOW() + INTERVAL '12 days',
    'EXPIRING',
    ARRAY['legacy.example.com']
FROM tls_endpoints e
JOIN certificate_authorities ca
    ON ca.ca_name = 'Enterprise Root CA'
WHERE e.hostname = 'legacy.example.com';

-- ============================================================
-- 19. CIPHER SUITES
-- ============================================================

INSERT INTO cipher_suites (
    cipher_name,
    protocol,
    encryption_algorithm,
    authentication_algorithm,
    key_exchange,
    approved
)
VALUES
(
    'TLS_AES_128_GCM_SHA256',
    'TLS_1_3',
    'AES_128_GCM',
    'AEAD',
    'ECDHE',
    TRUE
),
(
    'TLS_AES_256_GCM_SHA384',
    'TLS_1_3',
    'AES_256_GCM',
    'AEAD',
    'ECDHE',
    TRUE
),
(
    'TLS_CHACHA20_POLY1305_SHA256',
    'TLS_1_3',
    'CHACHA20_POLY1305',
    'AEAD',
    'ECDHE',
    TRUE
),
(
    'ECDHE-RSA-AES128-GCM-SHA256',
    'TLS_1_2',
    'AES_128_GCM',
    'RSA',
    'ECDHE',
    TRUE
),
(
    'TLS_RSA_WITH_3DES_EDE_CBC_SHA',
    'TLS_1_2',
    '3DES',
    'RSA',
    'RSA',
    FALSE
);

INSERT INTO endpoint_cipher_support (
    endpoint_id,
    cipher_id
)
SELECT
    e.endpoint_id,
    c.cipher_id
FROM tls_endpoints e
CROSS JOIN cipher_suites c
WHERE e.hostname = 'api.example.com'
AND c.approved = TRUE;

INSERT INTO endpoint_cipher_support (
    endpoint_id,
    cipher_id
)
SELECT
    e.endpoint_id,
    c.cipher_id
FROM tls_endpoints e
JOIN cipher_suites c
    ON c.cipher_name = 'ECDHE-RSA-AES128-GCM-SHA256'
WHERE e.hostname = 'legacy.example.com';

-- ============================================================
-- 20. TERMINATION CONFIGURATIONS
-- ============================================================

INSERT INTO termination_configurations (
    endpoint_id,
    mode,
    frontend_tls_enabled,
    backend_tls_enabled,
    backend_certificate_verification,
    trusted_proxy_headers,
    secure_cookies_enabled,
    hsts_enabled
)
SELECT
    endpoint_id,
    'REVERSE_PROXY',
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE
FROM tls_endpoints
WHERE hostname = 'api.example.com';

-- Intentionally insecure configuration for audit demonstration.
INSERT INTO termination_configurations (
    endpoint_id,
    mode,
    frontend_tls_enabled,
    backend_tls_enabled,
    backend_certificate_verification,
    trusted_proxy_headers,
    secure_cookies_enabled,
    hsts_enabled
)
SELECT
    endpoint_id,
    'REVERSE_PROXY',
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    FALSE,
    FALSE
FROM tls_endpoints
WHERE hostname = 'legacy.example.com';

-- ============================================================
-- 21. POLICY RECORDS
-- ============================================================

INSERT INTO tls_policies (
    organization_id,
    policy_name,
    minimum_protocol,
    certificate_warning_days,
    require_backend_tls,
    require_secure_cookies,
    require_hsts,
    require_trusted_ca,
    require_hostname_match
)
SELECT
    organization_id,
    'Production TLS Baseline',
    'TLS_1_2',
    30,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE
FROM organizations
WHERE organization_name = 'Enterprise Technology Division';

INSERT INTO policy_cipher_rules (
    policy_id,
    cipher_id
)
SELECT
    p.policy_id,
    c.cipher_id
FROM tls_policies p
CROSS JOIN cipher_suites c
WHERE p.policy_name = 'Production TLS Baseline'
AND c.approved = TRUE;

-- ============================================================
-- 22. HANDSHAKE AUDIT RECORDS
-- Successful records require verified certificates.
-- ============================================================

INSERT INTO handshake_audits (
    endpoint_id,
    certificate_id,
    cipher_id,
    negotiated_protocol,
    status,
    duration_ms,
    peer_verified,
    hostname_verified
)
SELECT
    e.endpoint_id,
    cert.certificate_id,
    cipher.cipher_id,
    'TLS_1_3',
    'SUCCESS',
    42,
    TRUE,
    TRUE
FROM tls_endpoints e
JOIN certificates cert
    ON cert.endpoint_id = e.endpoint_id
JOIN cipher_suites cipher
    ON cipher.cipher_name = 'TLS_AES_128_GCM_SHA256'
WHERE e.hostname = 'api.example.com';

INSERT INTO handshake_audits (
    endpoint_id,
    certificate_id,
    status,
    duration_ms,
    peer_verified,
    hostname_verified,
    error_code,
    error_message
)
SELECT
    e.endpoint_id,
    cert.certificate_id,
    'FAILED',
    120,
    FALSE,
    FALSE,
    'CERTIFICATE_VALIDATION_FAILED',
    'Certificate verification failed during the handshake'
FROM tls_endpoints e
JOIN certificates cert
    ON cert.endpoint_id = e.endpoint_id
WHERE e.hostname = 'legacy.example.com';

-- ============================================================
-- 23. REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW endpoint_security_overview AS
SELECT
    e.endpoint_id,
    e.hostname,
    e.port,
    e.environment,
    e.minimum_tls_version,
    c.common_name,
    c.status AS certificate_status,
    c.valid_until,
    c.valid_until - NOW() AS certificate_lifetime_remaining,
    t.mode AS termination_mode,
    t.frontend_tls_enabled,
    t.backend_tls_enabled,
    t.backend_certificate_verification,
    t.secure_cookies_enabled,
    t.hsts_enabled
FROM tls_endpoints e
LEFT JOIN certificates c
    ON c.endpoint_id = e.endpoint_id
LEFT JOIN termination_configurations t
    ON t.endpoint_id = e.endpoint_id;

-- ============================================================
-- 24. CERTIFICATE EXPIRATION REPORT
-- ============================================================

CREATE OR REPLACE VIEW certificate_expiration_report AS
SELECT
    certificate_id,
    common_name,
    serial_number,
    valid_until,
    status,
    GREATEST(
        0,
        CEIL(
            EXTRACT(
                EPOCH FROM (valid_until - NOW())
            ) / 86400
        )
    ) AS remaining_days
FROM certificates
WHERE status IN ('VALID', 'EXPIRING', 'EXPIRED');

-- ============================================================
-- 25. SECURITY POLICY VIOLATION PROCESSING
-- ============================================================

CREATE OR REPLACE PROCEDURE process_termination_violations(
    p_policy_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    endpoint_record RECORD;
    violation_record RECORD;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM tls_policies
        WHERE policy_id = p_policy_id
        AND active = TRUE
    ) THEN
        RAISE EXCEPTION
            'Active TLS policy % not found',
            p_policy_id;
    END IF;

    FOR endpoint_record IN
        SELECT endpoint_id
        FROM tls_endpoints
        WHERE enabled = TRUE
    LOOP
        FOR violation_record IN
            SELECT *
            FROM evaluate_termination(
                endpoint_record.endpoint_id
            )
        LOOP
            INSERT INTO policy_violations (
                policy_id,
                endpoint_id,
                violation_code,
                description,
                severity
            )
            VALUES (
                p_policy_id,
                endpoint_record.endpoint_id,
                violation_record.violation_code,
                violation_record.violation_description,
                'HIGH'
            );
        END LOOP;
    END LOOP;
END;
$$;

-- ============================================================
-- 26. OPERATIONAL QUERIES
-- ============================================================

-- A. Retrieve all registered HTTPS endpoints.

SELECT *
FROM endpoint_security_overview
ORDER BY environment, hostname;

-- B. Find certificates requiring renewal.

SELECT
    common_name,
    valid_until,
    remaining_days,
    status
FROM certificate_expiration_report
WHERE valid_until <= NOW() + INTERVAL '30 days'
ORDER BY valid_until;

-- C. Aggregate handshake success and failure rates.

SELECT
    e.hostname,
    COUNT(a.audit_id) AS total_handshakes,

    COUNT(*) FILTER (
        WHERE a.status = 'SUCCESS'
    ) AS successful_handshakes,

    COUNT(*) FILTER (
        WHERE a.status <> 'SUCCESS'
    ) AS failed_handshakes,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE a.status = 'SUCCESS'
        ) / NULLIF(COUNT(a.audit_id), 0),
        2
    ) AS success_percentage

FROM tls_endpoints e
LEFT JOIN handshake_audits a
    ON a.endpoint_id = e.endpoint_id
GROUP BY e.endpoint_id, e.hostname
ORDER BY e.hostname;

-- D. Evaluate HTTPS termination compliance.

SELECT
    e.hostname,
    eligibility.eligible,
    eligibility.violation_count
FROM tls_endpoints e
CROSS JOIN LATERAL evaluate_endpoint(
    e.endpoint_id
) eligibility;

-- E. Identify unapproved cipher suites.

SELECT
    e.hostname,
    c.cipher_name,
    c.protocol
FROM endpoint_cipher_support ecs
JOIN tls_endpoints e
    ON e.endpoint_id = ecs.endpoint_id
JOIN cipher_suites c
    ON c.cipher_id = ecs.cipher_id
WHERE c.approved = FALSE;

-- F. Identify endpoints with unsuccessful TLS handshakes.

SELECT
    e.hostname,
    a.status,
    a.error_code,
    a.error_message,
    a.observed_at
FROM handshake_audits a
JOIN tls_endpoints e
    ON e.endpoint_id = a.endpoint_id
WHERE a.status <> 'SUCCESS'
ORDER BY a.observed_at DESC;

-- G. Policy compliance using a CTE.

WITH endpoint_checks AS (
    SELECT
        e.endpoint_id,
        e.hostname,
        v.violation_code,
        v.violation_description
    FROM tls_endpoints e
    LEFT JOIN LATERAL evaluate_termination(
        e.endpoint_id
    ) v ON TRUE
)
SELECT
    hostname,
    COUNT(violation_code) AS violations,
    CASE
        WHEN COUNT(violation_code) = 0
            THEN 'COMPLIANT'
        ELSE 'NON_COMPLIANT'
    END AS compliance_status
FROM endpoint_checks
GROUP BY endpoint_id, hostname
ORDER BY hostname;

-- H. Latest successful handshake per endpoint.

SELECT DISTINCT ON (endpoint_id)
    endpoint_id,
    negotiated_protocol,
    status,
    duration_ms,
    observed_at
FROM handshake_audits
WHERE status = 'SUCCESS'
ORDER BY endpoint_id, observed_at DESC;

-- I. Certificate issuer and trust inventory.

SELECT
    cert.common_name,
    ca.ca_name,
    ca.issuer_common_name,
    ca.trusted,
    cert.status
FROM certificates cert
LEFT JOIN certificate_authorities ca
    ON ca.ca_id = cert.ca_id;

-- ============================================================
-- 27. TRANSACTIONAL POLICY PROCESSING
-- ============================================================

-- Savepoint allows the audit operation to be rolled back
-- without discarding unrelated transaction work.

SAVEPOINT before_policy_processing;

SELECT policy_id
FROM tls_policies
WHERE policy_name = 'Production TLS Baseline';

-- Process the active baseline policy.
CALL process_termination_violations(
    (
        SELECT policy_id
        FROM tls_policies
        WHERE policy_name = 'Production TLS Baseline'
    )
);

-- Verify the inserted violation records.
SELECT
    violation_code,
    description,
    severity
FROM policy_violations
ORDER BY detected_at DESC;

RELEASE SAVEPOINT before_policy_processing;

-- ============================================================
-- 28. CERTIFICATE STATUS REFRESH
-- ============================================================

CALL refresh_certificate_statuses(30);

SELECT
    common_name,
    status,
    valid_until
FROM certificates
ORDER BY valid_until;

-- ============================================================
-- 29. PERFORMANCE AND GOVERNANCE NOTES
-- ============================================================

-- Indexes support endpoint lookups, recent audit retrieval,
-- expiration monitoring, and unresolved violation reporting.
--
-- For high-volume audit deployments, partition handshake_audits
-- by observed_at using monthly range partitions.
--
-- Store private keys in an external secret-management system.
-- Never store private keys, passwords, session secrets, or
-- complete private certificate material in these tables.
--
-- Production roles should receive least-privilege permissions.
-- Database TLS and application HTTPS are separate security layers.

COMMIT;

-- ============================================================
-- 30. FINAL DATABASE REPORT
-- ============================================================

SELECT
    e.hostname,
    e.environment,
    c.status AS certificate_status,
    t.mode AS termination_mode,
    COUNT(a.audit_id) AS handshake_records
FROM tls_endpoints e
LEFT JOIN certificates c
    ON c.endpoint_id = e.endpoint_id
LEFT JOIN termination_configurations t
    ON t.endpoint_id = e.endpoint_id
LEFT JOIN handshake_audits a
    ON a.endpoint_id = e.endpoint_id
GROUP BY
    e.endpoint_id,
    e.hostname,
    e.environment,
    c.status,
    t.mode
ORDER BY e.hostname;

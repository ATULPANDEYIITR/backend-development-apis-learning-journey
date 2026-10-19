DROP SCHEMA IF EXISTS backend_architecture_lab CASCADE;
CREATE SCHEMA backend_architecture_lab;
SET search_path TO backend_architecture_lab;

-- PostgreSQL model for a backend that combines layered architecture,
-- modular-monolith boundaries, and clean-architecture dependency rules.

CREATE TYPE module_kind AS ENUM (
    'identity',
    'billing',
    'orders',
    'payments'
);

CREATE TYPE branch_layer AS ENUM (
    'api',
    'application',
    'domain',
    'infrastructure'
);

CREATE TYPE account_status AS ENUM (
    'active',
    'suspended'
);

CREATE TYPE review_state AS ENUM (
    'pending',
    'approved',
    'rejected'
);

CREATE TABLE backend_module (
    module_id BIGSERIAL PRIMARY KEY,
    module_name TEXT NOT NULL UNIQUE,
    module_type module_kind NOT NULL,
    public_api TEXT NOT NULL,
    CHECK (length(trim(module_name)) > 0),
    CHECK (length(trim(public_api)) > 0)
);

CREATE TABLE architecture_dependency (
    dependency_id BIGSERIAL PRIMARY KEY,
    source_module_id BIGINT NOT NULL
        REFERENCES backend_module(module_id),
    target_module_id BIGINT NOT NULL
        REFERENCES backend_module(module_id),
    source_layer branch_layer NOT NULL,
    target_layer branch_layer NOT NULL,
    rationale TEXT NOT NULL,
    CHECK (source_module_id <> target_module_id),
    CHECK (length(trim(rationale)) > 0),
    UNIQUE (
        source_module_id,
        target_module_id,
        source_layer,
        target_layer
    )
);

-- Domain code must not directly depend on infrastructure or API concerns.
ALTER TABLE architecture_dependency
ADD CONSTRAINT domain_dependency_direction
CHECK (
    NOT (
        source_layer = 'domain'
        AND target_layer IN ('infrastructure', 'api')
    )
);

-- Application code may coordinate domain policy and infrastructure ports,
-- but must not depend inward on an API adapter.
ALTER TABLE architecture_dependency
ADD CONSTRAINT application_dependency_direction
CHECK (
    NOT (
        source_layer = 'application'
        AND target_layer = 'api'
    )
);

CREATE TABLE account (
    account_id BIGSERIAL PRIMARY KEY,
    module_id BIGINT NOT NULL
        REFERENCES backend_module(module_id),
    owner_name TEXT NOT NULL,
    status account_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(owner_name)) > 0)
);

CREATE TABLE invoice (
    invoice_id BIGSERIAL PRIMARY KEY,
    billing_module_id BIGINT NOT NULL
        REFERENCES backend_module(module_id),
    account_id BIGINT NOT NULL
        REFERENCES account(account_id),
    amount_cents BIGINT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (amount_cents > 0)
);

CREATE TABLE payment_port (
    payment_port_id BIGSERIAL PRIMARY KEY,
    module_id BIGINT NOT NULL
        REFERENCES backend_module(module_id),
    port_name TEXT NOT NULL UNIQUE,
    external_adapter_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    CHECK (length(trim(port_name)) > 0),
    CHECK (length(trim(external_adapter_name)) > 0)
);

CREATE TABLE payment_transaction (
    transaction_id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL
        REFERENCES invoice(invoice_id),
    payment_port_id BIGINT NOT NULL
        REFERENCES payment_port(payment_port_id),
    external_reference TEXT NOT NULL UNIQUE,
    amount_cents BIGINT NOT NULL,
    state TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (amount_cents > 0),
    CHECK (state IN ('authorized', 'declined', 'failed'))
);

CREATE TABLE architectural_review (
    review_id BIGSERIAL PRIMARY KEY,
    dependency_id BIGINT NOT NULL
        REFERENCES architecture_dependency(dependency_id),
    reviewer TEXT NOT NULL,
    state review_state NOT NULL DEFAULT 'pending',
    comment TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ,
    CHECK (length(trim(reviewer)) > 0),
    CHECK (length(trim(comment)) > 0),
    CHECK (
        (state = 'pending' AND reviewed_at IS NULL)
        OR
        (state IN ('approved', 'rejected') AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX idx_architecture_dependency_source
    ON architecture_dependency(source_module_id, source_layer);

CREATE INDEX idx_architecture_dependency_target
    ON architecture_dependency(target_module_id, target_layer);

CREATE INDEX idx_account_module_status
    ON account(module_id, status);

CREATE INDEX idx_invoice_account
    ON invoice(account_id);

CREATE INDEX idx_payment_transaction_invoice
    ON payment_transaction(invoice_id);

INSERT INTO backend_module (
    module_name,
    module_type,
    public_api
) VALUES
    ('identity', 'identity', '/internal/identity'),
    ('billing', 'billing', '/internal/billing'),
    ('orders', 'orders', '/internal/orders'),
    ('payments', 'payments', '/internal/payments');

INSERT INTO architecture_dependency (
    source_module_id,
    target_module_id,
    source_layer,
    target_layer,
    rationale
)
SELECT
    source.module_id,
    target.module_id,
    'api',
    'application',
    'API adapters invoke application use cases.'
FROM backend_module source
JOIN backend_module target
    ON target.module_name = 'billing'
WHERE source.module_name = 'billing';

INSERT INTO architecture_dependency (
    source_module_id,
    target_module_id,
    source_layer,
    target_layer,
    rationale
)
SELECT
    source.module_id,
    target.module_id,
    'application',
    'domain',
    'Application services coordinate billing domain rules.'
FROM backend_module source
JOIN backend_module target
    ON target.module_name = 'billing'
WHERE source.module_name = 'orders';

INSERT INTO architecture_dependency (
    source_module_id,
    target_module_id,
    source_layer,
    target_layer,
    rationale
)
SELECT
    source.module_id,
    target.module_id,
    'application',
    'infrastructure',
    'Application composition uses infrastructure implementations through ports.'
FROM backend_module source
JOIN backend_module target
    ON target.module_name = 'payments'
WHERE source.module_name = 'billing';

INSERT INTO account (
    module_id,
    owner_name,
    status
)
SELECT module_id, 'Anita Verma', 'active'
FROM backend_module
WHERE module_name = 'identity';

INSERT INTO account (
    module_id,
    owner_name,
    status
)
SELECT module_id, 'Rohit Kapoor', 'suspended'
FROM backend_module
WHERE module_name = 'identity';

INSERT INTO invoice (
    billing_module_id,
    account_id,
    amount_cents
)
SELECT
    m.module_id,
    a.account_id,
    125000
FROM backend_module m
CROSS JOIN account a
WHERE m.module_name = 'billing'
  AND a.owner_name = 'Anita Verma';

INSERT INTO payment_port (
    module_id,
    port_name,
    external_adapter_name
)
SELECT
    module_id,
    'card_authorization',
    'AcquirerAdapter'
FROM backend_module
WHERE module_name = 'payments';

INSERT INTO payment_transaction (
    invoice_id,
    payment_port_id,
    external_reference,
    amount_cents,
    state
)
SELECT
    i.invoice_id,
    p.payment_port_id,
    'ACQ-100001',
    i.amount_cents,
    'authorized'
FROM invoice i
JOIN payment_port p
    ON p.port_name = 'card_authorization';

INSERT INTO architectural_review (
    dependency_id,
    reviewer,
    state,
    comment,
    reviewed_at
)
SELECT
    dependency_id,
    'principal-architect',
    'approved',
    'Dependency remains within the approved architectural direction.',
    now()
FROM architecture_dependency
WHERE source_layer = 'application'
  AND target_layer = 'domain';

-- Inspect module boundaries and their declared public APIs.
SELECT
    module_name,
    module_type,
    public_api
FROM backend_module
ORDER BY module_name;

-- Find dependencies that would be architecturally dangerous.
-- The constraints prevent insertion, while this query provides an audit view
-- useful for reporting and migration validation.
SELECT
    d.dependency_id,
    s.module_name AS source_module,
    t.module_name AS target_module,
    d.source_layer,
    d.target_layer,
    d.rationale
FROM architecture_dependency d
JOIN backend_module s
    ON s.module_id = d.source_module_id
JOIN backend_module t
    ON t.module_id = d.target_module_id
WHERE (
    d.source_layer = 'domain'
    AND d.target_layer IN ('api', 'infrastructure')
)
OR (
    d.source_layer = 'application'
    AND d.target_layer = 'api'
);

-- Show the business boundary between account state and billing operations.
SELECT
    a.owner_name,
    a.status,
    i.invoice_id,
    i.amount_cents,
    CASE
        WHEN a.status = 'active' THEN 'eligible for billing'
        ELSE 'blocked by domain state'
    END AS billing_decision
FROM account a
LEFT JOIN invoice i
    ON i.account_id = a.account_id
ORDER BY a.account_id;

-- Payment totals are derived from relational state rather than duplicated
-- inside account records.
SELECT
    p.port_name,
    COUNT(t.transaction_id) AS transaction_count,
    COALESCE(SUM(t.amount_cents), 0) AS authorized_cents
FROM payment_port p
LEFT JOIN payment_transaction t
    ON t.payment_port_id = p.payment_port_id
   AND t.state = 'authorized'
GROUP BY p.port_name
ORDER BY p.port_name;

-- Transactional workflow: invoice creation and payment authorization are
-- treated as one database operation in this demonstration.
BEGIN;

INSERT INTO invoice (
    billing_module_id,
    account_id,
    amount_cents
)
SELECT
    m.module_id,
    a.account_id,
    87500
FROM backend_module m
JOIN account a
    ON a.owner_name = 'Anita Verma'
WHERE m.module_name = 'billing'
  AND a.status = 'active';

COMMIT;

-- PostgreSQL transaction behavior can expose invalid domain state.
-- The following statement is deliberately inside a rollback transaction.
BEGIN;

INSERT INTO invoice (
    billing_module_id,
    account_id,
    amount_cents
)
SELECT
    m.module_id,
    a.account_id,
    -100
FROM backend_module m
JOIN account a
    ON a.owner_name = 'Anita Verma'
WHERE m.module_name = 'billing';

ROLLBACK;

-- The negative amount was rejected by the CHECK constraint and therefore
-- cannot become persistent application state.
SELECT
    COUNT(*) AS negative_invoices
FROM invoice
WHERE amount_cents <= 0;

-- Architectural review coverage identifies dependencies without a completed
-- review, making architecture governance observable rather than purely
-- documentary.
SELECT
    s.module_name AS source_module,
    t.module_name AS target_module,
    d.source_layer,
    d.target_layer,
    COALESCE(
        string_agg(r.state::text, ', ' ORDER BY r.review_id),
        'no review'
    ) AS review_states
FROM architecture_dependency d
JOIN backend_module s
    ON s.module_id = d.source_module_id
JOIN backend_module t
    ON t.module_id = d.target_module_id
LEFT JOIN architectural_review r
    ON r.dependency_id = d.dependency_id
GROUP BY
    s.module_name,
    t.module_name,
    d.source_layer,
    d.target_layer
ORDER BY
    s.module_name,
    t.module_name;

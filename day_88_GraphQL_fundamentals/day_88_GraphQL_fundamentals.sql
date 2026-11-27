-- =========================================================
-- GRAPHQL FUNDAMENTALS
-- PostgreSQL 15+
--
-- Relational representation of:
-- Schemas, types, fields, arguments, queries, mutations,
-- resolver registrations, execution records, authorization,
-- complexity policies, and execution errors.
--
-- The database stores GraphQL metadata and business state.
-- Actual GraphQL parsing and transport execution are handled
-- by an application server.
-- =========================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS graphql_lab;

SET search_path TO graphql_lab, public;

-- =========================================================
-- 1. ENUMERATIONS
-- =========================================================

CREATE TYPE operation_kind AS ENUM (
    'QUERY',
    'MUTATION',
    'SUBSCRIPTION'
);

CREATE TYPE graphql_type_kind AS ENUM (
    'SCALAR',
    'OBJECT',
    'INPUT_OBJECT',
    'ENUM',
    'INTERFACE',
    'UNION'
);

CREATE TYPE resolver_status AS ENUM (
    'ACTIVE',
    'DISABLED',
    'FAILED'
);

CREATE TYPE execution_status AS ENUM (
    'PENDING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED'
);

CREATE TYPE order_status AS ENUM (
    'CONFIRMED',
    'CANCELLED'
);

-- =========================================================
-- 2. DOMAIN TABLES
-- =========================================================

CREATE TABLE app_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role_name VARCHAR(30) NOT NULL
        CHECK (role_name IN ('CUSTOMER', 'ADMIN', 'VIEWER')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE product (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    price NUMERIC(12, 2) NOT NULL
        CHECK (price >= 0),
    stock INTEGER NOT NULL
        CHECK (stock >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE customer_order (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id BIGINT NOT NULL
        REFERENCES app_user(user_id),

    product_id BIGINT NOT NULL
        REFERENCES product(product_id),

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    unit_price NUMERIC(12, 2) NOT NULL
        CHECK (unit_price >= 0),

    status order_status NOT NULL DEFAULT 'CONFIRMED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_active
    ON product(product_id)
    WHERE active = TRUE;

CREATE INDEX idx_order_user_created
    ON customer_order(user_id, created_at DESC);

CREATE INDEX idx_order_product
    ON customer_order(product_id);

-- =========================================================
-- 3. GRAPHQL TYPE REGISTRY
-- =========================================================

CREATE TABLE graphql_type (
    type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    type_name VARCHAR(100) NOT NULL UNIQUE,

    type_kind graphql_type_kind NOT NULL,

    description TEXT,

    built_in BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO graphql_type (
    type_name,
    type_kind,
    description,
    built_in
)
VALUES
    ('String', 'SCALAR', 'UTF-8 textual value', TRUE),
    ('Int', 'SCALAR', 'Signed 32-bit integer', TRUE),
    ('Float', 'SCALAR', 'Floating-point number', TRUE),
    ('Boolean', 'SCALAR', 'Boolean value', TRUE),
    ('ID', 'SCALAR', 'Unique identifier', TRUE),
    ('User', 'OBJECT', 'Customer account object', FALSE),
    ('Product', 'OBJECT', 'Inventory product object', FALSE),
    ('Order', 'OBJECT', 'Customer order object', FALSE),
    ('Query', 'OBJECT', 'GraphQL query root', FALSE),
    ('Mutation', 'OBJECT', 'GraphQL mutation root', FALSE);

-- =========================================================
-- 4. GRAPHQL FIELD DEFINITIONS
-- =========================================================

CREATE TABLE graphql_field (
    field_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    parent_type_id BIGINT NOT NULL
        REFERENCES graphql_type(type_id),

    field_name VARCHAR(100) NOT NULL,

    return_type_id BIGINT NOT NULL
        REFERENCES graphql_type(type_id),

    is_list BOOLEAN NOT NULL DEFAULT FALSE,

    is_non_null BOOLEAN NOT NULL DEFAULT FALSE,

    description TEXT,

    UNIQUE(parent_type_id, field_name)
);

CREATE INDEX idx_graphql_field_parent
    ON graphql_field(parent_type_id);

-- =========================================================
-- 5. GRAPHQL FIELD ARGUMENTS
-- =========================================================

CREATE TABLE graphql_argument (
    argument_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    field_id BIGINT NOT NULL
        REFERENCES graphql_field(field_id)
        ON DELETE CASCADE,

    argument_name VARCHAR(100) NOT NULL,

    argument_type_id BIGINT NOT NULL
        REFERENCES graphql_type(type_id),

    is_required BOOLEAN NOT NULL DEFAULT FALSE,

    default_value JSONB,

    description TEXT,

    UNIQUE(field_id, argument_name),

    CHECK (
        NOT is_required OR default_value IS NULL
    )
);

-- =========================================================
-- 6. RESOLVER REGISTRY
-- =========================================================

CREATE TABLE resolver_registry (
    resolver_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    field_id BIGINT NOT NULL UNIQUE
        REFERENCES graphql_field(field_id)
        ON DELETE CASCADE,

    resolver_name VARCHAR(150) NOT NULL UNIQUE,

    resolver_module VARCHAR(255) NOT NULL,

    resolver_function VARCHAR(150) NOT NULL,

    status resolver_status NOT NULL DEFAULT 'ACTIVE',

    timeout_ms INTEGER NOT NULL DEFAULT 3000
        CHECK (timeout_ms BETWEEN 1 AND 60000),

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Resolver code is not stored as executable SQL.
-- The application resolves registered functions securely.

-- =========================================================
-- 7. GRAPHQL OPERATION REGISTRY
-- =========================================================

CREATE TABLE graphql_operation (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operation_name VARCHAR(150) NOT NULL UNIQUE,

    operation_type operation_kind NOT NULL,

    root_type_id BIGINT NOT NULL
        REFERENCES graphql_type(type_id),

    operation_document TEXT NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    max_depth INTEGER NOT NULL DEFAULT 5
        CHECK (max_depth BETWEEN 1 AND 50),

    max_complexity INTEGER NOT NULL DEFAULT 100
        CHECK (max_complexity BETWEEN 1 AND 10000),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 8. USERS, ROLES, AND PERMISSIONS
-- =========================================================

CREATE TABLE graphql_role (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE graphql_user_role (
    user_id BIGINT NOT NULL
        REFERENCES app_user(user_id)
        ON DELETE CASCADE,

    role_id BIGINT NOT NULL
        REFERENCES graphql_role(role_id)
        ON DELETE CASCADE,

    PRIMARY KEY(user_id, role_id)
);

CREATE TABLE graphql_field_permission (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    field_id BIGINT NOT NULL
        REFERENCES graphql_field(field_id)
        ON DELETE CASCADE,

    role_id BIGINT NOT NULL
        REFERENCES graphql_role(role_id)
        ON DELETE CASCADE,

    can_read BOOLEAN NOT NULL DEFAULT FALSE,

    can_write BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(field_id, role_id)
);

-- =========================================================
-- 9. GRAPHQL EXECUTION LOGS
-- =========================================================

CREATE TABLE graphql_execution (
    execution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id UUID NOT NULL UNIQUE,

    operation_id BIGINT
        REFERENCES graphql_operation(operation_id),

    user_id BIGINT
        REFERENCES app_user(user_id),

    operation_type operation_kind NOT NULL,

    status execution_status NOT NULL DEFAULT 'PENDING',

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    duration_ms NUMERIC(12, 3),

    complexity INTEGER
        CHECK (complexity IS NULL OR complexity >= 0),

    error_message TEXT,

    CHECK (
        (status = 'SUCCEEDED' AND completed_at IS NOT NULL)
        OR status <> 'SUCCEEDED'
    )
);

CREATE INDEX idx_execution_status_time
    ON graphql_execution(status, requested_at DESC);

CREATE INDEX idx_execution_user_time
    ON graphql_execution(user_id, requested_at DESC);

CREATE TABLE graphql_execution_field (
    execution_field_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    execution_id BIGINT NOT NULL
        REFERENCES graphql_execution(execution_id)
        ON DELETE CASCADE,

    field_id BIGINT
        REFERENCES graphql_field(field_id),

    field_path TEXT NOT NULL,

    resolver_duration_ms NUMERIC(12, 3),

    successful BOOLEAN NOT NULL,

    error_message TEXT,

    CHECK (
        successful = TRUE OR error_message IS NOT NULL
    )
);

-- =========================================================
-- 10. REVIEWABLE SCHEMA RELATIONSHIPS
-- =========================================================

INSERT INTO graphql_field (
    parent_type_id,
    field_name,
    return_type_id,
    is_list,
    is_non_null,
    description
)
SELECT parent.type_id,
       definitions.field_name,
       result.type_id,
       definitions.is_list,
       definitions.is_non_null,
       definitions.description
FROM (
    VALUES
        ('Query', 'users', 'User', TRUE, FALSE,
         'Retrieve customer accounts'),

        ('Query', 'user', 'User', FALSE, FALSE,
         'Retrieve one customer'),

        ('Query', 'products', 'Product', TRUE, FALSE,
         'Retrieve products'),

        ('Query', 'product', 'Product', FALSE, FALSE,
         'Retrieve one product'),

        ('Query', 'orders', 'Order', TRUE, FALSE,
         'Retrieve customer orders'),

        ('Mutation', 'createOrder', 'Order', FALSE, TRUE,
         'Create a customer order'),

        ('User', 'id', 'ID', FALSE, TRUE,
         'Unique user identifier'),

        ('User', 'name', 'String', FALSE, TRUE,
         'Customer name'),

        ('User', 'email', 'String', FALSE, TRUE,
         'Customer email'),

        ('Product', 'id', 'ID', FALSE, TRUE,
         'Product identifier'),

        ('Product', 'name', 'String', FALSE, TRUE,
         'Product name'),

        ('Product', 'price', 'Float', FALSE, TRUE,
         'Product price'),

        ('Product', 'stock', 'Int', FALSE, TRUE,
         'Available inventory'),

        ('Order', 'id', 'ID', FALSE, TRUE,
         'Order identifier'),

        ('Order', 'quantity', 'Int', FALSE, TRUE,
         'Ordered quantity'),

        ('Order', 'status', 'String', FALSE, TRUE,
         'Order state'),

        ('Order', 'user', 'User', FALSE, TRUE,
         'Associated customer'),

        ('Order', 'product', 'Product', FALSE, TRUE,
         'Associated product')
) AS definitions(
    parent_name,
    field_name,
    return_name,
    is_list,
    is_non_null,
    description
)
JOIN graphql_type parent
    ON parent.type_name = definitions.parent_name
JOIN graphql_type result
    ON result.type_name = definitions.return_name;

-- =========================================================
-- 11. ARGUMENT DEFINITIONS
-- =========================================================

INSERT INTO graphql_argument (
    field_id,
    argument_name,
    argument_type_id,
    is_required,
    description
)
SELECT f.field_id,
       args.argument_name,
       t.type_id,
       args.is_required,
       args.description
FROM (
    VALUES
        ('Query', 'user', 'id', 'ID', TRUE,
         'Customer identifier'),

        ('Query', 'product', 'id', 'ID', TRUE,
         'Product identifier'),

        ('Mutation', 'createOrder', 'userId', 'ID', TRUE,
         'Customer identifier'),

        ('Mutation', 'createOrder', 'productId', 'ID', TRUE,
         'Product identifier'),

        ('Mutation', 'createOrder', 'quantity', 'Int', TRUE,
         'Ordered quantity')
) AS args(
    parent_name,
    field_name,
    argument_name,
    argument_type,
    is_required,
    description
)
JOIN graphql_type parent
    ON parent.type_name = args.parent_name
JOIN graphql_field f
    ON f.parent_type_id = parent.type_id
   AND f.field_name = args.field_name
JOIN graphql_type t
    ON t.type_name = args.argument_type;

-- =========================================================
-- 12. RESOLVER REGISTRATION
-- =========================================================

INSERT INTO resolver_registry (
    field_id,
    resolver_name,
    resolver_module,
    resolver_function,
    timeout_ms,
    description
)
SELECT f.field_id,
       definitions.resolver_name,
       definitions.resolver_module,
       definitions.resolver_function,
       definitions.timeout_ms,
       definitions.description
FROM (
    VALUES
        ('Query', 'users', 'resolveUsers',
         'user_resolvers', 'get_users', 3000,
         'Returns user records'),

        ('Query', 'products', 'resolveProducts',
         'product_resolvers', 'get_products', 3000,
         'Returns active products'),

        ('Query', 'product', 'resolveProduct',
         'product_resolvers', 'get_product', 2000,
         'Returns one product'),

        ('Query', 'user', 'resolveUser',
         'user_resolvers', 'get_user', 2000,
         'Returns one user'),

        ('Query', 'orders', 'resolveOrders',
         'order_resolvers', 'get_orders', 3000,
         'Returns customer orders'),

        ('Mutation', 'createOrder', 'resolveCreateOrder',
         'order_resolvers', 'create_order', 5000,
         'Creates an order')
) AS definitions(
    parent_name,
    field_name,
    resolver_name,
    resolver_module,
    resolver_function,
    timeout_ms,
    description
)
JOIN graphql_type parent
    ON parent.type_name = definitions.parent_name
JOIN graphql_field f
    ON f.parent_type_id = parent.type_id
   AND f.field_name = definitions.field_name;

-- =========================================================
-- 13. ROLE AND PERMISSION CONFIGURATION
-- =========================================================

INSERT INTO graphql_role(role_name)
VALUES
    ('CUSTOMER'),
    ('ADMIN'),
    ('VIEWER');

INSERT INTO graphql_field_permission (
    field_id,
    role_id,
    can_read,
    can_write
)
SELECT f.field_id,
       r.role_id,
       CASE
           WHEN f.field_name = 'email'
                AND r.role_name = 'VIEWER'
               THEN FALSE
           ELSE TRUE
       END,
       CASE
           WHEN p.type_name = 'Mutation'
                AND r.role_name = 'CUSTOMER'
               THEN TRUE
           WHEN r.role_name = 'ADMIN'
               THEN TRUE
           ELSE FALSE
       END
FROM graphql_field f
JOIN graphql_type p
    ON p.type_id = f.parent_type_id
CROSS JOIN graphql_role r;

-- =========================================================
-- 14. OPERATION REGISTRATION
-- =========================================================

INSERT INTO graphql_operation (
    operation_name,
    operation_type,
    root_type_id,
    operation_document,
    max_depth,
    max_complexity
)
SELECT definitions.operation_name,
       definitions.operation_type::operation_kind,
       t.type_id,
       definitions.operation_document,
       definitions.max_depth,
       definitions.max_complexity
FROM (
    VALUES
        (
            'GetProducts',
            'QUERY',
            'Query',
            'query GetProducts { products { id name price stock } }',
            5,
            50
        ),
        (
            'GetProduct',
            'QUERY',
            'Query',
            'query GetProduct($id: ID!) { product(id: $id) { id name price } }',
            4,
            30
        ),
        (
            'CreateOrder',
            'MUTATION',
            'Mutation',
            'mutation CreateOrder($userId: ID!, $productId: ID!, $quantity: Int!) { createOrder(userId: $userId, productId: $productId, quantity: $quantity) { id status } }',
            5,
            50
        )
) AS definitions(
    operation_name,
    operation_type,
    root_name,
    operation_document,
    max_depth,
    max_complexity
)
JOIN graphql_type t
    ON t.type_name = definitions.root_name;

-- =========================================================
-- 15. DATABASE-LEVEL ORDER VALIDATION
-- =========================================================

CREATE OR REPLACE FUNCTION validate_order_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    available_stock INTEGER;
    current_price NUMERIC(12, 2);
BEGIN
    IF NEW.quantity <= 0 THEN
        RAISE EXCEPTION 'Order quantity must be positive';
    END IF;

    SELECT stock, price
    INTO available_stock, current_price
    FROM product
    WHERE product_id = NEW.product_id
      AND active = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product does not exist or is inactive';
    END IF;

    IF available_stock < NEW.quantity THEN
        RAISE EXCEPTION
            'Insufficient stock. Available: %, requested: %',
            available_stock,
            NEW.quantity;
    END IF;

    -- Capture the actual product price at order creation.
    NEW.unit_price := current_price;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_order_inventory
BEFORE INSERT ON customer_order
FOR EACH ROW
EXECUTE FUNCTION validate_order_inventory();

-- =========================================================
-- 16. ATOMIC INVENTORY UPDATE
-- =========================================================

CREATE OR REPLACE FUNCTION deduct_order_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE product
    SET stock = stock - NEW.quantity
    WHERE product_id = NEW.product_id
      AND stock >= NEW.quantity;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Inventory changed before order completion';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_deduct_order_inventory
AFTER INSERT ON customer_order
FOR EACH ROW
EXECUTE FUNCTION deduct_order_inventory();

-- =========================================================
-- 17. ORDER CANCELLATION AND STOCK RESTORATION
-- =========================================================

CREATE OR REPLACE FUNCTION restore_cancelled_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'CONFIRMED'
       AND NEW.status = 'CANCELLED' THEN

        UPDATE product
        SET stock = stock + OLD.quantity
        WHERE product_id = OLD.product_id;

    ELSIF OLD.status = 'CANCELLED'
       AND NEW.status = 'CONFIRMED' THEN

        UPDATE product
        SET stock = stock - NEW.quantity
        WHERE product_id = NEW.product_id
          AND stock >= NEW.quantity;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Cannot reactivate order: insufficient stock';
        END IF;

    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_restore_cancelled_inventory
AFTER UPDATE OF status ON customer_order
FOR EACH ROW
EXECUTE FUNCTION restore_cancelled_inventory();

-- =========================================================
-- 18. EXECUTION STATE VALIDATION
-- =========================================================

CREATE OR REPLACE FUNCTION validate_execution_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IN ('SUCCEEDED', 'FAILED')
       AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION
            'Terminal execution states cannot be changed';
    END IF;

    IF NEW.status IN ('SUCCEEDED', 'FAILED')
       AND NEW.completed_at IS NULL THEN
        NEW.completed_at := NOW();
    END IF;

    IF NEW.completed_at IS NOT NULL
       AND NEW.completed_at < NEW.requested_at THEN
        RAISE EXCEPTION
            'Completion cannot precede request time';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_execution_transition
BEFORE UPDATE ON graphql_execution
FOR EACH ROW
EXECUTE FUNCTION validate_execution_transition();

-- =========================================================
-- 19. SCHEMA INSPECTION VIEW
-- =========================================================

CREATE OR REPLACE VIEW graphql_schema_catalog AS
SELECT
    parent.type_name AS parent_type,
    f.field_name,
    result.type_name AS return_type,
    f.is_list,
    f.is_non_null,
    f.description,
    rr.resolver_name,
    rr.status AS resolver_status,
    rr.timeout_ms
FROM graphql_field f
JOIN graphql_type parent
    ON parent.type_id = f.parent_type_id
JOIN graphql_type result
    ON result.type_id = f.return_type_id
LEFT JOIN resolver_registry rr
    ON rr.field_id = f.field_id;

-- =========================================================
-- 20. ARGUMENT INSPECTION VIEW
-- =========================================================

CREATE OR REPLACE VIEW graphql_argument_catalog AS
SELECT
    parent.type_name AS parent_type,
    f.field_name,
    a.argument_name,
    t.type_name AS argument_type,
    a.is_required,
    a.default_value
FROM graphql_argument a
JOIN graphql_field f
    ON f.field_id = a.field_id
JOIN graphql_type parent
    ON parent.type_id = f.parent_type_id
JOIN graphql_type t
    ON t.type_id = a.argument_type_id;

-- =========================================================
-- 21. QUERY COMPLEXITY EVALUATION
-- =========================================================

CREATE OR REPLACE FUNCTION check_operation_eligibility(
    p_operation_id BIGINT,
    p_requested_depth INTEGER,
    p_requested_complexity INTEGER
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    configured_depth INTEGER;
    configured_complexity INTEGER;
    operation_enabled BOOLEAN;
BEGIN
    SELECT
        max_depth,
        max_complexity,
        enabled
    INTO
        configured_depth,
        configured_complexity,
        operation_enabled
    FROM graphql_operation
    WHERE operation_id = p_operation_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Operation does not exist';
        RETURN;
    END IF;

    IF NOT operation_enabled THEN
        RETURN QUERY
        SELECT FALSE, 'Operation is disabled';
        RETURN;
    END IF;

    IF p_requested_depth < 0
       OR p_requested_complexity < 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Depth and complexity must be non-negative';
        RETURN;
    END IF;

    IF p_requested_depth > configured_depth THEN
        RETURN QUERY
        SELECT FALSE, 'Maximum depth exceeded';
        RETURN;
    END IF;

    IF p_requested_complexity > configured_complexity THEN
        RETURN QUERY
        SELECT FALSE, 'Maximum complexity exceeded';
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'Operation is eligible';
END;
$$;

-- =========================================================
-- 22. EXECUTION REPORTING VIEW
-- =========================================================

CREATE OR REPLACE VIEW graphql_execution_report AS
SELECT
    e.execution_id,
    e.request_id,
    e.operation_type,
    o.operation_name,
    u.full_name AS requested_by,
    e.status,
    e.requested_at,
    e.completed_at,
    e.duration_ms,
    e.complexity,
    e.error_message
FROM graphql_execution e
LEFT JOIN graphql_operation o
    ON o.operation_id = e.operation_id
LEFT JOIN app_user u
    ON u.user_id = e.user_id;

-- =========================================================
-- 23. SAMPLE BUSINESS RECORDS
-- =========================================================

INSERT INTO app_user (
    full_name,
    email,
    role_name
)
VALUES
    ('Aarav Sharma', 'aarav@example.com', 'CUSTOMER'),
    ('Meera Singh', 'meera@example.com', 'CUSTOMER'),
    ('System Administrator', 'admin@example.com', 'ADMIN');

INSERT INTO product (
    product_name,
    price,
    stock
)
VALUES
    ('Laptop', 75000.00, 8),
    ('Keyboard', 2500.00, 20),
    ('Monitor', 18000.00, 5);

INSERT INTO graphql_user_role(user_id, role_id)
SELECT u.user_id, r.role_id
FROM app_user u
JOIN graphql_role r
    ON r.role_name = u.role_name;

-- =========================================================
-- 24. SAMPLE EXECUTION RECORDS
-- =========================================================

INSERT INTO graphql_execution (
    request_id,
    operation_id,
    user_id,
    operation_type,
    status,
    completed_at,
    duration_ms,
    complexity
)
SELECT
    '11111111-1111-4111-8111-111111111111'::UUID,
    o.operation_id,
    u.user_id,
    'QUERY',
    'SUCCEEDED',
    NOW(),
    12.50,
    15
FROM graphql_operation o
JOIN app_user u
    ON u.email = 'aarav@example.com'
WHERE o.operation_name = 'GetProducts';

INSERT INTO graphql_execution (
    request_id,
    operation_id,
    user_id,
    operation_type,
    status,
    completed_at,
    duration_ms,
    complexity,
    error_message
)
SELECT
    '22222222-2222-4222-8222-222222222222'::UUID,
    o.operation_id,
    u.user_id,
    'MUTATION',
    'FAILED',
    NOW(),
    4.25,
    10,
    'Insufficient inventory'
FROM graphql_operation o
JOIN app_user u
    ON u.email = 'aarav@example.com'
WHERE o.operation_name = 'CreateOrder';

-- =========================================================
-- 25. STORED PROCEDURE FOR ORDER CREATION
-- =========================================================

CREATE OR REPLACE PROCEDURE create_customer_order(
    IN p_user_id BIGINT,
    IN p_product_id BIGINT,
    IN p_quantity INTEGER,
    OUT p_order_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_price NUMERIC(12, 2);
BEGIN
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Quantity must be positive';
    END IF;

    SELECT price
    INTO current_price
    FROM product
    WHERE product_id = p_product_id
      AND active = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product does not exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_user
        WHERE user_id = p_user_id
          AND active = TRUE
    ) THEN
        RAISE EXCEPTION 'User does not exist or is inactive';
    END IF;

    INSERT INTO customer_order (
        user_id,
        product_id,
        quantity,
        unit_price
    )
    VALUES (
        p_user_id,
        p_product_id,
        p_quantity,
        current_price
    )
    RETURNING order_id INTO p_order_id;
END;
$$;

-- =========================================================
-- 26. TRANSACTIONAL WORKFLOW
-- =========================================================

-- This transaction demonstrates a successful mutation.
DO $$
DECLARE
    created_order_id BIGINT;
BEGIN
    CALL create_customer_order(
        1,
        2,
        2,
        created_order_id
    );

    RAISE NOTICE 'Created order: %', created_order_id;
END;
$$;

-- =========================================================
-- 27. RETRIEVAL QUERIES
-- =========================================================

-- Inspect registered object types and fields.
SELECT *
FROM graphql_schema_catalog
ORDER BY parent_type, field_name;

-- Inspect field arguments and required parameters.
SELECT *
FROM graphql_argument_catalog
ORDER BY parent_type, field_name, argument_name;

-- Retrieve products.
SELECT
    product_id,
    product_name,
    price,
    stock
FROM product
WHERE active = TRUE
ORDER BY product_name;

-- Retrieve a customer's orders.
SELECT
    o.order_id,
    u.full_name,
    p.product_name,
    o.quantity,
    o.unit_price,
    o.status,
    o.created_at
FROM customer_order o
JOIN app_user u
    ON u.user_id = o.user_id
JOIN product p
    ON p.product_id = o.product_id
WHERE u.email = 'aarav@example.com'
ORDER BY o.created_at DESC;

-- =========================================================
-- 28. VALIDATION QUERIES
-- =========================================================

-- Find fields without active resolvers.
SELECT
    parent.type_name,
    f.field_name
FROM graphql_field f
JOIN graphql_type parent
    ON parent.type_id = f.parent_type_id
LEFT JOIN resolver_registry rr
    ON rr.field_id = f.field_id
WHERE rr.resolver_id IS NULL
   OR rr.status <> 'ACTIVE';

-- Find arguments with inconsistent required/default settings.
SELECT
    argument_name,
    is_required,
    default_value
FROM graphql_argument
WHERE is_required = TRUE
  AND default_value IS NOT NULL;

-- Detect fields with missing permissions.
SELECT
    parent.type_name,
    f.field_name
FROM graphql_field f
JOIN graphql_type parent
    ON parent.type_id = f.parent_type_id
LEFT JOIN graphql_field_permission permission
    ON permission.field_id = f.field_id
WHERE permission.permission_id IS NULL;

-- =========================================================
-- 29. ELIGIBILITY DETERMINATION
-- =========================================================

SELECT
    operation_name,
    eligibility.eligible,
    eligibility.reason
FROM graphql_operation operation
CROSS JOIN LATERAL check_operation_eligibility(
    operation.operation_id,
    3,
    20
) AS eligibility
ORDER BY operation_name;

-- =========================================================
-- 30. AGGREGATION AND PERFORMANCE REPORTING
-- =========================================================

SELECT
    operation_type,
    status,
    COUNT(*) AS execution_count,
    ROUND(AVG(duration_ms), 3) AS average_duration_ms,
    MAX(duration_ms) AS maximum_duration_ms,
    AVG(complexity) AS average_complexity
FROM graphql_execution
GROUP BY operation_type, status
ORDER BY operation_type, status;

-- Resolver-level failures.
SELECT
    field_path,
    COUNT(*) AS failure_count
FROM graphql_execution_field
WHERE successful = FALSE
GROUP BY field_path
ORDER BY failure_count DESC;

-- Role-based field permission report.
SELECT
    r.role_name,
    COUNT(*) FILTER (WHERE p.can_read) AS readable_fields,
    COUNT(*) FILTER (WHERE p.can_write) AS writable_fields
FROM graphql_role r
LEFT JOIN graphql_field_permission p
    ON p.role_id = r.role_id
GROUP BY r.role_name
ORDER BY r.role_name;

-- =========================================================
-- 31. CTE-BASED OPERATION HEALTH REPORT
-- =========================================================

WITH operation_metrics AS (
    SELECT
        o.operation_name,
        COUNT(e.execution_id) AS total_requests,
        COUNT(*) FILTER (
            WHERE e.status = 'SUCCEEDED'
        ) AS successful_requests,
        COUNT(*) FILTER (
            WHERE e.status = 'FAILED'
        ) AS failed_requests,
        AVG(e.duration_ms) AS average_duration
    FROM graphql_operation o
    LEFT JOIN graphql_execution e
        ON e.operation_id = o.operation_id
    GROUP BY o.operation_id, o.operation_name
)
SELECT
    operation_name,
    total_requests,
    successful_requests,
    failed_requests,
    ROUND(
        100.0 * successful_requests /
        NULLIF(total_requests, 0),
        2
    ) AS success_percentage,
    ROUND(average_duration, 3) AS average_duration_ms
FROM operation_metrics
ORDER BY total_requests DESC, operation_name;

-- =========================================================
-- 32. MUTATION FAILURE TEST
-- =========================================================

-- The exception is caught inside a subtransaction.
-- The failed order does not deduct inventory.

DO $$
DECLARE
    failed_order_id BIGINT;
BEGIN
    BEGIN
        CALL create_customer_order(
            1,
            1,
            100000,
            failed_order_id
        );

    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected mutation failure: %',
                SQLERRM;
    END;
END;
$$;

-- =========================================================
-- 33. CANCELLATION WORKFLOW
-- =========================================================

-- Restore inventory when a confirmed order is cancelled.
UPDATE customer_order
SET status = 'CANCELLED'
WHERE order_id = (
    SELECT MIN(order_id)
    FROM customer_order
    WHERE status = 'CONFIRMED'
);

-- =========================================================
-- 34. FINAL STATE INSPECTION
-- =========================================================

SELECT
    p.product_name,
    p.stock,
    COUNT(o.order_id) FILTER (
        WHERE o.status = 'CONFIRMED'
    ) AS confirmed_orders
FROM product p
LEFT JOIN customer_order o
    ON o.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.stock
ORDER BY p.product_name;

SELECT *
FROM graphql_execution_report
ORDER BY requested_at DESC;

COMMIT;

-- =========================================================
-- 35. OPERATIONAL NOTES
-- =========================================================

-- 1. GraphQL parsing and validation belong to the application.
-- 2. Resolver registration maps schema fields to application functions.
-- 3. PostgreSQL constraints enforce persistent data integrity.
-- 4. Database transactions protect multi-step mutations.
-- 5. Resolver authorization must be checked at execution time.
-- 6. Query depth and complexity must be calculated from the
--    actual parsed selection tree, not trusted client input.
-- 7. Production systems should retain execution logs under an
--    explicit retention and access-control policy.
-- =========================================================

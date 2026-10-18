DROP SCHEMA IF EXISTS service_layer_demo CASCADE;

CREATE SCHEMA service_layer_demo;

SET search_path TO service_layer_demo;

-- The relational model mirrors architectural boundaries:
-- domain entities become tables, repositories become persistence operations,
-- while service-layer rules are reinforced with database constraints.

CREATE TYPE order_status AS ENUM (
    'draft',
    'confirmed',
    'cancelled'
);

CREATE TABLE customers (
    customer_id BIGSERIAL PRIMARY KEY,
    customer_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id BIGSERIAL PRIMARY KEY,
    product_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    price_cents BIGINT NOT NULL CHECK (price_cents >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    status order_status NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    CHECK (
        (status = 'draft' AND confirmed_at IS NULL AND cancelled_at IS NULL)
        OR
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND cancelled_at IS NULL)
        OR
        (status = 'cancelled' AND cancelled_at IS NOT NULL)
    )
);

CREATE TABLE order_lines (
    order_line_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,
    product_id BIGINT NOT NULL
        REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents BIGINT NOT NULL CHECK (unit_price_cents >= 0),
    UNIQUE (order_id, product_id)
);

-- Repository queries frequently retrieve aggregate state by foreign key.
CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

CREATE INDEX idx_order_lines_order_id
    ON order_lines(order_id);

CREATE INDEX idx_products_active
    ON products(product_id)
    WHERE active = TRUE;

INSERT INTO customers (customer_code, name)
VALUES
    ('CUST-001', 'Enterprise Customer'),
    ('CUST-002', 'Research Customer');

INSERT INTO products (
    product_code,
    name,
    price_cents,
    active
)
VALUES
    ('P-KEYBOARD', 'Mechanical Keyboard', 8500, TRUE),
    ('P-DOCK', 'USB-C Dock', 12000, TRUE),
    ('P-LEGACY', 'Legacy Adapter', 2500, FALSE);

-- A service would normally create this aggregate inside a transaction.
BEGIN;

INSERT INTO orders (customer_id)
SELECT customer_id
FROM customers
WHERE customer_code = 'CUST-001';

INSERT INTO order_lines (
    order_id,
    product_id,
    quantity,
    unit_price_cents
)
SELECT
    o.order_id,
    p.product_id,
    2,
    p.price_cents
FROM orders o
JOIN customers c
    ON c.customer_id = o.customer_id
JOIN products p
    ON p.product_code = 'P-KEYBOARD'
WHERE c.customer_code = 'CUST-001'
  AND o.status = 'draft'
  AND p.active = TRUE;

COMMIT;

-- A database view can provide a read model without moving domain calculations
-- into the controller.
CREATE VIEW order_totals AS
SELECT
    o.order_id,
    c.customer_code,
    o.status,
    COALESCE(
        SUM(
            ol.quantity::BIGINT * ol.unit_price_cents
        ),
        0
    ) AS total_cents,
    COUNT(ol.order_line_id) AS line_count
FROM orders o
JOIN customers c
    ON c.customer_id = o.customer_id
LEFT JOIN order_lines ol
    ON ol.order_id = o.order_id
GROUP BY
    o.order_id,
    c.customer_code,
    o.status;

-- Service-oriented read query.
SELECT
    order_id,
    customer_code,
    status,
    total_cents,
    line_count
FROM order_totals
ORDER BY order_id;

-- PostgreSQL trigger logic prevents a confirmed or cancelled aggregate
-- from being modified through direct persistence operations.
CREATE OR REPLACE FUNCTION prevent_non_draft_line_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_status order_status;
BEGIN
    SELECT status
    INTO current_status
    FROM orders
    WHERE order_id = COALESCE(NEW.order_id, OLD.order_id);

    IF current_status <> 'draft' THEN
        RAISE EXCEPTION
            'Order % cannot have line changes while status is %',
            COALESCE(NEW.order_id, OLD.order_id),
            current_status;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER trg_protect_order_lines
BEFORE INSERT OR UPDATE OR DELETE
ON order_lines
FOR EACH ROW
EXECUTE FUNCTION prevent_non_draft_line_changes();

-- The following function represents a persistence-level state transition.
-- Application services remain responsible for orchestration, while the
-- database protects the aggregate from an invalid persisted state.
CREATE OR REPLACE FUNCTION confirm_order(
    requested_order_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_status order_status;
    current_line_count BIGINT;
BEGIN
    SELECT status
    INTO current_status
    FROM orders
    WHERE order_id = requested_order_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Order % does not exist',
            requested_order_id;
    END IF;

    IF current_status <> 'draft' THEN
        RAISE EXCEPTION
            'Only draft orders can be confirmed';
    END IF;

    SELECT COUNT(*)
    INTO current_line_count
    FROM order_lines
    WHERE order_id = requested_order_id;

    IF current_line_count = 0 THEN
        RAISE EXCEPTION
            'Order % cannot be confirmed without lines',
            requested_order_id;
    END IF;

    UPDATE orders
    SET
        status = 'confirmed',
        confirmed_at = CURRENT_TIMESTAMP
    WHERE order_id = requested_order_id;
END;
$$;

-- Discover the draft order created above.
SELECT order_id
FROM orders
WHERE customer_id = (
    SELECT customer_id
    FROM customers
    WHERE customer_code = 'CUST-001'
)
ORDER BY order_id
LIMIT 1;

-- Confirm the first demonstration order.
SELECT confirm_order(
    (
        SELECT MIN(order_id)
        FROM orders
        WHERE customer_id = (
            SELECT customer_id
            FROM customers
            WHERE customer_code = 'CUST-001'
        )
    )
);

-- The service/read layer can now retrieve the aggregate's final state.
SELECT *
FROM order_totals
ORDER BY order_id;

-- This query exposes active products only, matching the repository's
-- find-active behavior.
SELECT
    product_id,
    product_code,
    name,
    price_cents
FROM products
WHERE active = TRUE
ORDER BY product_code;

-- The unique constraint below demonstrates a persistence-level invariant:
-- the same product cannot be inserted twice into one order.
--
-- An attempted duplicate would fail with a unique-constraint violation.
SELECT
    order_id,
    product_id,
    quantity,
    unit_price_cents
FROM order_lines
ORDER BY order_id, order_line_id;

-- A service-layer read can identify aggregates requiring attention without
-- embedding transport or presentation concerns into the database.
SELECT
    ot.order_id,
    ot.customer_code,
    ot.status,
    ot.total_cents,
    ot.line_count
FROM order_totals ot
WHERE ot.status = 'draft'
ORDER BY ot.order_id;

-- ORM Fundamentals
-- PostgreSQL-compatible relational model for a procurement domain.
--
-- The schema deliberately exposes the relational structures that an ORM would
-- map into application models. Foreign keys represent relationships, while
-- constraints enforce invariants that should not depend only on application
-- validation.

DROP SCHEMA IF EXISTS orm_fundamentals CASCADE;
CREATE SCHEMA orm_fundamentals;
SET search_path TO orm_fundamentals;

CREATE TABLE suppliers (
    supplier_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_code VARCHAR(30) NOT NULL UNIQUE,
    supplier_name VARCHAR(200) NOT NULL,
    tax_identifier VARCHAR(40) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(200) NOT NULL,
    unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE purchase_orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_id BIGINT NOT NULL,
    order_status VARCHAR(20) NOT NULL
        CHECK (
            order_status IN (
                'DRAFT',
                'SUBMITTED',
                'APPROVED',
                'FULFILLED',
                'CANCELLED'
            )
        ),
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMPTZ,
    CONSTRAINT fk_order_supplier
        FOREIGN KEY (supplier_id)
        REFERENCES suppliers(supplier_id)
);

CREATE TABLE purchase_order_lines (
    order_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
    CONSTRAINT fk_line_order
        FOREIGN KEY (order_id)
        REFERENCES purchase_orders(order_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_line_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id),
    CONSTRAINT uq_order_product
        UNIQUE (order_id, product_id)
);

CREATE INDEX idx_purchase_orders_supplier
    ON purchase_orders(supplier_id);

CREATE INDEX idx_purchase_orders_status
    ON purchase_orders(order_status);

CREATE INDEX idx_order_lines_order
    ON purchase_order_lines(order_id);

CREATE INDEX idx_order_lines_product
    ON purchase_order_lines(product_id);

CREATE VIEW order_totals AS
SELECT
    po.order_id,
    po.supplier_id,
    po.order_status,
    COALESCE(
        SUM(pol.quantity * pol.unit_price),
        0
    ) AS order_total
FROM purchase_orders po
LEFT JOIN purchase_order_lines pol
    ON pol.order_id = po.order_id
GROUP BY
    po.order_id,
    po.supplier_id,
    po.order_status;

CREATE OR REPLACE FUNCTION validate_order_status_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.order_status = 'DRAFT'
       AND NEW.order_status NOT IN ('DRAFT', 'SUBMITTED', 'CANCELLED') THEN
        RAISE EXCEPTION
            'Invalid transition from DRAFT to %',
            NEW.order_status;
    END IF;

    IF OLD.order_status = 'SUBMITTED'
       AND NEW.order_status NOT IN ('SUBMITTED', 'APPROVED', 'CANCELLED') THEN
        RAISE EXCEPTION
            'Invalid transition from SUBMITTED to %',
            NEW.order_status;
    END IF;

    IF OLD.order_status = 'APPROVED'
       AND NEW.order_status NOT IN ('APPROVED', 'FULFILLED', 'CANCELLED') THEN
        RAISE EXCEPTION
            'Invalid transition from APPROVED to %',
            NEW.order_status;
    END IF;

    IF OLD.order_status IN ('FULFILLED', 'CANCELLED')
       AND NEW.order_status <> OLD.order_status THEN
        RAISE EXCEPTION
            'Terminal order state % cannot be changed',
            OLD.order_status;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_order_status
BEFORE UPDATE OF order_status
ON purchase_orders
FOR EACH ROW
EXECUTE FUNCTION validate_order_status_transition();

INSERT INTO suppliers (
    supplier_code,
    supplier_name,
    tax_identifier
)
VALUES
    (
        'SUP-001',
        'Industrial Components Ltd.',
        'GSTIN-29ABCDE1234F1Z5'
    ),
    (
        'SUP-002',
        'Northstar Technology Services',
        'GSTIN-09XYZDE5678G2Z6'
    );

INSERT INTO products (
    sku,
    product_name,
    unit_price
)
VALUES
    ('SRV-001', 'Application Server', 125000.00),
    ('MON-002', 'Operations Monitor', 18000.00),
    ('NET-003', 'Managed Network Switch', 42000.00);

BEGIN;

INSERT INTO purchase_orders (
    supplier_id,
    order_status
)
SELECT
    supplier_id,
    'DRAFT'
FROM suppliers
WHERE supplier_code = 'SUP-001';

INSERT INTO purchase_order_lines (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    po.order_id,
    p.product_id,
    4,
    p.unit_price
FROM purchase_orders po
JOIN suppliers s
    ON s.supplier_id = po.supplier_id
JOIN products p
    ON p.sku = 'SRV-001'
WHERE s.supplier_code = 'SUP-001'
  AND po.order_status = 'DRAFT';

INSERT INTO purchase_order_lines (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    po.order_id,
    p.product_id,
    8,
    p.unit_price
FROM purchase_orders po
JOIN suppliers s
    ON s.supplier_id = po.supplier_id
JOIN products p
    ON p.sku = 'MON-002'
WHERE s.supplier_code = 'SUP-001'
  AND po.order_status = 'DRAFT';

COMMIT;

UPDATE purchase_orders
SET order_status = 'SUBMITTED'
WHERE order_id = 1;

UPDATE purchase_orders
SET
    order_status = 'APPROVED',
    approved_at = CURRENT_TIMESTAMP
WHERE order_id = 1;

SELECT
    po.order_id,
    s.supplier_name,
    po.order_status,
    p.product_name,
    pol.quantity,
    pol.unit_price,
    pol.quantity * pol.unit_price AS line_total
FROM purchase_orders po
JOIN suppliers s
    ON s.supplier_id = po.supplier_id
JOIN purchase_order_lines pol
    ON pol.order_id = po.order_id
JOIN products p
    ON p.product_id = pol.product_id
WHERE po.order_id = 1
ORDER BY pol.order_line_id;

SELECT
    ot.order_id,
    s.supplier_name,
    ot.order_status,
    ot.order_total
FROM order_totals ot
JOIN suppliers s
    ON s.supplier_id = ot.supplier_id
ORDER BY ot.order_id;

SELECT
    p.sku,
    p.product_name,
    COUNT(pol.order_line_id) AS order_count,
    COALESCE(
        SUM(pol.quantity),
        0
    ) AS units_ordered,
    COALESCE(
        SUM(pol.quantity * pol.unit_price),
        0
    ) AS procurement_value
FROM products p
LEFT JOIN purchase_order_lines pol
    ON pol.product_id = p.product_id
GROUP BY
    p.product_id,
    p.sku,
    p.product_name
ORDER BY procurement_value DESC;

-- The following transaction demonstrates database-level protection against
-- an invalid state transition. The trigger rejects APPROVED -> DRAFT.
BEGIN;

UPDATE purchase_orders
SET order_status = 'DRAFT'
WHERE order_id = 1;

ROLLBACK;

-- A foreign-key lookup demonstrates that a purchase line cannot reference a
-- product that does not exist. The statement is intentionally wrapped in a
-- transaction so the demonstration does not corrupt the database.
BEGIN;

INSERT INTO purchase_order_lines (
    order_id,
    product_id,
    quantity,
    unit_price
)
VALUES (
    1,
    999999,
    1,
    100.00
);

ROLLBACK;

-- The relational model separates entities into normalized tables.
-- An ORM can map these rows into Supplier, Product, PurchaseOrder, and
-- PurchaseLine objects, while joins and aggregation remain relational
-- operations performed efficiently by the database engine.

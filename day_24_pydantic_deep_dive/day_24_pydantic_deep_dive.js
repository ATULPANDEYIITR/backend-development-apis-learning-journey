/*
Pydantic Deep Dive Companion
============================

Pydantic is a Python library, so JavaScript cannot execute Pydantic itself.
This file demonstrates the same validation architecture in JavaScript:
schemas, nested data, constraints, transformations, cross-field rules,
structured errors, serialization, strictness, and JSON-Schema-like
descriptions.

The implementation deliberately uses only standard JavaScript so it can run
with:

    node pydantic_deep_dive.js

The examples show how a frontend or JavaScript service can validate data
before sending it to a Python/Pydantic API.
*/

"use strict";


// ---------------------------------------------------------------------------
// 1. Basic validation result
// ---------------------------------------------------------------------------

function validationSuccess(value) {
    return { success: true, value, errors: [] };
}

function validationFailure(errors) {
    return { success: false, value: undefined, errors };
}

function addError(errors, path, message, type) {
    errors.push({
        path,
        message,
        type,
    });
}


// ---------------------------------------------------------------------------
// 2. Primitive validators
// ---------------------------------------------------------------------------

function requireString(value, path, errors, options = {}) {
    if (typeof value !== "string") {
        addError(errors, path, "Expected a string", "string_type");
        return null;
    }

    let result = options.trim === false ? value : value.trim();

    if (options.minLength !== undefined && result.length < options.minLength) {
        addError(
            errors,
            path,
            `String must contain at least ${options.minLength} characters`,
            "string_too_short",
        );
    }

    if (options.maxLength !== undefined && result.length > options.maxLength) {
        addError(
            errors,
            path,
            `String must contain at most ${options.maxLength} characters`,
            "string_too_long",
        );
    }

    if (options.pattern && !options.pattern.test(result)) {
        addError(errors, path, "String does not match the required pattern", "string_pattern");
    }

    return result;
}

function requireNumber(value, path, errors, options = {}) {
    if (typeof value !== "number" || Number.isNaN(value)) {
        addError(errors, path, "Expected a number", "number_type");
        return null;
    }

    if (options.gt !== undefined && !(value > options.gt)) {
        addError(errors, path, `Value must be greater than ${options.gt}`, "greater_than");
    }

    if (options.ge !== undefined && !(value >= options.ge)) {
        addError(errors, path, `Value must be at least ${options.ge}`, "greater_than_equal");
    }

    if (options.lt !== undefined && !(value < options.lt)) {
        addError(errors, path, `Value must be less than ${options.lt}`, "less_than");
    }

    if (options.le !== undefined && !(value <= options.le)) {
        addError(errors, path, `Value must be at most ${options.le}`, "less_than_equal");
    }

    return value;
}

function requireInteger(value, path, errors, options = {}) {
    if (!Number.isInteger(value)) {
        addError(errors, path, "Expected an integer", "int_type");
        return null;
    }

    return requireNumber(value, path, errors, options);
}

function requireArray(value, path, errors, options = {}) {
    if (!Array.isArray(value)) {
        addError(errors, path, "Expected an array", "list_type");
        return null;
    }

    if (options.minLength !== undefined && value.length < options.minLength) {
        addError(errors, path, `Array must contain at least ${options.minLength} items`, "too_short");
    }

    if (options.maxLength !== undefined && value.length > options.maxLength) {
        addError(errors, path, `Array must contain at most ${options.maxLength} items`, "too_long");
    }

    return value;
}


// ---------------------------------------------------------------------------
// 3. BaseModel-like class
// ---------------------------------------------------------------------------

class ValidationModel {
    constructor(data) {
        const result = this.validate(data);

        if (!result.success) {
            const error = new Error("Validation failed");
            error.name = "ValidationError";
            error.errors = result.errors;
            throw error;
        }

        Object.assign(this, result.value);
    }

    static validate() {
        throw new Error("Subclass must implement validate()");
    }

    toJSON() {
        return { ...this };
    }
}


// ---------------------------------------------------------------------------
// 4. Simple model
// ---------------------------------------------------------------------------

class User extends ValidationModel {
    static validate(data) {
        const errors = [];

        if (data === null || typeof data !== "object" || Array.isArray(data)) {
            return validationFailure([
                {
                    path: [],
                    message: "Expected an object",
                    type: "model_type",
                },
            ]);
        }

        const name = requireString(data.name, ["name"], errors, {
            minLength: 1,
            maxLength: 100,
        });

        const age = requireInteger(data.age, ["age"], errors, {
            ge: 0,
            le: 150,
        });

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({ name, age });
    }
}

console.log("Basic user:");
console.log(new User({ name: "Atul", age: 30 }));

try {
    new User({ name: "", age: -5 });
} catch (error) {
    console.log(error.errors);
}


// ---------------------------------------------------------------------------
// 5. Field-like constraints
// ---------------------------------------------------------------------------

class Product extends ValidationModel {
    static validate(data) {
        const errors = [];

        const productId = requireInteger(data.productId, ["productId"], errors, {
            gt: 0,
        });

        const name = requireString(data.name, ["name"], errors, {
            minLength: 2,
            maxLength: 100,
        });

        const price = requireNumber(data.price, ["price"], errors, {
            gt: 0,
        });

        const stock = requireInteger(data.stock, ["stock"], errors, {
            ge: 0,
        });

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            productId,
            name,
            price,
            stock,
        });
    }
}

console.log(
    new Product({
        productId: 101,
        name: "Keyboard",
        price: 4999.99,
        stock: 25,
    }),
);


// ---------------------------------------------------------------------------
// 6. Transform-before-validation behavior
// ---------------------------------------------------------------------------

function normalizeUsername(value) {
    return value.trim().toLowerCase();
}

function normalizeEmail(value) {
    return value.trim().toLowerCase();
}

class RegistrationRequest extends ValidationModel {
    static validate(data) {
        const errors = [];

        let username = requireString(data.username, ["username"], errors, {
            minLength: 3,
            maxLength: 30,
        });

        let email = requireString(data.email, ["email"], errors, {
            minLength: 5,
            maxLength: 254,
        });

        const password = requireString(data.password, ["password"], errors, {
            minLength: 12,
        });

        if (username !== null) {
            username = normalizeUsername(username);

            if (/\s/.test(username)) {
                addError(
                    errors,
                    ["username"],
                    "Username cannot contain spaces",
                    "username_format",
                );
            }
        }

        if (email !== null) {
            email = normalizeEmail(email);

            if (email.split("@").length !== 2) {
                addError(
                    errors,
                    ["email"],
                    "Email must contain exactly one @",
                    "email_format",
                );
            }
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            username,
            email,
            password,
        });
    }
}

console.log(
    new RegistrationRequest({
        username: "  AtulPandey  ",
        email: " ATUL@EXAMPLE.COM ",
        password: "secure-password-2026",
    }),
);


// ---------------------------------------------------------------------------
// 7. Nested models
// ---------------------------------------------------------------------------

class Address extends ValidationModel {
    static validate(data) {
        const errors = [];

        const street = requireString(data.street, ["street"], errors, {
            minLength: 5,
            maxLength: 120,
        });

        const city = requireString(data.city, ["city"], errors, {
            minLength: 2,
            maxLength: 60,
        });

        const postalCode = requireString(data.postalCode, ["postalCode"], errors, {
            pattern: /^\d{6}$/,
        });

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            street,
            city,
            postalCode,
        });
    }
}

class Customer extends ValidationModel {
    static validate(data) {
        const errors = [];

        const customerId = requireInteger(
            data.customerId,
            ["customerId"],
            errors,
            { gt: 0 },
        );

        const name = requireString(data.name, ["name"], errors, {
            minLength: 2,
        });

        let address = null;

        try {
            address = new Address(data.address);
        } catch (error) {
            for (const nestedError of error.errors) {
                addError(
                    errors,
                    ["address", ...nestedError.path],
                    nestedError.message,
                    nestedError.type,
                );
            }
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            customerId,
            name,
            address,
        });
    }
}


// ---------------------------------------------------------------------------
// 8. Lists of nested models and computed fields
// ---------------------------------------------------------------------------

class LineItem extends ValidationModel {
    static validate(data) {
        const errors = [];

        const sku = requireString(data.sku, ["sku"], errors, {
            minLength: 1,
            maxLength: 50,
        });

        const quantity = requireInteger(
            data.quantity,
            ["quantity"],
            errors,
            { gt: 0, le: 10000 },
        );

        const unitPrice = requireNumber(
            data.unitPrice,
            ["unitPrice"],
            errors,
            { gt: 0 },
        );

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            sku,
            quantity,
            unitPrice,
        });
    }

    get lineTotal() {
        return this.quantity * this.unitPrice;
    }
}

class ShoppingOrder extends ValidationModel {
    static validate(data) {
        const errors = [];

        const orderId = requireString(data.orderId, ["orderId"], errors, {
            minLength: 3,
            maxLength: 50,
        });

        let customer = null;

        try {
            customer = new Customer(data.customer);
        } catch (error) {
            for (const nestedError of error.errors) {
                addError(
                    errors,
                    ["customer", ...nestedError.path],
                    nestedError.message,
                    nestedError.type,
                );
            }
        }

        const rawItems = requireArray(
            data.items,
            ["items"],
            errors,
            { minLength: 1, maxLength: 100 },
        );

        const items = [];

        if (rawItems !== null) {
            rawItems.forEach((rawItem, index) => {
                try {
                    items.push(new LineItem(rawItem));
                } catch (error) {
                    for (const nestedError of error.errors) {
                        addError(
                            errors,
                            ["items", index, ...nestedError.path],
                            nestedError.message,
                            nestedError.type,
                        );
                    }
                }
            });
        }

        // Cross-field/business validation:
        // every SKU must be unique in this order.
        if (items.length > 0) {
            const skuSet = new Set(items.map((item) => item.sku));

            if (skuSet.size !== items.length) {
                addError(
                    errors,
                    ["items"],
                    "Duplicate SKUs are not allowed",
                    "duplicate_items",
                );
            }
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            orderId,
            customer,
            items,
        });
    }

    get subtotal() {
        return this.items.reduce(
            (total, item) => total + item.lineTotal,
            0,
        );
    }
}

const customer = new Customer({
    customerId: 1,
    name: "Atul Pandey",
    address: {
        street: "12 Main Road",
        city: "Lucknow",
        postalCode: "226001",
    },
});

const order = new ShoppingOrder({
    orderId: "ORD-1001",
    customer: customer.toJSON(),
    items: [
        {
            sku: "KEY-001",
            quantity: 2,
            unitPrice: 2500,
        },
        {
            sku: "MOU-001",
            quantity: 1,
            unitPrice: 1200,
        },
    ],
});

console.log("Nested order:", order);
console.log("Computed subtotal:", order.subtotal);


// ---------------------------------------------------------------------------
// 9. Cross-field validation
// ---------------------------------------------------------------------------

class DateRange extends ValidationModel {
    static validate(data) {
        const errors = [];

        const startDate = new Date(data.startDate);
        const endDate = new Date(data.endDate);

        if (Number.isNaN(startDate.getTime())) {
            addError(errors, ["startDate"], "Invalid date", "date_parsing");
        }

        if (Number.isNaN(endDate.getTime())) {
            addError(errors, ["endDate"], "Invalid date", "date_parsing");
        }

        if (
            !Number.isNaN(startDate.getTime()) &&
            !Number.isNaN(endDate.getTime()) &&
            endDate < startDate
        ) {
            addError(
                errors,
                [],
                "endDate cannot be earlier than startDate",
                "date_range",
            );
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            startDate: startDate.toISOString(),
            endDate: endDate.toISOString(),
        });
    }
}

console.log(
    new DateRange({
        startDate: "2026-09-01",
        endDate: "2026-09-30",
    }),
);

try {
    new DateRange({
        startDate: "2026-09-30",
        endDate: "2026-09-01",
    });
} catch (error) {
    console.log(error.errors);
}


// ---------------------------------------------------------------------------
// 10. Strictness
// ---------------------------------------------------------------------------

class StrictRecord extends ValidationModel {
    static validate(data) {
        const errors = [];

        if (!Number.isInteger(data.quantity)) {
            addError(
                errors,
                ["quantity"],
                "Strict integer required",
                "strict_int",
            );
        }

        if (typeof data.active !== "boolean") {
            addError(
                errors,
                ["active"],
                "Strict boolean required",
                "strict_bool",
            );
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            quantity: data.quantity,
            active: data.active,
        });
    }
}

console.log(new StrictRecord({ quantity: 10, active: true }));

try {
    new StrictRecord({ quantity: "10", active: 1 });
} catch (error) {
    console.log("Strict validation:", error.errors);
}


// ---------------------------------------------------------------------------
// 11. Extra-field policy
// ---------------------------------------------------------------------------

function forbidUnknownFields(data, knownFields, errors) {
    for (const key of Object.keys(data)) {
        if (!knownFields.has(key)) {
            addError(
                errors,
                [key],
                "Extra inputs are not permitted",
                "extra_forbidden",
            );
        }
    }
}

class StrictAPIRequest extends ValidationModel {
    static validate(data) {
        const errors = [];
        const fields = new Set(["name", "quantity"]);

        forbidUnknownFields(data, fields, errors);

        const name = requireString(data.name, ["name"], errors, {
            minLength: 1,
        });

        const quantity = requireInteger(data.quantity, ["quantity"], errors, {
            gt: 0,
        });

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({ name, quantity });
    }
}

try {
    new StrictAPIRequest({
        name: "Keyboard",
        quantity: 5,
        unexpected: true,
    });
} catch (error) {
    console.log("Unknown-field error:", error.errors);
}


// ---------------------------------------------------------------------------
// 12. Discriminated union
// ---------------------------------------------------------------------------

class PaymentDetails {
    static validate(data) {
        const errors = [];

        if (data.method === "card") {
            const cardLast4 = requireString(
                data.cardLast4,
                ["cardLast4"],
                errors,
                { pattern: /^\d{4}$/ },
            );

            if (errors.length > 0) {
                return validationFailure(errors);
            }

            return validationSuccess({
                method: "card",
                cardLast4,
            });
        }

        if (data.method === "bank") {
            const accountReference = requireString(
                data.accountReference,
                ["accountReference"],
                errors,
                { minLength: 4 },
            );

            if (errors.length > 0) {
                return validationFailure(errors);
            }

            return validationSuccess({
                method: "bank",
                accountReference,
            });
        }

        addError(
            errors,
            ["method"],
            "method must be card or bank",
            "literal_error",
        );

        return validationFailure(errors);
    }
}

class Transaction extends ValidationModel {
    static validate(data) {
        const errors = [];

        const transactionId = requireString(
            data.transactionId,
            ["transactionId"],
            errors,
            { minLength: 3 },
        );

        let payment = null;

        try {
            const result = PaymentDetails.validate(data.payment);

            if (!result.success) {
                for (const nestedError of result.errors) {
                    addError(
                        errors,
                        ["payment", ...nestedError.path],
                        nestedError.message,
                        nestedError.type,
                    );
                }
            } else {
                payment = result.value;
            }
        } catch (error) {
            addError(errors, ["payment"], "Invalid payment", "payment_error");
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            transactionId,
            payment,
        });
    }
}

console.log(
    new Transaction({
        transactionId: "TX-001",
        payment: {
            method: "card",
            cardLast4: "1234",
        },
    }),
);


// ---------------------------------------------------------------------------
// 13. JSON serialization
// ---------------------------------------------------------------------------

function serializeModel(model) {
    return JSON.stringify(model.toJSON(), null, 2);
}

console.log("Serialized order:");
console.log(serializeModel(order));


// ---------------------------------------------------------------------------
// 14. JSON-Schema-like metadata
// ---------------------------------------------------------------------------

const productSchema = {
    type: "object",
    additionalProperties: false,
    required: ["productId", "name", "price", "stock"],
    properties: {
        productId: {
            type: "integer",
            exclusiveMinimum: 0,
        },
        name: {
            type: "string",
            minLength: 2,
            maxLength: 100,
        },
        price: {
            type: "number",
            exclusiveMinimum: 0,
        },
        stock: {
            type: "integer",
            minimum: 0,
        },
    },
};

console.log("Schema representation:");
console.log(JSON.stringify(productSchema, null, 2));


// ---------------------------------------------------------------------------
// 15. Realistic API payload validator
// ---------------------------------------------------------------------------

class CreateOrderRequest extends ValidationModel {
    static validate(data) {
        const errors = [];

        const knownFields = new Set([
            "customerId",
            "shippingAddress",
            "products",
            "couponCode",
        ]);

        forbidUnknownFields(data, knownFields, errors);

        const customerId = requireInteger(
            data.customerId,
            ["customerId"],
            errors,
            { gt: 0 },
        );

        let shippingAddress = null;

        try {
            shippingAddress = new Address(data.shippingAddress);
        } catch (error) {
            for (const nestedError of error.errors) {
                addError(
                    errors,
                    ["shippingAddress", ...nestedError.path],
                    nestedError.message,
                    nestedError.type,
                );
            }
        }

        const rawProducts = requireArray(
            data.products,
            ["products"],
            errors,
            { minLength: 1, maxLength: 100 },
        );

        const products = [];

        if (rawProducts !== null) {
            rawProducts.forEach((product, index) => {
                const productErrors = [];

                const productId = requireInteger(
                    product.productId,
                    ["productId"],
                    productErrors,
                    { gt: 0 },
                );

                const quantity = requireInteger(
                    product.quantity,
                    ["quantity"],
                    productErrors,
                    { gt: 0, le: 1000 },
                );

                if (productErrors.length > 0) {
                    for (const nestedError of productErrors) {
                        addError(
                            errors,
                            ["products", index, ...nestedError.path],
                            nestedError.message,
                            nestedError.type,
                        );
                    }
                } else {
                    products.push({
                        productId,
                        quantity,
                    });
                }
            });
        }

        let couponCode = data.couponCode ?? null;

        if (couponCode !== null) {
            couponCode = requireString(
                couponCode,
                ["couponCode"],
                errors,
                { minLength: 3, maxLength: 30 },
            );

            if (couponCode !== null) {
                couponCode = couponCode.toUpperCase();
            }
        }

        // Model-level business rule.
        if (products.length > 0) {
            const ids = products.map((product) => product.productId);

            if (new Set(ids).size !== ids.length) {
                addError(
                    errors,
                    ["products"],
                    "Duplicate product IDs are not allowed",
                    "duplicate_products",
                );
            }
        }

        if (errors.length > 0) {
            return validationFailure(errors);
        }

        return validationSuccess({
            customerId,
            shippingAddress,
            products,
            couponCode,
        });
    }
}

const validPayload = {
    customerId: 500,
    shippingAddress: {
        street: "12 Main Road",
        city: "Lucknow",
        postalCode: "226001",
    },
    products: [
        { productId: 101, quantity: 2 },
        { productId: 102, quantity: 1 },
    ],
    couponCode: "save20",
};

console.log("Validated API request:");
console.log(new CreateOrderRequest(validPayload));


// ---------------------------------------------------------------------------
// 16. Error reporting
// ---------------------------------------------------------------------------

const invalidPayload = {
    customerId: -1,
    shippingAddress: {
        street: "X",
        city: "L",
        postalCode: "123",
    },
    products: [
        { productId: 1, quantity: 0 },
        { productId: 1, quantity: 5 },
    ],
    unknown: true,
};

try {
    new CreateOrderRequest(invalidPayload);
} catch (error) {
    console.log("Structured API validation errors:");

    for (const item of error.errors) {
        console.log(
            `path=${JSON.stringify(item.path)} ` +
            `type=${item.type} ` +
            `message=${item.message}`,
        );
    }
}


// ---------------------------------------------------------------------------
// 17. Validation pipeline
// ---------------------------------------------------------------------------

function validateAndSerialize(ModelClass, payload) {
    const model = new ModelClass(payload);

    return {
        model,
        json: JSON.stringify(model.toJSON()),
    };
}

const pipelineResult = validateAndSerialize(
    CreateOrderRequest,
    validPayload,
);

console.log("Pipeline JSON:");
console.log(pipelineResult.json);


// ---------------------------------------------------------------------------
// 18. Edge cases
// ---------------------------------------------------------------------------

console.log("Edge-case tests:");

const edgeCases = [
    {
        name: "zero quantity",
        run: () =>
            new Product({
                productId: 1,
                name: "Item",
                price: 10,
                stock: 0,
            }),
    },
    {
        name: "negative price",
        run: () =>
            new Product({
                productId: 1,
                name: "Item",
                price: -10,
                stock: 5,
            }),
    },
    {
        name: "empty name",
        run: () =>
            new Product({
                productId: 1,
                name: "",
                price: 10,
                stock: 5,
            }),
    },
];

for (const test of edgeCases) {
    try {
        const result = test.run();
        console.log(test.name, "accepted:", result);
    } catch (error) {
        console.log(test.name, "rejected:", error.errors);
    }
}


// ---------------------------------------------------------------------------
// 19. Lightweight executable tests
// ---------------------------------------------------------------------------

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

const testProduct = new Product({
    productId: 10,
    name: "Mouse",
    price: 1200,
    stock: 5,
});

assert(testProduct.price === 1200, "price should be 1200");
assert(testProduct.stock === 5, "stock should be 5");

let rejectedInvalidProduct = false;

try {
    new Product({
        productId: 10,
        name: "Mouse",
        price: 0,
        stock: 5,
    });
} catch (error) {
    rejectedInvalidProduct = true;
}

assert(
    rejectedInvalidProduct,
    "zero price should be rejected",
);

assert(
    order.subtotal === 6200,
    "order subtotal should equal 6200",
);

console.log("All JavaScript validation assertions passed.");


// ---------------------------------------------------------------------------
// 20. Architectural distinction
// ---------------------------------------------------------------------------

console.log(`
Architectural distinction:

Pydantic performs runtime validation in Python and can generate JSON Schema.
JavaScript applications frequently need equivalent client-side validation
before sending data to a Python API.

The safest architecture is normally:

untrusted input
    -> validation boundary
    -> normalized internal representation
    -> business logic
    -> persistence or external API

Client-side validation improves user experience, but server-side validation
remains the authoritative security boundary.
`);

console.log("JavaScript Pydantic companion completed successfully.");

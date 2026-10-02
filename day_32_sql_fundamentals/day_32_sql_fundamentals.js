"use strict";

/*
 * SQL Fundamentals: SELECT, INSERT, UPDATE, DELETE, WHERE, ORDER BY, GROUP BY
 *
 * This Node.js program models a relational sales database without external
 * packages. It uses JavaScript data structures to expose the same reasoning
 * used when writing SQL and includes a small SQL-like query engine for the
 * fundamental operations.
 *
 * The implementation is intentionally not a translation of the Python
 * SQLite program. It focuses on JavaScript's event-driven execution model,
 * immutable-style transformations, validation, policy checks, and a
 * transaction snapshot.
 */

const readline = require("node:readline/promises");
const { stdin: input, stdout: output } = require("node:process");

const database = {
  customers: [
    { customerId: 1, name: "Aarav Mehta", city: "Lucknow", segment: "Consumer" },
    { customerId: 2, name: "Neha Sharma", city: "Delhi", segment: "Business" },
    { customerId: 3, name: "Rohan Verma", city: "Bengaluru", segment: "Enterprise" },
    { customerId: 4, name: "Isha Kapoor", city: "Mumbai", segment: "Consumer" },
    { customerId: 5, name: "Kabir Singh", city: "Lucknow", segment: "Business" },
    { customerId: 6, name: "Maya Rao", city: "Hyderabad", segment: "Enterprise" }
  ],

  products: [
    { productId: 1, name: "Mechanical Keyboard", category: "Computing", unitPrice: 4500, stock: 40 },
    { productId: 2, name: "USB-C Dock", category: "Computing", unitPrice: 7200, stock: 25 },
    { productId: 3, name: "Noise Cancelling Headphones", category: "Audio", unitPrice: 9800, stock: 18 },
    { productId: 4, name: "Webcam", category: "Video", unitPrice: 3200, stock: 30 },
    { productId: 5, name: "Monitor Arm", category: "Accessories", unitPrice: 4100, stock: 22 },
    { productId: 6, name: "Laptop Stand", category: "Accessories", unitPrice: 2600, stock: 35 }
  ],

  orders: [
    { orderId: 1001, customerId: 1, orderDate: "2026-09-01", status: "Paid" },
    { orderId: 1002, customerId: 2, orderDate: "2026-09-03", status: "Shipped" },
    { orderId: 1003, customerId: 3, orderDate: "2026-09-04", status: "Paid" },
    { orderId: 1004, customerId: 1, orderDate: "2026-09-07", status: "Cancelled" },
    { orderId: 1005, customerId: 4, orderDate: "2026-09-09", status: "Shipped" },
    { orderId: 1006, customerId: 5, orderDate: "2026-09-12", status: "Paid" },
    { orderId: 1007, customerId: 6, orderDate: "2026-09-14", status: "Pending" },
    { orderId: 1008, customerId: 2, orderDate: "2026-09-18", status: "Shipped" }
  ],

  orderItems: [
    { orderId: 1001, productId: 1, quantity: 1, unitPrice: 4500 },
    { orderId: 1001, productId: 6, quantity: 2, unitPrice: 2600 },
    { orderId: 1002, productId: 2, quantity: 1, unitPrice: 7200 },
    { orderId: 1002, productId: 4, quantity: 2, unitPrice: 3200 },
    { orderId: 1003, productId: 3, quantity: 2, unitPrice: 9800 },
    { orderId: 1003, productId: 5, quantity: 1, unitPrice: 4100 },
    { orderId: 1004, productId: 1, quantity: 1, unitPrice: 4500 },
    { orderId: 1005, productId: 4, quantity: 1, unitPrice: 3200 },
    { orderId: 1005, productId: 6, quantity: 1, unitPrice: 2600 },
    { orderId: 1006, productId: 2, quantity: 2, unitPrice: 7200 },
    { orderId: 1006, productId: 5, quantity: 2, unitPrice: 4100 },
    { orderId: 1007, productId: 3, quantity: 1, unitPrice: 9800 },
    { orderId: 1008, productId: 2, quantity: 1, unitPrice: 7200 },
    { orderId: 1008, productId: 6, quantity: 3, unitPrice: 2600 }
  ]
};

const allowedSegments = new Set(["Consumer", "Business", "Enterprise"]);
const allowedStatuses = new Set(["Pending", "Paid", "Shipped", "Cancelled"]);

function cloneDatabase(source) {
  return structuredClone(source);
}

function printRows(title, rows) {
  console.log(`\n--- ${title} ---`);

  if (rows.length === 0) {
    console.log("(no rows)");
    return;
  }

  const columns = Object.keys(rows[0]);
  const widths = Object.fromEntries(
    columns.map((column) => [
      column,
      Math.max(
        column.length,
        ...rows.map((row) => String(row[column] ?? "").length)
      )
    ])
  );

  console.log(
    columns.map((column) => column.padEnd(widths[column])).join(" | ")
  );
  console.log(
    columns.map((column) => "-".repeat(widths[column])).join("-+-")
  );

  for (const row of rows) {
    console.log(
      columns.map((column) => String(row[column] ?? "").padEnd(widths[column])).join(" | ")
    );
  }
}

function validateCustomer(customer) {
  if (!Number.isInteger(customer.customerId) || customer.customerId <= 0) {
    throw new Error("customerId must be a positive integer");
  }

  if (!customer.name?.trim()) {
    throw new Error("customer name is required");
  }

  if (!customer.city?.trim()) {
    throw new Error("customer city is required");
  }

  if (!allowedSegments.has(customer.segment)) {
    throw new Error(`Unsupported customer segment: ${customer.segment}`);
  }
}

function validateProduct(product) {
  if (!Number.isInteger(product.productId) || product.productId <= 0) {
    throw new Error("productId must be a positive integer");
  }

  if (!product.name?.trim()) {
    throw new Error("product name is required");
  }

  if (!Number.isFinite(product.unitPrice) || product.unitPrice < 0) {
    throw new Error("unitPrice cannot be negative");
  }

  if (!Number.isInteger(product.stock) || product.stock < 0) {
    throw new Error("stock cannot be negative");
  }
}

function validateOrder(order) {
  if (!Number.isInteger(order.orderId) || order.orderId <= 0) {
    throw new Error("orderId must be a positive integer");
  }

  if (!Number.isInteger(order.customerId)) {
    throw new Error("customerId must be an integer");
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(order.orderDate)) {
    throw new Error("orderDate must use YYYY-MM-DD");
  }

  if (!allowedStatuses.has(order.status)) {
    throw new Error(`Unsupported order status: ${order.status}`);
  }
}

function selectRows(rows, projection = (row) => ({ ...row })) {
  return rows.map(projection);
}

function where(rows, predicate) {
  return rows.filter(predicate);
}

function orderBy(rows, ...comparators) {
  return [...rows].sort((a, b) => {
    for (const comparator of comparators) {
      const result = comparator(a, b);
      if (result !== 0) {
        return result;
      }
    }
    return 0;
  });
}

function ascending(field) {
  return (a, b) => {
    if (a[field] < b[field]) return -1;
    if (a[field] > b[field]) return 1;
    return 0;
  };
}

function descending(field) {
  return (a, b) => ascending(field)(b, a);
}

function groupBy(rows, keySelector) {
  const groups = new Map();

  for (const row of rows) {
    const key = keySelector(row);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(row);
  }

  return groups;
}

function count(rows) {
  return rows.length;
}

function sum(rows, valueSelector) {
  return rows.reduce((total, row) => total + valueSelector(row), 0);
}

function insertCustomer(customer) {
  validateCustomer(customer);

  if (database.customers.some((row) => row.customerId === customer.customerId)) {
    throw new Error(`Customer ${customer.customerId} already exists`);
  }

  database.customers.push({ ...customer });
}

function insertProduct(product) {
  validateProduct(product);

  if (database.products.some((row) => row.productId === product.productId)) {
    throw new Error(`Product ${product.productId} already exists`);
  }

  if (database.products.some((row) => row.name === product.name)) {
    throw new Error(`Product name must be unique: ${product.name}`);
  }

  database.products.push({ ...product });
}

function updateProducts(predicate, changes) {
  let changed = 0;

  for (const product of database.products) {
    if (!predicate(product)) {
      continue;
    }

    const candidate = { ...product, ...changes };
    validateProduct(candidate);
    Object.assign(product, candidate);
    changed += 1;
  }

  return changed;
}

function deleteCustomerById(customerId) {
  const index = database.customers.findIndex(
    (customer) => customer.customerId === customerId
  );

  if (index === -1) {
    return false;
  }

  const referenced = database.orders.some(
    (order) => order.customerId === customerId
  );

  if (referenced) {
    throw new Error(
      `Customer ${customerId} cannot be deleted while orders reference it`
    );
  }

  database.customers.splice(index, 1);
  return true;
}

function demonstrateSelectWhereOrderBy() {
  const selected = selectRows(
    where(
      database.products,
      (product) => product.unitPrice >= 4000 && product.stock > 15
    ),
    (product) => ({
      product: product.name,
      category: product.category,
      price: product.unitPrice
    })
  );

  printRows(
    "SELECT projection after WHERE filtering",
    orderBy(selected, descending("price"), ascending("product"))
  );
}

function demonstrateInsert() {
  insertCustomer({
    customerId: 7,
    name: "Sara Khan",
    city: "Pune",
    segment: "Consumer"
  });

  insertProduct({
    productId: 7,
    name: "Desk Lamp",
    category: "Accessories",
    unitPrice: 1800,
    stock: 50
  });

  printRows(
    "Rows created by INSERT",
    database.customers.filter((customer) => customer.customerId === 7)
  );
}

function demonstrateUpdate() {
  const changed = updateProducts(
    (product) => product.category === "Accessories" && product.stock < 30,
    (product) => ({ stock: product.stock + 10 })
  );

  console.log(`\nUPDATE changed ${changed} product row(s).`);

  printRows(
    "Updated accessories",
    orderBy(
      selectRows(
        where(database.products, (product) => product.category === "Accessories"),
        (product) => ({
          product: product.name,
          stock: product.stock
        })
      ),
      descending("stock"),
      ascending("product")
    )
  );
}

function demonstrateDelete() {
  insertCustomer({
    customerId: 99,
    name: "Temporary Customer",
    city: "Test City",
    segment: "Consumer"
  });

  const deleted = deleteCustomerById(99);

  console.log(`\nDELETE removed temporary customer: ${deleted}`);
}

function demonstrateGrouping() {
  const groups = groupBy(database.orders, (order) => order.status);

  const report = [...groups.entries()]
    .map(([status, orders]) => ({
      status,
      orderCount: count(orders)
    }))
    .filter((row) => row.orderCount > 0);

  printRows(
    "GROUP BY order status",
    orderBy(report, descending("orderCount"), ascending("status"))
  );
}

function demonstrateAggregateSales() {
  const completedOrders = new Set(
    database.orders
      .filter((order) => order.status === "Paid" || order.status === "Shipped")
      .map((order) => order.orderId)
  );

  const salesLines = database.orderItems
    .filter((item) => completedOrders.has(item.orderId))
    .map((item) => {
      const product = database.products.find(
        (candidate) => candidate.productId === item.productId
      );

      return {
        category: product.category,
        units: item.quantity,
        value: item.quantity * item.unitPrice
      };
    });

  const groups = groupBy(salesLines, (line) => line.category);

  const report = [...groups.entries()].map(([category, lines]) => ({
    category,
    unitsSold: sum(lines, (line) => line.units),
    grossValue: Number(sum(lines, (line) => line.value).toFixed(2))
  }));

  printRows(
    "Grouped completed sales by product category",
    orderBy(report, descending("grossValue"), ascending("category"))
  );
}

function demonstrateHavingEquivalent() {
  const groups = groupBy(
    database.orderItems,
    (item) => item.productId
  );

  const report = [...groups.entries()]
    .map(([productId, items]) => {
      const product = database.products.find(
        (candidate) => candidate.productId === productId
      );

      return {
        product: product.name,
        unitsSold: sum(items, (item) => item.quantity),
        salesValue: Number(
          sum(items, (item) => item.quantity * item.unitPrice).toFixed(2)
        )
      };
    })
    .filter((row) => row.unitsSold >= 3);

  printRows(
    "HAVING-style filtering after grouping",
    orderBy(report, descending("salesValue"), ascending("product"))
  );
}

function demonstrateJoinAndReport() {
  const completedStatuses = new Set(["Paid", "Shipped"]);

  const rows = [];

  for (const order of database.orders) {
    if (!completedStatuses.has(order.status)) {
      continue;
    }

    const customer = database.customers.find(
      (candidate) => candidate.customerId === order.customerId
    );

    const items = database.orderItems.filter(
      (item) => item.orderId === order.orderId
    );

    for (const item of items) {
      rows.push({
        customerId: customer.customerId,
        customer: customer.name,
        city: customer.city,
        orderId: order.orderId,
        value: item.quantity * item.unitPrice
      });
    }
  }

  const groups = groupBy(rows, (row) => row.customerId);

  const report = [...groups.values()].map((customerRows) => ({
    customer: customerRows[0].customer,
    city: customerRows[0].city,
    completedOrders: new Set(customerRows.map((row) => row.orderId)).size,
    customerValue: Number(
      sum(customerRows, (row) => row.value).toFixed(2)
    )
  }));

  printRows(
    "Customer report using join-like relationship traversal",
    orderBy(report, descending("customerValue"), ascending("customer"))
  );
}

function demonstrateNullSemantics() {
  const customersWithOptionalCity = [
    ...database.customers,
    {
      customerId: 100,
      name: "No City Customer",
      city: null,
      segment: "Consumer"
    }
  ];

  const isNull = customersWithOptionalCity.filter(
    (customer) => customer.city === null
  );

  printRows("JavaScript null check corresponding to SQL IS NULL", isNull);
}

function demonstrateDynamicOrderingSafely() {
  /*
   * SQL parameters can bind values but cannot safely turn arbitrary text into
   * a column identifier. A trusted mapping is the correct pattern when a UI
   * allows users to choose among a small set of sort fields.
   */
  const allowedSorts = Object.freeze({
    name: ascending("name"),
    price: descending("unitPrice"),
    stock: descending("stock")
  });

  const requestedSort = "price";
  const comparator = allowedSorts[requestedSort];

  if (!comparator) {
    throw new Error("Unsupported sort option");
  }

  printRows(
    "Safe dynamic ordering",
    orderBy(
      selectRows(database.products, (product) => ({
        name: product.name,
        unitPrice: product.unitPrice,
        stock: product.stock
      })),
      comparator
    )
  );
}

async function demonstrateAsyncWorkflow() {
  /*
   * Real Node.js applications frequently execute database operations through
   * asynchronous drivers. The promise below models that boundary without
   * requiring an npm database dependency.
   */
  const delayedSelect = (predicate) =>
    new Promise((resolve) => {
      setImmediate(() => {
        resolve(database.products.filter(predicate));
      });
    });

  const expensiveProducts = await delayedSelect(
    (product) => product.unitPrice >= 7000
  );

  printRows("Asynchronous SELECT-style operation", expensiveProducts);
}

function demonstrateTransactionRollback() {
  /*
   * A real database transaction provides atomicity. The snapshot below models
   * that property: changes are made to a copy and committed only when every
   * operation succeeds.
   */
  const workingCopy = cloneDatabase(database);

  try {
    const product = workingCopy.products.find(
      (candidate) => candidate.productId === 1
    );

    if (!product) {
      throw new Error("Product not found");
    }

    product.stock -= 3;

    if (product.stock < 0) {
      throw new Error("Inventory cannot become negative");
    }

    // Deliberately trigger a referential-integrity failure.
    const invalidOrderItem = {
      orderId: 123456,
      productId: 1,
      quantity: 1,
      unitPrice: product.unitPrice
    };

    const orderExists = workingCopy.orders.some(
      (order) => order.orderId === invalidOrderItem.orderId
    );

    if (!orderExists) {
      throw new Error("Referenced order does not exist");
    }

    Object.assign(database, workingCopy);
  } catch (error) {
    console.log(`\nTransaction simulation rolled back: ${error.message}`);
  }
}

function demonstrateValidationFailure() {
  try {
    insertProduct({
      productId: 500,
      name: "Invalid Product",
      category: "Computing",
      unitPrice: -100,
      stock: 10
    });
  } catch (error) {
    console.log(`\nValidation rejected invalid INSERT: ${error.message}`);
  }
}

function createInteractiveQuery() {
  return readline.createInterface({ input, output });
}

async function optionalInteractiveFilter() {
  const rl = createInteractiveQuery();

  try {
    const city = (await rl.question(
      "\nEnter a customer city to filter (press Enter for Lucknow): "
    )).trim() || "Lucknow";

    /*
     * In a real SQL driver this value would be bound through a parameter
     * placeholder. The JavaScript simulation still validates the input as a
     * plain value and never treats it as executable SQL.
     */
    const matchingCustomers = database.customers.filter(
      (customer) => customer.city === city
    );

    printRows(`WHERE city = ${JSON.stringify(city)}`, matchingCustomers);
  } finally {
    rl.close();
  }
}

async function main() {
  console.log("=".repeat(72));
  console.log("SQL FUNDAMENTALS: JAVASCRIPT QUERY MODEL");
  console.log("SELECT | INSERT | UPDATE | DELETE | WHERE | ORDER BY | GROUP BY");
  console.log("=".repeat(72));

  demonstrateSelectWhereOrderBy();
  demonstrateInsert();
  demonstrateUpdate();
  demonstrateDelete();
  demonstrateGrouping();
  demonstrateAggregateSales();
  demonstrateHavingEquivalent();
  demonstrateJoinAndReport();
  demonstrateNullSemantics();
  demonstrateDynamicOrderingSafely();
  demonstrateTransactionRollback();
  demonstrateValidationFailure();
  await demonstrateAsyncWorkflow();

  /*
   * Set RUN_INTERACTIVE=true in the environment when an interactive terminal
   * filter is desired. Keeping it opt-in makes the program automation-friendly.
   */
  if (process.env.RUN_INTERACTIVE === "true") {
    await optionalInteractiveFilter();
  }

  console.log("\nJavaScript SQL fundamentals laboratory completed.");
}

main().catch((error) => {
  console.error(`Fatal error: ${error.message}`);
  process.exitCode = 1;
});

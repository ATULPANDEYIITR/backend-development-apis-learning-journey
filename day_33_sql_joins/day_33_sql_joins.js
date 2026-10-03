'use strict';

/*
 * SQL JOINs represented with JavaScript data structures.
 *
 * This implementation emphasizes JavaScript-specific techniques:
 * Map-based indexing, functional transformation, immutable-style result
 * creation, event-driven join processing, async policy evaluation, and
 * validation of relational data.
 *
 * The data models customers, orders, products, and employees. The functions
 * intentionally mirror relational operations rather than relying on a
 * database package.
 */

const customers = [
  { customerId: 1, name: 'Asha', city: 'Lucknow' },
  { customerId: 2, name: 'Ravi', city: 'Delhi' },
  { customerId: 3, name: 'Meera', city: 'Mumbai' },
  { customerId: 4, name: 'Kabir', city: 'Pune' },
  { customerId: 5, name: 'Nisha', city: 'Jaipur' }
];

const orders = [
  { orderId: 101, customerId: 1, productId: 501, amount: 2400 },
  { orderId: 102, customerId: 1, productId: 502, amount: 900 },
  { orderId: 103, customerId: 2, productId: 503, amount: 1500 },
  { orderId: 104, customerId: 2, productId: 501, amount: 3100 },
  { orderId: 105, customerId: 4, productId: 504, amount: 700 },
  { orderId: 106, customerId: 9, productId: 501, amount: 1200 }
];

const products = [
  { productId: 501, productName: 'Laptop', category: 'Computers' },
  { productId: 502, productName: 'Keyboard', category: 'Accessories' },
  { productId: 503, productName: 'Monitor', category: 'Displays' },
  { productId: 504, productName: 'Mouse', category: 'Accessories' },
  { productId: 505, productName: 'Webcam', category: 'Accessories' }
];

const employees = [
  { employeeId: 1, employeeName: 'Anika', managerId: null, department: 'Engineering' },
  { employeeId: 2, employeeName: 'Bharat', managerId: 1, department: 'Engineering' },
  { employeeId: 3, employeeName: 'Charu', managerId: 1, department: 'Engineering' },
  { employeeId: 4, employeeName: 'Dev', managerId: 2, department: 'Finance' },
  { employeeId: 5, employeeName: 'Esha', managerId: 2, department: 'Operations' },
  { employeeId: 6, employeeName: 'Farhan', managerId: 99, department: 'Operations' }
];


// ---------------------------------------------------------------------------
// Generic utilities
// ---------------------------------------------------------------------------

function combineRows(left, right, leftAlias = 'left', rightAlias = 'right') {
  const result = {};

  if (left !== null) {
    for (const [key, value] of Object.entries(left)) {
      result[`${leftAlias}.${key}`] = value;
    }
  }

  if (right !== null) {
    for (const [key, value] of Object.entries(right)) {
      result[`${rightAlias}.${key}`] = value;
    }
  }

  return result;
}

function nullRow(rows, alias) {
  if (rows.length === 0) {
    return {};
  }

  return Object.fromEntries(
    Object.keys(rows[0]).map(key => [`${alias}.${key}`, null])
  );
}

function display(title, rows) {
  console.log(`\n${title}`);
  console.log('-'.repeat(title.length));

  if (rows.length === 0) {
    console.log('(no rows)');
    return;
  }

  const columns = [];
  for (const row of rows) {
    for (const column of Object.keys(row)) {
      if (!columns.includes(column)) {
        columns.push(column);
      }
    }
  }

  console.table(
    rows.map(row => Object.fromEntries(
      columns.map(column => [column, row[column] ?? null])
    ))
  );
}


// ---------------------------------------------------------------------------
// Map indexing
// ---------------------------------------------------------------------------

function buildIndex(rows, keySelector) {
  /*
   * A Map preserves multiple rows for the same key by storing an array.
   * Storing only one row would silently lose valid matches in one-to-many
   * relationships.
   */
  const index = new Map();

  for (const row of rows) {
    const key = keySelector(row);

    if (!index.has(key)) {
      index.set(key, []);
    }

    index.get(key).push(row);
  }

  return index;
}


// ---------------------------------------------------------------------------
// INNER JOIN
// ---------------------------------------------------------------------------

function innerJoin(leftRows, rightRows, leftKey, rightKey) {
  const index = buildIndex(rightRows, rightKey);
  const result = [];

  for (const left of leftRows) {
    const matches = index.get(leftKey(left)) ?? [];

    for (const right of matches) {
      result.push(combineRows(left, right));
    }
  }

  return result;
}


// ---------------------------------------------------------------------------
// LEFT JOIN
// ---------------------------------------------------------------------------

function leftJoin(leftRows, rightRows, leftKey, rightKey) {
  const index = buildIndex(rightRows, rightKey);
  const result = [];

  for (const left of leftRows) {
    const matches = index.get(leftKey(left)) ?? [];

    if (matches.length === 0) {
      result.push({
        ...prefixExisting(left, 'left'),
        ...nullRow(rightRows, 'right')
      });
      continue;
    }

    for (const right of matches) {
      result.push(combineRows(left, right));
    }
  }

  return result;
}

function prefixExisting(row, alias) {
  return Object.fromEntries(
    Object.entries(row).map(([key, value]) => [`${alias}.${key}`, value])
  );
}


// ---------------------------------------------------------------------------
// RIGHT JOIN
// ---------------------------------------------------------------------------

function rightJoin(leftRows, rightRows, leftKey, rightKey) {
  /*
   * RIGHT JOIN can be expressed as LEFT JOIN with reversed relations.
   * The output aliases are then restored to reflect the original roles.
   */
  const reversed = leftJoin(
    rightRows,
    leftRows,
    rightKey,
    leftKey
  );

  return reversed.map(row => {
    const result = {};

    for (const [key, value] of Object.entries(row)) {
      if (key.startsWith('left.')) {
        result[`right.${key.slice(5)}`] = value;
      } else if (key.startsWith('right.')) {
        result[`left.${key.slice(6)}`] = value;
      }
    }

    return result;
  });
}


// ---------------------------------------------------------------------------
// FULL OUTER JOIN
// ---------------------------------------------------------------------------

function fullJoin(leftRows, rightRows, leftKey, rightKey) {
  const index = buildIndex(
    rightRows.map((row, index) => ({ row, originalIndex: index })),
    item => rightKey(item.row)
  );

  const matchedRightIndexes = new Set();
  const result = [];

  for (const left of leftRows) {
    const matches = index.get(leftKey(left)) ?? [];

    if (matches.length === 0) {
      result.push({
        ...prefixExisting(left, 'left'),
        ...nullRow(rightRows, 'right')
      });
      continue;
    }

    for (const match of matches) {
      matchedRightIndexes.add(match.originalIndex);
      result.push(combineRows(left, match.row));
    }
  }

  rightRows.forEach((right, indexNumber) => {
    if (!matchedRightIndexes.has(indexNumber)) {
      result.push({
        ...nullRow(leftRows, 'left'),
        ...prefixExisting(right, 'right')
      });
    }
  });

  return result;
}


// ---------------------------------------------------------------------------
// CROSS JOIN
// ---------------------------------------------------------------------------

function crossJoin(leftRows, rightRows) {
  /*
   * Array.flatMap makes the Cartesian product explicit:
   * every left row creates a set of results containing every right row.
   */
  return leftRows.flatMap(left =>
    rightRows.map(right => combineRows(left, right))
  );
}


// ---------------------------------------------------------------------------
// SELF JOIN
// ---------------------------------------------------------------------------

function selfJoin(rows, leftKey, rightKey) {
  /*
   * The same array participates twice. Aliases make the two logical roles
   * distinguishable even though both sides originate from one relation.
   */
  const index = buildIndex(rows, rightKey);
  const result = [];

  for (const employee of rows) {
    const managers = index.get(leftKey(employee)) ?? [];

    for (const manager of managers) {
      result.push(
        combineRows(employee, manager, 'employee', 'manager')
      );
    }
  }

  return result;
}


// ---------------------------------------------------------------------------
// Composite-key joins
// ---------------------------------------------------------------------------

function compositeKey(...parts) {
  /*
   * JSON serialization creates a deterministic compound representation for
   * the demonstration. Production systems should choose a key representation
   * that cannot become ambiguous when values contain separators.
   */
  return JSON.stringify(parts);
}

function compositeJoinDemo() {
  const inventory = [
    { warehouseId: 'LKO', productId: 501, quantity: 14 },
    { warehouseId: 'DEL', productId: 501, quantity: 6 },
    { warehouseId: 'LKO', productId: 502, quantity: 22 }
  ];

  const requests = [
    { warehouseId: 'LKO', productId: 501, requestId: 'R1' },
    { warehouseId: 'DEL', productId: 501, requestId: 'R2' },
    { warehouseId: 'LKO', productId: 999, requestId: 'R3' }
  ];

  return leftJoin(
    requests,
    inventory,
    row => compositeKey(row.warehouseId, row.productId),
    row => compositeKey(row.warehouseId, row.productId)
  );
}


// ---------------------------------------------------------------------------
// Join cardinality
// ---------------------------------------------------------------------------

function cardinality(leftRows, rightRows, leftKey, rightKey) {
  const leftCounts = new Map();
  const rightCounts = new Map();

  for (const row of leftRows) {
    const key = leftKey(row);
    leftCounts.set(key, (leftCounts.get(key) ?? 0) + 1);
  }

  for (const row of rightRows) {
    const key = rightKey(row);
    rightCounts.set(key, (rightCounts.get(key) ?? 0) + 1);
  }

  let innerRows = 0;
  let matchingKeys = 0;

  for (const [key, count] of leftCounts) {
    if (rightCounts.has(key)) {
      matchingKeys += 1;
      innerRows += count * rightCounts.get(key);
    }
  }

  return {
    leftRows: leftRows.length,
    rightRows: rightRows.length,
    matchingKeys,
    innerJoinRows: innerRows,
    leftOnlyKeys: [...leftCounts.keys()]
      .filter(key => !rightCounts.has(key)).length,
    rightOnlyKeys: [...rightCounts.keys()]
      .filter(key => !leftCounts.has(key)).length
  };
}


// ---------------------------------------------------------------------------
// Event-driven join workflow
// ---------------------------------------------------------------------------

class JoinWorkflow extends EventTarget {
  /*
   * EventTarget is a browser and modern Node.js mechanism. It demonstrates
   * how a join operation can participate in an event-driven data pipeline.
   */
  run(name, operation) {
    this.dispatchEvent(new CustomEvent('join:start', {
      detail: { name }
    }));

    try {
      const result = operation();

      this.dispatchEvent(new CustomEvent('join:complete', {
        detail: {
          name,
          rowCount: result.length
        }
      }));

      return result;
    } catch (error) {
      this.dispatchEvent(new CustomEvent('join:error', {
        detail: {
          name,
          message: error.message
        }
      }));

      throw error;
    }
  }
}

function demonstrateEvents() {
  const workflow = new JoinWorkflow();

  workflow.addEventListener('join:start', event => {
    console.log(`\n[event] starting ${event.detail.name}`);
  });

  workflow.addEventListener('join:complete', event => {
    console.log(
      `[event] ${event.detail.name} produced ${event.detail.rowCount} rows`
    );
  });

  workflow.addEventListener('join:error', event => {
    console.error(
      `[event] ${event.detail.name} failed: ${event.detail.message}`
    );
  });

  return workflow.run(
    'customer-order inner join',
    () => innerJoin(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );
}


// ---------------------------------------------------------------------------
// Async join validation
// ---------------------------------------------------------------------------

async function validateForeignKeysAsync(
  childRows,
  childKey,
  parentRows,
  parentKey
) {
  /*
   * Promise.resolve() keeps this function asynchronous without adding a
   * dependency. A real application could replace the parentRows argument
   * with data obtained from an API or database call.
   */
  await Promise.resolve();

  const parentKeys = new Set(parentRows.map(parentKey));
  const invalid = childRows
    .map(childKey)
    .filter(key => !parentKeys.has(key));

  return [...new Set(invalid)];
}


// ---------------------------------------------------------------------------
// Outer-join filtering trap
// ---------------------------------------------------------------------------

function demonstrateOuterJoinFilter() {
  const joined = leftJoin(
    customers,
    orders,
    row => row.customerId,
    row => row.customerId
  );

  /*
   * This post-join filter removes rows whose right side is null. It therefore
   * changes the population represented by the LEFT JOIN.
   */
  const postJoinFilter = joined.filter(
    row => row['right.amount'] !== null && row['right.amount'] >= 1500
  );

  /*
   * This version first limits the right relation. Customers without an
   * eligible order are still retained as NULL-extended rows.
   */
  const eligibleOrders = orders.filter(order => order.amount >= 1500);

  const conditionInJoin = leftJoin(
    customers,
    eligibleOrders,
    row => row.customerId,
    row => row.customerId
  );

  return { postJoinFilter, conditionInJoin };
}


// ---------------------------------------------------------------------------
// Customer totals
// ---------------------------------------------------------------------------

function customerTotals() {
  const joined = leftJoin(
    customers,
    orders,
    row => row.customerId,
    row => row.customerId
  );

  const totals = new Map(
    customers.map(customer => [customer.customerId, 0])
  );

  for (const row of joined) {
    if (row['right.amount'] !== null) {
      const current = totals.get(row['left.customerId']) ?? 0;
      totals.set(
        row['left.customerId'],
        current + row['right.amount']
      );
    }
  }

  return customers.map(customer => ({
    customerId: customer.customerId,
    customerName: customer.name,
    totalOrderValue: totals.get(customer.customerId)
  }));
}


// ---------------------------------------------------------------------------
// Practical multi-table report
// ---------------------------------------------------------------------------

function customerProductReport() {
  const customerOrders = innerJoin(
    customers,
    orders,
    row => row.customerId,
    row => row.customerId
  );

  const orderProducts = innerJoin(
    customerOrders,
    products,
    row => row['right.productId'],
    row => row.productId
  );

  return orderProducts.map(row => ({
    customer: row['left.left.name'],
    orderId: row['left.right.orderId'],
    product: row['right.productName'],
    category: row['right.category'],
    amount: row['left.right.amount']
  }));
}


// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function assertUnique(rows, keySelector, name) {
  const seen = new Set();

  for (const row of rows) {
    const key = keySelector(row);

    if (seen.has(key)) {
      throw new Error(`${name} contains duplicate key ${String(key)}`);
    }

    seen.add(key);
  }
}

function validateRelations() {
  assertUnique(
    customers,
    row => row.customerId,
    'customers.customerId'
  );

  assertUnique(
    products,
    row => row.productId,
    'products.productId'
  );

  const customerIds = new Set(customers.map(row => row.customerId));

  return orders
    .map(row => row.customerId)
    .filter(id => !customerIds.has(id));
}


// ---------------------------------------------------------------------------
// Main executable demonstration
// ---------------------------------------------------------------------------

async function main() {
  display(
    'INNER JOIN: customers with matching orders',
    innerJoin(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );

  display(
    'LEFT JOIN: preserve every customer',
    leftJoin(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );

  display(
    'RIGHT JOIN: preserve every order',
    rightJoin(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );

  display(
    'FULL OUTER JOIN: preserve unmatched rows on both sides',
    fullJoin(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );

  display(
    'CROSS JOIN: customer/departments combinations',
    crossJoin(customers.slice(0, 2), [
      { departmentId: 10, departmentName: 'Engineering' },
      { departmentId: 20, departmentName: 'Finance' }
    ])
  );

  display(
    'SELF JOIN: employees and their managers',
    selfJoin(
      employees,
      row => row.managerId,
      row => row.employeeId
    )
  );

  display(
    'Composite-key LEFT JOIN',
    compositeJoinDemo()
  );

  display(
    'Customer totals after LEFT JOIN',
    customerTotals()
  );

  display(
    'Customer/order/product report',
    customerProductReport()
  );

  console.log('\nJoin cardinality');
  console.log('----------------');
  console.table(
    cardinality(
      customers,
      orders,
      row => row.customerId,
      row => row.customerId
    )
  );

  console.log('\nReferential-integrity validation');
  console.log('--------------------------------');
  console.log(
    'Unmatched customer IDs:',
    validateRelations()
  );

  console.log('\nOuter-join filtering behavior');
  console.log('-----------------------------');
  const filters = demonstrateOuterJoinFilter();
  console.log('Post-join filter rows:', filters.postJoinFilter.length);
  console.log(
    'Condition applied before matching:',
    filters.conditionInJoin.length
  );

  console.log('\nEvent-driven workflow');
  console.log('---------------------');
  demonstrateEvents();

  console.log('\nAsync foreign-key validation');
  console.log('----------------------------');
  const invalidCustomerIds = await validateForeignKeysAsync(
    orders,
    row => row.customerId,
    customers,
    row => row.customerId
  );
  console.log('Invalid customer IDs:', invalidCustomerIds);

  console.log('\nImplementation notes');
  console.log('--------------------');
  console.log(
    'Map indexes preserve duplicate matches, which is necessary for one-to-many joins.'
  );
  console.log(
    'LEFT JOIN null-extension is represented with JavaScript null.'
  );
  console.log(
    'CROSS JOIN output grows multiplicatively: m left rows × n right rows.'
  );
  console.log(
    'SELF JOIN aliases distinguish two logical roles of the same relation.'
  );
  console.log(
    'A post-join right-side filter can unintentionally remove NULL-extended rows.'
  );
}

main().catch(error => {
  console.error('Join demonstration failed:', error);
  process.exitCode = 1;
});

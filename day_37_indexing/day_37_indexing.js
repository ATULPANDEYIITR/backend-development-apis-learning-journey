'use strict';

/*
 * Indexing laboratory for Node.js.
 *
 * This implementation focuses on JavaScript-specific behavior:
 * asynchronous workflow modeling, event-driven index maintenance, immutable
 * policy objects, query predicate evaluation, selectivity analysis, and an
 * in-memory representation of B-tree-like and hash access paths.
 *
 * No npm dependencies are required.
 */

const assert = require('node:assert/strict');

const SEED = 42;

function createRng(seed) {
    let state = seed >>> 0;

    return function random() {
        state = (1664525 * state + 1013904223) >>> 0;
        return state / 0x100000000;
    };
}

function choose(random, values, weights = null) {
    if (!weights) {
        return values[Math.floor(random() * values.length)];
    }

    const total = weights.reduce((sum, value) => sum + value, 0);
    let threshold = random() * total;

    for (let index = 0; index < values.length; index += 1) {
        threshold -= weights[index];
        if (threshold <= 0) {
            return values[index];
        }
    }

    return values[values.length - 1];
}

function generateOrders(count) {
    const random = createRng(SEED);
    const statuses = ['pending', 'paid', 'shipped', 'cancelled'];
    const regions = ['north', 'south', 'east', 'west'];

    return Array.from({ length: count }, (_, index) => {
        const year = choose(random, [2024, 2025, 2026]);
        const month = String(1 + Math.floor(random() * 12)).padStart(2, '0');
        const day = String(1 + Math.floor(random() * 28)).padStart(2, '0');

        return {
            id: index + 1,
            customerId: 1 + Math.floor(random() * 5000),
            status: choose(random, statuses, [8, 28, 45, 19]),
            region: choose(random, regions),
            orderDate: `${year}-${month}-${day}`,
            totalCents: 500 + Math.floor(random() * 499501)
        };
    });
}

class EventBus {
    #listeners = new Map();

    on(eventName, listener) {
        if (!this.#listeners.has(eventName)) {
            this.#listeners.set(eventName, new Set());
        }

        this.#listeners.get(eventName).add(listener);

        return () => this.#listeners.get(eventName)?.delete(listener);
    }

    emit(eventName, payload) {
        const listeners = this.#listeners.get(eventName) ?? [];

        for (const listener of listeners) {
            listener(payload);
        }
    }
}

class HashIndex {
    #buckets = new Map();

    add(key, rowId) {
        const bucket = this.#buckets.get(key) ?? [];
        bucket.push(rowId);
        this.#buckets.set(key, bucket);
    }

    lookup(key) {
        return [...(this.#buckets.get(key) ?? [])];
    }

    size() {
        return this.#buckets.size;
    }
}

class CompositeIndex {
    #entries = new Map();

    constructor(columns) {
        if (!Array.isArray(columns) || columns.length === 0) {
            throw new TypeError('A composite index needs at least one column.');
        }

        this.columns = Object.freeze([...columns]);
    }

    add(row) {
        const key = this.columns.map(column => String(row[column])).join('\u001F');
        const bucket = this.#entries.get(key) ?? [];
        bucket.push(row.id);
        this.#entries.set(key, bucket);
    }

    lookup(values) {
        if (values.length !== this.columns.length) {
            throw new Error(
                `Expected ${this.columns.length} key values, received ${values.length}.`
            );
        }

        const key = values.map(String).join('\u001F');
        return [...(this.#entries.get(key) ?? [])];
    }

    get distinctKeys() {
        return this.#entries.size;
    }
}

class PartialIndex {
    #rowIds = new Set();

    constructor(predicate) {
        if (typeof predicate !== 'function') {
            throw new TypeError('A partial index requires a predicate function.');
        }

        this.predicate = predicate;
    }

    consider(row) {
        if (this.predicate(row)) {
            this.#rowIds.add(row.id);
        }
    }

    contains(rowId) {
        return this.#rowIds.has(rowId);
    }

    get size() {
        return this.#rowIds.size;
    }
}

class IndexCatalog {
    constructor(rows) {
        this.rows = rows;
        this.hashByCustomer = new HashIndex();
        this.regionStatus = new CompositeIndex(['region', 'status']);
        this.pendingOrdersByDate = new PartialIndex(
            row => row.status === 'pending'
        );

        for (const row of rows) {
            this.hashByCustomer.add(row.customerId, row.id);
            this.regionStatus.add(row);
            this.pendingOrdersByDate.consider(row);
        }
    }

    explain(predicate) {
        if (predicate.customerId !== undefined) {
            return 'hash/customerId equality access path';
        }

        if (
            predicate.region !== undefined &&
            predicate.status !== undefined
        ) {
            return 'composite(region, status) access path';
        }

        if (predicate.status === 'pending' && predicate.orderDate !== undefined) {
            return 'partial(status = pending) + date filtering';
        }

        return 'full scan';
    }
}

function frequencyDistribution(rows, field) {
    const counts = new Map();

    for (const row of rows) {
        counts.set(fieldValue(row, field), (counts.get(fieldValue(row, field)) ?? 0) + 1);
    }

    return counts;
}

function fieldValue(row, field) {
    return row[field];
}

function calculateSelectivity(rows, field) {
    if (rows.length === 0) {
        return 0;
    }

    const distinct = new Set(rows.map(row => fieldValue(row, field))).size;
    return distinct / rows.length;
}

function selectivityReport(rows) {
    const fields = ['status', 'region', 'customerId', 'orderDate'];

    return fields.map(field => ({
        field,
        rows: rows.length,
        distinct: new Set(rows.map(row => fieldValue(row, field))).size,
        selectivity: calculateSelectivity(rows, field)
    }));
}

function runIndexedQuery(rows, catalog, predicate) {
    const start = process.hrtime.bigint();
    let candidateIds;

    if (predicate.customerId !== undefined) {
        candidateIds = catalog.hashByCustomer.lookup(predicate.customerId);
    } else {
        candidateIds = rows.map(row => row.id);
    }

    const candidateSet = new Set(candidateIds);

    const result = rows.filter(row => {
        if (!candidateSet.has(row.id)) {
            return false;
        }

        return Object.entries(predicate).every(([field, expected]) => {
            if (field === 'orderDateFrom') {
                return row.orderDate >= expected;
            }

            if (field === 'orderDateToExclusive') {
                return row.orderDate < expected;
            }

            return row[field] === expected;
        });
    });

    const elapsedMs = Number(process.hrtime.bigint() - start) / 1e6;

    return {
        result,
        elapsedMs,
        accessPath: catalog.explain(predicate)
    };
}

function demonstrateBTreeOrdering(rows) {
    console.log('\nB-tree-oriented ordered access');

    const sorted = [...rows].sort((left, right) =>
        left.orderDate.localeCompare(right.orderDate)
    );

    const lowerBound = '2026-06-01';
    const upperBound = '2026-07-01';

    const result = sorted.filter(row =>
        row.orderDate >= lowerBound && row.orderDate < upperBound
    );

    console.log(`Date range ${lowerBound} <= date < ${upperBound}`);
    console.log(`Matching rows: ${result.length}`);
    console.log(
        'An ordered index can locate a range and then traverse adjacent keys, '
        + 'which is fundamentally different from a bucketed equality lookup.'
    );
}

function demonstrateHashEquality(rows) {
    console.log('\nHash index for equality');

    const index = new HashIndex();

    for (const row of rows) {
        index.add(row.customerId, row.id);
    }

    const targetCustomer = 2500;
    const matches = index.lookup(targetCustomer);

    console.log(`Customer ${targetCustomer} has ${matches.length} indexed orders.`);
    console.log(
        'Hash access is appropriate for exact equality but does not naturally '
        + 'answer an ordered date range.'
    );
}

function demonstrateCompositeIndex(rows) {
    console.log('\nComposite index and leftmost-prefix behavior');

    const index = new CompositeIndex(['region', 'status']);

    for (const row of rows) {
        index.add(row);
    }

    const southPaid = index.lookup(['south', 'paid']);

    console.log(`Exact composite key south + paid: ${southPaid.length} rows.`);
    console.log(
        'The index encodes the pair as a combined key. A database optimizer '
        + 'can exploit the leading portion according to the engine and index '
        + 'definition, but a predicate on status alone does not have the same '
        + 'direct key alignment as region + status.'
    );
}

function demonstratePartialIndex(rows) {
    console.log('\nPartial index');

    const pending = new PartialIndex(row => row.status === 'pending');

    for (const row of rows) {
        pending.consider(row);
    }

    const pendingCount = rows.filter(row => row.status === 'pending').length;

    assert.equal(pending.size, pendingCount);

    console.log(`Rows represented by pending-only index: ${pending.size}`);
    console.log(`Rows in complete table: ${rows.length}`);
    console.log(
        'A partial index is attractive when the indexed predicate is stable '
        + 'and the indexed subset is materially smaller than the base table.'
    );
}

async function demonstrateEventDrivenMaintenance(rows) {
    console.log('\nEvent-driven index maintenance');

    const bus = new EventBus();
    const customerIndex = new HashIndex();

    bus.on('order.created', order => {
        customerIndex.add(order.customerId, order.id);
    });

    const newOrder = {
        id: rows.length + 1,
        customerId: 2500,
        status: 'pending',
        region: 'south',
        orderDate: '2026-10-07',
        totalCents: 129900
    };

    bus.emit('order.created', newOrder);

    await new Promise(resolve => setImmediate(resolve));

    console.log(
        `After event processing, customer 2500 has `
        + `${customerIndex.lookup(2500).length} newly indexed event entries.`
    );

    console.log(
        'Application-level simulations must still respect the database as '
        + 'the authoritative source of index maintenance in a real system.'
    );
}

function demonstrateWriteTradeoff(rows) {
    console.log('\nRead benefit versus write and storage cost');

    const fields = ['status', 'region', 'customerId', 'orderDate'];

    for (const field of fields) {
        const selectivity = calculateSelectivity(rows, field);
        console.log(
            `${field.padEnd(12)} selectivity=${selectivity.toFixed(6)}`
        );
    }

    console.log(
        'Every maintained index adds work to inserts and to updates that '
        + 'modify indexed values. Index count should therefore be driven by '
        + 'measured access patterns, not by the desire to index every column.'
    );
}

function demonstrateValidation() {
    console.log('\nValidation and failure conditions');

    const badComposite = () => new CompositeIndex([]);

    assert.throws(badComposite, /at least one column/);

    const validDate = /^\d{4}-\d{2}-\d{2}$/;
    const input = '2026-10-07';

    console.log(
        `Date ${input} passes structural validation: ${validDate.test(input)}`
    );

    console.log(
        'Structural validation is not a substitute for database-level '
        + 'constraints and query-plan analysis.'
    );
}

function printSelectivityReport(report) {
    console.log('\nSelectivity report');

    for (const item of report) {
        console.log(
            `${item.field.padEnd(12)} `
            + `distinct=${String(item.distinct).padStart(6)} `
            + `selectivity=${item.selectivity.toFixed(6)}`
        );
    }
}

async function main() {
    const rows = generateOrders(100_000);
    const catalog = new IndexCatalog(rows);

    console.log('Indexing laboratory');
    console.log(`Rows generated: ${rows.length}`);

    demonstrateBTreeOrdering(rows);
    demonstrateHashEquality(rows);
    demonstrateCompositeIndex(rows);
    demonstratePartialIndex(rows);

    const customerQuery = runIndexedQuery(
        rows,
        catalog,
        { customerId: 2500 }
    );

    console.log('\nIndexed customer query');
    console.log(`Access path: ${customerQuery.accessPath}`);
    console.log(`Rows returned: ${customerQuery.result.length}`);
    console.log(`Elapsed: ${customerQuery.elapsedMs.toFixed(3)} ms`);

    const report = selectivityReport(rows);
    printSelectivityReport(report);

    demonstrateWriteTradeoff(rows);
    demonstrateValidation();
    await demonstrateEventDrivenMaintenance(rows);

    console.log('\nComposite query simulation');

    const compositeQuery = runIndexedQuery(
        rows,
        catalog,
        { region: 'south', status: 'paid' }
    );

    console.log(`Access path: ${compositeQuery.accessPath}`);
    console.log(`Rows returned: ${compositeQuery.result.length}`);

    console.log('\nPartial-index predicate simulation');

    const pendingQuery = runIndexedQuery(
        rows,
        catalog,
        {
            status: 'pending',
            orderDateFrom: '2026-10-01'
        }
    );

    console.log(`Access path: ${pendingQuery.accessPath}`);
    console.log(`Rows returned: ${pendingQuery.result.length}`);

    console.log(
        '\nThe simulation separates the logical indexing concepts from the '
        + 'database engine. A production system must validate these assumptions '
        + 'against the optimizer and execution plans of its actual database.'
    );
}

main().catch(error => {
    console.error('Indexing laboratory failed:', error);
    process.exitCode = 1;
});

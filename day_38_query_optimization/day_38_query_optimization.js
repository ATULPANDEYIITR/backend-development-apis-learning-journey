"use strict";

/*
 * Query Optimization Laboratory
 *
 * This Node.js program complements the Python implementation by modeling
 * query-planner behavior as an event-driven workflow.
 *
 * It demonstrates:
 * - sequential versus index access
 * - selectivity
 * - query-plan nodes
 * - EXPLAIN-style inspection
 * - EXPLAIN ANALYZE-style measurements
 * - composite indexes
 * - covering indexes
 * - join strategy selection
 * - cardinality estimation
 * - stale-statistics effects
 * - sargability
 * - merge-oriented diagnostics
 *
 * No external npm packages are required.
 */

const { performance } = require("node:perf_hooks");

// -----------------------------------------------------------------------------
// Domain model
// -----------------------------------------------------------------------------

class Query {
    constructor({
        name,
        tableRows,
        estimatedRows,
        actualRows,
        predicates = [],
        orderBy = [],
        projectedColumns = [],
        joins = [],
    }) {
        if (!name || tableRows <= 0) {
            throw new Error("A query requires a name and positive table cardinality.");
        }

        if (estimatedRows < 0 || actualRows < 0) {
            throw new Error("Row counts cannot be negative.");
        }

        this.name = name;
        this.tableRows = tableRows;
        this.estimatedRows = estimatedRows;
        this.actualRows = actualRows;
        this.predicates = predicates;
        this.orderBy = orderBy;
        this.projectedColumns = projectedColumns;
        this.joins = joins;
    }
}

class IndexDefinition {
    constructor({
        name,
        table,
        columns,
        includedColumns = [],
        unique = false,
    }) {
        if (!name || !table || columns.length === 0) {
            throw new Error("An index needs a name, table, and indexed columns.");
        }

        this.name = name;
        this.table = table;
        this.columns = columns;
        this.includedColumns = includedColumns;
        this.unique = unique;
    }

    covers(columns) {
        const available = new Set([
            ...this.columns,
            ...this.includedColumns,
        ]);

        return columns.every((column) => available.has(column));
    }

    supportsPredicate(predicate) {
        /*
         * B-tree-style equality and range predicates are represented here as
         * searchable predicates. The first indexed column is especially
         * important because a composite index is ordered by its leading key.
         */
        return this.columns[0] === predicate.column;
    }
}

class PlanNode {
    constructor({
        nodeType,
        relation = null,
        estimatedRows = 0,
        actualRows = 0,
        estimatedCost = 0,
        actualTimeMs = 0,
        details = {},
        children = [],
    }) {
        this.nodeType = nodeType;
        this.relation = relation;
        this.estimatedRows = estimatedRows;
        this.actualRows = actualRows;
        this.estimatedCost = estimatedCost;
        this.actualTimeMs = actualTimeMs;
        this.details = details;
        this.children = children;
    }

    estimationRatio() {
        if (this.estimatedRows === 0) {
            return this.actualRows === 0 ? 1 : Infinity;
        }

        return this.actualRows / this.estimatedRows;
    }

    toLines(depth = 0) {
        const indent = "  ".repeat(depth);
        const relation = this.relation ? ` on ${this.relation}` : "";

        const line =
            `${indent}${this.nodeType}${relation} ` +
            `(cost=${this.estimatedCost.toFixed(2)}, ` +
            `rows=${this.estimatedRows}, ` +
            `actual rows=${this.actualRows}, ` +
            `actual time=${this.actualTimeMs.toFixed(3)} ms)`;

        return [
            line,
            ...this.children.flatMap((child) => child.toLines(depth + 1)),
        ];
    }
}

// -----------------------------------------------------------------------------
// Query planner
// -----------------------------------------------------------------------------

class QueryPlanner {
    constructor({ sequentialRowCost = 0.08, indexStartupCost = 2 }) {
        this.sequentialRowCost = sequentialRowCost;
        this.indexStartupCost = indexStartupCost;
        this.indexes = [];
    }

    addIndex(index) {
        this.indexes.push(index);
    }

    findUsefulIndex(query) {
        return this.indexes.find((index) =>
            query.predicates.some((predicate) =>
                index.supportsPredicate(predicate)
            )
        );
    }

    chooseAccessPath(query) {
        const index = this.findUsefulIndex(query);

        const sequentialCost = query.tableRows * this.sequentialRowCost;

        if (!index) {
            return {
                strategy: "SEQUENTIAL SCAN",
                cost: sequentialCost,
                index: null,
            };
        }

        /*
         * This is intentionally a transparent educational cost model rather
         * than PostgreSQL's internal cost formula. It exposes why estimated
         * cardinality matters to plan selection.
         */
        const indexRowCost = 1;
        const indexCost =
            this.indexStartupCost +
            query.estimatedRows * indexRowCost;

        if (indexCost < sequentialCost) {
            return {
                strategy: "INDEX SCAN",
                cost: indexCost,
                index,
            };
        }

        return {
            strategy: "SEQUENTIAL SCAN",
            cost: sequentialCost,
            index: null,
        };
    }

    buildPlan(query) {
        const access = this.chooseAccessPath(query);

        const nodeType = access.strategy === "INDEX SCAN"
            ? "Index Scan"
            : "Seq Scan";

        const indexDetails = access.index
            ? { indexName: access.index.name }
            : {};

        const node = new PlanNode({
            nodeType,
            relation: "orders",
            estimatedRows: query.estimatedRows,
            actualRows: query.actualRows,
            estimatedCost: access.cost,
            actualTimeMs: this.simulateExecution(query, access),
            details: indexDetails,
        });

        let root = node;

        if (query.orderBy.length > 0) {
            /*
             * If the access path does not naturally provide the requested
             * ordering, a separate sort becomes part of the plan.
             */
            const supportsOrder = access.index &&
                query.orderBy.every((column) =>
                    access.index.columns.includes(column)
                );

            if (!supportsOrder) {
                root = new PlanNode({
                    nodeType: "Sort",
                    estimatedRows: query.actualRows,
                    actualRows: query.actualRows,
                    estimatedCost: access.cost +
                        Math.max(1, query.actualRows * Math.log2(query.actualRows + 1) / 1000),
                    actualTimeMs: node.actualTimeMs + 0.5,
                    children: [node],
                    details: { orderBy: query.orderBy },
                });
            }
        }

        if (query.joins.length > 0) {
            /*
             * A highly selective outer relation plus an indexed inner
             * relation is a natural candidate for nested-loop access.
             */
            root = new PlanNode({
                nodeType: query.estimatedRows < query.tableRows * 0.05
                    ? "Nested Loop"
                    : "Hash Join",
                estimatedRows: query.actualRows,
                actualRows: query.actualRows,
                estimatedCost: root.estimatedCost + 12,
                actualTimeMs: root.actualTimeMs + 1.5,
                children: [root],
                details: {
                    join: query.joins,
                },
            });
        }

        return root;
    }

    simulateExecution(query, access) {
        /*
         * The busy loop makes the demonstration observable without requiring
         * a database server. The workload is deliberately small.
         */
        const iterations = Math.min(
            250_000,
            Math.max(2_000, Math.floor(
                access.strategy === "INDEX SCAN"
                    ? Math.max(1, query.actualRows) * 20
                    : query.tableRows / 3
            ))
        );

        const start = performance.now();
        let accumulator = 0;

        for (let i = 0; i < iterations; i += 1) {
            accumulator += (i * 17) % 31;
        }

        if (accumulator < 0) {
            throw new Error("Unreachable calculation guard.");
        }

        return performance.now() - start;
    }

    explain(query) {
        return this.buildPlan(query);
    }

    explainAnalyze(query) {
        const plan = this.buildPlan(query);

        return {
            plan,
            estimateRatio: plan.estimationRatio(),
            warning:
                plan.estimationRatio() > 10 ||
                plan.estimationRatio() < 0.1
                    ? "Large cardinality estimation mismatch detected."
                    : null,
        };
    }
}

// -----------------------------------------------------------------------------
// Sargability analysis
// -----------------------------------------------------------------------------

class PredicateAnalyzer {
    static analyze(predicate) {
        const expression = predicate.expression.toLowerCase();

        if (expression.includes(`lower(`) ||
            expression.includes(`upper(`) ||
            expression.includes(`date(`)) {
            return {
                sargable: false,
                reason:
                    "A function is applied to the filtered column. " +
                    "Consider a range predicate or an expression index " +
                    "when the workload justifies it.",
            };
        }

        if (expression.includes("like '%")) {
            return {
                sargable: false,
                reason:
                    "A leading wildcard prevents ordinary B-tree prefix lookup.",
            };
        }

        return {
            sargable: true,
            reason:
                "The predicate is represented as a direct equality or range condition.",
        };
    }
}

// -----------------------------------------------------------------------------
// Event-driven plan workflow
// -----------------------------------------------------------------------------

class OptimizationEventBus {
    constructor() {
        this.handlers = new Map();
    }

    on(eventName, handler) {
        if (!this.handlers.has(eventName)) {
            this.handlers.set(eventName, []);
        }

        this.handlers.get(eventName).push(handler);
    }

    emit(eventName, payload) {
        const handlers = this.handlers.get(eventName) || [];

        for (const handler of handlers) {
            handler(payload);
        }
    }
}

class OptimizationWorkflow {
    constructor(planner) {
        this.planner = planner;
        this.events = new OptimizationEventBus();
    }

    inspect(query) {
        this.events.emit("queryReceived", query);

        const plan = this.planner.explain(query);
        this.events.emit("planGenerated", plan);

        const analysis = this.planner.explainAnalyze(query);
        this.events.emit("executionMeasured", analysis);

        return analysis;
    }
}

// -----------------------------------------------------------------------------
// Demonstrations
// -----------------------------------------------------------------------------

function printPlan(title, analysis) {
    console.log(`\n=== ${title} ===`);

    for (const line of analysis.plan.toLines()) {
        console.log(line);
    }

    console.log(
        `Estimate ratio at root: ${analysis.estimateRatio.toFixed(2)}x`
    );

    if (analysis.warning) {
        console.log(`Warning: ${analysis.warning}`);
    }
}

function demonstrateSequentialScan(planner, workflow) {
    const query = new Query({
        name: "Broad status filter",
        tableRows: 1_000_000,
        estimatedRows: 300_000,
        actualRows: 295_000,
        predicates: [
            {
                column: "status",
                expression: "status = 'DELIVERED'",
            },
        ],
        projectedColumns: ["order_id", "customer_id", "total_amount"],
    });

    printPlan(
        "Sequential scan for a low-selectivity predicate",
        workflow.inspect(query)
    );
}

function demonstrateIndexScan(planner, workflow) {
    planner.addIndex(new IndexDefinition({
        name: "idx_orders_customer_date",
        table: "orders",
        columns: ["customer_id", "order_date"],
    }));

    const query = new Query({
        name: "Customer order history",
        tableRows: 1_000_000,
        estimatedRows: 900,
        actualRows: 840,
        predicates: [
            {
                column: "customer_id",
                expression: "customer_id = 420",
            },
            {
                column: "order_date",
                expression:
                    "order_date >= '2026-01-01' AND order_date < '2027-01-01'",
            },
        ],
        orderBy: ["order_date"],
        projectedColumns: ["order_id", "order_date", "total_amount"],
    });

    printPlan(
        "Composite index and selective access",
        workflow.inspect(query)
    );
}

function demonstrateCoveringIndex(planner, workflow) {
    const covering = new IndexDefinition({
        name: "idx_orders_customer_covering",
        table: "orders",
        columns: ["customer_id", "order_date"],
        includedColumns: ["total_amount"],
    });

    planner.addIndex(covering);

    const query = new Query({
        name: "Covered customer report",
        tableRows: 1_000_000,
        estimatedRows: 450,
        actualRows: 470,
        predicates: [
            {
                column: "customer_id",
                expression: "customer_id = 88",
            },
        ],
        orderBy: ["order_date"],
        projectedColumns: [
            "customer_id",
            "order_date",
            "total_amount",
        ],
    });

    const index = covering;
    console.log("\n=== Covering-index evaluation ===");
    console.log(
        `Index ${index.name} covers requested columns: ` +
        `${index.covers(query.projectedColumns)}`
    );

    printPlan(
        "Covering-index candidate",
        workflow.inspect(query)
    );
}

function demonstrateJoinPlanning(planner, workflow) {
    planner.addIndex(new IndexDefinition({
        name: "idx_orders_customer_id",
        table: "orders",
        columns: ["customer_id"],
    }));

    const query = new Query({
        name: "Regional customer order report",
        tableRows: 1_000_000,
        estimatedRows: 12_000,
        actualRows: 13_400,
        predicates: [
            {
                column: "region",
                expression: "customers.region = 'North'",
            },
        ],
        joins: [
            "customers.customer_id = orders.customer_id",
        ],
        projectedColumns: ["region", "customer_tier"],
    });

    printPlan(
        "Join strategy influenced by cardinality",
        workflow.inspect(query)
    );
}

function demonstrateStatisticsMismatch() {
    console.log("\n=== Statistics mismatch ===");

    const statistics = {
        tableRows: 1_000_000,
        distinctCustomerIds: 100_000,
        mostCommonCustomerFrequency: 0.03,
    };

    const rareEstimate =
        statistics.tableRows / statistics.distinctCustomerIds;

    const commonEstimate =
        statistics.tableRows *
        statistics.mostCommonCustomerFrequency;

    console.log(`Estimated rare customer rows: ${rareEstimate.toFixed(0)}`);
    console.log(`Estimated common customer rows: ${commonEstimate.toFixed(0)}`);

    const staleEstimate = 10;
    const actualRows = 30_000;

    console.log(`Stale estimate: ${staleEstimate}`);
    console.log(`Actual rows: ${actualRows}`);
    console.log(
        "A planner using stale statistics can select an access path that " +
        "looks cheap for ten rows but becomes expensive for thousands."
    );
}

function demonstrateSargability() {
    console.log("\n=== Sargability ===");

    const predicates = [
        {
            expression: "order_date >= '2026-01-01' AND order_date < '2027-01-01'",
        },
        {
            expression: "LOWER(sales_channel) = 'web'",
        },
        {
            expression: "customer_name LIKE '%ENTERPRISE%'",
        },
    ];

    for (const predicate of predicates) {
        const result = PredicateAnalyzer.analyze(predicate);

        console.log(`Predicate: ${predicate.expression}`);
        console.log(`Sargable: ${result.sargable}`);
        console.log(`Reason: ${result.reason}`);
    }
}

function demonstrateEventDrivenPlanning(planner) {
    console.log("\n=== Event-driven planning workflow ===");

    const workflow = new OptimizationWorkflow(planner);

    workflow.events.on("queryReceived", (query) => {
        console.log(`Query received: ${query.name}`);
    });

    workflow.events.on("planGenerated", (plan) => {
        console.log(`Plan generated: ${plan.nodeType}`);
    });

    workflow.events.on("executionMeasured", (analysis) => {
        console.log(
            `Measured execution time: ${analysis.plan.actualTimeMs.toFixed(3)} ms`
        );
    });

    const query = new Query({
        name: "Selective customer lookup",
        tableRows: 500_000,
        estimatedRows: 5,
        actualRows: 4,
        predicates: [
            {
                column: "customer_id",
                expression: "customer_id = 42",
            },
        ],
    });

    const result = workflow.inspect(query);

    for (const line of result.plan.toLines()) {
        console.log(line);
    }
}

// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------

function main() {
    console.log("QUERY OPTIMIZATION LABORATORY");
    console.log("========================================");

    const planner = new QueryPlanner({
        sequentialRowCost: 0.08,
        indexStartupCost: 2,
    });

    const workflow = new OptimizationWorkflow(planner);

    demonstrateSequentialScan(planner, workflow);
    demonstrateIndexScan(planner, workflow);
    demonstrateCoveringIndex(planner, workflow);
    demonstrateJoinPlanning(planner, workflow);
    demonstrateStatisticsMismatch();
    demonstrateSargability();
    demonstrateEventDrivenPlanning(planner);

    console.log("\n=== Operational rule ===");
    console.log(
        "An index is not an optimization by itself. The useful question is " +
        "whether the planner's estimated and observed costs justify the access path."
    );
}

main();

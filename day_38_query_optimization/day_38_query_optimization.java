import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Enterprise Query Optimization Governance Model.
 *
 * The program models how an enterprise reporting service evaluates query
 * candidates before production deployment.
 *
 * The implementation deliberately uses Java-specific domain abstractions:
 * records, enums, immutable views, validation, services, exceptions, and
 * explicit policy objects.
 *
 * The cost model is educational rather than PostgreSQL's internal formula.
 * Its purpose is to make cardinality estimation, access-path selection,
 * index coverage, ordering, and join strategy explicit.
 */
public class QueryOptimizationEnterpriseDemo {

    enum PredicateType {
        EQUALITY,
        RANGE,
        EXPRESSION,
        PREFIX_LIKE
    }

    enum AccessPath {
        SEQUENTIAL_SCAN,
        INDEX_SCAN,
        INDEX_ONLY_SCAN,
        BITMAP_HEAP_SCAN
    }

    enum JoinStrategy {
        NONE,
        NESTED_LOOP,
        HASH_JOIN,
        MERGE_JOIN
    }

    record Predicate(
        String column,
        PredicateType type,
        double selectivity
    ) {
        Predicate {
            Objects.requireNonNull(column, "column");
            Objects.requireNonNull(type, "type");

            if (column.isBlank()) {
                throw new IllegalArgumentException("Column cannot be blank.");
            }

            if (selectivity < 0 || selectivity > 1) {
                throw new IllegalArgumentException(
                    "Selectivity must be between 0 and 1."
                );
            }
        }
    }

    record IndexDefinition(
        String name,
        String table,
        List<String> keyColumns,
        List<String> includedColumns
    ) {
        IndexDefinition {
            Objects.requireNonNull(name, "name");
            Objects.requireNonNull(table, "table");
            Objects.requireNonNull(keyColumns, "keyColumns");
            Objects.requireNonNull(includedColumns, "includedColumns");

            if (name.isBlank() || table.isBlank() || keyColumns.isEmpty()) {
                throw new IllegalArgumentException(
                    "An index requires a name, table, and key columns."
                );
            }

            keyColumns = List.copyOf(keyColumns);
            includedColumns = List.copyOf(includedColumns);
        }

        boolean supports(Predicate predicate) {
            /*
             * A normal B-tree index can directly exploit the leading key.
             * Expression predicates require a matching expression index or
             * another specialized access strategy.
             */
            return !keyColumns.isEmpty()
                && keyColumns.get(0).equals(predicate.column())
                && predicate.type() != PredicateType.EXPRESSION;
        }

        boolean covers(List<String> requiredColumns) {
            for (String required : requiredColumns) {
                if (!keyColumns.contains(required)
                        && !includedColumns.contains(required)) {
                    return false;
                }
            }

            return true;
        }
    }

    record QueryRequest(
        String name,
        String table,
        long tableRows,
        long estimatedRows,
        long actualRows,
        List<Predicate> predicates,
        List<String> projectedColumns,
        List<String> orderColumns,
        boolean hasJoin
    ) {
        QueryRequest {
            Objects.requireNonNull(name, "name");
            Objects.requireNonNull(table, "table");
            Objects.requireNonNull(predicates, "predicates");
            Objects.requireNonNull(projectedColumns, "projectedColumns");
            Objects.requireNonNull(orderColumns, "orderColumns");

            if (tableRows <= 0) {
                throw new IllegalArgumentException(
                    "Table cardinality must be positive."
                );
            }

            if (estimatedRows < 0 || actualRows < 0) {
                throw new IllegalArgumentException(
                    "Row counts cannot be negative."
                );
            }

            predicates = List.copyOf(predicates);
            projectedColumns = List.copyOf(projectedColumns);
            orderColumns = List.copyOf(orderColumns);
        }
    }

    record PlanNode(
        String operation,
        AccessPath accessPath,
        JoinStrategy joinStrategy,
        long estimatedRows,
        long actualRows,
        double estimatedCost,
        double actualTimeMs,
        List<String> details,
        List<PlanNode> children
    ) {
        PlanNode {
            details = List.copyOf(details);
            children = List.copyOf(children);
        }

        double estimationRatio() {
            if (estimatedRows == 0) {
                return actualRows == 0
                    ? 1.0
                    : Double.POSITIVE_INFINITY;
            }

            return (double) actualRows / estimatedRows;
        }

        void print(String indent) {
            System.out.printf(
                "%s%s [access=%s, join=%s, cost=%.2f, estimated rows=%d, "
                    + "actual rows=%d, actual time=%.3f ms]%n",
                indent,
                operation,
                accessPath,
                joinStrategy,
                estimatedCost,
                estimatedRows,
                actualRows,
                actualTimeMs
            );

            for (String detail : details) {
                System.out.println(indent + "  " + detail);
            }

            for (PlanNode child : children) {
                child.print(indent + "  ");
            }
        }
    }

    static class InvalidQueryException extends RuntimeException {
        InvalidQueryException(String message) {
            super(message);
        }
    }

    static class QueryPlanner {
        private final double sequentialRowCost;
        private final double indexStartupCost;
        private final double indexRowCost;
        private final List<IndexDefinition> indexes;

        QueryPlanner(
            double sequentialRowCost,
            double indexStartupCost,
            double indexRowCost
        ) {
            this.sequentialRowCost = sequentialRowCost;
            this.indexStartupCost = indexStartupCost;
            this.indexRowCost = indexRowCost;
            this.indexes = new ArrayList<>();
        }

        void registerIndex(IndexDefinition index) {
            indexes.add(index);
        }

        Optional<IndexDefinition> findUsefulIndex(QueryRequest query) {
            return indexes.stream()
                .filter(index ->
                    query.predicates().stream().anyMatch(index::supports)
                )
                .findFirst();
        }

        PlanNode plan(QueryRequest query) {
            validate(query);

            double sequentialCost =
                query.tableRows() * sequentialRowCost;

            Optional<IndexDefinition> candidate =
                findUsefulIndex(query);

            double indexCost =
                indexStartupCost +
                query.estimatedRows() * indexRowCost;

            boolean useIndex =
                candidate.isPresent() &&
                indexCost < sequentialCost;

            PlanNode accessNode;

            if (!useIndex) {
                accessNode = new PlanNode(
                    "Sequential relation scan",
                    AccessPath.SEQUENTIAL_SCAN,
                    JoinStrategy.NONE,
                    query.estimatedRows(),
                    query.actualRows(),
                    sequentialCost,
                    simulateTime(query, false),
                    List.of(
                        "The estimated result is broad enough that scanning "
                            + "the relation is cheaper in this simplified model."
                    ),
                    List.of()
                );
            } else {
                IndexDefinition index = candidate.orElseThrow();

                boolean covering =
                    index.covers(query.projectedColumns());

                AccessPath path = covering
                    ? AccessPath.INDEX_ONLY_SCAN
                    : AccessPath.INDEX_SCAN;

                accessNode = new PlanNode(
                    covering
                        ? "Covered index access"
                        : "Indexed relation access",
                    path,
                    JoinStrategy.NONE,
                    query.estimatedRows(),
                    query.actualRows(),
                    indexCost,
                    simulateTime(query, true),
                    List.of(
                        "Index: " + index.name(),
                        covering
                            ? "Projected columns are available from index entries."
                            : "The base relation may still be visited for projected columns."
                    ),
                    List.of()
                );
            }

            PlanNode current = accessNode;

            if (!query.orderColumns().isEmpty()) {
                boolean orderedByIndex =
                    candidate.isPresent()
                    && candidate.get().keyColumns().contains(
                        query.orderColumns().get(0)
                    );

                if (!orderedByIndex) {
                    double sortCost =
                        Math.max(
                            0.5,
                            query.actualRows()
                                * Math.log(query.actualRows() + 1)
                                * 0.0005
                        );

                    current = new PlanNode(
                        "Explicit sort",
                        AccessPath.SEQUENTIAL_SCAN,
                        JoinStrategy.NONE,
                        query.actualRows(),
                        query.actualRows(),
                        current.estimatedCost() + sortCost,
                        current.actualTimeMs() + sortCost,
                        List.of(
                            "Requested ordering is not guaranteed by the selected access path."
                        ),
                        List.of(current)
                    );
                }
            }

            if (query.hasJoin()) {
                boolean selective =
                    query.estimatedRows()
                        < query.tableRows() * 0.05;

                JoinStrategy strategy =
                    selective
                        ? JoinStrategy.NESTED_LOOP
                        : JoinStrategy.HASH_JOIN;

                current = new PlanNode(
                    strategy == JoinStrategy.NESTED_LOOP
                        ? "Nested-loop join"
                        : "Hash join",
                    current.accessPath(),
                    strategy,
                    query.actualRows(),
                    query.actualRows(),
                    current.estimatedCost() + 15,
                    current.actualTimeMs() + 0.8,
                    List.of(
                        strategy == JoinStrategy.NESTED_LOOP
                            ? "Small outer cardinality favors repeated indexed probes."
                            : "Large join input makes repeated probing comparatively expensive."
                    ),
                    List.of(current)
                );
            }

            return current;
        }

        private void validate(QueryRequest query) {
            if (query.name().isBlank() || query.table().isBlank()) {
                throw new InvalidQueryException(
                    "Query name and table are required."
                );
            }

            for (Predicate predicate : query.predicates()) {
                if (predicate.type() == PredicateType.PREFIX_LIKE
                        && predicate.selectivity() > 0.5) {
                    throw new InvalidQueryException(
                        "A broad prefix search requires explicit workload review."
                    );
                }
            }
        }

        private double simulateTime(
            QueryRequest query,
            boolean indexed
        ) {
            long work = indexed
                ? Math.max(1, query.actualRows())
                : query.tableRows();

            double accumulator = 0;

            for (long i = 0; i < Math.min(200_000, work); i++) {
                accumulator += (i * 31) % 101;
            }

            return indexed
                ? 0.10 + accumulator * 0.000001
                : 0.75 + accumulator * 0.0000005;
        }
    }

    static class OptimizationService {
        private final QueryPlanner planner;

        OptimizationService(QueryPlanner planner) {
            this.planner = planner;
        }

        void inspect(QueryRequest query) {
            System.out.println("\nEXPLAIN");
            System.out.println("-------");
            System.out.println(query.name());

            PlanNode plan = planner.plan(query);
            plan.print("");

            System.out.printf(
                "Root actual/estimated ratio: %.2fx%n",
                plan.estimationRatio()
            );

            System.out.println("\nEXPLAIN ANALYZE interpretation");
            System.out.println("------------------------------");

            if (plan.estimationRatio() > 10
                    || plan.estimationRatio() < 0.1) {
                System.out.println(
                    "The cardinality estimate is substantially wrong. "
                        + "Investigate statistics, data skew, and predicate selectivity."
                );
            } else {
                System.out.println(
                    "The root estimate is reasonably close to observed cardinality."
                );
            }

            if (plan.accessPath() == AccessPath.SEQUENTIAL_SCAN) {
                System.out.println(
                    "Sequential access was selected. Do not assume this is a problem; "
                        + "a broad predicate can make a table scan cheaper."
                );
            }

            if (plan.accessPath() == AccessPath.INDEX_ONLY_SCAN) {
                System.out.println(
                    "The selected index contains the requested columns, making "
                        + "index-only access possible under suitable visibility conditions."
                );
            }
        }
    }

    static QueryRequest selectiveCustomerQuery() {
        return new QueryRequest(
            "Customer order history",
            "orders",
            1_000_000,
            900,
            840,
            List.of(
                new Predicate(
                    "customer_id",
                    PredicateType.EQUALITY,
                    0.0009
                ),
                new Predicate(
                    "order_date",
                    PredicateType.RANGE,
                    0.02
                )
            ),
            List.of(
                "customer_id",
                "order_date",
                "total_amount"
            ),
            List.of("order_date"),
            false
        );
    }

    static QueryRequest broadStatusQuery() {
        return new QueryRequest(
            "Delivered order population",
            "orders",
            1_000_000,
            300_000,
            295_000,
            List.of(
                new Predicate(
                    "status",
                    PredicateType.EQUALITY,
                    0.30
                )
            ),
            List.of(
                "order_id",
                "customer_id",
                "total_amount"
            ),
            Collections.emptyList(),
            false
        );
    }

    static QueryRequest regionalRevenueQuery() {
        return new QueryRequest(
            "Regional customer revenue",
            "orders",
            1_000_000,
            20_000,
            22_500,
            List.of(
                new Predicate(
                    "region",
                    PredicateType.EQUALITY,
                    0.02
                )
            ),
            List.of(
                "customer_id",
                "total_amount"
            ),
            List.of("customer_id"),
            true
        );
    }

    public static void main(String[] args) {
        QueryPlanner planner = new QueryPlanner(
            0.08,
            2.0,
            1.0
        );

        planner.registerIndex(
            new IndexDefinition(
                "idx_orders_customer_date",
                "orders",
                List.of("customer_id", "order_date"),
                List.of()
            )
        );

        planner.registerIndex(
            new IndexDefinition(
                "idx_orders_customer_covering",
                "orders",
                List.of("customer_id", "order_date"),
                List.of("total_amount", "status")
            )
        );

        planner.registerIndex(
            new IndexDefinition(
                "idx_orders_status",
                "orders",
                List.of("status"),
                List.of()
            )
        );

        OptimizationService service =
            new OptimizationService(planner);

        System.out.println("ENTERPRISE QUERY OPTIMIZATION MODEL");
        System.out.println("===================================");

        service.inspect(selectiveCustomerQuery());
        service.inspect(broadStatusQuery());
        service.inspect(regionalRevenueQuery());

        System.out.println("\nSTATISTICS FAILURE SCENARIO");
        System.out.println("===========================");

        QueryRequest skewedQuery = new QueryRequest(
            "Skewed customer lookup",
            "orders",
            1_000_000,
            10,
            30_000,
            List.of(
                new Predicate(
                    "customer_id",
                    PredicateType.EQUALITY,
                    0.00001
                )
            ),
            List.of("order_id"),
            Collections.emptyList(),
            false
        );

        service.inspect(skewedQuery);

        System.out.println("\nDOMAIN DESIGN PRINCIPLE");
        System.out.println("========================");
        System.out.println(
            "Query optimization is evidence-driven: compare estimated "
                + "cardinality, access paths, actual execution behavior, "
                + "data distribution, and workload requirements before changing SQL."
        );
    }
}

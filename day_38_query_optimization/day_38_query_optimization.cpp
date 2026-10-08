#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <vector>

/*
 * Repository-free query optimization case study:
 *
 * A transaction-reporting system needs to determine the best access path for
 * customer order searches. The engine models:
 *
 * - sequential scans
 * - index scans
 * - index-only scans
 * - bitmap-oriented access
 * - composite indexes
 * - cardinality estimation
 * - join selection
 * - sorting
 * - aggregation
 * - EXPLAIN-style plan trees
 * - EXPLAIN ANALYZE-style actual measurements
 *
 * The cost model is deliberately simplified. It is designed to make the
 * relationship between selectivity, cardinality, and access-path choice
 * explicit rather than pretending to reproduce PostgreSQL's internal formula.
 */

enum class PredicateType {
    Equality,
    Range,
    Expression,
    PrefixLike
};

struct Predicate {
    std::string column;
    PredicateType type;
    double selectivity;
    bool estimated;
};

struct Index {
    std::string name;
    std::string table;
    std::vector<std::string> keyColumns;
    std::vector<std::string> includedColumns;

    bool supports(const Predicate& predicate) const {
        if (keyColumns.empty()) {
            return false;
        }

        /*
         * The leading column of a B-tree composite index is the first
         * directly searchable key in this simplified model.
         */
        return keyColumns.front() == predicate.column &&
               predicate.type != PredicateType::Expression;
    }

    bool covers(const std::vector<std::string>& requiredColumns) const {
        std::set<std::string> available(
            keyColumns.begin(),
            keyColumns.end()
        );

        available.insert(
            includedColumns.begin(),
            includedColumns.end()
        );

        return std::all_of(
            requiredColumns.begin(),
            requiredColumns.end(),
            [&](const std::string& column) {
                return available.count(column) > 0;
            }
        );
    }
};

struct Query {
    std::string name;
    std::string table;
    std::size_t tableRows;
    std::size_t estimatedRows;
    std::size_t actualRows;
    std::vector<Predicate> predicates;
    std::vector<std::string> projectedColumns;
    std::vector<std::string> orderColumns;
    bool hasJoin;
};

struct PlanNode {
    std::string nodeType;
    std::string relation;
    double startupCost;
    double totalCost;
    std::size_t estimatedRows;
    std::size_t actualRows;
    double actualTimeMs;
    std::vector<std::string> attributes;
    std::vector<PlanNode> children;

    void print(std::size_t depth = 0) const {
        std::cout << std::string(depth * 2, ' ')
                  << nodeType;

        if (!relation.empty()) {
            std::cout << " on " << relation;
        }

        std::cout << "  (cost="
                  << std::fixed << std::setprecision(2)
                  << startupCost << ".." << totalCost
                  << ", rows=" << estimatedRows
                  << ", actual rows=" << actualRows
                  << ", actual time=" << actualTimeMs << " ms)\n";

        for (const auto& attribute : attributes) {
            std::cout << std::string(depth * 2 + 2, ' ')
                      << attribute << '\n';
        }

        for (const auto& child : children) {
            child.print(depth + 1);
        }
    }

    double estimationRatio() const {
        if (estimatedRows == 0) {
            return actualRows == 0
                ? 1.0
                : std::numeric_limits<double>::infinity();
        }

        return static_cast<double>(actualRows) /
               static_cast<double>(estimatedRows);
    }
};

class QueryOptimizer {
private:
    double sequentialRowCost_;
    double indexStartupCost_;
    double indexRowCost_;
    std::vector<Index> indexes_;

public:
    QueryOptimizer(
        double sequentialRowCost,
        double indexStartupCost,
        double indexRowCost
    )
        : sequentialRowCost_(sequentialRowCost),
          indexStartupCost_(indexStartupCost),
          indexRowCost_(indexRowCost) {}

    void addIndex(const Index& index) {
        indexes_.push_back(index);
    }

    const Index* findUsefulIndex(const Query& query) const {
        for (const auto& index : indexes_) {
            for (const auto& predicate : query.predicates) {
                if (index.supports(predicate)) {
                    return &index;
                }
            }
        }

        return nullptr;
    }

    PlanNode buildPlan(const Query& query) const {
        const Index* usefulIndex = findUsefulIndex(query);

        const double sequentialCost =
            static_cast<double>(query.tableRows) *
            sequentialRowCost_;

        const double indexCost =
            indexStartupCost_ +
            static_cast<double>(query.estimatedRows) *
            indexRowCost_;

        bool useIndex =
            usefulIndex != nullptr &&
            indexCost < sequentialCost;

        PlanNode accessNode;

        if (!useIndex) {
            accessNode = PlanNode{
                "Seq Scan",
                query.table,
                0.0,
                sequentialCost,
                query.estimatedRows,
                query.actualRows,
                simulatedTime(query, false),
                {"Filter evaluated while scanning the relation"},
                {}
            };
        } else {
            const bool covering =
                usefulIndex->covers(query.projectedColumns);

            accessNode = PlanNode{
                covering ? "Index Only Scan" : "Index Scan",
                query.table,
                indexStartupCost_,
                indexCost,
                query.estimatedRows,
                query.actualRows,
                simulatedTime(query, true),
                {
                    "Index: " + usefulIndex->name,
                    covering
                        ? "Required projected columns are available from the index"
                        : "Base-table row lookup may still be required"
                },
                {}
            };
        }

        PlanNode root = accessNode;

        /*
         * An ordering requirement can create an additional sort unless the
         * selected access path naturally produces the desired order.
         */
        if (!query.orderColumns.empty()) {
            bool naturallyOrdered = false;

            if (usefulIndex != nullptr) {
                naturallyOrdered =
                    !usefulIndex->keyColumns.empty() &&
                    usefulIndex->keyColumns.front() ==
                        query.orderColumns.front();
            }

            if (!naturallyOrdered) {
                double sortCost =
                    static_cast<double>(query.actualRows) *
                    std::log2(
                        static_cast<double>(query.actualRows) + 1.0
                    ) *
                    0.0005;

                root = PlanNode{
                    "Sort",
                    "",
                    accessNode.totalCost,
                    accessNode.totalCost + sortCost,
                    query.actualRows,
                    query.actualRows,
                    accessNode.actualTimeMs + sortCost,
                    {
                        "Required order: " +
                        join(query.orderColumns, ", ")
                    },
                    {accessNode}
                };
            }
        }

        /*
         * For a selective outer relation with an indexed inner relation,
         * nested-loop access can be attractive. For a larger relation,
         * a hash-oriented strategy can reduce repeated inner probes.
         */
        if (query.hasJoin) {
            const bool selective =
                query.estimatedRows <
                query.tableRows * 0.05;

            root = PlanNode{
                selective ? "Nested Loop" : "Hash Join",
                "",
                root.startupCost,
                root.totalCost + 15.0,
                query.actualRows,
                query.actualRows,
                root.actualTimeMs + 0.8,
                {
                    selective
                        ? "Selective outer relation favors repeated indexed probes"
                        : "Larger join input favors building and probing a hash structure"
                },
                {root}
            };
        }

        return root;
    }

    static double simulatedTime(
        const Query& query,
        bool indexed
    ) {
        const double work =
            indexed
                ? std::max(1.0, static_cast<double>(query.actualRows))
                : static_cast<double>(query.tableRows);

        /*
         * The case study uses deterministic arithmetic rather than sleeping,
         * so output remains reproducible and does not depend on wall-clock
         * scheduling.
         */
        volatile double accumulator = 0.0;

        const std::size_t iterations =
            std::min<std::size_t>(
                200'000,
                std::max<std::size_t>(
                    2'000,
                    static_cast<std::size_t>(work / 2.0)
                )
            );

        for (std::size_t i = 0; i < iterations; ++i) {
            accumulator += std::fmod(
                static_cast<double>(i * 17),
                97.0
            );
        }

        return indexed
            ? 0.15 + accumulator * 0.0000001
            : 0.75 + accumulator * 0.0000002;
    }

    static std::string join(
        const std::vector<std::string>& values,
        const std::string& separator
    ) {
        std::ostringstream output;

        for (std::size_t i = 0; i < values.size(); ++i) {
            if (i > 0) {
                output << separator;
            }

            output << values[i];
        }

        return output.str();
    }
};

class PlanAnalyzer {
public:
    static void printExplain(const QueryOptimizer& optimizer, const Query& query) {
        std::cout << "\nEXPLAIN: " << query.name << '\n';

        PlanNode plan = optimizer.buildPlan(query);
        plan.print();

        std::cout
            << "Planner estimate ratio: "
            << std::fixed << std::setprecision(2)
            << plan.estimationRatio()
            << "x\n";
    }

    static void printExplainAnalyze(
        const QueryOptimizer& optimizer,
        const Query& query
    ) {
        std::cout << "\nEXPLAIN ANALYZE: " << query.name << '\n';

        PlanNode plan = optimizer.buildPlan(query);
        plan.print();

        const double ratio = plan.estimationRatio();

        if (ratio > 10.0 || ratio < 0.1) {
            std::cout
                << "Diagnostic: substantial cardinality estimation error. "
                << "Investigate statistics and data distribution.\n";
        } else {
            std::cout
                << "Diagnostic: estimated and actual row counts are "
                << "reasonably aligned.\n";
        }
    }
};

class QueryDesignAnalyzer {
public:
    static void inspectPredicate(const Predicate& predicate) {
        std::cout
            << "\nPredicate on " << predicate.column << ": ";

        switch (predicate.type) {
            case PredicateType::Equality:
                std::cout << "equality";
                break;

            case PredicateType::Range:
                std::cout << "range";
                break;

            case PredicateType::Expression:
                std::cout << "expression";
                break;

            case PredicateType::PrefixLike:
                std::cout << "prefix LIKE";
                break;
        }

        std::cout
            << ", estimated selectivity="
            << std::fixed << std::setprecision(4)
            << predicate.selectivity
            << '\n';

        if (predicate.type == PredicateType::Expression) {
            std::cout
                << "  The expression may prevent direct use of a normal "
                << "index on the underlying column.\n";
        }

        if (predicate.selectivity > 0.30) {
            std::cout
                << "  Broad predicate: sequential access may be competitive.\n";
        }

        if (predicate.selectivity < 0.01) {
            std::cout
                << "  Highly selective predicate: index access deserves inspection.\n";
        }
    }
};

void runCaseStudy() {
    QueryOptimizer optimizer(
        0.08,  // sequential row cost
        2.0,   // index startup cost
        1.0    // index row cost
    );

    optimizer.addIndex(Index{
        "idx_orders_customer_date",
        "orders",
        {"customer_id", "order_date"},
        {}
    });

    optimizer.addIndex(Index{
        "idx_orders_customer_covering",
        "orders",
        {"customer_id", "order_date"},
        {"total_amount", "status"}
    });

    optimizer.addIndex(Index{
        "idx_orders_status",
        "orders",
        {"status"},
        {}
    });

    Query selectiveCustomer{
        "Selective customer history",
        "orders",
        1'000'000,
        750,
        810,
        {
            {
                "customer_id",
                PredicateType::Equality,
                0.00075,
                true
            },
            {
                "order_date",
                PredicateType::Range,
                0.02,
                true
            }
        },
        {"customer_id", "order_date", "total_amount"},
        {"order_date"},
        false
    };

    Query broadStatus{
        "Broad delivered-order report",
        "orders",
        1'000'000,
        300'000,
        295'000,
        {
            {
                "status",
                PredicateType::Equality,
                0.30,
                true
            }
        },
        {"order_id", "customer_id", "total_amount"},
        {},
        false
    };

    Query regionalJoin{
        "Regional revenue report",
        "orders",
        1'000'000,
        25'000,
        28'000,
        {
            {
                "region",
                PredicateType::Equality,
                0.04,
                true
            }
        },
        {"customer_id", "total_amount"},
        {"customer_id"},
        true
    };

    std::cout << "QUERY OPTIMIZATION CASE STUDY\n";
    std::cout << "============================\n";

    for (const auto& predicate : selectiveCustomer.predicates) {
        QueryDesignAnalyzer::inspectPredicate(predicate);
    }

    PlanAnalyzer::printExplain(optimizer, selectiveCustomer);
    PlanAnalyzer::printExplainAnalyze(optimizer, selectiveCustomer);

    for (const auto& predicate : broadStatus.predicates) {
        QueryDesignAnalyzer::inspectPredicate(predicate);
    }

    PlanAnalyzer::printExplain(optimizer, broadStatus);
    PlanAnalyzer::printExplainAnalyze(optimizer, broadStatus);

    PlanAnalyzer::printExplain(optimizer, regionalJoin);
    PlanAnalyzer::printExplainAnalyze(optimizer, regionalJoin);

    std::cout << "\nSARGABILITY CASE\n";
    std::cout << "================\n";

    Query expressionPredicate{
        "Expression-filtered channel report",
        "orders",
        1'000'000,
        250'000,
        248'000,
        {
            {
                "sales_channel",
                PredicateType::Expression,
                0.25,
                true
            }
        },
        {"order_id", "sales_channel"},
        {},
        false
    };

    QueryDesignAnalyzer::inspectPredicate(
        expressionPredicate.predicates.front()
    );

    PlanAnalyzer::printExplainAnalyze(
        optimizer,
        expressionPredicate
    );

    std::cout << "\nSTATISTICS FAILURE SCENARIO\n";
    std::cout << "===========================\n";

    Query staleStatistics{
        "Unexpected high-cardinality customer",
        "orders",
        1'000'000,
        10,
        35'000,
        {
            {
                "customer_id",
                PredicateType::Equality,
                0.00001,
                true
            }
        },
        {"order_id"},
        {},
        false
    };

    PlanNode stalePlan = optimizer.buildPlan(staleStatistics);
    stalePlan.print();

    std::cout
        << "Actual/estimated ratio: "
        << stalePlan.estimationRatio()
        << "x\n";

    std::cout
        << "A large mismatch indicates that planner statistics should be "
        << "investigated before assuming the SQL text or index definition "
        << "is the sole problem.\n";
}

int main() {
    try {
        runCaseStudy();
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}

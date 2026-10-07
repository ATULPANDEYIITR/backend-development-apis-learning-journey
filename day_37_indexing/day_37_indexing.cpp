#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Repository Analytics Indexing Engine
 *
 * This case study models a realistic analytics service for a commerce
 * repository. The service receives many order records and must support:
 *
 * - exact customer lookup
 * - date-range lookup
 * - region/status lookup
 * - lookup of operationally active orders
 *
 * The implementation deliberately represents different index structures:
 * - std::map models an ordered B-tree-like access path
 * - std::unordered_map models a hash access path
 * - a nested map models a composite key
 * - a filtered vector models a partial index
 *
 * The structures are educational models of database access paths, not
 * replacements for a database optimizer.
 */

struct Order {
    int id{};
    int customerId{};
    std::string region;
    std::string status;
    std::string orderDate;
    long long totalCents{};
};

struct QueryStats {
    std::size_t candidates{};
    std::size_t matches{};
    double elapsedMs{};
};

class BTreeLikeDateIndex {
private:
    std::map<std::string, std::vector<int>> entries;

public:
    void insert(const Order& order) {
        entries[order.orderDate].push_back(order.id);
    }

    std::vector<int> rangeQuery(
        const std::string& start,
        const std::string& end
    ) const {
        std::vector<int> result;

        auto first = entries.lower_bound(start);
        auto last = entries.lower_bound(end);

        for (auto it = first; it != last; ++it) {
            result.insert(
                result.end(),
                it->second.begin(),
                it->second.end()
            );
        }

        return result;
    }
};

class HashCustomerIndex {
private:
    std::unordered_map<int, std::vector<int>> entries;

public:
    void insert(const Order& order) {
        entries[order.customerId].push_back(order.id);
    }

    const std::vector<int>& lookup(int customerId) const {
        static const std::vector<int> empty;
        auto it = entries.find(customerId);
        return it == entries.end() ? empty : it->second;
    }
};

class CompositeRegionStatusIndex {
private:
    std::map<std::pair<std::string, std::string>, std::vector<int>> entries;

public:
    void insert(const Order& order) {
        entries[{order.region, order.status}].push_back(order.id);
    }

    const std::vector<int>& lookup(
        const std::string& region,
        const std::string& status
    ) const {
        static const std::vector<int> empty;
        auto it = entries.find({region, status});
        return it == entries.end() ? empty : it->second;
    }
};

class PartialPendingIndex {
private:
    std::vector<int> pendingOrderIds;

public:
    void insert(const Order& order) {
        if (order.status == "pending") {
            pendingOrderIds.push_back(order.id);
        }
    }

    const std::vector<int>& entries() const {
        return pendingOrderIds;
    }
};

class OrderIndexEngine {
private:
    std::vector<Order> orders;
    std::unordered_map<int, std::size_t> byId;

    BTreeLikeDateIndex dateIndex;
    HashCustomerIndex customerIndex;
    CompositeRegionStatusIndex regionStatusIndex;
    PartialPendingIndex pendingIndex;

public:
    explicit OrderIndexEngine(std::vector<Order> source)
        : orders(std::move(source)) {

        byId.reserve(orders.size());

        for (std::size_t position = 0; position < orders.size(); ++position) {
            const Order& order = orders[position];

            if (byId.contains(order.id)) {
                throw std::invalid_argument("Duplicate order ID");
            }

            byId.emplace(order.id, position);
            dateIndex.insert(order);
            customerIndex.insert(order);
            regionStatusIndex.insert(order);
            pendingIndex.insert(order);
        }
    }

    const Order& getOrder(int orderId) const {
        auto it = byId.find(orderId);

        if (it == byId.end()) {
            throw std::out_of_range("Order ID does not exist");
        }

        return orders[it->second];
    }

    QueryStats customerLookup(int customerId) const {
        auto start = std::chrono::steady_clock::now();

        const auto& ids = customerIndex.lookup(customerId);
        std::size_t matches = 0;

        for (int id : ids) {
            const Order& order = getOrder(id);
            if (order.customerId == customerId) {
                ++matches;
            }
        }

        auto end = std::chrono::steady_clock::now();

        return {
            ids.size(),
            matches,
            std::chrono::duration<double, std::milli>(end - start).count()
        };
    }

    QueryStats dateRangeLookup(
        const std::string& startDate,
        const std::string& endDate
    ) const {
        auto start = std::chrono::steady_clock::now();

        const auto ids = dateIndex.rangeQuery(startDate, endDate);
        std::size_t matches = 0;

        for (int id : ids) {
            const Order& order = getOrder(id);

            if (
                order.orderDate >= startDate &&
                order.orderDate < endDate
            ) {
                ++matches;
            }
        }

        auto end = std::chrono::steady_clock::now();

        return {
            ids.size(),
            matches,
            std::chrono::duration<double, std::milli>(end - start).count()
        };
    }

    QueryStats regionStatusLookup(
        const std::string& region,
        const std::string& status
    ) const {
        auto start = std::chrono::steady_clock::now();

        const auto& ids = regionStatusIndex.lookup(region, status);
        std::size_t matches = 0;

        for (int id : ids) {
            const Order& order = getOrder(id);

            if (
                order.region == region &&
                order.status == status
            ) {
                ++matches;
            }
        }

        auto end = std::chrono::steady_clock::now();

        return {
            ids.size(),
            matches,
            std::chrono::duration<double, std::milli>(end - start).count()
        };
    }

    QueryStats pendingLookup() const {
        auto start = std::chrono::steady_clock::now();

        const auto& ids = pendingIndex.entries();
        std::size_t matches = 0;

        for (int id : ids) {
            if (getOrder(id).status == "pending") {
                ++matches;
            }
        }

        auto end = std::chrono::steady_clock::now();

        return {
            ids.size(),
            matches,
            std::chrono::duration<double, std::milli>(end - start).count()
        };
    }

    const std::vector<Order>& allOrders() const {
        return orders;
    }
};

std::vector<Order> generateOrders(std::size_t count) {
    std::mt19937 rng(42);

    const std::vector<std::string> regions{
        "north", "south", "east", "west"
    };

    const std::vector<std::string> statuses{
        "pending", "paid", "shipped", "cancelled"
    };

    std::discrete_distribution<int> statusDistribution{
        8, 28, 45, 19
    };

    std::uniform_int_distribution<int> customerDistribution(1, 5000);
    std::uniform_int_distribution<int> regionDistribution(
        0,
        static_cast<int>(regions.size() - 1)
    );
    std::uniform_int_distribution<int> yearDistribution(2024, 2026);
    std::uniform_int_distribution<int> monthDistribution(1, 12);
    std::uniform_int_distribution<int> dayDistribution(1, 28);
    std::uniform_int_distribution<int> amountDistribution(
        500,
        500000
    );

    std::vector<Order> orders;
    orders.reserve(count);

    for (std::size_t index = 0; index < count; ++index) {
        int year = yearDistribution(rng);
        int month = monthDistribution(rng);
        int day = dayDistribution(rng);

        std::ostringstream date;

        date << year << '-'
             << std::setw(2) << std::setfill('0') << month << '-'
             << std::setw(2) << std::setfill('0') << day;

        orders.push_back({
            static_cast<int>(index + 1),
            customerDistribution(rng),
            regions[regionDistribution(rng)],
            statuses[statusDistribution(rng)],
            date.str(),
            amountDistribution(rng)
        });
    }

    return orders;
}

double calculateSelectivity(
    const std::vector<Order>& orders,
    const std::function<std::string(const Order&)>& extractor
) {
    if (orders.empty()) {
        return 0.0;
    }

    std::map<std::string, bool> distinctValues;

    for (const Order& order : orders) {
        distinctValues[extractor(order)] = true;
    }

    return static_cast<double>(distinctValues.size())
        / static_cast<double>(orders.size());
}

void printStats(const std::string& label, const QueryStats& stats) {
    std::cout << "\n" << label << "\n";
    std::cout << "  candidates: " << stats.candidates << "\n";
    std::cout << "  matches:    " << stats.matches << "\n";
    std::cout << "  time:       "
              << std::fixed << std::setprecision(3)
              << stats.elapsedMs << " ms\n";
}

int main() {
    try {
        std::cout << "Repository Analytics Indexing Engine\n";
        std::cout << "Generating realistic order workload...\n";

        std::vector<Order> orders = generateOrders(100000);
        OrderIndexEngine engine(std::move(orders));

        printStats(
            "Exact customer lookup through hash index",
            engine.customerLookup(2500)
        );

        printStats(
            "Date range lookup through ordered B-tree-like index",
            engine.dateRangeLookup("2026-06-01", "2026-07-01")
        );

        printStats(
            "Region + status lookup through composite index",
            engine.regionStatusLookup("south", "paid")
        );

        printStats(
            "Pending-order lookup through partial index",
            engine.pendingLookup()
        );

        const auto& allOrders = engine.allOrders();

        const double statusSelectivity = calculateSelectivity(
            allOrders,
            [](const Order& order) {
                return order.status;
            }
        );

        const double regionSelectivity = calculateSelectivity(
            allOrders,
            [](const Order& order) {
                return order.region;
            }
        );

        const double customerSelectivity = calculateSelectivity(
            allOrders,
            [](const Order& order) {
                return std::to_string(order.customerId);
            }
        );

        const double dateSelectivity = calculateSelectivity(
            allOrders,
            [](const Order& order) {
                return order.orderDate;
            }
        );

        std::cout << "\nSelectivity measurements\n";
        std::cout << std::setprecision(6);
        std::cout << "  status:     " << statusSelectivity << "\n";
        std::cout << "  region:     " << regionSelectivity << "\n";
        std::cout << "  customerId: " << customerSelectivity << "\n";
        std::cout << "  orderDate:  " << dateSelectivity << "\n";

        /*
         * Low-cardinality status values can match a large portion of the
         * table. A standalone status index therefore may be less useful than
         * a more selective access path. A partial index can change that
         * economics when one operational subset is queried frequently.
         */
        std::cout << "\nIndex-design decision\n";
        std::cout
            << "  A status-only index must be evaluated against the actual "
            << "distribution.\n"
            << "  A customer equality index is highly selective for this "
            << "workload.\n"
            << "  The date index supports ordered range access.\n"
            << "  The region/status index matches a multi-column access path.\n"
            << "  The pending index stores only rows relevant to an operational "
            << "workflow.\n";

        /*
         * Edge condition: querying an unknown customer is not an error in
         * the data model. It simply produces an empty index bucket.
         */
        QueryStats missingCustomer = engine.customerLookup(999999);

        printStats(
            "Missing customer lookup",
            missingCustomer
        );

        /*
         * Edge condition: an unknown order ID is a genuine lookup error
         * because the API contract asks for a specific existing entity.
         */
        try {
            static_cast<void>(engine.getOrder(999999999));
        } catch (const std::out_of_range& error) {
            std::cout
                << "\nValidation failure handled safely: "
                << error.what() << "\n";
        }

        std::cout
            << "\nProduction considerations\n"
            << "  Indexes consume memory/storage and increase write cost.\n"
            << "  Composite column order must follow real predicate patterns.\n"
            << "  Partial predicates must remain aligned with recurring queries.\n"
            << "  Selectivity should be measured from representative data.\n"
            << "  Execution plans from the real database remain authoritative.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal indexing-engine error: "
                  << error.what() << '\n';
        return 1;
    }
}

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * SQL Fundamentals Case Study
 *
 * Scenario:
 * A commerce platform wants a small in-memory governance layer for its sales
 * data before connecting the application to a relational database.
 *
 * The program models the semantics behind:
 *   SELECT  -> projection/read operations
 *   INSERT  -> validated row creation
 *   UPDATE  -> predicate-based modification
 *   DELETE  -> controlled row removal
 *   WHERE   -> row filtering
 *   ORDER BY -> deterministic result ordering
 *   GROUP BY -> aggregate reporting
 *
 * The C++ design deliberately differs from the Python SQLite laboratory:
 * instead of executing SQL strings, it exposes the relational reasoning as a
 * strongly typed C++ domain model.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic sql_fundamentals.cpp -o sql_lab
 */

struct Customer {
    int id;
    std::string name;
    std::string city;
    std::string segment;
};

struct Product {
    int id;
    std::string name;
    std::string category;
    double unitPrice;
    int stock;
};

struct Order {
    int id;
    int customerId;
    std::string date;
    std::string status;
};

struct OrderItem {
    int orderId;
    int productId;
    int quantity;
    double unitPrice;
};

struct CategoryReport {
    std::string category;
    int unitsSold{};
    double salesValue{};
};

struct CustomerReport {
    std::string customer;
    std::string city;
    int orderCount{};
    double salesValue{};
};

class SalesDatabase {
private:
    std::vector<Customer> customers_;
    std::vector<Product> products_;
    std::vector<Order> orders_;
    std::vector<OrderItem> orderItems_;

    static bool validSegment(const std::string& segment) {
        return segment == "Consumer" ||
               segment == "Business" ||
               segment == "Enterprise";
    }

    static bool validStatus(const std::string& status) {
        return status == "Pending" ||
               status == "Paid" ||
               status == "Shipped" ||
               status == "Cancelled";
    }

    static void validateCustomer(const Customer& customer) {
        if (customer.id <= 0) {
            throw std::invalid_argument("customer id must be positive");
        }
        if (customer.name.empty()) {
            throw std::invalid_argument("customer name cannot be empty");
        }
        if (customer.city.empty()) {
            throw std::invalid_argument("customer city cannot be empty");
        }
        if (!validSegment(customer.segment)) {
            throw std::invalid_argument("invalid customer segment");
        }
    }

    static void validateProduct(const Product& product) {
        if (product.id <= 0) {
            throw std::invalid_argument("product id must be positive");
        }
        if (product.name.empty()) {
            throw std::invalid_argument("product name cannot be empty");
        }
        if (product.unitPrice < 0.0) {
            throw std::invalid_argument("unit price cannot be negative");
        }
        if (product.stock < 0) {
            throw std::invalid_argument("stock cannot be negative");
        }
    }

    static void validateOrder(const Order& order) {
        if (order.id <= 0) {
            throw std::invalid_argument("order id must be positive");
        }
        if (order.customerId <= 0) {
            throw std::invalid_argument("order customer id must be positive");
        }
        if (order.date.empty()) {
            throw std::invalid_argument("order date cannot be empty");
        }
        if (!validStatus(order.status)) {
            throw std::invalid_argument("invalid order status");
        }
    }

    const Customer* findCustomer(int id) const {
        for (const auto& customer : customers_) {
            if (customer.id == id) {
                return &customer;
            }
        }
        return nullptr;
    }

    const Product* findProduct(int id) const {
        for (const auto& product : products_) {
            if (product.id == id) {
                return &product;
            }
        }
        return nullptr;
    }

    const Order* findOrder(int id) const {
        for (const auto& order : orders_) {
            if (order.id == id) {
                return &order;
            }
        }
        return nullptr;
    }

public:
    void insertCustomer(Customer customer) {
        validateCustomer(customer);

        if (findCustomer(customer.id) != nullptr) {
            throw std::invalid_argument("duplicate customer id");
        }

        customers_.push_back(std::move(customer));
    }

    void insertProduct(Product product) {
        validateProduct(product);

        if (findProduct(product.id) != nullptr) {
            throw std::invalid_argument("duplicate product id");
        }

        for (const auto& existing : products_) {
            if (existing.name == product.name) {
                throw std::invalid_argument("duplicate product name");
            }
        }

        products_.push_back(std::move(product));
    }

    void insertOrder(Order order) {
        validateOrder(order);

        if (findOrder(order.id) != nullptr) {
            throw std::invalid_argument("duplicate order id");
        }

        if (findCustomer(order.customerId) == nullptr) {
            throw std::invalid_argument("order references unknown customer");
        }

        orders_.push_back(std::move(order));
    }

    void insertOrderItem(OrderItem item) {
        if (item.quantity <= 0) {
            throw std::invalid_argument("order quantity must be positive");
        }

        if (item.unitPrice < 0.0) {
            throw std::invalid_argument("order item price cannot be negative");
        }

        if (findOrder(item.orderId) == nullptr) {
            throw std::invalid_argument("order item references unknown order");
        }

        if (findProduct(item.productId) == nullptr) {
            throw std::invalid_argument("order item references unknown product");
        }

        for (const auto& existing : orderItems_) {
            if (existing.orderId == item.orderId &&
                existing.productId == item.productId) {
                throw std::invalid_argument(
                    "duplicate product within the same order");
            }
        }

        orderItems_.push_back(std::move(item));
    }

    template <typename Predicate>
    std::vector<Product> selectProducts(Predicate predicate) const {
        /*
         * This method models SELECT ... FROM products WHERE ...
         *
         * The returned vector is a projection-like result. Returning copies
         * prevents callers from silently mutating the stored database rows.
         */
        std::vector<Product> result;

        for (const auto& product : products_) {
            if (predicate(product)) {
                result.push_back(product);
            }
        }

        return result;
    }

    template <typename Predicate>
    std::size_t updateProducts(Predicate predicate,
                               double newPrice,
                               std::optional<int> stockDelta = std::nullopt) {
        /*
         * UPDATE requires a predicate. The method first constructs a proposed
         * state and validates it before changing the stored object.
         */
        std::size_t changed = 0;

        for (auto& product : products_) {
            if (!predicate(product)) {
                continue;
            }

            Product candidate = product;
            candidate.unitPrice = newPrice;

            if (stockDelta.has_value()) {
                candidate.stock += *stockDelta;
            }

            validateProduct(candidate);
            product = std::move(candidate);
            ++changed;
        }

        return changed;
    }

    bool deleteProduct(int productId) {
        /*
         * A DELETE is rejected if another table depends on the product.
         * This models a restrictive foreign-key relationship.
         */
        const bool referenced = std::any_of(
            orderItems_.begin(),
            orderItems_.end(),
            [productId](const OrderItem& item) {
                return item.productId == productId;
            });

        if (referenced) {
            throw std::logic_error(
                "cannot delete product referenced by order items");
        }

        const auto oldSize = products_.size();

        products_.erase(
            std::remove_if(
                products_.begin(),
                products_.end(),
                [productId](const Product& product) {
                    return product.id == productId;
                }),
            products_.end());

        return products_.size() != oldSize;
    }

    std::vector<Product> productsOrderedByPrice(bool descending) const {
        auto result = products_;

        std::sort(
            result.begin(),
            result.end(),
            [descending](const Product& a, const Product& b) {
                if (a.unitPrice == b.unitPrice) {
                    return a.name < b.name;
                }

                return descending
                    ? a.unitPrice > b.unitPrice
                    : a.unitPrice < b.unitPrice;
            });

        return result;
    }

    std::vector<CategoryReport> groupSalesByCategory() const {
        /*
         * GROUP BY category:
         *
         * Each completed order item is assigned to its product category.
         * Aggregates are accumulated in a map keyed by category.
         *
         * Cancelled and pending orders are excluded before aggregation.
         * This is equivalent to applying WHERE before GROUP BY.
         */
        std::map<std::string, CategoryReport> groups;

        for (const auto& item : orderItems_) {
            const Order* order = findOrder(item.orderId);

            if (order == nullptr) {
                throw std::logic_error("orphan order item detected");
            }

            if (order->status != "Paid" && order->status != "Shipped") {
                continue;
            }

            const Product* product = findProduct(item.productId);

            if (product == nullptr) {
                throw std::logic_error("orphan product reference detected");
            }

            auto& report = groups[product->category];
            report.category = product->category;
            report.unitsSold += item.quantity;
            report.salesValue +=
                static_cast<double>(item.quantity) * item.unitPrice;
        }

        std::vector<CategoryReport> result;

        for (const auto& [category, report] : groups) {
            result.push_back(report);
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const CategoryReport& a, const CategoryReport& b) {
                if (std::abs(a.salesValue - b.salesValue) < 0.000001) {
                    return a.category < b.category;
                }

                return a.salesValue > b.salesValue;
            });

        return result;
    }

    std::vector<CustomerReport> customerSalesReport(
        double minimumValue) const {
        /*
         * This is a multi-table reporting query expressed as C++:
         *
         * customers
         *     JOIN orders
         *         JOIN order_items
         *
         * followed by WHERE, GROUP BY, HAVING, and ORDER BY semantics.
         */
        struct Accumulator {
            std::string customer;
            std::string city;
            std::set<int> orders;
            double value{};
        };

        std::unordered_map<int, Accumulator> grouped;

        for (const auto& order : orders_) {
            if (order.status != "Paid" && order.status != "Shipped") {
                continue;
            }

            const Customer* customer = findCustomer(order.customerId);

            if (customer == nullptr) {
                throw std::logic_error(
                    "order references missing customer");
            }

            auto& accumulator = grouped[customer->id];
            accumulator.customer = customer->name;
            accumulator.city = customer->city;
            accumulator.orders.insert(order.id);

            for (const auto& item : orderItems_) {
                if (item.orderId == order.id) {
                    accumulator.value +=
                        static_cast<double>(item.quantity) * item.unitPrice;
                }
            }
        }

        std::vector<CustomerReport> result;

        for (const auto& [customerId, accumulator] : grouped) {
            if (accumulator.value < minimumValue) {
                continue;
            }

            result.push_back({
                accumulator.customer,
                accumulator.city,
                static_cast<int>(accumulator.orders.size()),
                accumulator.value
            });
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const CustomerReport& a, const CustomerReport& b) {
                if (std::abs(a.salesValue - b.salesValue) < 0.000001) {
                    return a.customer < b.customer;
                }

                return a.salesValue > b.salesValue;
            });

        return result;
    }

    std::size_t customerCount() const {
        return customers_.size();
    }

    std::size_t productCount() const {
        return products_.size();
    }
};

void seedDatabase(SalesDatabase& db) {
    db.insertCustomer({1, "Aarav Mehta", "Lucknow", "Consumer"});
    db.insertCustomer({2, "Neha Sharma", "Delhi", "Business"});
    db.insertCustomer({3, "Rohan Verma", "Bengaluru", "Enterprise"});
    db.insertCustomer({4, "Isha Kapoor", "Mumbai", "Consumer"});
    db.insertCustomer({5, "Kabir Singh", "Lucknow", "Business"});
    db.insertCustomer({6, "Maya Rao", "Hyderabad", "Enterprise"});

    db.insertProduct({1, "Mechanical Keyboard", "Computing", 4500.0, 40});
    db.insertProduct({2, "USB-C Dock", "Computing", 7200.0, 25});
    db.insertProduct({3, "Noise Cancelling Headphones", "Audio", 9800.0, 18});
    db.insertProduct({4, "Webcam", "Video", 3200.0, 30});
    db.insertProduct({5, "Monitor Arm", "Accessories", 4100.0, 22});
    db.insertProduct({6, "Laptop Stand", "Accessories", 2600.0, 35});

    db.insertOrder({1001, 1, "2026-09-01", "Paid"});
    db.insertOrder({1002, 2, "2026-09-03", "Shipped"});
    db.insertOrder({1003, 3, "2026-09-04", "Paid"});
    db.insertOrder({1004, 1, "2026-09-07", "Cancelled"});
    db.insertOrder({1005, 4, "2026-09-09", "Shipped"});
    db.insertOrder({1006, 5, "2026-09-12", "Paid"});
    db.insertOrder({1007, 6, "2026-09-14", "Pending"});
    db.insertOrder({1008, 2, "2026-09-18", "Shipped"});

    db.insertOrderItem({1001, 1, 1, 4500.0});
    db.insertOrderItem({1001, 6, 2, 2600.0});
    db.insertOrderItem({1002, 2, 1, 7200.0});
    db.insertOrderItem({1002, 4, 2, 3200.0});
    db.insertOrderItem({1003, 3, 2, 9800.0});
    db.insertOrderItem({1003, 5, 1, 4100.0});
    db.insertOrderItem({1004, 1, 1, 4500.0});
    db.insertOrderItem({1005, 4, 1, 3200.0});
    db.insertOrderItem({1005, 6, 1, 2600.0});
    db.insertOrderItem({1006, 2, 2, 7200.0});
    db.insertOrderItem({1006, 5, 2, 4100.0});
    db.insertOrderItem({1007, 3, 1, 9800.0});
    db.insertOrderItem({1008, 2, 1, 7200.0});
    db.insertOrderItem({1008, 6, 3, 2600.0});
}

void printProductRows(const std::string& title,
                      const std::vector<Product>& products) {
    std::cout << "\n--- " << title << " ---\n";

    std::cout << std::left
              << std::setw(8) << "ID"
              << std::setw(32) << "Product"
              << std::setw(18) << "Category"
              << std::setw(14) << "Price"
              << std::setw(8) << "Stock"
              << '\n';

    std::cout << std::string(80, '-') << '\n';

    for (const auto& product : products) {
        std::cout << std::left
                  << std::setw(8) << product.id
                  << std::setw(32) << product.name
                  << std::setw(18) << product.category
                  << std::setw(14) << std::fixed
                  << std::setprecision(2) << product.unitPrice
                  << std::setw(8) << product.stock
                  << '\n';
    }
}

void demonstrateSelectWhereOrderBy(SalesDatabase& db) {
    /*
     * SELECT product columns
     * FROM products
     * WHERE unit_price >= 4000 AND stock >= 20
     * ORDER BY unit_price DESC, name ASC
     */
    const auto result = db.selectProducts(
        [](const Product& product) {
            return product.unitPrice >= 4000.0 && product.stock >= 20;
        });

    auto ordered = result;

    std::sort(
        ordered.begin(),
        ordered.end(),
        [](const Product& a, const Product& b) {
            if (a.unitPrice == b.unitPrice) {
                return a.name < b.name;
            }

            return a.unitPrice > b.unitPrice;
        });

    printProductRows("SELECT + WHERE + ORDER BY", ordered);
}

void demonstrateInsert(SalesDatabase& db) {
    db.insertProduct({
        7,
        "Desk Lamp",
        "Accessories",
        1800.0,
        50
    });

    std::cout << "\nINSERT created product 7.\n";
}

void demonstrateUpdate(SalesDatabase& db) {
    /*
     * The predicate limits the UPDATE to accessories with low stock.
     * This is the C++ equivalent of a carefully scoped SQL WHERE clause.
     */
    const std::size_t changed = db.updateProducts(
        [](const Product& product) {
            return product.category == "Accessories" && product.stock < 30;
        },
        4100.0,
        10);

    std::cout << "UPDATE changed " << changed << " row(s).\n";
}

void demonstrateDelete(SalesDatabase& db) {
    /*
     * The product is referenced by order_items, so a safe relational design
     * rejects the DELETE instead of silently breaking historical order data.
     */
    try {
        db.deleteProduct(1);
    } catch (const std::logic_error& error) {
        std::cout << "\nDELETE rejected by referential integrity: "
                  << error.what() << '\n';
    }
}

void printCategoryReports(const std::vector<CategoryReport>& reports) {
    std::cout << "\n--- GROUP BY category ---\n";

    for (const auto& report : reports) {
        std::cout << std::left
                  << std::setw(18) << report.category
                  << std::setw(12) << report.unitsSold
                  << std::fixed << std::setprecision(2)
                  << report.salesValue
                  << '\n';
    }
}

void printCustomerReports(const std::vector<CustomerReport>& reports) {
    std::cout << "\n--- Customer GROUP BY report with HAVING threshold ---\n";

    for (const auto& report : reports) {
        std::cout << std::left
                  << std::setw(24) << report.customer
                  << std::setw(16) << report.city
                  << std::setw(10) << report.orderCount
                  << std::fixed << std::setprecision(2)
                  << report.salesValue
                  << '\n';
    }
}

void demonstrateGroupBy(SalesDatabase& db) {
    const auto reports = db.groupSalesByCategory();
    printCategoryReports(reports);

    const auto customerReports = db.customerSalesReport(10000.0);
    printCustomerReports(customerReports);
}

void demonstrateConstraintFailures(SalesDatabase& db) {
    try {
        db.insertProduct({
            99,
            "Invalid Product",
            "Computing",
            -50.0,
            10
        });
    } catch (const std::invalid_argument& error) {
        std::cout << "\nConstraint validation rejected INSERT: "
                  << error.what() << '\n';
    }

    try {
        db.insertOrder({
            99,
            999999,
            "2026-10-01",
            "Paid"
        });
    } catch (const std::invalid_argument& error) {
        std::cout << "Foreign-key validation rejected order: "
                  << error.what() << '\n';
    }
}

void demonstrateAggregateOrdering(SalesDatabase& db) {
    /*
     * ORDER BY can operate on a derived aggregate rather than a stored
     * column. The category report is already sorted by sales value.
     */
    const auto reports = db.groupSalesByCategory();

    if (!reports.empty()) {
        std::cout << "\nHighest-value category: "
                  << reports.front().category
                  << " (" << std::fixed << std::setprecision(2)
                  << reports.front().salesValue << ")\n";
    }
}

int main() {
    try {
        std::cout << std::string(72, '=') << '\n';
        std::cout << "SQL FUNDAMENTALS: C++ RELATIONAL CASE STUDY\n";
        std::cout << "SELECT | INSERT | UPDATE | DELETE | WHERE | "
                     "ORDER BY | GROUP BY\n";
        std::cout << std::string(72, '=') << '\n';

        SalesDatabase database;
        seedDatabase(database);

        demonstrateSelectWhereOrderBy(database);
        demonstrateInsert(database);
        demonstrateUpdate(database);
        demonstrateDelete(database);
        demonstrateGroupBy(database);
        demonstrateConstraintFailures(database);
        demonstrateAggregateOrdering(database);

        const auto orderedProducts =
            database.productsOrderedByPrice(true);

        printProductRows(
            "Products ordered by price descending",
            orderedProducts);

        std::cout << "\nDatabase contains "
                  << database.customerCount()
                  << " customers and "
                  << database.productCount()
                  << " products after the demonstration.\n";

        std::cout << "C++ SQL fundamentals case study completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal database-model error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}

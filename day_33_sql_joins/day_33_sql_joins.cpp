#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

/*
 * C++17 case study:
 *
 * Repository analytics is modeled as a relational reporting system for a
 * fictional commerce platform. The system must reconcile customers, orders,
 * products, and employee ownership information.
 *
 * The program implements the join engine explicitly so that the business
 * consequences of each join type are visible:
 *
 *   INNER JOIN  -> valid customer/order matches
 *   LEFT JOIN   -> every customer, including inactive customers
 *   RIGHT JOIN  -> every order, including orphaned orders
 *   FULL JOIN   -> complete reconciliation of both relations
 *   CROSS JOIN  -> every region/notification combination
 *   SELF JOIN   -> employee/manager hierarchy
 *
 * The case study also examines composite keys, row multiplication,
 * validation, null-like values, and hash-index performance.
 */

using std::cout;
using std::endl;
using std::nullopt;
using std::optional;
using std::string;
using std::unordered_map;
using std::unordered_set;
using std::vector;


// ---------------------------------------------------------------------------
// Domain model
// ---------------------------------------------------------------------------

struct Customer {
    int id;
    string name;
    string city;
};

struct Order {
    int id;
    int customerId;
    int productId;
    double amount;
};

struct Product {
    int id;
    string name;
    string category;
};

struct Employee {
    int id;
    string name;
    optional<int> managerId;
    string department;
};

struct Region {
    string code;
    string name;
};


// ---------------------------------------------------------------------------
// Generic composite key
// ---------------------------------------------------------------------------

struct WarehouseProductKey {
    string warehouse;
    int productId;

    bool operator==(const WarehouseProductKey& other) const {
        return warehouse == other.warehouse &&
               productId == other.productId;
    }
};

struct WarehouseProductHash {
    std::size_t operator()(const WarehouseProductKey& key) const {
        const std::size_t first = std::hash<string>{}(key.warehouse);
        const std::size_t second = std::hash<int>{}(key.productId);

        return first ^ (second + 0x9e3779b9 +
                        (first << 6) + (first >> 2));
    }
};


// ---------------------------------------------------------------------------
// Indexed customer/order representation
// ---------------------------------------------------------------------------

struct CustomerOrderRow {
    optional<Customer> customer;
    optional<Order> order;
};

struct CustomerProductRow {
    optional<Customer> customer;
    optional<Order> order;
    optional<Product> product;
};


// ---------------------------------------------------------------------------
// INNER JOIN
// ---------------------------------------------------------------------------

vector<CustomerOrderRow> innerJoinCustomersOrders(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    /*
     * A hash index on customer ID avoids scanning all customers for every
     * order. Customer IDs are expected to be unique, so the index maps one
     * ID to one Customer.
     */
    unordered_map<int, const Customer*> customerIndex;

    for (const auto& customer : customers) {
        auto [iterator, inserted] =
            customerIndex.emplace(customer.id, &customer);

        if (!inserted) {
            throw std::runtime_error(
                "Duplicate customer primary key: " +
                std::to_string(customer.id)
            );
        }
    }

    vector<CustomerOrderRow> result;

    for (const auto& order : orders) {
        auto found = customerIndex.find(order.customerId);

        if (found != customerIndex.end()) {
            result.push_back({
                *found->second,
                order
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// LEFT JOIN
// ---------------------------------------------------------------------------

vector<CustomerOrderRow> leftJoinCustomersOrders(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    /*
     * Orders are indexed by customer ID. Multiple orders can belong to one
     * customer, so the value is a vector rather than a single pointer.
     */
    unordered_map<int, vector<const Order*>> ordersByCustomer;

    for (const auto& order : orders) {
        ordersByCustomer[order.customerId].push_back(&order);
    }

    vector<CustomerOrderRow> result;

    for (const auto& customer : customers) {
        auto found = ordersByCustomer.find(customer.id);

        if (found == ordersByCustomer.end()) {
            result.push_back({
                customer,
                nullopt
            });
            continue;
        }

        /*
         * A one-to-many relationship expands one customer into multiple
         * output rows. This is fundamental join behavior, not duplication
         * caused by the implementation.
         */
        for (const Order* order : found->second) {
            result.push_back({
                customer,
                *order
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// RIGHT JOIN
// ---------------------------------------------------------------------------

vector<CustomerOrderRow> rightJoinCustomersOrders(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    /*
     * RIGHT JOIN preserves every order. We can naturally implement that
     * requirement by indexing customers and iterating the right relation.
     */
    unordered_map<int, const Customer*> customerIndex;

    for (const auto& customer : customers) {
        customerIndex[customer.id] = &customer;
    }

    vector<CustomerOrderRow> result;

    for (const auto& order : orders) {
        auto found = customerIndex.find(order.customerId);

        if (found == customerIndex.end()) {
            result.push_back({
                nullopt,
                order
            });
        } else {
            result.push_back({
                *found->second,
                order
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// FULL OUTER JOIN
// ---------------------------------------------------------------------------

vector<CustomerOrderRow> fullJoinCustomersOrders(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    /*
     * Orders are indexed because there can be several orders per customer.
     * matchedOrderIds tracks individual rows, not just customer IDs, so that
     * every unmatched order can be emitted correctly.
     */
    unordered_map<int, vector<const Order*>> ordersByCustomer;
    unordered_set<int> matchedOrderIds;

    for (const auto& order : orders) {
        ordersByCustomer[order.customerId].push_back(&order);
    }

    vector<CustomerOrderRow> result;

    for (const auto& customer : customers) {
        auto found = ordersByCustomer.find(customer.id);

        if (found == ordersByCustomer.end()) {
            result.push_back({
                customer,
                nullopt
            });
            continue;
        }

        for (const Order* order : found->second) {
            matchedOrderIds.insert(order->id);

            result.push_back({
                customer,
                *order
            });
        }
    }

    for (const auto& order : orders) {
        if (!matchedOrderIds.contains(order.id)) {
            result.push_back({
                nullopt,
                order
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// CROSS JOIN
// ---------------------------------------------------------------------------

vector<std::pair<Region, string>> crossJoinNotifications(
    const vector<Region>& regions,
    const vector<string>& notificationTypes
) {
    /*
     * There is deliberately no predicate. Every region receives every
     * notification type. If there are m regions and n notification types,
     * the result has m*n combinations.
     */
    vector<std::pair<Region, string>> result;

    for (const auto& region : regions) {
        for (const auto& notification : notificationTypes) {
            result.emplace_back(region, notification);
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// SELF JOIN
// ---------------------------------------------------------------------------

struct EmployeeManagerRow {
    Employee employee;
    optional<Employee> manager;
};

vector<EmployeeManagerRow> selfJoinEmployees(
    const vector<Employee>& employees
) {
    /*
     * One Employee relation is given two logical roles:
     *
     * employee.managerId -> manager.id
     *
     * The manager is optional because top-level employees have no manager.
     * An invalid non-null manager ID remains visible as an unmatched
     * relationship, which is useful for data-quality detection.
     */
    unordered_map<int, const Employee*> employeesById;

    for (const auto& employee : employees) {
        auto [iterator, inserted] =
            employeesById.emplace(employee.id, &employee);

        if (!inserted) {
            throw std::runtime_error(
                "Duplicate employee ID: " +
                std::to_string(employee.id)
            );
        }
    }

    vector<EmployeeManagerRow> result;

    for (const auto& employee : employees) {
        if (!employee.managerId.has_value()) {
            result.push_back({
                employee,
                nullopt
            });
            continue;
        }

        auto manager = employeesById.find(*employee.managerId);

        if (manager == employeesById.end()) {
            result.push_back({
                employee,
                nullopt
            });
        } else {
            result.push_back({
                employee,
                *manager->second
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// Three-table INNER JOIN
// ---------------------------------------------------------------------------

vector<CustomerProductRow> customerOrderProductReport(
    const vector<Customer>& customers,
    const vector<Order>& orders,
    const vector<Product>& products
) {
    /*
     * The first join produces customer/order pairs. The second join matches
     * the order's product ID to the product relation.
     */
    auto customerOrders =
        innerJoinCustomersOrders(customers, orders);

    unordered_map<int, const Product*> productIndex;

    for (const auto& product : products) {
        auto [iterator, inserted] =
            productIndex.emplace(product.id, &product);

        if (!inserted) {
            throw std::runtime_error(
                "Duplicate product ID: " +
                std::to_string(product.id)
            );
        }
    }

    vector<CustomerProductRow> result;

    for (const auto& row : customerOrders) {
        auto found = productIndex.find(row.order->productId);

        if (found != productIndex.end()) {
            result.push_back({
                row.customer,
                row.order,
                *found->second
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// Composite-key join case study
// ---------------------------------------------------------------------------

struct Inventory {
    string warehouse;
    int productId;
    int quantity;
};

struct AllocationRequest {
    string warehouse;
    int productId;
    string requestId;
};

struct InventoryMatch {
    AllocationRequest request;
    optional<Inventory> inventory;
};

vector<InventoryMatch> joinInventoryRequests(
    const vector<AllocationRequest>& requests,
    const vector<Inventory>& inventory
) {
    /*
     * Joining only on productId would be incorrect because the same product
     * can exist in multiple warehouses. The complete business identity is
     * (warehouse, productId).
     */
    unordered_map<
        WarehouseProductKey,
        const Inventory*,
        WarehouseProductHash
    > index;

    for (const auto& item : inventory) {
        WarehouseProductKey key{
            item.warehouse,
            item.productId
        };

        if (!index.emplace(key, &item).second) {
            throw std::runtime_error(
                "Duplicate inventory key for warehouse/product pair"
            );
        }
    }

    vector<InventoryMatch> result;

    for (const auto& request : requests) {
        WarehouseProductKey key{
            request.warehouse,
            request.productId
        };

        auto found = index.find(key);

        if (found == index.end()) {
            result.push_back({
                request,
                nullopt
            });
        } else {
            result.push_back({
                request,
                *found->second
            });
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// Aggregation after a LEFT JOIN
// ---------------------------------------------------------------------------

struct CustomerTotal {
    int customerId;
    string customerName;
    double total;
};

vector<CustomerTotal> calculateCustomerTotals(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    auto joined = leftJoinCustomersOrders(customers, orders);

    unordered_map<int, double> totals;

    for (const auto& customer : customers) {
        totals[customer.id] = 0.0;
    }

    for (const auto& row : joined) {
        if (row.order.has_value()) {
            totals[row.customer->id] += row.order->amount;
        }
    }

    vector<CustomerTotal> result;

    for (const auto& customer : customers) {
        result.push_back({
            customer.id,
            customer.name,
            totals[customer.id]
        });
    }

    return result;
}


// ---------------------------------------------------------------------------
// Referential-integrity validation
// ---------------------------------------------------------------------------

vector<int> findOrphanOrders(
    const vector<Customer>& customers,
    const vector<Order>& orders
) {
    unordered_set<int> customerIds;

    for (const auto& customer : customers) {
        customerIds.insert(customer.id);
    }

    vector<int> orphanOrderIds;

    for (const auto& order : orders) {
        if (!customerIds.contains(order.customerId)) {
            orphanOrderIds.push_back(order.id);
        }
    }

    return orphanOrderIds;
}


// ---------------------------------------------------------------------------
// Reporting helpers
// ---------------------------------------------------------------------------

void printCustomerOrders(
    const string& title,
    const vector<CustomerOrderRow>& rows
) {
    cout << "\n" << title << "\n";
    cout << string(title.size(), '-') << "\n";
    cout << std::left
         << std::setw(10) << "Customer"
         << std::setw(12) << "Order"
         << std::setw(12) << "Amount"
         << "Status\n";

    for (const auto& row : rows) {
        string customer =
            row.customer.has_value()
                ? row.customer->name
                : "NULL";

        string order =
            row.order.has_value()
                ? std::to_string(row.order->id)
                : "NULL";

        string amount =
            row.order.has_value()
                ? std::to_string(row.order->amount)
                : "NULL";

        string status;

        if (!row.customer.has_value()) {
            status = "orphan order";
        } else if (!row.order.has_value()) {
            status = "customer without order";
        } else {
            status = "matched";
        }

        cout << std::setw(10) << customer
             << std::setw(12) << order
             << std::setw(12) << amount
             << status << "\n";
    }
}

void printEmployeeManagers(
    const vector<EmployeeManagerRow>& rows
) {
    cout << "\nEmployee SELF JOIN\n";
    cout << "------------------\n";

    for (const auto& row : rows) {
        cout << row.employee.name << " -> ";

        if (row.manager.has_value()) {
            cout << row.manager->name;
        } else if (!row.employee.managerId.has_value()) {
            cout << "top-level employee";
        } else {
            cout << "invalid manager reference";
        }

        cout << "\n";
    }
}


// ---------------------------------------------------------------------------
// Main case study
// ---------------------------------------------------------------------------

int main() {
    try {
        const vector<Customer> customers{
            {1, "Asha", "Lucknow"},
            {2, "Ravi", "Delhi"},
            {3, "Meera", "Mumbai"},
            {4, "Kabir", "Pune"},
            {5, "Nisha", "Jaipur"}
        };

        const vector<Order> orders{
            {101, 1, 501, 2400.0},
            {102, 1, 502, 900.0},
            {103, 2, 503, 1500.0},
            {104, 2, 501, 3100.0},
            {105, 4, 504, 700.0},
            {106, 9, 501, 1200.0}
        };

        const vector<Product> products{
            {501, "Laptop", "Computers"},
            {502, "Keyboard", "Accessories"},
            {503, "Monitor", "Displays"},
            {504, "Mouse", "Accessories"},
            {505, "Webcam", "Accessories"}
        };

        cout << "SQL JOIN case study: commerce reporting engine\n";
        cout << "===============================================\n";

        auto inner =
            innerJoinCustomersOrders(customers, orders);
        printCustomerOrders(
            "INNER JOIN: only customers with matching orders",
            inner
        );

        auto left =
            leftJoinCustomersOrders(customers, orders);
        printCustomerOrders(
            "LEFT JOIN: every customer remains visible",
            left
        );

        auto right =
            rightJoinCustomersOrders(customers, orders);
        printCustomerOrders(
            "RIGHT JOIN: every order remains visible",
            right
        );

        auto full =
            fullJoinCustomersOrders(customers, orders);
        printCustomerOrders(
            "FULL OUTER JOIN: reconcile both relations",
            full
        );

        const vector<Region> regions{
            {"N", "North"},
            {"S", "South"},
            {"W", "West"}
        };

        const vector<string> notificationTypes{
            "order-created",
            "delivery-delayed"
        };

        auto cross =
            crossJoinNotifications(
                regions,
                notificationTypes
            );

        cout << "\nCROSS JOIN: region x notification policy\n";
        cout << "-----------------------------------------\n";

        for (const auto& [region, notification] : cross) {
            cout << region.name
                 << " -> "
                 << notification
                 << "\n";
        }

        const vector<Employee> employees{
            {1, "Anika", nullopt, "Engineering"},
            {2, "Bharat", 1, "Engineering"},
            {3, "Charu", 1, "Engineering"},
            {4, "Dev", 2, "Finance"},
            {5, "Esha", 2, "Operations"},
            {6, "Farhan", 99, "Operations"}
        };

        auto hierarchy =
            selfJoinEmployees(employees);

        printEmployeeManagers(hierarchy);

        auto report =
            customerOrderProductReport(
                customers,
                orders,
                products
            );

        cout << "\nThree-table INNER JOIN report\n";
        cout << "-----------------------------\n";

        for (const auto& row : report) {
            cout << row.customer->name
                 << " | Order "
                 << row.order->id
                 << " | "
                 << row.product->name
                 << " | "
                 << row.product->category
                 << " | "
                 << row.order->amount
                 << "\n";
        }

        const vector<AllocationRequest> requests{
            {"LKO", 501, "R1"},
            {"DEL", 501, "R2"},
            {"LKO", 999, "R3"}
        };

        const vector<Inventory> inventory{
            {"LKO", 501, 14},
            {"DEL", 501, 6},
            {"LKO", 502, 22}
        };

        auto allocations =
            joinInventoryRequests(
                requests,
                inventory
            );

        cout << "\nComposite-key LEFT JOIN\n";
        cout << "-----------------------\n";

        for (const auto& row : allocations) {
            cout << row.request.requestId
                 << " | "
                 << row.request.warehouse
                 << " | product "
                 << row.request.productId
                 << " | quantity ";

            if (row.inventory.has_value()) {
                cout << row.inventory->quantity;
            } else {
                cout << "NULL";
            }

            cout << "\n";
        }

        auto totals =
            calculateCustomerTotals(
                customers,
                orders
            );

        cout << "\nAggregation after LEFT JOIN\n";
        cout << "----------------------------\n";

        for (const auto& total : totals) {
            cout << std::setw(10)
                 << total.customerName
                 << " total = "
                 << std::fixed
                 << std::setprecision(2)
                 << total.total
                 << "\n";
        }

        auto orphanOrders =
            findOrphanOrders(
                customers,
                orders
            );

        cout << "\nReferential-integrity check\n";
        cout << "---------------------------\n";

        if (orphanOrders.empty()) {
            cout << "No orphan orders found.\n";
        } else {
            cout << "Orders referencing unknown customers: ";

            for (int id : orphanOrders) {
                cout << id << " ";
            }

            cout << "\n";
            cout << "The FULL/RIGHT join exposes this data-quality issue "
                 << "instead of silently dropping the order.\n";
        }

        cout << "\nPerformance and design considerations\n";
        cout << "-------------------------------------\n";
        cout << "Hash indexes provide expected O(m+n) join work for "
             << "equality joins when hashing is appropriate.\n";
        cout << "A naive nested-loop implementation performs O(m*n) "
             << "comparisons.\n";
        cout << "One-to-many relationships multiply output rows, so "
             << "aggregation after a join must account for cardinality.\n";
        cout << "CROSS JOIN output is O(m*n) by definition and can become "
             << "large very quickly.\n";
        cout << "Optional fields model NULL-producing outer-join sides "
             << "without confusing missing data with a valid object.\n";
        cout << "A production database optimizer may select hash, merge, "
             << "nested-loop, or index-assisted join strategies based "
             << "on statistics and available indexes.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}

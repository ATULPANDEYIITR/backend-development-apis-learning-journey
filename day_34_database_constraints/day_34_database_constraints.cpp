/*
 * Database Constraints Case Study
 *
 * Scenario:
 * A commerce platform needs a small governance layer that guarantees customer,
 * product, order, and order-item integrity before records are committed.
 *
 * This C++17 program models:
 *   PRIMARY KEY
 *   FOREIGN KEY
 *   UNIQUE
 *   NOT NULL
 *   CHECK
 *   DEFAULT
 *
 * The implementation deliberately treats constraints as database invariants.
 * The repository layer rejects invalid state before it becomes persistent.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic constraints_case_study.cpp -o constraints_case_study
 */

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

class ConstraintViolation : public std::runtime_error {
public:
    ConstraintViolation(std::string type, std::string message)
        : std::runtime_error(std::move(message)),
          type_(std::move(type)) {}

    const std::string& type() const noexcept {
        return type_;
    }

private:
    std::string type_;
};

struct Customer {
    int id;
    std::string email;
    std::string name;
    int age;
    std::string status;
};

struct Product {
    int id;
    std::string sku;
    std::string name;
    double price;
    int stock;
};

struct Order {
    int id;
    int customerId;
    std::string status;
    std::string createdAt;
};

struct OrderItem {
    int orderId;
    int productId;
    int quantity;
    double unitPrice;
};

struct CompositeKey {
    int orderId;
    int productId;

    bool operator==(const CompositeKey& other) const noexcept {
        return orderId == other.orderId && productId == other.productId;
    }
};

struct CompositeKeyHash {
    std::size_t operator()(const CompositeKey& key) const noexcept {
        const std::size_t left = std::hash<int>{}(key.orderId);
        const std::size_t right = std::hash<int>{}(key.productId);

        return left ^ (right + 0x9e3779b9U + (left << 6U) + (left >> 2U));
    }
};

class CommerceRepository {
public:
    int createCustomer(
        const std::optional<std::string>& email,
        const std::optional<std::string>& name,
        const std::optional<int>& age,
        const std::optional<std::string>& status = std::nullopt
    ) {
        // NOT NULL: required columns cannot be represented by absent values.
        if (!email.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "customers.email cannot be NULL"
            );
        }

        if (!name.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "customers.name cannot be NULL"
            );
        }

        if (!age.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "customers.age cannot be NULL"
            );
        }

        // UNIQUE: email is indexed separately so duplicate detection is efficient.
        if (customerEmailIndex_.contains(*email)) {
            throw ConstraintViolation(
                "UNIQUE",
                "customers.email must be unique: " + *email
            );
        }

        // CHECK: domain-specific validation belongs at the integrity boundary.
        if (*age < 18) {
            throw ConstraintViolation(
                "CHECK",
                "customers.age must be >= 18"
            );
        }

        // DEFAULT: when status is omitted, the repository applies the schema rule.
        const std::string actualStatus = status.value_or("active");

        if (actualStatus != "active" && actualStatus != "suspended") {
            throw ConstraintViolation(
                "CHECK",
                "customers.status must be active or suspended"
            );
        }

        const int id = nextCustomerId_++;

        customers_.emplace(
            id,
            Customer{id, *email, *name, *age, actualStatus}
        );

        customerEmailIndex_.insert({*email, id});

        return id;
    }

    int createProduct(
        const std::optional<std::string>& sku,
        const std::optional<std::string>& name,
        const std::optional<double>& price,
        const std::optional<int>& stock = std::nullopt
    ) {
        if (!sku.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "products.sku cannot be NULL"
            );
        }

        if (!name.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "products.name cannot be NULL"
            );
        }

        if (!price.has_value()) {
            throw ConstraintViolation(
                "NOT NULL",
                "products.price cannot be NULL"
            );
        }

        if (productSkuIndex_.contains(*sku)) {
            throw ConstraintViolation(
                "UNIQUE",
                "products.sku must be unique: " + *sku
            );
        }

        if (*price <= 0.0) {
            throw ConstraintViolation(
                "CHECK",
                "products.price must be greater than zero"
            );
        }

        // DEFAULT stock = 0.
        const int actualStock = stock.value_or(0);

        if (actualStock < 0) {
            throw ConstraintViolation(
                "CHECK",
                "products.stock must be >= 0"
            );
        }

        const int id = nextProductId_++;

        products_.emplace(
            id,
            Product{id, *sku, *name, *price, actualStock}
        );

        productSkuIndex_.insert({*sku, id});

        return id;
    }

    int createOrder(
        int customerId,
        const std::vector<std::pair<std::string, int>>& requestedItems
    ) {
        // FOREIGN KEY: the parent row must exist before the child row.
        if (!customers_.contains(customerId)) {
            throw ConstraintViolation(
                "FOREIGN KEY",
                "orders.customer_id references a nonexistent customer"
            );
        }

        if (requestedItems.empty()) {
            throw ConstraintViolation(
                "CHECK",
                "An order must contain at least one item"
            );
        }

        /*
         * The order operation stages all changes first. If a later item violates
         * a constraint, no partially created order remains in the repository.
         */
        const int orderId = nextOrderId_++;

        std::vector<OrderItem> stagedItems;
        std::unordered_map<int, int> stagedStock;

        for (const auto& [sku, quantity] : requestedItems) {
            if (quantity <= 0) {
                throw ConstraintViolation(
                    "CHECK",
                    "order_items.quantity must be greater than zero"
                );
            }

            const auto skuIterator = productSkuIndex_.find(sku);

            if (skuIterator == productSkuIndex_.end()) {
                throw ConstraintViolation(
                    "FOREIGN KEY",
                    "order_items.product_id references nonexistent SKU: " + sku
                );
            }

            const int productId = skuIterator->second;
            const Product& product = products_.at(productId);

            const int availableStock =
                stagedStock.contains(productId)
                    ? stagedStock.at(productId)
                    : product.stock;

            if (availableStock < quantity) {
                throw ConstraintViolation(
                    "CHECK",
                    "Insufficient stock for SKU " + sku
                );
            }

            const CompositeKey key{orderId, productId};

            /*
             * PRIMARY KEY(order_id, product_id) means a product may appear only
             * once in a given order. A quantity belongs on that one row.
             */
            const bool duplicateInBatch = std::any_of(
                stagedItems.begin(),
                stagedItems.end(),
                [&](const OrderItem& item) {
                    return item.orderId == key.orderId &&
                           item.productId == key.productId;
                }
            );

            if (orderItems_.contains(key) || duplicateInBatch) {
                throw ConstraintViolation(
                    "PRIMARY KEY",
                    "Duplicate order_id/product_id pair"
                );
            }

            stagedItems.push_back(
                OrderItem{
                    orderId,
                    productId,
                    quantity,
                    product.price
                }
            );

            stagedStock[productId] = availableStock - quantity;
        }

        // DEFAULT status = "pending".
        const Order order{
            orderId,
            customerId,
            "pending",
            currentTimestamp()
        };

        orders_.emplace(orderId, order);

        for (const OrderItem& item : stagedItems) {
            orderItems_.emplace(
                CompositeKey{item.orderId, item.productId},
                item
            );
        }

        for (const auto& [productId, newStock] : stagedStock) {
            products_.at(productId).stock = newStock;
        }

        return orderId;
    }

    void deleteCustomer(int customerId) {
        if (!customers_.contains(customerId)) {
            return;
        }

        // ON DELETE RESTRICT: parent deletion is rejected while child rows exist.
        const bool referenced = std::any_of(
            orders_.begin(),
            orders_.end(),
            [&](const auto& entry) {
                return entry.second.customerId == customerId;
            }
        );

        if (referenced) {
            throw ConstraintViolation(
                "FOREIGN KEY",
                "Cannot delete customer while an order references it"
            );
        }

        const Customer customer = customers_.at(customerId);

        customers_.erase(customerId);
        customerEmailIndex_.erase(customer.email);
    }

    void deleteProduct(int productId) {
        if (!products_.contains(productId)) {
            return;
        }

        const bool referenced = std::any_of(
            orderItems_.begin(),
            orderItems_.end(),
            [&](const auto& entry) {
                return entry.second.productId == productId;
            }
        );

        if (referenced) {
            throw ConstraintViolation(
                "FOREIGN KEY",
                "Cannot delete product while an order item references it"
            );
        }

        const Product product = products_.at(productId);

        products_.erase(productId);
        productSkuIndex_.erase(product.sku);
    }

    void updateProductStock(int productId, int newStock) {
        if (!products_.contains(productId)) {
            throw ConstraintViolation(
                "FOREIGN KEY",
                "Product does not exist"
            );
        }

        if (newStock < 0) {
            throw ConstraintViolation(
                "CHECK",
                "products.stock must remain >= 0"
            );
        }

        products_.at(productId).stock = newStock;
    }

    void printState() const {
        std::cout << "\n=== CUSTOMERS ===\n";

        for (const auto& [id, customer] : customers_) {
            std::cout
                << "id=" << id
                << " email=" << customer.email
                << " name=" << customer.name
                << " age=" << customer.age
                << " status=" << customer.status
                << '\n';
        }

        std::cout << "\n=== PRODUCTS ===\n";

        for (const auto& [id, product] : products_) {
            std::cout
                << "id=" << id
                << " sku=" << product.sku
                << " name=" << product.name
                << " price=" << std::fixed << std::setprecision(2)
                << product.price
                << " stock=" << product.stock
                << '\n';
        }

        std::cout << "\n=== ORDERS ===\n";

        for (const auto& [id, order] : orders_) {
            std::cout
                << "order_id=" << id
                << " customer_id=" << order.customerId
                << " status=" << order.status
                << " created_at=" << order.createdAt
                << '\n';
        }

        std::cout << "\n=== ORDER ITEMS ===\n";

        for (const auto& [key, item] : orderItems_) {
            std::cout
                << "order_id=" << item.orderId
                << " product_id=" << item.productId
                << " quantity=" << item.quantity
                << " unit_price=" << std::fixed
                << std::setprecision(2)
                << item.unitPrice
                << '\n';
        }
    }

private:
    static std::string currentTimestamp() {
        const auto now = std::chrono::system_clock::now();
        const std::time_t time = std::chrono::system_clock::to_time_t(now);

        std::ostringstream output;
        output << std::put_time(std::localtime(&time), "%Y-%m-%d %H:%M:%S");

        return output.str();
    }

    int nextCustomerId_ = 1;
    int nextProductId_ = 1;
    int nextOrderId_ = 1;

    std::unordered_map<int, Customer> customers_;
    std::unordered_map<int, Product> products_;
    std::unordered_map<int, Order> orders_;

    std::unordered_map<CompositeKey, OrderItem, CompositeKeyHash>
        orderItems_;

    // Secondary indexes model the purpose of database indexes behind UNIQUE keys.
    std::unordered_map<std::string, int> customerEmailIndex_;
    std::unordered_map<std::string, int> productSkuIndex_;
};

template <typename Function>
void showConstraintFailure(
    const std::string& scenario,
    Function operation
) {
    try {
        operation();
        std::cout << scenario << ": unexpectedly accepted\n";
    } catch (const ConstraintViolation& error) {
        std::cout
            << scenario
            << ": rejected by "
            << error.type()
            << " -> "
            << error.what()
            << '\n';
    }
}

int main() {
    CommerceRepository repository;

    std::cout << "=== DATABASE CONSTRAINT CASE STUDY ===\n";

    const int aliceId = repository.createCustomer(
        "alice@example.com",
        "Alice Rao",
        29
        // status omitted, so DEFAULT "active" applies.
    );

    const int laptopId = repository.createProduct(
        "LT-100",
        "Developer Laptop",
        1299.00,
        5
    );

    const int monitorId = repository.createProduct(
        "MN-200",
        "4K Monitor",
        349.00,
        10
    );

    std::cout
        << "Created customer " << aliceId
        << ", laptop " << laptopId
        << ", monitor " << monitorId
        << '\n';

    std::cout << "\n=== CONSTRAINT VALIDATION ===\n";

    showConstraintFailure(
        "Duplicate customer email",
        [&]() {
            repository.createCustomer(
                "alice@example.com",
                "Second Alice",
                31
            );
        }
    );

    showConstraintFailure(
        "Underage customer",
        [&]() {
            repository.createCustomer(
                "minor@example.com",
                "Minor Customer",
                17
            );
        }
    );

    showConstraintFailure(
        "Invalid product price",
        [&]() {
            repository.createProduct(
                "BAD-PRICE",
                "Invalid Product",
                0.0,
                1
            );
        }
    );

    showConstraintFailure(
        "Missing customer foreign key",
        [&]() {
            repository.createOrder(
                999999,
                {{"LT-100", 1}}
            );
        }
    );

    showConstraintFailure(
        "Invalid order quantity",
        [&]() {
            repository.createOrder(
                aliceId,
                {{"LT-100", 0}}
            );
        }
    );

    showConstraintFailure(
        "Unknown product foreign key",
        [&]() {
            repository.createOrder(
                aliceId,
                {{"UNKNOWN-SKU", 1}}
            );
        }
    );

    std::cout << "\n=== VALID ORDER ===\n";

    const int orderId = repository.createOrder(
        aliceId,
        {
            {"LT-100", 1},
            {"MN-200", 2}
        }
    );

    std::cout
        << "Created order " << orderId
        << " using customer " << aliceId
        << '\n';

    std::cout << "\n=== FOREIGN KEY DELETE RESTRICTION ===\n";

    showConstraintFailure(
        "Delete referenced customer",
        [&]() {
            repository.deleteCustomer(aliceId);
        }
    );

    showConstraintFailure(
        "Delete referenced product",
        [&]() {
            repository.deleteProduct(laptopId);
        }
    );

    std::cout << "\n=== POST-ORDER STOCK VALIDATION ===\n";

    repository.updateProductStock(laptopId, 4);
    std::cout
        << "Laptop stock after successful order: 4\n";

    showConstraintFailure(
        "Negative stock update",
        [&]() {
            repository.updateProductStock(laptopId, -1);
        }
    );

    repository.printState();

    std::cout
        << "\n=== CONSTRAINT RELATIONSHIP ===\n"
        << "PRIMARY KEY identifies each entity or relationship row.\n"
        << "UNIQUE prevents duplicate business identifiers such as email and SKU.\n"
        << "NOT NULL prevents required attributes from being absent.\n"
        << "CHECK limits values to valid domain states.\n"
        << "DEFAULT supplies a value when the caller omits an optional column value.\n"
        << "FOREIGN KEY preserves relationships between parent and child rows.\n"
        << "Together these constraints prevent invalid relational state at the data boundary.\n";

    return 0;
}

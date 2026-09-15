/*
 * Backend Project Structure
 * =========================
 *
 * C++17 case study:
 *     A layered order-processing backend.
 *
 * The program demonstrates how a backend can separate:
 *
 *     Configuration
 *         |
 *     Controller
 *         |
 *     Service
 *         |
 *     Repository
 *         |
 *     In-memory persistence
 *
 * The scenario models a small e-commerce order system.
 *
 * Compile:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic backend_project_structure.cpp -o backend
 *
 * Run:
 *     ./backend
 *
 * On Windows with MinGW:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic backend_project_structure.cpp -o backend.exe
 */

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>


// ============================================================================
// 1. DOMAIN ENUMS
// ============================================================================

enum class OrderStatus {
    Pending,
    Paid,
    Cancelled
};

enum class PaymentStatus {
    Unpaid,
    Paid
};

std::string toString(OrderStatus status) {
    switch (status) {
        case OrderStatus::Pending:
            return "pending";
        case OrderStatus::Paid:
            return "paid";
        case OrderStatus::Cancelled:
            return "cancelled";
    }

    return "unknown";
}

std::string toString(PaymentStatus status) {
    switch (status) {
        case PaymentStatus::Unpaid:
            return "unpaid";
        case PaymentStatus::Paid:
            return "paid";
    }

    return "unknown";
}


// ============================================================================
// 2. APPLICATION EXCEPTIONS
// ============================================================================

class ApplicationError : public std::runtime_error {
public:
    explicit ApplicationError(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationError : public ApplicationError {
public:
    explicit ValidationError(const std::string& message)
        : ApplicationError(message) {}
};

class NotFoundError : public ApplicationError {
public:
    explicit NotFoundError(const std::string& message)
        : ApplicationError(message) {}
};

class AuthorizationError : public ApplicationError {
public:
    explicit AuthorizationError(const std::string& message)
        : ApplicationError(message) {}
};

class ConflictError : public ApplicationError {
public:
    explicit ConflictError(const std::string& message)
        : ApplicationError(message) {}
};


// ============================================================================
// 3. CONFIGURATION
// ============================================================================

struct Config {
    std::string environment = "development";
    std::string databaseUrl = "memory://orders";
    std::size_t maxItemsPerOrder = 20;
    double taxRate = 0.18;
    bool debug = true;

    void validate() const {
        if (maxItemsPerOrder == 0) {
            throw ValidationError(
                "Maximum items per order must be positive"
            );
        }

        if (taxRate < 0.0 || taxRate > 1.0) {
            throw ValidationError(
                "Tax rate must be between 0 and 1"
            );
        }

        if (environment == "production" && debug) {
            throw ValidationError(
                "Debug mode must be disabled in production"
            );
        }

        if (environment == "production" &&
            databaseUrl.rfind("memory://", 0) == 0) {
            throw ValidationError(
                "Production requires persistent storage"
            );
        }
    }
};


// ============================================================================
// 4. DOMAIN MODELS
// ============================================================================

struct Product {
    int id;
    std::string name;
    double price;
    int inventory;
};

struct OrderItem {
    int productId;
    std::string productName;
    int quantity;
    double unitPrice;

    double subtotal() const {
        return unitPrice * static_cast<double>(quantity);
    }
};

struct Order {
    int id = 0;
    int customerId = 0;
    std::vector<OrderItem> items;
    OrderStatus status = OrderStatus::Pending;
    PaymentStatus paymentStatus = PaymentStatus::Unpaid;

    double subtotal() const {
        double result = 0.0;

        for (const auto& item : items) {
            result += item.subtotal();
        }

        return result;
    }

    double tax(double taxRate) const {
        return subtotal() * taxRate;
    }

    double total(double taxRate) const {
        return subtotal() + tax(taxRate);
    }
};


// ============================================================================
// 5. UTILITY FUNCTIONS
// ============================================================================

namespace Utility {

std::string trim(const std::string& input) {
    const auto first = input.find_first_not_of(" \t\n\r");

    if (first == std::string::npos) {
        return "";
    }

    const auto last = input.find_last_not_of(" \t\n\r");

    return input.substr(
        first,
        last - first + 1
    );
}

void requirePositive(int value, const std::string& fieldName) {
    if (value <= 0) {
        throw ValidationError(
            fieldName + " must be positive"
        );
    }
}

void requirePositiveQuantity(int quantity) {
    if (quantity <= 0) {
        throw ValidationError(
            "Quantity must be positive"
        );
    }
}

} // namespace Utility


// ============================================================================
// 6. PRODUCT REPOSITORY INTERFACE
// ============================================================================

class ProductRepository {
public:
    virtual ~ProductRepository() = default;

    virtual std::optional<Product> findById(int productId) const = 0;

    virtual bool reduceInventory(
        int productId,
        int quantity
    ) = 0;
};


// ============================================================================
// 7. ORDER REPOSITORY INTERFACE
// ============================================================================

class OrderRepository {
public:
    virtual ~OrderRepository() = default;

    virtual Order create(Order order) = 0;

    virtual std::optional<Order> findById(
        int orderId
    ) const = 0;

    virtual Order update(Order order) = 0;

    virtual std::vector<Order> findByCustomer(
        int customerId
    ) const = 0;
};


// ============================================================================
// 8. IN-MEMORY PRODUCT REPOSITORY
// ============================================================================

class InMemoryProductRepository : public ProductRepository {
private:
    std::unordered_map<int, Product> products;

public:
    explicit InMemoryProductRepository(
        std::vector<Product> initialProducts
    ) {
        for (const auto& product : initialProducts) {
            products.emplace(product.id, product);
        }
    }

    std::optional<Product> findById(
        int productId
    ) const override {
        const auto iterator = products.find(productId);

        if (iterator == products.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    bool reduceInventory(
        int productId,
        int quantity
    ) override {
        auto iterator = products.find(productId);

        if (iterator == products.end()) {
            return false;
        }

        if (iterator->second.inventory < quantity) {
            return false;
        }

        iterator->second.inventory -= quantity;

        return true;
    }
};


// ============================================================================
// 9. IN-MEMORY ORDER REPOSITORY
// ============================================================================

class InMemoryOrderRepository : public OrderRepository {
private:
    std::unordered_map<int, Order> orders;
    int nextId = 1;

public:
    Order create(Order order) override {
        order.id = nextId++;
        orders[order.id] = order;

        return order;
    }

    std::optional<Order> findById(
        int orderId
    ) const override {
        const auto iterator = orders.find(orderId);

        if (iterator == orders.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    Order update(Order order) override {
        if (orders.find(order.id) == orders.end()) {
            throw NotFoundError(
                "Order does not exist"
            );
        }

        orders[order.id] = order;

        return order;
    }

    std::vector<Order> findByCustomer(
        int customerId
    ) const override {
        std::vector<Order> result;

        for (const auto& [id, order] : orders) {
            if (order.customerId == customerId) {
                result.push_back(order);
            }
        }

        return result;
    }
};


// ============================================================================
// 10. SERVICE LAYER
// ============================================================================

class OrderService {
private:
    std::shared_ptr<OrderRepository> orderRepository;
    std::shared_ptr<ProductRepository> productRepository;
    Config config;

public:
    OrderService(
        std::shared_ptr<OrderRepository> orderRepositoryValue,
        std::shared_ptr<ProductRepository> productRepositoryValue,
        Config configValue
    )
        : orderRepository(std::move(orderRepositoryValue)),
          productRepository(std::move(productRepositoryValue)),
          config(std::move(configValue)) {}

    Order createOrder(
        int customerId,
        const std::vector<std::pair<int, int>>& requestedItems
    ) {
        Utility::requirePositive(
            customerId,
            "Customer ID"
        );

        if (requestedItems.empty()) {
            throw ValidationError(
                "An order must contain at least one item"
            );
        }

        if (requestedItems.size() > config.maxItemsPerOrder) {
            throw ValidationError(
                "Order contains too many distinct products"
            );
        }

        Order order;
        order.customerId = customerId;

        /*
         * Validate all products and quantities before mutating inventory.
         *
         * This is an important transaction-like design principle:
         * validate the complete request before making irreversible changes.
         */

        for (const auto& [productId, quantity] : requestedItems) {
            Utility::requirePositive(
                productId,
                "Product ID"
            );

            Utility::requirePositiveQuantity(quantity);

            const auto product =
                productRepository->findById(productId);

            if (!product.has_value()) {
                throw NotFoundError(
                    "Product " +
                    std::to_string(productId) +
                    " was not found"
                );
            }

            if (product->inventory < quantity) {
                throw ConflictError(
                    "Insufficient inventory for product " +
                    std::to_string(productId)
                );
            }

            order.items.push_back(
                OrderItem{
                    product->id,
                    product->name,
                    quantity,
                    product->price
                }
            );
        }

        /*
         * Inventory changes happen only after all requested products pass
         * validation. A real database-backed implementation should perform
         * these operations inside an actual database transaction.
         */

        for (const auto& item : order.items) {
            const bool reduced =
                productRepository->reduceInventory(
                    item.productId,
                    item.quantity
                );

            if (!reduced) {
                throw ConflictError(
                    "Inventory changed before order completion"
                );
            }
        }

        return orderRepository->create(order);
    }

    Order getOrder(
        int actorCustomerId,
        int orderId
    ) const {
        Utility::requirePositive(
            actorCustomerId,
            "Customer ID"
        );

        Utility::requirePositive(
            orderId,
            "Order ID"
        );

        const auto order =
            orderRepository->findById(orderId);

        if (!order.has_value()) {
            throw NotFoundError(
                "Order was not found"
            );
        }

        if (order->customerId != actorCustomerId) {
            throw AuthorizationError(
                "Customer cannot access this order"
            );
        }

        return order.value();
    }

    Order payOrder(
        int actorCustomerId,
        int orderId
    ) {
        Order order = getOrder(
            actorCustomerId,
            orderId
        );

        if (order.status == OrderStatus::Cancelled) {
            throw ConflictError(
                "Cancelled order cannot be paid"
            );
        }

        if (order.paymentStatus == PaymentStatus::Paid) {
            throw ConflictError(
                "Order is already paid"
            );
        }

        /*
         * In a real system, payment processing should be delegated to a
         * payment gateway component and coordinated using appropriate
         * transaction/idempotency mechanisms.
         */

        order.paymentStatus = PaymentStatus::Paid;
        order.status = OrderStatus::Paid;

        return orderRepository->update(order);
    }

    Order cancelOrder(
        int actorCustomerId,
        int orderId
    ) {
        Order order = getOrder(
            actorCustomerId,
            orderId
        );

        if (order.status == OrderStatus::Paid) {
            throw ConflictError(
                "A paid order cannot be cancelled by this operation"
            );
        }

        if (order.status == OrderStatus::Cancelled) {
            throw ConflictError(
                "Order is already cancelled"
            );
        }

        order.status = OrderStatus::Cancelled;

        return orderRepository->update(order);
    }

    std::vector<Order> listCustomerOrders(
        int customerId
    ) const {
        Utility::requirePositive(
            customerId,
            "Customer ID"
        );

        return orderRepository->findByCustomer(
            customerId
        );
    }
};


// ============================================================================
// 11. PRESENTATION / CONTROLLER LAYER
// ============================================================================

class OrderController {
private:
    OrderService& service;
    const Config& config;

    static std::string formatMoney(double value) {
        std::ostringstream output;

        output << std::fixed
               << std::setprecision(2)
               << value;

        return output.str();
    }

    static void printOrder(
        const Order& order,
        const Config& config
    ) {
        std::cout
            << "Order #" << order.id
            << " | customer=" << order.customerId
            << " | status=" << toString(order.status)
            << " | payment=" << toString(order.paymentStatus)
            << "\n";

        for (const auto& item : order.items) {
            std::cout
                << "  "
                << item.productName
                << " x" << item.quantity
                << " @ " << formatMoney(item.unitPrice)
                << " = " << formatMoney(item.subtotal())
                << "\n";
        }

        std::cout
            << "  Subtotal: "
            << formatMoney(order.subtotal())
            << "\n";

        std::cout
            << "  Tax: "
            << formatMoney(order.tax(config.taxRate))
            << "\n";

        std::cout
            << "  Total: "
            << formatMoney(order.total(config.taxRate))
            << "\n";
    }

public:
    OrderController(
        OrderService& serviceValue,
        const Config& configValue
    )
        : service(serviceValue),
          config(configValue) {}

    void create(
        int customerId,
        const std::vector<std::pair<int, int>>& items
    ) {
        try {
            const Order order =
                service.createOrder(
                    customerId,
                    items
                );

            std::cout << "\nCREATE ORDER\n";
            printOrder(order, config);
        }
        catch (const ApplicationError& error) {
            std::cout
                << "Request rejected: "
                << error.what()
                << "\n";
        }
    }

    void get(
        int customerId,
        int orderId
    ) {
        try {
            const Order order =
                service.getOrder(
                    customerId,
                    orderId
                );

            std::cout << "\nGET ORDER\n";
            printOrder(order, config);
        }
        catch (const ApplicationError& error) {
            std::cout
                << "Request rejected: "
                << error.what()
                << "\n";
        }
    }

    void pay(
        int customerId,
        int orderId
    ) {
        try {
            const Order order =
                service.payOrder(
                    customerId,
                    orderId
                );

            std::cout << "\nPAY ORDER\n";
            printOrder(order, config);
        }
        catch (const ApplicationError& error) {
            std::cout
                << "Request rejected: "
                << error.what()
                << "\n";
        }
    }

    void cancel(
        int customerId,
        int orderId
    ) {
        try {
            const Order order =
                service.cancelOrder(
                    customerId,
                    orderId
                );

            std::cout << "\nCANCEL ORDER\n";
            printOrder(order, config);
        }
        catch (const ApplicationError& error) {
            std::cout
                << "Request rejected: "
                << error.what()
                << "\n";
        }
    }
};


// ============================================================================
// 12. APPLICATION COMPOSITION ROOT
// ============================================================================

class Application {
private:
    Config config;

    std::shared_ptr<InMemoryOrderRepository> orderRepository;
    std::shared_ptr<InMemoryProductRepository> productRepository;

    std::unique_ptr<OrderService> orderService;
    std::unique_ptr<OrderController> orderController;

public:
    Application() {
        /*
         * The composition root decides which concrete infrastructure
         * implementations the application uses.
         */

        config.environment = "development";
        config.databaseUrl = "memory://orders";
        config.maxItemsPerOrder = 5;
        config.taxRate = 0.18;
        config.debug = true;

        config.validate();

        productRepository =
            std::make_shared<InMemoryProductRepository>(
                std::vector<Product>{
                    {1, "Laptop", 75000.0, 10},
                    {2, "Keyboard", 2500.0, 30},
                    {3, "Mouse", 1200.0, 50},
                    {4, "Monitor", 18000.0, 5}
                }
            );

        orderRepository =
            std::make_shared<InMemoryOrderRepository>();

        orderService =
            std::make_unique<OrderService>(
                orderRepository,
                productRepository,
                config
            );

        orderController =
            std::make_unique<OrderController>(
                *orderService,
                config
            );
    }

    OrderController& controller() {
        return *orderController;
    }
};


// ============================================================================
// 13. EDGE CASES AND FAILURE CONDITIONS
// ============================================================================

void demonstrateFailureCases(
    OrderController& controller
) {
    std::cout << "\nFAILURE CASES\n";

    // Empty order.
    controller.create(
        10,
        {}
    );

    // Invalid customer.
    controller.create(
        0,
        {{1, 1}}
    );

    // Unknown product.
    controller.create(
        10,
        {{999, 1}}
    );

    // Quantity larger than available inventory.
    controller.create(
        10,
        {{4, 100}}
    );

    // Invalid quantity.
    controller.create(
        10,
        {{1, 0}}
    );
}


// ============================================================================
// 14. AUTHORIZATION CASE
// ============================================================================

void demonstrateAuthorization(
    OrderController& controller
) {
    std::cout << "\nAUTHORIZATION CASE\n";

    controller.create(
        101,
        {
            {2, 2},
            {3, 1}
        }
    );

    // The order created above has ID 1 in this fresh application.
    // A different customer attempts to access it.
    controller.get(
        999,
        1
    );
}


// ============================================================================
// 15. NORMAL WORKFLOW
// ============================================================================

void demonstrateNormalWorkflow(
    OrderController& controller
) {
    std::cout << "\nNORMAL WORKFLOW\n";

    controller.create(
        500,
        {
            {1, 1},
            {2, 2},
            {3, 1}
        }
    );

    controller.get(
        500,
        1
    );

    controller.pay(
        500,
        1
    );

    // Paying a second time demonstrates idempotency/conflict handling.
    controller.pay(
        500,
        1
    );

    // A paid order cannot be cancelled through this simplified workflow.
    controller.cancel(
        500,
        1
    );
}


// ============================================================================
// 16. PERFORMANCE MEASUREMENT
// ============================================================================

void demonstratePerformance() {
    /*
     * unordered_map provides average O(1) lookup by key.

     * The exact performance depends on hashing, load factor, memory locality,
     * compiler optimizations, hardware, and workload.

     * Benchmarking here is educational. It does not represent a production
     * database benchmark.
     */

    std::unordered_map<int, Product> products;

    for (int id = 1; id <= 100000; ++id) {
        products.emplace(
            id,
            Product{
                id,
                "Product " + std::to_string(id),
                100.0,
                100
            }
        );
    }

    const auto start =
        std::chrono::steady_clock::now();

    volatile int inventoryAccumulator = 0;

    for (int iteration = 0; iteration < 100000; ++iteration) {
        const int id = (iteration % 100000) + 1;

        const auto iterator = products.find(id);

        if (iterator != products.end()) {
            inventoryAccumulator += iterator->second.inventory;
        }
    }

    const auto end =
        std::chrono::steady_clock::now();

    const auto elapsed =
        std::chrono::duration_cast<
            std::chrono::microseconds
        >(end - start);

    std::cout
        << "\nPERFORMANCE\n"
        << "100,000 hash-map lookups: "
        << elapsed.count()
        << " microseconds\n"
        << "Accumulator: "
        << inventoryAccumulator
        << "\n";
}


// ============================================================================
// 17. ARCHITECTURAL TRADE-OFFS
// ============================================================================

void printArchitectureNotes() {
    std::cout
        << R"(
ARCHITECTURE NOTES

Layered architecture:
    Controller -> Service -> Repository

Controller responsibility:
    Request/response concerns and translation of errors into API responses.

Service responsibility:
    Business rules, workflow coordination, authorization, and transactions.

Repository responsibility:
    Persistence operations.

Domain responsibility:
    Business entities and state.

Configuration responsibility:
    Environment-specific behavior.

Utility responsibility:
    Small reusable operations without ownership of business workflows.

Trade-off:
    More layers create more classes and indirection.
    Fewer layers create faster initial development but can cause coupling.

A structure should be proportional to system complexity.
)"
        << "\n";
}


// ============================================================================
// 18. MAIN
// ============================================================================

int main() {
    try {
        std::cout
            << "============================================================\n"
            << "BACKEND PROJECT STRUCTURE - C++ CASE STUDY\n"
            << "============================================================\n";

        Application application;

        demonstrateNormalWorkflow(
            application.controller()
        );

        demonstrateFailureCases(
            application.controller()
        );

        demonstrateAuthorization(
            application.controller()
        );

        demonstratePerformance();

        printArchitectureNotes();

        std::cout
            << "Case study complete.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal application error: "
            << error.what()
            << "\n";

        return 1;
    }
}

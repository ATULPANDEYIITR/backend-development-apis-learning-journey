/*
 * Dependency Injection: Industry-Style Order Processing System
 *
 * C++17 case study demonstrating:
 *   - Dependencies
 *   - Interfaces and abstractions
 *   - Constructor injection
 *   - Dependency chains
 *   - Database dependencies
 *   - Repositories
 *   - Payment and notification services
 *   - Validation
 *   - Error handling
 *   - Ownership and lifetimes
 *   - Dependency containers
 *   - Testing with fakes
 *   - Complexity and performance considerations
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic dependency_injection.cpp -o dependency_injection
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
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
// 1. DOMAIN MODEL
// ============================================================================

struct User {
    int id;
    std::string name;
    std::string email;
};

struct Product {
    int id;
    std::string name;
    double price;
};

struct OrderItem {
    int productId;
    int quantity;
};

struct Order {
    int id;
    int userId;
    std::vector<OrderItem> items;
    double total = 0.0;
};

// ============================================================================
// 2. DATABASE ABSTRACTION
// ============================================================================

class IDatabase {
public:
    virtual ~IDatabase() = default;

    virtual std::optional<User> findUser(int userId) const = 0;
    virtual std::optional<Product> findProduct(int productId) const = 0;
    virtual bool saveOrder(const Order& order) = 0;
};

// ============================================================================
// 3. IN-MEMORY DATABASE
// ============================================================================

class InMemoryDatabase final : public IDatabase {
private:
    std::unordered_map<int, User> users_;
    std::unordered_map<int, Product> products_;
    std::unordered_map<int, Order> orders_;

public:
    InMemoryDatabase() {
        users_.emplace(
            1,
            User{1, "Alice", "alice@example.com"}
        );

        users_.emplace(
            2,
            User{2, "Bob", "bob@example.com"}
        );

        products_.emplace(
            101,
            Product{101, "Keyboard", 75.00}
        );

        products_.emplace(
            102,
            Product{102, "Mouse", 25.00}
        );

        products_.emplace(
            103,
            Product{103, "Monitor", 250.00}
        );
    }

    std::optional<User> findUser(int userId) const override {
        auto iterator = users_.find(userId);

        if (iterator == users_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    std::optional<Product> findProduct(int productId) const override {
        auto iterator = products_.find(productId);

        if (iterator == products_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    bool saveOrder(const Order& order) override {
        if (orders_.contains(order.id)) {
            return false;
        }

        orders_.emplace(order.id, order);
        return true;
    }

    std::size_t orderCount() const {
        return orders_.size();
    }
};

// ============================================================================
// 4. REPOSITORY ABSTRACTIONS
// ============================================================================

class IUserRepository {
public:
    virtual ~IUserRepository() = default;
    virtual std::optional<User> findById(int userId) const = 0;
};

class IProductRepository {
public:
    virtual ~IProductRepository() = default;
    virtual std::optional<Product> findById(int productId) const = 0;
};

class IOrderRepository {
public:
    virtual ~IOrderRepository() = default;
    virtual bool save(const Order& order) = 0;
};

// ============================================================================
// 5. DATABASE-BACKED REPOSITORIES
// ============================================================================

class DatabaseUserRepository final : public IUserRepository {
private:
    IDatabase& database_;

public:
    // Constructor injection of the database dependency.
    explicit DatabaseUserRepository(IDatabase& database)
        : database_(database) {}

    std::optional<User> findById(int userId) const override {
        return database_.findUser(userId);
    }
};

class DatabaseProductRepository final : public IProductRepository {
private:
    IDatabase& database_;

public:
    explicit DatabaseProductRepository(IDatabase& database)
        : database_(database) {}

    std::optional<Product> findById(int productId) const override {
        return database_.findProduct(productId);
    }
};

class DatabaseOrderRepository final : public IOrderRepository {
private:
    IDatabase& database_;

public:
    explicit DatabaseOrderRepository(IDatabase& database)
        : database_(database) {}

    bool save(const Order& order) override {
        return database_.saveOrder(order);
    }
};

// ============================================================================
// 6. APPLICATION SERVICES
// ============================================================================

class INotificationService {
public:
    virtual ~INotificationService() = default;

    virtual void notify(
        const User& user,
        const std::string& message
    ) = 0;
};

class ConsoleNotificationService final
    : public INotificationService {
public:
    void notify(
        const User& user,
        const std::string& message
    ) override {
        std::cout
            << "[NOTIFICATION] "
            << user.email
            << ": "
            << message
            << '\n';
    }
};

class IAuditLogger {
public:
    virtual ~IAuditLogger() = default;

    virtual void record(const std::string& event) = 0;
};

class ConsoleAuditLogger final : public IAuditLogger {
public:
    void record(const std::string& event) override {
        std::cout << "[AUDIT] " << event << '\n';
    }
};

// ============================================================================
// 7. PAYMENT DEPENDENCY
// ============================================================================

class IPaymentGateway {
public:
    virtual ~IPaymentGateway() = default;

    virtual std::string charge(
        double amount
    ) = 0;
};

class FakePaymentGateway final : public IPaymentGateway {
private:
    bool shouldFail_;

public:
    explicit FakePaymentGateway(bool shouldFail = false)
        : shouldFail_(shouldFail) {}

    std::string charge(double amount) override {
        if (!std::isfinite(amount) || amount <= 0.0) {
            throw std::invalid_argument(
                "Payment amount must be positive."
            );
        }

        if (shouldFail_) {
            throw std::runtime_error(
                "Payment gateway unavailable."
            );
        }

        std::ostringstream id;
        id << "PAY-" << static_cast<long long>(
            std::llround(amount * 100.0)
        );

        return id.str();
    }
};

// ============================================================================
// 8. ORDER VALIDATOR
// ============================================================================

class OrderValidator {
public:
    void validate(const Order& order) const {
        if (order.id <= 0) {
            throw std::invalid_argument(
                "Order ID must be positive."
            );
        }

        if (order.userId <= 0) {
            throw std::invalid_argument(
                "User ID must be positive."
            );
        }

        if (order.items.empty()) {
            throw std::invalid_argument(
                "Order must contain at least one item."
            );
        }

        for (const auto& item : order.items) {
            if (item.productId <= 0) {
                throw std::invalid_argument(
                    "Product ID must be positive."
                );
            }

            if (item.quantity <= 0) {
                throw std::invalid_argument(
                    "Quantity must be positive."
                );
            }
        }
    }
};

// ============================================================================
// 9. PAYMENT SERVICE
// ============================================================================

class PaymentService {
private:
    IPaymentGateway& gateway_;

public:
    explicit PaymentService(IPaymentGateway& gateway)
        : gateway_(gateway) {}

    std::optional<std::string> pay(double amount) {
        try {
            return gateway_.charge(amount);
        } catch (const std::exception& error) {
            std::cerr
                << "[PAYMENT ERROR] "
                << error.what()
                << '\n';

            return std::nullopt;
        }
    }
};

// ============================================================================
// 10. ORDER SERVICE: DEPENDENCY CHAIN
// ============================================================================

class OrderService {
private:
    IUserRepository& userRepository_;
    IProductRepository& productRepository_;
    IOrderRepository& orderRepository_;
    INotificationService& notificationService_;
    IAuditLogger& auditLogger_;
    PaymentService& paymentService_;
    const OrderValidator& validator_;

public:
    /*
     * This is the dependency chain:
     *
     * OrderService
     *   |
     *   +--> IUserRepository
     *   |       |
     *   |       +--> IDatabase
     *   |
     *   +--> IProductRepository
     *   |       |
     *   |       +--> IDatabase
     *   |
     *   +--> IOrderRepository
     *   |       |
     *   |       +--> IDatabase
     *   |
     *   +--> INotificationService
     *   +--> IAuditLogger
     *   +--> PaymentService
     *           |
     *           +--> IPaymentGateway
     *
     * The high-level service depends on abstractions.
     */
    OrderService(
        IUserRepository& userRepository,
        IProductRepository& productRepository,
        IOrderRepository& orderRepository,
        INotificationService& notificationService,
        IAuditLogger& auditLogger,
        PaymentService& paymentService,
        const OrderValidator& validator
    )
        : userRepository_(userRepository),
          productRepository_(productRepository),
          orderRepository_(orderRepository),
          notificationService_(notificationService),
          auditLogger_(auditLogger),
          paymentService_(paymentService),
          validator_(validator) {}

    bool placeOrder(Order order) {
        try {
            validator_.validate(order);

            const auto user =
                userRepository_.findById(order.userId);

            if (!user.has_value()) {
                throw std::runtime_error(
                    "User does not exist."
                );
            }

            double total = 0.0;

            for (const auto& item : order.items) {
                const auto product =
                    productRepository_.findById(item.productId);

                if (!product.has_value()) {
                    throw std::runtime_error(
                        "Product does not exist."
                    );
                }

                total +=
                    product->price *
                    static_cast<double>(item.quantity);
            }

            if (!std::isfinite(total) || total <= 0.0) {
                throw std::runtime_error(
                    "Calculated order total is invalid."
                );
            }

            order.total = total;

            const auto paymentId =
                paymentService_.pay(order.total);

            if (!paymentId.has_value()) {
                throw std::runtime_error(
                    "Payment failed."
                );
            }

            if (!orderRepository_.save(order)) {
                throw std::runtime_error(
                    "Could not persist order."
                );
            }

            auditLogger_.record(
                "Order " +
                std::to_string(order.id) +
                " created with payment " +
                *paymentId
            );

            notificationService_.notify(
                *user,
                "Order " +
                std::to_string(order.id) +
                " confirmed. Total: " +
                formatMoney(order.total)
            );

            return true;
        } catch (const std::exception& error) {
            auditLogger_.record(
                "Order " +
                std::to_string(order.id) +
                " failed: " +
                error.what()
            );

            return false;
        }
    }

private:
    static std::string formatMoney(double value) {
        std::ostringstream output;
        output
            << std::fixed
            << std::setprecision(2)
            << value;

        return output.str();
    }
};

// ============================================================================
// 11. TEST DOUBLES
// ============================================================================

class RecordingNotificationService final
    : public INotificationService {
public:
    struct Message {
        int userId;
        std::string text;
    };

private:
    std::vector<Message> messages_;

public:
    void notify(
        const User& user,
        const std::string& message
    ) override {
        messages_.push_back({user.id, message});
    }

    const std::vector<Message>& messages() const {
        return messages_;
    }
};

class RecordingAuditLogger final
    : public IAuditLogger {
private:
    std::vector<std::string> events_;

public:
    void record(const std::string& event) override {
        events_.push_back(event);
    }

    const std::vector<std::string>& events() const {
        return events_;
    }
};

class TestPaymentGateway final : public IPaymentGateway {
private:
    bool fail_;
    int chargeCount_ = 0;

public:
    explicit TestPaymentGateway(bool fail)
        : fail_(fail) {}

    std::string charge(double amount) override {
        ++chargeCount_;

        if (amount <= 0.0) {
            throw std::invalid_argument(
                "Invalid amount."
            );
        }

        if (fail_) {
            throw std::runtime_error(
                "Simulated gateway failure."
            );
        }

        return "TEST-PAYMENT";
    }

    int chargeCount() const {
        return chargeCount_;
    }
};

// ============================================================================
// 12. DATABASE TEST DOUBLE
// ============================================================================

class TestDatabase final : public IDatabase {
private:
    std::unordered_map<int, User> users_;
    std::unordered_map<int, Product> products_;
    std::vector<Order> orders_;

public:
    TestDatabase() {
        users_.emplace(
            1,
            User{1, "Test User", "test@example.com"}
        );

        products_.emplace(
            10,
            Product{10, "Test Product", 100.00}
        );
    }

    std::optional<User> findUser(int userId) const override {
        auto iterator = users_.find(userId);

        if (iterator == users_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    std::optional<Product> findProduct(
        int productId
    ) const override {
        auto iterator = products_.find(productId);

        if (iterator == products_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    bool saveOrder(const Order& order) override {
        auto duplicate = std::find_if(
            orders_.begin(),
            orders_.end(),
            [&order](const Order& existing) {
                return existing.id == order.id;
            }
        );

        if (duplicate != orders_.end()) {
            return false;
        }

        orders_.push_back(order);
        return true;
    }

    std::size_t orderCount() const {
        return orders_.size();
    }
};

// ============================================================================
// 13. MANUAL COMPOSITION
// ============================================================================

struct Application {
    std::unique_ptr<IDatabase> database;
    std::unique_ptr<IUserRepository> userRepository;
    std::unique_ptr<IProductRepository> productRepository;
    std::unique_ptr<IOrderRepository> orderRepository;
    std::unique_ptr<INotificationService> notificationService;
    std::unique_ptr<IAuditLogger> auditLogger;
    std::unique_ptr<IPaymentGateway> paymentGateway;
    std::unique_ptr<PaymentService> paymentService;
    std::unique_ptr<OrderService> orderService;
};

/*
 * The composition root is where concrete classes are selected and connected.
 *
 * Notice that OrderService itself does not know how the objects are created.
 */
Application buildApplication() {
    Application application;

    application.database =
        std::make_unique<InMemoryDatabase>();

    application.userRepository =
        std::make_unique<DatabaseUserRepository>(
            *application.database
        );

    application.productRepository =
        std::make_unique<DatabaseProductRepository>(
            *application.database
        );

    application.orderRepository =
        std::make_unique<DatabaseOrderRepository>(
            *application.database
        );

    application.notificationService =
        std::make_unique<ConsoleNotificationService>();

    application.auditLogger =
        std::make_unique<ConsoleAuditLogger>();

    application.paymentGateway =
        std::make_unique<FakePaymentGateway>();

    application.paymentService =
        std::make_unique<PaymentService>(
            *application.paymentGateway
        );

    auto validator =
        std::make_unique<OrderValidator>();

    /*
     * OrderService needs a stable reference to the validator.
     * The validator is therefore stored in a shared owner in a more
     * production-oriented design. This local demonstration instead
     * constructs the service below after moving the validator into a
     * static application-owned object.
     *
     * A cleaner representation is implemented by ApplicationWithValidator.
     */

    return application;
}

// ============================================================================
// 14. EXPLICIT APPLICATION OWNER
// ============================================================================

class ApplicationWithValidator {
private:
    std::unique_ptr<InMemoryDatabase> database_;
    std::unique_ptr<DatabaseUserRepository> userRepository_;
    std::unique_ptr<DatabaseProductRepository> productRepository_;
    std::unique_ptr<DatabaseOrderRepository> orderRepository_;
    std::unique_ptr<ConsoleNotificationService> notificationService_;
    std::unique_ptr<ConsoleAuditLogger> auditLogger_;
    std::unique_ptr<FakePaymentGateway> paymentGateway_;
    std::unique_ptr<PaymentService> paymentService_;
    std::unique_ptr<OrderValidator> validator_;
    std::unique_ptr<OrderService> orderService_;

public:
    ApplicationWithValidator() {
        /*
         * Member construction order matters in C++.
         * Each object is created only after its dependencies exist.
         */
        database_ =
            std::make_unique<InMemoryDatabase>();

        userRepository_ =
            std::make_unique<DatabaseUserRepository>(
                *database_
            );

        productRepository_ =
            std::make_unique<DatabaseProductRepository>(
                *database_
            );

        orderRepository_ =
            std::make_unique<DatabaseOrderRepository>(
                *database_
            );

        notificationService_ =
            std::make_unique<ConsoleNotificationService>();

        auditLogger_ =
            std::make_unique<ConsoleAuditLogger>();

        paymentGateway_ =
            std::make_unique<FakePaymentGateway>();

        paymentService_ =
            std::make_unique<PaymentService>(
                *paymentGateway_
            );

        validator_ =
            std::make_unique<OrderValidator>();

        orderService_ =
            std::make_unique<OrderService>(
                *userRepository_,
                *productRepository_,
                *orderRepository_,
                *notificationService_,
                *auditLogger_,
                *paymentService_,
                *validator_
            );
    }

    bool placeOrder(Order order) {
        return orderService_->placeOrder(
            std::move(order)
        );
    }

    std::size_t orderCount() const {
        return database_->orderCount();
    }
};

// ============================================================================
// 15. MANUAL TEST CASES
// ============================================================================

bool runSuccessfulOrderTest() {
    TestDatabase database;
    DatabaseUserRepository userRepository(database);
    DatabaseProductRepository productRepository(database);
    DatabaseOrderRepository orderRepository(database);

    RecordingNotificationService notifications;
    RecordingAuditLogger audit;
    TestPaymentGateway paymentGateway(false);
    PaymentService paymentService(paymentGateway);
    OrderValidator validator;

    OrderService service(
        userRepository,
        productRepository,
        orderRepository,
        notifications,
        audit,
        paymentService,
        validator
    );

    Order order;
    order.id = 1001;
    order.userId = 1;
    order.items = {
        OrderItem{10, 2}
    };

    const bool success = service.placeOrder(order);

    if (!success) {
        return false;
    }

    if (database.orderCount() != 1) {
        return false;
    }

    if (paymentGateway.chargeCount() != 1) {
        return false;
    }

    if (notifications.messages().size() != 1) {
        return false;
    }

    return true;
}

bool runUnknownUserTest() {
    TestDatabase database;
    DatabaseUserRepository userRepository(database);
    DatabaseProductRepository productRepository(database);
    DatabaseOrderRepository orderRepository(database);

    RecordingNotificationService notifications;
    RecordingAuditLogger audit;
    TestPaymentGateway paymentGateway(false);
    PaymentService paymentService(paymentGateway);
    OrderValidator validator;

    OrderService service(
        userRepository,
        productRepository,
        orderRepository,
        notifications,
        audit,
        paymentService,
        validator
    );

    Order order;
    order.id = 1002;
    order.userId = 999;
    order.items = {
        OrderItem{10, 1}
    };

    return !service.placeOrder(order)
        && database.orderCount() == 0
        && paymentGateway.chargeCount() == 0;
}

bool runUnknownProductTest() {
    TestDatabase database;
    DatabaseUserRepository userRepository(database);
    DatabaseProductRepository productRepository(database);
    DatabaseOrderRepository orderRepository(database);

    RecordingNotificationService notifications;
    RecordingAuditLogger audit;
    TestPaymentGateway paymentGateway(false);
    PaymentService paymentService(paymentGateway);
    OrderValidator validator;

    OrderService service(
        userRepository,
        productRepository,
        orderRepository,
        notifications,
        audit,
        paymentService,
        validator
    );

    Order order;
    order.id = 1003;
    order.userId = 1;
    order.items = {
        OrderItem{999, 1}
    };

    return !service.placeOrder(order)
        && database.orderCount() == 0
        && paymentGateway.chargeCount() == 0;
}

bool runPaymentFailureTest() {
    TestDatabase database;
    DatabaseUserRepository userRepository(database);
    DatabaseProductRepository productRepository(database);
    DatabaseOrderRepository orderRepository(database);

    RecordingNotificationService notifications;
    RecordingAuditLogger audit;
    TestPaymentGateway paymentGateway(true);
    PaymentService paymentService(paymentGateway);
    OrderValidator validator;

    OrderService service(
        userRepository,
        productRepository,
        orderRepository,
        notifications,
        audit,
        paymentService,
        validator
    );

    Order order;
    order.id = 1004;
    order.userId = 1;
    order.items = {
        OrderItem{10, 1}
    };

    return !service.placeOrder(order)
        && database.orderCount() == 0
        && notifications.messages().empty()
        && paymentGateway.chargeCount() == 1;
}

bool runInvalidOrderTest() {
    TestDatabase database;
    DatabaseUserRepository userRepository(database);
    DatabaseProductRepository productRepository(database);
    DatabaseOrderRepository orderRepository(database);

    RecordingNotificationService notifications;
    RecordingAuditLogger audit;
    TestPaymentGateway paymentGateway(false);
    PaymentService paymentService(paymentGateway);
    OrderValidator validator;

    OrderService service(
        userRepository,
        productRepository,
        orderRepository,
        notifications,
        audit,
        paymentService,
        validator
    );

    Order order;
    order.id = 1005;
    order.userId = 1;
    order.items = {
        OrderItem{10, 0}
    };

    return !service.placeOrder(order)
        && database.orderCount() == 0
        && paymentGateway.chargeCount() == 0;
}

void runTests() {
    std::cout << "\n=== AUTOMATED TESTS ===\n";

    const std::vector<std::pair<std::string, bool (*)()>> tests = {
        {"Successful order", runSuccessfulOrderTest},
        {"Unknown user", runUnknownUserTest},
        {"Unknown product", runUnknownProductTest},
        {"Payment failure", runPaymentFailureTest},
        {"Invalid order", runInvalidOrderTest}
    };

    int passed = 0;

    for (const auto& [name, test] : tests) {
        const bool result = test();

        std::cout
            << std::left
            << std::setw(22)
            << name
            << ": "
            << (result ? "PASS" : "FAIL")
            << '\n';

        if (result) {
            ++passed;
        }
    }

    if (passed != static_cast<int>(tests.size())) {
        throw std::runtime_error(
            "At least one test failed."
        );
    }

    std::cout
        << "Tests passed: "
        << passed
        << '/'
        << tests.size()
        << '\n';
}

// ============================================================================
// 16. PERFORMANCE EXAMPLE
// ============================================================================

int directCalculation(int value) {
    return value * 2;
}

void demonstratePerformance() {
    std::cout << "\n=== PERFORMANCE CONSIDERATIONS ===\n";

    constexpr int count = 1'000'000;

    auto start =
        std::chrono::high_resolution_clock::now();

    long long total = 0;

    for (int i = 0; i < count; ++i) {
        total += directCalculation(i);
    }

    auto end =
        std::chrono::high_resolution_clock::now();

    const auto elapsed =
        std::chrono::duration<double, std::micro>(
            end - start
        ).count();

    std::cout
        << "Operations: "
        << count
        << '\n';

    std::cout
        << "Result checksum: "
        << total
        << '\n';

    std::cout
        << "Elapsed microseconds: "
        << elapsed
        << '\n';

    std::cout
        << "Dependency abstractions improve substitution and testing, "
        << "while virtual dispatch can introduce a small runtime cost. "
        << "For I/O-heavy services, database and network latency usually "
        << "dominates that cost.\n";
}

// ============================================================================
// 17. COMPLETE CASE STUDY
// ============================================================================

void runCompleteCaseStudy() {
    std::cout << "\n=== COMPLETE ORDER PROCESSING CASE STUDY ===\n";

    ApplicationWithValidator application;

    Order order;
    order.id = 5001;
    order.userId = 1;
    order.items = {
        OrderItem{101, 1},
        OrderItem{102, 2},
        OrderItem{103, 1}
    };

    const bool success =
        application.placeOrder(order);

    std::cout
        << "Order result: "
        << (success ? "SUCCESS" : "FAILED")
        << '\n';

    std::cout
        << "Persisted orders: "
        << application.orderCount()
        << '\n';

    // Edge case: an empty order.
    Order emptyOrder;
    emptyOrder.id = 5002;
    emptyOrder.userId = 1;

    std::cout
        << "Empty order result: "
        << (
            application.placeOrder(emptyOrder)
                ? "SUCCESS"
                : "FAILED"
        )
        << '\n';

    // Edge case: unknown product.
    Order invalidProductOrder;
    invalidProductOrder.id = 5003;
    invalidProductOrder.userId = 1;
    invalidProductOrder.items = {
        OrderItem{99999, 1}
    };

    std::cout
        << "Unknown product result: "
        << (
            application.placeOrder(invalidProductOrder)
                ? "SUCCESS"
                : "FAILED"
        )
        << '\n';
}

// ============================================================================
// MAIN
// ============================================================================

int main() {
    try {
        std::cout
            << "============================================================\n"
            << "DEPENDENCY INJECTION - C++17 CASE STUDY\n"
            << "============================================================\n";

        runTests();
        runCompleteCaseStudy();
        demonstratePerformance();

        std::cout
            << "\nCase study completed successfully.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "\nFatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}

/*
Error Handling Case Study: Order Processing REST Service

C++17 standard-library-only implementation.

Scenario:
    A small order-processing service receives commands resembling API
    operations. It validates requests, looks up customers and products,
    checks authorization and inventory, calculates totals, and translates
    domain exceptions into structured HTTP-style responses.

The implementation demonstrates:

    - standard exceptions
    - custom exception classes
    - exception inheritance
    - structured error information
    - validation
    - domain/service/repository separation
    - HTTP-style status mapping
    - safe error messages
    - transaction-style rollback
    - input processing
    - edge cases
    - complexity considerations
    - logging
    - security-aware error responses

Compile:
    g++ -std=c++17 -Wall -Wextra -pedantic error_handling_case_study.cpp -o error_demo

Run:
    ./error_demo
*/

#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;


// =============================================================================
// 1. STRUCTURED ERROR TYPES
// =============================================================================

enum class ErrorCode {
    Validation,
    Authentication,
    Authorization,
    NotFound,
    Conflict,
    InsufficientInventory,
    Internal
};


string errorCodeToString(ErrorCode code) {
    switch (code) {
        case ErrorCode::Validation:
            return "VALIDATION_ERROR";
        case ErrorCode::Authentication:
            return "AUTHENTICATION_ERROR";
        case ErrorCode::Authorization:
            return "AUTHORIZATION_ERROR";
        case ErrorCode::NotFound:
            return "RESOURCE_NOT_FOUND";
        case ErrorCode::Conflict:
            return "CONFLICT";
        case ErrorCode::InsufficientInventory:
            return "INSUFFICIENT_INVENTORY";
        case ErrorCode::Internal:
            return "INTERNAL_SERVER_ERROR";
    }

    return "UNKNOWN_ERROR";
}


struct ErrorDetail {
    string field;
    string code;
    string message;
};


struct ErrorResponse {
    int statusCode;
    ErrorCode code;
    string message;
    string requestId;
    vector<ErrorDetail> details;

    string toJson() const {
        ostringstream output;

        output << "{";
        output << "\"error\":{";
        output << "\"code\":\"" << errorCodeToString(code) << "\",";
        output << "\"message\":\"" << message << "\",";
        output << "\"status\":" << statusCode << ",";
        output << "\"request_id\":\"" << requestId << "\",";
        output << "\"details\":[";

        for (size_t i = 0; i < details.size(); ++i) {
            const auto& detail = details[i];

            if (i > 0) {
                output << ",";
            }

            output << "{";
            output << "\"field\":\"" << detail.field << "\",";
            output << "\"code\":\"" << detail.code << "\",";
            output << "\"message\":\"" << detail.message << "\"";
            output << "}";
        }

        output << "]";
        output << "}";
        output << "}";

        return output.str();
    }
};


// =============================================================================
// 2. CUSTOM EXCEPTION HIERARCHY
// =============================================================================

class ApplicationException : public runtime_error {
public:
    ApplicationException(
        string message,
        int statusCode,
        ErrorCode code,
        vector<ErrorDetail> details = {}
    )
        : runtime_error(std::move(message)),
          statusCode_(statusCode),
          code_(code),
          details_(std::move(details)) {}

    int statusCode() const noexcept {
        return statusCode_;
    }

    ErrorCode code() const noexcept {
        return code_;
    }

    const vector<ErrorDetail>& details() const noexcept {
        return details_;
    }

private:
    int statusCode_;
    ErrorCode code_;
    vector<ErrorDetail> details_;
};


class ValidationException : public ApplicationException {
public:
    explicit ValidationException(
        string message,
        vector<ErrorDetail> details = {}
    )
        : ApplicationException(
            std::move(message),
            422,
            ErrorCode::Validation,
            std::move(details)
        ) {}
};


class AuthenticationException : public ApplicationException {
public:
    explicit AuthenticationException(string message)
        : ApplicationException(
            std::move(message),
            401,
            ErrorCode::Authentication
        ) {}
};


class AuthorizationException : public ApplicationException {
public:
    explicit AuthorizationException(string message)
        : ApplicationException(
            std::move(message),
            403,
            ErrorCode::Authorization
        ) {}
};


class NotFoundException : public ApplicationException {
public:
    explicit NotFoundException(string message)
        : ApplicationException(
            std::move(message),
            404,
            ErrorCode::NotFound
        ) {}
};


class ConflictException : public ApplicationException {
public:
    explicit ConflictException(string message)
        : ApplicationException(
            std::move(message),
            409,
            ErrorCode::Conflict
        ) {}
};


class InsufficientInventoryException : public ApplicationException {
public:
    explicit InsufficientInventoryException(
        string message,
        vector<ErrorDetail> details = {}
    )
        : ApplicationException(
            std::move(message),
            409,
            ErrorCode::InsufficientInventory,
            std::move(details)
        ) {}
};


// =============================================================================
// 3. DOMAIN MODELS
// =============================================================================

struct Customer {
    int id;
    string name;
    bool active;
    bool canCreateOrders;
};


struct Product {
    int id;
    string name;
    double price;
    int inventory;
};


struct OrderItem {
    int productId;
    int quantity;
};


struct Order {
    int id;
    int customerId;
    vector<OrderItem> items;
    double total;
    string status;
};


// =============================================================================
// 4. REPOSITORIES
// =============================================================================

class CustomerRepository {
public:
    CustomerRepository() {
        customers_.emplace(
            1,
            Customer{1, "Atul", true, true}
        );

        customers_.emplace(
            2,
            Customer{2, "Restricted User", true, false}
        );

        customers_.emplace(
            3,
            Customer{3, "Inactive User", false, true}
        );
    }

    const Customer& findById(int customerId) const {
        auto iterator = customers_.find(customerId);

        if (iterator == customers_.end()) {
            throw NotFoundException(
                "Customer does not exist."
            );
        }

        return iterator->second;
    }

private:
    unordered_map<int, Customer> customers_;
};


class ProductRepository {
public:
    ProductRepository() {
        products_.emplace(
            101,
            Product{101, "Keyboard", 75.00, 10}
        );

        products_.emplace(
            102,
            Product{102, "Monitor", 250.00, 5}
        );

        products_.emplace(
            103,
            Product{103, "Mouse", 25.00, 20}
        );
    }

    Product& findById(int productId) {
        auto iterator = products_.find(productId);

        if (iterator == products_.end()) {
            throw NotFoundException(
                "Product does not exist."
            );
        }

        return iterator->second;
    }

    const Product& findById(int productId) const {
        auto iterator = products_.find(productId);

        if (iterator == products_.end()) {
            throw NotFoundException(
                "Product does not exist."
            );
        }

        return iterator->second;
    }

private:
    unordered_map<int, Product> products_;
};


class OrderRepository {
public:
    int nextId() const {
        return nextId_;
    }

    int save(Order order) {
        const int id = nextId_++;
        order.id = id;
        orders_.emplace(id, std::move(order));
        return id;
    }

    const Order& findById(int orderId) const {
        auto iterator = orders_.find(orderId);

        if (iterator == orders_.end()) {
            throw NotFoundException(
                "Order does not exist."
            );
        }

        return iterator->second;
    }

private:
    int nextId_ = 1001;
    unordered_map<int, Order> orders_;
};


// =============================================================================
// 5. VALIDATION
// =============================================================================

void validateOrderItems(const vector<OrderItem>& items) {
    vector<ErrorDetail> details;

    if (items.empty()) {
        details.push_back({
            "items",
            "REQUIRED",
            "At least one order item is required."
        });
    }

    for (size_t index = 0; index < items.size(); ++index) {
        const auto& item = items[index];

        if (item.productId <= 0) {
            details.push_back({
                "items[" + to_string(index) + "].product_id",
                "INVALID_ID",
                "Product ID must be positive."
            });
        }

        if (item.quantity <= 0) {
            details.push_back({
                "items[" + to_string(index) + "].quantity",
                "INVALID_QUANTITY",
                "Quantity must be greater than zero."
            });
        }

        // Prevent absurdly large quantities from becoming accidental
        // resource-exhaustion inputs.
        if (item.quantity > 1000) {
            details.push_back({
                "items[" + to_string(index) + "].quantity",
                "QUANTITY_TOO_LARGE",
                "Quantity exceeds the allowed limit."
            });
        }
    }

    if (!details.empty()) {
        throw ValidationException(
            "Order validation failed.",
            std::move(details)
        );
    }
}


// =============================================================================
// 6. SERVICE LAYER
// =============================================================================

class OrderService {
public:
    OrderService(
        CustomerRepository& customerRepository,
        ProductRepository& productRepository,
        OrderRepository& orderRepository
    )
        : customers_(customerRepository),
          products_(productRepository),
          orders_(orderRepository) {}

    int createOrder(
        int customerId,
        const vector<OrderItem>& requestedItems,
        const string& authorizationToken
    ) {
        validateAuthentication(authorizationToken);
        validateOrderItems(requestedItems);

        const Customer& customer = customers_.findById(customerId);

        if (!customer.active) {
            throw ConflictException(
                "Inactive customers cannot create orders."
            );
        }

        if (!customer.canCreateOrders) {
            throw AuthorizationException(
                "Customer is not permitted to create orders."
            );
        }

        /*
        Transaction-style design:

        Before changing inventory, capture the previous values.
        If any later operation fails, restore the inventory.

        A real production service would normally rely on database
        transactions, row-level locking, optimistic concurrency, or another
        durable consistency mechanism rather than an in-memory rollback.
        */

        vector<pair<int, int>> originalInventory;
        double total = 0.0;

        try {
            for (const auto& item : requestedItems) {
                Product& product = products_.findById(item.productId);

                if (product.inventory < item.quantity) {
                    throw InsufficientInventoryException(
                        "Requested quantity is not available.",
                        {
                            {
                                "product_id",
                                "INSUFFICIENT_STOCK",
                                "Product " +
                                    to_string(item.productId) +
                                    " does not have enough inventory."
                            }
                        }
                    );
                }

                originalInventory.emplace_back(
                    item.productId,
                    product.inventory
                );

                product.inventory -= item.quantity;
                total += product.price *
                         static_cast<double>(item.quantity);
            }

            // A simple numerical sanity check protects against overflow or
            // invalid floating-point calculations in this demonstration.
            if (!std::isfinite(total) || total < 0.0) {
                throw ValidationException(
                    "Calculated order total is invalid."
                );
            }

            Order order{
                0,
                customerId,
                requestedItems,
                total,
                "CREATED"
            };

            return orders_.save(std::move(order));
        }
        catch (...) {
            // Restore every inventory value changed during this operation.
            for (const auto& [productId, previousInventory] :
                 originalInventory) {
                Product& product = products_.findById(productId);
                product.inventory = previousInventory;
            }

            throw;
        }
    }

private:
    void validateAuthentication(
        const string& authorizationToken
    ) const {
        if (authorizationToken.empty()) {
            throw AuthenticationException(
                "Authentication is required."
            );
        }

        if (authorizationToken != "Bearer demo-token") {
            throw AuthenticationException(
                "Authentication credentials are invalid."
            );
        }
    }

    CustomerRepository& customers_;
    ProductRepository& products_;
    OrderRepository& orders_;
};


// =============================================================================
// 7. HTTP-STYLE ERROR TRANSLATION
// =============================================================================

ErrorResponse convertExceptionToResponse(
    const exception& error,
    const string& requestId
) {
    const auto* applicationError =
        dynamic_cast<const ApplicationException*>(&error);

    if (applicationError != nullptr) {
        return ErrorResponse{
            applicationError->statusCode(),
            applicationError->code(),
            applicationError->what(),
            requestId,
            applicationError->details()
        };
    }

    /*
    Unexpected errors are intentionally generalized.

    A production API should not expose internal exception text, stack traces,
    database messages, filesystem paths, or implementation details to clients.
    */

    return ErrorResponse{
        500,
        ErrorCode::Internal,
        "An unexpected server error occurred.",
        requestId,
        {}
    };
}


// =============================================================================
// 8. SAFE REQUEST PROCESSING
// =============================================================================

void processCreateOrderRequest(
    OrderService& service,
    int customerId,
    const vector<OrderItem>& items,
    const string& authorization,
    const string& requestId
) {
    try {
        const int orderId = service.createOrder(
            customerId,
            items,
            authorization
        );

        cout << "{";
        cout << "\"status\":201,";
        cout << "\"data\":{";
        cout << "\"order_id\":" << orderId;
        cout << "}";
        cout << "}" << '\n';
    }
    catch (const ApplicationException& error) {
        ErrorResponse response =
            convertExceptionToResponse(error, requestId);

        cout << response.toJson() << '\n';
    }
    catch (const exception& error) {
        /*
        This is the final application boundary.

        The diagnostic message can be logged internally, but the client
        receives a generic error.
        */
        cerr << "[internal] " << error.what() << '\n';

        ErrorResponse response =
            convertExceptionToResponse(error, requestId);

        cout << response.toJson() << '\n';
    }
}


// =============================================================================
// 9. INVENTORY INSPECTION
// =============================================================================

void printKnownProducts(const ProductRepository& repository) {
    cout << "\nInventory state is intentionally represented by known products."
         << '\n';

    for (int productId : {101, 102, 103}) {
        try {
            const Product& product =
                repository.findById(productId);

            cout << "Product " << product.id
                 << " | " << product.name
                 << " | inventory=" << product.inventory
                 << " | price=" << fixed << setprecision(2)
                 << product.price
                 << '\n';
        }
        catch (const ApplicationException& error) {
            cerr << "Unable to inspect product: "
                 << error.what() << '\n';
        }
    }
}


// =============================================================================
// 10. COMPLEXITY DISCUSSION
// =============================================================================

void printComplexityNotes() {
    cout << "\n=== Complexity considerations ===\n";

    cout << "Customer lookup: average O(1) using unordered_map.\n";
    cout << "Product lookup: average O(1) using unordered_map.\n";
    cout << "Order insertion: average O(1) using unordered_map.\n";
    cout << "Order validation: O(n) for n requested items.\n";
    cout << "Order total calculation: O(n).\n";
    cout << "Inventory rollback: O(n) for changed products.\n";

    cout << "\nTrade-off:\n";
    cout << "unordered_map provides fast average lookup but does not preserve "
            "ordering.\n";

    cout << "A database-backed implementation would add transaction and "
            "concurrency considerations.\n";
}


// =============================================================================
// 11. EDGE CASES
// =============================================================================

void demonstrateEdgeCases(OrderService& service) {
    cout << "\n=== Edge cases ===\n";

    // 1. Missing authentication.
    processCreateOrderRequest(
        service,
        1,
        {{101, 1}},
        "",
        "req-auth-missing"
    );

    // 2. Invalid authentication.
    processCreateOrderRequest(
        service,
        1,
        {{101, 1}},
        "Bearer wrong-token",
        "req-auth-invalid"
    );

    // 3. Empty order.
    processCreateOrderRequest(
        service,
        1,
        {},
        "Bearer demo-token",
        "req-empty"
    );

    // 4. Unknown customer.
    processCreateOrderRequest(
        service,
        999,
        {{101, 1}},
        "Bearer demo-token",
        "req-customer-missing"
    );

    // 5. Unauthorized customer.
    processCreateOrderRequest(
        service,
        2,
        {{101, 1}},
        "Bearer demo-token",
        "req-forbidden"
    );

    // 6. Unknown product.
    processCreateOrderRequest(
        service,
        1,
        {{999, 1}},
        "Bearer demo-token",
        "req-product-missing"
    );

    // 7. Invalid quantity.
    processCreateOrderRequest(
        service,
        1,
        {{101, 0}},
        "Bearer demo-token",
        "req-invalid-quantity"
    );

    // 8. Insufficient inventory.
    processCreateOrderRequest(
        service,
        1,
        {{102, 100}},
        "Bearer demo-token",
        "req-stock"
    );

    // 9. Valid request.
    processCreateOrderRequest(
        service,
        1,
        {{101, 2}, {103, 3}},
        "Bearer demo-token",
        "req-success"
    );
}


// =============================================================================
// 12. MAIN CASE STUDY
// =============================================================================

int main() {
    cout << "============================================================\n";
    cout << "Error Handling: Order Processing Service\n";
    cout << "============================================================\n";

    try {
        CustomerRepository customerRepository;
        ProductRepository productRepository;
        OrderRepository orderRepository;

        OrderService orderService(
            customerRepository,
            productRepository,
            orderRepository
        );

        printKnownProducts(productRepository);

        demonstrateEdgeCases(orderService);

        cout << "\n=== Inventory after requests ===\n";
        printKnownProducts(productRepository);

        printComplexityNotes();

        cout << "\n=== Error-handling architecture ===\n";
        cout << "Input -> Validation -> Authentication -> Authorization -> "
                "Domain operation -> Structured response\n";

        cout << "\n=== Production considerations ===\n";
        cout << "Use database transactions for durable state changes.\n";
        cout << "Use authenticated identity rather than trusting customer IDs.\n";
        cout << "Use authorization checks at the service boundary.\n";
        cout << "Log internal failures without exposing sensitive details.\n";
        cout << "Use stable machine-readable error codes for API clients.\n";
        cout << "Test every important success and failure path.\n";
    }
    catch (const exception& error) {
        /*
        This is the process-level safety boundary.

        It should be reached rarely because expected application failures are
        handled closer to the request boundary.
        */
        cerr << "Fatal application error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

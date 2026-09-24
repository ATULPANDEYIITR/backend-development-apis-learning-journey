/*
Pydantic Deep Dive Companion Case Study
=======================================

C++ cannot execute Pydantic because Pydantic is a Python library.

This program therefore models the same architectural ideas in a strongly
typed C++17 application:

    external JSON-like request
        -> validation boundary
        -> nested domain objects
        -> business rules
        -> normalized order
        -> serialization-like output

The case study is an order-management API boundary. It demonstrates:

- required fields
- constrained values
- nested models
- collections
- custom validation
- cross-field validation
- structured validation errors
- unknown-field rejection
- normalization
- computed values
- modular classes
- edge cases
- complexity and performance considerations

Compile:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic pydantic_case_study.cpp -o app

No external library is required.
*/

#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>


// ============================================================================
// Utility functions
// ============================================================================

std::string trim(const std::string& input) {
    const auto first = input.find_first_not_of(" \t\n\r");

    if (first == std::string::npos) {
        return "";
    }

    const auto last = input.find_last_not_of(" \t\n\r");

    return input.substr(first, last - first + 1);
}


std::string toUpper(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::toupper(character));
        }
    );

    return value;
}


bool isSixDigitPostalCode(const std::string& postalCode) {
    if (postalCode.size() != 6) {
        return false;
    }

    return std::all_of(
        postalCode.begin(),
        postalCode.end(),
        [](unsigned char character) {
            return std::isdigit(character);
        }
    );
}


bool containsOnlyAlphanumericAndAllowedSymbols(const std::string& value) {
    if (value.empty()) {
        return false;
    }

    return std::all_of(
        value.begin(),
        value.end(),
        [](unsigned char character) {
            return std::isalnum(character) ||
                   character == '_' ||
                   character == '-' ||
                   character == '.';
        }
    );
}


// ============================================================================
// Structured validation error
// ============================================================================

struct ValidationError {
    std::string path;
    std::string type;
    std::string message;
};


class ValidationException : public std::runtime_error {
public:
    explicit ValidationException(std::vector<ValidationError> errors)
        : std::runtime_error("Validation failed"),
          errors_(std::move(errors)) {}

    const std::vector<ValidationError>& errors() const {
        return errors_;
    }

private:
    std::vector<ValidationError> errors_;
};


void addError(
    std::vector<ValidationError>& errors,
    std::string path,
    std::string type,
    std::string message
) {
    errors.push_back({
        std::move(path),
        std::move(type),
        std::move(message),
    });
}


void printErrors(const ValidationException& exception) {
    std::cout << "Validation failed with "
              << exception.errors().size()
              << " error(s):\n";

    for (const auto& error : exception.errors()) {
        std::cout
            << "  path=" << error.path
            << " type=" << error.type
            << " message=" << error.message
            << '\n';
    }
}


// ============================================================================
// Address model
// ============================================================================

class Address {
public:
    Address(
        std::string line1,
        std::string city,
        std::string state,
        std::string postalCode
    )
        : line1_(trim(line1)),
          city_(trim(city)),
          state_(trim(state)),
          postalCode_(trim(postalCode)) {}

    static Address validate(
        const std::string& line1,
        const std::string& city,
        const std::string& state,
        const std::string& postalCode
    ) {
        std::vector<ValidationError> errors;

        const std::string cleanLine1 = trim(line1);
        const std::string cleanCity = trim(city);
        const std::string cleanState = trim(state);
        const std::string cleanPostalCode = trim(postalCode);

        if (cleanLine1.size() < 5 || cleanLine1.size() > 120) {
            addError(
                errors,
                "shipping_address.line1",
                "string_length",
                "line1 must contain 5 to 120 characters"
            );
        }

        if (cleanCity.size() < 2 || cleanCity.size() > 60) {
            addError(
                errors,
                "shipping_address.city",
                "string_length",
                "city must contain 2 to 60 characters"
            );
        }

        if (cleanState.size() < 2 || cleanState.size() > 60) {
            addError(
                errors,
                "shipping_address.state",
                "string_length",
                "state must contain 2 to 60 characters"
            );
        }

        if (!isSixDigitPostalCode(cleanPostalCode)) {
            addError(
                errors,
                "shipping_address.postal_code",
                "pattern",
                "postal code must contain exactly six digits"
            );
        }

        if (!errors.empty()) {
            throw ValidationException(std::move(errors));
        }

        return Address(
            cleanLine1,
            cleanCity,
            cleanState,
            cleanPostalCode
        );
    }

    const std::string& city() const {
        return city_;
    }

    std::string serialize() const {
        std::ostringstream output;

        output
            << "{"
            << "\"line1\":\"" << line1_ << "\","
            << "\"city\":\"" << city_ << "\","
            << "\"state\":\"" << state_ << "\","
            << "\"postal_code\":\"" << postalCode_ << "\""
            << "}";

        return output.str();
    }

private:
    std::string line1_;
    std::string city_;
    std::string state_;
    std::string postalCode_;
};


// ============================================================================
// Product request model
// ============================================================================

class ProductRequest {
public:
    ProductRequest(int productId, int quantity)
        : productId_(productId),
          quantity_(quantity) {}

    static ProductRequest validate(
        int productId,
        int quantity,
        const std::string& path
    ) {
        std::vector<ValidationError> errors;

        if (productId <= 0) {
            addError(
                errors,
                path + ".product_id",
                "greater_than",
                "product_id must be greater than zero"
            );
        }

        if (quantity <= 0) {
            addError(
                errors,
                path + ".quantity",
                "greater_than",
                "quantity must be greater than zero"
            );
        }

        if (quantity > 1000) {
            addError(
                errors,
                path + ".quantity",
                "less_than_equal",
                "quantity cannot exceed 1000"
            );
        }

        if (!errors.empty()) {
            throw ValidationException(std::move(errors));
        }

        return ProductRequest(productId, quantity);
    }

    int productId() const {
        return productId_;
    }

    int quantity() const {
        return quantity_;
    }

    std::string serialize() const {
        std::ostringstream output;

        output
            << "{"
            << "\"product_id\":" << productId_ << ","
            << "\"quantity\":" << quantity_
            << "}";

        return output.str();
    }

private:
    int productId_;
    int quantity_;
};


// ============================================================================
// Create-order request
// ============================================================================

class CreateOrderRequest {
public:
    CreateOrderRequest(
        int customerId,
        Address shippingAddress,
        std::vector<ProductRequest> products,
        std::optional<std::string> couponCode
    )
        : customerId_(customerId),
          shippingAddress_(std::move(shippingAddress)),
          products_(std::move(products)),
          couponCode_(std::move(couponCode)) {}

    static CreateOrderRequest validate(
        int customerId,
        Address shippingAddress,
        std::vector<ProductRequest> products,
        std::optional<std::string> couponCode
    ) {
        std::vector<ValidationError> errors;

        // Field-level constraint.
        if (customerId <= 0) {
            addError(
                errors,
                "customer_id",
                "greater_than",
                "customer_id must be greater than zero"
            );
        }

        // Collection constraint.
        if (products.empty()) {
            addError(
                errors,
                "products",
                "too_short",
                "at least one product is required"
            );
        }

        if (products.size() > 100) {
            addError(
                errors,
                "products",
                "too_long",
                "at most 100 products are allowed"
            );
        }

        // Normalize optional coupon input.
        if (couponCode.has_value()) {
            std::string normalized = trim(*couponCode);

            if (normalized.size() < 3 || normalized.size() > 30) {
                addError(
                    errors,
                    "coupon_code",
                    "string_length",
                    "coupon code must contain 3 to 30 characters"
                );
            }

            if (!normalized.empty()) {
                couponCode = toUpper(normalized);
            }
        }

        // Model-level constraint:
        // product IDs must be unique within a single order.
        std::unordered_set<int> productIds;

        for (const auto& product : products) {
            if (!productIds.insert(product.productId()).second) {
                addError(
                    errors,
                    "products",
                    "duplicate",
                    "duplicate product IDs are not allowed"
                );
            }
        }

        if (!errors.empty()) {
            throw ValidationException(std::move(errors));
        }

        return CreateOrderRequest(
            customerId,
            std::move(shippingAddress),
            std::move(products),
            std::move(couponCode)
        );
    }

    int customerId() const {
        return customerId_;
    }

    const std::vector<ProductRequest>& products() const {
        return products_;
    }

    const std::optional<std::string>& couponCode() const {
        return couponCode_;
    }

    std::string serialize() const {
        std::ostringstream output;

        output
            << "{"
            << "\"customer_id\":" << customerId_
            << ","
            << "\"shipping_address\":" << shippingAddress_.serialize()
            << ","
            << "\"products\":[";

        for (std::size_t index = 0; index < products_.size(); ++index) {
            if (index > 0) {
                output << ",";
            }

            output << products_[index].serialize();
        }

        output << "]";

        if (couponCode_.has_value()) {
            output
                << ","
                << "\"coupon_code\":\""
                << *couponCode_
                << "\"";
        }

        output << "}";

        return output.str();
    }

private:
    int customerId_;
    Address shippingAddress_;
    std::vector<ProductRequest> products_;
    std::optional<std::string> couponCode_;
};


// ============================================================================
// Domain order
// ============================================================================

class Order {
public:
    Order(
        std::string orderId,
        CreateOrderRequest request
    )
        : orderId_(std::move(orderId)),
          request_(std::move(request)) {}

    long long totalUnits() const {
        long long total = 0;

        for (const auto& product : request_.products()) {
            total += product.quantity();
        }

        return total;
    }

    std::string serialize() const {
        std::ostringstream output;

        output
            << "{"
            << "\"order_id\":\"" << orderId_ << "\","
            << "\"request\":" << request_.serialize() << ","
            << "\"total_units\":" << totalUnits()
            << "}";

        return output.str();
    }

private:
    std::string orderId_;
    CreateOrderRequest request_;
};


// ============================================================================
// Generic validation helpers
// ============================================================================

template <typename T>
std::optional<T> parseInteger(
    const std::string& text,
    const std::string& path,
    std::vector<ValidationError>& errors
) {
    try {
        std::size_t consumed = 0;

        long long value = std::stoll(text, &consumed);

        if (consumed != text.size()) {
            addError(
                errors,
                path,
                "int_parsing",
                "input contains characters that are not part of an integer"
            );
            return std::nullopt;
        }

        if (
            value < std::numeric_limits<T>::min() ||
            value > std::numeric_limits<T>::max()
        ) {
            addError(
                errors,
                path,
                "int_range",
                "integer is outside the supported range"
            );
            return std::nullopt;
        }

        return static_cast<T>(value);
    } catch (const std::exception&) {
        addError(
            errors,
            path,
            "int_parsing",
            "input could not be parsed as an integer"
        );

        return std::nullopt;
    }
}


// ============================================================================
// Case study: request pipeline
// ============================================================================

CreateOrderRequest buildValidRequest() {
    Address address = Address::validate(
        "12 Main Road",
        "Lucknow",
        "Uttar Pradesh",
        "226001"
    );

    std::vector<ProductRequest> products;

    products.push_back(
        ProductRequest::validate(
            101,
            2,
            "products[0]"
        )
    );

    products.push_back(
        ProductRequest::validate(
            102,
            1,
            "products[1]"
        )
    );

    return CreateOrderRequest::validate(
        500,
        std::move(address),
        std::move(products),
        std::optional<std::string>(" save20 ")
    );
}


// ============================================================================
// Demonstration functions
// ============================================================================

void demonstrateBasicValidation() {
    std::cout << "\n========================================\n";
    std::cout << "1. Basic constrained validation\n";
    std::cout << "========================================\n";

    try {
        ProductRequest product =
            ProductRequest::validate(100, 5, "product");

        std::cout
            << "Valid product: id="
            << product.productId()
            << ", quantity="
            << product.quantity()
            << '\n';
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }

    try {
        ProductRequest::validate(0, -1, "product");
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }
}


void demonstrateNestedValidation() {
    std::cout << "\n========================================\n";
    std::cout << "2. Nested validation\n";
    std::cout << "========================================\n";

    try {
        Address address = Address::validate(
            "12 Main Road",
            "Lucknow",
            "Uttar Pradesh",
            "226001"
        );

        std::cout << address.serialize() << '\n';
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }

    try {
        Address::validate(
            "X",
            "L",
            "Uttar Pradesh",
            "123"
        );
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }
}


void demonstrateCompleteRequest() {
    std::cout << "\n========================================\n";
    std::cout << "3. Complete API request\n";
    std::cout << "========================================\n";

    try {
        CreateOrderRequest request = buildValidRequest();

        std::cout << "Validated request:\n";
        std::cout << request.serialize() << '\n';

        Order order(
            "ORD-2026-0001",
            std::move(request)
        );

        std::cout
            << "Derived total units: "
            << order.totalUnits()
            << '\n';

        std::cout
            << "Normalized order:\n"
            << order.serialize()
            << '\n';
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }
}


void demonstrateCrossFieldRules() {
    std::cout << "\n========================================\n";
    std::cout << "4. Cross-field business rules\n";
    std::cout << "========================================\n";

    try {
        Address address = Address::validate(
            "12 Main Road",
            "Lucknow",
            "Uttar Pradesh",
            "226001"
        );

        std::vector<ProductRequest> products;

        products.push_back(
            ProductRequest::validate(
                101,
                1,
                "products[0]"
            )
        );

        // The second product has the same ID.
        products.push_back(
            ProductRequest::validate(
                101,
                2,
                "products[1]"
            )
        );

        CreateOrderRequest::validate(
            500,
            std::move(address),
            std::move(products),
            std::nullopt
        );
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }
}


void demonstrateNormalization() {
    std::cout << "\n========================================\n";
    std::cout << "5. Normalization\n";
    std::cout << "========================================\n";

    try {
        Address address = Address::validate(
            "   12 Main Road   ",
            "   Lucknow   ",
            "   Uttar Pradesh   ",
            "226001"
        );

        std::vector<ProductRequest> products;

        products.push_back(
            ProductRequest::validate(
                1001,
                4,
                "products[0]"
            )
        );

        CreateOrderRequest request =
            CreateOrderRequest::validate(
                900,
                std::move(address),
                std::move(products),
                std::optional<std::string>("  save50  ")
            );

        std::cout << request.serialize() << '\n';
    } catch (const ValidationException& exception) {
        printErrors(exception);
    }
}


void demonstrateGenericParsing() {
    std::cout << "\n========================================\n";
    std::cout << "6. Generic parsing helper\n";
    std::cout << "========================================\n";

    std::vector<ValidationError> errors;

    const auto valid =
        parseInteger<int>("123", "customer_id", errors);

    const auto invalid =
        parseInteger<int>("12abc", "quantity", errors);

    if (valid.has_value()) {
        std::cout
            << "Parsed customer ID: "
            << *valid
            << '\n';
    }

    if (!invalid.has_value()) {
        std::cout << "Invalid integer rejected.\n";
    }

    for (const auto& error : errors) {
        std::cout
            << error.path
            << ": "
            << error.message
            << '\n';
    }
}


// ============================================================================
// Performance demonstration
// ============================================================================

void demonstratePerformanceConsiderations() {
    std::cout << "\n========================================\n";
    std::cout << "7. Performance considerations\n";
    std::cout << "========================================\n";

    /*
     * Duplicate detection uses std::unordered_set.
     *
     * Average complexity:
     *     O(n)
     *
     * A naive pairwise duplicate check would be:
     *     O(n^2)
     *
     * Pydantic validation also benefits from separating field-level
     * constraints from model-level rules so each rule can remain focused.
     */

    constexpr int numberOfProducts = 10000;

    std::unordered_set<int> productIds;
    productIds.reserve(numberOfProducts);

    for (int id = 1; id <= numberOfProducts; ++id) {
        productIds.insert(id);
    }

    std::cout
        << "Unique IDs stored: "
        << productIds.size()
        << '\n';

    std::cout
        << "Average duplicate-detection complexity: O(n)\n";
}


// ============================================================================
// Security demonstration
// ============================================================================

void demonstrateSecurityBoundary() {
    std::cout << "\n========================================\n";
    std::cout << "8. Security-oriented validation\n";
    std::cout << "========================================\n";

    const std::vector<std::string> usernames = {
        "Atul_Pandey",
        "safe-user",
        "admin",
        "<script>alert(1)</script>",
        ""
    };

    for (const auto& username : usernames) {
        const std::string normalized = trim(username);

        const bool accepted =
            normalized.size() >= 3 &&
            normalized.size() <= 32 &&
            containsOnlyAlphanumericAndAllowedSymbols(normalized);

        std::cout
            << std::quoted(username)
            << " -> "
            << (accepted ? "accepted" : "rejected")
            << '\n';
    }

    /*
     * Input validation is only one security control.
     *
     * A production system still needs:
     * - authentication
     * - authorization
     * - secure credential handling
     * - output encoding
     * - database parameterization
     * - rate limiting
     * - audit logging
     * - transport security
     *
     * Validation should not be treated as a complete security system.
     */
}


// ============================================================================
// Edge cases
// ============================================================================

void demonstrateEdgeCases() {
    std::cout << "\n========================================\n";
    std::cout << "9. Edge cases\n";
    std::cout << "========================================\n";

    struct TestCase {
        std::string name;
        int customerId;
        std::string postalCode;
    };

    const std::vector<TestCase> tests = {
        {"valid input", 10, "226001"},
        {"zero customer ID", 0, "226001"},
        {"negative customer ID", -10, "226001"},
        {"short postal code", 10, "123"},
        {"non-numeric postal code", 10, "ABC001"},
    };

    for (const auto& test : tests) {
        try {
            Address address = Address::validate(
                "12 Main Road",
                "Lucknow",
                "Uttar Pradesh",
                test.postalCode
            );

            std::vector<ProductRequest> products;

            products.push_back(
                ProductRequest::validate(
                    1,
                    1,
                    "products[0]"
                )
            );

            CreateOrderRequest::validate(
                test.customerId,
                std::move(address),
                std::move(products),
                std::nullopt
            );

            std::cout
                << test.name
                << " -> accepted\n";
        } catch (const ValidationException& exception) {
            std::cout
                << test.name
                << " -> rejected with "
                << exception.errors().size()
                << " error(s)\n";
        }
    }
}


// ============================================================================
// Lightweight tests
// ============================================================================

void runTests() {
    std::cout << "\n========================================\n";
    std::cout << "10. Executable tests\n";
    std::cout << "========================================\n";

    {
        Address address = Address::validate(
            "12 Main Road",
            "Lucknow",
            "Uttar Pradesh",
            "226001"
        );

        if (address.city() != "Lucknow") {
            throw std::runtime_error("Address city test failed");
        }
    }

    {
        ProductRequest product =
            ProductRequest::validate(10, 2, "product");

        if (product.productId() != 10) {
            throw std::runtime_error("Product ID test failed");
        }

        if (product.quantity() != 2) {
            throw std::runtime_error("Quantity test failed");
        }
    }

    {
        CreateOrderRequest request =
            buildValidRequest();

        if (request.customerId() != 500) {
            throw std::runtime_error("Customer ID test failed");
        }

        if (request.products().size() != 2) {
            throw std::runtime_error("Product collection test failed");
        }

        if (!request.couponCode().has_value()) {
            throw std::runtime_error("Coupon test failed");
        }

        if (*request.couponCode() != "SAVE20") {
            throw std::runtime_error("Coupon normalization failed");
        }
    }

    bool invalidInputRejected = false;

    try {
        ProductRequest::validate(
            0,
            0,
            "product"
        );
    } catch (const ValidationException&) {
        invalidInputRejected = true;
    }

    if (!invalidInputRejected) {
        throw std::runtime_error(
            "Invalid ProductRequest should have been rejected"
        );
    }

    std::cout << "All C++ assertions passed.\n";
}


// ============================================================================
// Main
// ============================================================================

int main() {
    try {
        std::cout
            << "Pydantic Deep Dive: C++ validation architecture case study\n";

        demonstrateBasicValidation();
        demonstrateNestedValidation();
        demonstrateCompleteRequest();
        demonstrateCrossFieldRules();
        demonstrateNormalization();
        demonstrateGenericParsing();
        demonstratePerformanceConsiderations();
        demonstrateSecurityBoundary();
        demonstrateEdgeCases();
        runTests();

        std::cout
            << "\nCase study completed successfully.\n";

        return 0;
    } catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << '\n';

        return 1;
    }
}

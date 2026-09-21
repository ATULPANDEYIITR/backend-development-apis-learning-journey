/*
 * Request Bodies and Validation: C++ Technical Case Study
 * ========================================================
 *
 * Scenario:
 *     An order-management service receives JSON-like request data from
 *     clients. The service must validate required fields, optional fields,
 *     nested objects, lists, payment methods, quantities, prices, and
 *     business rules before accepting an order.
 *
 * The program deliberately uses only the C++17 standard library.
 *
 * It models the same architectural concepts that FastAPI + Pydantic provide:
 *
 *     raw request
 *          |
 *          v
 *     structural validation
 *          |
 *          v
 *     field validation
 *          |
 *          v
 *     nested-object validation
 *          |
 *          v
 *     business validation
 *          |
 *          v
 *     accepted domain object
 *
 * This is a case study rather than a JSON parser implementation.
 * A production C++ HTTP service would normally use an established JSON and
 * HTTP library, but the validation architecture itself can be demonstrated
 * entirely with the standard library.
 *
 * Compile:
 *     g++ -std=c++17 -Wall -Wextra -pedantic request_bodies.cpp -o request_bodies
 *
 * Run:
 *     ./request_bodies
 */

#include <algorithm>
#include <chrono>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <utility>
#include <vector>


// ============================================================================
// SECTION 1: GENERAL VALIDATION RESULT
// ============================================================================

struct ValidationResult {
    bool valid{true};
    std::vector<std::string> errors;

    void addError(std::string message) {
        valid = false;
        errors.push_back(std::move(message));
    }
};


// ============================================================================
// SECTION 2: BASIC UTILITY FUNCTIONS
// ============================================================================

std::string trim(const std::string& value) {
    const auto first = std::find_if(
        value.begin(),
        value.end(),
        [](unsigned char character) {
            return !std::isspace(character);
        }
    );

    const auto last = std::find_if(
        value.rbegin(),
        value.rend(),
        [](unsigned char character) {
            return !std::isspace(character);
        }
    ).base();

    if (first >= last) {
        return {};
    }

    return std::string(first, last);
}


std::string uppercase(std::string value) {
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


bool isBlank(const std::string& value) {
    return trim(value).empty();
}


void printValidationResult(const ValidationResult& result) {
    if (result.valid) {
        std::cout << "VALID\n";
        return;
    }

    std::cout << "INVALID\n";

    for (const auto& error : result.errors) {
        std::cout << "  - " << error << '\n';
    }
}


// ============================================================================
// SECTION 3: DOMAIN ENUMERATION
// ============================================================================

enum class PaymentMethod {
    Card,
    Upi,
    BankTransfer
};


std::optional<PaymentMethod> parsePaymentMethod(
    const std::string& value
) {
    if (value == "card") {
        return PaymentMethod::Card;
    }

    if (value == "upi") {
        return PaymentMethod::Upi;
    }

    if (value == "bank_transfer") {
        return PaymentMethod::BankTransfer;
    }

    return std::nullopt;
}


std::string paymentMethodToString(PaymentMethod method) {
    switch (method) {
        case PaymentMethod::Card:
            return "card";

        case PaymentMethod::Upi:
            return "upi";

        case PaymentMethod::BankTransfer:
            return "bank_transfer";
    }

    return "unknown";
}


// ============================================================================
// SECTION 4: MONEY REPRESENTATION
// ============================================================================

/*
 * Floating-point values such as double are convenient but can introduce
 * representation issues for money.
 *
 * This case study stores money in integer paise:
 *
 *     ₹24.99 -> 2499 paise
 *
 * Integer minor units make arithmetic deterministic for ordinary monetary
 * calculations where the currency has two decimal places.
 */

class Money {
private:
    long long paise_;

public:
    explicit Money(long long paise = 0)
        : paise_(paise) {}

    long long paise() const {
        return paise_;
    }

    Money operator*(int quantity) const {
        return Money(paise_ * quantity);
    }

    Money operator+(const Money& other) const {
        return Money(paise_ + other.paise_);
    }

    std::string toString() const {
        const long long absoluteValue = std::llabs(paise_);

        std::ostringstream output;

        if (paise_ < 0) {
            output << '-';
        }

        output
            << "₹"
            << absoluteValue / 100
            << '.'
            << std::setw(2)
            << std::setfill('0')
            << absoluteValue % 100;

        return output.str();
    }
};


// ============================================================================
// SECTION 5: ADDRESS REQUEST MODEL
// ============================================================================

struct ShippingAddress {
    std::string recipientName;
    std::string street;
    std::string city;
    std::string state;
    std::string postalCode;
    std::string country{"India"};

    ValidationResult validate() const {
        ValidationResult result;

        if (isBlank(recipientName)) {
            result.addError("shippingAddress.recipientName is required.");
        }

        if (isBlank(street)) {
            result.addError("shippingAddress.street is required.");
        }

        if (isBlank(city)) {
            result.addError("shippingAddress.city is required.");
        }

        if (isBlank(state)) {
            result.addError("shippingAddress.state is required.");
        }

        if (isBlank(postalCode)) {
            result.addError("shippingAddress.postalCode is required.");
        }

        if (postalCode.size() > 20) {
            result.addError(
                "shippingAddress.postalCode is too long."
            );
        }

        if (isBlank(country)) {
            result.addError("shippingAddress.country cannot be blank.");
        }

        return result;
    }
};


// ============================================================================
// SECTION 6: PRODUCT LINE MODEL
// ============================================================================

struct ProductLine {
    int productId{};
    std::string productName;
    int quantity{};
    Money unitPrice;

    ValidationResult validate(std::size_t index) const {
        ValidationResult result;

        const std::string prefix =
            "items[" + std::to_string(index) + "]";

        if (productId <= 0) {
            result.addError(
                prefix + ".productId must be positive."
            );
        }

        if (isBlank(productName)) {
            result.addError(
                prefix + ".productName is required."
            );
        }

        if (productName.size() > 150) {
            result.addError(
                prefix + ".productName is too long."
            );
        }

        if (quantity <= 0) {
            result.addError(
                prefix + ".quantity must be greater than zero."
            );
        }

        if (quantity > 1000) {
            result.addError(
                prefix + ".quantity exceeds the maximum allowed value."
            );
        }

        if (unitPrice.paise() <= 0) {
            result.addError(
                prefix + ".unitPrice must be greater than zero."
            );
        }

        return result;
    }
};


// ============================================================================
// SECTION 7: ORDER REQUEST MODEL
// ============================================================================

struct OrderRequest {
    int customerId{};
    ShippingAddress shippingAddress;
    std::vector<ProductLine> items;

    PaymentMethod paymentMethod{PaymentMethod::Upi};

    /*
     * std::optional represents an optional field.
     *
     * A missing coupon is represented by std::nullopt.
     * A supplied coupon is represented by a string.
     */
    std::optional<std::string> couponCode;

    ValidationResult validate() const {
        ValidationResult result;

        if (customerId <= 0) {
            result.addError("customerId must be positive.");
        }

        const ValidationResult addressResult =
            shippingAddress.validate();

        for (const auto& error : addressResult.errors) {
            result.addError(error);
        }

        if (items.empty()) {
            result.addError("items must contain at least one item.");
        }

        if (items.size() > 100) {
            result.addError("items cannot contain more than 100 items.");
        }

        for (std::size_t index = 0; index < items.size(); ++index) {
            const ValidationResult itemResult =
                items[index].validate(index);

            for (const auto& error : itemResult.errors) {
                result.addError(error);
            }
        }

        if (couponCode.has_value()) {
            const std::string normalizedCoupon =
                uppercase(trim(*couponCode));

            if (normalizedCoupon.empty()) {
                result.addError(
                    "couponCode cannot contain only whitespace."
                );
            }
        }

        /*
         * Cross-field business rule.
         *
         * Schema validation alone cannot express every business rule.
         */
        if (
            paymentMethod == PaymentMethod::Card &&
            couponCode.has_value() &&
            uppercase(trim(*couponCode)) == "CASHONLY"
        ) {
            result.addError(
                "CASHONLY cannot be used with card payments."
            );
        }

        return result;
    }

    Money subtotal() const {
        Money total;

        for (const auto& item : items) {
            total = total + item.unitPrice * item.quantity;
        }

        return total;
    }
};


// ============================================================================
// SECTION 8: ACCEPTED ORDER
// ============================================================================

struct AcceptedOrder {
    long long orderId{};
    OrderRequest request;
    std::string status{"confirmed"};

    void print() const {
        std::cout << "Order ID: " << orderId << '\n';
        std::cout << "Customer ID: " << request.customerId << '\n';
        std::cout << "Status: " << status << '\n';
        std::cout
            << "Payment method: "
            << paymentMethodToString(request.paymentMethod)
            << '\n';

        if (request.couponCode.has_value()) {
            std::cout
                << "Coupon: "
                << uppercase(trim(*request.couponCode))
                << '\n';
        } else {
            std::cout << "Coupon: none\n";
        }

        std::cout << "Items: " << request.items.size() << '\n';
        std::cout << "Subtotal: " << request.subtotal().toString() << '\n';
    }
};


// ============================================================================
// SECTION 9: ORDER SERVICE
// ============================================================================

class OrderService {
private:
    long long nextOrderId_{9001};

public:
    std::pair<std::optional<AcceptedOrder>, ValidationResult>
    createOrder(const OrderRequest& request) {

        /*
         * Validation happens before the order enters the accepted domain
         * state.
         */
        ValidationResult validation = request.validate();

        if (!validation.valid) {
            return {std::nullopt, std::move(validation)};
        }

        AcceptedOrder accepted{
            nextOrderId_++,
            request,
            "confirmed"
        };

        return {accepted, validation};
    }
};


// ============================================================================
// SECTION 10: VALID REQUEST
// ============================================================================

OrderRequest createValidRequest() {
    OrderRequest request;

    request.customerId = 1001;

    request.shippingAddress = ShippingAddress{
        "Atul Pandey",
        "MG Road",
        "Lucknow",
        "Uttar Pradesh",
        "226001",
        "India"
    };

    request.items.push_back(
        ProductLine{
            101,
            "Mechanical Keyboard",
            2,
            Money(249900)
        }
    );

    request.items.push_back(
        ProductLine{
            102,
            "Wireless Mouse",
            1,
            Money(129900)
        }
    );

    request.paymentMethod = PaymentMethod::Upi;
    request.couponCode = " save10 ";

    return request;
}


// ============================================================================
// SECTION 11: INVALID REQUEST
// ============================================================================

OrderRequest createInvalidRequest() {
    OrderRequest request;

    request.customerId = -10;

    request.shippingAddress = ShippingAddress{
        "",
        "",
        "Lucknow",
        "",
        "",
        "India"
    };

    request.items.push_back(
        ProductLine{
            -1,
            "",
            -5,
            Money(-100)
        }
    );

    request.paymentMethod = PaymentMethod::Card;
    request.couponCode = " CASHONLY ";

    return request;
}


// ============================================================================
// SECTION 12: REQUIRED VS OPTIONAL FIELD DEMONSTRATION
// ============================================================================

struct UserRequest {
    /*
     * username is required because it is a normal string.
     */
    std::string username;

    /*
     * phone is optional because it uses std::optional.
     */
    std::optional<std::string> phone;

    ValidationResult validate() const {
        ValidationResult result;

        if (isBlank(username)) {
            result.addError("username is required.");
        }

        if (phone.has_value() && phone->size() > 30) {
            result.addError("phone is too long.");
        }

        return result;
    }
};


void demonstrateRequiredOptional() {
    std::cout << "\n=== REQUIRED VS OPTIONAL ===\n";

    UserRequest withoutPhone{
        "atul",
        std::nullopt
    };

    UserRequest withPhone{
        "atul",
        "+91-9876543210"
    };

    std::cout << "Without phone:\n";
    printValidationResult(withoutPhone.validate());

    std::cout << "With phone:\n";
    printValidationResult(withPhone.validate());
}


// ============================================================================
// SECTION 13: NESTED OBJECT VALIDATION
// ============================================================================

void demonstrateNestedObjectValidation() {
    std::cout << "\n=== NESTED OBJECT VALIDATION ===\n";

    OrderRequest request = createValidRequest();

    std::cout << "Shipping address city: "
              << request.shippingAddress.city
              << '\n';

    std::cout << "Address validation:\n";
    printValidationResult(request.shippingAddress.validate());

    std::cout << "First item name: "
              << request.items.front().productName
              << '\n';
}


// ============================================================================
// SECTION 14: PAYMENT METHOD PARSING
// ============================================================================

void demonstratePaymentParsing() {
    std::cout << "\n=== PAYMENT METHOD PARSING ===\n";

    const std::vector<std::string> values{
        "upi",
        "card",
        "bank_transfer",
        "cash"
    };

    for (const auto& value : values) {
        const auto method = parsePaymentMethod(value);

        if (method.has_value()) {
            std::cout
                << value
                << " -> accepted as "
                << paymentMethodToString(*method)
                << '\n';
        } else {
            std::cout
                << value
                << " -> rejected\n";
        }
    }
}


// ============================================================================
// SECTION 15: VALID ORDER CASE STUDY
// ============================================================================

void demonstrateValidOrder() {
    std::cout << "\n=== VALID ORDER CASE STUDY ===\n";

    OrderService service;
    OrderRequest request = createValidRequest();

    const auto [order, validation] =
        service.createOrder(request);

    if (!order.has_value()) {
        printValidationResult(validation);
        return;
    }

    order->print();
}


// ============================================================================
// SECTION 16: INVALID ORDER CASE STUDY
// ============================================================================

void demonstrateInvalidOrder() {
    std::cout << "\n=== INVALID ORDER CASE STUDY ===\n";

    OrderService service;
    OrderRequest request = createInvalidRequest();

    const auto [order, validation] =
        service.createOrder(request);

    if (!order.has_value()) {
        printValidationResult(validation);
        return;
    }

    order->print();
}


// ============================================================================
// SECTION 17: EDGE CASES
// ============================================================================

void demonstrateEdgeCases() {
    std::cout << "\n=== EDGE CASES ===\n";

    OrderService service;

    {
        std::cout << "\nCase: zero customer ID\n";

        OrderRequest request = createValidRequest();
        request.customerId = 0;

        const auto [order, validation] =
            service.createOrder(request);

        printValidationResult(validation);
    }

    {
        std::cout << "\nCase: empty item list\n";

        OrderRequest request = createValidRequest();
        request.items.clear();

        const auto [order, validation] =
            service.createOrder(request);

        printValidationResult(validation);
    }

    {
        std::cout << "\nCase: excessive item quantity\n";

        OrderRequest request = createValidRequest();
        request.items.front().quantity = 1001;

        const auto [order, validation] =
            service.createOrder(request);

        printValidationResult(validation);
    }

    {
        std::cout << "\nCase: optional coupon absent\n";

        OrderRequest request = createValidRequest();
        request.couponCode.reset();

        const auto [order, validation] =
            service.createOrder(request);

        printValidationResult(validation);

        if (order.has_value()) {
            order->print();
        }
    }
}


// ============================================================================
// SECTION 18: PERFORMANCE DEMONSTRATION
// ============================================================================

void demonstratePerformance() {
    std::cout << "\n=== PERFORMANCE DEMONSTRATION ===\n";

    OrderRequest request = createValidRequest();

    /*
     * Keep the demonstration within the API's 100-item constraint.
     */
    while (request.items.size() < 100) {
        request.items.push_back(
            ProductLine{
                static_cast<int>(request.items.size()) + 1000,
                "Performance Test Product",
                1,
                Money(10000)
            }
        );
    }

    const auto start =
        std::chrono::steady_clock::now();

    constexpr int repetitions = 10000;

    int successfulValidations = 0;

    for (int iteration = 0;
         iteration < repetitions;
         ++iteration) {

        const ValidationResult result =
            request.validate();

        if (result.valid) {
            ++successfulValidations;
        }
    }

    const auto end =
        std::chrono::steady_clock::now();

    const auto elapsedMicroseconds =
        std::chrono::duration_cast<
            std::chrono::microseconds
        >(end - start).count();

    std::cout
        << "Validations: "
        << successfulValidations
        << '\n';

    std::cout
        << "Elapsed time: "
        << elapsedMicroseconds
        << " microseconds\n";

    /*
     * This is an educational local benchmark.
     *
     * It is not a substitute for a production load test because real API
     * performance also depends on:
     *
     * - HTTP parsing
     * - JSON parsing
     * - network latency
     * - authentication
     * - database access
     * - concurrency
     * - memory allocation
     * - operating-system scheduling
     */
}


// ============================================================================
// SECTION 19: SECURITY DESIGN
// ============================================================================

void demonstrateSecurityDesign() {
    std::cout << "\n=== SECURITY DESIGN ===\n";

    const std::vector<std::string> rules{
        "Validate every client-controlled field.",
        "Do not trust prices supplied by a client when the server owns pricing.",
        "Do not let request fields directly grant permissions.",
        "Keep authentication separate from request-body validation.",
        "Keep authorization separate from request-body validation.",
        "Limit request size and nested collection size.",
        "Reject impossible numeric ranges.",
        "Avoid exposing sensitive internal fields in API responses.",
        "Normalize input only where the API contract permits it.",
        "Avoid logging secrets and sensitive request bodies."
    };

    for (std::size_t index = 0; index < rules.size(); ++index) {
        std::cout
            << index + 1
            << ". "
            << rules[index]
            << '\n';
    }
}


// ============================================================================
// SECTION 20: ARCHITECTURAL COMPARISON
// ============================================================================

void demonstrateArchitecture() {
    std::cout << "\n=== ARCHITECTURAL LAYERS ===\n";

    const std::vector<std::pair<std::string, std::string>> layers{
        {
            "HTTP layer",
            "Receives the request and identifies its media type."
        },
        {
            "JSON layer",
            "Converts JSON text into structured data."
        },
        {
            "Schema layer",
            "Checks required fields, types, nested objects, and constraints."
        },
        {
            "Business layer",
            "Checks rules involving the application's domain."
        },
        {
            "Authorization layer",
            "Determines whether the caller is permitted to perform the action."
        },
        {
            "Persistence layer",
            "Stores the accepted domain state."
        }
    };

    for (const auto& [layer, explanation] : layers) {
        std::cout
            << layer
            << ": "
            << explanation
            << '\n';
    }
}


// ============================================================================
// SECTION 21: MAIN
// ============================================================================

int main() {
    std::cout
        << "============================================================\n"
        << "C++ REQUEST BODY VALIDATION CASE STUDY\n"
        << "============================================================\n";

    demonstrateRequiredOptional();
    demonstrateNestedObjectValidation();
    demonstratePaymentParsing();
    demonstrateValidOrder();
    demonstrateInvalidOrder();
    demonstrateEdgeCases();
    demonstratePerformance();
    demonstrateSecurityDesign();
    demonstrateArchitecture();

    std::cout
        << "\nProgram completed successfully.\n";

    return 0;
}

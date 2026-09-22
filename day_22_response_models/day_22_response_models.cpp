/*
 * FastAPI + Pydantic Response Models
 * ==================================
 *
 * C++17 case study:
 *
 * A production-style API response layer for an e-commerce service.
 *
 * The program models:
 *   - Internal database entities
 *   - Public response DTOs
 *   - Sensitive-field filtering
 *   - Nested response structures
 *   - Response serialization
 *   - Response validation
 *   - Pagination
 *   - Error responses
 *   - Decimal-like monetary representation
 *   - Computed response fields
 *   - Performance considerations
 *
 * The C++ standard library is used exclusively.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic response_models_fastapi.cpp -o response_models
 *
 * Run:
 *   ./response_models
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
#include <utility>
#include <vector>


// ============================================================================
// 1. DOMAIN TYPES
// ============================================================================

struct DatabaseUser {
    int id;
    std::string username;
    std::string email;
    std::string password_hash;
    bool is_admin;
};


// ============================================================================
// 2. PUBLIC USER RESPONSE DTO
// ============================================================================

struct UserResponse {
    int id;
    std::string username;
    std::string email;
    bool is_admin;

    /*
     * A response DTO deliberately does not contain password_hash.
     *
     * This mirrors the architectural principle of a FastAPI response model:
     * internal persistence data and externally visible API data should not
     * automatically be the same structure.
     */
};


// ============================================================================
// 3. ADDRESS RESPONSE
// ============================================================================

struct AddressResponse {
    std::string street;
    std::string city;
    std::string state;
    std::string postal_code;
};


// ============================================================================
// 4. CUSTOMER RESPONSE
// ============================================================================

struct CustomerResponse {
    int id;
    std::string name;
    std::string email;
    AddressResponse address;
};


// ============================================================================
// 5. PRODUCT RESPONSE
// ============================================================================

struct ProductResponse {
    int id;
    std::string name;

    /*
     * Store money as integer minor units instead of double.
     *
     * Example:
     *   8499990 = ₹84,999.90
     *
     * This avoids many binary floating-point precision problems.
     */
    long long price_minor_units;

    std::string currency;
    int stock_quantity;
};


// ============================================================================
// 6. RESPONSE VALIDATION ERROR
// ============================================================================

class ResponseValidationError : public std::runtime_error {
public:
    explicit ResponseValidationError(const std::string& message)
        : std::runtime_error(message) {}
};


// ============================================================================
// 7. API ERROR
// ============================================================================

class ApiError : public std::runtime_error {
private:
    int status_code_;

public:
    ApiError(int status_code, const std::string& message)
        : std::runtime_error(message),
          status_code_(status_code) {}

    int status_code() const noexcept {
        return status_code_;
    }
};


// ============================================================================
// 8. TRANSACTION
// ============================================================================

enum class TransactionStatus {
    Pending,
    Completed,
    Failed,
    Refunded
};


std::string transaction_status_to_string(TransactionStatus status) {
    switch (status) {
        case TransactionStatus::Pending:
            return "pending";
        case TransactionStatus::Completed:
            return "completed";
        case TransactionStatus::Failed:
            return "failed";
        case TransactionStatus::Refunded:
            return "refunded";
    }

    throw ResponseValidationError("Unknown transaction status.");
}


struct TransactionResponse {
    int id;
    long long amount_minor_units;
    std::string currency;
    TransactionStatus status;
};


// ============================================================================
// 9. PAGINATION
// ============================================================================

struct PaginationMeta {
    int page;
    int page_size;
    int total;
};


struct PaginatedUsersResponse {
    std::vector<UserResponse> items;
    PaginationMeta meta;
};


// ============================================================================
// 10. RESPONSE ENVELOPE
// ============================================================================

template <typename T>
struct ApiResponse {
    bool success;
    std::string message;
    T data;
};


// ============================================================================
// 11. SERIALIZATION HELPERS
// ============================================================================

std::string escape_json(const std::string& input) {
    std::ostringstream output;

    for (char character : input) {
        switch (character) {
            case '"':
                output << "\\\"";
                break;
            case '\\':
                output << "\\\\";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                output << character;
                break;
        }
    }

    return output.str();
}


std::string json_string(const std::string& value) {
    return "\"" + escape_json(value) + "\"";
}


std::string bool_json(bool value) {
    return value ? "true" : "false";
}


std::string format_money(long long minor_units) {
    const bool negative = minor_units < 0;
    const long long absolute_value =
        negative ? -minor_units : minor_units;

    const long long major = absolute_value / 100;
    const long long minor = absolute_value % 100;

    std::ostringstream output;

    if (negative) {
        output << "-";
    }

    output << major
           << "."
           << std::setw(2)
           << std::setfill('0')
           << minor;

    return output.str();
}


// ============================================================================
// 12. INTERNAL TO PUBLIC MAPPING
// ============================================================================

UserResponse to_public_user(const DatabaseUser& user) {
    /*
     * Only explicitly selected public fields cross the API boundary.
     *
     * password_hash is never copied into UserResponse.
     */
    return UserResponse{
        user.id,
        user.username,
        user.email,
        user.is_admin
    };
}


// ============================================================================
// 13. USER RESPONSE SERIALIZER
// ============================================================================

std::string serialize_user(const UserResponse& user) {
    std::ostringstream output;

    output << "{"
           << "\"id\":" << user.id << ","
           << "\"username\":" << json_string(user.username) << ","
           << "\"email\":" << json_string(user.email) << ","
           << "\"isAdmin\":" << bool_json(user.is_admin)
           << "}";

    return output.str();
}


// ============================================================================
// 14. ADDRESS SERIALIZATION
// ============================================================================

std::string serialize_address(const AddressResponse& address) {
    std::ostringstream output;

    output << "{"
           << "\"street\":" << json_string(address.street) << ","
           << "\"city\":" << json_string(address.city) << ","
           << "\"state\":" << json_string(address.state) << ","
           << "\"postalCode\":" << json_string(address.postal_code)
           << "}";

    return output.str();
}


// ============================================================================
// 15. CUSTOMER SERIALIZATION
// ============================================================================

std::string serialize_customer(const CustomerResponse& customer) {
    std::ostringstream output;

    output << "{"
           << "\"id\":" << customer.id << ","
           << "\"name\":" << json_string(customer.name) << ","
           << "\"email\":" << json_string(customer.email) << ","
           << "\"address\":" << serialize_address(customer.address)
           << "}";

    return output.str();
}


// ============================================================================
// 16. PRODUCT AVAILABILITY
// ============================================================================

std::string availability_for(int stock_quantity) {
    if (stock_quantity < 0) {
        throw ResponseValidationError(
            "Stock quantity cannot be negative."
        );
    }

    if (stock_quantity == 0) {
        return "out_of_stock";
    }

    if (stock_quantity < 10) {
        return "low_stock";
    }

    return "available";
}


// ============================================================================
// 17. PRODUCT SERIALIZATION
// ============================================================================

std::string serialize_product(const ProductResponse& product) {
    if (product.stock_quantity < 0) {
        throw ResponseValidationError(
            "Cannot serialize product with negative stock."
        );
    }

    std::ostringstream output;

    output << "{"
           << "\"id\":" << product.id << ","
           << "\"name\":" << json_string(product.name) << ","
           << "\"price\":" << json_string(
                  format_money(product.price_minor_units)
              ) << ","
           << "\"currency\":" << json_string(product.currency) << ","
           << "\"stockQuantity\":" << product.stock_quantity << ","
           << "\"availability\":"
           << json_string(
                  availability_for(product.stock_quantity)
              )
           << "}";

    return output.str();
}


// ============================================================================
// 18. TRANSACTION VALIDATION
// ============================================================================

void validate_transaction(const TransactionResponse& transaction) {
    if (transaction.id <= 0) {
        throw ResponseValidationError(
            "Transaction ID must be positive."
        );
    }

    if (transaction.amount_minor_units < 0) {
        throw ResponseValidationError(
            "Transaction amount cannot be negative."
        );
    }

    if (transaction.currency.empty()) {
        throw ResponseValidationError(
            "Transaction currency cannot be empty."
        );

    }

    switch (transaction.status) {
        case TransactionStatus::Pending:
        case TransactionStatus::Completed:
        case TransactionStatus::Failed:
        case TransactionStatus::Refunded:
            break;

        default:
            throw ResponseValidationError(
                "Transaction status is invalid."
            );
    }
}


// ============================================================================
// 19. TRANSACTION SERIALIZATION
// ============================================================================

std::string serialize_transaction(
    const TransactionResponse& transaction
) {
    validate_transaction(transaction);

    std::ostringstream output;

    output << "{"
           << "\"id\":" << transaction.id << ","
           << "\"amount\":"
           << json_string(
                  format_money(transaction.amount_minor_units)
              )
           << ","
           << "\"currency\":"
           << json_string(transaction.currency)
           << ","
           << "\"status\":"
           << json_string(
                  transaction_status_to_string(transaction.status)
              )
           << "}";

    return output.str();
}


// ============================================================================
// 20. USER LIST SERIALIZATION
// ============================================================================

std::string serialize_user_list(
    const std::vector<UserResponse>& users
) {
    std::ostringstream output;

    output << "[";

    for (std::size_t index = 0; index < users.size(); ++index) {
        if (index > 0) {
            output << ",";
        }

        output << serialize_user(users[index]);
    }

    output << "]";

    return output.str();
}


// ============================================================================
// 21. PAGINATION VALIDATION
// ============================================================================

void validate_pagination(
    int page,
    int page_size,
    int total
) {
    if (page < 1) {
        throw ApiError(
            400,
            "Page must be greater than or equal to 1."
        );
    }

    if (page_size < 1 || page_size > 100) {
        throw ApiError(
            400,
            "Page size must be between 1 and 100."
        );
    }

    if (total < 0) {
        throw ApiError(
            500,
            "Total cannot be negative."
        );
    }
}


// ============================================================================
// 22. PAGINATED USER QUERY
// ============================================================================

PaginatedUsersResponse paginate_users(
    const std::vector<UserResponse>& users,
    int page,
    int page_size
) {
    const int total = static_cast<int>(users.size());

    validate_pagination(
        page,
        page_size,
        total
    );

    const std::size_t start =
        static_cast<std::size_t>(
            (page - 1) * page_size
        );

    std::vector<UserResponse> selected;

    if (start < users.size()) {
        const std::size_t end =
            std::min(
                start + static_cast<std::size_t

#include <algorithm>
#include <cmath>
#include <cctype>
#include <iostream>
#include <map>
#include <optional>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

using namespace std;

/*
 * C++17 Input Validation and API Gateway Engine
 *
 * Scenario:
 * An enterprise inventory API receives product registration requests.
 *
 * Validation layers:
 * 1. Structural and schema validation
 * 2. Type validation
 * 3. Boundary validation
 * 4. Format validation
 * 5. Sanitization
 * 6. Security inspection
 * 7. Business rule validation
 */

enum class ValueType {
    STRING,
    INTEGER,
    NUMBER,
    BOOLEAN
};

enum class IssueType {
    REQUIRED,
    TYPE,
    FORMAT,
    BOUNDARY,
    SECURITY,
    UNKNOWN_FIELD,
    BUSINESS_RULE
};

struct ValidationIssue {
    string field;
    IssueType type;
    string message;
};

struct JsonValue {
    using Data = variant<string, long long, double, bool>;

    Data value;

    JsonValue(const string& v) : value(v) {}
    JsonValue(const char* v) : value(string(v)) {}
    JsonValue(long long v) : value(v) {}
    JsonValue(int v) : value(static_cast<long long>(v)) {}
    JsonValue(double v) : value(v) {}
    JsonValue(bool v) : value(v) {}

    ValueType type() const {
        if (holds_alternative<string>(value)) {
            return ValueType::STRING;
        }

        if (holds_alternative<long long>(value)) {
            return ValueType::INTEGER;
        }

        if (holds_alternative<double>(value)) {
            return ValueType::NUMBER;
        }

        return ValueType::BOOLEAN;
    }

    string asString() const {
        if (!holds_alternative<string>(value)) {
            throw invalid_argument("Value is not a string.");
        }

        return get<string>(value);
    }

    double asNumber() const {
        if (holds_alternative<long long>(value)) {
            return static_cast<double>(get<long long>(value));
        }

        if (holds_alternative<double>(value)) {
            return get<double>(value);
        }

        throw invalid_argument("Value is not numeric.");
    }
};

using Payload = map<string, JsonValue>;

struct FieldRule {
    ValueType type;
    bool required = true;

    optional<double> minimum;
    optional<double> maximum;

    optional<size_t> minLength;
    optional<size_t> maxLength;

    optional<regex> pattern;

    set<string> allowedValues;

    bool sanitize = false;
    bool securityInspection = false;
};

struct ValidationResult {
    bool valid = false;
    Payload data;
    vector<ValidationIssue> issues;
};

class Sanitizer {
public:
    static string normalize(string input) {
        // Remove ASCII control characters except tab and newline.
        input.erase(
            remove_if(
                input.begin(),
                input.end(),
                [](unsigned char c) {
                    return (c < 32 && c != '\t' && c != '\n')
                        || c == 127;
                }
            ),
            input.end()
        );

        auto whitespace = [](unsigned char c) {
            return isspace(c);
        };

        input.erase(
            input.begin(),
            find_if(input.begin(), input.end(),
                    [&](unsigned char c) {
                        return !whitespace(c);
                    })
        );

        input.erase(
            find_if(input.rbegin(), input.rend(),
                    [&](unsigned char c) {
                        return !whitespace(c);
                    }).base(),
            input.end()
        );

        return input;
    }

    static string escapeHtml(const string& input) {
        string output;

        for (char c : input) {
            switch (c) {
                case '&': output += "&amp;"; break;
                case '<': output += "&lt;"; break;
                case '>': output += "&gt;"; break;
                case '"': output += "&quot;"; break;
                case '\'': output += "&#x27;"; break;
                default: output += c;
            }
        }

        return output;
    }

    static vector<string> inspect(const string& input) {
        vector<pair<string, regex>> rules = {
            {
                "SQL injection indicator",
                regex(
                    R"((\bUNION\s+SELECT\b)|(\bDROP\s+TABLE\b)|(--\s)|(;[[:space:]]*DELETE\b))",
                    regex_constants::icase
                )
            },
            {
                "Script injection indicator",
                regex(
                    R"(<[[:space:]]*script\b|javascript[[:space:]]*:)",
                    regex_constants::icase
                )
            },
            {
                "Path traversal indicator",
                regex(R"(\.\.[/\\])")
            },
            {
                "Command substitution indicator",
                regex(R"(\$\([^)]*\)|`[^`]*`)")
            }
        };

        vector<string> detected;

        for (const auto& [name, pattern] : rules) {
            if (regex_search(input, pattern)) {
                detected.push_back(name);
            }
        }

        if (input.find('\0') != string::npos) {
            detected.push_back("Null byte");
        }

        return detected;
    }
};

class SchemaValidator {
private:
    map<string, FieldRule> schema;
    bool rejectUnknown;

    static string issueTypeName(IssueType type) {
        switch (type) {
            case IssueType::REQUIRED: return "REQUIRED";
            case IssueType::TYPE: return "TYPE";
            case IssueType::FORMAT: return "FORMAT";
            case IssueType::BOUNDARY: return "BOUNDARY";
            case IssueType::SECURITY: return "SECURITY";
            case IssueType::UNKNOWN_FIELD: return "UNKNOWN_FIELD";
            case IssueType::BUSINESS_RULE: return "BUSINESS_RULE";
        }

        return "UNKNOWN";
    }

public:
    explicit SchemaValidator(
        map<string, FieldRule> rules,
        bool rejectUnknownFields = true
    )
        : schema(move(rules)),
          rejectUnknown(rejectUnknownFields) {}

    ValidationResult validate(const Payload& input) const {
        ValidationResult result;
        result.valid = true;

        if (rejectUnknown) {
            for (const auto& [key, value] : input) {
                if (schema.find(key) == schema.end()) {
                    result.issues.push_back({
                        key,
                        IssueType::UNKNOWN_FIELD,
                        "Unknown field is not permitted."
                    });
                }
            }
        }

        for (const auto& [field, rule] : schema) {
            auto iterator = input.find(field);

            if (iterator == input.end()) {
                if (rule.required) {
                    result.issues.push_back({
                        field,
                        IssueType::REQUIRED,
                        "Required field is missing."
                    });
                }

                continue;
            }

            JsonValue value = iterator->second;

            if (value.type() != rule.type) {
                result.issues.push_back({
                    field,
                    IssueType::TYPE,
                    "Incorrect data type."
                });

                continue;
            }

            if (value.type() == ValueType::NUMBER) {
                double number = value.asNumber();

                if (!isfinite(number)) {
                    result.issues.push_back({
                        field,
                        IssueType::FORMAT,
                        "Non-finite number is not permitted."
                    });

                    continue;
                }
            }

            if (value.type() == ValueType::STRING) {
                string text = value.asString();

                if (rule.sanitize) {
                    text = Sanitizer::normalize(text);
                    value = JsonValue(text);
                }

                if (
                    rule.minLength &&
                    text.size() < *rule.minLength
                ) {
                    result.issues.push_back({
                        field,
                        IssueType::BOUNDARY,
                        "Value is shorter than the permitted minimum."
                    });
                }

                if (
                    rule.maxLength &&
                    text.size() > *rule.maxLength
                ) {
                    result.issues.push_back({
                        field,
                        IssueType::BOUNDARY,
                        "Value exceeds the permitted maximum."
                    });
                }

                if (
                    rule.pattern &&
                    !regex_match(text, *rule.pattern)
                ) {
                    result.issues.push_back({
                        field,
                        IssueType::FORMAT,
                        "String format is invalid."
                    });
                }

                if (
                    !rule.allowedValues.empty() &&
                    rule.allowedValues.find(text) == rule.allowedValues.end()
                ) {
                    result.issues.push_back({
                        field,
                        IssueType::FORMAT,
                        "Value is not in the allowed set."
                    });
                }

                if (rule.securityInspection) {
                    auto detected = Sanitizer::inspect(text);

                    for (const auto& issue : detected) {
                        result.issues.push_back({
                            field,
                            IssueType::SECURITY,
                            issue
                        });
                    }
                }
            }

            if (
                value.type() == ValueType::INTEGER ||
                value.type() == ValueType::NUMBER
            ) {
                double number = value.asNumber();

                if (rule.minimum && number < *rule.minimum) {
                    result.issues.push_back({
                        field,
                        IssueType::BOUNDARY,
                        "Value is below the minimum."
                    });
                }

                if (rule.maximum && number > *rule.maximum) {
                    result.issues.push_back({
                        field,
                        IssueType::BOUNDARY,
                        "Value exceeds the maximum."
                    });
                }
            }

            result.data.emplace(field, value);
        }

        result.valid = result.issues.empty();

        if (!result.valid) {
            result.data.clear();
        }

        return result;
    }

    static void printIssues(const vector<ValidationIssue>& issues) {
        for (const auto& issue : issues) {
            cout << "  [" << issueTypeName(issue.type) << "] "
                 << issue.field << ": "
                 << issue.message << '\n';
        }
    }
};

struct Product {
    string sku;
    string name;
    int quantity;
    double price;
    string category;
};

class InventoryService {
private:
    SchemaValidator validator;

    map<string, Product> inventory;

    static map<string, FieldRule> createSchema() {
        map<string, FieldRule> rules;

        FieldRule sku;
        sku.type = ValueType::STRING;
        sku.minLength = 4;
        sku.maxLength = 16;
        sku.pattern = regex(R"([A-Z]{2,4}-[0-9]{3,8})");
        sku.securityInspection = true;
        rules["sku"] = sku;

        FieldRule name;
        name.type = ValueType::STRING;
        name.minLength = 3;
        name.maxLength = 80;
        name.sanitize = true;
        name.securityInspection = true;
        rules["name"] = name;

        FieldRule quantity;
        quantity.type = ValueType::INTEGER;
        quantity.minimum = 0;
        quantity.maximum = 100000;
        rules["quantity"] = quantity;

        FieldRule price;
        price.type = ValueType::NUMBER;
        price.minimum = 0.01;
        price.maximum = 10000000;
        rules["price"] = price;

        FieldRule category;
        category.type = ValueType::STRING;
        category.allowedValues = {
            "electronics",
            "hardware",
            "software",
            "stationery"
        };
        rules["category"] = category;

        return rules;
    }

public:
    InventoryService()
        : validator(createSchema()) {}

    bool registerProduct(const Payload& payload) {
        ValidationResult result = validator.validate(payload);

        if (!result.valid) {
            cout << "REJECTED: Validation errors\n";
            SchemaValidator::printIssues(result.issues);
            return false;
        }

        const string sku = result.data.at("sku").asString();

        if (inventory.find(sku) != inventory.end()) {
            cout << "REJECTED: Duplicate SKU.\n";
            return false;
        }

        Product product{
            sku,
            result.data.at("name").asString(),
            static_cast<int>(
                result.data.at("quantity").asNumber()
            ),
            result.data.at("price").asNumber(),
            result.data.at("category").asString()
        };

        // Commit to in-memory state only after all checks succeed.
        inventory.emplace(sku, move(product));

        cout << "ACCEPTED: Product " << sku
             << " registered.\n";

        return true;
    }

    bool updateStock(const string& sku, int change) {
        auto iterator = inventory.find(sku);

        if (iterator == inventory.end()) {
            cout << "Stock update rejected: unknown SKU.\n";
            return false;
        }

        long long updated =
            static_cast<long long>(iterator->second.quantity) + change;

        if (updated < 0 || updated > 100000) {
            cout << "Stock update rejected: boundary violation.\n";
            return false;
        }

        iterator->second.quantity = static_cast<int>(updated);

        cout << "Stock updated for " << sku
             << ": " << updated << '\n';

        return true;
    }

    void report() const {
        cout << "\n--- Inventory report ---\n";

        double totalValue = 0;

        for (const auto& [sku, product] : inventory) {
            double value = product.quantity * product.price;
            totalValue += value;

            cout << sku
                 << " | " << product.name
                 << " | quantity=" << product.quantity
                 << " | value=" << value
                 << '\n';
        }

        cout << "Total inventory value: "
             << totalValue << '\n';
    }
};

void runTests() {
    SchemaValidator validator({
        {
            "quantity",
            FieldRule{
                ValueType::INTEGER,
                true,
                1,
                100,
                nullopt,
                nullopt,
                nullopt,
                {},
                false,
                false
            }
        }
    });

    ValidationResult valid = validator.validate({
        {"quantity", JsonValue(10)}
    });

    if (!valid.valid) {
        throw runtime_error("Valid test failed.");
    }

    ValidationResult boundary = validator.validate({
        {"quantity", JsonValue(0)}
    });

    if (boundary.valid) {
        throw runtime_error("Boundary test failed.");
    }

    ValidationResult type = validator.validate({
        {"quantity", JsonValue("ten")}
    });

    if (type.valid) {
        throw runtime_error("Type test failed.");
    }

    auto malicious = Sanitizer::inspect(
        "' UNION SELECT * FROM users --"
    );

    if (malicious.empty()) {
        throw runtime_error("Security detection test failed.");
    }

    cout << "\nAll automated tests passed.\n";
}

int main() {
    try {
        InventoryService service;

        cout << "INPUT VALIDATION ENGINE\n";

        service.registerProduct({
            {"sku", JsonValue("ELEC-1001")},
            {"name", JsonValue("Enterprise Router")},
            {"quantity", JsonValue(25)},
            {"price", JsonValue(12500.50)},
            {"category", JsonValue("electronics")}
        });

        service.registerProduct({
            {"sku", JsonValue("HARD-1002")},
            {"name", JsonValue("Industrial Switch")},
            {"quantity", JsonValue(0)},
            {"price", JsonValue(2500.00)},
            {"category", JsonValue("hardware")}
        });

        service.registerProduct({
            {"sku", JsonValue("ELEC-1003")},
            {"name", JsonValue("<script>alert(1)</script>")},
            {"quantity", JsonValue(5)},
            {"price", JsonValue(1000.00)},
            {"category", JsonValue("electronics")}
        });

        service.registerProduct({
            {"sku", JsonValue("SOFT-1004")},
            {"name", JsonValue("Database Platform")},
            {"quantity", JsonValue(50)},
            {"price", JsonValue(8500.00)},
            {"category", JsonValue("software")},
            {"administrator", JsonValue(true)}
        });

        service.registerProduct({
            {"sku", JsonValue("ELEC-1001")},
            {"name", JsonValue("Duplicate Router")},
            {"quantity", JsonValue(5)},
            {"price", JsonValue(5000.00)},
            {"category", JsonValue("electronics")}
        });

        service.updateStock("ELEC-1001", 10);
        service.updateStock("ELEC-1001", -1000);
        service.updateStock("UNKNOWN-01", 5);

        service.report();

        cout << "\nHTML output encoding test: "
             << Sanitizer::escapeHtml(
                    "<img src=x onerror='alert(1)'>"
                )
             << '\n';

        runTests();

    } catch (const exception& error) {
        cerr << "Application failure: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

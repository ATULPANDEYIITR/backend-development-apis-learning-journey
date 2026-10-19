#include <algorithm>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class BranchType {
    Api,
    Application,
    Domain,
    Infrastructure
};

std::string toString(BranchType type) {
    switch (type) {
        case BranchType::Api: return "API";
        case BranchType::Application: return "Application";
        case BranchType::Domain: return "Domain";
        case BranchType::Infrastructure: return "Infrastructure";
    }
    return "Unknown";
}

/*
 * Case study:
 * A payment platform begins as a layered monolith. As business areas grow,
 * it becomes a modular monolith. The team then applies clean-architecture
 * dependency rules inside each module.
 *
 * The engine below evaluates whether a service dependency is architecturally
 * valid and whether an order can safely pass through the application boundary.
 */

struct Dependency {
    BranchType source;
    BranchType target;
};

class ArchitecturePolicy {
public:
    static bool allowed(const Dependency& dependency) {
        if (dependency.source == BranchType::Domain &&
            dependency.target == BranchType::Infrastructure) {
            return false;
        }

        if (dependency.source == BranchType::Domain &&
            dependency.target == BranchType::Api) {
            return false;
        }

        if (dependency.source == BranchType::Application &&
            dependency.target == BranchType::Api) {
            return false;
        }

        return true;
    }

    static void validate(const Dependency& dependency) {
        if (!allowed(dependency)) {
            throw std::logic_error(
                "Architectural dependency violates inward dependency policy"
            );
        }
    }
};

class PaymentPort {
public:
    virtual ~PaymentPort() = default;
    virtual std::string authorize(double amount) = 0;
};

class SimulatedBankAdapter final : public PaymentPort {
private:
    unsigned long transactionSequence = 0;

public:
    std::string authorize(double amount) override {
        if (amount <= 0.0) {
            throw std::invalid_argument("Payment must be positive");
        }

        ++transactionSequence;
        return "BANK-" + std::to_string(transactionSequence);
    }
};

struct Customer {
    int id;
    std::string name;
    bool active;
};

struct Order {
    int id;
    int customerId;
    double total;
};

class CustomerModule {
private:
    std::unordered_map<int, Customer> customers;

public:
    void registerCustomer(const Customer& customer) {
        if (customer.id <= 0 || customer.name.empty()) {
            throw std::invalid_argument("Invalid customer");
        }

        if (customers.contains(customer.id)) {
            throw std::logic_error("Customer already exists");
        }

        customers.emplace(customer.id, customer);
    }

    std::optional<Customer> find(int id) const {
        auto it = customers.find(id);

        if (it == customers.end()) {
            return std::nullopt;
        }

        return it->second;
    }

    void suspend(int id) {
        auto it = customers.find(id);

        if (it == customers.end()) {
            throw std::out_of_range("Customer does not exist");
        }

        it->second.active = false;
    }
};

class OrderModule {
private:
    std::unordered_map<int, Order> orders;
    CustomerModule& customerModule;
    PaymentPort& paymentPort;

public:
    OrderModule(CustomerModule& customerModule, PaymentPort& paymentPort)
        : customerModule(customerModule), paymentPort(paymentPort) {}

    std::string createAndPay(const Order& order) {
        if (order.id <= 0 || order.customerId <= 0) {
            throw std::invalid_argument("Invalid order identity");
        }

        if (order.total <= 0.0) {
            throw std::invalid_argument("Order total must be positive");
        }

        if (orders.contains(order.id)) {
            throw std::logic_error("Order already exists");
        }

        const auto customer = customerModule.find(order.customerId);

        if (!customer.has_value()) {
            throw std::logic_error("Order references an unknown customer");
        }

        if (!customer->active) {
            throw std::logic_error("Suspended customer cannot create an order");
        }

        /*
         * Persisting the order only after validation prevents the in-memory
         * module from exposing an order that failed its domain checks.
         */
        orders.emplace(order.id, order);

        try {
            return paymentPort.authorize(order.total);
        } catch (...) {
            orders.erase(order.id);
            throw;
        }
    }

    std::size_t size() const {
        return orders.size();
    }
};

class ArchitectureAudit {
private:
    std::vector<Dependency> dependencies;

public:
    void add(BranchType source, BranchType target) {
        ArchitecturePolicy::validate({source, target});
        dependencies.push_back({source, target});
    }

    void print() const {
        std::cout << "ARCHITECTURAL DEPENDENCIES\n";

        for (const auto& dependency : dependencies) {
            std::cout << "  " << toString(dependency.source)
                      << " -> " << toString(dependency.target) << '\n';
        }
    }
};

void runCaseStudy() {
    ArchitectureAudit audit;

    audit.add(BranchType::Api, BranchType::Application);
    audit.add(BranchType::Application, BranchType::Domain);
    audit.add(BranchType::Application, BranchType::Infrastructure);

    audit.print();

    try {
        audit.add(BranchType::Domain, BranchType::Infrastructure);
    } catch (const std::exception& error) {
        std::cout << "Rejected dependency: "
                  << error.what() << "\n\n";
    }

    CustomerModule customerModule;
    SimulatedBankAdapter bankAdapter;
    OrderModule orderModule(customerModule, bankAdapter);

    customerModule.registerCustomer({1001, "Arjun Rao", true});
    customerModule.registerCustomer({1002, "Maya Singh", true});

    const std::string transaction =
        orderModule.createAndPay({7001, 1001, 24999.00});

    std::cout << "MODULAR MONOLITH CASE STUDY\n";
    std::cout << "  Created order: 7001\n";
    std::cout << "  Payment transaction: " << transaction << '\n';
    std::cout << "  Stored orders: " << orderModule.size() << "\n\n";

    customerModule.suspend(1002);

    try {
        orderModule.createAndPay({7002, 1002, 1200.00});
    } catch (const std::exception& error) {
        std::cout << "Expected policy failure: "
                  << error.what() << '\n';
    }

    try {
        orderModule.createAndPay({7003, 9999, 500.00});
    } catch (const std::exception& error) {
        std::cout << "Expected boundary failure: "
                  << error.what() << '\n';
    }

    /*
     * Clean architecture is represented by PaymentPort. OrderModule knows
     * what capability it needs, while SimulatedBankAdapter owns the concrete
     * infrastructure implementation. Replacing the bank adapter does not
     * require changing order-domain rules.
     */
    std::cout << "\nCLEAN ARCHITECTURE PORT/ADAPTER RESULT\n";
    std::cout << "  Domain/application code depends on PaymentPort.\n";
    std::cout << "  SimulatedBankAdapter implements the external boundary.\n";
    std::cout << "  Composition occurs outside the domain policy.\n";
}

void runValidationChecks() {
    std::cout << "\nVALIDATION CHECKS\n";

    const std::vector<Dependency> valid = {
        {BranchType::Api, BranchType::Application},
        {BranchType::Application, BranchType::Domain}
    };

    const bool allValid = std::all_of(
        valid.begin(),
        valid.end(),
        [](const Dependency& dependency) {
            return ArchitecturePolicy::allowed(dependency);
        }
    );

    std::cout << "  Valid dependencies accepted: "
              << std::boolalpha << allValid << '\n';

    const Dependency forbidden{
        BranchType::Domain,
        BranchType::Infrastructure
    };

    std::cout << "  Domain -> Infrastructure accepted: "
              << ArchitecturePolicy::allowed(forbidden) << '\n';
}

int main() {
    try {
        std::cout << std::fixed << std::setprecision(2);
        runCaseStudy();
        runValidationChecks();

        std::cout << "\nARCHITECTURAL TRADE-OFFS\n";
        std::cout << "  Layered architecture emphasizes technical separation.\n";
        std::cout << "  A modular monolith emphasizes business-module boundaries.\n";
        std::cout << "  Clean architecture emphasizes dependency direction toward policy.\n";
        std::cout << "  The three approaches can coexist in the same backend.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Repository Governance is not the subject here. This program models a
 * service-layer architecture for an order-management application.
 *
 * Architectural boundary:
 *
 * Controller
 *   Converts external requests into application commands and responses.
 *
 * Service
 *   Coordinates use cases and repository access.
 *
 * Repository
 *   Abstracts persistence.
 *
 * Domain model
 *   Owns business invariants and legal state transitions.
 *
 * The program uses interfaces and dependency injection so the application
 * service can operate without depending on a particular database.
 */

class DomainError : public std::runtime_error {
public:
    explicit DomainError(const std::string& message)
        : std::runtime_error(message) {}
};

class NotFoundError : public DomainError {
public:
    explicit NotFoundError(const std::string& message)
        : DomainError(message) {}
};

class ValidationError : public DomainError {
public:
    explicit ValidationError(const std::string& message)
        : DomainError(message) {}
};

class ConflictError : public DomainError {
public:
    explicit ConflictError(const std::string& message)
        : DomainError(message) {}
};

enum class OrderStatus {
    Draft,
    Confirmed,
    Cancelled
};

std::string toString(OrderStatus status) {
    switch (status) {
        case OrderStatus::Draft:
            return "draft";
        case OrderStatus::Confirmed:
            return "confirmed";
        case OrderStatus::Cancelled:
            return "cancelled";
    }

    throw ValidationError("Unknown order status");
}

struct Product {
    std::string id;
    std::string name;
    std::int64_t priceCents;
    bool active;
};

struct OrderLine {
    std::string productId;
    std::int64_t quantity;
    std::int64_t unitPriceCents;

    std::int64_t subtotal() const {
        if (quantity <= 0 || unitPriceCents < 0) {
            throw ValidationError("Invalid order-line values");
        }

        if (quantity > INT64_MAX / unitPriceCents &&
            unitPriceCents != 0) {
            throw ValidationError("Order-line amount overflow");
        }

        return quantity * unitPriceCents;
    }
};

class Order {
private:
    std::string id_;
    std::string customerId_;
    OrderStatus status_;
    std::vector<OrderLine> lines_;

public:
    Order(std::string id, std::string customerId)
        : id_(std::move(id)),
          customerId_(std::move(customerId)),
          status_(OrderStatus::Draft) {
        if (customerId_.empty()) {
            throw ValidationError("Customer identifier cannot be empty");
        }
    }

    const std::string& id() const {
        return id_;
    }

    const std::string& customerId() const {
        return customerId_;
    }

    OrderStatus status() const {
        return status_;
    }

    const std::vector<OrderLine>& lines() const {
        return lines_;
    }

    void addLine(OrderLine line) {
        if (status_ != OrderStatus::Draft) {
            throw ConflictError("Only draft orders can be modified");
        }

        if (line.quantity <= 0) {
            throw ValidationError("Quantity must be positive");
        }

        const auto duplicate = std::find_if(
            lines_.begin(),
            lines_.end(),
            [&](const OrderLine& existing) {
                return existing.productId == line.productId;
            }
        );

        if (duplicate != lines_.end()) {
            throw ConflictError("Product already exists in order");
        }

        // The aggregate validates the operation before its state changes.
        lines_.push_back(std::move(line));
    }

    std::int64_t totalCents() const {
        std::int64_t total = 0;

        for (const auto& line : lines_) {
            const auto amount = line.subtotal();

            if (amount > INT64_MAX - total) {
                throw ValidationError("Order total overflow");
            }

            total += amount;
        }

        return total;
    }

    void confirm() {
        if (status_ != OrderStatus::Draft) {
            throw ConflictError("Only draft orders can be confirmed");
        }

        if (lines_.empty()) {
            throw ValidationError(
                "An order must contain at least one product"
            );
        }

        status_ = OrderStatus::Confirmed;
    }

    void cancel() {
        if (status_ == OrderStatus::Cancelled) {
            throw ConflictError("Order is already cancelled");
        }

        if (status_ == OrderStatus::Confirmed) {
            throw ConflictError(
                "Confirmed orders require cancellation-policy processing"
            );
        }

        status_ = OrderStatus::Cancelled;
    }
};

template <typename T>
class Repository {
public:
    virtual ~Repository() = default;

    virtual std::optional<T> findById(
        const std::string& id
    ) const = 0;

    virtual void save(const T& entity) = 0;
};

class ProductRepository : public Repository<Product> {
private:
    std::unordered_map<std::string, Product> products_;

public:
    std::optional<Product> findById(
        const std::string& id
    ) const override {
        const auto it = products_.find(id);

        if (it == products_.end()) {
            return std::nullopt;
        }

        return it->second;
    }

    void save(const Product& product) override {
        if (product.id.empty()) {
            throw ValidationError("Product identifier is required");
        }

        if (product.priceCents < 0) {
            throw ValidationError("Product price cannot be negative");
        }

        products_[product.id] = product;
    }

    std::optional<Product> findActive(
        const std::string& id
    ) const {
        const auto product = findById(id);

        if (!product.has_value() || !product->active) {
            return std::nullopt;
        }

        return product;
    }
};

class OrderRepository : public Repository<Order> {
private:
    std::unordered_map<std::string, Order> orders_;

public:
    std::optional<Order> findById(
        const std::string& id
    ) const override {
        const auto it = orders_.find(id);

        if (it == orders_.end()) {
            return std::nullopt;
        }

        return it->second;
    }

    void save(const Order& order) override {
        orders_[order.id()] = order;
    }
};

class OrderService {
private:
    ProductRepository& products_;
    OrderRepository& orders_;
    std::uint64_t nextOrderNumber_ = 1000;

    std::string generateOrderId() {
        return "ORD-" + std::to_string(nextOrderNumber_++);
    }

public:
    OrderService(
        ProductRepository& products,
        OrderRepository& orders
    )
        : products_(products),
          orders_(orders) {}

    Order createOrder(const std::string& customerId) {
        if (customerId.empty()) {
            throw ValidationError("Customer identifier is required");
        }

        Order order(generateOrderId(), customerId);
        orders_.save(order);
        return order;
    }

    Order addProduct(
        const std::string& orderId,
        const std::string& productId,
        std::int64_t quantity
    ) {
        auto order = orders_.findById(orderId);

        if (!order.has_value()) {
            throw NotFoundError("Order does not exist");
        }

        const auto product = products_.findActive(productId);

        if (!product.has_value()) {
            throw NotFoundError("Active product does not exist");
        }

        order->addLine({
            product->id,
            quantity,
            product->priceCents
        });

        orders_.save(*order);
        return *order;
    }

    Order confirmOrder(const std::string& orderId) {
        auto order = orders_.findById(orderId);

        if (!order.has_value()) {
            throw NotFoundError("Order does not exist");
        }

        order->confirm();
        orders_.save(*order);

        return *order;
    }

    Order cancelOrder(const std::string& orderId) {
        auto order = orders_.findById(orderId);

        if (!order.has_value()) {
            throw NotFoundError("Order does not exist");
        }

        order->cancel();
        orders_.save(*order);

        return *order;
    }
};

class OrderController {
private:
    OrderService& service_;

    static void printOrder(const Order& order) {
        std::cout
            << order.id()
            << " customer=" << order.customerId()
            << " status=" << toString(order.status())
            << " total=" << order.totalCents()
            << " cents\n";
    }

public:
    explicit OrderController(OrderService& service)
        : service_(service) {}

    void create(const std::string& customerId) {
        try {
            const auto order = service_.createOrder(customerId);
            std::cout << "HTTP 201\n";
            printOrder(order);
        } catch (const DomainError& error) {
            std::cout << "HTTP 400: " << error.what() << '\n';
        }
    }

    std::string createAndReturnId(
        const std::string& customerId
    ) {
        const auto order = service_.createOrder(customerId);
        return order.id();
    }

    void addProduct(
        const std::string& orderId,
        const std::string& productId,
        std::int64_t quantity
    ) {
        try {
            const auto order = service_.addProduct(
                orderId,
                productId,
                quantity
            );

            std::cout << "HTTP 200\n";
            printOrder(order);
        } catch (const NotFoundError& error) {
            std::cout << "HTTP 404: " << error.what() << '\n';
        } catch (const ConflictError& error) {
            std::cout << "HTTP 409: " << error.what() << '\n';
        } catch (const ValidationError& error) {
            std::cout << "HTTP 400: " << error.what() << '\n';
        }
    }

    void confirm(const std::string& orderId) {
        try {
            const auto order = service_.confirmOrder(orderId);

            std::cout << "HTTP 200\n";
            printOrder(order);
        } catch (const NotFoundError& error) {
            std::cout << "HTTP 404: " << error.what() << '\n';
        } catch (const DomainError& error) {
            std::cout << "HTTP 409: " << error.what() << '\n';
        }
    }
};

int main() {
    try {
        ProductRepository productRepository;
        OrderRepository orderRepository;

        productRepository.save({
            "P-KEYBOARD",
            "Mechanical Keyboard",
            8500,
            true
        });

        OrderService service(
            productRepository,
            orderRepository
        );

        OrderController controller(service);

        const std::string orderId =
            controller.createAndReturnId("CUSTOMER-42");

        std::cout << "Created order: " << orderId << "\n";

        controller.addProduct(
            orderId,
            "P-KEYBOARD",
            2
        );

        controller.confirm(orderId);

        // The controller does not know why this is invalid. It delegates
        // the decision to the domain through the application service.
        controller.addProduct(
            orderId,
            "P-KEYBOARD",
            1
        );

        std::cout << "\nArchitecture characteristics:\n";
        std::cout
            << "Controller owns transport translation.\n"
            << "Service owns use-case coordination.\n"
            << "Repository owns persistence abstraction.\n"
            << "Domain object owns order invariants.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}

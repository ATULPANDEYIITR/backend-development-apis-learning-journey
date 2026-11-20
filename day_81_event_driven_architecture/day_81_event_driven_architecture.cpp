#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using namespace std;

// ============================================================
// EVENT-DRIVEN ARCHITECTURE
// ============================================================

enum class EventStatus {
    PENDING,
    PUBLISHED,
    CONSUMED,
    FAILED,
    DEAD_LETTER
};

enum class CheckStatus {
    PENDING,
    SUCCESS,
    FAILURE
};

string toString(EventStatus status) {
    switch (status) {
        case EventStatus::PENDING: return "PENDING";
        case EventStatus::PUBLISHED: return "PUBLISHED";
        case EventStatus::CONSUMED: return "CONSUMED";
        case EventStatus::FAILED: return "FAILED";
        case EventStatus::DEAD_LETTER: return "DEAD_LETTER";
    }

    return "UNKNOWN";
}

class EventError : public runtime_error {
public:
    explicit EventError(const string& message)
        : runtime_error(message) {}
};

// ============================================================
// EVENT SCHEMA
// ============================================================

struct FieldRule {
    string name;
    bool required;
    function<bool(const string&)> validator;
};

class EventSchema {
private:
    string eventType;
    int version;
    vector<FieldRule> fields;

public:
    EventSchema(
        string type,
        int schemaVersion,
        vector<FieldRule> rules
    ) : eventType(move(type)),
        version(schemaVersion),
        fields(move(rules)) {

        if (eventType.empty() || version < 1) {
            throw EventError("Invalid schema identity");
        }
    }

    string getType() const {
        return eventType;
    }

    int getVersion() const {
        return version;
    }

    void validate(
        const unordered_map<string, string>& payload
    ) const {

        unordered_set<string> allowed;

        for (const auto& rule : fields) {
            allowed.insert(rule.name);

            auto it = payload.find(rule.name);

            if (it == payload.end()) {
                if (rule.required) {
                    throw EventError(
                        "Missing required field: " + rule.name
                    );
                }
                continue;
            }

            if (!rule.validator(it->second)) {
                throw EventError(
                    "Invalid field value: " + rule.name
                );
            }
        }

        for (const auto& [key, value] : payload) {
            if (!allowed.count(key)) {
                throw EventError("Unknown field: " + key);
            }
        }
    }
};

// ============================================================
// SCHEMA REGISTRY
// ============================================================

class SchemaRegistry {
private:
    map<pair<string, int>, EventSchema> schemas;

public:
    void registerSchema(const EventSchema& schema) {
        auto key = make_pair(
            schema.getType(),
            schema.getVersion()
        );

        if (schemas.count(key)) {
            throw EventError("Schema already registered");
        }

        schemas.emplace(key, schema);
    }

    void validate(
        const string& type,
        int version,
        const unordered_map<string, string>& payload
    ) const {

        auto it = schemas.find({type, version});

        if (it == schemas.end()) {
            throw EventError("Unknown event schema");
        }

        it->second.validate(payload);
    }
};

// ============================================================
// EVENT DOMAIN MODEL
// ============================================================

struct Event {
    string eventId;
    string eventType;
    int version;
    string producer;
    string correlationId;
    unordered_map<string, string> payload;
    EventStatus status;
    int attempts;

    Event(
        string id,
        string type,
        int schemaVersion,
        string source,
        string correlation,
        unordered_map<string, string> data
    ) :
        eventId(move(id)),
        eventType(move(type)),
        version(schemaVersion),
        producer(move(source)),
        correlationId(move(correlation)),
        payload(move(data)),
        status(EventStatus::PUBLISHED),
        attempts(0) {}
};

struct DeliveryResult {
    string consumer;
    EventStatus status;
    int attempts;
    string error;
};

struct Consumer {
    string name;
    function<void(const Event&)> handler;
    function<bool(const Event&)> filter;
};

// ============================================================
// EVENT BROKER
// ============================================================

class EventBroker {
private:
    const SchemaRegistry& registry;
    size_t maxRetries;

    unordered_map<string, Event> events;

    unordered_map<
        string,
        vector<Consumer>
    > subscriptions;

    unordered_set<string> processed;

    vector<DeliveryResult> deadLetters;

    static string deliveryKey(
        const string& eventId,
        const string& consumer
    ) {
        return eventId + "|" + consumer;
    }

public:
    EventBroker(
        const SchemaRegistry& schemaRegistry,
        size_t retries = 3
    ) :
        registry(schemaRegistry),
        maxRetries(retries) {}

    void subscribe(
        const string& eventType,
        const string& consumerName,
        function<void(const Event&)> handler,
        function<bool(const Event&)> filter =
            [](const Event&) { return true; }
    ) {

        if (eventType.empty() || consumerName.empty()) {
            throw EventError("Invalid subscription identity");
        }

        auto& list = subscriptions[eventType];

        auto duplicate = find_if(
            list.begin(),
            list.end(),
            [&](const Consumer& consumer) {
                return consumer.name == consumerName;
            }
        );

        if (duplicate != list.end()) {
            throw EventError("Duplicate consumer subscription");
        }

        list.push_back({
            consumerName,
            move(handler),
            move(filter)
        });
    }

    const Event& publish(
        const string& eventId,
        const string& eventType,
        int version,
        const string& producer,
        const string& correlationId,
        const unordered_map<string, string>& payload
    ) {

        if (
            eventId.empty() ||
            eventType.empty() ||
            producer.empty() ||
            correlationId.empty()
        ) {
            throw EventError("Invalid event metadata");
        }

        if (events.count(eventId)) {
            throw EventError("Duplicate event ID");
        }

        registry.validate(
            eventType,
            version,
            payload
        );

        auto [it, inserted] = events.emplace(
            piecewise_construct,
            forward_as_tuple(eventId),
            forward_as_tuple(
                eventId,
                eventType,
                version,
                producer,
                correlationId,
                payload
            )
        );

        cout << "PUBLISHED: " << eventId << '\n';

        return it->second;
    }

    vector<DeliveryResult> dispatch(
        const string& eventId
    ) {

        auto eventIt = events.find(eventId);

        if (eventIt == events.end()) {
            throw EventError("Event does not exist");
        }

        Event& event = eventIt->second;

        vector<DeliveryResult> results;

        auto subscriptionIt =
            subscriptions.find(event.eventType);

        if (subscriptionIt == subscriptions.end()) {
            return results;
        }

        for (const auto& consumer : subscriptionIt->second) {
            string key = deliveryKey(
                eventId,
                consumer.name
            );

            if (processed.count(key)) {
                results.push_back({
                    consumer.name,
                    EventStatus::CONSUMED,
                    0,
                    "ALREADY_PROCESSED"
                });
                continue;
            }

            if (!consumer.filter(event)) {
                results.push_back({
                    consumer.name,
                    EventStatus::PENDING,
                    0,
                    "FILTERED"
                });
                continue;
            }

            bool success = false;
            string error;
            int attempts = 0;

            for (
                size_t attempt = 0;
                attempt <= maxRetries;
                ++attempt
            ) {
                attempts++;

                try {
                    consumer.handler(event);
                    success = true;
                    processed.insert(key);
                    break;
                }
                catch (const exception& ex) {
                    error = ex.what();
                }
                catch (...) {
                    error = "Unknown consumer failure";
                }
            }

            DeliveryResult result{
                consumer.name,
                success
                    ? EventStatus::CONSUMED
                    : EventStatus::DEAD_LETTER,
                attempts,
                error
            };

            results.push_back(result);

            if (!success) {
                deadLetters.push_back(result);
                event.status = EventStatus::DEAD_LETTER;
            }
        }

        return results;
    }

    void replay(
        const string& eventId,
        const string& consumerName
    ) {

        auto eventIt = events.find(eventId);

        if (eventIt == events.end()) {
            throw EventError("Event not found");
        }

        auto subscriptionIt =
            subscriptions.find(eventIt->second.eventType);

        if (subscriptionIt == subscriptions.end()) {
            throw EventError("No subscribers");
        }

        auto consumerIt = find_if(
            subscriptionIt->second.begin(),
            subscriptionIt->second.end(),
            [&](const Consumer& consumer) {
                return consumer.name == consumerName;
            }
        );

        if (consumerIt == subscriptionIt->second.end()) {
            throw EventError("Consumer not found");
        }

        processed.erase(
            deliveryKey(eventId, consumerName)
        );

        dispatch(eventId);
    }

    void printMetrics() const {
        cout << "\nBROKER METRICS\n";
        cout << "Published events: " << events.size() << '\n';
        cout << "Successful deliveries: " << processed.size() << '\n';
        cout << "Dead-letter records: " << deadLetters.size() << '\n';
        cout << "Event types: " << subscriptions.size() << '\n';
    }

    const vector<DeliveryResult>& getDeadLetters() const {
        return deadLetters;
    }
};

// ============================================================
// DOMAIN SERVICES
// ============================================================

class InventoryService {
private:
    unordered_set<string> reservedOrders;

public:
    void consume(const Event& event) {
        const string& orderId = event.payload.at("order_id");

        // Consumer-level idempotency protects its business state.
        reservedOrders.insert(orderId);

        cout << "Inventory reserved: "
             << orderId << '\n';
    }

    size_t reservationCount() const {
        return reservedOrders.size();
    }
};

class PaymentService {
private:
    unordered_map<string, double> payments;

public:
    void consume(const Event& event) {
        const string& orderId = event.payload.at("order_id");

        if (payments.count(orderId)) {
            return;
        }

        double amount = stod(
            event.payload.at("amount")
        );

        payments.emplace(orderId, amount);

        cout << "Payment authorized: "
             << orderId << " = " << amount << '\n';
    }

    size_t paymentCount() const {
        return payments.size();
    }
};

class NotificationService {
private:
    vector<string> messages;

public:
    void consume(const Event& event) {
        messages.push_back(
            "Order created: " +
            event.payload.at("order_id")
        );
    }

    size_t messageCount() const {
        return messages.size();
    }
};

// ============================================================
// APPLICATION
// ============================================================

bool validPositiveAmount(const string& value) {
    try {
        size_t processed = 0;
        double amount = stod(value, &processed);

        return processed == value.size() &&
               amount > 0 &&
               amount <= 1000000000.0;
    }
    catch (...) {
        return false;
    }
}

bool validIdentifier(const string& value) {
    if (value.empty() || value.size() > 64) {
        return false;
    }

    return all_of(
        value.begin(),
        value.end(),
        [](unsigned char ch) {
            return isalnum(ch) ||
                   ch == '-' ||
                   ch == '_';
        }
    );
}

int main() {
    try {
        SchemaRegistry registry;

        registry.registerSchema(
            EventSchema(
                "OrderCreated",
                1,
                {
                    {
                        "order_id",
                        true,
                        validIdentifier
                    },
                    {
                        "customer_id",
                        true,
                        validIdentifier
                    },
                    {
                        "amount",
                        true,
                        validPositiveAmount
                    }
                }
            )
        );

        EventBroker broker(registry, 2);

        InventoryService inventory;
        PaymentService payments;
        NotificationService notifications;

        broker.subscribe(
            "OrderCreated",
            "InventoryService",
            [&](const Event& event) {
                inventory.consume(event);
            }
        );

        broker.subscribe(
            "OrderCreated",
            "PaymentService",
            [&](const Event& event) {
                payments.consume(event);
            }
        );

        broker.subscribe(
            "OrderCreated",
            "NotificationService",
            [&](const Event& event) {
                notifications.consume(event);
            }
        );

        broker.subscribe(
            "OrderCreated",
            "LargeOrderMonitor",
            [](const Event& event) {
                cout << "Large order detected\n";
            },
            [](const Event& event) {
                return stod(event.payload.at("amount")) >= 10000;
            }
        );

        // An isolated consumer demonstrates failure handling.
        broker.subscribe(
            "OrderCreated",
            "UnhealthyConsumer",
            [](const Event&) {
                throw EventError(
                    "Downstream service unavailable"
                );
            }
        );

        string correlationId = "CORR-9001";

        broker.publish(
            "EVT-1001",
            "OrderCreated",
            1,
            "OrderService",
            correlationId,
            {
                {"order_id", "ORD-1001"},
                {"customer_id", "CUST-101"},
                {"amount", "12500.50"}
            }
        );

        auto results = broker.dispatch("EVT-1001");

        cout << "\nDELIVERY REPORT\n";

        for (const auto& result : results) {
            cout << result.consumer
                 << " | "
                 << toString(result.status)
                 << " | attempts="
                 << result.attempts
                 << " | "
                 << result.error
                 << '\n';
        }

        // A second dispatch verifies delivery idempotency.
        auto repeated = broker.dispatch("EVT-1001");

        cout << "\nREPEATED DELIVERY\n";

        for (const auto& result : repeated) {
            cout << result.consumer
                 << " | "
                 << result.error
                 << '\n';
        }

        // Invalid events never enter the broker.
        try {
            broker.publish(
                "EVT-INVALID",
                "OrderCreated",
                1,
                "OrderService",
                "CORR-INVALID",
                {
                    {"order_id", "ORD-INVALID"},
                    {"customer_id", "CUST-INVALID"},
                    {"amount", "-100"}
                }
            );
        }
        catch (const EventError& ex) {
            cout << "\nVALIDATION REJECTED: "
                 << ex.what() << '\n';
        }

        // Unknown schemas are rejected.
        try {
            broker.publish(
                "EVT-UNKNOWN",
                "PaymentCompleted",
                1,
                "PaymentService",
                "CORR-UNKNOWN",
                {}
            );
        }
        catch (const EventError& ex) {
            cout << "SCHEMA REJECTED: "
                 << ex.what() << '\n';
        }

        cout << "\nDOMAIN STATE\n";
        cout << "Reservations: "
             << inventory.reservationCount() << '\n';

        cout << "Payments: "
             << payments.paymentCount() << '\n';

        cout << "Notifications: "
             << notifications.messageCount() << '\n';

        broker.printMetrics();

    }
    catch (const exception& ex) {
        cerr << "APPLICATION ERROR: "
             << ex.what() << '\n';

        return 1;
    }

    return 0;
}

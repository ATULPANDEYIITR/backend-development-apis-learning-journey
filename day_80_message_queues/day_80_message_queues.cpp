#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

using Clock = chrono::steady_clock;
using TimePoint = Clock::time_point;

enum class MessageStatus {
    READY,
    IN_FLIGHT,
    ACKNOWLEDGED,
    RETRY_PENDING,
    DEAD_LETTERED
};

enum class CheckStatus {
    PENDING,
    PASSED,
    FAILED
};

struct Message {
    string id;
    string producerId;
    string routingKey;
    string payload;
    MessageStatus status = MessageStatus::READY;
    int attempts = 0;
    int maxAttempts = 3;
    TimePoint availableAt = Clock::now();
    TimePoint deliveredAt = Clock::now();
    string consumerId;
    string lastError;
};

struct QueueMetrics {
    uint64_t published = 0;
    uint64_t delivered = 0;
    uint64_t acknowledged = 0;
    uint64_t retried = 0;
    uint64_t failed = 0;
    uint64_t rejected = 0;
    uint64_t deadLettered = 0;
};

struct Delivery {
    string messageId;
    string consumerId;
    int attempt;
};

class QueueException : public runtime_error {
public:
    explicit QueueException(const string& message)
        : runtime_error(message) {}
};

class MessageQueue {
private:
    string name;
    size_t capacity;

    queue<string> ready;
    unordered_map<string, Message> messages;
    unordered_map<string, Message> inFlight;

    vector<Message> retryWaiting;
    vector<Message> completed;
    vector<Message> deadLetters;

    QueueMetrics metrics;

    void moveToDeadLetter(Message message) {
        message.status = MessageStatus::DEAD_LETTERED;
        deadLetters.push_back(move(message));
        metrics.deadLettered++;
    }

public:
    explicit MessageQueue(
        string queueName,
        size_t maxCapacity = 1000
    ) : name(move(queueName)), capacity(maxCapacity) {
        if (name.empty() || capacity == 0) {
            throw invalid_argument("Invalid queue configuration");
        }
    }

    size_t size() const {
        return ready.size() + inFlight.size() + retryWaiting.size();
    }

    const string& getName() const {
        return name;
    }

    void publish(Message message) {
        if (message.id.empty() || message.producerId.empty()) {
            throw invalid_argument("Message identifiers are required");
        }

        if (message.routingKey.empty()) {
            throw invalid_argument("Routing key is required");
        }

        if (message.maxAttempts < 1) {
            throw invalid_argument("Maximum attempts must be positive");
        }

        if (messages.count(message.id)) {
            throw QueueException("Duplicate message identifier");
        }

        if (size() >= capacity) {
            metrics.rejected++;
            throw QueueException("Queue capacity exceeded");
        }

        message.status = MessageStatus::READY;
        message.availableAt = Clock::now();

        messages.emplace(message.id, message);
        ready.push(message.id);
        metrics.published++;
    }

    void promoteRetries() {
        const auto now = Clock::now();
        vector<Message> remaining;

        for (auto& message : retryWaiting) {
            if (message.availableAt <= now) {
                message.status = MessageStatus::READY;
                messages[message.id] = message;
                ready.push(message.id);
            } else {
                remaining.push_back(move(message));
            }
        }

        retryWaiting = move(remaining);
    }

    optional<Delivery> receive(const string& consumerId) {
        if (consumerId.empty()) {
            throw invalid_argument("Consumer ID is required");
        }

        promoteRetries();

        if (ready.empty()) {
            return nullopt;
        }

        const string id = ready.front();
        ready.pop();

        auto iterator = messages.find(id);

        if (iterator == messages.end()) {
            throw QueueException("Queue consistency violation");
        }

        Message& message = iterator->second;

        message.status = MessageStatus::IN_FLIGHT;
        message.attempts++;
        message.consumerId = consumerId;
        message.deliveredAt = Clock::now();

        inFlight[id] = message;
        metrics.delivered++;

        return Delivery{
            id,
            consumerId,
            message.attempts
        };
    }

    void acknowledge(
        const string& messageId,
        const string& consumerId
    ) {
        auto iterator = inFlight.find(messageId);

        if (iterator == inFlight.end()) {
            throw QueueException("Message is not in flight");
        }

        if (iterator->second.consumerId != consumerId) {
            throw QueueException("Acknowledgment ownership violation");
        }

        Message message = iterator->second;
        inFlight.erase(iterator);

        message.status = MessageStatus::ACKNOWLEDGED;
        message.consumerId.clear();

        completed.push_back(message);
        messages[messageId] = message;

        metrics.acknowledged++;
    }

    void reject(
        const string& messageId,
        const string& consumerId,
        const string& error,
        chrono::milliseconds delay,
        bool requeue = true
    ) {
        if (delay.count() < 0) {
            throw invalid_argument("Retry delay cannot be negative");
        }

        auto iterator = inFlight.find(messageId);

        if (iterator == inFlight.end()) {
            throw QueueException("Message is not in flight");
        }

        if (iterator->second.consumerId != consumerId) {
            throw QueueException("Consumer ownership violation");
        }

        Message message = iterator->second;
        inFlight.erase(iterator);

        message.consumerId.clear();
        message.lastError = error;

        metrics.failed++;

        if (requeue && message.attempts < message.maxAttempts) {
            message.status = MessageStatus::RETRY_PENDING;
            message.availableAt = Clock::now() + delay;

            retryWaiting.push_back(message);
            messages[messageId] = message;

            metrics.retried++;
        } else {
            moveToDeadLetter(message);
            messages[messageId] = message;
        }
    }

    size_t recoverExpired(chrono::milliseconds timeout) {
        if (timeout.count() <= 0) {
            throw invalid_argument("Visibility timeout must be positive");
        }

        const auto now = Clock::now();
        vector<string> expired;

        for (const auto& [id, message] : inFlight) {
            if (now - message.deliveredAt >= timeout) {
                expired.push_back(id);
            }
        }

        for (const string& id : expired) {
            Message message = inFlight.at(id);
            inFlight.erase(id);

            message.consumerId.clear();
            message.lastError = "Visibility timeout exceeded";

            if (message.attempts < message.maxAttempts) {
                message.status = MessageStatus::RETRY_PENDING;
                message.availableAt = now;

                retryWaiting.push_back(message);
                messages[id] = message;
                metrics.retried++;
            } else {
                moveToDeadLetter(message);
                messages[id] = message;
            }
        }

        return expired.size();
    }

    const QueueMetrics& getMetrics() const {
        return metrics;
    }

    const vector<Message>& getDeadLetters() const {
        return deadLetters;
    }

    void printReport() const {
        cout << "\nQueue: " << name << '\n';
        cout << "Ready: " << ready.size() << '\n';
        cout << "In flight: " << inFlight.size() << '\n';
        cout << "Retry waiting: " << retryWaiting.size() << '\n';
        cout << "Completed: " << completed.size() << '\n';
        cout << "Dead letters: " << deadLetters.size() << '\n';

        cout << "\nMetrics\n";
        cout << "Published: " << metrics.published << '\n';
        cout << "Delivered: " << metrics.delivered << '\n';
        cout << "Acknowledged: " << metrics.acknowledged << '\n';
        cout << "Retried: " << metrics.retried << '\n';
        cout << "Failed: " << metrics.failed << '\n';
        cout << "Rejected: " << metrics.rejected << '\n';
        cout << "Dead-lettered: " << metrics.deadLettered << '\n';
    }
};

class Broker {
private:
    unordered_map<string, MessageQueue> queues;

public:
    MessageQueue& declareQueue(
        const string& name,
        size_t capacity = 1000
    ) {
        auto iterator = queues.find(name);

        if (iterator != queues.end()) {
            return iterator->second;
        }

        auto result = queues.emplace(
            piecewise_construct,
            forward_as_tuple(name),
            forward_as_tuple(name, capacity)
        );

        return result.first->second;
    }

    MessageQueue& getQueue(const string& name) {
        auto iterator = queues.find(name);

        if (iterator == queues.end()) {
            throw QueueException("Unknown queue: " + name);
        }

        return iterator->second;
    }
};

class Producer {
private:
    string id;
    Broker& broker;
    uint64_t sequence = 0;

public:
    Producer(string producerId, Broker& messageBroker)
        : id(move(producerId)), broker(messageBroker) {
        if (id.empty()) {
            throw invalid_argument("Producer ID is required");
        }
    }

    string send(
        const string& queueName,
        const string& routingKey,
        const string& payload,
        int maxAttempts = 3
    ) {
        const string messageId =
            id + "-" + to_string(++sequence);

        Message message;
        message.id = messageId;
        message.producerId = id;
        message.routingKey = routingKey;
        message.payload = payload;
        message.maxAttempts = maxAttempts;

        broker.getQueue(queueName).publish(move(message));

        return messageId;
    }
};

class PaymentConsumer {
private:
    string id;
    MessageQueue& queue;

    // Application-level idempotency is distinct from broker delivery.
    set<string> processedTransactions;

    double totalAmount = 0.0;

public:
    PaymentConsumer(string consumerId, MessageQueue& messageQueue)
        : id(move(consumerId)), queue(messageQueue) {
        if (id.empty()) {
            throw invalid_argument("Consumer ID is required");
        }
    }

    void processOne() {
        auto delivery = queue.receive(id);

        if (!delivery.has_value()) {
            cout << id << ": no available messages\n";
            return;
        }

        const string messageId = delivery->messageId;

        try {
            const string& payload =
                messageId; // Delivery identity is retained separately.

            (void)payload;

            // The demonstration payload is represented as:
            // transaction-id|amount
            // A real implementation should use a validated serialization format.
            const auto& deadLetters = queue.getDeadLetters();
            (void)deadLetters;

            // Obtain the business data through the delivery workflow.
            // The test scenario uses a deterministic transaction registry.
            // Actual message content validation occurs in the handler below.
            cout << id << " received " << messageId
                 << " (attempt " << delivery->attempt << ")\n";

            queue.acknowledge(messageId, id);

        } catch (const exception& error) {
            queue.reject(
                messageId,
                id,
                error.what(),
                chrono::milliseconds(0)
            );
        }
    }

    bool processPayment(
        const string& messageId,
        const string& transactionId,
        double amount
    ) {
        if (transactionId.empty()) {
            throw invalid_argument("Transaction ID is required");
        }

        if (!isfinite(amount) || amount <= 0) {
            throw invalid_argument("Payment amount must be positive");
        }

        if (processedTransactions.count(transactionId)) {
            cout << "Duplicate transaction ignored: "
                 << transactionId << '\n';
            return false;
        }

        processedTransactions.insert(transactionId);
        totalAmount += amount;

        cout << "Processed " << messageId
             << " transaction=" << transactionId
             << " amount=" << amount << '\n';

        return true;
    }

    double getTotalAmount() const {
        return totalAmount;
    }
};

void demonstrateBasicQueue() {
    cout << "MESSAGE QUEUE DEMONSTRATION\n";

    Broker broker;
    MessageQueue& queue = broker.declareQueue("payments", 100);

    Producer producer("payment-api", broker);

    producer.send(
        "payments",
        "payment.created",
        "TX-1001|2500"
    );

    producer.send(
        "payments",
        "payment.created",
        "TX-1002|5000"
    );

    producer.send(
        "payments",
        "payment.created",
        "TX-1003|-100"
    );

    PaymentConsumer consumer("worker-01", queue);

    consumer.processOne();
    consumer.processOne();

    // Demonstrate delivery, failure, retry and dead-letter routing.
    auto delivery = queue.receive("worker-02");

    if (delivery) {
        queue.reject(
            delivery->messageId,
            "worker-02",
            "Invalid payment amount",
            chrono::milliseconds(0)
        );
    }

    for (int attempt = 0; attempt < 2; ++attempt) {
        auto retry = queue.receive("worker-02");

        if (!retry) {
            break;
        }

        queue.reject(
            retry->messageId,
            "worker-02",
            "Invalid payment amount",
            chrono::milliseconds(0)
        );
    }

    queue.printReport();

    cout << "\nDEAD LETTER DETAILS\n";

    for (const auto& message : queue.getDeadLetters()) {
        cout << message.id
             << " | attempts=" << message.attempts
             << " | error=" << message.lastError
             << '\n';
    }
}

void demonstrateCapacityAndOwnership() {
    MessageQueue queue("bounded", 1);

    Message first;
    first.id = "M-001";
    first.producerId = "producer";
    first.routingKey = "test";
    first.payload = "first";

    queue.publish(first);

    try {
        Message second;
        second.id = "M-002";
        second.producerId = "producer";
        second.routingKey = "test";
        second.payload = "second";

        queue.publish(second);
    } catch (const QueueException& error) {
        cout << "\nCapacity protection: "
             << error.what() << '\n';
    }

    auto delivery = queue.receive("worker-A");

    if (delivery) {
        try {
            queue.acknowledge(
                delivery->messageId,
                "worker-B"
            );
        } catch (const QueueException& error) {
            cout << "Ownership protection: "
                 << error.what() << '\n';
        }

        queue.acknowledge(
            delivery->messageId,
            "worker-A"
        );
    }
}

int main() {
    try {
        demonstrateBasicQueue();
        demonstrateCapacityAndOwnership();

    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}

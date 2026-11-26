#include <algorithm>
#include <chrono>
#include <cstdint>
#include <deque>
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
#include <vector>

/*
 * Server-Sent Events: Repository-Independent Streaming Engine
 *
 * C++17 implementation of a real-time event distribution system.
 *
 * Demonstrates:
 * - Event domain modeling.
 * - Event identifiers.
 * - Bounded event history.
 * - Replay using Last-Event-ID semantics.
 * - Multiple subscribers.
 * - Named event types.
 * - Subscription filtering.
 * - Client backpressure.
 * - Connection state transitions.
 * - Heartbeat generation.
 * - Delivery tracking.
 *
 * Transport is simulated through an in-memory interface.
 * A production HTTP adapter can use this engine behind an
 * HTTP response implementation.
 */

enum class EventType {
    Message,
    Update,
    Notification,
    Progress,
    Error
};

enum class ClientState {
    Connected,
    Disconnected,
    SlowConsumer
};

enum class PublishResult {
    Published,
    Rejected,
    NoSubscribers
};


std::string toString(EventType type) {
    switch (type) {
        case EventType::Message:
            return "message";
        case EventType::Update:
            return "update";
        case EventType::Notification:
            return "notification";
        case EventType::Progress:
            return "progress";
        case EventType::Error:
            return "error";
    }

    throw std::invalid_argument("Unknown event type");
}


struct SSEEvent {
    std::uint64_t id;
    EventType type;
    std::string data;
    std::chrono::system_clock::time_point timestamp;

    std::string encode() const {
        std::ostringstream output;

        output << "id: " << id << "\n";
        output << "event: " << toString(type) << "\n";
        output << "data: " << data << "\n\n";

        return output.str();
    }
};


struct Client {
    std::string id;
    ClientState state = ClientState::Connected;

    std::set<EventType> subscriptions;

    std::deque<std::string> outgoing;

    std::size_t maxQueueSize = 100;
    std::uint64_t lastDeliveredId = 0;
    std::uint64_t droppedEvents = 0;
};


class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};


class EventHistory {
private:
    std::deque<SSEEvent> events;
    std::size_t capacity;

public:
    explicit EventHistory(std::size_t maxCapacity)
        : capacity(maxCapacity) {

        if (capacity == 0) {
            throw ValidationError("History capacity must be positive");
        }
    }

    void append(const SSEEvent& event) {
        events.push_back(event);

        if (events.size() > capacity) {
            events.pop_front();
        }
    }

    std::vector<SSEEvent> after(
        std::optional<std::uint64_t> cursor
    ) const {

        std::vector<SSEEvent> result;

        if (!cursor.has_value()) {
            result.assign(events.begin(), events.end());
            return result;
        }

        auto found = std::find_if(
            events.begin(),
            events.end(),
            [&](const SSEEvent& event) {
                return event.id == cursor.value();
            }
        );

        if (found == events.end()) {
            return result;
        }

        ++found;

        result.assign(found, events.end());

        return result;
    }

    bool contains(std::uint64_t id) const {
        return std::any_of(
            events.begin(),
            events.end(),
            [&](const SSEEvent& event) {
                return event.id == id;
            }
        );
    }

    std::size_t size() const {
        return events.size();
    }
};


class EventBroker {
private:
    EventHistory history;

    std::unordered_map<std::string, Client> clients;

    std::uint64_t sequence = 0;

    static constexpr std::size_t MAX_PAYLOAD = 64000;

    void deliver(Client& client, const SSEEvent& event) {
        if (client.state != ClientState::Connected) {
            return;
        }

        if (!client.subscriptions.empty() &&
            client.subscriptions.count(event.type) == 0) {
            return;
        }

        if (client.outgoing.size() >= client.maxQueueSize) {
            client.state = ClientState::SlowConsumer;
            client.droppedEvents++;
            return;
        }

        client.outgoing.push_back(event.encode());
    }

public:
    explicit EventBroker(std::size_t historyCapacity = 500)
        : history(historyCapacity) {}

    void connect(
        const std::string& clientId,
        std::size_t maxQueueSize = 100
    ) {

        if (clientId.empty() || clientId.size() > 100) {
            throw ValidationError("Invalid client identifier");
        }

        if (maxQueueSize == 0) {
            throw ValidationError("Queue capacity must be positive");
        }

        if (clients.count(clientId)) {
            throw ValidationError("Client already connected");
        }

        Client client;

        client.id = clientId;
        client.maxQueueSize = maxQueueSize;

        clients.emplace(clientId, std::move(client));
    }

    void subscribe(
        const std::string& clientId,
        EventType type
    ) {

        auto found = clients.find(clientId);

        if (found == clients.end()) {
            throw ValidationError("Client does not exist");
        }

        found->second.subscriptions.insert(type);
    }

    void reconnect(
        const std::string& clientId,
        std::optional<std::uint64_t> lastEventId
    ) {

        connect(clientId);

        if (!lastEventId.has_value()) {
            return;
        }

        auto replayed = history.after(lastEventId);

        for (const auto& event : replayed) {
            auto& client = clients.at(clientId);

            deliver(client, event);

            if (client.state != ClientState::Connected) {
                break;
            }
        }
    }

    SSEEvent publish(EventType type, const std::string& data) {
        if (data.empty()) {
            throw ValidationError("Event payload cannot be empty");
        }

        if (data.size() > MAX_PAYLOAD) {
            throw ValidationError("Event payload exceeds 64 KB");
        }

        if (sequence == UINT64_MAX) {
            throw std::overflow_error("Event sequence exhausted");
        }

        SSEEvent event {
            ++sequence,
            type,
            data,
            std::chrono::system_clock::now()
        };

        history.append(event);

        for (auto& entry : clients) {
            deliver(entry.second, event);
        }

        return event;
    }

    std::vector<std::string> drain(
        const std::string& clientId,
        std::size_t maximum = 100
    ) {

        auto found = clients.find(clientId);

        if (found == clients.end()) {
            throw ValidationError("Unknown client");
        }

        Client& client = found->second;

        std::vector<std::string> result;

        while (
            !client.outgoing.empty() &&
            result.size() < maximum
        ) {
            result.push_back(client.outgoing.front());
            client.outgoing.pop_front();
        }

        return result;
    }

    std::string heartbeat() const {
        return ": heartbeat\n\n";
    }

    void disconnect(const std::string& clientId) {
        clients.erase(clientId);
    }

    std::size_t subscriberCount() const {
        return clients.size();
    }

    std::size_t historySize() const {
        return history.size();
    }

    const Client& getClient(const std::string& clientId) const {
        auto found = clients.find(clientId);

        if (found == clients.end()) {
            throw ValidationError("Unknown client");
        }

        return found->second;
    }
};


class StreamingService {
private:
    EventBroker broker;

public:
    StreamingService()
        : broker(5) {}

    EventBroker& getBroker() {
        return broker;
    }

    SSEEvent publishJobProgress(
        const std::string& jobId,
        int percentage,
        const std::string& status
    ) {

        if (jobId.empty() || jobId.size() > 100) {
            throw ValidationError("Invalid job ID");
        }

        if (percentage < 0 || percentage > 100) {
            throw ValidationError("Invalid progress percentage");
        }

        if (status.empty()) {
            throw ValidationError("Status cannot be empty");
        }

        std::ostringstream json;

        json << "{\"job_id\":\"" << jobId
             << "\",\"progress\":" << percentage
             << ",\"status\":\"" << status << "\"}";

        return broker.publish(EventType::Progress, json.str());
    }
};


int main() {
    try {
        StreamingService service;

        EventBroker& broker = service.getBroker();

        broker.connect("browser-001", 10);
        broker.connect("browser-002", 10);

        broker.subscribe("browser-001", EventType::Progress);
        broker.subscribe("browser-002", EventType::Notification);

        std::cout << "Publishing real-time events\n\n";

        service.publishJobProgress(
            "job-001",
            20,
            "processing"
        );

        service.publishJobProgress(
            "job-001",
            60,
            "processing"
        );

        broker.publish(
            EventType::Notification,
            "{\"message\":\"Deployment started\"}"
        );

        service.publishJobProgress(
            "job-001",
            100,
            "completed"
        );

        std::cout << "Browser 1 received:\n";

        auto firstMessages = broker.drain("browser-001");

        for (const auto& message : firstMessages) {
            std::cout << message;
        }

        std::cout << "\nBrowser 2 received:\n";

        auto secondMessages = broker.drain("browser-002");

        for (const auto& message : secondMessages) {
            std::cout << message;
        }

        std::cout << "\nHeartbeat:\n";
        std::cout << broker.heartbeat();

        std::cout << "\nReconnection demonstration:\n";

        broker.disconnect("browser-001");

        broker.reconnect("browser-001", 1);

        auto replay = broker.drain("browser-001");

        for (const auto& message : replay) {
            std::cout << message;
        }

        std::cout << "\nEngine statistics:\n";

        std::cout << "Subscribers: "
                  << broker.subscriberCount() << "\n";

        std::cout << "Retained events: "
                  << broker.historySize() << "\n";

        std::cout << "\nValidation tests:\n";

        bool rejected = false;

        try {
            service.publishJobProgress(
                "invalid-job",
                150,
                "processing"
            );
        } catch (const ValidationError&) {
            rejected = true;
        }

        if (!rejected) {
            throw std::runtime_error(
                "Invalid progress was not rejected"
            );
        }

        std::cout << "Invalid progress rejected successfully.\n";

        std::cout << "\nAll tests passed.\n";

        /*
         * Complexity:
         * Publish: O(H + C), where H is history insertion overhead
         * and C is the number of connected clients.
         * Replay: O(H).
         * Subscribe filtering: O(log S) with ordered event-type sets.
         * Client queue insertion: O(1).
         *
         * The demonstration is single-threaded. A network service
         * must protect shared state using synchronization and
         * separate slow network writers from event publication.
         */

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: "
                  << error.what() << "\n";

        return 1;
    }

    return 0;
}

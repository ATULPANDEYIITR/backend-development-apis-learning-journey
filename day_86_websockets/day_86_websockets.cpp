#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * WebSocket Connection and Lifecycle Management Engine
 *
 * C++17 repository-independent connection management model.
 *
 * Models:
 * - Persistent connection lifecycle
 * - Client and server identities
 * - HTTP upgrade completion
 * - Message delivery
 * - Ping/pong heartbeat
 * - Connection timeouts
 * - Backpressure
 * - Graceful and abnormal termination
 * - Reconnection and session replacement
 * - Metrics and operational reporting
 *
 * The program models transport state. Actual RFC 6455 socket
 * framing and TLS are intentionally delegated to a transport layer.
 */

using namespace std;
using Clock = chrono::steady_clock;
using TimePoint = Clock::time_point;


enum class ConnectionState {
    CONNECTING,
    OPEN,
    CLOSING,
    CLOSED,
    FAILED
};

enum class FrameType {
    TEXT,
    BINARY,
    PING,
    PONG,
    CLOSE
};

enum class CloseReason {
    NORMAL,
    GOING_AWAY,
    PROTOCOL_ERROR,
    TIMEOUT,
    SERVER_ERROR
};


string toString(ConnectionState state) {
    switch (state) {
        case ConnectionState::CONNECTING: return "CONNECTING";
        case ConnectionState::OPEN: return "OPEN";
        case ConnectionState::CLOSING: return "CLOSING";
        case ConnectionState::CLOSED: return "CLOSED";
        case ConnectionState::FAILED: return "FAILED";
    }

    return "UNKNOWN";
}


struct WebSocketMessage {
    uint64_t sequence;
    FrameType type;
    string payload;
    TimePoint createdAt = Clock::now();
};


struct ConnectionConfig {
    size_t maximumMessageBytes = 1024 * 1024;
    size_t maximumQueuedBytes = 4 * 1024 * 1024;
    chrono::seconds heartbeatInterval{20};
    chrono::seconds idleTimeout{60};
    unsigned maximumMissedHeartbeats = 2;
};


struct ConnectionMetrics {
    uint64_t messagesReceived = 0;
    uint64_t messagesSent = 0;
    uint64_t bytesReceived = 0;
    uint64_t bytesSent = 0;
    uint64_t heartbeatFailures = 0;
    uint64_t rejectedMessages = 0;
    uint64_t reconnections = 0;
};


class WebSocketConnection {

private:

    string connectionId;
    string userId;
    string sessionId;

    ConnectionState state;

    ConnectionConfig config;
    ConnectionMetrics metrics;

    vector<WebSocketMessage> outboundQueue;

    size_t queuedBytes = 0;
    uint64_t nextSequence = 1;

    unsigned missedHeartbeats = 0;

    TimePoint createdAt;
    TimePoint lastActivity;
    TimePoint lastHeartbeat;

    bool authenticated = false;

    void validateTransition(ConnectionState next) const {

        const map<ConnectionState, set<ConnectionState>> allowed = {
            {
                ConnectionState::CONNECTING,
                {
                    ConnectionState::OPEN,
                    ConnectionState::FAILED,
                    ConnectionState::CLOSED
                }
            },
            {
                ConnectionState::OPEN,
                {
                    ConnectionState::CLOSING,
                    ConnectionState::FAILED
                }
            },
            {
                ConnectionState::CLOSING,
                {
                    ConnectionState::CLOSED,
                    ConnectionState::FAILED
                }
            },
            {
                ConnectionState::CLOSED, {}
            },
            {
                ConnectionState::FAILED,
                {
                    ConnectionState::CLOSED
                }
            }
        };

        auto it = allowed.find(state);

        if (
            it == allowed.end() ||
            !it->second.count(next)
        ) {
            throw logic_error(
                "Invalid transition: " +
                toString(state) + " -> " +
                toString(next)
            );
        }
    }

public:

    WebSocketConnection(
        string connectionId,
        string userId,
        string sessionId,
        ConnectionConfig config = {}
    )
        : connectionId(move(connectionId)),
          userId(move(userId)),
          sessionId(move(sessionId)),
          state(ConnectionState::CONNECTING),
          config(config),
          createdAt(Clock::now()),
          lastActivity(createdAt),
          lastHeartbeat(createdAt)
    {

        if (
            this->connectionId.empty() ||
            this->userId.empty() ||
            this->sessionId.empty()
        ) {
            throw invalid_argument(
                "Connection identity fields cannot be empty"
            );
        }

        if (
            config.maximumMessageBytes == 0 ||
            config.maximumQueuedBytes == 0 ||
            config.idleTimeout.count() <= 0 ||
            config.heartbeatInterval.count() <= 0 ||
            config.maximumMissedHeartbeats == 0
        ) {
            throw invalid_argument(
                "Invalid connection configuration"
            );
        }
    }

    void transition(ConnectionState next) {
        validateTransition(next);
        state = next;
    }

    void completeHandshake(bool authenticationValid) {

        if (state != ConnectionState::CONNECTING) {
            throw logic_error(
                "Handshake is only valid while connecting"
            );
        }

        if (!authenticationValid) {
            transition(ConnectionState::FAILED);
            throw runtime_error(
                "Authentication failed"
            );
        }

        authenticated = true;

        transition(ConnectionState::OPEN);

        lastActivity = Clock::now();
    }

    void send(FrameType type, const string& payload) {

        if (state != ConnectionState::OPEN) {
            throw logic_error(
                "Cannot send on a non-open connection"
            );
        }

        if (!authenticated) {
            throw logic_error(
                "Connection is not authenticated"
            );
        }

        if (type == FrameType::CLOSE ||
            type == FrameType::PING ||
            type == FrameType::PONG) {
            throw invalid_argument(
                "Control frames require dedicated operations"
            );
        }

        if (payload.size() > config.maximumMessageBytes) {
            metrics.rejectedMessages++;

            throw length_error(
                "Message exceeds maximum payload size"
            );
        }

        if (
            payload.size() >
            config.maximumQueuedBytes - queuedBytes
        ) {
            metrics.rejectedMessages++;

            throw overflow_error(
                "Outbound queue capacity exceeded"
            );
        }

        outboundQueue.push_back({
            nextSequence++,
            type,
            payload,
            Clock::now()
        });

        queuedBytes += payload.size();
        lastActivity = Clock::now();
    }

    optional<WebSocketMessage> consumeNext() {

        if (outboundQueue.empty()) {
            return nullopt;
        }

        WebSocketMessage message = outboundQueue.front();

        outboundQueue.erase(outboundQueue.begin());

        queuedBytes -= message.payload.size();

        metrics.messagesSent++;
        metrics.bytesSent += message.payload.size();

        return message;
    }

    void receive(FrameType type, const string& payload) {

        if (state != ConnectionState::OPEN) {
            throw logic_error(
                "Cannot receive on a non-open connection"
            );
        }

        if (payload.size() > config.maximumMessageBytes) {
            metrics.rejectedMessages++;

            throw length_error(
                "Incoming message exceeds size limit"
            );
        }

        lastActivity = Clock::now();

        if (
            type == FrameType::PING ||
            type == FrameType::CLOSE
        ) {
            throw invalid_argument(
                "Control frames require dedicated operations"
            );
        }

        if (type == FrameType::PONG) {
            missedHeartbeats = 0;
            metrics.bytesReceived += payload.size();
            return;
        }

        metrics.messagesReceived++;
        metrics.bytesReceived += payload.size();
    }

    void sendHeartbeat() {

        if (state != ConnectionState::OPEN) {
            return;
        }

        if (
            Clock::now() - lastHeartbeat <
            config.heartbeatInterval
        ) {
            return;
        }

        lastHeartbeat = Clock::now();
        missedHeartbeats++;

        if (missedHeartbeats > config.maximumMissedHeartbeats) {
            metrics.heartbeatFailures++;
            fail("Heartbeat threshold exceeded");
        }
    }

    void checkIdleTimeout() {

        if (state != ConnectionState::OPEN) {
            return;
        }

        if (
            Clock::now() - lastActivity >
            config.idleTimeout
        ) {
            fail("Connection idle timeout");
        }
    }

    void acknowledgeHeartbeat() {

        if (state != ConnectionState::OPEN) {
            return;
        }

        missedHeartbeats = 0;
        lastActivity = Clock::now();
    }

    void beginClose() {

        if (state != ConnectionState::OPEN) {
            throw logic_error(
                "Only open connections can begin closing"
            );
        }

        transition(ConnectionState::CLOSING);
    }

    void completeClose() {

        if (
            state != ConnectionState::CLOSING &&
            state != ConnectionState::FAILED
        ) {
            throw logic_error(
                "Connection is not closing"
            );
        }

        outboundQueue.clear();
        queuedBytes = 0;

        transition(ConnectionState::CLOSED);
    }

    void fail(const string& reason) {

        if (
            state == ConnectionState::CLOSED ||
            state == ConnectionState::FAILED
        ) {
            return;
        }

        transition(ConnectionState::FAILED);

        outboundQueue.clear();
        queuedBytes = 0;

        cerr << "Connection failure "
             << connectionId << ": "
             << reason << '\n';
    }

    void recordReconnection() {
        metrics.reconnections++;
    }

    bool isOpen() const {
        return state == ConnectionState::OPEN;
    }

    ConnectionState getState() const {
        return state;
    }

    const string& getId() const {
        return connectionId;
    }

    const string& getUserId() const {
        return userId;
    }

    const string& getSessionId() const {
        return sessionId;
    }

    const ConnectionMetrics& getMetrics() const {
        return metrics;
    }

    size_t getQueuedBytes() const {
        return queuedBytes;
    }

    void report() const {

        cout << "\nConnection: " << connectionId
             << "\nUser: " << userId
             << "\nSession: " << sessionId
             << "\nState: " << toString(state)
             << "\nAuthenticated: "
             << boolalpha << authenticated
             << "\nQueued bytes: " << queuedBytes
             << "\nMessages received: "
             << metrics.messagesReceived
             << "\nMessages sent: "
             << metrics.messagesSent
             << "\nBytes received: "
             << metrics.bytesReceived
             << "\nBytes sent: "
             << metrics.bytesSent
             << "\nRejected messages: "
             << metrics.rejectedMessages
             << "\nHeartbeat failures: "
             << metrics.heartbeatFailures
             << "\nReconnections: "
             << metrics.reconnections
             << '\n';
    }
};


class ConnectionManager {

private:

    map<string, WebSocketConnection> connections;

    map<string, string> activeUserSessions;

public:

    void registerConnection(
        const string& id,
        const string& user,
        const string& session,
        const ConnectionConfig& config = {}
    ) {

        if (connections.count(id)) {
            throw invalid_argument(
                "Duplicate connection identifier"
            );
        }

        connections.emplace(
            piecewise_construct,
            forward_as_tuple(id),
            forward_as_tuple(id, user, session, config)
        );
    }

    void authenticate(const string& id, bool valid) {

        auto it = connections.find(id);

        if (it == connections.end()) {
            throw out_of_range(
                "Connection not found"
            );
        }

        it->second.completeHandshake(valid);

        if (valid) {
            activeUserSessions[it->second.getUserId()] = id;
        }
    }

    void replaceUserSession(
        const string& user,
        const string& newConnectionId
    ) {

        auto it = activeUserSessions.find(user);

        if (it != activeUserSessions.end()) {

            const string oldId = it->second;

            if (oldId != newConnectionId) {

                auto oldConnection = connections.find(oldId);

                if (
                    oldConnection != connections.end() &&
                    oldConnection->second.isOpen()
                ) {
                    oldConnection->second.beginClose();
                    oldConnection->second.completeClose();
                }
            }
        }

        auto next = connections.find(newConnectionId);

        if (
            next == connections.end() ||
            !next->second.isOpen() ||
            next->second.getUserId() != user
        ) {
            throw logic_error(
                "Replacement connection is invalid"
            );
        }

        activeUserSessions[user] = newConnectionId;
    }

    void sendToUser(
        const string& user,
        const string& message
    ) {

        auto session = activeUserSessions.find(user);

        if (session == activeUserSessions.end()) {
            throw runtime_error(
                "User has no active connection"
            );
        }

        connections.at(session->second).send(
            FrameType::TEXT,
            message
        );
    }

    void broadcast(const string& message) {

        for (auto& [id, connection] : connections) {

            if (connection.isOpen()) {
                connection.send(
                    FrameType::TEXT,
                    message
                );
            }
        }
    }

    void close(const string& id) {

        auto it = connections.find(id);

        if (it == connections.end()) {
            return;
        }

        auto& connection = it->second;

        if (connection.isOpen()) {
            connection.beginClose();
        }

        if (
            connection.getState() == ConnectionState::CLOSING ||
            connection.getState() == ConnectionState::FAILED
        ) {
            connection.completeClose();
        }

        auto session = activeUserSessions.find(
            connection.getUserId()
        );

        if (
            session != activeUserSessions.end() &&
            session->second == id
        ) {
            activeUserSessions.erase(session);
        }
    }

    void checkConnections() {

        for (auto& [id, connection] : connections) {
            connection.checkIdleTimeout();
        }
    }

    void report() const {

        cout << "\n========== CONNECTION MANAGER ==========\n";

        cout << "Total registered connections: "
             << connections.size() << '\n';

        cout << "Active user sessions: "
             << activeUserSessions.size() << '\n';

        for (const auto& [id, connection] : connections) {
            connection.report();
        }
    }

    WebSocketConnection& get(const string& id) {
        return connections.at(id);
    }
};


int main() {

    try {

        ConnectionManager manager;

        cout << "WebSocket Lifecycle Management Engine\n";

        // Two clients establish independent persistent connections.
        manager.registerConnection(
            "conn-1001",
            "user-alice",
            "session-a"
        );

        manager.registerConnection(
            "conn-1002",
            "user-bob",
            "session-b"
        );

        manager.authenticate("conn-1001", true);
        manager.authenticate("conn-1002", true);

        // Application messages are queued independently of TCP delivery.
        manager.sendToUser(
            "user-alice",
            "Real-time notification: deployment completed"
        );

        manager.sendToUser(
            "user-bob",
            "Real-time notification: new message received"
        );

        manager.broadcast(
            "System maintenance scheduled"
        );

        cout << "\nConsuming outbound messages:\n";

        for (const string id : {"conn-1001", "conn-1002"}) {

            auto& connection = manager.get(id);

            while (true) {

                auto message = connection.consumeNext();

                if (!message.has_value()) {
                    break;
                }

                cout << id
                     << " | Sequence: " << message->sequence
                     << " | Payload: " << message->payload
                     << '\n';
            }
        }

        // A valid pong resets missed-heartbeat tracking.
        manager.get("conn-1001").receive(
            FrameType::PONG,
            "heartbeat-1"
        );

        manager.get("conn-1001").acknowledgeHeartbeat();

        // A failed authentication must never produce an open session.
        manager.registerConnection(
            "conn-1003",
            "user-charlie",
            "session-c"
        );

        try {
            manager.authenticate("conn-1003", false);
        }
        catch (const exception& error) {
            cout << "\nExpected authentication rejection: "
                 << error.what() << '\n';

            manager.get("conn-1003").completeClose();
        }

        // Session replacement prevents an old connection from remaining
        // the active session for the same user.
        manager.registerConnection(
            "conn-1004",
            "user-alice",
            "session-a2"
        );

        manager.authenticate("conn-1004", true);

        manager.get("conn-1004").recordReconnection();

        manager.replaceUserSession(
            "user-alice",
            "conn-1004"
        );

        cout << "\nAfter session replacement:\n";

        manager.report();

        // Explicit graceful shutdown.
        manager.close("conn-1001");
        manager.close("conn-1002");
        manager.close("conn-1004");

        cout << "\nAfter graceful shutdown:\n";

        manager.report();

    }
    catch (const exception& error) {

        cerr << "Fatal error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

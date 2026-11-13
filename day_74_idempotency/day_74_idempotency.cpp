#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class PaymentStatus {
    PROCESSING,
    SUCCEEDED,
    FAILED,
    UNKNOWN
};

enum class Decision {
    CREATED,
    REPLAYED,
    REJECTED,
    IN_PROGRESS
};

string statusName(PaymentStatus status) {
    switch (status) {
        case PaymentStatus::PROCESSING: return "PROCESSING";
        case PaymentStatus::SUCCEEDED: return "SUCCEEDED";
        case PaymentStatus::FAILED: return "FAILED";
        case PaymentStatus::UNKNOWN: return "UNKNOWN";
    }
    return "INVALID";
}

struct PaymentRequest {
    string customerId;
    int64_t amount;
    string currency;
    string paymentMethod;
};

struct Payment {
    string id;
    PaymentRequest request;
    PaymentStatus status;
    string providerReference;
    string failureReason;
};

struct IdempotencyRecord {
    string fingerprint;
    string paymentId;
    PaymentStatus status;
    string cachedResponse;
    chrono::system_clock::time_point expiresAt;
};

struct OperationResult {
    Decision decision;
    string paymentId;
    string response;
};

class PaymentGateway {
public:
    bool charge(const PaymentRequest& request, string& reference) {
        // Deterministic simulated provider behavior.
        if (request.paymentMethod == "DECLINED") {
            return false;
        }

        reference = "GW-" + to_string(++sequence);
        return true;
    }

private:
    uint64_t sequence = 1000;
};

class GovernanceEngine {
public:
    explicit GovernanceEngine(int retentionSeconds = 86400)
        : retentionSeconds(retentionSeconds) {

        if (retentionSeconds <= 0) {
            throw invalid_argument("Retention must be positive.");
        }
    }

    OperationResult execute(
        const string& key,
        const PaymentRequest& request
    ) {
        validateKey(key);
        validateRequest(request);

        const string hash = fingerprint(request);
        const auto now = chrono::system_clock::now();

        auto existing = registry.find(key);

        if (existing != registry.end()) {
            const IdempotencyRecord& record = existing->second;

            if (record.fingerprint != hash) {
                throw runtime_error(
                    "409: Idempotency key payload conflict."
                );
            }

            if (record.expiresAt <= now) {
                throw runtime_error(
                    "409: Expired key requires reconciliation."
                );
            }

            if (record.status == PaymentStatus::PROCESSING ||
                record.status == PaymentStatus::UNKNOWN) {

                return {
                    Decision::IN_PROGRESS,
                    record.paymentId,
                    "Payment operation is unresolved."
                };
            }

            return {
                Decision::REPLAYED,
                record.paymentId,
                record.cachedResponse
            };
        }

        const string paymentId = generatePaymentId();

        // Reserve key and create payment before external execution.
        Payment payment{
            paymentId,
            request,
            PaymentStatus::PROCESSING,
            "",
            ""
        };

        payments.emplace(paymentId, payment);

        IdempotencyRecord record{
            hash,
            paymentId,
            PaymentStatus::PROCESSING,
            "",
            now + chrono::seconds(retentionSeconds)
        };

        registry.emplace(key, record);

        audit.push_back("RESERVED:" + paymentId);

        return process(key, paymentId);
    }

    OperationResult reconcile(
        const string& key,
        bool providerConfirmedSuccess,
        const string& providerReference
    ) {
        auto it = registry.find(key);

        if (it == registry.end()) {
            throw runtime_error("Idempotency record not found.");
        }

        auto& record = it->second;

        if (record.status != PaymentStatus::UNKNOWN &&
            record.status != PaymentStatus::PROCESSING) {
            throw runtime_error("Payment does not require reconciliation.");
        }

        auto& payment = payments.at(record.paymentId);

        if (providerConfirmedSuccess) {
            payment.status = PaymentStatus::SUCCEEDED;
            payment.providerReference = providerReference;
            record.status = PaymentStatus::SUCCEEDED;
            record.cachedResponse = "PAYMENT_SUCCEEDED";

        } else {
            payment.status = PaymentStatus::FAILED;
            payment.failureReason = "Provider confirmed no charge.";
            record.status = PaymentStatus::FAILED;
            record.cachedResponse = "PAYMENT_FAILED";
        }

        audit.push_back("RECONCILED:" + payment.id);

        return {
            Decision::CREATED,
            payment.id,
            record.cachedResponse
        };
    }

    void simulateUnknown(const string& key) {
        auto it = registry.find(key);

        if (it == registry.end()) {
            throw runtime_error("Key not found.");
        }

        auto& record = it->second;
        auto& payment = payments.at(record.paymentId);

        if (record.status != PaymentStatus::PROCESSING) {
            throw runtime_error("Payment is not processing.");
        }

        // Models a lost response where provider execution is uncertain.
        record.status = PaymentStatus::UNKNOWN;
        payment.status = PaymentStatus::UNKNOWN;

        audit.push_back("UNKNOWN:" + payment.id);
    }

    void report() const {
        map<PaymentStatus, int> counts;

        for (const auto& entry : payments) {
            counts[entry.second.status]++;
        }

        cout << "\nPayment state report\n";

        for (const auto& entry : counts) {
            cout << statusName(entry.first)
                 << ": " << entry.second << '\n';
        }

        cout << "\nAudit events\n";

        for (const auto& event : audit) {
            cout << event << '\n';
        }
    }

    size_t cleanup() {
        const auto now = chrono::system_clock::now();
        size_t removed = 0;

        for (auto it = registry.begin(); it != registry.end();) {
            if (
                it->second.expiresAt <= now &&
                it->second.status != PaymentStatus::PROCESSING &&
                it->second.status != PaymentStatus::UNKNOWN
            ) {
                it = registry.erase(it);
                ++removed;
            } else {
                ++it;
            }
        }

        return removed;
    }

private:
    int retentionSeconds;

    unordered_map<string, IdempotencyRecord> registry;
    unordered_map<string, Payment> payments;
    vector<string> audit;

    PaymentGateway gateway;

    static void validateKey(const string& key) {
        static const regex pattern("^[A-Za-z0-9_-]{16,128}$");

        if (!regex_match(key, pattern)) {
            throw invalid_argument("Invalid idempotency key.");
        }
    }

    static void validateRequest(const PaymentRequest& request) {
        if (request.customerId.empty()) {
            throw invalid_argument("Customer ID is required.");
        }

        if (request.amount <= 0 || request.amount > 100000000) {
            throw invalid_argument("Invalid payment amount.");
        }

        if (!regex_match(request.currency, regex("^[A-Z]{3}$"))) {
            throw invalid_argument("Invalid currency.");
        }

        if (request.paymentMethod.empty()) {
            throw invalid_argument("Payment method is required.");
        }
    }

    static string fingerprint(const PaymentRequest& request) {
        // Length-prefixing avoids ambiguous concatenation.
        ostringstream canonical;

        auto append = [&](const string& value) {
            canonical << value.size() << ':' << value << '|';
        };

        append(request.customerId);
        append(to_string(request.amount));
        append(request.currency);
        append(request.paymentMethod);

        // Demonstration hash only. Production systems should use
        // a cryptographic hash such as SHA-256.
        hash<string> hasher;

        return to_string(hasher(canonical.str()));
    }

    static string generatePaymentId() {
        static uint64_t sequence = 100000;
        return "PAY-" + to_string(++sequence);
    }

    OperationResult process(
        const string& key,
        const string& paymentId
    ) {
        auto& payment = payments.at(paymentId);
        auto& record = registry.at(key);

        string providerReference;

        try {
            const bool approved = gateway.charge(
                payment.request,
                providerReference
            );

            if (!approved) {
                payment.status = PaymentStatus::FAILED;
                payment.failureReason = "Gateway declined payment.";

                record.status = PaymentStatus::FAILED;
                record.cachedResponse = "PAYMENT_FAILED";

                audit.push_back("FAILED:" + paymentId);

                return {
                    Decision::CREATED,
                    paymentId,
                    record.cachedResponse
                };
            }

            payment.status = PaymentStatus::SUCCEEDED;
            payment.providerReference = providerReference;

            record.status = PaymentStatus::SUCCEEDED;
            record.cachedResponse = "PAYMENT_SUCCEEDED";

            audit.push_back("SUCCEEDED:" + paymentId);

            return {
                Decision::CREATED,
                paymentId,
                record.cachedResponse
            };

        } catch (const exception& error) {
            // Preserve uncertainty instead of blindly retrying
            // an external payment operation.
            payment.status = PaymentStatus::UNKNOWN;
            payment.failureReason = error.what();
            record.status = PaymentStatus::UNKNOWN;

            audit.push_back("UNKNOWN:" + paymentId);

            return {
                Decision::IN_PROGRESS,
                paymentId,
                "Reconciliation required."
            };
        }
    }
};

void runTests() {
    GovernanceEngine engine;

    PaymentRequest request{
        "CUSTOMER-3001",
        45000,
        "INR",
        "CARD-TOKEN-3001"
    };

    const string key = "payment_request_300001";

    auto first = engine.execute(key, request);

    if (first.decision != Decision::CREATED) {
        throw runtime_error("Initial request failed.");
    }

    auto second = engine.execute(key, request);

    if (
        second.decision != Decision::REPLAYED ||
        second.paymentId != first.paymentId
    ) {
        throw runtime_error("Idempotency replay failed.");
    }

    PaymentRequest modified = request;
    modified.amount = 90000;

    try {
        engine.execute(key, modified);
        throw runtime_error("Expected payload conflict.");
    } catch (const runtime_error& error) {
        if (string(error.what()).find("409:") == string::npos) {
            throw;
        }
    }

    PaymentRequest declined{
        "CUSTOMER-3002",
        20000,
        "INR",
        "DECLINED"
    };

    auto failure = engine.execute(
        "payment_request_300002",
        declined
    );

    if (failure.response != "PAYMENT_FAILED") {
        throw runtime_error("Failure handling test failed.");
    }

    // Demonstrate uncertain payment outcome and reconciliation.
    auto pending = engine.execute(
        "payment_request_300003",
        request
    );

    engine.simulateUnknown("payment_request_300003");

    auto reconciled = engine.reconcile(
        "payment_request_300003",
        true,
        "GW-RECONCILED-100"
    );

    if (reconciled.response != "PAYMENT_SUCCEEDED") {
        throw runtime_error("Reconciliation failed.");
    }

    cout << "All governance engine tests passed.\n";

    engine.report();
}

int main() {
    try {
        runTests();
        return 0;
    } catch (const exception& error) {
        cerr << "Application error: " << error.what() << '\n';
        return 1;
    }
}

#include <algorithm>
#include <chrono>
#include <cctype>
#include <ctime>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Secure Secrets Management
 * C++17
 *
 * Scenario:
 * A payment platform manages database and payment-provider
 * credentials using versioned secrets, role-based permissions,
 * controlled rotation, and revocation.
 *
 * Compile:
 * g++ -std=c++17 -Wall -Wextra -pedantic secure_secrets.cpp -o secure_secrets
 */

using namespace std;

// ============================================================
// 1. Domain model
// ============================================================

enum class SecretState {
    ACTIVE,
    STAGED,
    RETIRED,
    REVOKED
};

enum class Operation {
    READ,
    CREATE,
    ROTATE,
    REVOKE,
    METADATA
};

string stateName(SecretState state) {
    switch (state) {
        case SecretState::ACTIVE: return "ACTIVE";
        case SecretState::STAGED: return "STAGED";
        case SecretState::RETIRED: return "RETIRED";
        case SecretState::REVOKED: return "REVOKED";
    }

    throw logic_error("Unknown secret state.");
}

string operationName(Operation operation) {
    switch (operation) {
        case Operation::READ: return "READ";
        case Operation::CREATE: return "CREATE";
        case Operation::ROTATE: return "ROTATE";
        case Operation::REVOKE: return "REVOKE";
        case Operation::METADATA: return "METADATA";
    }

    throw logic_error("Unknown operation.");
}

class SecretError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class AccessDenied : public SecretError {
public:
    using SecretError::SecretError;
};

class ValidationError : public SecretError {
public:
    using SecretError::SecretError;
};

class StateError : public SecretError {
public:
    using SecretError::SecretError;
};

class NotFound : public SecretError {
public:
    using SecretError::SecretError;
};

// ============================================================
// 2. Secret metadata and versions
// ============================================================

struct SecretMetadata {
    string name;
    int version;
    SecretState state;
    time_t createdAt;
    optional<time_t> expiresAt;
};

struct SecretVersion {
    SecretMetadata metadata;

    // Do not include secret contents in debugging output.
    string value;
};

struct AuditEvent {
    time_t timestamp;
    string actor;
    Operation operation;
    string secretName;
    int version;
    string outcome;
};

// ============================================================
// 3. Utility functions
// ============================================================

time_t currentTime() {
    return chrono::system_clock::to_time_t(
        chrono::system_clock::now()
    );
}

void validateName(const string& name) {
    if (name.empty() || name.size() > 128) {
        throw ValidationError("Invalid secret name.");
    }

    for (unsigned char c : name) {
        if (
            !isalnum(c) &&
            c != '_' &&
            c != '-' &&
            c != '.'
        ) {
            throw ValidationError(
                "Secret name contains invalid characters."
            );
        }
    }
}

void validateValue(const string& value) {
    if (value.size() < 16 || value.size() > 8192) {
        throw ValidationError(
            "Secret must contain between 16 and 8192 characters."
        );
    }
}

string generateSecret(size_t length = 48) {
    if (length < 32 || length > 256) {
        throw ValidationError("Invalid secret length.");
    }

    static const string alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789-_!@#$%";

    random_device device;
    mt19937_64 generator(device());
    uniform_int_distribution<size_t> distribution(
        0, alphabet.size() - 1
    );

    string result;
    result.reserve(length);

    for (size_t i = 0; i < length; ++i) {
        result.push_back(alphabet[distribution(generator)]);
    }

    return result;
}

string stateToString(SecretState state) {
    return stateName(state);
}

// ============================================================
// 4. Role-based access-control engine
// ============================================================

class AccessControl {
private:
    map<string, set<Operation>> permissions;

public:
    AccessControl() {
        permissions["application"] = {
            Operation::READ
        };

        permissions["security-admin"] = {
            Operation::READ,
            Operation::CREATE,
            Operation::ROTATE,
            Operation::REVOKE,
            Operation::METADATA
        };

        permissions["rotation-service"] = {
            Operation::READ,
            Operation::CREATE,
            Operation::ROTATE
        };

        permissions["auditor"] = {
            Operation::METADATA
        };
    }

    void authorize(
        const string& actor,
        Operation operation
    ) const {
        auto iterator = permissions.find(actor);

        if (
            iterator == permissions.end() ||
            iterator->second.find(operation) ==
                iterator->second.end()
        ) {
            throw AccessDenied(
                "Actor is not authorized for operation."
            );
        }
    }
};

// ============================================================
// 5. Secret manager
// ============================================================

class SecretManager {
private:
    map<string, vector<SecretVersion>> secrets;
    vector<AuditEvent> audit;
    AccessControl access;

    void record(
        const string& actor,
        Operation operation,
        const string& name,
        int version,
        const string& outcome
    ) {
        audit.push_back({
            currentTime(),
            actor,
            operation,
            name,
            version,
            outcome
        });
    }

    vector<SecretVersion>& getVersions(
        const string& name
    ) {
        auto iterator = secrets.find(name);

        if (iterator == secrets.end()) {
            throw NotFound("Secret does not exist.");
        }

        return iterator->second;
    }

    const SecretVersion* findState(
        const vector<SecretVersion>& versions,
        SecretState state
    ) const {
        auto iterator = find_if(
            versions.rbegin(),
            versions.rend(),
            [state](const SecretVersion& version) {
                return version.metadata.state == state;
            }
        );

        return iterator == versions.rend()
            ? nullptr
            : &(*iterator);
    }

public:

    // --------------------------------------------------------
    // Create a new secret
    // --------------------------------------------------------

    SecretMetadata create(
        const string& name,
        const string& value,
        const string& actor,
        optional<int> expiryDays = nullopt
    ) {
        access.authorize(actor, Operation::CREATE);

        validateName(name);
        validateValue(value);

        if (secrets.count(name)) {
            throw StateError("Secret already exists.");
        }

        if (expiryDays && *expiryDays <= 0) {
            throw ValidationError("Expiry must be positive.");
        }

        time_t now = currentTime();

        optional<time_t> expiry = nullopt;

        if (expiryDays) {
            expiry = now + (*expiryDays * 86400);
        }

        SecretMetadata metadata{
            name,
            1,
            SecretState::ACTIVE,
            now,
            expiry
        };

        secrets[name].push_back({
            metadata,
            value
        });

        record(
            actor,
            Operation::CREATE,
            name,
            1,
            "SUCCESS"
        );

        return metadata;
    }

    // --------------------------------------------------------
    // Read active secret
    // --------------------------------------------------------

    string getSecret(
        const string& name,
        const string& actor
    ) {
        access.authorize(actor, Operation::READ);

        const auto& versions = getVersions(name);

        const SecretVersion* active = findState(
            versions,
            SecretState::ACTIVE
        );

        if (!active) {
            throw StateError("No active secret version.");
        }

        if (
            active->metadata.expiresAt &&
            currentTime() >= *active->metadata.expiresAt
        ) {
            throw StateError("Secret has expired.");
        }

        record(
            actor,
            Operation::READ,
            name,
            active->metadata.version,
            "SUCCESS"
        );

        return active->value;
    }

    // --------------------------------------------------------
    // Stage a replacement credential
    // --------------------------------------------------------

    SecretMetadata stageRotation(
        const string& name,
        const string& value,
        const string& actor
    ) {
        access.authorize(actor, Operation::ROTATE);

        validateName(name);
        validateValue(value);

        auto& versions = getVersions(name);

        bool stagedExists = any_of(
            versions.begin(),
            versions.end(),
            [](const SecretVersion& version) {
                return version.metadata.state ==
                    SecretState::STAGED;
            }
        );

        if (stagedExists) {
            throw StateError(
                "A rotation is already staged."
            );
        }

        const SecretVersion* active = findState(
            versions,
            SecretState::ACTIVE
        );

        if (!active) {
            throw StateError("No active version.");
        }

        if (active->value == value) {
            throw ValidationError(
                "Replacement must differ from active secret."
            );
        }

        int nextVersion = 1;

        for (const auto& version : versions) {
            nextVersion = max(
                nextVersion,
                version.metadata.version + 1
            );
        }

        SecretMetadata metadata{
            name,
            nextVersion,
            SecretState::STAGED,
            currentTime(),
            nullopt
        };

        versions.push_back({
            metadata,
            value
        });

        record(
            actor,
            Operation::ROTATE,
            name,
            nextVersion,
            "STAGED"
        );

        return metadata;
    }

    // --------------------------------------------------------
    // Activate staged credential
    // --------------------------------------------------------

    SecretMetadata activateRotation(
        const string& name,
        const string& actor
    ) {
        access.authorize(actor, Operation::ROTATE);

        auto& versions = getVersions(name);

        auto staged = find_if(
            versions.begin(),
            versions.end(),
            [](const SecretVersion& version) {
                return version.metadata.state ==
                    SecretState::STAGED;
            }
        );

        if (staged == versions.end()) {
            throw StateError("No staged version.");
        }

        auto active = find_if(
            versions.begin(),
            versions.end(),
            [](const SecretVersion& version) {
                return version.metadata.state ==
                    SecretState::ACTIVE;
            }
        );

        if (active != versions.end()) {
            active->metadata.state = SecretState::RETIRED;
        }

        staged->metadata.state = SecretState::ACTIVE;

        record(
            actor,
            Operation::ROTATE,
            name,
            staged->metadata.version,
            "ACTIVATED"
        );

        return staged->metadata;
    }

    // --------------------------------------------------------
    // Revoke a retired or staged credential
    // --------------------------------------------------------

    void revoke(
        const string& name,
        int versionNumber,
        const string& actor
    ) {
        access.authorize(actor, Operation::REVOKE);

        auto& versions = getVersions(name);

        auto target = find_if(
            versions.begin(),
            versions.end(),
            [versionNumber](const SecretVersion& version) {
                return version.metadata.version == versionNumber;
            }
        );

        if (target == versions.end()) {
            throw NotFound("Secret version not found.");
        }

        if (
            target->metadata.state == SecretState::ACTIVE
        ) {
            throw StateError(
                "Cannot revoke the active credential."
            );
        }

        if (
            target->metadata.state == SecretState::REVOKED
        ) {
            throw StateError("Credential already revoked.");
        }

        // Standard strings do not guarantee secure erasure.
        // Production systems require protected memory handling.
        fill(
            target->value.begin(),
            target->value.end(),
            '\0'
        );

        target->value.clear();
        target->metadata.state = SecretState::REVOKED;

        record(
            actor,
            Operation::REVOKE,
            name,
            versionNumber,
            "SUCCESS"
        );
    }

    // --------------------------------------------------------
    // Metadata-only access
    // --------------------------------------------------------

    vector<SecretMetadata> getMetadata(
        const string& name,
        const string& actor
    ) const {
        access.authorize(actor, Operation::METADATA);

        auto iterator = secrets.find(name);

        if (iterator == secrets.end()) {
            throw NotFound("Secret not found.");
        }

        vector<SecretMetadata> result;

        for (const auto& version : iterator->second) {
            result.push_back(version.metadata);
        }

        return result;
    }

    size_t auditCount() const {
        return audit.size();
    }
};

// ============================================================
// 6. Credential rotation coordinator
// ============================================================

class RotationCoordinator {
private:
    SecretManager& manager;

    // Represents verification against the actual downstream service.
    function<bool(const string&)> verifier;

public:
    RotationCoordinator(
        SecretManager& manager,
        function<bool(const string&)> verifier
    )
        : manager(manager),
          verifier(move(verifier)) {}

    SecretMetadata rotate(
        const string& name,
        const string& actor
    ) {
        string replacement = generateSecret();

        SecretMetadata staged = manager.stageRotation(
            name,
            replacement,
            actor
        );

        if (!verifier(replacement)) {
            // The old version remains active.
            // The failed staged version requires explicit cleanup.
            throw StateError(
                "Downstream credential verification failed."
            );
        }

        return manager.activateRotation(name, actor);
    }
};

// ============================================================
// 7. Demonstration
// ============================================================

int main() {
    try {
        cout << "SECURE SECRETS MANAGEMENT\n";
        cout << string(45, '=') << "\n";

        SecretManager manager;

        string initial = generateSecret();

        manager.create(
            "database-password",
            initial,
            "security-admin",
            90
        );

        string retrieved = manager.getSecret(
            "database-password",
            "application"
        );

        if (retrieved != initial) {
            throw StateError("Credential retrieval mismatch.");
        }

        cout << "Initial credential created and retrieved.\n";

        // Test access-control enforcement.
        try {
            manager.getSecret(
                "database-password",
                "auditor"
            );

            throw logic_error(
                "Unauthorized access was not rejected."
            );
        } catch (const AccessDenied&) {
            cout << "Unauthorized access correctly rejected.\n";
        }

        RotationCoordinator coordinator(
            manager,
            [](const string& candidate) {
                return candidate.size() >= 32;
            }
        );

        SecretMetadata activated = coordinator.rotate(
            "database-password",
            "security-admin"
        );

        cout << "Rotation activated: version "
             << activated.version << "\n";

        string current = manager.getSecret(
            "database-password",
            "application"
        );

        if (current == initial) {
            throw StateError("Rotation did not change credential.");
        }

        // Revoke old version only after activation.
        manager.revoke(
            "database-password",
            1,
            "security-admin"
        );

        cout << "Previous version revoked.\n";

        auto metadata = manager.getMetadata(
            "database-password",
            "auditor"
        );

        cout << "\nVERSION REPORT\n";

        for (const auto& item : metadata) {
            cout << "Version " << item.version
                 << " | State: "
                 << stateToString(item.state)
                 << "\n";
        }

        cout << "\nAudit events: "
             << manager.auditCount() << "\n";

        // Active version cannot be revoked.
        try {
            manager.revoke(
                "database-password",
                activated.version,
                "security-admin"
            );

            throw logic_error(
                "Active credential revocation was not rejected."
            );
        } catch (const StateError&) {
            cout << "Active-version revocation correctly rejected.\n";
        }

        // Invalid secret must be rejected.
        try {
            manager.create(
                "weak-secret",
                "short",
                "security-admin"
            );

            throw logic_error(
                "Weak credential was accepted."
            );
        } catch (const ValidationError&) {
            cout << "Weak credential correctly rejected.\n";
        }

        cout << "\nAll security checks passed.\n";

        return 0;

    } catch (const exception& error) {
        // Never print secret values or credential contents.
        cerr << "Management failure: "
             << error.what() << "\n";

        return 1;
    }
}

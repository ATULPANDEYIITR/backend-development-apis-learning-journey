#include <algorithm>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class TLSVersion {
    TLS12,
    TLS13
};

enum class CertificateStatus {
    VALID,
    EXPIRING,
    EXPIRED,
    INVALID
};

enum class TerminationMode {
    EDGE,
    REVERSE_PROXY,
    PASSTHROUGH
};

enum class HandshakeState {
    NEW_CONNECTION,
    CLIENT_HELLO_SENT,
    SERVER_HELLO_RECEIVED,
    CERTIFICATE_RECEIVED,
    CERTIFICATE_VERIFIED,
    KEY_ESTABLISHED,
    SECURE,
    FAILED
};

string toString(TLSVersion version) {
    return version == TLSVersion::TLS13
        ? "TLS 1.3"
        : "TLS 1.2";
}

string toString(CertificateStatus status) {
    switch (status) {
        case CertificateStatus::VALID:
            return "VALID";
        case CertificateStatus::EXPIRING:
            return "EXPIRING";
        case CertificateStatus::EXPIRED:
            return "EXPIRED";
        case CertificateStatus::INVALID:
            return "INVALID";
    }

    return "UNKNOWN";
}

string toString(HandshakeState state) {
    static const map<HandshakeState, string> names = {
        {HandshakeState::NEW_CONNECTION, "NEW_CONNECTION"},
        {HandshakeState::CLIENT_HELLO_SENT, "CLIENT_HELLO_SENT"},
        {HandshakeState::SERVER_HELLO_RECEIVED, "SERVER_HELLO_RECEIVED"},
        {HandshakeState::CERTIFICATE_RECEIVED, "CERTIFICATE_RECEIVED"},
        {HandshakeState::CERTIFICATE_VERIFIED, "CERTIFICATE_VERIFIED"},
        {HandshakeState::KEY_ESTABLISHED, "KEY_ESTABLISHED"},
        {HandshakeState::SECURE, "SECURE"},
        {HandshakeState::FAILED, "FAILED"}
    };

    return names.at(state);
}

struct Certificate {
    string commonName;
    string issuer;
    vector<string> subjectAlternativeNames;
    int daysRemaining;
    bool signatureValid;
    bool trustedIssuer;

    CertificateStatus evaluate(int warningDays = 30) const {
        if (warningDays < 0) {
            throw invalid_argument(
                "Warning period cannot be negative"
            );
        }

        if (!signatureValid || !trustedIssuer) {
            return CertificateStatus::INVALID;
        }

        if (daysRemaining < 0) {
            return CertificateStatus::EXPIRED;
        }

        if (daysRemaining <= warningDays) {
            return CertificateStatus::EXPIRING;
        }

        return CertificateStatus::VALID;
    }

    bool matchesHostname(const string& hostname) const {
        // Simplified exact SAN matching for this policy model.
        // Production hostname matching must implement RFC 6125
        // wildcard and IP-address matching rules.
        return find(
            subjectAlternativeNames.begin(),
            subjectAlternativeNames.end(),
            hostname
        ) != subjectAlternativeNames.end();
    }
};

struct TLSConfiguration {
    string hostname;
    int port = 443;
    TLSVersion minimumVersion = TLSVersion::TLS12;
    int timeoutSeconds = 5;
    bool certificateVerification = true;
    bool hostnameVerification = true;

    void validate() const {
        if (hostname.empty()) {
            throw invalid_argument("Hostname is required");
        }

        if (port < 1 || port > 65535) {
            throw invalid_argument("Invalid TCP port");
        }

        if (timeoutSeconds <= 0) {
            throw invalid_argument(
                "Timeout must be positive"
            );
        }

        if (
            hostnameVerification &&
            !certificateVerification
        ) {
            throw invalid_argument(
                "Hostname verification requires certificate verification"
            );
        }
    }
};

class HandshakeSimulator {
private:
    HandshakeState state =
        HandshakeState::NEW_CONNECTION;

    vector<HandshakeState> history;

    void transition(HandshakeState next) {
        if (state == HandshakeState::FAILED ||
            state == HandshakeState::SECURE) {
            throw logic_error(
                "Handshake is already terminal"
            );
        }

        history.push_back(next);
        state = next;
    }

public:
    HandshakeState getState() const {
        return state;
    }

    const vector<HandshakeState>& getHistory() const {
        return history;
    }

    bool execute(
        const TLSConfiguration& configuration,
        const Certificate& certificate,
        TLSVersion serverVersion,
        const set<string>& supportedCipherSuites
    ) {
        configuration.validate();

        try {
            transition(
                HandshakeState::CLIENT_HELLO_SENT
            );

            // ClientHello advertises protocol versions and
            // supported cipher suites.

            if (
                static_cast<int>(serverVersion) <
                static_cast<int>(configuration.minimumVersion)
            ) {
                throw runtime_error(
                    "Server TLS version is below policy minimum"
                );
            }

            if (supportedCipherSuites.empty()) {
                throw runtime_error(
                    "No common cipher suite available"
                );
            }

            transition(
                HandshakeState::SERVER_HELLO_RECEIVED
            );

            transition(
                HandshakeState::CERTIFICATE_RECEIVED
            );

            const CertificateStatus status =
                certificate.evaluate();

            if (
                configuration.certificateVerification &&
                status != CertificateStatus::VALID &&
                status != CertificateStatus::EXPIRING
            ) {
                throw runtime_error(
                    "Certificate is expired or untrusted"
                );
            }

            if (
                configuration.hostnameVerification &&
                !certificate.matchesHostname(
                    configuration.hostname
                )
            ) {
                throw runtime_error(
                    "Certificate hostname mismatch"
                );
            }

            transition(
                HandshakeState::CERTIFICATE_VERIFIED
            );

            // The actual TLS protocol performs authenticated
            // ephemeral key exchange and derives traffic keys.
            // This model records that protocol stage only.

            transition(
                HandshakeState::KEY_ESTABLISHED
            );

            transition(
                HandshakeState::SECURE
            );

            return true;

        } catch (const exception& error) {
            state = HandshakeState::FAILED;
            history.push_back(state);

            cerr << "Handshake failed: "
                 << error.what() << '\n';

            return false;
        }
    }

    void printHistory() const {
        for (const auto& item : history) {
            cout << "  -> " << toString(item) << '\n';
        }
    }
};

struct TerminationPolicy {
    TerminationMode mode;
    bool frontendTLS = true;
    bool backendTLS = true;
    bool backendCertificateVerification = true;
    bool secureCookies = true;
    bool trustedForwardedHeaders = true;

    vector<string> evaluate() const {
        vector<string> violations;

        if (!frontendTLS) {
            violations.push_back(
                "Public traffic does not enforce HTTPS"
            );
        }

        if (!secureCookies) {
            violations.push_back(
                "Secure cookie attribute is missing"
            );
        }

        if (
            mode == TerminationMode::EDGE ||
            mode == TerminationMode::REVERSE_PROXY
        ) {
            if (!backendTLS) {
                violations.push_back(
                    "Proxy-to-backend communication is unencrypted"
                );
            }

            if (
                backendTLS &&
                !backendCertificateVerification
            ) {
                violations.push_back(
                    "Backend certificate is not verified"
                );
            }

            if (!trustedForwardedHeaders) {
                violations.push_back(
                    "Forwarded protocol metadata is not trusted"
                );
            }
        }

        return violations;
    }
};

struct Endpoint {
    string hostname;
    int port;
    TLSVersion serverVersion;
    Certificate certificate;
    set<string> cipherSuites;
};

class SecurityAudit {
private:
    vector<Endpoint> endpoints;

public:
    void addEndpoint(const Endpoint& endpoint) {
        if (endpoint.hostname.empty()) {
            throw invalid_argument(
                "Endpoint hostname cannot be empty"
            );
        }

        if (endpoint.port < 1 || endpoint.port > 65535) {
            throw invalid_argument(
                "Invalid endpoint port"
            );
        }

        auto duplicate = find_if(
            endpoints.begin(),
            endpoints.end(),
            [&](const Endpoint& existing) {
                return existing.hostname == endpoint.hostname &&
                       existing.port == endpoint.port;
            }
        );

        if (duplicate != endpoints.end()) {
            throw invalid_argument(
                "Duplicate endpoint"
            );
        }

        endpoints.push_back(endpoint);
    }

    void run() const {
        int successful = 0;
        int failed = 0;

        for (const auto& endpoint : endpoints) {
            cout << "\nEndpoint: "
                 << endpoint.hostname
                 << ":" << endpoint.port << '\n';

            TLSConfiguration configuration;
            configuration.hostname = endpoint.hostname;
            configuration.port = endpoint.port;

            HandshakeSimulator simulator;

            const bool result = simulator.execute(
                configuration,
                endpoint.certificate,
                endpoint.serverVersion,
                endpoint.cipherSuites
            );

            simulator.printHistory();

            cout << "Certificate: "
                 << toString(
                     endpoint.certificate.evaluate()
                 ) << '\n';

            if (result) {
                ++successful;
            } else {
                ++failed;
            }
        }

        cout << "\nAUDIT RESULTS\n";
        cout << "Total: " << endpoints.size() << '\n';
        cout << "Successful: " << successful << '\n';
        cout << "Failed: " << failed << '\n';
    }
};

void testSecurityEngine() {
    TLSConfiguration invalid;
    invalid.hostname = "";

    bool rejected = false;

    try {
        invalid.validate();
    } catch (const invalid_argument&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error(
            "Empty hostname validation failed"
        );
    }

    Certificate validCertificate{
        "api.example.com",
        "Example Root CA",
        {"api.example.com", "example.com"},
        180,
        true,
        true
    };

    HandshakeSimulator successful;

    TLSConfiguration configuration;
    configuration.hostname = "api.example.com";

    if (!successful.execute(
        configuration,
        validCertificate,
        TLSVersion::TLS13,
        {"TLS_AES_128_GCM_SHA256"}
    )) {
        throw runtime_error(
            "Valid handshake simulation failed"
        );
    }

    if (
        successful.getState() != HandshakeState::SECURE
    ) {
        throw runtime_error(
            "Unexpected final handshake state"
        );
    }

    Certificate wrongHostname{
        "other.example.com",
        "Example Root CA",
        {"other.example.com"},
        100,
        true,
        true
    };

    HandshakeSimulator failed;

    if (failed.execute(
        configuration,
        wrongHostname,
        TLSVersion::TLS13,
        {"TLS_AES_128_GCM_SHA256"}
    )) {
        throw runtime_error(
            "Hostname mismatch was not rejected"
        );
    }

    TerminationPolicy insecure{
        TerminationMode::REVERSE_PROXY,
        true,
        false,
        true,
        true,
        true
    };

    if (insecure.evaluate().empty()) {
        throw runtime_error(
            "Insecure termination policy was accepted"
        );
    }

    cout << "\nAll C++17 tests passed.\n";
}

int main() {
    try {
        testSecurityEngine();

        Certificate productionCertificate{
            "api.example.com",
            "Enterprise Root CA",
            {"api.example.com", "www.example.com"},
            120,
            true,
            true
        };

        Certificate expiringCertificate{
            "legacy.example.com",
            "Enterprise Root CA",
            {"legacy.example.com"},
            12,
            true,
            true
        };

        SecurityAudit audit;

        audit.addEndpoint({
            "api.example.com",
            443,
            TLSVersion::TLS13,
            productionCertificate,
            {
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384"
            }
        });

        audit.addEndpoint({
            "legacy.example.com",
            443,
            TLSVersion::TLS12,
            expiringCertificate,
            {
                "ECDHE-RSA-AES128-GCM-SHA256"
            }
        });

        cout << "\nENTERPRISE TLS SECURITY AUDIT\n";

        audit.run();

        TerminationPolicy reverseProxy{
            TerminationMode::REVERSE_PROXY,
            true,
            true,
            true,
            true,
            true
        };

        cout << "\nHTTPS TERMINATION POLICY\n";

        const auto violations = reverseProxy.evaluate();

        if (violations.empty()) {
            cout << "Policy compliant\n";
        } else {
            for (const auto& violation : violations) {
                cout << "Violation: " << violation << '\n';
            }
        }

    } catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

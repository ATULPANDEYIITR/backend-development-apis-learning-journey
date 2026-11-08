import javax.net.ssl.*;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * HTTPS and TLS Enterprise Security Management.
 *
 * Java 17 standard library only.
 *
 * Capabilities:
 * - Real TLS connections and handshakes
 * - X.509 certificate inspection
 * - Certificate expiration monitoring
 * - TLS version and cipher-suite assessment
 * - Enterprise termination policies
 * - Immutable assessment records
 * - Concurrent endpoint monitoring
 * - Merge-free policy evaluation and reporting
 *
 * Run:
 *   javac HttpsTlsManager.java
 *   java HttpsTlsManager example.com google.com
 *   java HttpsTlsManager --test
 */
public class HttpsTlsManager {

    enum TLSVersion {
        TLS_1_2("TLSv1.2"),
        TLS_1_3("TLSv1.3");

        private final String protocol;

        TLSVersion(String protocol) {
            this.protocol = protocol;
        }

        public String protocol() {
            return protocol;
        }
    }

    enum CertificateStatus {
        VALID,
        EXPIRING,
        EXPIRED,
        INVALID
    }

    enum TerminationMode {
        EDGE,
        REVERSE_PROXY,
        PASSTHROUGH
    }

    enum ConnectionStatus {
        SECURE,
        FAILED
    }

    record Endpoint(
        String hostname,
        int port,
        TLSVersion minimumVersion,
        int timeoutMillis
    ) {
        Endpoint {
            if (hostname == null || hostname.isBlank()) {
                throw new IllegalArgumentException(
                    "Hostname is required"
                );
            }

            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException(
                    "Invalid port"
                );
            }

            if (minimumVersion == null) {
                throw new IllegalArgumentException(
                    "Minimum TLS version is required"
                );
            }

            if (timeoutMillis <= 0) {
                throw new IllegalArgumentException(
                    "Timeout must be positive"
                );
            }
        }
    }

    record CertificateAssessment(
        String subject,
        String issuer,
        String serialNumber,
        Instant validFrom,
        Instant validUntil,
        long daysRemaining,
        CertificateStatus status,
        String signatureAlgorithm
    ) {}

    record HandshakeResult(
        Endpoint endpoint,
        ConnectionStatus status,
        String negotiatedProtocol,
        String cipherSuite,
        CertificateAssessment certificate,
        String error
    ) {}

    record AuditSummary(
        int total,
        int successful,
        int failed,
        long expiringCertificates,
        long expiredCertificates,
        Map<String, Long> protocolCounts
    ) {}

    interface SecurityPolicy<T> {
        List<String> evaluate(T configuration);
    }

    static class CertificateService {

        private final int warningDays;

        CertificateService(int warningDays) {
            if (warningDays < 0) {
                throw new IllegalArgumentException(
                    "Warning days cannot be negative"
                );
            }

            this.warningDays = warningDays;
        }

        CertificateAssessment assess(X509Certificate certificate) {
            try {
                certificate.checkValidity();
            } catch (Exception ignored) {
                // Expiry is classified below. Signature and trust
                // verification are performed by the TLS trust manager.
            }

            Instant now = Instant.now();
            Instant validUntil = certificate.getNotAfter().toInstant();

            long daysRemaining = ChronoUnit.DAYS.between(
                now,
                validUntil
            );

            CertificateStatus status;

            if (validUntil.isBefore(now)) {
                status = CertificateStatus.EXPIRED;
            } else if (daysRemaining <= warningDays) {
                status = CertificateStatus.EXPIRING;
            } else {
                status = CertificateStatus.VALID;
            }

            return new CertificateAssessment(
                certificate.getSubjectX500Principal().getName(),
                certificate.getIssuerX500Principal().getName(),
                certificate.getSerialNumber().toString(16),
                certificate.getNotBefore().toInstant(),
                validUntil,
                daysRemaining,
                status,
                certificate.getSigAlgName()
            );
        }
    }

    static class TLSConnectionService {

        private final CertificateService certificateService;

        TLSConnectionService(
            CertificateService certificateService
        ) {
            this.certificateService = certificateService;
        }

        HandshakeResult inspect(Endpoint endpoint) {
            try {
                SSLContext context = SSLContext.getDefault();

                try (SSLSocket socket = (SSLSocket)
                    context.getSocketFactory().createSocket()) {

                    socket.connect(
                        new InetSocketAddress(
                            endpoint.hostname(),
                            endpoint.port()
                        ),
                        endpoint.timeoutMillis()
                    );

                    socket.setSoTimeout(
                        endpoint.timeoutMillis()
                    );

                    SSLParameters parameters =
                        socket.getSSLParameters();

                    parameters.setProtocols(
                        endpoint.minimumVersion() == TLSVersion.TLS_1_3
                            ? new String[]{"TLSv1.3"}
                            : new String[]{"TLSv1.3", "TLSv1.2"}
                    );

                    // Endpoint identification enables hostname
                    // verification during the TLS handshake.
                    parameters.setEndpointIdentificationAlgorithm(
                        "HTTPS"
                    );

                    socket.setSSLParameters(parameters);
                    socket.startHandshake();

                    SSLSession session = socket.getSession();

                    Certificate[] peerCertificates =
                        session.getPeerCertificates();

                    if (
                        peerCertificates.length == 0 ||
                        !(peerCertificates[0] instanceof X509Certificate)
                    ) {
                        throw new SSLPeerUnverifiedException(
                            "No X.509 server certificate"
                        );
                    }

                    X509Certificate serverCertificate =
                        (X509Certificate) peerCertificates[0];

                    CertificateAssessment assessment =
                        certificateService.assess(
                            serverCertificate
                        );

                    return new HandshakeResult(
                        endpoint,
                        ConnectionStatus.SECURE,
                        session.getProtocol(),
                        session.getCipherSuite(),
                        assessment,
                        null
                    );
                }

            } catch (
                IOException |
                java.security.GeneralSecurityException |
                IllegalStateException error
            ) {
                return new HandshakeResult(
                    endpoint,
                    ConnectionStatus.FAILED,
                    null,
                    null,
                    null,
                    error.getClass().getSimpleName()
                        + ": " + error.getMessage()
                );
            }
        }
    }

    record TerminationConfiguration(
        TerminationMode mode,
        boolean frontendTLS,
        boolean backendTLS,
        boolean backendCertificateVerification,
        boolean secureCookies,
        boolean trustedProxyHeaders
    ) {}

    static class TerminationPolicy
        implements SecurityPolicy<TerminationConfiguration> {

        @Override
        public List<String> evaluate(
            TerminationConfiguration configuration
        ) {
            List<String> violations = new ArrayList<>();

            if (!configuration.frontendTLS()) {
                violations.add(
                    "Frontend HTTPS is mandatory"
                );
            }

            if (!configuration.secureCookies()) {
                violations.add(
                    "Secure cookie attribute is mandatory"
                );
            }

            if (
                configuration.mode() == TerminationMode.EDGE ||
                configuration.mode() == TerminationMode.REVERSE_PROXY
            ) {
                if (!configuration.backendTLS()) {
                    violations.add(
                        "Backend TLS is disabled"
                    );
                }

                if (
                    configuration.backendTLS() &&
                    !configuration.backendCertificateVerification()
                ) {
                    violations.add(
                        "Backend certificate verification is disabled"
                    );
                }

                if (!configuration.trustedProxyHeaders()) {
                    violations.add(
                        "Trusted proxy metadata is not configured"
                    );
                }
            }

            return List.copyOf(violations);
        }
    }

    static class TLSAuditService {

        private final TLSConnectionService connectionService;

        TLSAuditService(
            TLSConnectionService connectionService
        ) {
            this.connectionService = connectionService;
        }

        List<HandshakeResult> inspectAll(
            List<Endpoint> endpoints
        ) {
            ExecutorService executor =
                Executors.newFixedThreadPool(
                    Math.min(5, endpoints.size())
                );

            try {
                List<Callable<HandshakeResult>> tasks =
                    endpoints.stream()
                        .map(endpoint ->
                            (Callable<HandshakeResult>) () ->
                                connectionService.inspect(endpoint)
                        )
                        .collect(Collectors.toList());

                List<Future<HandshakeResult>> futures =
                    executor.invokeAll(
                        tasks,
                        15,
                        TimeUnit.SECONDS
                    );

                List<HandshakeResult> results =
                    new ArrayList<>();

                for (int i = 0; i < futures.size(); i++) {
                    Future<HandshakeResult> future = futures.get(i);

                    try {
                        if (future.isCancelled()) {
                            results.add(new HandshakeResult(
                                endpoints.get(i),
                                ConnectionStatus.FAILED,
                                null,
                                null,
                                null,
                                "Audit task timed out"
                            ));
                        } else {
                            results.add(future.get());
                        }
                    } catch (ExecutionException error) {
                        results.add(new HandshakeResult(
                            endpoints.get(i),
                            ConnectionStatus.FAILED,
                            null,
                            null,
                            null,
                            error.getCause().getMessage()
                        ));
                    }
                }

                return List.copyOf(results);

            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();

                throw new IllegalStateException(
                    "TLS audit interrupted",
                    error
                );
            } finally {
                executor.shutdownNow();
            }
        }

        AuditSummary summarize(
            List<HandshakeResult> results
        ) {
            int successful = (int) results.stream()
                .filter(result ->
                    result.status() == ConnectionStatus.SECURE
                )
                .count();

            long expiring = results.stream()
                .filter(result -> result.certificate() != null)
                .filter(result ->
                    result.certificate().status()
                        == CertificateStatus.EXPIRING
                )
                .count();

            long expired = results.stream()
                .filter(result -> result.certificate() != null)
                .filter(result ->
                    result.certificate().status()
                        == CertificateStatus.EXPIRED
                )
                .count();

            Map<String, Long> protocols =
                results.stream()
                    .filter(result ->
                        result.status() == ConnectionStatus.SECURE
                    )
                    .collect(Collectors.groupingBy(
                        HandshakeResult::negotiatedProtocol,
                        TreeMap::new,
                        Collectors.counting()
                    ));

            return new AuditSummary(
                results.size(),
                successful,
                results.size() - successful,
                expiring,
                expired,
                Collections.unmodifiableMap(protocols)
            );
        }
    }

    static void runTests() {
        Endpoint valid = new Endpoint(
            "example.com",
            443,
            TLSVersion.TLS_1_2,
            5000
        );

        if (valid.port() != 443) {
            throw new AssertionError(
                "Endpoint validation failed"
            );
        }

        try {
            new Endpoint(
                "",
                443,
                TLSVersion.TLS_1_2,
                5000
            );

            throw new AssertionError(
                "Empty hostname accepted"
            );
        } catch (IllegalArgumentException expected) {
            System.out.println(
                "Hostname validation passed"
            );
        }

        TerminationPolicy policy =
            new TerminationPolicy();

        TerminationConfiguration insecure =
            new TerminationConfiguration(
                TerminationMode.REVERSE_PROXY,
                true,
                false,
                false,
                false,
                true
            );

        if (policy.evaluate(insecure).isEmpty()) {
            throw new AssertionError(
                "Insecure termination accepted"
            );
        }

        TerminationConfiguration secure =
            new TerminationConfiguration(
                TerminationMode.EDGE,
                true,
                true,
                true,
                true,
                true
            );

        if (!policy.evaluate(secure).isEmpty()) {
            throw new AssertionError(
                "Secure termination rejected"
            );
        }

        System.out.println(
            "All Java 17 tests passed."
        );
    }

    public static void main(String[] args) {
        if (
            args.length > 0 &&
            args[0].equals("--test")
        ) {
            runTests();
            return;
        }

        List<String> hostnames =
            args.length == 0
                ? List.of("example.com", "google.com")
                : Arrays.asList(args);

        try {
            CertificateService certificateService =
                new CertificateService(30);

            TLSConnectionService connectionService =
                new TLSConnectionService(
                    certificateService
                );

            TLSAuditService auditService =
                new TLSAuditService(
                    connectionService
                );

            List<Endpoint> endpoints =
                hostnames.stream()
                    .distinct()
                    .map(hostname ->
                        new Endpoint(
                            hostname,
                            443,
                            TLSVersion.TLS_1_2,
                            5000
                        )
                    )
                    .toList();

            List<HandshakeResult> results =
                auditService.inspectAll(endpoints);

            System.out.println(
                "\nENTERPRISE HTTPS/TLS AUDIT"
            );

            for (HandshakeResult result : results) {
                System.out.println(
                    "\nEndpoint: "
                    + result.endpoint().hostname()
                );

                System.out.println(
                    "Status: " + result.status()
                );

                if (result.status() == ConnectionStatus.SECURE) {
                    System.out.println(
                        "Protocol: " + result.negotiatedProtocol()
                    );

                    System.out.println(
                        "Cipher: " + result.cipherSuite()
                    );

                    System.out.println(
                        "Certificate: "
                        + result.certificate().status()
                    );

                    System.out.println(
                        "Days remaining: "
                        + result.certificate().daysRemaining()
                    );
                } else {
                    System.out.println(
                        "Error: " + result.error()
                    );
                }
            }

            System.out.println(
                "\nAUDIT SUMMARY"
            );

            System.out.println(
                auditService.summarize(results)
            );

            TerminationConfiguration termination =
                new TerminationConfiguration(
                    TerminationMode.REVERSE_PROXY,
                    true,
                    true,
                    true,
                    true,
                    true
                );

            System.out.println(
                "\nTERMINATION POLICY"
            );

            List<String> violations =
                new TerminationPolicy().evaluate(
                    termination
                );

            System.out.println(
                violations.isEmpty()
                    ? "Compliant"
                    : violations
            );

        } catch (Exception error) {
            System.err.println(
                "Audit failed: " + error.getMessage()
            );

            System.exit(1);
        }
    }
}

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

/*
 * PostgreSQL Advanced Fundamentals
 *
 * Enterprise-oriented domain model for a PostgreSQL-backed configuration
 * registry.
 *
 * The program models the application-side meaning of:
 *
 *   PostgreSQL schema     -> Registry namespace
 *   sequence              -> human-readable database number
 *   UUID                  -> durable object identity
 *   enum                  -> controlled lifecycle state
 *   JSONB                 -> flexible nested configuration
 *   array                 -> typed multi-value attributes
 *   extension             -> database capability
 *
 * Compile:
 *   javac PostgreSQLAdvancedFundamentals.java
 *
 * Run:
 *   java PostgreSQLAdvancedFundamentals
 *
 * No third-party dependencies are required because this is a domain model
 * rather than a JDBC connectivity example.
 */
public class PostgreSQLAdvancedFundamentals {

    enum Environment {
        DEVELOPMENT,
        STAGING,
        PRODUCTION
    }

    enum ApplicationState {
        ACTIVE,
        SUSPENDED,
        RETIRED
    }

    enum DeploymentState {
        PLANNED,
        RUNNING,
        SUCCEEDED,
        FAILED,
        CANCELLED
    }

    enum ApprovalRequirement {
        OPTIONAL,
        REQUIRED
    }

    record BranchPolicy(
            ApprovalRequirement approvalRequirement,
            int requiredApprovals,
            boolean requireLinearHistory,
            boolean allowForcePush,
            boolean allowDeletion,
            Set<String> requiredChecks
    ) {
        BranchPolicy {
            Objects.requireNonNull(approvalRequirement);
            Objects.requireNonNull(requiredChecks);

            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                        "Approval count cannot be negative"
                );
            }

            if (approvalRequirement == ApprovalRequirement.REQUIRED
                    && requiredApprovals == 0) {
                throw new IllegalArgumentException(
                        "A required approval policy needs at least one approval"
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class JsonDocument {
        private final Map<String, Object> values;

        JsonDocument() {
            this.values = new LinkedHashMap<>();
        }

        JsonDocument(Map<String, Object> values) {
            this.values = new LinkedHashMap<>(values);
        }

        JsonDocument put(String key, Object value) {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                        "JSONB object keys cannot be blank"
                );
            }

            values.put(key, value);
            return this;
        }

        Optional<Object> get(String key) {
            return Optional.ofNullable(values.get(key));
        }

        Object require(String key) {
            return get(key).orElseThrow(
                    () -> new IllegalArgumentException(
                            "Required JSONB property is missing: " + key
                    )
            );
        }

        Map<String, Object> immutableView() {
            return Collections.unmodifiableMap(values);
        }

        @Override
        public String toString() {
            return values.toString();
        }
    }

    static final class Sequence {
        private final AtomicLong value;

        Sequence(long start) {
            if (start < 1) {
                throw new IllegalArgumentException(
                        "Sequence must start with a positive value"
                );
            }

            value = new AtomicLong(start);
        }

        long nextValue() {
            return value.getAndIncrement();
        }
    }

    static final class Application {
        private final UUID id;
        private final long applicationNumber;
        private final String name;
        private final String owner;
        private final Environment environment;
        private final List<String> supportedRegions;
        private final JsonDocument configuration;
        private ApplicationState state;

        Application(
                long applicationNumber,
                String name,
                String owner,
                Environment environment,
                List<String> supportedRegions,
                JsonDocument configuration
        ) {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                        "Application name is required"
                );
            }

            if (owner == null || !owner.contains("@")) {
                throw new IllegalArgumentException(
                        "Owner must contain an email address"
                );
            }

            if (supportedRegions == null) {
                throw new IllegalArgumentException(
                        "Supported regions cannot be null"
                );
            }

            if (supportedRegions.size() > 20) {
                throw new IllegalArgumentException(
                        "PostgreSQL array cardinality policy exceeded"
                );
            }

            this.id = UUID.randomUUID();
            this.applicationNumber = applicationNumber;
            this.name = name;
            this.owner = owner;
            this.environment = Objects.requireNonNull(environment);
            this.supportedRegions =
                    List.copyOf(supportedRegions);
            this.configuration =
                    Objects.requireNonNull(configuration);
            this.state = ApplicationState.ACTIVE;
        }

        UUID id() {
            return id;
        }

        long applicationNumber() {
            return applicationNumber;
        }

        String name() {
            return name;
        }

        Environment environment() {
            return environment;
        }

        JsonDocument configuration() {
            return configuration;
        }

        ApplicationState state() {
            return state;
        }

        void suspend() {
            if (state != ApplicationState.ACTIVE) {
                throw new IllegalStateException(
                        "Only active applications can be suspended"
                );
            }

            state = ApplicationState.SUSPENDED;
        }

        void retire() {
            if (state == ApplicationState.RETIRED) {
                throw new IllegalStateException(
                        "Application is already retired"
                );
            }

            state = ApplicationState.RETIRED;
        }

        List<String> supportedRegions() {
            return supportedRegions;
        }
    }

    static final class Deployment {
        private final UUID id;
        private final UUID applicationId;
        private final String requestedBy;
        private final JsonDocument metadata;
        private final List<String> tags;
        private DeploymentState state;
        private Instant startedAt;
        private Instant completedAt;

        Deployment(
                UUID applicationId,
                String requestedBy,
                JsonDocument metadata,
                List<String> tags
        ) {
            this.id = UUID.randomUUID();
            this.applicationId =
                    Objects.requireNonNull(applicationId);
            this.requestedBy =
                    Objects.requireNonNull(requestedBy);
            this.metadata =
                    Objects.requireNonNull(metadata);
            this.tags = List.copyOf(tags);
            this.state = DeploymentState.PLANNED;
        }

        void start() {
            if (state != DeploymentState.PLANNED) {
                throw new IllegalStateException(
                        "Only planned deployments can start"
                );
            }

            state = DeploymentState.RUNNING;
            startedAt = Instant.now();
        }

        void succeed() {
            if (state != DeploymentState.RUNNING) {
                throw new IllegalStateException(
                        "Only running deployments can succeed"
                );
            }

            state = DeploymentState.SUCCEEDED;
            completedAt = Instant.now();
        }

        void fail() {
            if (state != DeploymentState.RUNNING) {
                throw new IllegalStateException(
                        "Only running deployments can fail"
                );
            }

            state = DeploymentState.FAILED;
            completedAt = Instant.now();
        }

        DeploymentState state() {
            return state;
        }

        UUID id() {
            return id;
        }

        JsonDocument metadata() {
            return metadata;
        }

        Instant startedAt() {
            return startedAt;
        }

        Instant completedAt() {
            return completedAt;
        }
    }

    static final class RegistryService {
        private final Sequence applicationSequence =
                new Sequence(7000);

        private final Map<UUID, Application> applications =
                new LinkedHashMap<>();

        private final Map<UUID, Deployment> deployments =
                new LinkedHashMap<>();

        Application registerApplication(
                String name,
                String owner,
                Environment environment,
                List<String> regions,
                JsonDocument configuration
        ) {
            boolean duplicate = applications.values()
                    .stream()
                    .anyMatch(application ->
                            application.name().equalsIgnoreCase(name));

            if (duplicate) {
                throw new IllegalArgumentException(
                        "Application name already exists"
                );
            }

            Application application = new Application(
                    applicationSequence.nextValue(),
                    name,
                    owner,
                    environment,
                    regions,
                    configuration
            );

            applications.put(application.id(), application);

            return application;
        }

        Deployment createDeployment(
                Application application,
                String requester,
                JsonDocument metadata,
                List<String> tags
        ) {
            if (application.state() != ApplicationState.ACTIVE) {
                throw new IllegalStateException(
                        "Retired or suspended applications cannot deploy"
                );
            }

            Deployment deployment = new Deployment(
                    application.id(),
                    requester,
                    metadata,
                    tags
            );

            deployments.put(deployment.id(), deployment);

            return deployment;
        }

        List<Deployment> deploymentsFor(
                Application application
        ) {
            return deployments.values()
                    .stream()
                    .filter(deployment ->
                            deployment
                                    .applicationId
                                    .equals(application.id()))
                    .toList();
        }
    }

    private static void printApplication(
            Application application
    ) {
        System.out.println("\nApplication");
        System.out.println("  UUID: " + application.id());
        System.out.println(
                "  Sequence-backed number: "
                        + application.applicationNumber()
        );
        System.out.println(
                "  Name: " + application.name()
        );
        System.out.println(
                "  Environment: "
                        + application.environment()
        );
        System.out.println(
                "  Regions: "
                        + application.supportedRegions()
        );
        System.out.println(
                "  State: " + application.state()
        );
        System.out.println(
                "  JSONB-style configuration: "
                        + application.configuration()
        );
    }

    private static void demonstrateInvalidState(
            Deployment deployment
    ) {
        try {
            deployment.succeed();
        } catch (IllegalStateException exception) {
            System.out.println(
                    "\nExpected state transition failure: "
                            + exception.getMessage()
            );
        }
    }

    public static void main(String[] args) {
        RegistryService registry = new RegistryService();

        JsonDocument productionConfiguration =
                new JsonDocument()
                        .put("runtime", "java")
                        .put("replicas", 6)
                        .put(
                                "features",
                                List.of(
                                        "audit",
                                        "metrics",
                                        "releases"
                                )
                        )
                        .put(
                                "limits",
                                new JsonDocument()
                                        .put(
                                                "requestsPerMinute",
                                                2500
                                        )
                                        .put(
                                                "maximumDeploymentSize",
                                                50
                                        )
                        );

        Application application =
                registry.registerApplication(
                        "release-control-plane",
                        "platform@example.com",
                        Environment.PRODUCTION,
                        List.of(
                                "ap-south-1",
                                "eu-west-1",
                                "us-east-1"
                        ),
                        productionConfiguration
                );

        printApplication(application);

        BranchPolicy policy = new BranchPolicy(
                ApprovalRequirement.REQUIRED,
                2,
                true,
                false,
                false,
                Set.of(
                        "unit-tests",
                        "integration-tests",
                        "security-scan"
                )
        );

        System.out.println("\nBranch policy model");
        System.out.println(
                "  Approval requirement: "
                        + policy.approvalRequirement()
        );
        System.out.println(
                "  Required approvals: "
                        + policy.requiredApprovals()
        );
        System.out.println(
                "  Linear history: "
                        + policy.requireLinearHistory()
        );
        System.out.println(
                "  Force push: "
                        + policy.allowForcePush()
        );
        System.out.println(
                "  Deletion: "
                        + policy.allowDeletion()
        );
        System.out.println(
                "  Required checks: "
                        + policy.requiredChecks()
        );

        JsonDocument deploymentMetadata =
                new JsonDocument()
                        .put("commit", "8f5a1c2d7e9b")
                        .put("pipeline", "production-release")
                        .put(
                                "artifact",
                                new JsonDocument()
                                        .put(
                                                "name",
                                                "release-control-plane"
                                        )
                                        .put(
                                                "version",
                                                "2026.10.06"
                                        )
                        );

        Deployment deployment =
                registry.createDeployment(
                        application,
                        "release-bot",
                        deploymentMetadata,
                        List.of(
                                "production",
                                "automated",
                                "verified"
                        )
                );

        demonstrateInvalidState(deployment);

        deployment.start();
        deployment.succeed();

        System.out.println("\nDeployment");
        System.out.println("  UUID: " + deployment.id());
        System.out.println(
                "  State: " + deployment.state()
        );
        System.out.println(
                "  Metadata: " + deployment.metadata()
        );
        System.out.println(
                "  Started: " + deployment.startedAt()
        );
        System.out.println(
                "  Completed: " + deployment.completedAt()
        );

        System.out.println("\nRelational model mapping");
        System.out.println(
                "  UUID identifies the application and deployment."
        );
        System.out.println(
                "  Sequence-backed numbers provide ordered human-facing identifiers."
        );
        System.out.println(
                "  Enums constrain lifecycle values."
        );
        System.out.println(
                "  JSONB-style documents carry changing nested configuration."
        );
        System.out.println(
                "  Arrays represent bounded multi-valued attributes."
        );
        System.out.println(
                "  PostgreSQL extensions add capabilities such as UUID generation."
        );

        System.out.println(
                "\nDeployment count for application: "
                        + registry.deploymentsFor(application).size()
        );
    }
}

import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class AttributeBasedAccessControl {

    enum Effect {
        ALLOW, DENY
    }

    enum Decision {
        ALLOW, DENY
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    record User(
        String id,
        String department,
        Set<String> roles,
        int clearance,
        boolean active
    ) {
        User {
            Objects.requireNonNull(id);
            Objects.requireNonNull(department);
            roles = Set.copyOf(roles);

            if (id.isBlank()) {
                throw new IllegalArgumentException("User id cannot be blank");
            }

            if (clearance < 0 || clearance > 5) {
                throw new IllegalArgumentException(
                    "Clearance must be between 0 and 5"
                );
            }
        }

        boolean hasRole(String role) {
            return roles.contains(role);
        }
    }

    record Resource(
        String id,
        String type,
        String ownerDepartment,
        int classification
    ) {
        Resource {
            Objects.requireNonNull(id);
            Objects.requireNonNull(type);
            Objects.requireNonNull(ownerDepartment);

            if (classification < 0 || classification > 5) {
                throw new IllegalArgumentException(
                    "Classification must be between 0 and 5"
                );
            }
        }
    }

    record AccessContext(
        User user,
        Resource resource,
        String action,
        String ipAddress,
        boolean trustedDevice,
        boolean mfaVerified,
        String country,
        String environment,
        Map<String, String> attributes
    ) {
        AccessContext {
            Objects.requireNonNull(user);
            Objects.requireNonNull(resource);
            Objects.requireNonNull(action);
            Objects.requireNonNull(ipAddress);
            Objects.requireNonNull(country);
            Objects.requireNonNull(environment);
            attributes = Map.copyOf(attributes);

            if (action.isBlank()) {
                throw new IllegalArgumentException(
                    "Action cannot be blank"
                );
            }
        }
    }

    record Policy(
        String id,
        String name,
        Effect effect,
        int priority,
        Set<String> actions,
        Set<String> resourceTypes,
        List<Predicate<AccessContext>> conditions
    ) {
        Policy {
            Objects.requireNonNull(id);
            Objects.requireNonNull(name);
            Objects.requireNonNull(effect);
            actions = Set.copyOf(actions);
            resourceTypes = Set.copyOf(resourceTypes);
            conditions = List.copyOf(conditions);

            if (priority < 0) {
                throw new IllegalArgumentException(
                    "Policy priority cannot be negative"
                );
            }
        }

        boolean matches(AccessContext context) {
            boolean actionMatch =
                actions.contains("*") ||
                actions.contains(context.action());

            boolean resourceMatch =
                resourceTypes.contains("*") ||
                resourceTypes.contains(context.resource().type());

            return actionMatch &&
                resourceMatch &&
                conditions.stream()
                    .allMatch(condition -> condition.test(context));
        }
    }

    record AuthorizationDecision(
        Instant timestamp,
        String userId,
        String resourceId,
        String action,
        Decision decision,
        List<String> matchedPolicies,
        String reason
    ) {}

    static final class AuthorizationException
        extends RuntimeException {

        AuthorizationException(String message) {
            super(message);
        }
    }

    static final class PolicyConflictException
        extends AuthorizationException {

        PolicyConflictException(String message) {
            super(message);
        }
    }

    interface PolicyRepository {
        List<Policy> findActivePolicies();
    }

    static final class InMemoryPolicyRepository
        implements PolicyRepository {

        private final List<Policy> policies;

        InMemoryPolicyRepository(List<Policy> policies) {
            this.policies = List.copyOf(policies);
        }

        @Override
        public List<Policy> findActivePolicies() {
            return policies;
        }
    }

    static final class AuthorizationService {
        private final PolicyRepository repository;
        private final List<AuthorizationDecision> auditTrail =
            new ArrayList<>();

        AuthorizationService(PolicyRepository repository) {
            this.repository = repository;
        }

        AuthorizationDecision authorize(AccessContext context) {
            validate(context);

            List<Policy> matched = repository.findActivePolicies()
                .stream()
                .filter(policy -> policy.matches(context))
                .sorted(
                    java.util.Comparator
                        .comparingInt(Policy::priority)
                        .reversed()
                )
                .toList();

            if (!context.user().active()) {
                return record(
                    context,
                    Decision.DENY,
                    matched,
                    "Inactive user"
                );
            }

            List<Policy> denies = matched.stream()
                .filter(policy -> policy.effect() == Effect.DENY)
                .toList();

            if (!denies.isEmpty()) {
                return record(
                    context,
                    Decision.DENY,
                    matched,
                    "Explicit deny policy matched: " +
                        denies.getFirst().id()
                );
            }

            List<Policy> allows = matched.stream()
                .filter(policy -> policy.effect() == Effect.ALLOW)
                .toList();

            if (allows.isEmpty()) {
                return record(
                    context,
                    Decision.DENY,
                    matched,
                    "Default deny: no applicable allow policy"
                );
            }

            int highestPriority = allows.getFirst().priority();

            long samePriority = allows.stream()
                .filter(policy ->
                    policy.priority() == highestPriority)
                .count();

            if (samePriority > 1) {
                throw new PolicyConflictException(
                    "Multiple allow policies share highest priority " +
                    highestPriority
                );
            }

            return record(
                context,
                Decision.ALLOW,
                matched,
                "Allowed by policy: " + allows.getFirst().id()
            );
        }

        private AuthorizationDecision record(
            AccessContext context,
            Decision decision,
            List<Policy> matched,
            String reason
        ) {
            AuthorizationDecision result =
                new AuthorizationDecision(
                    Instant.now(),
                    context.user().id(),
                    context.resource().id(),
                    context.action(),
                    decision,
                    matched.stream()
                        .map(Policy::id)
                        .collect(Collectors.toUnmodifiableList()),
                    reason
                );

            auditTrail.add(result);
            return result;
        }

        private void validate(AccessContext context) {
            if (context.user().clearance() <
                context.resource().classification()) {
                throw new AuthorizationException(
                    "User clearance is below resource classification"
                );
            }

            if (!validIpv4(context.ipAddress())) {
                throw new AuthorizationException(
                    "Invalid IPv4 address"
                );
            }
        }

        List<AuthorizationDecision> auditTrail() {
            return List.copyOf(auditTrail);
        }

        private boolean validIpv4(String address) {
            String[] parts = address.split("\\.", -1);

            if (parts.length != 4) {
                return false;
            }

            for (String part : parts) {
                try {
                    int value = Integer.parseInt(part);
                    if (value < 0 || value > 255) {
                        return false;
                    }
                } catch (NumberFormatException error) {
                    return false;
                }
            }

            return true;
        }
    }

    static Predicate<AccessContext> role(String role) {
        return context -> context.user().hasRole(role);
    }

    static Predicate<AccessContext> department(String department) {
        return context ->
            context.user().department().equals(department);
    }

    static Predicate<AccessContext> classificationAtMost(int value) {
        return context ->
            context.resource().classification() <= value;
    }

    static Predicate<AccessContext> classificationAtLeast(int value) {
        return context ->
            context.resource().classification() >= value;
    }

    static Predicate<AccessContext> trustedDevice() {
        return AccessContext::trustedDevice;
    }

    static Predicate<AccessContext> mfa() {
        return AccessContext::mfaVerified;
    }

    static Predicate<AccessContext> environment(String value) {
        return context ->
            context.environment().equals(value);
    }

    static Predicate<AccessContext> emergencyTicket() {
        return context -> context.attributes()
            .getOrDefault("emergencyTicket", "")
            .matches("INC-[0-9]{6}");
    }

    static List<Policy> createPolicies() {
        return List.of(
            new Policy(
                "P001",
                "Trusted analyst access",
                Effect.ALLOW,
                50,
                Set.of("read"),
                Set.of("report"),
                List.of(
                    role("analyst"),
                    classificationAtMost(2),
                    trustedDevice()
                )
            ),
            new Policy(
                "P002",
                "Manager confidential access",
                Effect.ALLOW,
                70,
                Set.of("read"),
                Set.of("report"),
                List.of(
                    role("manager"),
                    classificationAtMost(4),
                    trustedDevice(),
                    mfa()
                )
            ),
            new Policy(
                "P003",
                "Restricted resource block",
                Effect.DENY,
                100,
                Set.of("read", "write", "delete"),
                Set.of("report", "database"),
                List.of(
                    classificationAtLeast(4),
                    context ->
                        !context.trustedDevice()
                )
            ),
            new Policy(
                "P004",
                "Security administrator database access",
                Effect.ALLOW,
                90,
                Set.of("read", "write", "delete"),
                Set.of("database"),
                List.of(
                    department("security"),
                    role("administrator"),
                    mfa(),
                    environment("production")
                )
            ),
            new Policy(
                "P005",
                "Incident responder emergency access",
                Effect.ALLOW,
                80,
                Set.of("read"),
                Set.of("report"),
                List.of(
                    role("incident_responder"),
                    mfa(),
                    emergencyTicket()
                )
            )
        );
    }

    static AccessContext context(
        User user,
        Resource resource,
        String action
    ) {
        return new AccessContext(
            user,
            resource,
            action,
            "10.20.30.40",
            true,
            true,
            "IN",
            "production",
            Map.of()
        );
    }

    static AccessContext context(
        User user,
        Resource resource,
        String action,
        boolean trusted,
        boolean mfa,
        Map<String, String> attributes
    ) {
        return new AccessContext(
            user,
            resource,
            action,
            "10.20.30.40",
            trusted,
            mfa,
            "IN",
            "production",
            attributes
        );
    }

    public static void main(String[] args) {
        PolicyRepository repository =
            new InMemoryPolicyRepository(createPolicies());

        AuthorizationService service =
            new AuthorizationService(repository);

        User analyst = new User(
            "U100",
            "analytics",
            Set.of("employee", "analyst"),
            2,
            true
        );

        User manager = new User(
            "U200",
            "operations",
            Set.of("employee", "manager"),
            4,
            true
        );

        User securityAdmin = new User(
            "U300",
            "security",
            Set.of("employee", "administrator"),
            5,
            true
        );

        User responder = new User(
            "U400",
            "security",
            Set.of("employee", "incident_responder"),
            5,
            true
        );

        Resource report = new Resource(
            "R100",
            "report",
            "analytics",
            2
        );

        Resource confidentialReport = new Resource(
            "R200",
            "report",
            "security",
            4
        );

        Resource database = new Resource(
            "DB100",
            "database",
            "security",
            5
        );

        List<AccessContext> requests = List.of(
            context(analyst, report, "read"),
            context(manager, confidentialReport, "read"),
            context(
                manager,
                confidentialReport,
                "read",
                true,
                false,
                Map.of()
            ),
            context(
                securityAdmin,
                database,
                "delete"
            ),
            context(
                securityAdmin,
                database,
                "read",
                false,
                true,
                Map.of()
            ),
            context(
                responder,
                confidentialReport,
                "read",
                true,
                true,
                Map.of("emergencyTicket", "INC-123456")
            )
        );

        for (AccessContext request : requests) {
            try {
                AuthorizationDecision decision =
                    service.authorize(request);

                System.out.printf(
                    "%s -> %s: %s (%s)%n",
                    decision.userId(),
                    decision.resourceId(),
                    decision.decision(),
                    decision.reason()
                );
            } catch (AuthorizationException error) {
                System.out.printf(
                    "%s -> %s: ERROR: %s%n",
                    request.user().id(),
                    request.resource().id(),
                    error.getMessage()
                );
            }
        }

        System.out.println(
            "Audit records: " + service.auditTrail().size()
        );
    }
}

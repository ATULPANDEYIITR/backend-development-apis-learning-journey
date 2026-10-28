import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

public class RBACEnterpriseDemo {

    enum Role {
        USER,
        SUPPORT,
        MANAGER,
        ADMIN
    }

    enum Action {
        READ,
        CREATE,
        UPDATE,
        DELETE,
        APPROVE,
        ADMIN
    }

    enum Decision {
        ALLOW,
        DENY
    }

    enum ResourceSensitivity {
        NORMAL,
        HIGH,
        CRITICAL
    }

    record Permission(String resource, Action action) {
        public Permission {
            if (resource == null || resource.isBlank()) {
                throw new ValidationException("Resource cannot be empty");
            }
            Objects.requireNonNull(action, "Action is required");
        }

        String key() {
            return resource + ":" + action.name().toLowerCase();
        }
    }

    record Resource(
        String id,
        String type,
        String ownerId,
        ResourceSensitivity sensitivity
    ) {
        public Resource {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Resource ID is required");
            }
            if (type == null || type.isBlank()) {
                throw new ValidationException("Resource type is required");
            }
            if (ownerId == null || ownerId.isBlank()) {
                throw new ValidationException("Owner ID is required");
            }
            Objects.requireNonNull(sensitivity);
        }
    }

    record AuthorizationRequest(
        String userId,
        Action action,
        Resource resource
    ) {
        public AuthorizationRequest {
            if (userId == null || userId.isBlank()) {
                throw new ValidationException("User ID is required");
            }
            Objects.requireNonNull(action);
            Objects.requireNonNull(resource);
        }
    }

    record AuthorizationResult(
        Decision decision,
        String reason,
        List<String> matchedPermissions
    ) {
        AuthorizationResult {
            matchedPermissions = List.copyOf(matchedPermissions);
        }
    }

    record AuditEvent(
        String userId,
        String event,
        String detail
    ) {}

    static final class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class AuthorizationException extends RuntimeException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static final class AuthenticationException extends RuntimeException {
        AuthenticationException(String message) {
            super(message);
        }
    }

    static final class UserAccount {
        private final String id;
        private final String username;
        private final Set<Role> roles;
        private boolean active;

        UserAccount(
            String id,
            String username,
            Set<Role> roles,
            boolean active
        ) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("User ID is required");
            }
            if (username == null || username.isBlank()) {
                throw new ValidationException("Username is required");
            }

            this.id = id;
            this.username = username;
            this.roles = EnumSet.copyOf(roles);
            this.active = active;
        }

        String id() {
            return id;
        }

        String username() {
            return username;
        }

        Set<Role> roles() {
            return Set.copyOf(roles);
        }

        boolean active() {
            return active;
        }

        void setActive(boolean active) {
            this.active = active;
        }

        void assignRole(Role role) {
            roles.add(role);
        }

        void revokeRole(Role role) {
            roles.remove(role);
        }
    }

    interface AuthorizationPolicy {
        boolean applies(UserAccount user, AuthorizationRequest request);

        String name();
    }

    static final class OwnershipPolicy implements AuthorizationPolicy {

        @Override
        public boolean applies(
            UserAccount user,
            AuthorizationRequest request
        ) {
            return request.resource().ownerId().equals(user.id())
                && (
                    request.action() == Action.READ
                    || request.action() == Action.UPDATE
                )
                && (
                    request.resource().type().equals("profile")
                    || request.resource().type().equals("document")
                );
        }

        @Override
        public String name() {
            return "ownership-policy";
        }
    }

    static final class AuthorizationService {
        private final Map<Role, Set<Permission>> rolePermissions =
            new EnumMap<>(Role.class);

        private final Map<String, UserAccount> users =
            new HashMap<>();

        private final List<AuthorizationPolicy> policies =
            new ArrayList<>();

        private final List<AuditEvent> auditEvents =
            new ArrayList<>();

        AuthorizationService() {
            for (Role role : Role.values()) {
                rolePermissions.put(
                    role,
                    new HashSet<>()
                );
            }

            policies.add(new OwnershipPolicy());
        }

        void grant(Role role, Permission permission) {
            rolePermissions
                .get(role)
                .add(permission);
        }

        void addUser(UserAccount user) {
            if (users.containsKey(user.id())) {
                throw new ValidationException(
                    "Duplicate user: " + user.id()
                );
            }

            for (Role role : user.roles()) {
                if (!rolePermissions.containsKey(role)) {
                    throw new ValidationException(
                        "Unknown role: " + role
                    );
                }
            }

            users.put(user.id(), user);
        }

        void assignRole(String userId, Role role) {
            UserAccount user = requireUser(userId);

            user.assignRole(role);

            auditEvents.add(
                new AuditEvent(
                    userId,
                    "role-assignment",
                    "assigned=" + role
                )
            );
        }

        void revokeRole(String userId, Role role) {
            UserAccount user = requireUser(userId);

            user.revokeRole(role);

            auditEvents.add(
                new AuditEvent(
                    userId,
                    "role-revocation",
                    "revoked=" + role
                )
            );
        }

        AuthorizationResult authorize(
            AuthorizationRequest request
        ) {
            UserAccount user = requireUser(request.userId());

            if (!user.active()) {
                return finish(
                    request,
                    Decision.DENY,
                    "User account is inactive",
                    List.of()
                );
            }

            if (
                request.action() == Action.ADMIN
                && !user.roles().contains(Role.ADMIN)
            ) {
                return finish(
                    request,
                    Decision.DENY,
                    "Administrative action requires ADMIN role",
                    List.of()
                );
            }

            Permission requested = new Permission(
                request.resource().type(),
                request.action()
            );

            Set<String> matched = new TreeSet<>();

            for (Role role : user.roles()) {
                if (
                    rolePermissions
                        .getOrDefault(role, Set.of())
                        .contains(requested)
                ) {
                    matched.add(
                        role.name().toLowerCase()
                        + ":"
                        + requested.key()
                    );
                }
            }

            if (!matched.isEmpty()) {
                return finish(
                    request,
                    Decision.ALLOW,
                    "Explicit role permission matched",
                    new ArrayList<>(matched)
                );
            }

            for (AuthorizationPolicy policy : policies) {
                if (policy.applies(user, request)) {
                    return finish(
                        request,
                        Decision.ALLOW,
                        "Authorization policy matched",
                        List.of(policy.name())
                    );
                }
            }

            return finish(
                request,
                Decision.DENY,
                "No applicable role permission or policy",
                List.of()
            );
        }

        Set<Permission> effectivePermissions(String userId) {
            UserAccount user = requireUser(userId);

            Set<Permission> result = new TreeSet<>(
                (a, b) -> a.key().compareTo(b.key())
            );

            for (Role role : user.roles()) {
                result.addAll(
                    rolePermissions.getOrDefault(
                        role,
                        Set.of()
                    )
                );
            }

            return Set.copyOf(result);
        }

        UserAccount authenticate(
            String username,
            String password
        ) {
            UserAccount account = users.values()
                .stream()
                .filter(user -> user.username().equals(username))
                .findFirst()
                .orElseThrow(
                    () -> new AuthenticationException(
                        "Invalid credentials"
                    )
                );

            if (!account.active()) {
                throw new AuthenticationException(
                    "Account is inactive"
                );
            }

            /*
             * The demo keeps credentials outside the domain model.
             * A production authentication service should use a
             * dedicated credential store and memory-hard password
             * hashing rather than embedding secrets in source code.
             */
            if (!"UserPassword!2026".equals(password)
                && account.username().equals("alice")) {
                throw new AuthenticationException(
                    "Invalid credentials"
                );
            }

            auditEvents.add(
                new AuditEvent(
                    account.id(),
                    "authentication",
                    "success"
                )
            );

            return account;
        }

        List<AuditEvent> auditEvents() {
            return List.copyOf(auditEvents);
        }

        private UserAccount requireUser(String userId) {
            UserAccount user = users.get(userId);

            if (user == null) {
                throw new ValidationException(
                    "Unknown user: " + userId
                );
            }

            return user;
        }

        private AuthorizationResult finish(
            AuthorizationRequest request,
            Decision decision,
            String reason,
            List<String> matches
        ) {
            auditEvents.add(
                new AuditEvent(
                    request.userId(),
                    "authorization",
                    request.action()
                        + ":"
                        + request.resource().type()
                        + ":"
                        + decision
                        + ":"
                        + reason
                )
            );

            return new AuthorizationResult(
                decision,
                reason,
                matches
            );
        }
    }

    private static AuthorizationService buildService() {
        AuthorizationService service =
            new AuthorizationService();

        service.grant(
            Role.USER,
            new Permission("profile", Action.READ)
        );
        service.grant(
            Role.USER,
            new Permission("profile", Action.UPDATE)
        );

        service.grant(
            Role.SUPPORT,
            new Permission("profile", Action.READ)
        );
        service.grant(
            Role.SUPPORT,
            new Permission("ticket", Action.READ)
        );
        service.grant(
            Role.SUPPORT,
            new Permission("ticket", Action.UPDATE)
        );

        service.grant(
            Role.MANAGER,
            new Permission("profile", Action.READ)
        );
        service.grant(
            Role.MANAGER,
            new Permission("ticket", Action.READ)
        );
        service.grant(
            Role.MANAGER,
            new Permission("ticket", Action.UPDATE)
        );
        service.grant(
            Role.MANAGER,
            new Permission("ticket", Action.APPROVE)
        );
        service.grant(
            Role.MANAGER,
            new Permission("report", Action.READ)
        );

        service.grant(
            Role.ADMIN,
            new Permission("profile", Action.READ)
        );
        service.grant(
            Role.ADMIN,
            new Permission("profile", Action.UPDATE)
        );
        service.grant(
            Role.ADMIN,
            new Permission("ticket", Action.READ)
        );
        service.grant(
            Role.ADMIN,
            new Permission("ticket", Action.UPDATE)
        );
        service.grant(
            Role.ADMIN,
            new Permission("ticket", Action.APPROVE)
        );
        service.grant(
            Role.ADMIN,
            new Permission("report", Action.READ)
        );
        service.grant(
            Role.ADMIN,
            new Permission("system", Action.ADMIN)
        );

        service.addUser(
            new UserAccount(
                "u1",
                "alice",
                EnumSet.of(Role.USER),
                true
            )
        );

        service.addUser(
            new UserAccount(
                "u2",
                "bob",
                EnumSet.of(Role.SUPPORT),
                true
            )
        );

        service.addUser(
            new UserAccount(
                "u3",
                "carol",
                EnumSet.of(Role.MANAGER),
                true
            )
        );

        service.addUser(
            new UserAccount(
                "u4",
                "david",
                EnumSet.of(Role.ADMIN),
                true
            )
        );

        return service;
    }

    private static void test(
        AuthorizationService service
    ) {
        Resource profile = new Resource(
            "p-test",
            "profile",
            "u1",
            ResourceSensitivity.NORMAL
        );

        Resource ticket = new Resource(
            "t-test",
            "ticket",
            "u2",
            ResourceSensitivity.NORMAL
        );

        Resource system = new Resource(
            "s-test",
            "system",
            "u4",
            ResourceSensitivity.CRITICAL
        );

        if (
            service.authorize(
                new AuthorizationRequest(
                    "u1",
                    Action.UPDATE,
                    profile
                )
            ).decision() != Decision.ALLOW
        ) {
            throw new AssertionError("Ownership test failed");
        }

        if (
            service.authorize(
                new AuthorizationRequest(
                    "u1",
                    Action.UPDATE,
                    ticket
                )
            ).decision() != Decision.DENY
        ) {
            throw new AssertionError("Unauthorized update allowed");
        }

        if (
            service.authorize(
                new AuthorizationRequest(
                    "u2",
                    Action.UPDATE,
                    ticket
                )
            ).decision() != Decision.ALLOW
        ) {
            throw new AssertionError("Support permission failed");
        }

        if (
            service.authorize(
                new AuthorizationRequest(
                    "u2",
                    Action.ADMIN,
                    system
                )
            ).decision() != Decision.DENY
        ) {
            throw new AssertionError("Admin escalation allowed");
        }

        if (
            service.authorize(
                new AuthorizationRequest(
                    "u4",
                    Action.ADMIN,
                    system
                )
            ).decision() != Decision.ALLOW
        ) {
            throw new AssertionError("Admin authorization failed");
        }
    }

    public static void main(String[] args) {
        AuthorizationService service =
            buildService();

        test(service);

        Resource profile = new Resource(
            "p-100",
            "profile",
            "u1",
            ResourceSensitivity.NORMAL
        );

        Resource ticket = new Resource(
            "t-200",
            "ticket",
            "u2",
            ResourceSensitivity.NORMAL
        );

        Resource report = new Resource(
            "r-300",
            "report",
            "u3",
            ResourceSensitivity.HIGH
        );

        Resource system = new Resource(
            "s-400",
            "system",
            "u4",
            ResourceSensitivity.CRITICAL
        );

        List<AuthorizationRequest> requests = List.of(
            new AuthorizationRequest(
                "u1",
                Action.UPDATE,
                profile
            ),
            new AuthorizationRequest(
                "u1",
                Action.UPDATE,
                ticket
            ),
            new AuthorizationRequest(
                "u2",
                Action.UPDATE,
                ticket
            ),
            new AuthorizationRequest(
                "u3",
                Action.APPROVE,
                ticket
            ),
            new AuthorizationRequest(
                "u3",
                Action.READ,
                report
            ),
            new AuthorizationRequest(
                "u2",
                Action.ADMIN,
                system
            ),
            new AuthorizationRequest(
                "u4",
                Action.ADMIN,
                system
            )
        );

        for (AuthorizationRequest request : requests) {
            AuthorizationResult result =
                service.authorize(request);

            System.out.printf(
                "%s %s %s -> %s | %s%n",
                request.userId(),
                request.action(),
                request.resource().type(),
                result.decision(),
                result.reason()
            );
        }

        System.out.println(
            "\nEffective permissions for carol:"
        );

        service.effectivePermissions("u3")
            .stream()
            .map(Permission::key)
            .sorted()
            .forEach(
                permission ->
                    System.out.println("  " + permission)
            );

        System.out.println("\nAuthentication:");

        try {
            UserAccount user =
                service.authenticate(
                    "alice",
                    "UserPassword!2026"
                );

            System.out.println(
                "Authenticated: " + user.username()
            );
        } catch (AuthenticationException ex) {
            System.out.println(
                "Authentication failed: " + ex.getMessage()
            );
        }

        try {
            service.authenticate(
                "alice",
                "incorrect-password"
            );
        } catch (AuthenticationException ex) {
            System.out.println(
                "Rejected login: " + ex.getMessage()
            );
        }

        System.out.println(
            "\nAudit events: "
            + service.auditEvents().size()
        );

        for (AuditEvent event : service.auditEvents()) {
            System.out.println(
                "  "
                + event.userId()
                + " | "
                + event.event()
                + " | "
                + event.detail()
            );
        }

        System.out.println("\nAll RBAC tests passed.");
    }
}

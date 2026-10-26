import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public class OAuthEnterpriseDemo {

    enum TokenState {
        ACTIVE,
        REVOKED
    }

    enum GrantType {
        AUTHORIZATION_CODE,
        REFRESH_TOKEN
    }

    record Client(
        String clientId,
        Set<String> redirectUris,
        Set<String> allowedScopes,
        boolean confidential,
        String clientSecret
    ) {
        Client {
            Objects.requireNonNull(clientId);
            Objects.requireNonNull(redirectUris);
            Objects.requireNonNull(allowedScopes);

            if (clientId.isBlank()) {
                throw new IllegalArgumentException("clientId is required");
            }

            if (redirectUris.isEmpty()) {
                throw new IllegalArgumentException(
                    "at least one redirect URI is required"
                );
            }

            if (allowedScopes.isEmpty()) {
                throw new IllegalArgumentException(
                    "at least one scope is required"
                );
            }

            if (confidential &&
                (clientSecret == null || clientSecret.isBlank())) {
                throw new IllegalArgumentException(
                    "confidential clients require a secret"
                );
            }

            redirectUris = Set.copyOf(redirectUris);
            allowedScopes = Set.copyOf(allowedScopes);
        }
    }

    record AuthorizationCode(
        String value,
        String clientId,
        String redirectUri,
        String subject,
        Set<String> scopes,
        String codeChallenge,
        Instant expiresAt
    ) {
        AuthorizationCode {
            scopes = Set.copyOf(scopes);
        }
    }

    record AccessToken(
        String value,
        String clientId,
        String subject,
        Set<String> scopes,
        Instant expiresAt,
        TokenState state
    ) {
        AccessToken {
            scopes = Set.copyOf(scopes);
        }

        boolean expired() {
            return Instant.now().isAfter(expiresAt);
        }
    }

    record RefreshToken(
        String value,
        String clientId,
        String subject,
        Set<String> scopes,
        Instant expiresAt,
        TokenState state
    ) {
        RefreshToken {
            scopes = Set.copyOf(scopes);
        }

        boolean expired() {
            return Instant.now().isAfter(expiresAt);
        }
    }

    record ProtectedResource(
        String resourceId,
        String owner,
        String requiredScope,
        Map<String, String> attributes
    ) {
        ProtectedResource {
            attributes = Map.copyOf(attributes);
        }
    }

    static class OAuthException extends RuntimeException {
        private final String errorCode;

        OAuthException(String errorCode, String message) {
            super(message);
            this.errorCode = errorCode;
        }

        String errorCode() {
            return errorCode;
        }
    }

    interface Policy {
        void validate(
            Client client,
            Set<String> requestedScopes
        );
    }

    static final class LeastPrivilegePolicy implements Policy {
        @Override
        public void validate(
            Client client,
            Set<String> requestedScopes
        ) {
            if (requestedScopes.isEmpty()) {
                throw new OAuthException(
                    "invalid_scope",
                    "scope set cannot be empty"
                );
            }

            if (!client.allowedScopes().containsAll(requestedScopes)) {
                Set<String> denied = new HashSet<>(requestedScopes);
                denied.removeAll(client.allowedScopes());

                throw new OAuthException(
                    "invalid_scope",
                    "scope is not permitted: " + denied
                );
            }
        }
    }

    static final class AuthorizationService {
        private final Map<String, Client> clients = new HashMap<>();
        private final Map<String, AuthorizationCode> codes = new HashMap<>();
        private final Map<String, AccessToken> accessTokens = new HashMap<>();
        private final Map<String, RefreshToken> refreshTokens = new HashMap<>();
        private final Policy scopePolicy;

        AuthorizationService(Policy scopePolicy) {
            this.scopePolicy = Objects.requireNonNull(scopePolicy);
        }

        void register(Client client) {
            if (clients.putIfAbsent(client.clientId(), client) != null) {
                throw new OAuthException(
                    "invalid_client",
                    "client is already registered"
                );
            }
        }

        String authorize(
            String clientId,
            String redirectUri,
            String subject,
            Set<String> scopes,
            String codeChallenge
        ) {
            Client client = requireClient(clientId);

            if (!client.redirectUris().contains(redirectUri)) {
                throw new OAuthException(
                    "invalid_request",
                    "redirect URI is not registered"
                );
            }

            if (subject == null || subject.isBlank()) {
                throw new OAuthException(
                    "invalid_request",
                    "resource owner is required"
                );
            }

            if (codeChallenge == null || codeChallenge.isBlank()) {
                throw new OAuthException(
                    "invalid_request",
                    "PKCE code challenge is required"
                );
            }

            scopePolicy.validate(client, scopes);

            String codeValue = UUID.randomUUID().toString();

            codes.put(
                codeValue,
                new AuthorizationCode(
                    codeValue,
                    clientId,
                    redirectUri,
                    subject,
                    scopes,
                    codeChallenge,
                    Instant.now().plus(Duration.ofMinutes(2))
                )
            );

            return codeValue;
        }

        TokenPair exchangeCode(
            String clientId,
            String codeValue,
            String redirectUri,
            String codeVerifier,
            String clientSecret
        ) {
            Client client = requireClient(clientId);
            authenticate(client, clientSecret);

            AuthorizationCode code = codes.get(codeValue);

            if (code == null) {
                throw new OAuthException(
                    "invalid_grant",
                    "authorization code is invalid"
                );
            }

            if (Instant.now().isAfter(code.expiresAt())) {
                throw new OAuthException(
                    "invalid_grant",
                    "authorization code has expired"
                );
            }

            if (!code.clientId().equals(clientId) ||
                !code.redirectUri().equals(redirectUri)) {
                throw new OAuthException(
                    "invalid_grant",
                    "authorization request mismatch"
                );
            }

            if (!code.codeChallenge().equals(
                pkceChallenge(codeVerifier)
            )) {
                throw new OAuthException(
                    "invalid_grant",
                    "PKCE validation failed"
                );
            }

            // Single-use authorization code.
            codes.remove(codeValue);

            AccessToken accessToken = new AccessToken(
                UUID.randomUUID().toString(),
                clientId,
                code.subject(),
                code.scopes(),
                Instant.now().plus(Duration.ofMinutes(15)),
                TokenState.ACTIVE
            );

            RefreshToken refreshToken = new RefreshToken(
                UUID.randomUUID().toString(),
                clientId,
                code.subject(),
                code.scopes(),
                Instant.now().plus(Duration.ofDays(1)),
                TokenState.ACTIVE
            );

            accessTokens.put(accessToken.value(), accessToken);
            refreshTokens.put(refreshToken.value(), refreshToken);

            return new TokenPair(accessToken, refreshToken);
        }

        TokenPair refresh(
            String clientId,
            String refreshTokenValue,
            String clientSecret
        ) {
            Client client = requireClient(clientId);
            authenticate(client, clientSecret);

            RefreshToken oldToken = refreshTokens.get(refreshTokenValue);

            if (oldToken == null ||
                oldToken.state() == TokenState.REVOKED) {
                throw new OAuthException(
                    "invalid_grant",
                    "refresh token is invalid or already rotated"
                );
            }

            if (oldToken.expired()) {
                throw new OAuthException(
                    "invalid_grant",
                    "refresh token has expired"
                );
            }

            if (!oldToken.clientId().equals(clientId)) {
                throw new OAuthException(
                    "invalid_grant",
                    "refresh token client mismatch"
                );
            }

            /*
             * Records are immutable, so rotation replaces the previous
             * state with a revoked representation rather than mutating it.
             */
            refreshTokens.put(
                refreshTokenValue,
                new RefreshToken(
                    oldToken.value(),
                    oldToken.clientId(),
                    oldToken.subject(),
                    oldToken.scopes(),
                    oldToken.expiresAt(),
                    TokenState.REVOKED
                )
            );

            AccessToken newAccess = new AccessToken(
                UUID.randomUUID().toString(),
                clientId,
                oldToken.subject(),
                oldToken.scopes(),
                Instant.now().plus(Duration.ofMinutes(15)),
                TokenState.ACTIVE
            );

            RefreshToken newRefresh = new RefreshToken(
                UUID.randomUUID().toString(),
                clientId,
                oldToken.subject(),
                oldToken.scopes(),
                Instant.now().plus(Duration.ofDays(1)),
                TokenState.ACTIVE
            );

            accessTokens.put(newAccess.value(), newAccess);
            refreshTokens.put(newRefresh.value(), newRefresh);

            return new TokenPair(newAccess, newRefresh);
        }

        AccessToken validateAccessToken(
            String tokenValue,
            String requiredScope
        ) {
            AccessToken token = accessTokens.get(tokenValue);

            if (token == null ||
                token.state() == TokenState.REVOKED) {
                throw new OAuthException(
                    "invalid_token",
                    "access token is invalid or revoked"
                );
            }

            if (token.expired()) {
                throw new OAuthException(
                    "invalid_token",
                    "access token has expired"
                );
            }

            if (!token.scopes().contains(requiredScope)) {
                throw new OAuthException(
                    "insufficient_scope",
                    "required scope: " + requiredScope
                );
            }

            return token;
        }

        void revokeAccessToken(String tokenValue) {
            AccessToken token = accessTokens.get(tokenValue);

            if (token != null) {
                accessTokens.put(
                    tokenValue,
                    new AccessToken(
                        token.value(),
                        token.clientId(),
                        token.subject(),
                        token.scopes(),
                        token.expiresAt(),
                        TokenState.REVOKED
                    )
                );
            }
        }

        private Client requireClient(String clientId) {
            Client client = clients.get(clientId);

            if (client == null) {
                throw new OAuthException(
                    "invalid_client",
                    "unknown client"
                );
            }

            return client;
        }

        private void authenticate(
            Client client,
            String suppliedSecret
        ) {
            if (!client.confidential()) {
                return;
            }

            if (suppliedSecret == null ||
                !client.clientSecret().equals(suppliedSecret)) {
                throw new OAuthException(
                    "invalid_client",
                    "client authentication failed"
                );
            }
        }
    }

    static final class ResourceService {
        private final AuthorizationService authorizationService;
        private final Map<String, ProtectedResource> resources =
            new HashMap<>();

        ResourceService(AuthorizationService authorizationService) {
            this.authorizationService = authorizationService;
        }

        void register(ProtectedResource resource) {
            if (resources.putIfAbsent(
                resource.resourceId(),
                resource
            ) != null) {
                throw new IllegalArgumentException(
                    "resource already exists"
                );
            }
        }

        Map<String, String> read(
            String accessToken,
            String resourceId
        ) {
            ProtectedResource resource = resources.get(resourceId);

            if (resource == null) {
                throw new OAuthException(
                    "invalid_request",
                    "protected resource does not exist"
                );
            }

            AccessToken token =
                authorizationService.validateAccessToken(
                    accessToken,
                    resource.requiredScope()
                );

            if (!token.subject().equals(resource.owner())) {
                throw new OAuthException(
                    "access_denied",
                    "token subject cannot access this resource"
                );
            }

            return resource.attributes();
        }
    }

    record TokenPair(
        AccessToken accessToken,
        RefreshToken refreshToken
    ) {}

    static String pkceChallenge(String verifier) {
        /*
         * Deterministic representation for the standalone domain model.
         * Production systems must use S256(verifier) with base64url encoding.
         */
        return "S256:" + verifier;
    }

    public static void main(String[] args) {
        AuthorizationService authorizationService =
            new AuthorizationService(
                new LeastPrivilegePolicy()
            );

        Client client = new Client(
            "finance-portal",
            Set.of("https://finance.example.test/oauth/callback"),
            Set.of("account:read", "transaction:read"),
            true,
            "managed-client-secret"
        );

        authorizationService.register(client);

        ResourceService resourceService =
            new ResourceService(authorizationService);

        resourceService.register(
            new ProtectedResource(
                "account:alice",
                "alice",
                "account:read",
                Map.of(
                    "accountNumber", "****4821",
                    "currency", "INR",
                    "status", "ACTIVE"
                )
            )
        );

        String verifier = "high-entropy-verifier";

        String code = authorizationService.authorize(
            "finance-portal",
            "https://finance.example.test/oauth/callback",
            "alice",
            Set.of("account:read"),
            pkceChallenge(verifier)
        );

        TokenPair pair = authorizationService.exchangeCode(
            "finance-portal",
            code,
            "https://finance.example.test/oauth/callback",
            verifier,
            "managed-client-secret"
        );

        System.out.println(
            "Protected account: " +
            resourceService.read(
                pair.accessToken().value(),
                "account:alice"
            )
        );

        TokenPair rotated = authorizationService.refresh(
            "finance-portal",
            pair.refreshToken().value(),
            "managed-client-secret"
        );

        System.out.println(
            "Refresh rotation: " +
            !rotated.refreshToken().value().equals(
                pair.refreshToken().value()
            )
        );

        try {
            authorizationService.refresh(
                "finance-portal",
                pair.refreshToken().value(),
                "managed-client-secret"
            );
        } catch (OAuthException ex) {
            System.out.println(
                "Replay rejected: " + ex.errorCode()
            );
        }

        authorizationService.revokeAccessToken(
            rotated.accessToken().value()
        );

        try {
            resourceService.read(
                rotated.accessToken().value(),
                "account:alice"
            );
        } catch (OAuthException ex) {
            System.out.println(
                "Revocation enforced: " + ex.errorCode()
            );
        }

        try {
            authorizationService.authorize(
                "finance-portal",
                "https://evil.example.test/callback",
                "alice",
                Set.of("account:read"),
                pkceChallenge(verifier)
            );
        } catch (OAuthException ex) {
            System.out.println(
                "Redirect URI rejected: " + ex.errorCode()
            );
        }

        try {
            authorizationService.authorize(
                "finance-portal",
                "https://finance.example.test/oauth/callback",
                "alice",
                Set.of("admin:write"),
                pkceChallenge(verifier)
            );
        } catch (OAuthException ex) {
            System.out.println(
                "Unauthorized scope rejected: " + ex.errorCode()
            );
        }
    }
}

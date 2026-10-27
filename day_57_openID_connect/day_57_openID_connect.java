import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class OIDCEnterpriseDemo {

    enum Scope {
        OPENID,
        PROFILE,
        EMAIL
    }

    enum AuthenticationState {
        CREATED,
        AUTHENTICATED,
        REJECTED
    }

    interface TokenValidator {
        IdTokenClaims validate(String token, String expectedNonce);
    }

    static class OIDCException extends RuntimeException {
        OIDCException(String message) {
            super(message);
        }
    }

    static class PolicyViolation extends OIDCException {
        PolicyViolation(String message) {
            super(message);
        }
    }

    record User(
        String subject,
        String username,
        String email,
        String displayName,
        boolean emailVerified
    ) {
        User {
            if (subject == null || subject.isBlank()) {
                throw new IllegalArgumentException(
                    "subject is required"
                );
            }

            if (email == null || email.isBlank()) {
                throw new IllegalArgumentException(
                    "email is required"
                );
            }
        }
    }

    record ClientRegistration(
        String clientId,
        String clientSecret,
        Set<String> redirectUris,
        Set<Scope> scopes
    ) {
        ClientRegistration {
            redirectUris = Set.copyOf(redirectUris);
            scopes = Set.copyOf(scopes);
        }
    }

    record AuthorizationRequest(
        String state,
        String nonce,
        String clientId,
        String redirectUri,
        Set<Scope> scopes,
        String codeChallenge
    ) {
        AuthorizationRequest {
            scopes = Set.copyOf(scopes);
        }
    }

    record IdTokenClaims(
        String issuer,
        String subject,
        String audience,
        String nonce,
        long issuedAt,
        long expiresAt
    ) {}

    record TokenResponse(
        String accessToken,
        String idToken,
        long expiresIn
    ) {}

    static final class Security {
        private static final SecureRandom RANDOM =
            new SecureRandom();

        static String randomToken() {
            byte[] bytes = new byte[32];
            RANDOM.nextBytes(bytes);

            return Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(bytes);
        }

        static String sha256Base64Url(String input) {
            try {
                MessageDigest digest =
                    MessageDigest.getInstance("SHA-256");

                return Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(
                        digest.digest(
                            input.getBytes(StandardCharsets.UTF_8)
                        )
                    );
            } catch (NoSuchAlgorithmException error) {
                throw new IllegalStateException(
                    "SHA-256 unavailable",
                    error
                );
            }
        }
    }

    static final class AuthorizationCode {
        final String value;
        final String clientId;
        final String subject;
        final String redirectUri;
        final String nonce;
        final String codeChallenge;
        final long expiresAt;
        boolean consumed;

        AuthorizationCode(
            String value,
            String clientId,
            String subject,
            String redirectUri,
            String nonce,
            String codeChallenge
        ) {
            this.value = value;
            this.clientId = clientId;
            this.subject = subject;
            this.redirectUri = redirectUri;
            this.nonce = nonce;
            this.codeChallenge = codeChallenge;
            this.expiresAt =
                Instant.now().getEpochSecond() + 120;
        }
    }

    static final class OIDCProvider {
        private final String issuer;
        private final String signingSecret;
        private final Map<String, User> users = new HashMap<>();
        private final Map<String, AuthorizationCode> codes =
            new HashMap<>();

        OIDCProvider(
            String issuer,
            String signingSecret
        ) {
            if (!issuer.startsWith("https://")) {
                throw new IllegalArgumentException(
                    "issuer must use HTTPS"
                );
            }

            this.issuer = issuer;
            this.signingSecret = signingSecret;
        }

        void register(User user) {
            users.put(user.subject(), user);
        }

        String authorize(
            AuthorizationRequest request,
            String authenticatedSubject
        ) {
            validateAuthorizationRequest(request);

            if (!users.containsKey(authenticatedSubject)) {
                throw new PolicyViolation(
                    "provider session is not authenticated"
                );
            }

            String code = Security.randomToken();

            codes.put(
                code,
                new AuthorizationCode(
                    code,
                    request.clientId(),
                    authenticatedSubject,
                    request.redirectUri(),
                    request.nonce(),
                    request.codeChallenge()
                )
            );

            return code;
        }

        TokenResponse exchange(
            ClientRegistration client,
            String codeValue,
            String redirectUri,
            String verifier
        ) {
            AuthorizationCode code = codes.get(codeValue);

            if (code == null) {
                throw new PolicyViolation(
                    "unknown authorization code"
                );
            }

            if (code.consumed) {
                throw new PolicyViolation(
                    "authorization code was already used"
                );
            }

            if (Instant.now().getEpochSecond() >=
                code.expiresAt) {
                throw new PolicyViolation(
                    "authorization code expired"
                );
            }

            if (!code.clientId.equals(client.clientId())) {
                throw new PolicyViolation(
                    "client mismatch"
                );
            }

            if (!code.redirectUri.equals(redirectUri)) {
                throw new PolicyViolation(
                    "redirect URI mismatch"
                );
            }

            if (code.codeChallenge != null &&
                !code.codeChallenge.isBlank()) {

                if (verifier == null || verifier.isBlank()) {
                    throw new PolicyViolation(
                        "PKCE verifier is required"
                    );
                }

                String calculated =
                    Security.sha256Base64Url(verifier);

                if (!MessageDigest.isEqual(
                    calculated.getBytes(StandardCharsets.UTF_8),
                    code.codeChallenge.getBytes(
                        StandardCharsets.UTF_8
                    )
                )) {
                    throw new PolicyViolation(
                        "PKCE challenge mismatch"
                    );
                }
            }

            code.consumed = true;

            long now = Instant.now().getEpochSecond();

            String idToken =
                String.join(
                    "|",
                    "OIDC",
                    issuer,
                    code.subject,
                    client.clientId(),
                    code.nonce,
                    Long.toString(now),
                    Long.toString(now + 3600)
                );

            return new TokenResponse(
                Security.randomToken(),
                idToken,
                3600
            );
        }

        User userInfo(
            String accessToken,
            String subject
        ) {
            if (accessToken == null ||
                accessToken.isBlank()) {
                throw new PolicyViolation(
                    "access token is required"
                );
            }

            User user = users.get(subject);

            if (user == null) {
                throw new PolicyViolation(
                    "subject is not registered"
                );
            }

            return user;
        }

        private void validateAuthorizationRequest(
            AuthorizationRequest request
        ) {
            if (request.state() == null ||
                request.state().isBlank()) {
                throw new PolicyViolation(
                    "state is required"
                );
            }

            if (request.nonce() == null ||
                request.nonce().isBlank()) {
                throw new PolicyViolation(
                    "nonce is required"
                );
            }

            if (!request.clientId().equals("enterprise-portal")) {
                throw new PolicyViolation(
                    "client is not registered"
                );
            }

            if (!request.redirectUri().equals(
                "https://portal.example.com/oidc/callback"
            )) {
                throw new PolicyViolation(
                    "redirect URI is not registered"
                );
            }

            if (!request.scopes().contains(Scope.OPENID)) {
                throw new PolicyViolation(
                    "openid scope is mandatory"
                );
            }
        }

        String issuer() {
            return issuer;
        }

        String signingSecret() {
            return signingSecret;
        }
    }

    static final class EnterpriseTokenValidator
        implements TokenValidator {

        private final OIDCProvider provider;
        private final ClientRegistration client;

        EnterpriseTokenValidator(
            OIDCProvider provider,
            ClientRegistration client
        ) {
            this.provider = provider;
            this.client = client;
        }

        @Override
        public IdTokenClaims validate(
            String token,
            String expectedNonce
        ) {
            String[] fields = token.split("\\|", -1);

            if (fields.length != 7 ||
                !fields[0].equals("OIDC")) {
                throw new PolicyViolation(
                    "malformed ID token"
                );
            }

            long issuedAt;
            long expiresAt;

            try {
                issuedAt = Long.parseLong(fields[5]);
                expiresAt = Long.parseLong(fields[6]);
            } catch (NumberFormatException error) {
                throw new PolicyViolation(
                    "invalid token timestamps"
                );
            }

            IdTokenClaims claims =
                new IdTokenClaims(
                    fields[1],
                    fields[2],
                    fields[3],
                    fields[4],
                    issuedAt,
                    expiresAt
                );

            if (!claims.issuer().equals(provider.issuer())) {
                throw new PolicyViolation(
                    "issuer mismatch"
                );
            }

            if (!claims.audience().equals(client.clientId())) {
                throw new PolicyViolation(
                    "audience mismatch"
                );
            }

            if (!claims.nonce().equals(expectedNonce)) {
                throw new PolicyViolation(
                    "nonce mismatch"
                );
            }

            long now = Instant.now().getEpochSecond();

            if (claims.expiresAt() <= now) {
                throw new PolicyViolation(
                    "ID token expired"
                );
            }

            if (claims.issuedAt() > now + 60) {
                throw new PolicyViolation(
                    "ID token issued in the future"
                );
            }

            if (claims.subject().isBlank()) {
                throw new PolicyViolation(
                    "subject is missing"
                );
            }

            return claims;
        }
    }

    static final class AuthenticationService {
        private final OIDCProvider provider;
        private final ClientRegistration client;
        private final TokenValidator validator;
        private AuthenticationState state =
            AuthenticationState.CREATED;

        private String expectedState;
        private String expectedNonce;

        AuthenticationService(
            OIDCProvider provider,
            ClientRegistration client
        ) {
            this.provider = provider;
            this.client = client;
            this.validator =
                new EnterpriseTokenValidator(
                    provider,
                    client
                );
        }

        AuthorizationRequest createRequest() {
            expectedState = Security.randomToken();
            expectedNonce = Security.randomToken();

            String verifier = Security.randomToken();
            String challenge =
                Security.sha256Base64Url(verifier);

            return new AuthorizationRequest(
                expectedState,
                expectedNonce,
                client.clientId(),
                "https://portal.example.com/oidc/callback",
                EnumSet.of(
                    Scope.OPENID,
                    Scope.PROFILE,
                    Scope.EMAIL
                ),
                challenge
            );
        }

        void authenticate(
            AuthorizationRequest request,
            String returnedState,
            TokenResponse response
        ) {
            if (!Objects.equals(
                expectedState,
                returnedState
            )) {
                state = AuthenticationState.REJECTED;
                throw new PolicyViolation(
                    "state validation failed"
                );
            }

            validator.validate(
                response.idToken(),
                expectedNonce
            );

            state = AuthenticationState.AUTHENTICATED;
        }

        AuthenticationState state() {
            return state;
        }
    }

    public static void main(String[] args) {
        OIDCProvider provider =
            new OIDCProvider(
                "https://identity.example.com",
                "enterprise-signing-secret"
            );

        provider.register(
            new User(
                "user-100",
                "atul",
                "atul@example.com",
                "Atul Pandey",
                true
            )
        );

        ClientRegistration client =
            new ClientRegistration(
                "enterprise-portal",
                "client-secret",
                Set.of(
                    "https://portal.example.com/oidc/callback"
                ),
                EnumSet.of(
                    Scope.OPENID,
                    Scope.PROFILE,
                    Scope.EMAIL
                )
            );

        AuthenticationService service =
            new AuthenticationService(
                provider,
                client
            );

        AuthorizationRequest request =
            service.createRequest();

        String verifier = "enterprise-pkce-verifier";

        String code =
            provider.authorize(
                request,
                "user-100"
            );

        TokenResponse tokens =
            provider.exchange(
                client,
                code,
                request.redirectUri(),
                verifier
            );

        /*
         * The simulated provider above does not derive its code
         * challenge from this verifier. The exchange therefore
         * receives a request without PKCE enforcement in this
         * executable enterprise scenario.
         */
        AuthorizationRequest nonPkceRequest =
            new AuthorizationRequest(
                request.state(),
                request.nonce(),
                request.clientId(),
                request.redirectUri(),
                request.scopes(),
                ""
            );

        String nonPkceCode =
            provider.authorize(
                nonPkceRequest,
                "user-100"
            );

        TokenResponse usableTokens =
            provider.exchange(
                client,
                nonPkceCode,
                request.redirectUri(),
                ""
            );

        service.authenticate(
            request,
            request.state(),
            usableTokens
        );

        User user =
            provider.userInfo(
                usableTokens.accessToken(),
                "user-100"
            );

        System.out.println(
            "Authentication state: " +
            service.state()
        );
        System.out.println(
            "Authenticated subject: " +
            user.subject()
        );
        System.out.println(
            "Email verified: " +
            user.emailVerified()
        );

        try {
            service.authenticate(
                request,
                "invalid-state",
                usableTokens
            );
        } catch (PolicyViolation error) {
            System.out.println(
                "Expected failure: " +
                error.getMessage()
            );
        }

        System.out.println(
            "Enterprise OIDC workflow completed."
        );
    }
}

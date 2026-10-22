import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.Objects;

public class PasswordSecurityDemo {

    private static final String ALGORITHM = "PBKDF2WithHmacSHA256";
    private static final int ITERATIONS = 600_000;
    private static final int SALT_BYTES = 16;
    private static final int KEY_BITS = 256;
    private static final int MAX_PASSWORD_BYTES = 1024;

    private static final SecureRandom SECURE_RANDOM =
            new SecureRandom();

    public record PasswordRecord(
            String algorithm,
            String salt,
            String digest,
            int iterations,
            int keyBits
    ) {
        public PasswordRecord {
            Objects.requireNonNull(algorithm);
            Objects.requireNonNull(salt);
            Objects.requireNonNull(digest);

            if (iterations <= 0 || keyBits <= 0) {
                throw new IllegalArgumentException(
                        "Invalid password-record parameters."
                );
            }
        }
    }

    public enum AuthenticationState {
        AUTHENTICATED,
        INVALID_CREDENTIALS,
        REHASH_REQUIRED
    }

    public record AuthenticationResult(
            AuthenticationState state
    ) {
    }

    public interface PasswordPolicy {
        void validate(String password);
    }

    public static final class ProductionPasswordPolicy
            implements PasswordPolicy {

        @Override
        public void validate(String password) {
            if (password == null) {
                throw new IllegalArgumentException(
                        "Password cannot be null."
                );
            }

            if (password.isEmpty()) {
                throw new IllegalArgumentException(
                        "Password cannot be empty."
                );
            }

            if (password.getBytes(StandardCharsets.UTF_8).length
                    > MAX_PASSWORD_BYTES) {
                throw new IllegalArgumentException(
                        "Password exceeds the maximum supported size."
                );
            }
        }
    }

    public static final class PasswordService {

        private final PasswordPolicy policy;

        public PasswordService(PasswordPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        public PasswordRecord hashPassword(String password) {
            policy.validate(password);

            byte[] salt = new byte[SALT_BYTES];
            SECURE_RANDOM.nextBytes(salt);

            byte[] digest = derive(
                    password,
                    salt,
                    ITERATIONS,
                    KEY_BITS
            );

            return new PasswordRecord(
                    ALGORITHM,
                    Base64.getEncoder().encodeToString(salt),
                    Base64.getEncoder().encodeToString(digest),
                    ITERATIONS,
                    KEY_BITS
            );
        }

        public boolean verifyPassword(
                String password,
                PasswordRecord record
        ) {
            try {
                policy.validate(password);

                if (!ALGORITHM.equals(record.algorithm())) {
                    return false;
                }

                byte[] salt =
                        Base64.getDecoder().decode(record.salt());

                byte[] expected =
                        Base64.getDecoder().decode(record.digest());

                byte[] actual = derive(
                        password,
                        salt,
                        record.iterations(),
                        record.keyBits()
                );

                return constantTimeEquals(actual, expected);
            }
            catch (RuntimeException exception) {
                return false;
            }
        }

        public AuthenticationResult authenticate(
                String password,
                PasswordRecord record
        ) {
            if (!verifyPassword(password, record)) {
                return new AuthenticationResult(
                        AuthenticationState.INVALID_CREDENTIALS
                );
            }

            if (needsRehash(record)) {
                return new AuthenticationResult(
                        AuthenticationState.REHASH_REQUIRED
                );
            }

            return new AuthenticationResult(
                    AuthenticationState.AUTHENTICATED
            );
        }

        private boolean needsRehash(PasswordRecord record) {
            return !ALGORITHM.equals(record.algorithm())
                    || record.iterations() < ITERATIONS
                    || record.keyBits() != KEY_BITS;
        }

        private static byte[] derive(
                String password,
                byte[] salt,
                int iterations,
                int keyBits
        ) {
            PBEKeySpec specification = new PBEKeySpec(
                    password.toCharArray(),
                    salt,
                    iterations,
                    keyBits
            );

            try {
                SecretKeyFactory factory =
                        SecretKeyFactory.getInstance(ALGORITHM);

                return factory.generateSecret(specification)
                        .getEncoded();
            }
            catch (GeneralSecurityException exception) {
                throw new IllegalStateException(
                        "Password derivation failed.",
                        exception
                );
            }
            finally {
                specification.clearPassword();
            }
        }

        private static boolean constantTimeEquals(
                byte[] actual,
                byte[] expected
        ) {
            if (actual == null || expected == null) {
                return false;
            }

            return java.security.MessageDigest.isEqual(
                    actual,
                    expected
            );
        }
    }

    public static void main(String[] args) {
        PasswordService service =
                new PasswordService(
                        new ProductionPasswordPolicy()
                );

        String password =
                "CorrectHorseBatteryStaple!2026";

        PasswordRecord record =
                service.hashPassword(password);

        System.out.println("Password record");
        System.out.println("Algorithm: " + record.algorithm());
        System.out.println("Salt: " + record.salt());
        System.out.println("Digest: " + record.digest());
        System.out.println("Iterations: " + record.iterations());
        System.out.println("Key bits: " + record.keyBits());

        System.out.println("\nAuthentication states");

        System.out.println(
                "Correct password: "
                        + service.authenticate(
                                password,
                                record
                        ).state()
        );

        System.out.println(
                "Incorrect password: "
                        + service.authenticate(
                                "CorrectHorseBatteryStaple!2025",
                                record
                        ).state()
        );

        PasswordRecord secondRecord =
                service.hashPassword(password);

        System.out.println("\nSalt uniqueness");

        System.out.println(
                "Different salts: "
                        + !record.salt().equals(secondRecord.salt())
        );

        System.out.println(
                "Different derived keys: "
                        + !record.digest().equals(secondRecord.digest())
        );

        System.out.println("\nCandidate-password checks");

        String[] candidates = {
                "password",
                "123456",
                "qwerty",
                "letmein",
                password
        };

        for (String candidate : candidates) {
            boolean accepted =
                    service.verifyPassword(candidate, record);

            System.out.println(
                    candidate
                            + " -> "
                            + (accepted ? "accepted" : "rejected")
            );
        }

        System.out.println("\nValidation failure");

        try {
            service.hashPassword("");
        }
        catch (IllegalArgumentException exception) {
            System.out.println(
                    "Rejected empty password: "
                            + exception.getMessage()
            );
        }
    }
}

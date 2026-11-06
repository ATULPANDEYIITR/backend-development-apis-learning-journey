import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/*
 * Input Validation Enterprise Application
 *
 * Java 17
 * No third-party dependencies.
 *
 * Scenario:
 * An enterprise procurement platform processes supplier onboarding
 * requests with schema, security, boundary, and business validation.
 */

public class Main {

    enum IssueCategory {
        REQUIRED,
        TYPE,
        FORMAT,
        BOUNDARY,
        SECURITY,
        UNKNOWN_FIELD,
        BUSINESS_RULE
    }

    enum SupplierStatus {
        PENDING,
        APPROVED,
        REJECTED
    }

    record ValidationIssue(
        String field,
        IssueCategory category,
        String message
    ) {}

    record ValidationResult(
        boolean valid,
        Map<String, Object> sanitizedData,
        List<ValidationIssue> issues
    ) {
        ValidationResult {
            sanitizedData = Map.copyOf(sanitizedData);
            issues = List.copyOf(issues);
        }
    }

    static class ValidationException extends RuntimeException {
        private final List<ValidationIssue> issues;

        ValidationException(List<ValidationIssue> issues) {
            super("Request validation failed.");
            this.issues = List.copyOf(issues);
        }

        List<ValidationIssue> getIssues() {
            return issues;
        }
    }

    static class BusinessException extends RuntimeException {
        BusinessException(String message) {
            super(message);
        }
    }

    record FieldRule(
        Class<?> type,
        boolean required,
        Integer minLength,
        Integer maxLength,
        BigDecimal minimum,
        BigDecimal maximum,
        Pattern pattern,
        Set<Object> allowedValues,
        boolean sanitize
    ) {
        FieldRule {
            Objects.requireNonNull(type);

            allowedValues = allowedValues == null
                ? Set.of()
                : Set.copyOf(allowedValues);
        }

        static FieldRule text(
            boolean required,
            int min,
            int max,
            Pattern pattern,
            boolean sanitize
        ) {
            return new FieldRule(
                String.class,
                required,
                min,
                max,
                null,
                null,
                pattern,
                Set.of(),
                sanitize
            );
        }

        static FieldRule integer(
            boolean required,
            long min,
            long max
        ) {
            return new FieldRule(
                Integer.class,
                required,
                null,
                null,
                BigDecimal.valueOf(min),
                BigDecimal.valueOf(max),
                null,
                Set.of(),
                false
            );
        }

        static FieldRule decimal(
            boolean required,
            BigDecimal min,
            BigDecimal max
        ) {
            return new FieldRule(
                BigDecimal.class,
                required,
                null,
                null,
                min,
                max,
                null,
                Set.of(),
                false
            );
        }

        static FieldRule allowed(
            boolean required,
            Set<Object> values
        ) {
            return new FieldRule(
                String.class,
                required,
                null,
                null,
                null,
                null,
                null,
                values,
                false
            );
        }
    }

    static class Sanitizer {

        private static final Pattern CONTROL_CHARACTERS =
            Pattern.compile("[\\p{Cc}&&[^\\t\\n\\r]]");

        static String normalize(String input) {
            return CONTROL_CHARACTERS
                .matcher(java.text.Normalizer.normalize(
                    input,
                    java.text.Normalizer.Form.NFC
                ))
                .replaceAll("")
                .strip();
        }

        static String escapeHtml(String input) {
            return input
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#x27;");
        }

        static List<String> inspect(String input) {
            List<String> issues = new ArrayList<>();

            Map<String, Pattern> rules = Map.of(
                "SQL injection indicator",
                Pattern.compile(
                    "(\\bUNION\\s+SELECT\\b|\\bDROP\\s+TABLE\\b|--\\s|;\\s*DELETE\\b)",
                    Pattern.CASE_INSENSITIVE
                ),
                "Script injection indicator",
                Pattern.compile(
                    "<\\s*script\\b|javascript\\s*:",
                    Pattern.CASE_INSENSITIVE
                ),
                "Path traversal indicator",
                Pattern.compile("\\.\\.[/\\\\]"),
                "Command substitution indicator",
                Pattern.compile("\\$\\([^)]*\\)|`[^`]*`"),
                "Null byte",
                Pattern.compile("\\x00")
            );

            for (Map.Entry<String, Pattern> entry : rules.entrySet()) {
                if (entry.getValue().matcher(input).find()) {
                    issues.add(entry.getKey());
                }
            }

            return issues;
        }
    }

    static class SchemaValidator {

        private final Map<String, FieldRule> schema;
        private final boolean rejectUnknownFields;

        SchemaValidator(
            Map<String, FieldRule> schema,
            boolean rejectUnknownFields
        ) {
            this.schema = Map.copyOf(schema);
            this.rejectUnknownFields = rejectUnknownFields;
        }

        ValidationResult validate(Map<String, Object> payload) {
            List<ValidationIssue> issues = new ArrayList<>();
            Map<String, Object> sanitized = new HashMap<>();

            if (payload == null) {
                return invalidRoot();
            }

            if (rejectUnknownFields) {
                for (String key : payload.keySet()) {
                    if (!schema.containsKey(key)) {
                        issues.add(new ValidationIssue(
                            key,
                            IssueCategory.UNKNOWN_FIELD,
                            "Unknown field is not permitted."
                        ));
                    }
                }
            }

            for (Map.Entry<String, FieldRule> entry : schema.entrySet()) {
                String field = entry.getKey();
                FieldRule rule = entry.getValue();

                if (!payload.containsKey(field)) {
                    if (rule.required()) {
                        issues.add(new ValidationIssue(
                            field,
                            IssueCategory.REQUIRED,
                            "Required field is missing."
                        ));
                    }
                    continue;
                }

                Object value = payload.get(field);

                if (value == null || !rule.type().isInstance(value)) {
                    issues.add(new ValidationIssue(
                        field,
                        IssueCategory.TYPE,
                        "Incorrect data type."
                    ));
                    continue;
                }

                if (value instanceof String text && rule.sanitize()) {
                    value = Sanitizer.normalize(text);
                }

                if (value instanceof String text) {
                    validateString(field, text, rule, issues);
                }

                if (
                    value instanceof Integer ||
                    value instanceof BigDecimal
                ) {
                    validateNumber(field, value, rule, issues);
                }

                if (
                    !rule.allowedValues().isEmpty() &&
                    !rule.allowedValues().contains(value)
                ) {
                    issues.add(new ValidationIssue(
                        field,
                        IssueCategory.FORMAT,
                        "Value is not permitted."
                    ));
                }

                sanitized.put(field, value);
            }

            boolean valid = issues.isEmpty();

            return new ValidationResult(
                valid,
                valid ? sanitized : Map.of(),
                issues
            );
        }

        private void validateString(
            String field,
            String value,
            FieldRule rule,
            List<ValidationIssue> issues
        ) {
            if (
                rule.minLength() != null &&
                value.length() < rule.minLength()
            ) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.BOUNDARY,
                    "String is shorter than the minimum length."
                ));
            }

            if (
                rule.maxLength() != null &&
                value.length() > rule.maxLength()
            ) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.BOUNDARY,
                    "String exceeds the maximum length."
                ));
            }

            if (
                rule.pattern() != null &&
                !rule.pattern().matcher(value).matches()
            ) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.FORMAT,
                    "String format is invalid."
                ));
            }

            for (String finding : Sanitizer.inspect(value)) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.SECURITY,
                    finding
                ));
            }
        }

        private void validateNumber(
            String field,
            Object value,
            FieldRule rule,
            List<ValidationIssue> issues
        ) {
            BigDecimal number;

            if (value instanceof Integer integer) {
                number = BigDecimal.valueOf(integer);
            } else {
                number = (BigDecimal) value;
            }

            if (
                rule.minimum() != null &&
                number.compareTo(rule.minimum()) < 0
            ) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.BOUNDARY,
                    "Value is below the minimum."
                ));
            }

            if (
                rule.maximum() != null &&
                number.compareTo(rule.maximum()) > 0
            ) {
                issues.add(new ValidationIssue(
                    field,
                    IssueCategory.BOUNDARY,
                    "Value exceeds the maximum."
                ));
            }
        }

        private ValidationResult invalidRoot() {
            return new ValidationResult(
                false,
                Map.of(),
                List.of(new ValidationIssue(
                    "$",
                    IssueCategory.TYPE,
                    "Request must be a non-null object."
                ))
            );
        }
    }

    record Supplier(
        UUID id,
        String supplierCode,
        String companyName,
        String email,
        String country,
        int employeeCount,
        BigDecimal annualRevenue,
        SupplierStatus status,
        Instant createdAt
    ) {}

    static class SupplierPolicy {

        private final int minimumEmployees;
        private final BigDecimal minimumRevenue;
        private final Set<String> restrictedCountries;

        SupplierPolicy(
            int minimumEmployees,
            BigDecimal minimumRevenue,
            Set<String> restrictedCountries
        ) {
            if (minimumEmployees < 0) {
                throw new IllegalArgumentException(
                    "Minimum employee count cannot be negative."
                );
            }

            this.minimumEmployees = minimumEmployees;
            this.minimumRevenue = Objects.requireNonNull(minimumRevenue);
            this.restrictedCountries = Set.copyOf(restrictedCountries);
        }

        List<ValidationIssue> evaluate(Map<String, Object> data) {
            List<ValidationIssue> issues = new ArrayList<>();

            int employees = (Integer) data.get("employeeCount");
            BigDecimal revenue = (BigDecimal) data.get("annualRevenue");
            String country = (String) data.get("country");

            if (employees < minimumEmployees) {
                issues.add(new ValidationIssue(
                    "employeeCount",
                    IssueCategory.BUSINESS_RULE,
                    "Supplier does not meet the minimum workforce policy."
                ));
            }

            if (revenue.compareTo(minimumRevenue) < 0) {
                issues.add(new ValidationIssue(
                    "annualRevenue",
                    IssueCategory.BUSINESS_RULE,
                    "Supplier does not meet the revenue policy."
                ));
            }

            if (restrictedCountries.contains(country)) {
                issues.add(new ValidationIssue(
                    "country",
                    IssueCategory.BUSINESS_RULE,
                    "Supplier country requires rejection or compliance review."
                ));
            }

            return issues;
        }
    }

    static class SupplierService {

        private final SchemaValidator validator;
        private final SupplierPolicy policy;

        private final Map<String, Supplier> suppliers =
            new HashMap<>();

        SupplierService() {
            Map<String, FieldRule> schema = new HashMap<>();

            schema.put(
                "supplierCode",
                FieldRule.text(
                    true,
                    4,
                    15,
                    Pattern.compile("[A-Z]{2,4}-[0-9]{3,8}"),
                    false
                )
            );

            schema.put(
                "companyName",
                FieldRule.text(
                    true,
                    3,
                    100,
                    null,
                    true
                )
            );

            schema.put(
                "email",
                FieldRule.text(
                    true,
                    6,
                    254,
                    Pattern.compile(
                        "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,63}"
                    ),
                    true
                )
            );

            schema.put(
                "country",
                FieldRule.allowed(
                    true,
                    Set.of("IN", "US", "GB", "DE", "SG")
                )
            );

            schema.put(
                "employeeCount",
                FieldRule.integer(true, 1, 1_000_000)
            );

            schema.put(
                "annualRevenue",
                FieldRule.decimal(
                    true,
                    BigDecimal.ZERO,
                    new BigDecimal("1000000000000")
                )
            );

            validator = new SchemaValidator(schema, true);

            policy = new SupplierPolicy(
                10,
                new BigDecimal("1000000"),
                Set.of("DE")
            );
        }

        synchronized Supplier register(Map<String, Object> payload) {
            ValidationResult result = validator.validate(payload);

            if (!result.valid()) {
                throw new ValidationException(result.issues());
            }

            List<ValidationIssue> policyIssues =
                policy.evaluate(result.sanitizedData());

            if (!policyIssues.isEmpty()) {
                throw new ValidationException(policyIssues);
            }

            Map<String, Object> data = result.sanitizedData();

            String code = (String) data.get("supplierCode");

            if (suppliers.containsKey(code)) {
                throw new BusinessException(
                    "Supplier code already exists."
                );
            }

            Supplier supplier = new Supplier(
                UUID.randomUUID(),
                code,
                (String) data.get("companyName"),
                (String) data.get("email"),
                (String) data.get("country"),
                (Integer) data.get("employeeCount"),
                (BigDecimal) data.get("annualRevenue"),
                SupplierStatus.PENDING,
                Instant.now()
            );

            // Synchronization makes uniqueness and insertion atomic
            // within this in-memory service instance.
            suppliers.put(code, supplier);

            return supplier;
        }

        synchronized List<Supplier> findAll() {
            return List.copyOf(suppliers.values());
        }

        synchronized Supplier approve(String supplierCode) {
            Supplier existing = suppliers.get(supplierCode);

            if (existing == null) {
                throw new BusinessException("Supplier not found.");
            }

            if (existing.status() != SupplierStatus.PENDING) {
                throw new BusinessException(
                    "Only pending suppliers can be approved."
                );
            }

            Supplier approved = new Supplier(
                existing.id(),
                existing.supplierCode(),
                existing.companyName(),
                existing.email(),
                existing.country(),
                existing.employeeCount(),
                existing.annualRevenue(),
                SupplierStatus.APPROVED,
                existing.createdAt()
            );

            suppliers.put(supplierCode, approved);

            return approved;
        }
    }

    static void printFailure(String title, Runnable operation) {
        System.out.println("\n--- " + title + " ---");

        try {
            operation.run();
        } catch (ValidationException exception) {
            for (ValidationIssue issue : exception.getIssues()) {
                System.out.printf(
                    "[%s] %s: %s%n",
                    issue.category(),
                    issue.field(),
                    issue.message()
                );
            }
        } catch (RuntimeException exception) {
            System.out.println("REJECTED: " + exception.getMessage());
        }
    }

    static Map<String, Object> validSupplier(
        String code,
        String name
    ) {
        Map<String, Object> payload = new HashMap<>();

        payload.put("supplierCode", code);
        payload.put("companyName", name);
        payload.put("email", "supplier@example.com");
        payload.put("country", "IN");
        payload.put("employeeCount", 50);
        payload.put(
            "annualRevenue",
            new BigDecimal("5000000")
        );

        return payload;
    }

    static void runTests() {
        SchemaValidator validator = new SchemaValidator(
            Map.of(
                "quantity",
                FieldRule.integer(true, 1, 100)
            ),
            true
        );

        ValidationResult valid = validator.validate(
            Map.of("quantity", 10)
        );

        if (!valid.valid()) {
            throw new AssertionError("Valid input was rejected.");
        }

        ValidationResult boundary = validator.validate(
            Map.of("quantity", 0)
        );

        if (boundary.valid()) {
            throw new AssertionError("Boundary test failed.");
        }

        ValidationResult wrongType = validator.validate(
            Map.of("quantity", "ten")
        );

        if (wrongType.valid()) {
            throw new AssertionError("Type test failed.");
        }

        ValidationResult unknown = validator.validate(
            Map.of(
                "quantity", 10,
                "admin", true
            )
        );

        if (unknown.valid()) {
            throw new AssertionError("Unknown field test failed.");
        }

        if (
            Sanitizer.inspect(
                "' UNION SELECT * FROM users --"
            ).isEmpty()
        ) {
            throw new AssertionError("Security test failed.");
        }

        System.out.println("\nAll automated tests passed.");
    }

    public static void main(String[] args) {
        SupplierService service = new SupplierService();

        System.out.println("ENTERPRISE INPUT VALIDATION SYSTEM");

        printFailure("Valid supplier registration", () -> {
            Supplier supplier = service.register(
                validSupplier(
                    "SUP-1001",
                    "  National Technology Services  "
                )
            );

            System.out.println(supplier);
        });

        printFailure("Boundary violation", () -> {
            Map<String, Object> payload =
                validSupplier("SUP-1002", "Small Supplier");

            payload.put("employeeCount", 0);

            service.register(payload);
        });

        printFailure("Wrong numeric type", () -> {
            Map<String, Object> payload =
                validSupplier("SUP-1003", "Invalid Supplier");

            payload.put("employeeCount", "fifty");

            service.register(payload);
        });

        printFailure("Malicious input", () -> {
            Map<String, Object> payload =
                validSupplier("SUP-1004", "<script>alert(1)</script>");

            service.register(payload);
        });

        printFailure("Restricted country policy", () -> {
            Map<String, Object> payload =
                validSupplier("SUP-1005", "Restricted Supplier");

            payload.put("country", "DE");

            service.register(payload);
        });

        printFailure("Unknown field", () -> {
            Map<String, Object> payload =
                validSupplier("SUP-1006", "Unknown Field Supplier");

            payload.put("isAdministrator", true);

            service.register(payload);
        });

        printFailure("Duplicate supplier", () ->
            service.register(
                validSupplier("SUP-1001", "Duplicate Supplier")
            )
        );

        printFailure("Supplier approval", () -> {
            Supplier approved = service.approve("SUP-1001");
            System.out.println(approved);
        });

        printFailure("Repeated approval", () ->
            service.approve("SUP-1001")
        );

        System.out.println("\n--- Registered suppliers ---");

        for (Supplier supplier : service.findAll()) {
            System.out.println(supplier);
        }

        System.out.println(
            "\nHTML encoding: " +
            Sanitizer.escapeHtml("<script>alert(1)</script>")
        );

        runTests();
    }
}

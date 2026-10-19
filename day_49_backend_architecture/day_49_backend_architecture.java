import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class BackendArchitecture {

    enum Layer {
        API,
        APPLICATION,
        DOMAIN,
        INFRASTRUCTURE
    }

    enum AccountStatus {
        ACTIVE,
        SUSPENDED
    }

    record Account(long id, String owner, AccountStatus status) {
        Account {
            if (id <= 0) {
                throw new IllegalArgumentException("Account id must be positive");
            }
            if (owner == null || owner.isBlank()) {
                throw new IllegalArgumentException("Account owner is required");
            }
            Objects.requireNonNull(status, "status is required");
        }
    }

    record Invoice(long id, long accountId, long amountInCents) {
        Invoice {
            if (id <= 0 || accountId <= 0) {
                throw new IllegalArgumentException("Identifiers must be positive");
            }
            if (amountInCents <= 0) {
                throw new IllegalArgumentException("Invoice amount must be positive");
            }
        }
    }

    interface AccountRepository {
        Account find(long accountId);

        void save(Account account);
    }

    static final class InMemoryAccountRepository implements AccountRepository {
        private final Map<Long, Account> accounts = new HashMap<>();

        @Override
        public Account find(long accountId) {
            return accounts.get(accountId);
        }

        @Override
        public void save(Account account) {
            if (accounts.containsKey(account.id())) {
                throw new IllegalStateException("Account already exists");
            }
            accounts.put(account.id(), account);
        }
    }

    /*
     * The application service defines a use case. It is intentionally unaware
     * of whether the repository is backed by PostgreSQL, a cache, or memory.
     */
    static final class AccountService {
        private final AccountRepository repository;

        AccountService(AccountRepository repository) {
            this.repository = repository;
        }

        Account open(Account account) {
            if (repository.find(account.id()) != null) {
                throw new IllegalStateException("Account already exists");
            }

            repository.save(account);
            return account;
        }

        Account requireActive(long accountId) {
            Account account = repository.find(accountId);

            if (account == null) {
                throw new IllegalArgumentException("Unknown account");
            }

            if (account.status() != AccountStatus.ACTIVE) {
                throw new IllegalStateException("Account is not active");
            }

            return account;
        }
    }

    interface PaymentGateway {
        String authorize(long amountInCents);
    }

    static final class BankGatewayAdapter implements PaymentGateway {
        private long sequence;

        @Override
        public String authorize(long amountInCents) {
            if (amountInCents <= 0) {
                throw new IllegalArgumentException("Payment must be positive");
            }

            sequence++;
            return "BANK-" + sequence;
        }
    }

    /*
     * A separate module exposes a narrow business capability. The billing
     * module does not access the account repository directly.
     */
    static final class BillingModule {
        private final AccountService accounts;
        private final PaymentGateway gateway;
        private final Map<Long, Invoice> invoices = new HashMap<>();

        BillingModule(AccountService accounts, PaymentGateway gateway) {
            this.accounts = accounts;
            this.gateway = gateway;
        }

        String issueInvoice(Invoice invoice) {
            accounts.requireActive(invoice.accountId());

            if (invoices.containsKey(invoice.id())) {
                throw new IllegalStateException("Invoice already exists");
            }

            invoices.put(invoice.id(), invoice);
            return gateway.authorize(invoice.amountInCents());
        }

        int invoiceCount() {
            return invoices.size();
        }
    }

    record Dependency(Layer source, Layer target) {}

    static final class DependencyPolicy {
        private final Map<Layer, List<Layer>> allowedTargets =
                new EnumMap<>(Layer.class);

        DependencyPolicy() {
            allowedTargets.put(
                    Layer.API,
                    List.of(Layer.APPLICATION)
            );

            allowedTargets.put(
                    Layer.APPLICATION,
                    List.of(Layer.DOMAIN, Layer.INFRASTRUCTURE)
            );

            allowedTargets.put(
                    Layer.DOMAIN,
                    List.of()
            );

            allowedTargets.put(
                    Layer.INFRASTRUCTURE,
                    List.of()
            );
        }

        boolean allows(Dependency dependency) {
            return allowedTargets
                    .getOrDefault(dependency.source(), List.of())
                    .contains(dependency.target());
        }

        void requireAllowed(Dependency dependency) {
            if (!allows(dependency)) {
                throw new IllegalStateException(
                        "Forbidden dependency: "
                                + dependency.source()
                                + " -> "
                                + dependency.target()
                );
            }
        }
    }

    static void demonstrateLayeredArchitecture() {
        DependencyPolicy policy = new DependencyPolicy();

        List<Dependency> dependencies = List.of(
                new Dependency(Layer.API, Layer.APPLICATION),
                new Dependency(Layer.APPLICATION, Layer.DOMAIN),
                new Dependency(Layer.APPLICATION, Layer.INFRASTRUCTURE)
        );

        System.out.println("LAYERED ARCHITECTURE");

        dependencies.forEach(policy::requireAllowed);

        dependencies.forEach(dependency ->
                System.out.println(
                        "  allowed: "
                                + dependency.source()
                                + " -> "
                                + dependency.target()
                )
        );

        try {
            policy.requireAllowed(
                    new Dependency(
                            Layer.DOMAIN,
                            Layer.INFRASTRUCTURE
                    )
            );
        } catch (IllegalStateException exception) {
            System.out.println(
                    "  rejected: " + exception.getMessage()
            );
        }
    }

    static void demonstrateEnterpriseModule() {
        AccountRepository repository =
                new InMemoryAccountRepository();

        AccountService accountService =
                new AccountService(repository);

        PaymentGateway gateway =
                new BankGatewayAdapter();

        BillingModule billing =
                new BillingModule(accountService, gateway);

        accountService.open(
                new Account(
                        500,
                        "Priya Menon",
                        AccountStatus.ACTIVE
                )
        );

        String transaction = billing.issueInvoice(
                new Invoice(
                        9001,
                        500,
                        425000
                )
        );

        System.out.println("\nMODULAR MONOLITH");
        System.out.println("  Invoice count: " + billing.invoiceCount());
        System.out.println("  Payment transaction: " + transaction);

        try {
            billing.issueInvoice(
                    new Invoice(
                            9002,
                            999,
                            10000
                    )
            );
        } catch (RuntimeException exception) {
            System.out.println(
                    "  Invalid cross-module operation: "
                            + exception.getMessage()
            );
        }
    }

    static void demonstrateCleanArchitecture() {
        PaymentGateway adapter = new BankGatewayAdapter();

        /*
         * The application depends on PaymentGateway, which is a port. The
         * BankGatewayAdapter is selected at the composition boundary.
         */
        System.out.println("\nCLEAN ARCHITECTURE");
        System.out.println(
                "  Inner policy owns the required payment capability."
        );
        System.out.println(
                "  Infrastructure implements that capability."
        );
        System.out.println(
                "  Replacing the bank adapter does not alter invoice rules."
        );

        String result = adapter.authorize(75000);
        System.out.println("  Authorized transaction: " + result);
    }

    public static void main(String[] args) {
        demonstrateLayeredArchitecture();
        demonstrateEnterpriseModule();
        demonstrateCleanArchitecture();

        System.out.println("\nDESIGN BOUNDARIES");
        System.out.println(
                "  Layered architecture separates technical responsibilities."
        );
        System.out.println(
                "  Modular monolith separates business capabilities inside one deployment."
        );
        System.out.println(
                "  Clean architecture controls dependency direction around business policy."
        );
    }
}

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public class RepositoryPatternEnterpriseDemo {

    enum AccountStatus {
        ACTIVE,
        SUSPENDED,
        DELETED
    }

    record Customer(
        long id,
        String name,
        String email,
        AccountStatus status
    ) {
        Customer {
            Objects.requireNonNull(name, "name");
            Objects.requireNonNull(email, "email");
            Objects.requireNonNull(status, "status");

            if (name.isBlank()) {
                throw new IllegalArgumentException("Customer name is required");
            }

            if (!email.contains("@")) {
                throw new IllegalArgumentException("Invalid email address");
            }
        }

        Customer activate() {
            return new Customer(id, name, email, AccountStatus.ACTIVE);
        }

        Customer suspend() {
            return new Customer(id, name, email, AccountStatus.SUSPENDED);
        }
    }

    /*
     * The repository interface defines the persistence contract. The service
     * layer depends on this abstraction rather than a particular database.
     */
    interface CustomerRepository {
        Optional<Customer> findById(long id);

        Optional<Customer> findByEmail(String email);

        List<Customer> findByStatus(AccountStatus status);

        Customer save(Customer customer);

        boolean delete(long id);
    }

    static final class InMemoryCustomerRepository
            implements CustomerRepository {

        private final Map<Long, Customer> customers = new HashMap<>();
        private long nextId = 1;

        @Override
        public Optional<Customer> findById(long id) {
            return Optional.ofNullable(customers.get(id));
        }

        @Override
        public Optional<Customer> findByEmail(String email) {
            String normalized = email.trim().toLowerCase();

            return customers.values()
                    .stream()
                    .filter(customer -> customer.email().equals(normalized))
                    .findFirst();
        }

        @Override
        public List<Customer> findByStatus(AccountStatus status) {
            return customers.values()
                    .stream()
                    .filter(customer -> customer.status() == status)
                    .toList();
        }

        @Override
        public Customer save(Customer customer) {
            Optional<Customer> duplicate = findByEmail(customer.email());

            if (duplicate.isPresent() && duplicate.get().id() != customer.id()) {
                throw new RepositoryException(
                        "Email address already exists",
                        RepositoryError.DUPLICATE
                );
            }

            Customer persisted = customer;

            if (customer.id() == 0) {
                persisted = new Customer(
                        nextId++,
                        customer.name(),
                        customer.email().trim().toLowerCase(),
                        customer.status()
                );
            }

            customers.put(persisted.id(), persisted);
            return persisted;
        }

        @Override
        public boolean delete(long id) {
            return customers.remove(id) != null;
        }
    }

    enum RepositoryError {
        DUPLICATE,
        NOT_FOUND,
        CONFLICT
    }

    static final class RepositoryException extends RuntimeException {
        private final RepositoryError error;

        RepositoryException(String message, RepositoryError error) {
            super(message);
            this.error = error;
        }

        RepositoryError error() {
            return error;
        }
    }

    /*
     * Application services express business operations. They do not construct
     * SQL statements or depend on storage-specific classes.
     */
    static final class CustomerService {
        private final CustomerRepository repository;

        CustomerService(CustomerRepository repository) {
            this.repository = Objects.requireNonNull(repository);
        }

        Customer register(String name, String email) {
            String normalizedEmail = email.trim().toLowerCase();

            if (normalizedEmail.isBlank()) {
                throw new IllegalArgumentException("Email is required");
            }

            if (repository.findByEmail(normalizedEmail).isPresent()) {
                throw new RepositoryException(
                        "Customer already exists",
                        RepositoryError.DUPLICATE
                );
            }

            return repository.save(
                    new Customer(
                            0,
                            name.trim(),
                            normalizedEmail,
                            AccountStatus.ACTIVE
                    )
            );
        }

        Customer suspend(long customerId) {
            Customer customer = repository.findById(customerId)
                    .orElseThrow(() -> new RepositoryException(
                            "Customer does not exist",
                            RepositoryError.NOT_FOUND
                    ));

            if (customer.status() == AccountStatus.DELETED) {
                throw new IllegalStateException(
                        "Deleted customers cannot be suspended"
                );
            }

            if (customer.status() == AccountStatus.SUSPENDED) {
                return customer;
            }

            return repository.save(customer.suspend());
        }

        Customer reactivate(long customerId) {
            Customer customer = repository.findById(customerId)
                    .orElseThrow(() -> new RepositoryException(
                            "Customer does not exist",
                            RepositoryError.NOT_FOUND
                    ));

            if (customer.status() == AccountStatus.DELETED) {
                throw new IllegalStateException(
                        "Deleted customers cannot be reactivated"
                );
            }

            return repository.save(customer.activate());
        }

        List<Customer> activeCustomers() {
            return Collections.unmodifiableList(
                    repository.findByStatus(AccountStatus.ACTIVE)
            );
        }
    }

    /*
     * A specification-like policy object keeps a business query explicit.
     * The service can request customers satisfying a known status without
     * knowing whether filtering occurs in memory or inside SQL.
     */
    static final class CustomerReport {
        private final CustomerRepository repository;

        CustomerReport(CustomerRepository repository) {
            this.repository = repository;
        }

        String generate() {
            List<Customer> active =
                    repository.findByStatus(AccountStatus.ACTIVE);

            return active.stream()
                    .map(customer ->
                            customer.id()
                                    + " | "
                                    + customer.name()
                                    + " | "
                                    + customer.email())
                    .reduce(
                            "Generated at " + Instant.now() + "\n",
                            (result, line) -> result + line + "\n"
                    );
        }
    }

    public static void main(String[] args) {
        CustomerRepository repository =
                new InMemoryCustomerRepository();

        CustomerService service = new CustomerService(repository);

        Customer first =
                service.register("Ananya Kapoor", "ANANYA@example.com");

        Customer second =
                service.register("Vikram Joshi", "vikram@example.com");

        System.out.println("Registered:");
        System.out.println(first);
        System.out.println(second);

        Customer suspended = service.suspend(first.id());
        System.out.println("Suspended customer: " + suspended);

        Customer reactivated = service.reactivate(first.id());
        System.out.println("Reactivated customer: " + reactivated);

        System.out.println("Active customer report:");
        System.out.println(new CustomerReport(repository).generate());

        try {
            service.register("Duplicate", "ananya@example.com");
        } catch (RepositoryException exception) {
            System.out.println(
                    "Expected persistence conflict: "
                            + exception.getMessage()
                            + " ["
                            + exception.error()
                            + "]"
            );
        }

        try {
            service.suspend(9999);
        } catch (RepositoryException exception) {
            System.out.println(
                    "Expected missing-record failure: "
                            + exception.getMessage()
            );
        }
    }
}

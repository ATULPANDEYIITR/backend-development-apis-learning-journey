import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public class DatabaseMigrationEnterpriseDemo {

    enum MigrationStatus {
        PENDING,
        APPLIED,
        FAILED
    }

    enum ColumnType {
        BIGINT,
        VARCHAR,
        TIMESTAMP,
        BOOLEAN
    }

    record Column(
        String name,
        ColumnType type,
        boolean nullable
    ) {
        Column {
            Objects.requireNonNull(name);
            Objects.requireNonNull(type);

            if (name.isBlank()) {
                throw new IllegalArgumentException("Column name cannot be blank.");
            }
        }
    }

    record MigrationDefinition(
        int version,
        String name,
        String checksum,
        MigrationAction up,
        MigrationAction down
    ) {
        MigrationDefinition {
            if (version <= 0) {
                throw new IllegalArgumentException(
                    "Migration version must be positive."
                );
            }

            Objects.requireNonNull(name);
            Objects.requireNonNull(checksum);
            Objects.requireNonNull(up);
            Objects.requireNonNull(down);
        }
    }

    @FunctionalInterface
    interface MigrationAction {
        void execute(DatabaseSchema schema);
    }

    record MigrationRecord(
        int version,
        String name,
        String checksum,
        Instant appliedAt
    ) {}

    static final class MigrationException extends RuntimeException {
        MigrationException(String message) {
            super(message);
        }

        MigrationException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static final class TableDefinition {
        private final String name;
        private final LinkedHashMap<String, Column> columns =
            new LinkedHashMap<>();

        TableDefinition(String name, List<Column> initialColumns) {
            this.name = Objects.requireNonNull(name);

            for (Column column : initialColumns) {
                addColumn(column);
            }
        }

        TableDefinition(TableDefinition other) {
            this.name = other.name;
            this.columns.putAll(other.columns);
        }

        void addColumn(Column column) {
            if (columns.containsKey(column.name())) {
                throw new MigrationException(
                    "Column already exists: " + column.name()
                );
            }

            columns.put(column.name(), column);
        }

        void removeColumn(String columnName) {
            if (!columns.containsKey(columnName)) {
                throw new MigrationException(
                    "Column does not exist: " + columnName
                );
            }

            columns.remove(columnName);
        }

        String name() {
            return name;
        }

        Map<String, Column> columns() {
            return Collections.unmodifiableMap(columns);
        }
    }

    static final class DatabaseSchema {
        private final LinkedHashMap<String, TableDefinition> tables =
            new LinkedHashMap<>();

        DatabaseSchema() {}

        DatabaseSchema(DatabaseSchema other) {
            for (TableDefinition table : other.tables.values()) {
                tables.put(table.name(), new TableDefinition(table));
            }
        }

        void createTable(String name, List<Column> columns) {
            if (tables.containsKey(name)) {
                throw new MigrationException(
                    "Table already exists: " + name
                );
            }

            tables.put(name, new TableDefinition(name, columns));
        }

        void dropTable(String name) {
            if (!tables.containsKey(name)) {
                throw new MigrationException(
                    "Table does not exist: " + name
                );
            }

            tables.remove(name);
        }

        void addColumn(String tableName, Column column) {
            table(tableName).addColumn(column);
        }

        void removeColumn(String tableName, String columnName) {
            table(tableName).removeColumn(columnName);
        }

        TableDefinition table(String name) {
            TableDefinition table = tables.get(name);

            if (table == null) {
                throw new MigrationException(
                    "Table does not exist: " + name
                );
            }

            return table;
        }

        Map<String, TableDefinition> tables() {
            return Collections.unmodifiableMap(tables);
        }
    }

    static final class MigrationRepository {
        private final Map<Integer, MigrationRecord> records =
            new LinkedHashMap<>();

        void save(MigrationRecord record) {
            if (records.containsKey(record.version())) {
                throw new MigrationException(
                    "Migration version already recorded: " +
                    record.version()
                );
            }

            records.put(record.version(), record);
        }

        boolean contains(int version) {
            return records.containsKey(version);
        }

        Optional<MigrationRecord> find(int version) {
            return Optional.ofNullable(records.get(version));
        }

        void delete(int version) {
            if (records.remove(version) == null) {
                throw new MigrationException(
                    "Migration history entry does not exist: " +
                    version
                );
            }
        }

        List<MigrationRecord> all() {
            return List.copyOf(records.values());
        }
    }

    static final class MigrationService {
        private final DatabaseSchema schema;
        private final MigrationRepository repository;

        MigrationService(
            DatabaseSchema schema,
            MigrationRepository repository
        ) {
            this.schema = schema;
            this.repository = repository;
        }

        void migrate(List<MigrationDefinition> definitions) {
            List<MigrationDefinition> ordered =
                new ArrayList<>(definitions);

            ordered.sort(
                (left, right) ->
                    Integer.compare(left.version(), right.version())
            );

            validateHistory(ordered);

            for (MigrationDefinition migration : ordered) {
                if (!repository.contains(migration.version())) {
                    apply(migration);
                }
            }
        }

        private void validateHistory(
            List<MigrationDefinition> definitions
        ) {
            Map<Integer, MigrationDefinition> byVersion =
                new HashMap<>();

            for (MigrationDefinition definition : definitions) {
                byVersion.put(definition.version(), definition);
            }

            for (MigrationRecord record : repository.all()) {
                MigrationDefinition definition =
                    byVersion.get(record.version());

                if (definition == null) {
                    throw new MigrationException(
                        "Applied migration is missing from source: " +
                        record.version()
                    );
                }

                if (!definition.checksum().equals(record.checksum())) {
                    throw new MigrationException(
                        "Checksum mismatch for migration " +
                        record.version()
                    );
                }
            }
        }

        private void apply(MigrationDefinition migration) {
            DatabaseSchema snapshot = new DatabaseSchema(schema);

            try {
                migration.up().execute(schema);

                repository.save(
                    new MigrationRecord(
                        migration.version(),
                        migration.name(),
                        migration.checksum(),
                        Instant.now()
                    )
                );

                System.out.println(
                    "Applied v" +
                    migration.version() +
                    ": " +
                    migration.name()
                );
            } catch (RuntimeException error) {
                restore(snapshot);

                throw new MigrationException(
                    "Migration v" +
                    migration.version() +
                    " rolled back.",
                    error
                );
            }
        }

        void rollbackLast(
            List<MigrationDefinition> definitions
        ) {
            Optional<MigrationRecord> last =
                repository.all()
                    .stream()
                    .reduce((first, second) -> second);

            if (last.isEmpty()) {
                throw new MigrationException(
                    "No migration is available for rollback."
                );
            }

            MigrationRecord record = last.get();

            MigrationDefinition definition =
                definitions.stream()
                    .filter(
                        item -> item.version() == record.version()
                    )
                    .findFirst()
                    .orElseThrow(
                        () -> new MigrationException(
                            "Rollback definition is unavailable."
                        )
                    );

            DatabaseSchema snapshot = new DatabaseSchema(schema);

            try {
                definition.down().execute(schema);
                repository.delete(record.version());

                System.out.println(
                    "Rolled back v" +
                    record.version() +
                    ": " +
                    record.name()
                );
            } catch (RuntimeException error) {
                restore(snapshot);

                throw new MigrationException(
                    "Rollback failed for v" +
                    record.version(),
                    error
                );
            }
        }

        private void restore(DatabaseSchema snapshot) {
            schema.tables().keySet().forEach(
                tableName -> {
                    if (!snapshot.tables().containsKey(tableName)) {
                        schema.dropTable(tableName);
                    }
                }
            );

            for (TableDefinition snapshotTable :
                snapshot.tables().values()) {

                if (!schema.tables().containsKey(snapshotTable.name())) {
                    schema.createTable(
                        snapshotTable.name(),
                        List.copyOf(snapshotTable.columns().values())
                    );
                    continue;
                }

                TableDefinition current =
                    schema.table(snapshotTable.name());

                for (String columnName :
                    new ArrayList<>(current.columns().keySet())) {

                    if (!snapshotTable.columns().containsKey(columnName)) {
                        current.removeColumn(columnName);
                    }
                }

                for (Column column :
                    snapshotTable.columns().values()) {

                    if (!current.columns().containsKey(column.name())) {
                        current.addColumn(column);
                    }
                }
            }
        }

        void printSchema() {
            System.out.println("\nDatabase schema");

            for (TableDefinition table : schema.tables().values()) {
                System.out.println("TABLE " + table.name());

                for (Column column : table.columns().values()) {
                    System.out.println(
                        "  " +
                        column.name() +
                        " " +
                        column.type() +
                        (column.nullable() ? " NULL" : " NOT NULL")
                    );
                }
            }
        }

        void printHistory() {
            System.out.println("\nMigration history");

            for (MigrationRecord record : repository.all()) {
                System.out.println(
                    "v" +
                    record.version() +
                    " | " +
                    record.name() +
                    " | " +
                    record.checksum() +
                    " | " +
                    record.appliedAt()
                );
            }
        }
    }

    private static MigrationDefinition createCustomers() {
        return new MigrationDefinition(
            1,
            "create_customers",
            "sha256:create_customers_v1",
            schema -> schema.createTable(
                "customers",
                List.of(
                    new Column("id", ColumnType.BIGINT, false),
                    new Column("email", ColumnType.VARCHAR, false),
                    new Column("created_at", ColumnType.TIMESTAMP, false)
                )
            ),
            schema -> schema.dropTable("customers")
        );
    }

    private static MigrationDefinition addCustomerStatus() {
        return new MigrationDefinition(
            2,
            "add_customer_status",
            "sha256:add_customer_status_v2",
            schema -> schema.addColumn(
                "customers",
                new Column("status", ColumnType.VARCHAR, false)
            ),
            schema -> schema.removeColumn(
                "customers",
                "status"
            )
        );
    }

    private static MigrationDefinition createInvoices() {
        return new MigrationDefinition(
            3,
            "create_invoices",
            "sha256:create_invoices_v3",
            schema -> schema.createTable(
                "invoices",
                List.of(
                    new Column("id", ColumnType.BIGINT, false),
                    new Column("customer_id", ColumnType.BIGINT, false),
                    new Column("amount", ColumnType.BIGINT, false),
                    new Column("issued_at", ColumnType.TIMESTAMP, false)
                )
            ),
            schema -> schema.dropTable("invoices")
        );
    }

    private static MigrationDefinition addExternalIdentity() {
        return new MigrationDefinition(
            4,
            "add_external_identity",
            "sha256:add_external_identity_v4",
            schema -> schema.addColumn(
                "customers",
                new Column("external_id", ColumnType.VARCHAR, true)
            ),
            schema -> schema.removeColumn(
                "customers",
                "external_id"
            )
        );
    }

    private static MigrationDefinition failingMigration() {
        return new MigrationDefinition(
            5,
            "add_billing_profile",
            "sha256:add_billing_profile_v5",
            schema -> {
                schema.addColumn(
                    "customers",
                    new Column(
                        "billing_profile_id",
                        ColumnType.BIGINT,
                        false
                    )
                );

                throw new MigrationException(
                    "Existing customers cannot satisfy the new NOT NULL requirement."
                );
            },
            schema -> schema.removeColumn(
                "customers",
                "billing_profile_id"
            )
        );
    }

    public static void main(String[] args) {
        DatabaseSchema schema = new DatabaseSchema();
        MigrationRepository repository =
            new MigrationRepository();

        MigrationService service =
            new MigrationService(schema, repository);

        List<MigrationDefinition> migrations = List.of(
            createCustomers(),
            addCustomerStatus(),
            createInvoices(),
            addExternalIdentity()
        );

        System.out.println("Applying enterprise schema evolution...");
        service.migrate(migrations);

        service.printSchema();
        service.printHistory();

        System.out.println(
            "\nTesting failed migration and rollback..."
        );

        try {
            service.migrate(
                List.of(
                    createCustomers(),
                    addCustomerStatus(),
                    createInvoices(),
                    addExternalIdentity(),
                    failingMigration()
                )
            );
        } catch (MigrationException error) {
            System.out.println(
                "Expected deployment failure: " +
                error.getMessage()
            );
        }

        service.printSchema();
        service.printHistory();

        System.out.println(
            "\nRolling back the latest successful migration..."
        );

        service.rollbackLast(migrations);

        service.printSchema();
        service.printHistory();

        /*
         * EnumSet illustrates that migration state belongs to the deployment
         * lifecycle, while migration history is the durable record of which
         * states actually reached the database.
         */
        Set<MigrationStatus> deploymentStates =
            EnumSet.of(
                MigrationStatus.PENDING,
                MigrationStatus.APPLIED,
                MigrationStatus.FAILED
            );

        System.out.println(
            "\nSupported deployment states: " +
            deploymentStates
        );
    }
}

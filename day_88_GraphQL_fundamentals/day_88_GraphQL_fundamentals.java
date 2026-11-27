import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BiFunction;

/*
 * GraphQL Fundamentals: Enterprise Execution Model
 *
 * Java 17
 * No external dependencies.
 *
 * Covers:
 * - Schema and object types
 * - Scalar and composite types
 * - Queries and mutations
 * - Resolver registration
 * - Argument validation
 * - Authorization
 * - Nested object resolution
 * - Execution context
 * - State management
 * - Complexity restrictions
 * - Enterprise error handling
 */

public class Main {

    // -----------------------------------------------------
    // 1. GraphQL exceptions
    // -----------------------------------------------------

    static class GraphQLException extends RuntimeException {
        GraphQLException(String message) {
            super(message);
        }
    }

    // -----------------------------------------------------
    // 2. GraphQL type system
    // -----------------------------------------------------

    enum Scalar {
        STRING,
        INT,
        FLOAT,
        BOOLEAN,
        ID
    }

    sealed interface GraphQLType
            permits ScalarType, ObjectType, ListType, NonNullType {
    }

    record ScalarType(Scalar scalar) implements GraphQLType {
    }

    record ListType(GraphQLType elementType)
            implements GraphQLType {

        ListType {
            Objects.requireNonNull(elementType);
        }
    }

    record NonNullType(GraphQLType innerType)
            implements GraphQLType {

        NonNullType {
            Objects.requireNonNull(innerType);
        }
    }

    record ArgumentDefinition(
            GraphQLType type,
            boolean required
    ) {
    }

    // -----------------------------------------------------
    // 3. Resolver contracts
    // -----------------------------------------------------

    @FunctionalInterface
    interface Resolver {
        Object resolve(
                Object source,
                Map<String, Object> arguments,
                ExecutionContext context
        );
    }

    record FieldDefinition(
            GraphQLType type,
            Resolver resolver,
            Map<String, ArgumentDefinition> arguments,
            String description
    ) {
        FieldDefinition {
            Objects.requireNonNull(type);
            arguments = Map.copyOf(arguments);
            description = description == null ? "" : description;
        }
    }

    // -----------------------------------------------------
    // 4. Object type definitions
    // -----------------------------------------------------

    static final class ObjectType implements GraphQLType {

        private final String name;
        private final Map<String, FieldDefinition> fields;

        ObjectType(
                String name,
                Map<String, FieldDefinition> fields
        ) {
            if (name == null || name.isBlank()) {
                throw new GraphQLException("Type name is required");
            }

            this.name = name;
            this.fields = new LinkedHashMap<>(fields);
        }

        String name() {
            return name;
        }

        FieldDefinition field(String fieldName) {
            FieldDefinition definition = fields.get(fieldName);

            if (definition == null) {
                throw new GraphQLException(
                        "Unknown field: " + name + "." + fieldName
                );
            }

            return definition;
        }

        Map<String, FieldDefinition> fields() {
            return Collections.unmodifiableMap(fields);
        }
    }

    // -----------------------------------------------------
    // 5. Execution context and security
    // -----------------------------------------------------

    record ExecutionContext(
            String userId,
            Set<String> roles,
            String requestId
    ) {
        ExecutionContext {
            roles = Collections.unmodifiableSet(
                    new LinkedHashSet<>(roles)
            );

            Objects.requireNonNull(requestId);
        }

        boolean hasRole(String role) {
            return roles.contains(role);
        }
    }

    // -----------------------------------------------------
    // 6. GraphQL schema registry
    // -----------------------------------------------------

    static final class GraphQLSchema {

        private final ObjectType query;
        private final ObjectType mutation;
        private final Map<String, ObjectType> types;

        GraphQLSchema(
                ObjectType query,
                ObjectType mutation,
                List<ObjectType> types
        ) {
            this.query = Objects.requireNonNull(query);
            this.mutation = Objects.requireNonNull(mutation);

            Map<String, ObjectType> registry =
                    new LinkedHashMap<>();

            for (ObjectType type : types) {
                if (registry.putIfAbsent(type.name(), type) != null) {
                    throw new GraphQLException(
                            "Duplicate type: " + type.name()
                    );
                }
            }

            this.types = Collections.unmodifiableMap(registry);
        }

        ObjectType root(String operation) {
            return switch (operation) {
                case "query" -> query;
                case "mutation" -> mutation;
                default -> throw new GraphQLException(
                        "Unsupported operation: " + operation
                );
            };
        }

        Map<String, ObjectType> types() {
            return types;
        }
    }

    // -----------------------------------------------------
    // 7. Query selection model
    // -----------------------------------------------------

    record Selection(
            String field,
            Map<String, Object> arguments,
            Map<String, Selection> children
    ) {
        Selection {
            Objects.requireNonNull(field);
            arguments = Map.copyOf(arguments);
            children = Map.copyOf(children);
        }

        static Selection scalar(String field) {
            return new Selection(
                    field,
                    Map.of(),
                    Map.of()
            );
        }

        static Selection field(
                String field,
                Map<String, Object> arguments,
                Selection... children
        ) {
            Map<String, Selection> nested = new LinkedHashMap<>();

            for (Selection selection : children) {
                if (nested.putIfAbsent(
                        selection.field(),
                        selection
                ) != null) {
                    throw new GraphQLException(
                            "Duplicate selection: " + selection.field()
                    );
                }
            }

            return new Selection(field, arguments, nested);
        }
    }

    // -----------------------------------------------------
    // 8. Enterprise domain records
    // -----------------------------------------------------

    record User(
            String id,
            String name,
            String email
    ) {
    }

    record Product(
            String id,
            String name,
            double price,
            int stock
    ) {
    }

    record Order(
            String id,
            String userId,
            String productId,
            int quantity,
            String status,
            Instant createdAt
    ) {
    }

    // -----------------------------------------------------
    // 9. Inventory service
    // -----------------------------------------------------

    static final class InventoryService {

        private final Map<String, User> users =
                new ConcurrentHashMap<>();

        private final Map<String, Product> products =
                new ConcurrentHashMap<>();

        private final Map<String, Order> orders =
                new ConcurrentHashMap<>();

        private final AtomicInteger orderSequence =
                new AtomicInteger(1);

        InventoryService() {
            users.put(
                    "1",
                    new User(
                            "1",
                            "Aarav Sharma",
                            "aarav@example.com"
                    )
            );

            users.put(
                    "2",
                    new User(
                            "2",
                            "Meera Singh",
                            "meera@example.com"
                    )
            );

            products.put(
                    "101",
                    new Product(
                            "101",
                            "Laptop",
                            75000,
                            8
                    )
            );

            products.put(
                    "102",
                    new Product(
                            "102",
                            "Keyboard",
                            2500,
                            20
                    )
            );
        }

        User findUser(String id) {
            return users.get(id);
        }

        Product findProduct(String id) {
            return products.get(id);
        }

        List<Product> products() {
            return List.copyOf(products.values());
        }

        List<Order> orders() {
            return List.copyOf(orders.values());
        }

        synchronized Order createOrder(
                String userId,
                String productId,
                int quantity
        ) {
            User user = findUser(userId);
            Product product = findProduct(productId);

            if (user == null) {
                throw new GraphQLException("User does not exist");
            }

            if (product == null) {
                throw new GraphQLException("Product does not exist");
            }

            if (quantity <= 0) {
                throw new GraphQLException(
                        "Quantity must be positive"
                );
            }

            if (product.stock() < quantity) {
                throw new GraphQLException(
                        "Insufficient inventory"
                );
            }

            // Synchronization protects the inventory check and update.
            products.put(
                    productId,
                    new Product(
                            product.id(),
                            product.name(),
                            product.price(),
                            product.stock() - quantity
                    )
            );

            Order order = new Order(
                    String.valueOf(orderSequence.getAndIncrement()),
                    userId,
                    productId,
                    quantity,
                    "CONFIRMED",
                    Instant.now()
            );

            orders.put(order.id(), order);

            return order;
        }
    }

    // -----------------------------------------------------
    // 10. GraphQL schema factory
    // -----------------------------------------------------

    static final class SchemaFactory {

        private static ScalarType scalar(Scalar scalar) {
            return new ScalarType(scalar);
        }

        private static ArgumentDefinition required(
                Scalar scalar
        ) {
            return new ArgumentDefinition(
                    new NonNullType(scalar(scalar)),
                    true
            );
        }

        static GraphQLSchema create(InventoryService service) {

            ObjectType user = new ObjectType(
                    "User",
                    Map.of(
                            "id", new FieldDefinition(
                                    scalar(Scalar.ID),
                                    (source, args, context) ->
                                            ((User) source).id(),
                                    Map.of(),
                                    "Unique user identifier"
                            ),
                            "name", new FieldDefinition(
                                    scalar(Scalar.STRING),
                                    (source, args, context) ->
                                            ((User) source).name(),
                                    Map.of(),
                                    "User name"
                            ),
                            "email", new FieldDefinition(
                                    scalar(Scalar.STRING),
                                    (source, args, context) ->
                                            ((User) source).email(),
                                    Map.of(),
                                    "User email"
                            )
                    )
            );

            ObjectType product = new ObjectType(
                    "Product",
                    Map.of(
                            "id", new FieldDefinition(
                                    scalar(Scalar.ID),
                                    (source, args, context) ->
                                            ((Product) source).id(),
                                    Map.of(),
                                    "Product identifier"
                            ),
                            "name", new FieldDefinition(
                                    scalar(Scalar.STRING),
                                    (source, args, context) ->
                                            ((Product) source).name(),
                                    Map.of(),
                                    "Product name"
                            ),
                            "price", new FieldDefinition(
                                    scalar(Scalar.FLOAT),
                                    (source, args, context) ->
                                            ((Product) source).price(),
                                    Map.of(),
                                    "Product price"
                            ),
                            "stock", new FieldDefinition(
                                    scalar(Scalar.INT),
                                    (source, args, context) ->
                                            ((Product) source).stock(),
                                    Map.of(),
                                    "Available stock"
                            )
                    )
            );

            ObjectType order = new ObjectType(
                    "Order",
                    Map.of(
                            "id", new FieldDefinition(
                                    scalar(Scalar.ID),
                                    (source, args, context) ->
                                            ((Order) source).id(),
                                    Map.of(),
                                    "Order identifier"
                            ),
                            "quantity", new FieldDefinition(
                                    scalar(Scalar.INT),
                                    (source, args, context) ->
                                            ((Order) source).quantity(),
                                    Map.of(),
                                    "Ordered quantity"
                            ),
                            "status", new FieldDefinition(
                                    scalar(Scalar.STRING),
                                    (source, args, context) ->
                                            ((Order) source).status(),
                                    Map.of(),
                                    "Order status"
                            ),
                            "user", new FieldDefinition(
                                    user,
                                    (source, args, context) ->
                                            service.findUser(
                                                    ((Order) source).userId()
                                            ),
                                    Map.of(),
                                    "Associated customer"
                            ),
                            "product", new FieldDefinition(
                                    product,
                                    (source, args, context) ->
                                            service.findProduct(
                                                    ((Order) source).productId()
                                            ),
                                    Map.of(),
                                    "Ordered product"
                            )
                    )
            );

            ObjectType query = new ObjectType(
                    "Query",
                    Map.of(
                            "products", new FieldDefinition(
                                    new ListType(product),
                                    (source, args, context) ->
                                            service.products(),
                                    Map.of(),
                                    "Retrieve products"
                            ),
                            "product", new FieldDefinition(
                                    product,
                                    (source, args, context) ->
                                            service.findProduct(
                                                    (String) args.get("id")
                                            ),
                                    Map.of(
                                            "id", required(Scalar.ID)
                                    ),
                                    "Retrieve one product"
                            ),
                            "user", new FieldDefinition(
                                    user,
                                    (source, args, context) ->
                                            service.findUser(
                                                    (String) args.get("id")
                                            ),
                                    Map.of(
                                            "id", required(Scalar.ID)
                                    ),
                                    "Retrieve one user"
                            ),
                            "orders", new FieldDefinition(
                                    new ListType(order),
                                    (source, args, context) ->
                                            service.orders(),
                                    Map.of(),
                                    "Retrieve orders"
                            )
                    )
            );

            ObjectType mutation = new ObjectType(
                    "Mutation",
                    Map.of(
                            "createOrder", new FieldDefinition(
                                    order,
                                    (source, args, context) -> {
                                        if (context.userId() == null) {
                                            throw new GraphQLException(
                                                    "Authentication required"
                                            );
                                        }

                                        if (!context.hasRole("CUSTOMER")) {
                                            throw new GraphQLException(
                                                    "Customer role required"
                                            );
                                        }

                                        String userId =
                                                (String) args.get("userId");

                                        if (!context.userId().equals(userId)) {
                                            throw new GraphQLException(
                                                    "Cannot order for another user"
                                            );
                                        }

                                        return service.createOrder(
                                                userId,
                                                (String) args.get("productId"),
                                                (Integer) args.get("quantity")
                                        );
                                    },
                                    Map.of(
                                            "userId", required(Scalar.ID),
                                            "productId", required(Scalar.ID),
                                            "quantity", required(Scalar.INT)
                                    ),
                                    "Create a customer order"
                            )
                    )
            );

            return new GraphQLSchema(
                    query,
                    mutation,
                    List.of(user, product, order)
            );
        }
    }

    // -----------------------------------------------------
    // 11. GraphQL scalar validation
    // -----------------------------------------------------

    static void validateScalar(
            Object value,
            Scalar scalar,
            String path
    ) {
        boolean valid = switch (scalar) {
            case STRING -> value instanceof String;

            case INT -> value instanceof Integer;

            case FLOAT -> value instanceof Number &&
                    Double.isFinite(((Number) value).doubleValue());

            case BOOLEAN -> value instanceof Boolean;

            case ID -> value instanceof String ||
                    value instanceof Integer;
        };

        if (!valid) {
            throw new GraphQLException(
                    "Invalid " + scalar + " value for " + path
            );
        }
    }

    static void validateValue(
            Object value,
            GraphQLType type,
            String path
    ) {
        if (type instanceof NonNullType nonNull) {
            if (value == null) {
                throw new GraphQLException(
                        path + " cannot be null"
                );
            }

            validateValue(value, nonNull.innerType(), path);
            return;
        }

        if (value == null) {
            return;
        }

        if (type instanceof ScalarType scalar) {
            validateScalar(value, scalar.scalar(), path);
        } else if (type instanceof ListType list) {
            if (!(value instanceof List<?> values)) {
                throw new GraphQLException(
                        path + " must be a list"
                );
            }

            for (int i = 0; i < values.size(); i++) {
                validateValue(
                        values.get(i),
                        list.elementType(),
                        path + "[" + i + "]"
                );
            }
        } else if (type instanceof ObjectType &&
                !(value instanceof Map<?, ?>) &&
                !(value instanceof User) &&
                !(value instanceof Product) &&
                !(value instanceof Order)) {
            throw new GraphQLException(
                    path + " must be an object"
            );
        }
    }

    // -----------------------------------------------------
    // 12. Execution result
    // -----------------------------------------------------

    record ExecutionResult(
            Object data,
            List<String> errors,
            Map<String, Object> extensions
    ) {
        ExecutionResult {
            errors = List.copyOf(errors);
            extensions = Map.copyOf(extensions);
        }
    }

    // -----------------------------------------------------
    // 13. Enterprise execution service
    // -----------------------------------------------------

    static final class GraphQLExecutionService {

        private final GraphQLSchema schema;
        private final ExecutionContext context;
        private final int maxDepth;
        private final int maxFields;

        private int fieldCount;

        GraphQLExecutionService(
                GraphQLSchema schema,
                ExecutionContext context,
                int maxDepth,
                int maxFields
        ) {
            this.schema = schema;
            this.context = context;
            this.maxDepth = maxDepth;
            this.maxFields = maxFields;
        }

        ExecutionResult execute(
                String operation,
                Map<String, Selection> selection
        ) {
            fieldCount = 0;
            long started = System.nanoTime();

            try {
                Object data = executeObject(
                        null,
                        schema.root(operation),
                        selection,
                        0
                );

                return new ExecutionResult(
                        data,
                        List.of(),
                        Map.of(
                                "requestId", context.requestId(),
                                "fieldsExecuted", fieldCount,
                                "durationNanos",
                                System.nanoTime() - started
                        )
                );
            } catch (GraphQLException exception) {
                return new ExecutionResult(
                        null,
                        List.of(exception.getMessage()),
                        Map.of("requestId", context.requestId())
                );
            }
        }

        private void increment(int depth) {
            if (depth > maxDepth) {
                throw new GraphQLException(
                        "Maximum query depth exceeded"
                );
            }

            if (++fieldCount > maxFields) {
                throw new GraphQLException(
                        "Maximum field count exceeded"
                );
            }
        }

        private void validateArguments(
                FieldDefinition definition,
                Map<String, Object> arguments
        ) {
            for (String key : arguments.keySet()) {
                if (!definition.arguments().containsKey(key)) {
                    throw new GraphQLException(
                            "Unknown argument: " + key
                    );
                }
            }

            for (var entry : definition.arguments().entrySet()) {
                String key = entry.getKey();
                ArgumentDefinition argument = entry.getValue();

                if (argument.required() && !arguments.containsKey(key)) {
                    throw new GraphQLException(
                            "Missing required argument: " + key
                    );
                }

                if (arguments.containsKey(key)) {
                    validateValue(
                            arguments.get(key),
                            argument.type(),
                            key
                    );
                }
            }
        }

        private Object executeObject(
                Object source,
                ObjectType type,
                Map<String, Selection> selections,
                int depth
        ) {
            if (selections.isEmpty()) {
                throw new GraphQLException(
                        "Object selection cannot be empty"
                );
            }

            Map<String, Object> output = new LinkedHashMap<>();

            for (var entry : selections.entrySet()) {
                String fieldName = entry.getKey();
                Selection selection = entry.getValue();

                increment(depth);

                FieldDefinition definition = type.field(fieldName);

                validateArguments(
                        definition,
                        selection.arguments()
                );

                Object value = definition.resolver().resolve(
                        source,
                        selection.arguments(),
                        context
                );

                output.put(
                        fieldName,
                        completeValue(
                                value,
                                definition.type(),
                                selection.children(),
                                depth + 1
                        )
                );
            }

            return Collections.unmodifiableMap(output);
        }

        private Object completeValue(
                Object value,
                GraphQLType type,
                Map<String, Selection> selections,
                int depth
        ) {
            if (type instanceof NonNullType nonNull) {
                if (value == null) {
                    throw new GraphQLException(
                            "Non-null resolver returned null"
                    );
                }

                return completeValue(
                        value,
                        nonNull.innerType(),
                        selections,
                        depth
                );
            }

            if (value == null) {
                return null;
            }

            if (type instanceof ScalarType scalar) {
                if (!selections.isEmpty()) {
                    throw new GraphQLException(
                            "Scalar field cannot have child selections"
                    );
                }

                validateScalar(value, scalar.scalar(), "result");
                return value;
            }

            if (type instanceof ListType listType) {
                if (!(value instanceof List<?> values)) {
                    throw new GraphQLException(
                            "Resolver must return a list"
                    );
                }

                List<Object> result = new ArrayList<>();

                for (Object item : values) {
                    result.add(
                            completeValue(
                                    item,
                                    listType.elementType(),
                                    selections,
                                    depth + 1
                            )
                    );
                }

                return List.copyOf(result);
            }

            if (type instanceof ObjectType objectType) {
                if (selections.isEmpty()) {
                    throw new GraphQLException(
                            "Composite field requires a selection"
                    );
                }

                return executeObject(
                        value,
                        objectType,
                        selections,
                        depth + 1
                );
            }

            throw new GraphQLException("Unsupported GraphQL type");
        }
    }

    // -----------------------------------------------------
    // 14. Output utility
    // -----------------------------------------------------

    static void printResult(
            String title,
            ExecutionResult result
    ) {
        System.out.println("\n" + title);
        System.out.println("Data: " + result.data());
        System.out.println("Errors: " + result.errors());
        System.out.println("Extensions: " + result.extensions());
    }

    // -----------------------------------------------------
    // 15. Demonstration
    // -----------------------------------------------------

    public static void main(String[] args) {

        InventoryService inventory = new InventoryService();

        GraphQLSchema schema = SchemaFactory.create(inventory);

        ExecutionContext context = new ExecutionContext(
                "1",
                Set.of("CUSTOMER"),
                "java-graphql-001"
        );

        GraphQLExecutionService executor =
                new GraphQLExecutionService(
                        schema,
                        context,
                        5,
                        30
                );

        System.out.println("GRAPHQL FUNDAMENTALS: JAVA 17");

        // Query: retrieve products.
        Selection products = Selection.field(
                "products",
                Map.of(),
                Selection.scalar("id"),
                Selection.scalar("name"),
                Selection.scalar("price"),
                Selection.scalar("stock")
        );

        printResult(
                "1. PRODUCT QUERY",
                executor.execute(
                        "query",
                        Map.of("products", products)
                )
        );

        // Query: retrieve one user.
        Selection user = Selection.field(
                "user",
                Map.of("id", "1"),
                Selection.scalar("id"),
                Selection.scalar("name"),
                Selection.scalar("email")
        );

        printResult(
                "2. USER QUERY",
                executor.execute(
                        "query",
                        Map.of("user", user)
                )
        );

        // Mutation: create an order with nested relationships.
        Selection createOrder = Selection.field(
                "createOrder",
                Map.of(
                        "userId", "1",
                        "productId", "101",
                        "quantity", 2
                ),
                Selection.scalar("id"),
                Selection.scalar("quantity"),
                Selection.scalar("status"),

                Selection.field(
                        "user",
                        Map.of(),
                        Selection.scalar("name")
                ),

                Selection.field(
                        "product",
                        Map.of(),
                        Selection.scalar("name"),
                        Selection.scalar("stock")
                )
        );

        ExecutionResult mutationResult = executor.execute(
                "mutation",
                Map.of("createOrder", createOrder)
        );

        printResult("3. ORDER MUTATION", mutationResult);

        if (!mutationResult.errors().isEmpty()) {
            throw new AssertionError("Valid mutation failed");
        }

        if (inventory.findProduct("101").stock() != 6) {
            throw new AssertionError("Inventory update failed");
        }

        // Invalid quantity.
        Selection invalidOrder = Selection.field(
                "createOrder",
                Map.of(
                        "userId", "1",
                        "productId", "101",
                        "quantity", -2
                ),
                Selection.scalar("id")
        );

        printResult(
                "4. INVALID QUANTITY",
                executor.execute(
                        "mutation",
                        Map.of("createOrder", invalidOrder)
                )
        );

        // Missing required argument.
        Selection missingArgument = Selection.field(
                "product",
                Map.of(),
                Selection.scalar("name")
        );

        printResult(
                "5. MISSING ARGUMENT",
                executor.execute(
                        "query",
                        Map.of("product", missingArgument)
                )
        );

        // Unknown field.
        Selection unknown = Selection.scalar("unknownField");

        printResult(
                "6. UNKNOWN FIELD",
                executor.execute(
                        "query",
                        Map.of("unknownField", unknown)
                )
        );

        // Authorization failure.
        ExecutionContext anonymous = new ExecutionContext(
                null,
                Set.of(),
                "anonymous-001"
        );

        GraphQLExecutionService anonymousExecutor =
                new GraphQLExecutionService(
                        schema,
                        anonymous,
                        5,
                        30
                );

        printResult(
                "7. AUTHORIZATION FAILURE",
                anonymousExecutor.execute(
                        "mutation",
                        Map.of("createOrder", createOrder)
                )
        );

        System.out.println("\nAll Java 17 demonstrations completed.");
    }
}

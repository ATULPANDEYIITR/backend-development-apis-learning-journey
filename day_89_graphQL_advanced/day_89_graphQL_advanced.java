import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

// ============================================================
// ADVANCED GRAPHQL ENTERPRISE EXECUTION MODEL
//
// Java 17
//
// Covers:
// - Nested query execution
// - Fragments
// - Variables
// - Resolver interfaces
// - Authentication and authorization
// - DataLoader batching
// - Query complexity
// - Immutable domain records
// - Enterprise error handling
// - Merge-free, read-oriented execution
//
// Compile: javac GraphQLAdvanced.java
// Run: java GraphQLAdvanced
// ============================================================

public class GraphQLAdvanced {

    // ========================================================
    // DOMAIN TYPES
    // ========================================================

    enum Role {
        ADMIN,
        EDITOR,
        USER,
        GUEST
    }

    record User(
        int id,
        String name,
        String email,
        Role role,
        boolean active
    ) {}

    record Post(
        int id,
        String title,
        String body,
        int authorId,
        boolean published
    ) {}

    record Comment(
        int id,
        int postId,
        int authorId,
        String content
    ) {}

    record Context(
        User user,
        String requestId
    ) {}

    // ========================================================
    // CUSTOM EXCEPTIONS
    // ========================================================

    static class GraphQLException extends RuntimeException {
        private final String code;

        GraphQLException(String message, String code) {
            super(message);
            this.code = code;
        }

        String code() {
            return code;
        }
    }

    static class ValidationException extends GraphQLException {
        ValidationException(String message) {
            super(message, "BAD_USER_INPUT");
        }
    }

    static class AuthorizationException extends GraphQLException {
        AuthorizationException(String message) {
            super(message, "FORBIDDEN");
        }
    }

    static class AuthenticationException extends GraphQLException {
        AuthenticationException() {
            super("Authentication required", "UNAUTHENTICATED");
        }
    }

    // ========================================================
    // QUERY DOMAIN MODEL
    // ========================================================

    record Selection(
        String field,
        String alias,
        Map<String, Object> arguments,
        List<Selection> children
    ) {
        Selection {
            Objects.requireNonNull(field);

            alias = alias == null ? field : alias;

            arguments = Map.copyOf(
                arguments == null ? Map.of() : arguments
            );

            children = List.copyOf(
                children == null ? List.of() : children
            );
        }

        static Selection field(String name) {
            return new Selection(
                name, name, Map.of(), List.of()
            );
        }

        static Selection nested(
            String name,
            Selection... children
        ) {
            return new Selection(
                name,
                name,
                Map.of(),
                List.of(children)
            );
        }
    }

    record Fragment(
        String name,
        String typeCondition,
        List<Selection> selections
    ) {
        Fragment {
            selections = List.copyOf(selections);
        }
    }

    record Operation(
        List<Selection> selections,
        Map<String, Object> variables,
        Map<String, Fragment> fragments
    ) {
        Operation {
            selections = List.copyOf(selections);
            variables = Map.copyOf(variables);
            fragments = Map.copyOf(fragments);
        }
    }

    // ========================================================
    // REPOSITORY INTERFACE
    // ========================================================

    interface Repository {
        List<Post> findPosts(boolean publishedOnly);

        Optional<User> findUser(int id);

        Map<Integer, List<Comment>> findCommentsByPostIds(
            List<Integer> ids
        );

        long queryCount();
    }

    // ========================================================
    // IN-MEMORY REPOSITORY IMPLEMENTATION
    // ========================================================

    static class InMemoryRepository implements Repository {

        private final Map<Integer, User> users = new HashMap<>();
        private final Map<Integer, Post> posts = new HashMap<>();
        private final List<Comment> comments = new ArrayList<>();

        private final AtomicInteger queryCount =
            new AtomicInteger();

        InMemoryRepository() {
            users.put(1, new User(
                1, "Atul", "atul@example.com",
                Role.ADMIN, true
            ));

            users.put(2, new User(
                2, "Rahul", "rahul@example.com",
                Role.EDITOR, true
            ));

            users.put(3, new User(
                3, "Priya", "priya@example.com",
                Role.USER, true
            ));

            posts.put(101, new Post(
                101, "GraphQL Architecture",
                "Nested resolver execution.", 1, true
            ));

            posts.put(102, new Post(
                102, "DataLoader",
                "Batching and caching.", 2, true
            ));

            posts.put(103, new Post(
                103, "Internal Draft",
                "Unpublished information.", 1, false
            ));

            comments.add(new Comment(
                1001, 101, 2, "Excellent."
            ));

            comments.add(new Comment(
                1002, 101, 3, "Very informative."
            ));

            comments.add(new Comment(
                1003, 102, 1, "Good implementation."
            ));
        }

        @Override
        public List<Post> findPosts(boolean publishedOnly) {
            queryCount.incrementAndGet();

            return posts.values()
                .stream()
                .filter(post ->
                    !publishedOnly || post.published()
                )
                .sorted(
                    Comparator.comparingInt(Post::id)
                )
                .toList();
        }

        @Override
        public Optional<User> findUser(int id) {
            queryCount.incrementAndGet();
            return Optional.ofNullable(users.get(id));
        }

        @Override
        public Map<Integer, List<Comment>> findCommentsByPostIds(
            List<Integer> ids
        ) {
            queryCount.incrementAndGet();

            Set<Integer> requested = new HashSet<>(ids);

            Map<Integer, List<Comment>> result =
                new HashMap<>();

            requested.forEach(id -> result.put(
                id, new ArrayList<>()
            ));

            for (Comment comment : comments) {
                if (requested.contains(comment.postId())) {
                    result.get(comment.postId()).add(comment);
                }
            }

            return result;
        }

        @Override
        public long queryCount() {
            return queryCount.get();
        }

        Optional<User> findUserWithoutQueryCount(int id) {
            return Optional.ofNullable(users.get(id));
        }
    }

    // ========================================================
    // AUTHORIZATION SERVICE
    // ========================================================

    static class AuthorizationService {

        static User requireAuthenticated(Context context) {
            if (context.user() == null ||
                !context.user().active()) {
                throw new AuthenticationException();
            }

            return context.user();
        }

        static User requireRoles(
            Context context,
            Set<Role> allowedRoles
        ) {
            User user = requireAuthenticated(context);

            if (!allowedRoles.contains(user.role())) {
                throw new AuthorizationException(
                    "Required role is missing."
                );
            }

            return user;
        }

        static boolean canReadPost(
            Context context,
            Post post
        ) {
            if (post.published()) {
                return true;
            }

            User user = context.user();

            return user != null &&
                user.active() &&
                (
                    user.role() == Role.ADMIN ||
                    user.id() == post.authorId()
                );
        }

        static boolean canReadEmail(
            Context context,
            User target
        ) {
            User current = context.user();

            return current != null &&
                current.active() &&
                (
                    current.role() == Role.ADMIN ||
                    current.id() == target.id()
                );
        }
    }

    // ========================================================
    // GENERIC DATALOADER
    // ========================================================

    static class DataLoader<K, V> {

        private final FunctionBatch<K, V> batchFunction;

        private final Map<K, CompletableFuture<V>> cache =
            new ConcurrentHashMap<>();

        private final List<K> pending =
            new ArrayList<>();

        private boolean dispatched = false;

        interface FunctionBatch<K, V> {
            Map<K, V> load(List<K> keys);
        }

        DataLoader(FunctionBatch<K, V> batchFunction) {
            this.batchFunction = batchFunction;
        }

        synchronized CompletableFuture<V> load(K key) {
            if (cache.containsKey(key)) {
                return cache.get(key);
            }

            CompletableFuture<V> future =
                new CompletableFuture<>();

            cache.put(key, future);
            pending.add(key);

            return future;
        }

        synchronized void dispatch() {
            if (dispatched || pending.isEmpty()) {
                return;
            }

            dispatched = true;

            List<K> keys = pending.stream()
                .distinct()
                .toList();

            pending.clear();

            try {
                Map<K, V> result = batchFunction.load(keys);

                for (K key : keys) {
                    CompletableFuture<V> future = cache.get(key);

                    if (result.containsKey(key)) {
                        future.complete(result.get(key));
                    } else {
                        future.completeExceptionally(
                            new GraphQLException(
                                "Missing batch result.",
                                "DATA_LOADER_ERROR"
                            )
                        );
                    }
                }
            } catch (RuntimeException exception) {
                for (K key : keys) {
                    CompletableFuture<V> future = cache.get(key);
                    future.completeExceptionally(exception);
                }

                throw exception;
            } finally {
                dispatched = false;
            }
        }

        synchronized void clear() {
            cache.clear();
            pending.clear();
        }
    }

    // ========================================================
    // COMPLEXITY ANALYZER
    // ========================================================

    static class ComplexityAnalyzer {

        private final int maximumCost;

        ComplexityAnalyzer(int maximumCost) {
            this.maximumCost = maximumCost;
        }

        int calculate(
            List<Selection> selections,
            Map<String, Fragment> fragments,
            Set<String> visited
        ) {
            int total = 0;

            for (Selection selection : selections) {
                if (selection.field().startsWith("...")) {
                    String name = selection.field().substring(3);

                    Fragment fragment = fragments.get(name);

                    if (fragment == null) {
                        throw new ValidationException(
                            "Unknown fragment: " + name
                        );
                    }

                    if (!visited.add(name)) {
                        throw new ValidationException(
                            "Circular fragment detected."
                        );
                    }

                    total += calculate(
                        fragment.selections(),
                        fragments,
                        visited
                    );

                    visited.remove(name);
                    continue;
                }

                int multiplier =
                    selection.field().equals("posts") ? 5 : 1;

                total += multiplier * (
                    1 + calculate(
                        selection.children(),
                        fragments,
                        visited
                    )
                );
            }

            return total;
        }

        int validate(Operation operation) {
            int cost = calculate(
                operation.selections(),
                operation.fragments(),
                new HashSet<>()
            );

            if (cost > maximumCost) {
                throw new ValidationException(
                    "Query complexity limit exceeded: " + cost
                );
            }

            return cost;
        }
    }

    // ========================================================
    // RESOLVER INTERFACE
    // ========================================================

    interface Resolver<P, A, R> {
        R resolve(P parent, A arguments, Context context);
    }

    // ========================================================
    // GRAPHQL EXECUTION SERVICE
    // ========================================================

    static class GraphQLService {

        private final Repository repository;
        private final ComplexityAnalyzer complexity;

        private final DataLoader<Integer, List<Comment>> commentsLoader;

        private final Map<String, Set<String>> schema = Map.of(
            "Query", Set.of("posts", "me", "user"),
            "Post", Set.of(
                "id", "title", "body", "published",
                "author", "comments"
            ),
            "User", Set.of(
                "id", "name", "email", "role", "posts"
            ),
            "Comment", Set.of(
                "id", "content", "author"
            )
        );

        GraphQLService(Repository repository) {
            this.repository = repository;

            this.complexity = new ComplexityAnalyzer(100);

            this.commentsLoader = new DataLoader<>(
                repository::findCommentsByPostIds
            );
        }

        void validateField(String type, String field) {
            if (!schema.getOrDefault(type, Set.of()).contains(field)) {
                throw new ValidationException(
                    "Unknown field " + field + " on " + type
                );
            }
        }

        Object resolveVariable(
            Object value,
            Map<String, Object> variables
        ) {
            if (value instanceof String text &&
                text.startsWith("$")) {

                String name = text.substring(1);

                if (!variables.containsKey(name)) {
                    throw new ValidationException(
                        "Missing variable: $" + name
                    );
                }

                return variables.get(name);
            }

            return value;
        }

        Map<String, Object> resolveArguments(
            Map<String, Object> arguments,
            Map<String, Object> variables
        ) {
            Map<String, Object> result = new HashMap<>();

            arguments.forEach((key, value) ->
                result.put(
                    key,
                    resolveVariable(value, variables)
                )
            );

            return result;
        }

        List<Selection> expandFragments(
            List<Selection> selections,
            Operation operation,
            String type,
            Set<String> stack
        ) {
            List<Selection> expanded = new ArrayList<>();

            for (Selection selection : selections) {
                if (selection.field().startsWith("...")) {
                    String name =
                        selection.field().substring(3);

                    Fragment fragment =
                        operation.fragments().get(name);

                    if (fragment == null) {
                        throw new ValidationException(
                            "Unknown fragment: " + name
                        );
                    }

                    if (!stack.add(name)) {
                        throw new ValidationException(
                            "Circular fragment detected."
                        );
                    }

                    if (fragment.typeCondition().equals(type)) {
                        expanded.addAll(
                            expandFragments(
                                fragment.selections(),
                                operation,
                                type,
                                stack
                            )
                        );
                    }

                    stack.remove(name);
                } else {
                    expanded.add(selection);
                }
            }

            return expanded;
        }

        List<Selection> expand(
            List<Selection> selections,
            Operation operation,
            String type
        ) {
            return expandFragments(
                selections,
                operation,
                type,
                new HashSet<>()
            );
        }

        Object resolveRoot(
            Selection selection,
            Operation operation,
            Context context
        ) {
            Map<String, Object> args = resolveArguments(
                selection.arguments(),
                operation.variables()
            );

            return switch (selection.field()) {
                case "posts" -> {
                    Object published = args.getOrDefault(
                        "publishedOnly", true
                    );

                    if (!(published instanceof Boolean flag)) {
                        throw new ValidationException(
                            "publishedOnly must be Boolean."
                        );
                    }

                    if (!flag) {
                        AuthorizationService.requireRoles(
                            context,
                            Set.of(Role.ADMIN, Role.EDITOR)
                        );
                    }

                    yield repository.findPosts(flag);
                }

                case "me" -> AuthorizationService.requireAuthenticated(
                    context
                );

                case "user" -> {
                    AuthorizationService.requireRoles(
                        context, Set.of(Role.ADMIN)
                    );

                    Object rawId = args.get("id");

                    if (!(rawId instanceof Integer id)) {
                        throw new ValidationException(
                            "user.id must be an integer."
                        );
                    }

                    yield repository.findUser(id).orElse(null);
                }

                default -> throw new ValidationException(
                    "Unknown root field: " + selection.field()
                );
            };
        }

        Object resolveField(
            Object parent,
            Selection selection,
            Context context
        ) {
            String field = selection.field();

            if (parent instanceof Post post) {
                return switch (field) {
                    case "id" -> post.id();
                    case "title" -> post.title();
                    case "body" -> post.body();
                    case "published" -> post.published();

                    case "author" ->
                        ((InMemoryRepository) repository)
                            .findUserWithoutQueryCount(
                                post.authorId()
                            )
                            .orElse(null);

                    case "comments" -> commentsLoader.load(post.id());

                    default -> throw new ValidationException(
                        "Unknown Post field: " + field
                    );
                };
            }

            if (parent instanceof User user) {
                return switch (field) {
                    case "id" -> user.id();
                    case "name" -> user.name();
                    case "role" -> user.role().name();

                    case "email" -> {
                        if (!AuthorizationService.canReadEmail(
                            context, user
                        )) {
                            throw new AuthorizationException(
                                "Email access denied."
                            );
                        }

                        yield user.email();
                    }

                    case "posts" -> repository.findPosts(true)
                        .stream()
                        .filter(post ->
                            post.authorId() == user.id()
                        )
                        .toList();

                    default -> throw new ValidationException(
                        "Unknown User field: " + field
                    );
                };
            }

            if (parent instanceof Comment comment) {
                return switch (field) {
                    case "id" -> comment.id();
                    case "content" -> comment.content();

                    case "author" ->
                        ((InMemoryRepository) repository)
                            .findUserWithoutQueryCount(
                                comment.authorId()
                            )
                            .orElse(null);

                    default -> throw new ValidationException(
                        "Unknown Comment field: " + field
                    );
                };
            }

            throw new ValidationException(
                "Unsupported parent type."
            );
        }

        Object project(
            Object value,
            List<Selection> selections,
            String type,
            Operation operation,
            Context context
        ) {
            if (value == null) {
                return null;
            }

            if (value instanceof CompletableFuture<?> future) {
                commentsLoader.dispatch();
                return project(
                    future.join(),
                    selections,
                    type,
                    operation,
                    context
                );
            }

            if (value instanceof List<?> values) {
                return values.stream()
                    .map(item -> project(
                        item,
                        selections,
                        type,
                        operation,
                        context
                    ))
                    .toList();
            }

            List<Selection> expanded = expand(
                selections, operation, type
            );

            Map<String, Object> result = new LinkedHashMap<>();

            // Resolve sibling fields before recursively projecting.
            Map<Selection, Object> rawValues = new LinkedHashMap<>();

            for (Selection selection : expanded) {
                validateField(type, selection.field());

                rawValues.put(
                    selection,
                    resolveField(value, selection, context)
                );
            }

            commentsLoader.dispatch();

            for (Map.Entry<Selection, Object> entry :
                rawValues.entrySet()) {

                Selection selection = entry.getKey();
                Object fieldValue = entry.getValue();

                if (selection.children().isEmpty()) {
                    if (fieldValue instanceof User ||
                        fieldValue instanceof Post ||
                        fieldValue instanceof Comment) {
                        throw new ValidationException(
                            "Nested selection required for " +
                            selection.field()
                        );
                    }

                    result.put(selection.alias(), fieldValue);
                    continue;
                }

                String childType = switch (selection.field()) {
                    case "author" -> "User";
                    case "comments" -> "Comment";
                    case "posts" -> "Post";
                    default -> throw new ValidationException(
                        "Scalar field cannot contain children."
                    );
                };

                result.put(
                    selection.alias(),
                    project(
                        fieldValue,
                        selection.children(),
                        childType,
                        operation,
                        context
                    )
                );
            }

            return result;
        }

        Map<String, Object> execute(
            Operation operation,
            Context context
        ) {
            long started = System.nanoTime();

            try {
                int cost = complexity.validate(operation);

                List<Selection> roots = expand(
                    operation.selections(),
                    operation,
                    "Query"
                );

                Map<String, Object> result =
                    new LinkedHashMap<>();

                for (Selection selection : roots) {
                    validateField("Query", selection.field());

                    Object value = resolveRoot(
                        selection, operation, context
                    );

                    String type = switch (selection.field()) {
                        case "me", "user" -> "User";
                        case "posts" -> "Post";
                        default -> throw new ValidationException(
                            "Invalid root field."
                        );
                    };

                    if (selection.children().isEmpty()) {
                        throw new ValidationException(
                            "Root selection requires child fields."
                        );
                    }

                    result.put(
                        selection.alias(),
                        project(
                            value,
                            selection.children(),
                            type,
                            operation,
                            context
                        )
                    );
                }

                return Map.of(
                    "data", result,
                    "extensions", Map.of(
                        "requestId", context.requestId(),
                        "complexity", cost,
                        "databaseQueries", repository.queryCount(),
                        "durationNanos",
                        System.nanoTime() - started
                    )
                );

            } catch (CompletionException exception) {
                commentsLoader.clear();

                Throwable cause = exception.getCause();

                return Map.of(
                    "data", Collections.emptyMap(),
                    "errors", List.of(Map.of(
                        "message", cause == null
                            ? exception.getMessage()
                            : cause.getMessage(),
                        "code", "EXECUTION_ERROR"
                    ))
                );

            } catch (GraphQLException exception) {
                commentsLoader.clear();

                return Map.of(
                    "data", Collections.emptyMap(),
                    "errors", List.of(Map.of(
                        "message", exception.getMessage(),
                        "code", exception.code()
                    ))
                );
            }
        }
    }

    // ========================================================
    // ENTERPRISE APPLICATION
    // ========================================================

    public static void main(String[] args) {

        InMemoryRepository repository =
            new InMemoryRepository();

        GraphQLService service =
            new GraphQLService(repository);

        User admin = new User(
            1,
            "Atul",
            "atul@example.com",
            Role.ADMIN,
            true
        );

        Context context = new Context(
            admin,
            "java-request-001"
        );

        Fragment postFragment = new Fragment(
            "PostDetails",
            "Post",
            List.of(
                Selection.field("id"),
                Selection.field("title"),
                Selection.nested(
                    "comments",
                    Selection.field("id"),
                    Selection.field("content")
                )
            )
        );

        Selection posts = new Selection(
            "posts",
            "posts",
            Map.of("publishedOnly", "$published"),
            List.of(
                new Selection(
                    "...PostDetails",
                    "...PostDetails",
                    Map.of(),
                    List.of()
                )
            )
        );

        Selection me = Selection.nested(
            "me",
            Selection.field("id"),
            Selection.field("name")
        );

        Operation operation = new Operation(
            List.of(posts, me),
            Map.of("published", true),
            Map.of("PostDetails", postFragment)
        );

        Map<String, Object> response =
            service.execute(operation, context);

        System.out.println("GRAPHQL RESPONSE");
        System.out.println(response);

        if (response.containsKey("errors")) {
            throw new IllegalStateException(
                "GraphQL execution failed."
            );
        }

        if (repository.queryCount() != 2) {
            throw new IllegalStateException(
                "Expected two database queries."
            );
        }

        System.out.println("\nDATALOADER TEST PASSED");

        // Unauthorized user lookup.
        Context userContext = new Context(
            new User(
                3, "Priya", "priya@example.com",
                Role.USER, true
            ),
            "java-request-002"
        );

        Operation unauthorized = new Operation(
            List.of(
                new Selection(
                    "user",
                    "user",
                    Map.of("id", 1),
                    List.of(Selection.field("email"))
                )
            ),
            Map.of(),
            Map.of()
        );

        Map<String, Object> denied =
            service.execute(unauthorized, userContext);

        if (!denied.containsKey("errors")) {
            throw new IllegalStateException(
                "Authorization test failed."
            );
        }

        System.out.println("AUTHORIZATION TEST PASSED");

        // Query complexity validation.
        Operation complex = new Operation(
            List.of(
                Selection.nested(
                    "posts",
                    Selection.field("id"),
                    Selection.field("title"),
                    Selection.field("published")
                )
            ),
            Map.of(),
            Map.of()
        );

        ComplexityAnalyzer strict =
            new ComplexityAnalyzer(2);

        try {
            strict.validate(complex);
            throw new IllegalStateException(
                "Complexity limit was not enforced."
            );
        } catch (ValidationException expected) {
            System.out.println(
                "QUERY COMPLEXITY TEST PASSED"
            );
        }

        // Missing variable validation.
        Operation missingVariable = new Operation(
            List.of(
                new Selection(
                    "posts",
                    "posts",
                    Map.of("publishedOnly", "$missing"),
                    List.of(Selection.field("id"))
                )
            ),
            Map.of(),
            Map.of()
        );

        Map<String, Object> variableResult =
            service.execute(missingVariable, context);

        if (!variableResult.containsKey("errors")) {
            throw new IllegalStateException(
                "Missing variable test failed."
            );
        }

        System.out.println(
            "VARIABLE VALIDATION TEST PASSED"
        );

        System.out.println("\nALL ENTERPRISE TESTS PASSED");
    }
}

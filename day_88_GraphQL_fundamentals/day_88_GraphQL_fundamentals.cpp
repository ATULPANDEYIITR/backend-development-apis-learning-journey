#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

using namespace std;

// ---------------------------------------------------------
// 1. GraphQL domain types
// ---------------------------------------------------------

enum class ScalarType {
    STRING,
    INTEGER,
    FLOAT,
    BOOLEAN,
    ID
};

enum class OperationType {
    QUERY,
    MUTATION
};

using ScalarValue = variant<
    string,
    int,
    double,
    bool
>;

struct GraphQLValue {
    using Object = map<string, GraphQLValue>;
    using Array = vector<GraphQLValue>;

    variant<
        monostate,
        string,
        int,
        double,
        bool,
        Object,
        Array
    > value;

    GraphQLValue() : value(monostate{}) {}

    GraphQLValue(const char* v) : value(string(v)) {}
    GraphQLValue(string v) : value(move(v)) {}
    GraphQLValue(int v) : value(v) {}
    GraphQLValue(double v) : value(v) {}
    GraphQLValue(bool v) : value(v) {}
    GraphQLValue(Object v) : value(move(v)) {}
    GraphQLValue(Array v) : value(move(v)) {}

    bool isNull() const {
        return holds_alternative<monostate>(value);
    }
};

struct TypeRef {
    ScalarType scalar;
    bool nonNull = false;
    bool isList = false;
};

struct Argument {
    TypeRef type;
    bool required = false;
};

struct FieldDefinition {
    TypeRef type;
    map<string, Argument> arguments;
};

struct Selection {
    string field;
    map<string, GraphQLValue> arguments;
    vector<Selection> children;
};

struct User {
    string id;
    string name;
    string email;
};

struct Product {
    string id;
    string name;
    double price;
    int stock;
};

struct Order {
    string id;
    string userId;
    string productId;
    int quantity;
    string status;
};

// ---------------------------------------------------------
// 2. GraphQL validation
// ---------------------------------------------------------

class GraphQLError : public runtime_error {
public:
    explicit GraphQLError(const string& message)
        : runtime_error(message) {}
};

void validateScalar(
    const GraphQLValue& value,
    ScalarType expected,
    const string& path
) {
    bool valid = false;

    switch (expected) {
        case ScalarType::STRING:
        case ScalarType::ID:
            valid = holds_alternative<string>(value.value) ||
                    (expected == ScalarType::ID &&
                     holds_alternative<int>(value.value));
            break;

        case ScalarType::INTEGER:
            valid = holds_alternative<int>(value.value);
            break;

        case ScalarType::FLOAT:
            valid = holds_alternative<double>(value.value) ||
                    holds_alternative<int>(value.value);
            break;

        case ScalarType::BOOLEAN:
            valid = holds_alternative<bool>(value.value);
            break;
    }

    if (!valid) {
        throw GraphQLError(
            "Invalid scalar type at " + path
        );
    }
}

string scalarToString(const GraphQLValue& value) {
    if (holds_alternative<string>(value.value)) {
        return get<string>(value.value);
    }

    if (holds_alternative<int>(value.value)) {
        return to_string(get<int>(value.value));
    }

    throw GraphQLError("Expected string or integer ID");
}

// ---------------------------------------------------------
// 3. Schema definition
// ---------------------------------------------------------

class GraphQLSchema {
private:
    map<string, map<string, FieldDefinition>> types;

public:
    void registerType(
        const string& name,
        const map<string, FieldDefinition>& fields
    ) {
        if (name.empty() || types.count(name)) {
            throw GraphQLError("Invalid or duplicate type");
        }

        types.emplace(name, fields);
    }

    const FieldDefinition& getField(
        const string& typeName,
        const string& fieldName
    ) const {
        auto type = types.find(typeName);

        if (type == types.end()) {
            throw GraphQLError("Unknown type: " + typeName);
        }

        auto field = type->second.find(fieldName);

        if (field == type->second.end()) {
            throw GraphQLError(
                "Unknown field: " + typeName + "." + fieldName
            );
        }

        return field->second;
    }
};

// ---------------------------------------------------------
// 4. Repository and inventory state
// ---------------------------------------------------------

class InventoryRepository {
private:
    map<string, User> users;
    map<string, Product> products;
    map<string, Order> orders;
    int nextOrderId = 1;

public:
    InventoryRepository() {
        users.emplace(
            "1",
            User{"1", "Aarav Sharma", "aarav@example.com"}
        );

        users.emplace(
            "2",
            User{"2", "Meera Singh", "meera@example.com"}
        );

        products.emplace(
            "101",
            Product{"101", "Laptop", 75000.0, 8}
        );

        products.emplace(
            "102",
            Product{"102", "Keyboard", 2500.0, 20}
        );
    }

    const map<string, User>& getUsers() const {
        return users;
    }

    const map<string, Product>& getProducts() const {
        return products;
    }

    const map<string, Order>& getOrders() const {
        return orders;
    }

    const User* findUser(const string& id) const {
        auto it = users.find(id);
        return it == users.end() ? nullptr : &it->second;
    }

    const Product* findProduct(const string& id) const {
        auto it = products.find(id);
        return it == products.end() ? nullptr : &it->second;
    }

    const Product& product(const string& id) const {
        auto it = products.find(id);

        if (it == products.end()) {
            throw GraphQLError("Product does not exist");
        }

        return it->second;
    }

    Order createOrder(
        const string& userId,
        const string& productId,
        int quantity
    ) {
        if (!findUser(userId)) {
            throw GraphQLError("User does not exist");
        }

        auto productIt = products.find(productId);

        if (productIt == products.end()) {
            throw GraphQLError("Product does not exist");
        }

        if (quantity <= 0) {
            throw GraphQLError("Quantity must be positive");
        }

        Product& product = productIt->second;

        if (product.stock < quantity) {
            throw GraphQLError("Insufficient inventory");
        }

        // All validation occurs before state modification.
        product.stock -= quantity;

        Order order{
            to_string(nextOrderId++),
            userId,
            productId,
            quantity,
            "CONFIRMED"
        };

        orders.emplace(order.id, order);

        return order;
    }
};

// ---------------------------------------------------------
// 5. Request identity and permissions
// ---------------------------------------------------------

struct RequestContext {
    string userId;
    set<string> roles;
    string requestId;

    bool hasRole(const string& role) const {
        return roles.count(role) > 0;
    }
};

// ---------------------------------------------------------
// 6. GraphQL governance and execution engine
// ---------------------------------------------------------

class GraphQLExecutor {
private:
    const GraphQLSchema& schema;
    InventoryRepository& repository;
    RequestContext context;

    int maxFields;
    int maxDepth;
    int fieldCount = 0;

    void validateArguments(
        const string& parentType,
        const Selection& selection
    ) const {
        const auto& definition = schema.getField(
            parentType,
            selection.field
        );

        for (const auto& [name, value] : selection.arguments) {
            auto it = definition.arguments.find(name);

            if (it == definition.arguments.end()) {
                throw GraphQLError(
                    "Unknown argument: " + name
                );
            }

            validateScalar(
                value,
                it->second.type.scalar,
                name
            );
        }

        for (const auto& [name, argument] :
             definition.arguments) {

            if (argument.required &&
                !selection.arguments.count(name)) {
                throw GraphQLError(
                    "Missing required argument: " + name
                );
            }
        }
    }

    void checkLimits(int depth) {
        if (depth > maxDepth) {
            throw GraphQLError("Maximum query depth exceeded");
        }

        ++fieldCount;

        if (fieldCount > maxFields) {
            throw GraphQLError("Maximum field count exceeded");
        }
    }

    string getArgument(
        const Selection& selection,
        const string& name
    ) const {
        auto it = selection.arguments.find(name);

        if (it == selection.arguments.end()) {
            throw GraphQLError("Missing argument: " + name);
        }

        return scalarToString(it->second);
    }

    int getIntegerArgument(
        const Selection& selection,
        const string& name
    ) const {
        auto it = selection.arguments.find(name);

        if (it == selection.arguments.end() ||
            !holds_alternative<int>(it->second.value)) {
            throw GraphQLError("Expected integer argument: " + name);
        }

        return get<int>(it->second.value);
    }

    string scalarValue(
        const string& type,
        const void* source,
        const string& field
    ) const {
        if (type == "User") {
            const User* user = static_cast<const User*>(source);

            if (field == "id") return user->id;
            if (field == "name") return user->name;
            if (field == "email") return user->email;
        }

        if (type == "Product") {
            const Product* product =
                static_cast<const Product*>(source);

            if (field == "id") return product->id;
            if (field == "name") return product->name;
            if (field == "price") return to_string(product->price);
            if (field == "stock") return to_string(product->stock);
        }

        if (type == "Order") {
            const Order* order = static_cast<const Order*>(source);

            if (field == "id") return order->id;
            if (field == "quantity") return to_string(order->quantity);
            if (field == "status") return order->status;
        }

        throw GraphQLError("Unsupported scalar field");
    }

    map<string, string> resolveObject(
        const string& type,
        const void* source,
        const vector<Selection>& selections,
        int depth
    ) {
        map<string, string> output;

        for (const Selection& selection : selections) {
            checkLimits(depth);
            validateArguments(type, selection);

            if (!selection.children.empty()) {
                throw GraphQLError(
                    "Nested selections are supported through "
                    "relationship resolution in this engine's "
                    "explicit execution paths"
                );
            }

            output[selection.field] = scalarValue(
                type,
                source,
                selection.field
            );
        }

        return output;
    }

    void printObject(
        const map<string, string>& object
    ) const {
        cout << "{";

        bool first = true;

        for (const auto& [key, value] : object) {
            if (!first) cout << ", ";

            cout << "\"" << key << "\": \"" << value << "\"";
            first = false;
        }

        cout << "}";
    }

public:
    GraphQLExecutor(
        const GraphQLSchema& schema,
        InventoryRepository& repository,
        RequestContext context,
        int maxFields = 30,
        int maxDepth = 5
    )
        : schema(schema),
          repository(repository),
          context(move(context)),
          maxFields(maxFields),
          maxDepth(maxDepth) {}

    void executeQuery(const vector<Selection>& selections) {
        fieldCount = 0;

        cout << "{\n  \"data\": {\n";

        bool first = true;

        for (const Selection& selection : selections) {
            checkLimits(1);
            validateArguments("Query", selection);

            if (!first) cout << ",\n";

            cout << "    \"" << selection.field << "\": ";

            if (selection.field == "users") {
                cout << "[";

                bool firstUser = true;

                for (const auto& [id, user] :
                     repository.getUsers()) {

                    if (!firstUser) cout << ", ";

                    printObject(resolveObject(
                        "User",
                        &user,
                        selection.children,
                        2
                    ));

                    firstUser = false;
                }

                cout << "]";
            }
            else if (selection.field == "products") {
                cout << "[";

                bool firstProduct = true;

                for (const auto& [id, product] :
                     repository.getProducts()) {

                    if (!firstProduct) cout << ", ";

                    printObject(resolveObject(
                        "Product",
                        &product,
                        selection.children,
                        2
                    ));

                    firstProduct = false;
                }

                cout << "]";
            }
            else if (selection.field == "product") {
                string id = getArgument(selection, "id");
                const Product* product =
                    repository.findProduct(id);

                if (product) {
                    printObject(resolveObject(
                        "Product",
                        product,
                        selection.children,
                        2
                    ));
                } else {
                    cout << "null";
                }
            }
            else {
                throw GraphQLError("Unsupported query root field");
            }

            first = false;
        }

        cout << "\n  },\n";
        cout << "  \"extensions\": {\"fieldsExecuted\": "
             << fieldCount << "}\n";
        cout << "}\n";
    }

    void executeMutation(const Selection& selection) {
        fieldCount = 0;

        checkLimits(1);
        validateArguments("Mutation", selection);

        if (selection.field != "createOrder") {
            throw GraphQLError("Unsupported mutation");
        }

        if (context.userId.empty()) {
            throw GraphQLError("Authentication required");
        }

        if (!context.hasRole("CUSTOMER")) {
            throw GraphQLError("Customer role required");
        }

        string userId = getArgument(selection, "userId");
        string productId = getArgument(selection, "productId");
        int quantity = getIntegerArgument(selection, "quantity");

        if (userId != context.userId) {
            throw GraphQLError(
                "Cannot create orders for another user"
            );
        }

        Order order = repository.createOrder(
            userId,
            productId,
            quantity
        );

        cout << "{\n  \"data\": {\n"
             << "    \"createOrder\": {\n"
             << "      \"id\": \"" << order.id << "\",\n"
             << "      \"quantity\": " << order.quantity << ",\n"
             << "      \"status\": \"" << order.status << "\"\n"
             << "    }\n"
             << "  }\n}\n";
    }
};

// ---------------------------------------------------------
// 7. Application schema
// ---------------------------------------------------------

GraphQLSchema buildSchema() {
    GraphQLSchema schema;

    auto scalar = [](ScalarType type) {
        return FieldDefinition{TypeRef{type, false, false}, {}};
    };

    auto requiredArgument = [](ScalarType type) {
        return Argument{
            TypeRef{type, true, false},
            true
        };
    };

    map<string, FieldDefinition> userFields = {
        {"id", scalar(ScalarType::ID)},
        {"name", scalar(ScalarType::STRING)},
        {"email", scalar(ScalarType::STRING)}
    };

    map<string, FieldDefinition> productFields = {
        {"id", scalar(ScalarType::ID)},
        {"name", scalar(ScalarType::STRING)},
        {"price", scalar(ScalarType::FLOAT)},
        {"stock", scalar(ScalarType::INTEGER)}
    };

    map<string, FieldDefinition> queryFields = {
        {"users", scalar(ScalarType::STRING)},
        {"products", scalar(ScalarType::STRING)},
        {"product", FieldDefinition{
            TypeRef{ScalarType::STRING, false, false},
            {{"id", requiredArgument(ScalarType::ID)}}
        }}
    };

    map<string, FieldDefinition> mutationFields = {
        {"createOrder", FieldDefinition{
            TypeRef{ScalarType::STRING, false, false},
            {
                {"userId", requiredArgument(ScalarType::ID)},
                {"productId", requiredArgument(ScalarType::ID)},
                {"quantity", requiredArgument(ScalarType::INTEGER)}
            }
        }}
    };

    schema.registerType("User", userFields);
    schema.registerType("Product", productFields);
    schema.registerType("Query", queryFields);
    schema.registerType("Mutation", mutationFields);

    return schema;
}

// ---------------------------------------------------------
// 8. Demonstration
// ---------------------------------------------------------

int main() {
    try {
        InventoryRepository repository;
        GraphQLSchema schema = buildSchema();

        RequestContext context{
            "1",
            {"CUSTOMER"},
            "request-cpp-001"
        };

        GraphQLExecutor executor(
            schema,
            repository,
            context
        );

        cout << "GRAPHQL FUNDAMENTALS: C++17\n";

        cout << "\n1. QUERY PRODUCTS\n";

        Selection products{
            "products",
            {},
            {
                {"id", {}, {}},
                {"name", {}, {}},
                {"price", {}, {}},
                {"stock", {}, {}}
            }
        };

        executor.executeQuery({products});

        cout << "\n2. QUERY ONE PRODUCT\n";

        Selection product{
            "product",
            {{"id", GraphQLValue("101")}},
            {
                {"id", {}, {}},
                {"name", {}, {}},
                {"stock", {}, {}}
            }
        };

        executor.executeQuery({product});

        cout << "\n3. MUTATION: CREATE ORDER\n";

        Selection mutation{
            "createOrder",
            {
                {"userId", GraphQLValue("1")},
                {"productId", GraphQLValue("101")},
                {"quantity", GraphQLValue(2)}
            },
            {}
        };

        executor.executeMutation(mutation);

        cout << "\n4. INVENTORY AFTER MUTATION\n";
        cout << "Laptop stock: "
             << repository.product("101").stock << "\n";

        cout << "\n5. FAILURE: INVALID QUANTITY\n";

        try {
            Selection invalid{
                "createOrder",
                {
                    {"userId", GraphQLValue("1")},
                    {"productId", GraphQLValue("101")},
                    {"quantity", GraphQLValue(-5)}
                },
                {}
            };

            executor.executeMutation(invalid);
        }
        catch (const GraphQLError& error) {
            cout << "Expected error: " << error.what() << "\n";
        }

        cout << "\n6. FAILURE: MISSING REQUIRED ARGUMENT\n";

        try {
            Selection invalid{
                "product",
                {},
                {}
            };

            executor.executeQuery({invalid});
        }
        catch (const GraphQLError& error) {
            cout << "Expected error: " << error.what() << "\n";
        }

        cout << "\n7. FAILURE: AUTHORIZATION\n";

        try {
            RequestContext anonymous{
                "",
                {},
                "anonymous-request"
            };

            GraphQLExecutor anonymousExecutor(
                schema,
                repository,
                anonymous
            );

            anonymousExecutor.executeMutation(mutation);
        }
        catch (const GraphQLError& error) {
            cout << "Expected error: " << error.what() << "\n";
        }

        cout << "\n8. FAILURE: UNKNOWN FIELD\n";

        try {
            schema.getField("Product", "unknownField");
        }
        catch (const GraphQLError& error) {
            cout << "Expected error: " << error.what() << "\n";
        }

        cout << "\nC++17 execution completed.\n";
    }
    catch (const exception& error) {
        cerr << "Fatal execution error: "
             << error.what() << "\n";

        return 1;
    }

    return 0;
}

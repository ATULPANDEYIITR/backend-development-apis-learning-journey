/*
 * API PAGINATION AND GOVERNANCE ENGINE
 *
 * Offset Pagination, Cursor Pagination, and Keyset Pagination.
 *
 * C++17
 * Standard library only.
 *
 * Implements:
 * - Repository domain model.
 * - Three pagination strategies.
 * - Composite ordering keys.
 * - Cursor integrity using keyed hashing.
 * - Cursor expiration.
 * - Dataset version validation.
 * - Filtering and sorting.
 * - Merge-free immutable page results.
 * - Performance-aware STL operations.
 *
 * The demonstration cursor signer uses a deterministic keyed hash
 * for illustrating integrity validation. Production distributed
 * systems should use a vetted HMAC-SHA256 implementation.
 */

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include <functional>
#include <limits>

using namespace std;

using Timestamp = int64_t;

// ============================================================
// 1. DOMAIN TYPES
// ============================================================

enum class PaginationStrategy {
    OFFSET,
    CURSOR,
    KEYSET
};

enum class SortDirection {
    ASCENDING,
    DESCENDING
};

struct Product {
    int64_t id;
    string name;
    string category;
    double price;
    Timestamp createdAt;
    bool active;
};

struct PageRequest {
    size_t pageSize = 10;
    int64_t page = 1;
    optional<string> category;
};

struct CursorPosition {
    Timestamp createdAt;
    int64_t id;
};

struct CursorState {
    CursorPosition position;
    uint64_t repositoryVersion;
    Timestamp expiresAt;
    string filter;
};

struct PageResult {
    vector<Product> items;
    PaginationStrategy strategy;
    size_t pageSize;
    optional<size_t> totalItems;
    bool hasNext;
    bool hasPrevious;
    optional<string> nextCursor;
    optional<int64_t> nextOffset;
    double executionMs;
};

class PaginationException : public runtime_error {
public:
    explicit PaginationException(const string& message)
        : runtime_error(message) {}
};

// ============================================================
// 2. CONFIGURATION
// ============================================================

class PaginationConfig {
public:
    static constexpr size_t MAX_PAGE_SIZE = 100;
    static constexpr size_t DEFAULT_PAGE_SIZE = 10;
    static constexpr Timestamp CURSOR_TTL = 1800;

    static size_t validatePageSize(size_t value) {
        if (value < 1 || value > MAX_PAGE_SIZE) {
            throw PaginationException(
                "Page size must be between 1 and 100."
            );
        }

        return value;
    }

    static int64_t validatePage(int64_t page) {
        if (page < 1) {
            throw PaginationException(
                "Page number must be positive."
            );
        }

        return page;
    }
};

// ============================================================
// 3. REPOSITORY
// ============================================================

class ProductRepository {
private:
    map<int64_t, Product> products;
    uint64_t version = 1;

public:
    void insert(const Product& product) {
        if (product.id <= 0) {
            throw PaginationException("Invalid product ID.");
        }

        if (product.name.empty()) {
            throw PaginationException("Product name is required.");
        }

        if (product.price < 0 || !isfinite(product.price)) {
            throw PaginationException("Invalid product price.");
        }

        if (products.count(product.id)) {
            throw PaginationException("Duplicate product ID.");
        }

        products.emplace(product.id, product);
        ++version;
    }

    void update(const Product& product) {
        auto it = products.find(product.id);

        if (it == products.end()) {
            throw PaginationException("Product not found.");
        }

        if (product.price < 0 || !isfinite(product.price)) {
            throw PaginationException("Invalid product price.");
        }

        it->second = product;
        ++version;
    }

    void erase(int64_t id) {
        if (products.erase(id)) {
            ++version;
        }
    }

    vector<Product> findAll() const {
        vector<Product> result;
        result.reserve(products.size());

        for (const auto& [id, product] : products) {
            result.push_back(product);
        }

        return result;
    }

    uint64_t getVersion() const {
        return version;
    }

    size_t count() const {
        return products.size();
    }
};

// ============================================================
// 4. CURSOR SIGNING
// ============================================================

class CursorSigner {
private:
    string secret;

    static uint64_t hashString(const string& input) {
        // FNV-1a is used only as a compact demonstration hash.
        uint64_t hash = 14695981039346656037ULL;

        for (unsigned char ch : input) {
            hash ^= ch;
            hash *= 1099511628211ULL;
        }

        return hash;
    }

    static string toHex(uint64_t value) {
        stringstream stream;
        stream << hex << setw(16) << setfill('0') << value;
        return stream.str();
    }

public:
    explicit CursorSigner(string signingSecret)
        : secret(move(signingSecret)) {

        if (secret.size() < 32) {
            throw PaginationException(
                "Cursor secret must contain at least 32 characters."
            );
        }
    }

    string encode(const CursorState& state) const {
        string payload =
            to_string(state.position.createdAt) + "|" +
            to_string(state.position.id) + "|" +
            to_string(state.repositoryVersion) + "|" +
            to_string(state.expiresAt) + "|" +
            state.filter;

        const uint64_t signature = hashString(
            secret + "|" + payload
        );

        return payload + "|" + toHex(signature);
    }

    CursorState decode(const string& token) const {
        if (token.empty() || token.size() > 4096) {
            throw PaginationException("Invalid cursor size.");
        }

        vector<string> parts;
        string part;
        stringstream stream(token);

        while (getline(stream, part, '|')) {
            parts.push_back(part);
        }

        if (parts.size() != 6) {
            throw PaginationException("Malformed cursor.");
        }

        string payload = parts[0] + "|" + parts[1] + "|" +
                         parts[2] + "|" + parts[3] + "|" +
                         parts[4];

        if (toHex(hashString(secret + "|" + payload)) != parts[5]) {
            throw PaginationException(
                "Cursor authentication failed."
            );
        }

        CursorState state;

        try {
            state.position.createdAt = stoll(parts[0]);
            state.position.id = stoll(parts[1]);
            state.repositoryVersion = stoull(parts[2]);
            state.expiresAt = stoll(parts[3]);
            state.filter = parts[4];
        } catch (const exception&) {
            throw PaginationException("Invalid cursor fields.");
        }

        if (state.position.id <= 0) {
            throw PaginationException("Invalid cursor position.");
        }

        const Timestamp now = static_cast<Timestamp>(
            chrono::duration_cast<chrono::seconds>(
                chrono::system_clock::now().time_since_epoch()
            ).count()
        );

        if (state.expiresAt < now) {
            throw PaginationException("Cursor has expired.");
        }

        return state;
    }
};

// ============================================================
// 5. PAGINATION ENGINE
// ============================================================

class PaginationEngine {
private:
    const ProductRepository& repository;
    CursorSigner signer;

    vector<Product> query(
        optional<string> category
    ) const {

        vector<Product> result;

        for (const Product& product : repository.findAll()) {
            if (!product.active) {
                continue;
            }

            if (category && product.category != *category) {
                continue;
            }

            result.push_back(product);
        }

        sort(
            result.begin(),
            result.end(),
            [](const Product& a, const Product& b) {
                if (a.createdAt != b.createdAt) {
                    return a.createdAt < b.createdAt;
                }

                return a.id < b.id;
            }
        );

        return result;
    }

    static string normalizeFilter(
        const optional<string>& category
    ) {
        return category.value_or("");
    }

public:
    PaginationEngine(
        const ProductRepository& repositoryRef,
        const string& secret
    )
        : repository(repositoryRef), signer(secret) {}

    // --------------------------------------------------------
    // OFFSET PAGINATION
    // --------------------------------------------------------

    PageResult offset(
        const PageRequest& request
    ) const {

        const auto started = chrono::steady_clock::now();

        const size_t pageSize =
            PaginationConfig::validatePageSize(request.pageSize);

        const int64_t page =
            PaginationConfig::validatePage(request.page);

        const vector<Product> products = query(request.category);

        if (
            page - 1 >
            numeric_limits<int64_t>::max() /
            static_cast<int64_t>(pageSize)
        ) {
            throw PaginationException("Offset overflow.");
        }

        const int64_t offsetValue =
            (page - 1) * static_cast<int64_t>(pageSize);

        const size_t total = products.size();

        const size_t begin = min(
            static_cast<size_t>(offsetValue),
            total
        );

        const size_t end = min(
            begin + pageSize,
            total
        );

        vector<Product> items(
            products.begin() + begin,
            products.begin() + end
        );

        const bool hasNext = end < total;

        const auto finished = chrono::steady_clock::now();

        const double elapsed =
            chrono::duration<double, milli>(
                finished - started
            ).count();

        return {
            move(items),
            PaginationStrategy::OFFSET,
            pageSize,
            total,
            hasNext,
            page > 1 && begin > 0,
            nullopt,
            hasNext
                ? optional<int64_t>(offsetValue + pageSize)
                : nullopt,
            elapsed
        };
    }

    // --------------------------------------------------------
    // CURSOR PAGINATION
    // --------------------------------------------------------

    PageResult cursor(
        size_t pageSize,
        optional<string> token,
        optional<string> category
    ) const {

        const auto started = chrono::steady_clock::now();

        PaginationConfig::validatePageSize(pageSize);

        const auto products = query(category);

        const string filter = normalizeFilter(category);

        optional<CursorPosition> position;

        if (token) {
            CursorState state = signer.decode(*token);

            if (state.filter != filter) {
                throw PaginationException(
                    "Cursor filter does not match request."
                );
            }

            if (
                state.repositoryVersion != repository.getVersion()
            ) {
                throw PaginationException(
                    "Repository changed. Restart pagination."
                );
            }

            position = state.position;
        }

        vector<Product> remaining;

        for (const auto& product : products) {
            if (
                !position ||
                product.createdAt > position->createdAt ||
                (
                    product.createdAt == position->createdAt &&
                    product.id > position->id
                )
            ) {
                remaining.push_back(product);
            }
        }

        const bool hasNext = remaining.size() > pageSize;

        if (remaining.size() > pageSize) {
            remaining.resize(pageSize);
        }

        optional<string> nextCursor;

        if (hasNext && !remaining.empty()) {
            const Product& last = remaining.back();

            const Timestamp now = static_cast<Timestamp>(
                chrono::duration_cast<chrono::seconds>(
                    chrono::system_clock::now().time_since_epoch()
                ).count()
            );

            CursorState state{
                {last.createdAt, last.id},
                repository.getVersion(),
                now + PaginationConfig::CURSOR_TTL,
                filter
            };

            nextCursor = signer.encode(state);
        }

        const auto finished = chrono::steady_clock::now();

        const double elapsed =
            chrono::duration<double, milli>(
                finished - started
            ).count();

        return {
            move(remaining),
            PaginationStrategy::CURSOR,
            pageSize,
            nullopt,
            hasNext,
            token.has_value(),
            nextCursor,
            nullopt,
            elapsed
        };
    }

    // --------------------------------------------------------
    // KEYSET PAGINATION
    // --------------------------------------------------------

    PageResult keyset(
        size_t pageSize,
        optional<CursorPosition> boundary,
        optional<string> category,
        SortDirection direction = SortDirection::ASCENDING
    ) const {

        const auto started = chrono::steady_clock::now();

        PaginationConfig::validatePageSize(pageSize);

        if (boundary && boundary->id <= 0) {
            throw PaginationException("Invalid keyset ID.");
        }

        vector<Product> products = query(category);

        if (direction == SortDirection::DESCENDING) {
            reverse(products.begin(), products.end());
        }

        vector<Product> remaining;

        for (const Product& product : products) {
            bool eligible = !boundary.has_value();

            if (boundary) {
                const bool after =
                    product.createdAt > boundary->createdAt ||
                    (
                        product.createdAt == boundary->createdAt &&
                        product.id > boundary->id
                    );

                const bool before =
                    product.createdAt < boundary->createdAt ||
                    (
                        product.createdAt == boundary->createdAt &&
                        product.id < boundary->id
                    );

                eligible = direction == SortDirection::ASCENDING
                    ? after
                    : before;
            }

            if (eligible) {
                remaining.push_back(product);
            }
        }

        const bool hasNext = remaining.size() > pageSize;

        if (remaining.size() > pageSize) {
            remaining.resize(pageSize);
        }

        const auto finished = chrono::steady_clock::now();

        const double elapsed =
            chrono::duration<double, milli>(
                finished - started
            ).count();

        return {
            move(remaining),
            PaginationStrategy::KEYSET,
            pageSize,
            nullopt,
            hasNext,
            boundary.has_value(),
            nullopt,
            nullopt,
            elapsed
        };
    }
};

// ============================================================
// 6. SAMPLE DATA
// ============================================================

ProductRepository createRepository() {
    ProductRepository repository;

    const vector<string> categories = {
        "Electronics",
        "Books",
        "Furniture",
        "Software"
    };

    for (int64_t i = 1; i <= 40; ++i) {
        Product product{
            i,
            "Product " + to_string(i),
            categories[(i - 1) % categories.size()],
            100.0 + i * 25.0,
            1767225600 + i / 2,
            i % 13 != 0
        };

        repository.insert(product);
    }

    return repository;
}

// ============================================================
// 7. OUTPUT
// ============================================================

void printPage(const PageResult& result) {
    cout << "\nPage size: " << result.pageSize << '\n';

    cout << "Returned records: "
         << result.items.size() << '\n';

    if (result.totalItems) {
        cout << "Total records: "
             << *result.totalItems << '\n';
    } else {
        cout << "Total records: not calculated\n";
    }

    cout << "Has next: "
         << boolalpha << result.hasNext << '\n';

    cout << "Has previous: "
         << result.hasPrevious << '\n';

    cout << "Execution time: "
         << fixed << setprecision(4)
         << result.executionMs << " ms\n";

    for (const auto& product : result.items) {
        cout << product.id << " | "
             << product.name << " | "
             << product.category << " | "
             << product.createdAt << '\n';
    }

    if (result.nextOffset) {
        cout << "Next offset: "
             << *result.nextOffset << '\n';
    }

    if (result.nextCursor) {
        cout << "Next cursor: "
             << *result.nextCursor << '\n';
    }
}

// ============================================================
// 8. TESTING
// ============================================================

void runTests(
    const PaginationEngine& engine
) {
    PageRequest request;
    request.pageSize = 5;
    request.page = 1;

    auto first = engine.offset(request);

    request.page = 2;

    auto second = engine.offset(request);

    if (first.items.size() != 5) {
        throw runtime_error("Offset test failed.");
    }

    if (
        first.items.back().id ==
        second.items.front().id
    ) {
        throw runtime_error("Offset pages overlap.");
    }

    auto cursorFirst = engine.cursor(
        5,
        nullopt,
        nullopt
    );

    if (!cursorFirst.nextCursor) {
        throw runtime_error("Cursor generation failed.");
    }

    auto cursorSecond = engine.cursor(
        5,
        cursorFirst.nextCursor,
        nullopt
    );

    set<int64_t> firstIds;

    for (const auto& product : cursorFirst.items) {
        firstIds.insert(product.id);
    }

    for (const auto& product : cursorSecond.items) {
        if (firstIds.count(product.id)) {
            throw runtime_error("Cursor pages overlap.");
        }
    }

    auto keysetFirst = engine.keyset(
        5,
        nullopt,
        nullopt
    );

    if (keysetFirst.items.size() != 5) {
        throw runtime_error("Keyset test failed.");
    }

    const Product& last = keysetFirst.items.back();

    CursorPosition boundary{
        last.createdAt,
        last.id
    };

    auto keysetSecond = engine.keyset(
        5,
        boundary,
        nullopt
    );

    for (const auto& product : keysetSecond.items) {
        if (firstIds.count(product.id)) {
            throw runtime_error("Keyset pages overlap.");
        }
    }

    bool rejected = false;

    try {
        engine.offset(PageRequest{0, 1, nullopt});
    } catch (const PaginationException&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error("Invalid page size accepted.");
    }

    cout << "All C++ pagination tests passed.\n";
}

// ============================================================
// 9. MAIN
// ============================================================

int main() {
    try {
        ProductRepository repository = createRepository();

        const string secret =
            "production-demonstration-secret-key-2026";

        PaginationEngine engine(repository, secret);

        runTests(engine);

        cout << "\nOFFSET PAGINATION\n";

        PageRequest offsetRequest;
        offsetRequest.page = 2;
        offsetRequest.pageSize = 5;

        auto offsetResult = engine.offset(offsetRequest);

        printPage(offsetResult);

        cout << "\nCURSOR PAGINATION\n";

        auto cursorFirst = engine.cursor(
            5,
            nullopt,
            nullopt
        );

        printPage(cursorFirst);

        if (cursorFirst.nextCursor) {
            auto cursorSecond = engine.cursor(
                5,
                cursorFirst.nextCursor,
                nullopt
            );

            cout << "\nSecond cursor page\n";
            printPage(cursorSecond);
        }

        cout << "\nKEYSET PAGINATION\n";

        auto keysetFirst = engine.keyset(
            5,
            nullopt,
            nullopt
        );

        printPage(keysetFirst);

        if (!keysetFirst.items.empty()) {
            const auto& last = keysetFirst.items.back();

            auto keysetSecond = engine.keyset(
                5,
                CursorPosition{
                    last.createdAt,
                    last.id
                },
                nullopt
            );

            cout << "\nSecond keyset page\n";
            printPage(keysetSecond);
        }

        cout << "\nExecution completed.\n";

    } catch (const exception& error) {
        cerr << "Pagination failure: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

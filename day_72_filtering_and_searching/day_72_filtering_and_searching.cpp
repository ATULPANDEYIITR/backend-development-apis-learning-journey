#include <algorithm>
#include <cctype>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

class SearchError : public runtime_error {
public:
    explicit SearchError(const string& message)
        : runtime_error(message) {}
};

class ValidationError : public SearchError {
public:
    explicit ValidationError(const string& message)
        : SearchError(message) {}
};

enum class SortField {
    Id,
    Name,
    Category,
    Price,
    Rating
};

enum class SortDirection {
    Ascending,
    Descending
};

struct Product {
    int id;
    string name;
    string category;
    double price;
    double rating;
    bool active;
};

struct SearchCriteria {
    string keyword;
    optional<string> category;
    optional<double> minPrice;
    optional<double> maxPrice;
    optional<double> minRating;
    bool activeOnly = true;
    SortField sortBy = SortField::Name;
    SortDirection direction = SortDirection::Ascending;
    size_t limit = 10;
    size_t offset = 0;
};

struct SearchResult {
    vector<Product> products;
    size_t total = 0;
    size_t limit = 0;
    size_t offset = 0;

    bool hasNext() const {
        return offset + products.size() < total;
    }
};

string lowercase(string value) {
    transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char c) {
            return static_cast<char>(tolower(c));
        }
    );

    return value;
}

bool containsIgnoreCase(
    const string& source,
    const string& target
) {
    return lowercase(source).find(lowercase(target))
        != string::npos;
}

class ProductCatalog {
private:
    vector<Product> products;

    static void validate(const SearchCriteria& criteria) {
        if (criteria.limit < 1 || criteria.limit > 100) {
            throw ValidationError(
                "Limit must be between 1 and 100."
            );
        }

        if (criteria.minPrice &&
            (!isfinite(*criteria.minPrice) || *criteria.minPrice < 0)) {
            throw ValidationError("Invalid minimum price.");
        }

        if (criteria.maxPrice &&
            (!isfinite(*criteria.maxPrice) || *criteria.maxPrice < 0)) {
            throw ValidationError("Invalid maximum price.");
        }

        if (criteria.minPrice && criteria.maxPrice &&
            *criteria.minPrice > *criteria.maxPrice) {
            throw ValidationError(
                "Minimum price exceeds maximum price."
            );
        }

        if (criteria.minRating &&
            (!isfinite(*criteria.minRating) ||
             *criteria.minRating < 0 ||
             *criteria.minRating > 5)) {
            throw ValidationError(
                "Rating must be between 0 and 5."
            );
        }

        if (criteria.keyword.size() > 100) {
            throw ValidationError("Keyword is too long.");
        }

        if (criteria.category && criteria.category->size() > 80) {
            throw ValidationError("Category is too long.");
        }
    }

    static bool matches(
        const Product& product,
        const SearchCriteria& criteria
    ) {
        if (criteria.activeOnly && !product.active) {
            return false;
        }

        if (!criteria.keyword.empty()) {
            if (
                !containsIgnoreCase(product.name, criteria.keyword) &&
                !containsIgnoreCase(product.category, criteria.keyword)
            ) {
                return false;
            }
        }

        if (criteria.category &&
            lowercase(product.category) !=
            lowercase(*criteria.category)) {
            return false;
        }

        if (criteria.minPrice &&
            product.price < *criteria.minPrice) {
            return false;
        }

        if (criteria.maxPrice &&
            product.price > *criteria.maxPrice) {
            return false;
        }

        if (criteria.minRating &&
            product.rating < *criteria.minRating) {
            return false;
        }

        return true;
    }

    static bool compare(
        const Product& a,
        const Product& b,
        SortField field,
        SortDirection direction
    ) {
        bool less;

        switch (field) {
            case SortField::Id:
                less = a.id < b.id;
                break;

            case SortField::Name:
                less = lowercase(a.name) < lowercase(b.name);
                break;

            case SortField::Category:
                less = lowercase(a.category) < lowercase(b.category);
                break;

            case SortField::Price:
                less = a.price < b.price;
                break;

            case SortField::Rating:
                less = a.rating < b.rating;
                break;

            default:
                throw ValidationError("Unsupported sort field.");
        }

        bool equal = false;

        switch (field) {
            case SortField::Id:
                equal = a.id == b.id;
                break;
            case SortField::Name:
                equal = lowercase(a.name) == lowercase(b.name);
                break;
            case SortField::Category:
                equal = lowercase(a.category) == lowercase(b.category);
                break;
            case SortField::Price:
                equal = a.price == b.price;
                break;
            case SortField::Rating:
                equal = a.rating == b.rating;
                break;
        }

        if (equal) {
            return a.id < b.id;
        }

        return direction == SortDirection::Ascending
            ? less
            : !less;
    }

public:
    ProductCatalog() {
        products = {
            {1, "Laptop Pro", "Electronics", 95000, 4.8, true},
            {2, "Wireless Mouse", "Electronics", 1200, 4.2, true},
            {3, "Mechanical Keyboard", "Electronics", 4500, 4.6, true},
            {4, "Office Chair", "Furniture", 12500, 4.3, true},
            {5, "Standing Desk", "Furniture", 22000, 4.7, true},
            {6, "Old Monitor", "Electronics", 8000, 3.5, false},
            {7, "Notebook", "Stationery", 100, 4.0, true},
            {8, "Premium Headphones", "Electronics", 6500, 4.9, true},
            {9, "Desk Lamp", "Furniture", 1800, 3.9, true},
            {10, "USB Hub", "Electronics", 1500, 4.1, true}
        };
    }

    void addProduct(const Product& product) {
        if (product.id <= 0) {
            throw ValidationError("Product ID must be positive.");
        }

        if (product.name.empty() || product.category.empty()) {
            throw ValidationError(
                "Product name and category are required."
            );
        }

        if (!isfinite(product.price) || product.price < 0) {
            throw ValidationError("Invalid product price.");
        }

        if (!isfinite(product.rating) ||
            product.rating < 0 ||
            product.rating > 5) {
            throw ValidationError("Invalid product rating.");
        }

        auto existing = find_if(
            products.begin(),
            products.end(),
            [&](const Product& item) {
                return item.id == product.id;
            }
        );

        if (existing != products.end()) {
            throw ValidationError("Duplicate product ID.");
        }

        products.push_back(product);
    }

    SearchResult search(const SearchCriteria& criteria) const {
        validate(criteria);

        vector<Product> filtered;
        filtered.reserve(products.size());

        // Apply filters before sorting and pagination.
        for (const auto& product : products) {
            if (matches(product, criteria)) {
                filtered.push_back(product);
            }
        }

        const size_t total = filtered.size();

        sort(
            filtered.begin(),
            filtered.end(),
            [&](const Product& a, const Product& b) {
                return compare(
                    a,
                    b,
                    criteria.sortBy,
                    criteria.direction
                );
            }
        );

        SearchResult result;
        result.total = total;
        result.limit = criteria.limit;
        result.offset = criteria.offset;

        if (criteria.offset >= total) {
            return result;
        }

        const size_t end = min(
            total,
            criteria.offset + criteria.limit
        );

        result.products.assign(
            filtered.begin() + criteria.offset,
            filtered.begin() + end
        );

        return result;
    }

    vector<SearchResult> searchAllPages(
        SearchCriteria criteria
    ) const {
        validate(criteria);

        vector<SearchResult> pages;
        criteria.offset = 0;

        while (true) {
            SearchResult page = search(criteria);
            pages.push_back(page);

            if (!page.hasNext()) {
                break;
            }

            criteria.offset += criteria.limit;
        }

        return pages;
    }

    size_t size() const {
        return products.size();
    }
};

void printResults(const SearchResult& result) {
    cout << left
         << setw(5) << "ID"
         << setw(25) << "NAME"
         << setw(16) << "CATEGORY"
         << setw(12) << "PRICE"
         << setw(10) << "RATING"
         << '\n';

    cout << string(68, '-') << '\n';

    for (const auto& product : result.products) {
        cout << left
             << setw(5) << product.id
             << setw(25) << product.name
             << setw(16) << product.category
             << setw(12) << fixed << setprecision(2)
             << product.price
             << setw(10) << product.rating
             << '\n';
    }

    cout << "Matched: " << result.total
         << ", returned: " << result.products.size()
         << ", has next: "
         << (result.hasNext() ? "yes" : "no")
         << "\n\n";
}

void runTests(const ProductCatalog& catalog) {
    SearchCriteria criteria;

    criteria.category = "Electronics";

    auto result = catalog.search(criteria);

    if (result.total != 6) {
        throw runtime_error("Category filtering failed.");
    }

    criteria = SearchCriteria{};
    criteria.minPrice = 1000;
    criteria.maxPrice = 7000;
    criteria.minRating = 4.0;
    criteria.sortBy = SortField::Price;

    result = catalog.search(criteria);

    for (const auto& product : result.products) {
        if (product.price < 1000 ||
            product.price > 7000 ||
            product.rating < 4.0) {
            throw runtime_error("Combined filtering failed.");
        }
    }

    criteria = SearchCriteria{};
    criteria.keyword = "desk";

    result = catalog.search(criteria);

    if (result.total != 2) {
        throw runtime_error("Keyword search failed.");
    }

    criteria = SearchCriteria{};
    criteria.limit = 2;

    auto first = catalog.search(criteria);

    criteria.offset = 2;

    auto second = catalog.search(criteria);

    if (first.products.front().id ==
        second.products.front().id) {
        throw runtime_error("Pagination failed.");
    }

    criteria = SearchCriteria{};
    criteria.offset = 100;

    result = catalog.search(criteria);

    if (!result.products.empty()) {
        throw runtime_error("Out-of-range pagination failed.");
    }

    bool rejected = false;

    try {
        criteria = SearchCriteria{};
        criteria.minPrice = 10000;
        criteria.maxPrice = 100;

        catalog.search(criteria);
    } catch (const ValidationError&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error("Invalid price range was accepted.");
    }

    cout << "All automated tests passed.\n\n";
}

int main() {
    try {
        ProductCatalog catalog;

        cout << "PRODUCT FILTERING AND SEARCH ENGINE\n";
        cout << "Catalog records: " << catalog.size() << "\n\n";

        cout << "1. Keyword search\n";

        SearchCriteria criteria;
        criteria.keyword = "keyboard";

        printResults(catalog.search(criteria));

        cout << "2. Multiple filters\n";

        criteria = SearchCriteria{};
        criteria.category = "Electronics";
        criteria.minPrice = 1000;
        criteria.maxPrice = 10000;
        criteria.minRating = 4.0;
        criteria.sortBy = SortField::Rating;
        criteria.direction = SortDirection::Descending;

        printResults(catalog.search(criteria));

        cout << "3. Price sorting and pagination\n";

        criteria = SearchCriteria{};
        criteria.sortBy = SortField::Price;
        criteria.direction = SortDirection::Ascending;
        criteria.limit = 3;

        printResults(catalog.search(criteria));

        cout << "4. Search with no matching records\n";

        criteria = SearchCriteria{};
        criteria.keyword = "nonexistent";

        printResults(catalog.search(criteria));

        cout << "5. Multi-page retrieval\n";

        criteria = SearchCriteria{};
        criteria.limit = 3;

        auto pages = catalog.searchAllPages(criteria);

        for (size_t i = 0; i < pages.size(); ++i) {
            cout << "Page " << i + 1 << '\n';
            printResults(pages[i]);
        }

        cout << "6. Automated tests\n";
        runTests(catalog);

        cout << "7. Validation failure\n";

        try {
            criteria = SearchCriteria{};
            criteria.minRating = 8;

            catalog.search(criteria);
        } catch (const ValidationError& error) {
            cout << "Rejected: " << error.what() << '\n';
        }

        cout << "\n8. Duplicate insertion protection\n";

        try {
            catalog.addProduct({
                1, "Duplicate", "Electronics", 500, 4.0, true
            });
        } catch (const ValidationError& error) {
            cout << "Rejected: " << error.what() << '\n';
        }

    } catch (const exception& error) {
        cerr << "Application failure: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}

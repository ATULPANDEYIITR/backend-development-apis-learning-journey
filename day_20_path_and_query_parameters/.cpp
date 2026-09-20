// File: cpp/main.cpp

#include <algorithm>
#include <cctype>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

struct Product {
    int id;
    std::string name;
    std::string category;
    double price;
    int stock;
};

struct QueryParameters {
    std::optional<std::string> category;
    std::optional<double> min_price;
    std::optional<double> max_price;
    std::optional<std::string> search;
    bool in_stock = false;
    int skip = 0;
    int limit = 5;
};

std::string to_lower(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        }
    );

    return value;
}

void validate_query(const QueryParameters& query) {
    if (query.skip < 0) {
        throw std::invalid_argument("skip must be greater than or equal to zero");
    }

    if (query.limit < 1 || query.limit > 20) {
        throw std::invalid_argument("limit must be between 1 and 20");
    }

    if (query.min_price && *query.min_price < 0) {
        throw std::invalid_argument("min_price cannot be negative");
    }

    if (query.max_price && *query.max_price < 0) {
        throw std::invalid_argument("max_price cannot be negative");
    }

    if (query.min_price && query.max_price &&
        *query.min_price > *query.max_price) {
        throw std::invalid_argument(
            "min_price must be less than or equal to max_price"
        );
    }
}

std::vector<Product> filter_products(
    const std::vector<Product>& products,
    const QueryParameters& query
) {
    validate_query(query);

    std::vector<Product> filtered;

    const std::optional<std::string> category =
        query.category ? std::optional(to_lower(*query.category)) : std::nullopt;

    const std::optional<std::string> search =
        query.search ? std::optional(to_lower(*query.search)) : std::nullopt;

    for (const Product& product : products) {
        if (category && to_lower(product.category) != *category) {
            continue;
        }

        if (query.min_price && product.price < *query.min_price) {
            continue;
        }

        if (query.max_price && product.price > *query.max_price) {
            continue;
        }

        if (search && to_lower(product.name).find(*search) == std::string::npos) {
            continue;
        }

        if (query.in_stock && product.stock == 0) {
            continue;
        }

        filtered.push_back(product);
    }

    const std::size_t start = static_cast<std::size_t>(query.skip);

    if (start >= filtered.size()) {
        return {};
    }

    const std::size_t end = std::min(
        start + static_cast<std::size_t>(query.limit),
        filtered.size()
    );

    return {
        filtered.begin() + static_cast<std::ptrdiff_t>(start),
        filtered.begin() + static_cast<std::ptrdiff_t>(end)
    };
}

void print_products(const std::vector<Product>& products) {
    if (products.empty()) {
        std::cout << "No matching products.\n";
        return;
    }

    for (const Product& product : products) {
        std::cout
            << product.id << " | "
            << product.name << " | "
            << product.category << " | $"
            << product.price << " | stock: "
            << product.stock << '\n';
    }
}

int main() {
    const std::vector<Product> products = {
        {1, "Mechanical Keyboard", "electronics", 89.99, 24},
        {2, "Wireless Mouse", "electronics", 39.99, 51},
        {3, "USB-C Hub", "electronics", 29.99, 37},
        {4, "Notebook", "stationery", 5.49, 100},
        {5, "Desk Lamp", "home", 44.99, 18},
        {6, "Office Chair", "furniture", 219.99, 7},
        {7, "Monitor Stand", "furniture", 59.99, 12},
        {8, "Python Handbook", "books", 34.99, 31},
    };

    try {
        QueryParameters query;
        query.category = "electronics";
        query.min_price = 30.0;
        query.max_price = 100.0;
        query.in_stock = true;
        query.limit = 10;

        const std::vector<Product> results =
            filter_products(products, query);

        std::cout << "Filtered products:\n";
        print_products(results);

        std::cout << "\nPath parameter example:\n";

        const int product_id = 2;

        const auto match = std::find_if(
            products.begin(),
            products.end(),
            [product_id](const Product& product) {
                return product.id == product_id;
            }
        );

        if (match == products.end()) {
            std::cout << "Product not found.\n";
        } else {
            std::cout << "Found: " << match->name << '\n';
        }
    } catch (const std::invalid_argument& error) {
        std::cerr << "Validation error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}

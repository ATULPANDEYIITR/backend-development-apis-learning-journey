// File: cpp/tests.cpp

#include <cassert>
#include <stdexcept>
#include <string>
#include <vector>

#include "../main.cpp"

int main() {
    const std::vector<Product> products = {
        {1, "Mechanical Keyboard", "electronics", 89.99, 24},
        {2, "Wireless Mouse", "electronics", 39.99, 51},
        {3, "USB-C Hub", "electronics", 29.99, 37},
        {4, "Notebook", "stationery", 5.49, 100},
    };

    {
        QueryParameters query;
        query.category = "electronics";

        const auto result = filter_products(products, query);

        assert(result.size() == 3);
    }

    {
        QueryParameters query;
        query.min_price = 40.0;
        query.max_price = 100.0;

        const auto result = filter_products(products, query);

        assert(result.size() == 1);
        assert(result.front().name == "Mechanical Keyboard");
    }

    {
        QueryParameters query;
        query.search = "mouse";

        const auto result = filter_products(products, query);

        assert(result.size() == 1);
        assert(result.front().id == 2);
    }

    {
        QueryParameters query;
        query.limit = 1;
        query.skip = 1;

        const auto result = filter_products(products, query);

        assert(result.size() == 1);
        assert(result.front().id == 2);
    }

    {
        QueryParameters query;
        query.limit = 0;

        bool rejected = false;

        try {
            filter_products(products, query);
        } catch (const std::invalid_argument&) {
            rejected = true;
        }

        assert(rejected);
    }

    {
        QueryParameters query;
        query.min_price = 100.0;
        query.max_price = 50.0;

        bool rejected = false;

        try {
            filter_products(products, query);
        } catch (const std::invalid_argument&) {
            rejected = true;
        }

        assert(rejected);
    }

    return 0;
}

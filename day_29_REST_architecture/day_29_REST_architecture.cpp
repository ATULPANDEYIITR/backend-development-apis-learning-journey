/*
 * REST Architecture Case Study
 * =============================
 *
 * C++17 implementation of a small resource-oriented Book Catalog API.
 *
 * The case study demonstrates how REST ideas can influence the design of a
 * realistic service:
 *
 *   - Resources and resource identifiers
 *   - Representations
 *   - Uniform interface
 *   - HTTP method semantics
 *   - Stateless request processing
 *   - CRUD operations
 *   - Validation
 *   - Status codes
 *   - Hypermedia links
 *   - ETags and conditional updates
 *   - Pagination
 *   - Error handling
 *   - Thread-safe resource storage
 *   - Complexity and scalability considerations
 *
 * No third-party library is required.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic rest_architecture.cpp -o rest_demo
 *
 * Run:
 *   ./rest_demo
 */

#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

// ============================================================================
// 1. UTILITY FUNCTIONS
// ============================================================================

std::string trim(const std::string& value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return "";
    }

    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string jsonEscape(const std::string& value) {
    std::string output;

    for (const char character : value) {
        switch (character) {
            case '"':
                output += "\\\"";
                break;
            case '\\':
                output += "\\\\";
                break;
            case '\n':
                output += "\\n";
                break;
            case '\r':
                output += "\\r";
                break;
            case '\t':
                output += "\\t";
                break;
            default:
                output += character;
        }
    }

    return output;
}

std::string simpleHash(const std::string& input) {
    /*
     * This is intentionally a simple deterministic hash for demonstrating
     * the ETag concept. It is NOT a cryptographic hash and must not be used
     * as a production security primitive.
     */
    std::size_t hash = 1469598103934665603ULL;

    for (unsigned char character : input) {
        hash ^= character;
        hash *= 1099511628211ULL;
    }

    std::ostringstream stream;
    stream << std::hex << hash;
    return stream.str();
}


// ============================================================================
// 2. HTTP-LIKE DATA STRUCTURES
// ============================================================================

enum class HttpMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE_METHOD,
    UNKNOWN
};

std::string methodName(HttpMethod method) {
    switch (method) {
        case HttpMethod::GET:
            return "GET";
        case HttpMethod::POST:
            return "POST";
        case HttpMethod::PUT:
            return "PUT";
        case HttpMethod::PATCH:
            return "PATCH";
        case HttpMethod::DELETE_METHOD:
            return "DELETE";
        default:
            return "UNKNOWN";
    }
}

struct Request {
    HttpMethod method;
    std::string path;
    std::map<std::string, std::string> query;
    std::map<std::string, std::string> headers;
    std::string body;
};

struct Response {
    int status = 500;
    std::map<std::string, std::string> headers;
    std::string body;
};

std::string statusText(int status) {
    switch (status) {
        case 200:
            return "OK";
        case 201:
            return "Created";
        case 204:
            return "No Content";
        case 304:
            return "Not Modified";
        case 400:
            return "Bad Request";
        case 404:
            return "Not Found";
        case 405:
            return "Method Not Allowed";
        case 409:
            return "Conflict";
        case 412:
            return "Precondition Failed";
        case 413:
            return "Payload Too Large";
        case 500:
            return "Internal Server Error";
        default:
            return "Unknown";
    }
}


// ============================================================================
// 3. DOMAIN RESOURCE
// ============================================================================

struct Book {
    int id;
    std::string title;
    std::string author;
    int year;
    std::string genre;
    int version = 1;

    std::string representation(
        const std::string& baseUrl
    ) const {
        /*
         * The public representation is deliberately not a serialization of
         * every internal field. A representation is an API contract, not a
         * direct dump of the database row.
         */
        std::ostringstream json;

        json << "{"
             << "\"id\":" << id << ","
             << "\"title\":\"" << jsonEscape(title) << "\","
             << "\"author\":\"" << jsonEscape(author) << "\","
             << "\"year\":" << year << ","
             << "\"genre\":\"" << jsonEscape(genre) << "\","
             << "\"links\":{"
             << "\"self\":\"" << baseUrl << "/books/" << id << "\","
             << "\"collection\":\"" << baseUrl << "/books\""
             << "}"
             << "}";

        return json.str();
    }
};


// ============================================================================
// 4. VALIDATION
// ============================================================================

class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};

void validateBook(
    const Book& book
) {
    if (trim(book.title).empty()) {
        throw ValidationError("title cannot be empty");
    }

    if (trim(book.author).empty()) {
        throw ValidationError("author cannot be empty");
    }

    if (trim(book.genre).empty()) {
        throw ValidationError("genre cannot be empty");
    }

    if (book.year <= 0 || book.year > 3000) {
        throw ValidationError("year must be between 1 and 3000");
    }
}


// ============================================================================
// 5. THREAD-SAFE RESOURCE REPOSITORY
// ============================================================================

class BookRepository {
private:
    std::unordered_map<int, Book> books_;
    int nextId_ = 1;
    mutable std::mutex mutex_;

public:
    std::vector<Book> list() const {
        std::lock_guard<std::mutex> lock(mutex_);

        std::vector<Book> result;
        result.reserve(books_.size());

        for (const auto& [id, book] : books_) {
            result.push_back(book);
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const Book& left, const Book& right) {
                return left.id < right.id;
            }
        );

        return result;
    }

    std::optional<Book> get(int id) const {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto iterator = books_.find(id);

        if (iterator == books_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    Book create(
        std::string title,
        std::string author,
        int year,
        std::string genre
    ) {
        Book book{
            nextId_,
            std::move(title),
            std::move(author),
            year,
            std::move(genre),
            1
        };

        validateBook(book);

        std::lock_guard<std::mutex> lock(mutex_);

        book.id = nextId_++;
        books_[book.id] = book;

        return book;
    }

    std::optional<Book> replace(
        int id,
        std::string title,
        std::string author,
        int year,
        std::string genre
    ) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = books_.find(id);

        if (iterator == books_.end()) {
            return std::nullopt;
        }

        Book replacement{
            id,
            std::move(title),
            std::move(author),
            year,
            std::move(genre),
            iterator->second.version + 1
        };

        validateBook(replacement);

        iterator->second = replacement;

        return iterator->second;
    }

    std::optional<Book> patch(
        int id,
        const std::optional<std::string>& title,
        const std::optional<std::string>& author,
        const std::optional<int>& year,
        const std::optional<std::string>& genre
    ) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = books_.find(id);

        if (iterator == books_.end()) {
            return std::nullopt;
        }

        Book updated = iterator->second;

        if (title.has_value()) {
            updated.title = *title;
        }

        if (author.has_value()) {
            updated.author = *author;
        }

        if (year.has_value()) {
            updated.year = *year;
        }

        if (genre.has_value()) {
            updated.genre = *genre;
        }

        updated.version++;

        validateBook(updated);

        iterator->second = updated;

        return updated;
    }

    bool erase(int id) {
        std::lock_guard<std::mutex> lock(mutex_);
        return books_.erase(id) > 0;
    }
};


// ============================================================================
// 6. REPRESENTATION AND ETAG FUNCTIONS
// ============================================================================

std::string etagFor(
    const Book& book,
    const std::string& baseUrl
) {
    return "\"" + simpleHash(book.representation(baseUrl)) + "\"";
}

Response jsonResponse(
    int status,
    std::string body
) {
    Response response;
    response.status = status;
    response.headers["Content-Type"] =
        "application/json; charset=utf-8";
    response.body = std::move(body);

    return response;
}

Response errorResponse(
    int status,
    const std::string& code,
    const std::string& message
) {
    std::ostringstream body;

    body << "{"
         << "\"error\":{"
         << "\"code\":\"" << jsonEscape(code) << "\","
         << "\"message\":\"" << jsonEscape(message) << "\""
         << "}"
         << "}";

    return jsonResponse(status, body.str());
}


// ============================================================================
// 7. APPLICATION SERVICE
// ============================================================================

class BookApi {
private:
    BookRepository repository_;
    std::string baseUrl_;

    static std::optional<int> queryInteger(
        const Request& request,
        const std::string& key
    ) {
        const auto iterator = request.query.find(key);

        if (iterator == request.query.end()) {
            return std::nullopt;
        }

        try {
            std::size_t consumed = 0;
            const int value = std::stoi(iterator->second, &consumed);

            if (consumed != iterator->second.size()) {
                return std::nullopt;
            }

            return value;
        } catch (const std::exception&) {
            return std::nullopt;
        }
    }

    static bool headerEquals(
        const Request& request,
        const std::string& name,
        const std::string& expected
    ) {
        const auto iterator = request.headers.find(name);

        return iterator != request.headers.end()
            && iterator->second == expected;
    }

    Response getCollection(
        const Request& request
    ) {
        const auto limitValue = queryInteger(request, "limit");
        const auto offsetValue = queryInteger(request, "offset");

        const int limit = limitValue.value_or(20);
        const int offset = offsetValue.value_or(0);

        if (limit < 1 || limit > 100) {
            return errorResponse(
                400,
                "invalid_query",
                "limit must be between 1 and 100"
            );
        }

        if (offset < 0) {
            return errorResponse(
                400,
                "invalid_query",
                "offset cannot be negative"
            );
        }

        std::vector<Book> books = repository_.list();

        const auto genreIterator =
            request.query.find("genre");

        if (genreIterator != request.query.end()) {
            books.erase(
                std::remove_if(
                    books.begin(),
                    books.end(),
                    [&](const Book& book) {
                        return book.genre != genreIterator->second;
                    }
                ),
                books.end()
            );
        }

        const std::size_t total = books.size();

        const std::size_t start =
            static_cast<std::size_t>(offset);

        const std::size_t end =
            std::min(
                start + static_cast<std::size_t>(limit),
                books.size()
            );

        std::ostringstream body;

        body << "{"
             << "\"items\":[";

        bool first = true;

        if (start < books.size()) {
            for (std::size_t index = start; index < end; ++index) {
                if (!first) {
                    body << ",";
                }

                body << books[index].representation(baseUrl_);
                first = false;
            }
        }

        body << "],"
             << "\"pagination\":{"
             << "\"offset\":" << offset << ","
             << "\"limit\":" << limit << ","
             << "\"count\":"
             << (start < books.size() ? end - start : 0)
             << ","
             << "\"total\":" << total
             << "},"
             << "\"links\":{"
             << "\"self\":\""
             << baseUrl_
             << "/books?offset="
             << offset
             << "&limit="
             << limit
             << "\"";

        if (start + static_cast<std::size_t>(limit) < total) {
            body << ",\"next\":\""
                 << baseUrl_
                 << "/books?offset="
                 << (offset + limit)
                 << "&limit="
                 << limit
                 << "\"";
        }

        if (offset > 0) {
            const int previous =
                std::max(0, offset - limit);

            body << ",\"previous\":\""
                 << baseUrl_
                 << "/books?offset="
                 << previous
                 << "&limit="
                 << limit
                 << "\"";
        }

        body << "}"
             << "}";

        Response response = jsonResponse(
            200,
            body.str()
        );

        response.headers["Cache-Control"] = "no-cache";

        return response;
    }

    Response getBook(
        const Request& request,
        int id
    ) {
        const auto book = repository_.get(id);

        if (!book.has_value()) {
            return errorResponse(
                404,
                "not_found",
                "Book does not exist"
            );
        }

        const std::string etag =
            etagFor(*book, baseUrl_);

        const auto iterator =
            request.headers.find("if-none-match");

        if (
            iterator != request.headers.end()
            && iterator->second == etag
        ) {
            Response response;
            response.status = 304;
            response.headers["ETag"] = etag;
            return response;
        }

        Response response = jsonResponse(
            200,
            book->representation(baseUrl_)
        );

        response.headers["ETag"] = etag;
        response.headers["Cache-Control"] = "max-age=60";

        return response;
    }

public:
    explicit BookApi(
        std::string baseUrl
    )
        : baseUrl_(std::move(baseUrl)) {}

    void seed() {
        repository_.create(
            "The Pragmatic Programmer",
            "Andrew Hunt",
            1999,
            "software"
        );

        repository_.create(
            "Clean Architecture",
            "Robert C. Martin",
            2017,
            "software"
        );

        repository_.create(
            "Designing Data-Intensive Applications",
            "Martin Kleppmann",
            2017,
            "data"
        );
    }

    Response handle(
        const Request& request
    ) {
        /*
         * This router intentionally uses resource-oriented paths rather than
         * action-oriented endpoints such as /getBook or /deleteBook.
         */
        if (request.path == "/books") {
            if (request.method == HttpMethod::GET) {
                return getCollection(request);
            }

            if (request.method == HttpMethod::POST) {
                /*
                 * A complete JSON parser would normally be used here.
                 * To keep the case study dependency-free, POST input is
                 * represented by a deliberately constrained request format:
                 *
                 * title=...;author=...;year=...;genre=...
                 *
                 * The application still treats the result as a resource
                 * creation operation.
                 */
                std::map<std::string, std::string> fields;
                std::stringstream input(request.body);
                std::string pair;

                while (std::getline(input, pair, ';')) {
                    const auto separator = pair.find('=');

                    if (separator == std::string::npos) {
                        return errorResponse(
                            400,
                            "invalid_representation",
                            "Malformed field"
                        );
                    }

                    const std::string key =
                        trim(pair.substr(0, separator));

                    const std::string value =
                        trim(pair.substr(separator + 1));

                    fields[key] = value;
                }

                try {
                    const int year =
                        std::stoi(fields.at("year"));

                    Book book = repository_.create(
                        fields.at("title"),
                        fields.at("author"),
                        year,
                        fields.at("genre")
                    );

                    Response response = jsonResponse(
                        201,
                        book.representation(baseUrl_)
                    );

                    response.headers["Location"] =
                        baseUrl_
                        + "/books/"
                        + std::to_string(book.id);

                    response.headers["ETag"] =
                        etagFor(book, baseUrl_);

                    return response;
                } catch (
                    const std::out_of_range&
                    ) {
                    return errorResponse(
                        400,
                        "invalid_representation",
                        "Missing required field"
                    );
                } catch (
                    const std::invalid_argument&
                    ) {
                    return errorResponse(
                        400,
                        "invalid_representation",
                        "year must be an integer"
                    );
                } catch (
                    const ValidationError& error
                    ) {
                    return errorResponse(
                        400,
                        "invalid_representation",
                        error.what()
                    );
                }
            }

            Response response = errorResponse(
                405,
                "method_not_allowed",
                "Method not allowed"
            );

            response.headers["Allow"] = "GET, POST";
            return response;
        }

        /*
         * Match /books/{id}.
         */
        const std::regex pattern(
            R"(^/books/([0-9]+)$)"
        );

        std::smatch match;

        if (
            std::regex_match(
                request.path,
                match,
                pattern
            )
        ) {
            const int id = std::stoi(match[1].str());

            if (request.method == HttpMethod::GET) {
                return getBook(request, id);
            }

            if (request.method == HttpMethod::PUT) {
                const auto existing =
                    repository_.get(id);

                if (!existing.has_value()) {
                    return errorResponse(
                        404,
                        "not_found",
                        "Book does not exist"
                    );
                }

                const std::string currentEtag =
                    etagFor(*existing, baseUrl_);

                const auto ifMatch =
                    request.headers.find("if-match");

                if (
                    ifMatch != request.headers.end()
                    && ifMatch->second != currentEtag
                ) {
                    return errorResponse(
                        412,
                        "precondition_failed",
                        "The resource changed before replacement"
                    );
                }

                try {
                    /*
                     * PUT replaces the complete representation.
                     */
                    std::map<std::string, std::string> fields;
                    std::stringstream input(request.body);
                    std::string pair;

                    while (std::getline(input, pair, ';')) {
                        const auto separator = pair.find('=');

                        if (separator == std::string::npos) {
                            throw ValidationError(
                                "Malformed replacement"
                            );
                        }

                        fields[
                            trim(pair.substr(0, separator))
                        ] =
                            trim(pair.substr(separator + 1));
                    }

                    Book replacement{
                        id,
                        fields.at("title"),
                        fields.at("author"),
                        std::stoi(fields.at("year")),
                        fields.at("genre"),
                        existing->version + 1
                    };

                    validateBook(replacement);

                    auto updated = repository_.replace(
                        id,
                        replacement.title,
                        replacement.author,
                        replacement.year,
                        replacement.genre
                    );

                    if (!updated.has_value()) {
                        return errorResponse(
                            404,
                            "not_found",
                            "Book does not exist"
                        );
                    }

                    Response response = jsonResponse(
                        200,
                        updated->representation(baseUrl_)
                    );

                    response.headers["ETag"] =
                        etagFor(*updated, baseUrl_);

                    return response;
                } catch (
                    const std::exception& error
                    ) {
                    return errorResponse(
                        400,
                        "invalid_representation",
                        error.what()
                    );
                }
            }

            if (request.method == HttpMethod::PATCH) {
                const auto existing =
                    repository_.get(id);

                if (!existing.has_value()) {
                    return errorResponse(
                        404,
                        "not_found",
                        "Book does not exist"
                    );
                }

                const std::string currentEtag =
                    etagFor(*existing, baseUrl_);

                const auto ifMatch =
                    request.headers.find("if-match");

                if (
                    ifMatch != request.headers.end()
                    && ifMatch->second != currentEtag
                ) {
                    return errorResponse(
                        412,
                        "precondition_failed",
                        "The resource changed before patch"
                    );
                }

                /*
                 * The educational PATCH syntax accepts:
                 *   title=value;genre=value
                 *
                 * Missing fields remain unchanged.
                 */
                std::optional<std::string> title;
                std::optional<std::string> author;
                std::optional<int> year;
                std::optional<std::string> genre;

                std::stringstream input(request.body);
                std::string pair;

                try {
                    while (std::getline(input, pair, ';')) {
                        const auto separator = pair.find('=');

                        if (separator == std::string::npos) {
                            throw ValidationError(
                                "Malformed patch field"
                            );
                        }

                        const std::string key =
                            trim(pair.substr(0, separator));

                        const std::string value =
                            trim(pair.substr(separator + 1));

                        if (key == "title") {
                            title = value;
                        } else if (key == "author") {
                            author = value;
                        } else if (key == "year") {
                            year = std::stoi(value);
                        } else if (key == "genre") {
                            genre = value;
                        } else {
                            throw ValidationError(
                                "Unknown patch field"
                            );
                        }
                    }

                    const auto updated =
                        repository_.patch(
                            id,
                            title,
                            author,
                            year,
                            genre
                        );

                    if (!updated.has_value()) {
                        return errorResponse(
                            404,
                            "not_found",
                            "Book does not exist"
                        );
                    }

                    Response response = jsonResponse(
                        200,
                        updated->representation(baseUrl_)
                    );

                    response.headers["ETag"] =
                        etagFor(*updated, baseUrl_);

                    return response;
                } catch (
                    const std::exception& error
                    ) {
                    return errorResponse(
                        400,
                        "invalid_patch",
                        error.what()
                    );
                }
            }

            if (request.method == HttpMethod::DELETE_METHOD) {
                const auto existing =
                    repository_.get(id);

                /*
                 * DELETE is idempotent: once the resource is absent,
                 * repeating the operation does not create another state.
                 */
                if (!existing.has_value()) {
                    return Response{204, {}, ""};
                }

                const std::string currentEtag =
                    etagFor(*existing, baseUrl_);

                const auto ifMatch =
                    request.headers.find("if-match");

                if (
                    ifMatch != request.headers.end()
                    && ifMatch->second != currentEtag
                ) {
                    return errorResponse(
                        412,
                        "precondition_failed",
                        "The resource changed before deletion"
                    );
                }

                repository_.erase(id);

                return Response{204, {}, ""};
            }

            Response response = errorResponse(
                405,
                "method_not_allowed",
                "Method not allowed"
            );

            response.headers["Allow"] =
                "GET, PUT, PATCH, DELETE";

            return response;
        }

        return errorResponse(
            404,
            "not_found",
            "The requested resource does not exist"
        );
    }
};


// ============================================================================
// 8. OUTPUT HELPERS
// ============================================================================

void printResponse(
    const std::string& description,
    const Response& response
) {
    std::cout
        << "\n--- "
        << description
        << " ---\n";

    std::cout
        << response.status
        << " "
        << statusText(response.status)
        << "\n";

    for (const auto& [name, value] : response.headers) {
        std::cout
            << name
            << ": "
            << value
            << "\n";
    }

    if (!response.body.empty()) {
        std::cout
            << response.body
            << "\n";
    }
}


// ============================================================================
// 9. CASE STUDY
// ============================================================================

void runCaseStudy() {
    BookApi api("http://localhost:8000");
    api.seed();

    std::cout
        << "============================================================\n"
        << "REST BOOK CATALOG CASE STUDY\n"
        << "============================================================\n";

    /*
     * Resource collection:
     *   /books
     *
     * Individual resource:
     *   /books/{id}
     *
     * Notice that the URI identifies the resource. The HTTP method describes
     * the requested operation.
     */
    Request listRequest{
        HttpMethod::GET,
        "/books",
        {},
        {},
        ""
    };

    printResponse(
        "GET /books",
        api.handle(listRequest)
    );

    Request createRequest{
        HttpMethod::POST,
        "/books",
        {},
        {},
        "title=REST in Practice;"
        "author=Jim Webber;"
        "year=2010;"
        "genre=web"
    };

    Response created =
        api.handle(createRequest);

    printResponse(
        "POST /books",
        created
    );

    /*
     * The new resource URI comes from the Location header.
     */
    const std::string location =
        created.headers.at("Location");

    const int createdId =
        std::stoi(
            location.substr(
                location.find_last_of('/') + 1
            )
        );

    Request getCreated{
        HttpMethod::GET,
        "/books/" + std::to_string(createdId),
        {},
        {},
        ""
    };

    Response fetched =
        api.handle(getCreated);

    printResponse(
        "GET /books/{id}",
        fetched
    );

    const std::string etag =
        fetched.headers.at("ETag");

    /*
     * Conditional GET demonstrates cache validation.
     */
    Request conditionalGet{
        HttpMethod::GET,
        "/books/" + std::to_string(createdId),
        {},
        {{"if-none-match", etag}},
        ""
    };

    printResponse(
        "Conditional GET using If-None-Match",
        api.handle(conditionalGet)
    );

    /*
     * PATCH modifies only one field.
     */
    Request patchRequest{
        HttpMethod::PATCH,
        "/books/" + std::to_string(createdId),
        {},
        {{"if-match", etag}},
        "genre=web-architecture"
    };

    Response patched =
        api.handle(patchRequest);

    printResponse(
        "PATCH /books/{id}",
        patched
    );

    /*
     * Demonstrate optimistic concurrency:
     *
     * 1. Capture the new ETag.
     * 2. Modify the resource.
     * 3. Attempt another update with the stale ETag.
     */
    const std::string newEtag =
        patched.headers.at("ETag");

    Request anotherClientUpdate{
        HttpMethod::PATCH,
        "/books/" + std::to_string(createdId),
        {},
        {{"if-match", newEtag}},
        "genre=client-b"
    };

    api.handle(anotherClientUpdate);

    Request staleClientUpdate{
        HttpMethod::PATCH,
        "/books/" + std::to_string(createdId),
        {},
        {{"if-match", newEtag}},
        "genre=client-a"
    };

    printResponse(
        "PATCH using stale ETag",
        api.handle(staleClientUpdate)
    );

    /*
     * DELETE can be repeated without creating additional state transitions.
     */
    Request deleteRequest{
        HttpMethod::DELETE_METHOD,
        "/books/" + std::to_string(createdId),
        {},
        {},
        ""
    };

    printResponse(
        "DELETE /books/{id}",
        api.handle(deleteRequest)
    );

    printResponse(
        "Repeat DELETE /books/{id}",
        api.handle(deleteRequest)
    );
}


// ============================================================================
// 10. EDGE CASES AND DESIGN NOTES
// ============================================================================

void demonstrateEdgeCases() {
    BookApi api("http://localhost:8000");
    api.seed();

    std::cout
        << "\n============================================================\n"
        << "EDGE CASES\n"
        << "============================================================\n";

    Request missingResource{
        HttpMethod::GET,
        "/books/99999",
        {},
        {},
        ""
    };

    printResponse(
        "GET missing resource",
        api.handle(missingResource)
    );

    Request invalidQuery{
        HttpMethod::GET,
        "/books",
        {{"limit", "500"}},
        {},
        ""
    };

    printResponse(
        "GET with invalid limit",
        api.handle(invalidQuery)
    );

    Request unsupported{
        HttpMethod::PATCH,
        "/books/99999",
        {},
        {},
        ""
    };

    printResponse(
        "PATCH missing resource",
        api.handle(unsupported)
    );

    std::cout
        << "\nComplexity notes:\n"
        << "  ID lookup: average O(1) with unordered_map.\n"
        << "  Collection sorting: O(n log n).\n"
        << "  Filtering: O(n) in this demonstration.\n"
        << "  Database indexes can improve filtering in production.\n"
        << "  Offset pagination can become expensive for large offsets.\n"
        << "  Cursor/keyset pagination is useful for large datasets.\n";

    std::cout
        << "\nSecurity notes:\n"
        << "  HTTPS should protect production traffic.\n"
        << "  Authentication and authorization belong at the service boundary.\n"
        << "  Request bodies and query parameters require validation.\n"
        << "  Rate limiting and request-size limits reduce abuse risk.\n"
        << "  Internal exceptions should not be exposed directly to clients.\n";
}


// ============================================================================
// 11. MAIN
// ============================================================================

int main() {
    try {
        runCaseStudy();
        demonstrateEdgeCases();

        std::cout
            << "\n============================================================\n"
            << "CASE STUDY COMPLETED\n"
            << "============================================================\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}

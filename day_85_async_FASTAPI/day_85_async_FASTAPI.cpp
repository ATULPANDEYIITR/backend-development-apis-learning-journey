#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <exception>
#include <functional>
#include <future>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Async FastAPI Engineering: Concurrent Request and Resource Engine
 *
 * C++17 standalone implementation.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -pthread async_engine.cpp -o async_engine
 *
 * Run:
 *   ./async_engine
 *
 * The program models:
 *   - Concurrent HTTP-style request processing
 *   - Bounded worker execution
 *   - Connection-pool capacity
 *   - Non-blocking task submission
 *   - Blocking versus non-blocking workloads
 *   - Request timeouts
 *   - Failure propagation
 *   - Resource lifecycle management
 */

using namespace std;
using namespace std::chrono;

// ---------------------------------------------------------
// Domain types
// ---------------------------------------------------------

enum class RequestStatus {
    PENDING,
    RUNNING,
    COMPLETED,
    FAILED,
    TIMED_OUT
};

enum class OperationType {
    DATABASE_READ,
    DATABASE_WRITE,
    CPU_COMPUTATION,
    BLOCKING_IO
};

string to_string(RequestStatus status) {
    switch (status) {
        case RequestStatus::PENDING: return "PENDING";
        case RequestStatus::RUNNING: return "RUNNING";
        case RequestStatus::COMPLETED: return "COMPLETED";
        case RequestStatus::FAILED: return "FAILED";
        case RequestStatus::TIMED_OUT: return "TIMED_OUT";
    }

    return "UNKNOWN";
}

struct Request {
    int id;
    OperationType operation;
    int duration_ms;
    string payload;
};

struct RequestResult {
    int request_id;
    RequestStatus status;
    string message;
    double elapsed_ms;
};

// ---------------------------------------------------------
// Thread-safe bounded executor
// ---------------------------------------------------------

class ThreadPool {
private:
    vector<thread> workers;

    queue<function<void()>> jobs;

    mutex queue_mutex;
    condition_variable condition;

    bool stopping = false;

    atomic<size_t> submitted{0};
    atomic<size_t> completed{0};

public:
    explicit ThreadPool(size_t worker_count) {
        if (worker_count == 0 || worker_count > 128) {
            throw invalid_argument("Invalid worker count");
        }

        for (size_t i = 0; i < worker_count; ++i) {
            workers.emplace_back([this]() {
                while (true) {
                    function<void()> job;

                    {
                        unique_lock<mutex> lock(queue_mutex);

                        condition.wait(lock, [this]() {
                            return stopping || !jobs.empty();
                        });

                        if (stopping && jobs.empty()) {
                            return;
                        }

                        job = move(jobs.front());
                        jobs.pop();
                    }

                    try {
                        job();
                    } catch (...) {
                        // Each submitted task owns its exception state.
                    }

                    completed++;
                }
            });
        }
    }

    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;

    template<typename Function>
    auto submit(Function&& function)
        -> future<typename result_of<Function()>::type> {

        using Result = typename result_of<Function()>::type;

        auto task = make_shared<packaged_task<Result()>>(
            forward<Function>(function)
        );

        future<Result> result = task->get_future();

        {
            lock_guard<mutex> lock(queue_mutex);

            if (stopping) {
                throw runtime_error("Executor is shutting down");
            }

            if (jobs.size() >= 1000) {
                throw runtime_error("Executor queue is full");
            }

            jobs.emplace([task]() {
                (*task)();
            });

            submitted++;
        }

        condition.notify_one();

        return result;
    }

    size_t submitted_count() const {
        return submitted.load();
    }

    size_t completed_count() const {
        return completed.load();
    }

    ~ThreadPool() {
        {
            lock_guard<mutex> lock(queue_mutex);
            stopping = true;
        }

        condition.notify_all();

        for (auto& worker : workers) {
            if (worker.joinable()) {
                worker.join();
            }
        }
    }
};

// ---------------------------------------------------------
// Simulated database connection pool
// ---------------------------------------------------------

class ConnectionPool {
private:
    mutex pool_mutex;
    condition_variable available;

    size_t capacity;
    size_t active = 0;

public:
    explicit ConnectionPool(size_t maximum_connections)
        : capacity(maximum_connections) {

        if (capacity == 0) {
            throw invalid_argument(
                "Database pool capacity must be positive"
            );
        }
    }

    class Lease {
    private:
        ConnectionPool* owner;

    public:
        explicit Lease(ConnectionPool* pool)
            : owner(pool) {}

        Lease(const Lease&) = delete;
        Lease& operator=(const Lease&) = delete;

        Lease(Lease&& other) noexcept
            : owner(exchange(other.owner, nullptr)) {}

        ~Lease() {
            if (owner) {
                owner->release();
            }
        }
    };

    Lease acquire(milliseconds timeout) {
        unique_lock<mutex> lock(pool_mutex);

        bool acquired = available.wait_for(
            lock,
            timeout,
            [this]() {
                return active < capacity;
            }
        );

        if (!acquired) {
            throw runtime_error(
                "Database connection acquisition timed out"
            );
        }

        active++;

        return Lease(this);
    }

    void release() {
        {
            lock_guard<mutex> lock(pool_mutex);

            if (active == 0) {
                throw logic_error("Connection pool underflow");
            }

            active--;
        }

        available.notify_one();
    }

    size_t active_connections() {
        lock_guard<mutex> lock(pool_mutex);
        return active;
    }

    size_t maximum_connections() const {
        return capacity;
    }
};

// ---------------------------------------------------------
// Asynchronous request engine
// ---------------------------------------------------------

class RequestEngine {
private:
    ThreadPool executor;
    ConnectionPool database;

    atomic<int> successful{0};
    atomic<int> failed{0};

public:
    RequestEngine(size_t worker_count, size_t connection_count)
        : executor(worker_count),
          database(connection_count) {}

    future<RequestResult> submit(Request request) {

        if (request.id <= 0) {
            throw invalid_argument("Invalid request identifier");
        }

        if (request.duration_ms < 0 ||
            request.duration_ms > 10000) {
            throw invalid_argument("Invalid operation duration");
        }

        auto start = steady_clock::now();

        return executor.submit(
            [this, request, start]() -> RequestResult {

                try {
                    RequestStatus status = RequestStatus::RUNNING;

                    switch (request.operation) {

                        case OperationType::DATABASE_READ:
                        case OperationType::DATABASE_WRITE: {
                            // RAII automatically returns the connection.
                            auto lease = database.acquire(
                                milliseconds(2000)
                            );

                            this_thread::sleep_for(
                                milliseconds(request.duration_ms)
                            );

                            break;
                        }

                        case OperationType::CPU_COMPUTATION: {
                            volatile unsigned long long value = 0;

                            for (unsigned long long i = 0;
                                 i < 1000000;
                                 ++i) {
                                value += i % 17;
                            }

                            (void)value;
                            break;
                        }

                        case OperationType::BLOCKING_IO: {
                            // Represents synchronous blocking I/O.
                            this_thread::sleep_for(
                                milliseconds(request.duration_ms)
                            );

                            break;
                        }
                    }

                    status = RequestStatus::COMPLETED;
                    successful++;

                    double elapsed = duration<double, milli>(
                        steady_clock::now() - start
                    ).count();

                    return {
                        request.id,
                        status,
                        "Operation completed",
                        elapsed
                    };

                } catch (const exception& error) {

                    failed++;

                    double elapsed = duration<double, milli>(
                        steady_clock::now() - start
                    ).count();

                    return {
                        request.id,
                        RequestStatus::FAILED,
                        error.what(),
                        elapsed
                    };
                }
            }
        );
    }

    int success_count() const {
        return successful.load();
    }

    int failure_count() const {
        return failed.load();
    }

    size_t active_connections() {
        return database.active_connections();
    }

    size_t maximum_connections() const {
        return database.maximum_connections();
    }
};

// ---------------------------------------------------------
// Request execution and result reporting
// ---------------------------------------------------------

void print_result(const RequestResult& result) {
    cout << left
         << setw(12) << result.request_id
         << setw(15) << to_string(result.status)
         << setw(35) << result.message
         << fixed << setprecision(2)
         << result.elapsed_ms << " ms\n";
}

int main() {
    try {
        cout << "ASYNC REQUEST ENGINE\n";
        cout << "====================\n\n";

        const size_t worker_count = 4;
        const size_t connection_count = 2;

        RequestEngine engine(
            worker_count,
            connection_count
        );

        vector<Request> requests = {
            {1, OperationType::DATABASE_READ, 200, "Read tasks"},
            {2, OperationType::DATABASE_WRITE, 300, "Create task"},
            {3, OperationType::DATABASE_READ, 150, "Read users"},
            {4, OperationType::CPU_COMPUTATION, 0, "Compute"},
            {5, OperationType::DATABASE_WRITE, 250, "Update task"},
            {6, OperationType::BLOCKING_IO, 400, "File operation"},
            {7, OperationType::DATABASE_READ, 100, "Read reports"},
            {8, OperationType::DATABASE_READ, 100, "Read metrics"}
        };

        vector<future<RequestResult>> futures;

        auto overall_start = steady_clock::now();

        // Submit all requests before collecting their results.
        for (const auto& request : requests) {
            futures.push_back(engine.submit(request));
        }

        cout << "REQUEST RESULTS\n";
        cout << "---------------\n";

        cout << left
             << setw(12) << "ID"
             << setw(15) << "STATUS"
             << setw(35) << "MESSAGE"
             << "TIME\n";

        for (auto& future : futures) {
            RequestResult result = future.get();
            print_result(result);
        }

        double total_ms = duration<double, milli>(
            steady_clock::now() - overall_start
        ).count();

        cout << "\nSYSTEM METRICS\n";
        cout << "--------------\n";

        cout << "Workers: "
             << worker_count << '\n';

        cout << "Database connections: "
             << connection_count << '\n';

        cout << "Successful requests: "
             << engine.success_count() << '\n';

        cout << "Failed requests: "
             << engine.failure_count() << '\n';

        cout << "Total elapsed time: "
             << fixed << setprecision(2)
             << total_ms << " ms\n";

        cout << "\nBLOCKING AND CONCURRENCY ANALYSIS\n";
        cout << "--------------------------------\n";

        cout << "1. Worker threads execute submitted operations.\n";

        cout << "2. Database leases limit simultaneous database access.\n";

        cout << "3. Blocking work occupies its worker thread.\n";

        cout << "4. A bounded executor prevents unlimited task submission.\n";

        cout << "5. RAII releases database connections after failures.\n";

        cout << "6. Futures propagate completion and execution results.\n";

        cout << "\nVALIDATION TESTS\n";
        cout << "----------------\n";

        bool invalid_request_rejected = false;

        try {
            engine.submit({
                -1,
                OperationType::DATABASE_READ,
                100,
                "Invalid request"
            });

        } catch (const invalid_argument&) {
            invalid_request_rejected = true;
        }

        cout << "Invalid identifier rejected: "
             << boolalpha
             << invalid_request_rejected << '\n';

        bool invalid_duration_rejected = false;

        try {
            engine.submit({
                99,
                OperationType::DATABASE_READ,
                20000,
                "Invalid duration"
            });

        } catch (const invalid_argument&) {
            invalid_duration_rejected = true;
        }

        cout << "Invalid duration rejected: "
             << invalid_duration_rejected << '\n';

        cout << "\nExecutor shutdown is handled automatically.\n";

    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}

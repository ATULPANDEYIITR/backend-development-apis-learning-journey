#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <exception>
#include <functional>
#include <future>
#include <iostream>
#include <memory>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

/*
 * C++17 ASYNCHRONOUS EXECUTION ENGINE
 *
 * Implements:
 * - Thread-based asynchronous execution
 * - Future and promise communication
 * - Bounded worker pool
 * - Task queue
 * - Mutex and condition variable synchronization
 * - Graceful shutdown
 * - Exception propagation
 * - Concurrent repository data processing
 *
 * C++17 does not provide the C++20 coroutine language feature.
 * This implementation uses standard-library concurrency primitives.
 */

using namespace std;
using namespace std::chrono;


// ============================================================
// 1. DOMAIN TYPES
// ============================================================

enum class TaskStatus {
    PENDING,
    RUNNING,
    COMPLETED,
    FAILED
};

struct TaskResult {
    int id;
    TaskStatus status;
    string message;
    double duration_ms;
};


// ============================================================
// 2. THREAD POOL
// ============================================================

class ThreadPool {

private:

    vector<thread> workers;

    queue<function<void()>> tasks;

    mutex queueMutex;

    condition_variable condition;

    bool stopping = false;

    atomic<size_t> submitted{0};
    atomic<size_t> completed{0};

public:

    explicit ThreadPool(size_t threadCount) {

        if (threadCount == 0) {
            throw invalid_argument(
                "Thread count must be positive"
            );
        }

        for (size_t i = 0; i < threadCount; ++i) {

            workers.emplace_back([this]() {

                while (true) {

                    function<void()> task;

                    {
                        unique_lock<mutex> lock(queueMutex);

                        condition.wait(lock, [this]() {
                            return stopping || !tasks.empty();
                        });

                        if (stopping && tasks.empty()) {
                            return;
                        }

                        task = move(tasks.front());
                        tasks.pop();
                    }

                    task();

                    completed.fetch_add(1);
                }
            });
        }
    }

    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;

    template <typename F, typename... Args>
    auto submit(F&& function, Args&&... args)
        -> future<invoke_result_t<F, Args...>> {

        using ReturnType = invoke_result_t<F, Args...>;

        auto packagedTask = make_shared<packaged_task<ReturnType()>>(
            bind(
                forward<F>(function),
                forward<Args>(args)...
            )
        );

        future<ReturnType> result = packagedTask->get_future();

        {
            lock_guard<mutex> lock(queueMutex);

            if (stopping) {
                throw runtime_error("Thread pool is shutting down");
            }

            tasks.emplace([packagedTask]() {
                (*packagedTask)();
            });

            submitted.fetch_add(1);
        }

        condition.notify_one();

        return result;
    }

    void shutdown() {

        {
            lock_guard<mutex> lock(queueMutex);

            if (stopping) {
                return;
            }

            stopping = true;
        }

        condition.notify_all();

        for (auto& worker : workers) {
            if (worker.joinable()) {
                worker.join();
            }
        }

        workers.clear();
    }

    size_t getSubmitted() const {
        return submitted.load();
    }

    size_t getCompleted() const {
        return completed.load();
    }

    ~ThreadPool() {
        shutdown();
    }
};


// ============================================================
// 3. ASYNCHRONOUS TASK
// ============================================================

TaskResult processTask(
    int id,
    int duration,
    bool shouldFail = false
) {

    auto start = steady_clock::now();

    this_thread::sleep_for(milliseconds(duration));

    if (shouldFail) {
        throw runtime_error(
            "Task " + to_string(id) + " failed"
        );
    }

    auto end = steady_clock::now();

    double elapsed = duration<double, milli>(
        end - start
    ).count();

    return {
        id,
        TaskStatus::COMPLETED,
        "Task processed",
        elapsed
    };
}


// ============================================================
// 4. FUTURE AND PROMISE
// ============================================================

void demonstratePromise() {

    cout << "\n1. FUTURE AND PROMISE\n";

    promise<string> promiseObject;

    future<string> futureObject =
        promiseObject.get_future();

    thread worker([&promiseObject]() {

        this_thread::sleep_for(milliseconds(100));

        promiseObject.set_value(
            "Asynchronous result received"
        );
    });

    cout << futureObject.get() << endl;

    worker.join();
}


// ============================================================
// 5. ASYNCHRONOUS THREAD EXECUTION
// ============================================================

void demonstrateAsync() {

    cout << "\n2. STD::ASYNC\n";

    auto task = async(
        launch::async,
        []() {
            this_thread::sleep_for(milliseconds(200));
            return 100;
        }
    );

    cout << "Task result: " << task.get() << endl;
}


// ============================================================
// 6. THREAD POOL PROCESSING
// ============================================================

void demonstrateThreadPool() {

    cout << "\n3. BOUNDED THREAD POOL\n";

    ThreadPool pool(3);

    vector<future<TaskResult>> futures;

    for (int i = 1; i <= 8; ++i) {

        futures.push_back(
            pool.submit(
                processTask,
                i,
                100 + (i % 3) * 50,
                false
            )
        );
    }

    for (auto& result : futures) {

        TaskResult task = result.get();

        cout << "Task " << task.id
             << ": " << task.message
             << ", duration=" << task.duration_ms
             << "ms\n";
    }

    pool.shutdown();

    cout << "Submitted: " << pool.getSubmitted() << endl;
    cout << "Completed: " << pool.getCompleted() << endl;
}


// ============================================================
// 7. EXCEPTION PROPAGATION
// ============================================================

void demonstrateExceptionHandling() {

    cout << "\n4. EXCEPTION PROPAGATION\n";

    ThreadPool pool(2);

    vector<future<TaskResult>> futures;

    futures.push_back(
        pool.submit(processTask, 1, 100, false)
    );

    futures.push_back(
        pool.submit(processTask, 2, 100, true)
    );

    for (auto& futureResult : futures) {

        try {

            TaskResult result = futureResult.get();

            cout << "Success: " << result.id << endl;

        } catch (const exception& error) {

            cout << "Failure: " << error.what() << endl;
        }
    }

    pool.shutdown();
}


// ============================================================
// 8. PARALLEL DATA PROCESSING
// ============================================================

long long calculateSquareSum(
    const vector<int>& values,
    size_t start,
    size_t end
) {

    long long total = 0;

    for (size_t i = start; i < end; ++i) {

        long long value = values[i];

        total += value * value;
    }

    return total;
}


void demonstrateParallelProcessing() {

    cout << "\n5. PARALLEL DATA PROCESSING\n";

    vector<int> values(10000);

    for (size_t i = 0; i < values.size(); ++i) {
        values[i] = static_cast<int>(i + 1);
    }

    const size_t workerCount = 4;

    ThreadPool pool(workerCount);

    vector<future<long long>> futures;

    size_t chunkSize =
        (values.size() + workerCount - 1) / workerCount;

    for (size_t i = 0; i < workerCount; ++i) {

        size_t start = i * chunkSize;

        size_t end = min(
            values.size(),
            start + chunkSize
        );

        if (start >= values.size()) {
            break;
        }

        futures.push_back(
            pool.submit(
                calculateSquareSum,
                cref(values),
                start,
                end
            )
        );
    }

    long long total = 0;

    for (auto& futureResult : futures) {
        total += futureResult.get();
    }

    cout << "Square sum: " << total << endl;

    pool.shutdown();
}


// ============================================================
// 9. SYNCHRONIZED SHARED STATE
// ============================================================

class SafeCounter {

private:

    mutex mutexObject;

    long long value = 0;

public:

    void increment() {

        lock_guard<mutex> lock(mutexObject);

        ++value;
    }

    long long getValue() {

        lock_guard<mutex> lock(mutexObject);

        return value;
    }
};


void demonstrateSynchronization() {

    cout << "\n6. SHARED STATE SYNCHRONIZATION\n";

    SafeCounter counter;

    vector<thread> threads;

    for (int i = 0; i < 5; ++i) {

        threads.emplace_back([&counter]() {

            for (int j = 0; j < 1000; ++j) {
                counter.increment();
            }
        });
    }

    for (auto& worker : threads) {
        worker.join();
    }

    cout << "Counter: " << counter.getValue() << endl;
}


// ============================================================
// 10. CONDITION VARIABLE
// ============================================================

class MessageQueue {

private:

    queue<string> messages;

    mutex mutexObject;

    condition_variable condition;

    bool closed = false;

public:

    void push(string message) {

        {
            lock_guard<mutex> lock(mutexObject);

            if (closed) {
                throw runtime_error("Queue is closed");
            }

            messages.push(move(message));
        }

        condition.notify_one();
    }

    bool pop(string& output) {

        unique_lock<mutex> lock(mutexObject);

        condition.wait(lock, [this]() {
            return closed || !messages.empty();
        });

        if (messages.empty()) {
            return false;
        }

        output = move(messages.front());
        messages.pop();

        return true;
    }

    void close() {

        {
            lock_guard<mutex> lock(mutexObject);
            closed = true;
        }

        condition.notify_all();
    }
};


void demonstrateMessageQueue() {

    cout << "\n7. PRODUCER-CONSUMER QUEUE\n";

    MessageQueue queueObject;

    thread producer([&queueObject]() {

        for (int i = 1; i <= 5; ++i) {

            queueObject.push(
                "Message " + to_string(i)
            );
        }

        queueObject.close();
    });

    thread consumer([&queueObject]() {

        string message;

        while (queueObject.pop(message)) {
            cout << "Consumed: " << message << endl;
        }
    });

    producer.join();
    consumer.join();
}


// ============================================================
// 11. TASK DEPENDENCY EXECUTION
// ============================================================

void demonstrateTaskDependencies() {

    cout << "\n8. TASK DEPENDENCIES\n";

    auto first = async(
        launch::async,
        []() {
            this_thread::sleep_for(milliseconds(100));
            return 10;
        }
    );

    auto second = async(
        launch::async,
        []() {
            this_thread::sleep_for(milliseconds(150));
            return 20;
        }
    );

    auto aggregate = async(
        launch::async,
        [&first, &second]() {

            return first.get() + second.get();
        }
    );

    cout << "Aggregate result: "
         << aggregate.get()
         << endl;
}


// ============================================================
// 12. PERFORMANCE MEASUREMENT
// ============================================================

void demonstratePerformance() {

    cout << "\n9. EXECUTION PERFORMANCE\n";

    auto start = steady_clock::now();

    vector<future<int>> futures;

    for (int i = 0; i < 5; ++i) {

        futures.push_back(
            async(
                launch::async,
                [i]() {

                    this_thread::sleep_for(
                        milliseconds(100)
                    );

                    return i * i;
                }
            )
        );
    }

    int total = 0;

    for (auto& result : futures) {
        total += result.get();
    }

    auto end = steady_clock::now();

    auto elapsed =
        duration_cast<milliseconds>(end - start).count();

    cout << "Total: " << total << endl;
    cout << "Elapsed: " << elapsed << "ms" << endl;
}


// ============================================================
// 13. TESTS
// ============================================================

void runTests() {

    cout << "\n10. VALIDATION TESTS\n";

    ThreadPool pool(2);

    auto first = pool.submit([]() {
        return 10;
    });

    auto second = pool.submit([]() {
        return 20;
    });

    if (first.get() != 10 || second.get() != 20) {
        throw runtime_error("Thread pool test failed");
    }

    pool.shutdown();

    SafeCounter counter;

    vector<thread> workers;

    for (int i = 0; i < 4; ++i) {

        workers.emplace_back([&counter]() {

            for (int j = 0; j < 100; ++j) {
                counter.increment();
            }
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    if (counter.getValue() != 400) {
        throw runtime_error("Counter test failed");
    }

    cout << "All C++ assertions passed" << endl;
}


// ============================================================
// 14. MAIN
// ============================================================

int main() {

    try {

        demonstratePromise();

        demonstrateAsync();

        demonstrateThreadPool();

        demonstrateExceptionHandling();

        demonstrateParallelProcessing();

        demonstrateSynchronization();

        demonstrateMessageQueue();

        demonstrateTaskDependencies();

        demonstratePerformance();

        runTests();

        cout << "\nAll demonstrations completed\n";

        return 0;

    } catch (const exception& error) {

        cerr << "Application failure: "
             << error.what()
             << endl;

        return 1;
    }
}

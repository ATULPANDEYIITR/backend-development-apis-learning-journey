#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Background Task Governance Engine
 *
 * C++17
 *
 * Implements:
 * - Priority task scheduling.
 * - Multiple worker threads.
 * - Task lifecycle management.
 * - Retry policies.
 * - Dependency evaluation.
 * - Idempotency.
 * - Dead-letter processing.
 * - Thread-safe task storage.
 * - Operational reporting.
 */

using namespace std;
using Clock = chrono::steady_clock;
using Milliseconds = chrono::milliseconds;

// ============================================================
// 1. DOMAIN TYPES
// ============================================================

enum class TaskStatus {
    Pending,
    Queued,
    Running,
    RetryWait,
    Completed,
    Failed,
    DeadLetter,
    Cancelled
};

enum class Priority {
    Critical = 1,
    High = 3,
    Normal = 5,
    Low = 8
};

string statusName(TaskStatus status) {
    switch (status) {
        case TaskStatus::Pending: return "PENDING";
        case TaskStatus::Queued: return "QUEUED";
        case TaskStatus::Running: return "RUNNING";
        case TaskStatus::RetryWait: return "RETRY_WAIT";
        case TaskStatus::Completed: return "COMPLETED";
        case TaskStatus::Failed: return "FAILED";
        case TaskStatus::DeadLetter: return "DEAD_LETTER";
        case TaskStatus::Cancelled: return "CANCELLED";
    }

    return "UNKNOWN";
}

class TaskException : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class PermanentTaskException : public TaskException {
public:
    using TaskException::TaskException;
};

bool terminal(TaskStatus status) {
    return status == TaskStatus::Completed ||
           status == TaskStatus::DeadLetter ||
           status == TaskStatus::Cancelled;
}

// ============================================================
// 2. RETRY POLICY
// ============================================================

struct RetryPolicy {
    int maxAttempts = 3;
    int initialDelayMs = 50;
    int maxDelayMs = 1000;
    double multiplier = 2.0;

    void validate() const {
        if (maxAttempts < 1 ||
            initialDelayMs < 0 ||
            maxDelayMs < 0 ||
            multiplier < 1.0) {
            throw TaskException("Invalid retry policy.");
        }
    }

    int delay(int attempt) const {
        double value = initialDelayMs *
            pow(multiplier, max(0, attempt - 1));

        return static_cast<int>(
            min<double>(value, maxDelayMs)
        );
    }
};

// ============================================================
// 3. TASK ENTITY
// ============================================================

struct Task {
    string id;
    string type;
    string payload;
    string idempotencyKey;

    Priority priority = Priority::Normal;
    RetryPolicy retryPolicy;

    TaskStatus status = TaskStatus::Pending;

    int attempts = 0;
    int64_t result = 0;

    string error;
    string workerId;

    set<string> dependencies;

    Clock::time_point scheduledAt = Clock::now();
    Clock::time_point createdAt = Clock::now();

    Task(
        string taskId,
        string taskType,
        string taskPayload,
        Priority taskPriority = Priority::Normal
    )
        : id(move(taskId)),
          type(move(taskType)),
          payload(move(taskPayload)),
          priority(taskPriority) {

        if (id.empty() || type.empty()) {
            throw TaskException("Task ID and type are required.");
        }

        if (type.size() > 100 || payload.size() > 1000000) {
            throw TaskException("Task exceeds permitted size.");
        }
    }

    void transition(TaskStatus next) {
        bool valid = false;

        switch (status) {
            case TaskStatus::Pending:
                valid = next == TaskStatus::Queued ||
                        next == TaskStatus::Cancelled;
                break;

            case TaskStatus::Queued:
                valid = next == TaskStatus::Running ||
                        next == TaskStatus::Cancelled;
                break;

            case TaskStatus::Running:
                valid = next == TaskStatus::Completed ||
                        next == TaskStatus::RetryWait ||
                        next == TaskStatus::Failed ||
                        next == TaskStatus::DeadLetter;
                break;

            case TaskStatus::RetryWait:
                valid = next == TaskStatus::Queued ||
                        next == TaskStatus::Cancelled ||
                        next == TaskStatus::DeadLetter;
                break;

            case TaskStatus::Failed:
                valid = next == TaskStatus::Queued ||
                        next == TaskStatus::DeadLetter;
                break;

            default:
                valid = false;
        }

        if (!valid) {
            throw TaskException(
                "Invalid task state transition: " +
                statusName(status) + " -> " + statusName(next)
            );
        }

        status = next;
    }
};

// ============================================================
// 4. PRIORITY QUEUE
// ============================================================

struct QueueItem {
    int priority;
    uint64_t sequence;
    string taskId;
};

struct QueueComparator {
    bool operator()(
        const QueueItem& a,
        const QueueItem& b
    ) const {
        if (a.priority != b.priority) {
            return a.priority > b.priority;
        }

        return a.sequence > b.sequence;
    }
};

class TaskQueue {
private:
    priority_queue<
        QueueItem,
        vector<QueueItem>,
        QueueComparator
    > queue;

    uint64_t sequence = 0;

    mutable mutex mutex_;
    condition_variable condition_;

public:
    void push(const Task& task) {
        {
            lock_guard<mutex> lock(mutex_);

            queue.push({
                static_cast<int>(task.priority),
                sequence++,
                task.id
            });
        }

        condition_.notify_one();
    }

    optional<string> pop(Milliseconds timeout) {
        unique_lock<mutex> lock(mutex_);

        if (!condition_.wait_for(
            lock,
            timeout,
            [&] { return !queue.empty(); }
        )) {
            return nullopt;
        }

        string result = queue.top().taskId;
        queue.pop();

        return result;
    }

    size_t size() const {
        lock_guard<mutex> lock(mutex_);
        return queue.size();
    }

    void notifyAll() {
        condition_.notify_all();
    }
};

// ============================================================
// 5. TASK STORE
// ============================================================

class TaskStore {
private:
    unordered_map<string, shared_ptr<Task>> tasks;
    unordered_map<string, string> idempotency;

    mutable mutex mutex_;

public:
    shared_ptr<Task> create(shared_ptr<Task> task) {
        lock_guard<mutex> lock(mutex_);

        if (!task->idempotencyKey.empty()) {
            auto existing = idempotency.find(
                task->idempotencyKey
            );

            if (existing != idempotency.end()) {
                return tasks.at(existing->second);
            }
        }

        if (tasks.count(task->id)) {
            throw TaskException("Duplicate task ID.");
        }

        for (const auto& dependency : task->dependencies) {
            if (!tasks.count(dependency)) {
                throw TaskException(
                    "Unknown dependency: " + dependency
                );
            }
        }

        tasks.emplace(task->id, task);

        if (!task->idempotencyKey.empty()) {
            idempotency.emplace(
                task->idempotencyKey,
                task->id
            );
        }

        return task;
    }

    shared_ptr<Task> get(const string& id) {
        lock_guard<mutex> lock(mutex_);

        auto it = tasks.find(id);

        if (it == tasks.end()) {
            throw TaskException("Task not found: " + id);
        }

        return it->second;
    }

    vector<shared_ptr<Task>> all() {
        lock_guard<mutex> lock(mutex_);

        vector<shared_ptr<Task>> result;

        for (auto& entry : tasks) {
            result.push_back(entry.second);
        }

        return result;
    }

    bool dependenciesCompleted(const Task& task) {
        lock_guard<mutex> lock(mutex_);

        for (const auto& dependency : task.dependencies) {
            auto it = tasks.find(dependency);

            if (it == tasks.end() ||
                it->second->status != TaskStatus::Completed) {
                return false;
            }
        }

        return true;
    }
};

// ============================================================
// 6. HANDLER REGISTRY
// ============================================================

using TaskHandler = function<int64_t(const string&)>;

class HandlerRegistry {
private:
    unordered_map<string, TaskHandler> handlers;

public:
    void registerHandler(
        const string& type,
        TaskHandler handler
    ) {
        if (type.empty() || !handler) {
            throw TaskException("Invalid handler.");
        }

        if (handlers.count(type)) {
            throw TaskException("Handler already registered.");
        }

        handlers.emplace(type, move(handler));
    }

    TaskHandler get(const string& type) const {
        auto it = handlers.find(type);

        if (it == handlers.end()) {
            throw TaskException("No handler for: " + type);
        }

        return it->second;
    }
};

// ============================================================
// 7. GOVERNANCE ENGINE
// ============================================================

class BackgroundTaskEngine {
private:
    TaskStore store;
    TaskQueue queue;
    HandlerRegistry registry;

    vector<string> deadLetters;

    vector<thread> workers;
    mutex stateMutex;
    condition_variable stateCondition;

    atomic<bool> stopping{false};
    atomic<int> activeWorkers{0};

    mutex metricsMutex;

    struct Metrics {
        uint64_t submitted = 0;
        uint64_t completed = 0;
        uint64_t failed = 0;
        uint64_t retried = 0;
        uint64_t deadLettered = 0;
    } metrics;

    void record(uint64_t Metrics::*field) {
        lock_guard<mutex> lock(metricsMutex);
        metrics.*field += 1;
    }

    void process(const string& id, const string& workerId) {
        auto task = store.get(id);

        {
            lock_guard<mutex> lock(stateMutex);

            if (task->status != TaskStatus::Queued) {
                return;
            }

            if (!store.dependenciesCompleted(*task)) {
                task->transition(TaskStatus::Pending);
                return;
            }

            task->transition(TaskStatus::Running);
            task->attempts++;
            task->workerId = workerId;
        }

        try {
            TaskHandler handler = registry.get(task->type);

            int64_t result = handler(task->payload);

            {
                lock_guard<mutex> lock(stateMutex);

                if (task->status != TaskStatus::Running) {
                    return;
                }

                task->result = result;
                task->transition(TaskStatus::Completed);
            }

            record(&Metrics::completed);

            cout << workerId << " completed " << task->id
                 << " result=" << result << '\n';

        } catch (const PermanentTaskException& error) {
            moveToDeadLetter(task, error.what());

        } catch (const exception& error) {
            handleRetry(task, error.what());
        }
    }

    void moveToDeadLetter(
        const shared_ptr<Task>& task,
        const string& error
    ) {
        lock_guard<mutex> lock(stateMutex);

        if (task->status != TaskStatus::Running) return;

        task->error = error;
        task->transition(TaskStatus::DeadLetter);

        deadLetters.push_back(task->id);

        record(&Metrics::failed);
        record(&Metrics::deadLettered);
    }

    void handleRetry(
        const shared_ptr<Task>& task,
        const string& error
    ) {
        lock_guard<mutex> lock(stateMutex);

        if (task->status != TaskStatus::Running) return;

        task->error = error;

        if (task->attempts >= task->retryPolicy.maxAttempts) {
            task->transition(TaskStatus::DeadLetter);
            deadLetters.push_back(task->id);

            record(&Metrics::failed);
            record(&Metrics::deadLettered);
            return;
        }

        int delay = task->retryPolicy.delay(task->attempts);

        task->scheduledAt =
            Clock::now() + Milliseconds(delay);

        task->transition(TaskStatus::RetryWait);
        record(&Metrics::retried);
    }

    void workerLoop(string workerId) {
        while (true) {
            if (stopping.load() && queue.size() == 0) {
                break;
            }

            auto id = queue.pop(Milliseconds(50));

            if (!id) {
                continue;
            }

            activeWorkers.fetch_add(1);

            try {
                process(*id, workerId);
            } catch (const exception& error) {
                cerr << "Worker error: " << error.what() << '\n';
            }

            activeWorkers.fetch_sub(1);
            stateCondition.notify_all();
        }
    }

public:
    BackgroundTaskEngine() = default;

    ~BackgroundTaskEngine() {
        shutdown();
    }

    void registerHandler(
        const string& type,
        TaskHandler handler
    ) {
        registry.registerHandler(type, move(handler));
    }

    shared_ptr<Task> submit(shared_ptr<Task> task) {
        if (stopping.load()) {
            throw TaskException("Engine is shutting down.");
        }

        auto stored = store.create(task);

        if (stored != task) {
            return stored;
        }

        record(&Metrics::submitted);

        if (task->scheduledAt <= Clock::now()) {
            enqueue(task);
        }

        return task;
    }

    void enqueue(shared_ptr<Task> task) {
        lock_guard<mutex> lock(stateMutex);

        if (task->status == TaskStatus::Pending ||
            task->status == TaskStatus::RetryWait) {

            if (!store.dependenciesCompleted(*task)) {
                return;
            }

            task->transition(TaskStatus::Queued);
        }

        if (task->status == TaskStatus::Queued) {
            queue.push(*task);
        }
    }

    void scheduleDueTasks() {
        for (auto& task : store.all()) {
            if ((task->status == TaskStatus::Pending ||
                 task->status == TaskStatus::RetryWait) &&
                task->scheduledAt <= Clock::now()) {
                enqueue(task);
            }
        }
    }

    void start(size_t workerCount) {
        if (workerCount == 0 || workerCount > 64) {
            throw TaskException("Invalid worker count.");
        }

        if (!workers.empty()) {
            throw TaskException("Workers already started.");
        }

        stopping.store(false);

        for (size_t i = 0; i < workerCount; ++i) {
            string id = "worker-" + to_string(i + 1);

            workers.emplace_back(
                &BackgroundTaskEngine::workerLoop,
                this,
                id
            );
        }
    }

    void cancel(const string& id) {
        lock_guard<mutex> lock(stateMutex);

        auto task = store.get(id);

        if (task->status != TaskStatus::Pending &&
            task->status != TaskStatus::Queued &&
            task->status != TaskStatus::RetryWait) {
            throw TaskException("Task cannot be cancelled.");
        }

        task->transition(TaskStatus::Cancelled);
    }

    void retryDeadLetter(const string& id) {
        lock_guard<mutex> lock(stateMutex);

        auto task = store.get(id);

        if (task->status != TaskStatus::DeadLetter) {
            throw TaskException("Task is not dead-lettered.");
        }

        if (task->attempts >= task->retryPolicy.maxAttempts) {
            throw TaskException("Retry limit exhausted.");
        }

        task->transition(TaskStatus::Queued);
        task->error.clear();

        auto it = find(deadLetters.begin(), deadLetters.end(), id);

        if (it != deadLetters.end()) {
            deadLetters.erase(it);
        }

        queue.push(*task);
    }

    void shutdown() {
        if (workers.empty()) return;

        stopping.store(true);
        queue.notifyAll();

        for (auto& worker : workers) {
            if (worker.joinable()) {
                worker.join();
            }
        }

        workers.clear();
    }

    void report() {
        cout << "\nTASK REPORT\n";

        map<string, int> counts;

        for (const auto& task : store.all()) {
            counts[statusName(task->status)]++;

            cout << task->id << " | "
                 << task->type << " | "
                 << statusName(task->status)
                 << " | attempts=" << task->attempts
                 << " | worker=" << task->workerId
                 << '\n';
        }

        cout << "\nSTATE COUNTS\n";

        for (const auto& entry : counts) {
            cout << entry.first << ": " << entry.second << '\n';
        }

        lock_guard<mutex> lock(metricsMutex);

        cout << "\nMETRICS\n"
             << "Submitted: " << metrics.submitted << '\n'
             << "Completed: " << metrics.completed << '\n'
             << "Failed: " << metrics.failed << '\n'
             << "Retried: " << metrics.retried << '\n'
             << "Dead-lettered: " << metrics.deadLettered << '\n';
    }

    TaskStore& getStore() {
        return store;
    }
};

// ============================================================
// 8. TASK HANDLERS
// ============================================================

int64_t reportHandler(const string& payload) {
    if (payload.empty()) {
        throw PermanentTaskException("Empty report payload.");
    }

    this_thread::sleep_for(Milliseconds(80));

    return static_cast<int64_t>(payload.size() * 100);
}

int64_t notificationHandler(const string& payload) {
    if (payload.find('@') == string::npos) {
        throw PermanentTaskException("Invalid email address.");
    }

    this_thread::sleep_for(Milliseconds(40));

    return 1;
}

int64_t unreliableHandler(const string& payload) {
    static atomic<int> attempts{0};

    if (attempts.fetch_add(1) == 0) {
        throw TaskException("Temporary service unavailable.");
    }

    return 200;
}

// ============================================================
// 9. MAIN EXECUTION
// ============================================================

int main() {
    try {
        BackgroundTaskEngine engine;

        engine.registerHandler("report", reportHandler);
        engine.registerHandler("notification", notificationHandler);
        engine.registerHandler("unreliable", unreliableHandler);

        auto report = make_shared<Task>(
            "TASK-001",
            "report",
            "Monthly Operations",
            Priority::High
        );

        report->idempotencyKey = "monthly-report-2026-11";

        engine.submit(report);

        auto notification = make_shared<Task>(
            "TASK-002",
            "notification",
            "operations@example.com",
            Priority::Normal
        );

        notification->dependencies.insert(report->id);

        engine.submit(notification);

        auto unreliable = make_shared<Task>(
            "TASK-003",
            "unreliable",
            "external-service",
            Priority::Low
        );

        unreliable->retryPolicy = {
            3,
            50,
            500,
            2.0
        };

        engine.submit(unreliable);

        // Duplicate idempotency keys must not create new work.
        auto duplicate = make_shared<Task>(
            "TASK-004",
            "report",
            "Duplicate",
            Priority::Normal
        );

        duplicate->idempotencyKey = "monthly-report-2026-11";

        auto existing = engine.submit(duplicate);

        if (existing->id != report->id) {
            throw TaskException("Idempotency assertion failed.");
        }

        engine.start(3);

        auto deadline = Clock::now() + chrono::seconds(5);

        while (Clock::now() < deadline) {
            engine.scheduleDueTasks();

            bool finished =
                report->status == TaskStatus::Completed &&
                notification->status == TaskStatus::Completed &&
                unreliable->status == TaskStatus::Completed;

            if (finished) break;

            this_thread::sleep_for(Milliseconds(20));
        }

        engine.shutdown();

        if (report->status != TaskStatus::Completed ||
            notification->status != TaskStatus::Completed ||
            unreliable->status != TaskStatus::Completed ||
            unreliable->attempts != 2) {
            throw TaskException("Execution validation failed.");
        }

        engine.report();

        cout << "\nAll C++17 assertions passed.\n";

        return 0;

    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}

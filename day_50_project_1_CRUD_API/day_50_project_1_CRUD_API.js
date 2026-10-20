"use strict";

const API_BASE = process.env.API_BASE || "http://127.0.0.1:8000";

class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });

    const text = await response.text();
    let body = null;

    try {
        body = text ? JSON.parse(text) : null;
    } catch {
        body = { detail: text };
    }

    if (!response.ok) {
        const message =
            typeof body?.detail === "string"
                ? body.detail
                : body?.detail?.message || `HTTP ${response.status}`;

        throw new ApiError(response.status, message);
    }

    return body;
}

function assertString(value, field, maxLength = 200) {
    if (typeof value !== "string" || value.trim().length === 0) {
        throw new TypeError(`${field} must be a non-empty string`);
    }

    if (value.length > maxLength) {
        throw new RangeError(`${field} exceeds ${maxLength} characters`);
    }

    return value.trim();
}

function validatePullRequest(input) {
    const title = assertString(input.title, "title");
    const sourceBranch = assertString(input.source_branch, "source_branch", 100);
    const targetBranch = assertString(input.target_branch, "target_branch", 100);

    if (sourceBranch === targetBranch) {
        throw new Error("source_branch and target_branch must differ");
    }

    if (!Number.isInteger(input.commits) || input.commits < 1) {
        throw new Error("commits must be a positive integer");
    }

    const strategies = new Set(["merge", "squash", "rebase"]);
    if (!strategies.has(input.merge_strategy)) {
        throw new Error("unsupported merge strategy");
    }

    return {
        title,
        source_branch: sourceBranch,
        target_branch: targetBranch,
        merge_strategy: input.merge_strategy,
        commits: input.commits,
    };
}

class RepositoryGovernanceClient {
    constructor(baseUrl = API_BASE) {
        this.baseUrl = baseUrl.replace(/\/$/, "");
    }

    async createRepository(name, defaultBranch = "main") {
        const repository = assertString(name, "name", 100);

        if (!/^[A-Za-z0-9_.-]+$/.test(repository)) {
            throw new Error("repository name contains invalid characters");
        }

        return request("/repositories", {
            method: "POST",
            body: JSON.stringify({
                name: repository,
                default_branch: assertString(defaultBranch, "default_branch", 100),
            }),
        });
    }

    async createPullRequest(repositoryId, input) {
        if (!Number.isInteger(repositoryId) || repositoryId < 1) {
            throw new TypeError("repositoryId must be a positive integer");
        }

        return request(`/repositories/${repositoryId}/pull-requests`, {
            method: "POST",
            body: JSON.stringify(validatePullRequest(input)),
        });
    }

    async configureProtection(repositoryId, policy) {
        if (!Number.isInteger(repositoryId) || repositoryId < 1) {
            throw new TypeError("repositoryId must be a positive integer");
        }

        const requiredReviews = policy.required_reviews ?? 1;

        if (!Number.isInteger(requiredReviews) || requiredReviews < 0 || requiredReviews > 20) {
            throw new RangeError("required_reviews must be between 0 and 20");
        }

        return request(`/repositories/${repositoryId}/protection`, {
            method: "PUT",
            body: JSON.stringify({
                required_reviews: requiredReviews,
                require_status_checks: Boolean(policy.require_status_checks),
                require_conversation_resolution:
                    Boolean(policy.require_conversation_resolution),
                restrict_direct_push: Boolean(policy.restrict_direct_push),
                restrict_force_push: Boolean(policy.restrict_force_push),
                restrict_deletion: Boolean(policy.restrict_deletion),
                require_linear_history: Boolean(policy.require_linear_history),
            }),
        });
    }

    async getMergeEligibility(pullRequestId) {
        if (!Number.isInteger(pullRequestId) || pullRequestId < 1) {
            throw new TypeError("pullRequestId must be a positive integer");
        }

        return request(`/pull-requests/${pullRequestId}/merge-eligibility`);
    }

    async mergePullRequest(pullRequestId) {
        if (!Number.isInteger(pullRequestId) || pullRequestId < 1) {
            throw new TypeError("pullRequestId must be a positive integer");
        }

        return request(`/pull-requests/${pullRequestId}/merge`, {
            method: "POST",
        });
    }
}

class GovernanceEventBus extends EventTarget {
    emit(type, detail) {
        this.dispatchEvent(new CustomEvent(type, { detail }));
    }
}

async function runInteractiveWorkflow() {
    const client = new RepositoryGovernanceClient();
    const events = new GovernanceEventBus();

    events.addEventListener("repository-created", event => {
        console.log(`Repository created: ${event.detail.name}`);
    });

    events.addEventListener("merge-blocked", event => {
        console.warn("Merge blocked:", event.detail.reasons);
    });

    try {
        const repository = await client.createRepository(
            "payments-service",
            "main"
        );

        events.emit("repository-created", repository);

        await client.configureProtection(repository.id, {
            required_reviews: 2,
            require_status_checks: true,
            require_conversation_resolution: true,
            restrict_direct_push: true,
            restrict_force_push: true,
            restrict_deletion: true,
            require_linear_history: true,
        });

        const pullRequest = await client.createPullRequest(repository.id, {
            title: "Add transaction idempotency",
            source_branch: "feature/idempotency",
            target_branch: "main",
            merge_strategy: "squash",
            commits: 3,
        });

        const eligibility = await client.getMergeEligibility(pullRequest.id);

        if (!eligibility.eligible) {
            events.emit("merge-blocked", eligibility);
            console.log("Merge conditions:", eligibility.reasons);
            return;
        }

        const merged = await client.mergePullRequest(pullRequest.id);
        console.log("Merged:", merged);
    } catch (error) {
        if (error instanceof ApiError) {
            console.error(`API error ${error.status}: ${error.message}`);
        } else {
            console.error("Workflow error:", error.message);
        }
    }
}

if (require.main === module) {
    runInteractiveWorkflow();
}

module.exports = {
    ApiError,
    GovernanceEventBus,
    RepositoryGovernanceClient,
    validatePullRequest,
};

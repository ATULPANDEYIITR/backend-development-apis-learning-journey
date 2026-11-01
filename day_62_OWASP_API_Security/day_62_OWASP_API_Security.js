"use strict";

/*
 * Secure API change governance model.
 *
 * Pull Requests provide the change workflow.
 * Code reviews evaluate the proposed implementation.
 * Approvals record review decisions.
 * Branch protection determines whether repository policy permits merging.
 *
 * The model also evaluates OWASP API security findings:
 * - Broken authorization
 * - Excessive data exposure
 * - Injection
 * - SSRF
 * - Security misconfiguration
 */

const crypto = require("node:crypto");
const EventEmitter = require("node:events");

const PR_STATE = Object.freeze({
  DRAFT: "draft",
  OPEN: "open",
  CLOSED: "closed",
  MERGED: "merged",
});

const REVIEW_STATE = Object.freeze({
  COMMENTED: "commented",
  APPROVED: "approved",
  CHANGES_REQUESTED: "changes_requested",
  DISMISSED: "dismissed",
});

const CHECK_STATE = Object.freeze({
  PENDING: "pending",
  PASSED: "passed",
  FAILED: "failed",
});

const SEVERITY = Object.freeze({
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
});

const SECURITY_CATEGORIES = new Set([
  "broken_authorization",
  "excessive_data_exposure",
  "injection",
  "ssrf",
  "security_misconfiguration",
]);

class DomainError extends Error {}

class ValidationError extends DomainError {}

class MergeBlockedError extends DomainError {
  constructor(reasons) {
    super(`Merge blocked:\n- ${reasons.join("\n- ")}`);
    this.reasons = reasons;
  }
}

function assertNonEmpty(value, field) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new ValidationError(`${field} must be non-empty.`);
  }
}

function createSha(parts) {
  return crypto
    .createHash("sha256")
    .update(parts.join("|"))
    .digest("hex")
    .slice(0, 12);
}

class RepositoryEventBus extends EventEmitter {
  emitSecurityFinding(pr, finding) {
    this.emit("security.finding.created", {
      pullRequest: pr.number,
      finding,
    });
  }

  emitReview(pr, review) {
    this.emit("review.submitted", {
      pullRequest: pr.number,
      review,
    });
  }

  emitMerge(pr) {
    this.emit("pull_request.merged", {
      pullRequest: pr.number,
      mergeCommit: pr.mergeCommit,
    });
  }
}

class SecurityFinding {
  constructor(category, severity, endpoint, description) {
    if (!SECURITY_CATEGORIES.has(category)) {
      throw new ValidationError(`Unsupported security category: ${category}`);
    }

    if (!Object.values(SEVERITY).includes(severity)) {
      throw new ValidationError("Invalid severity.");
    }

    assertNonEmpty(endpoint, "endpoint");
    assertNonEmpty(description, "description");

    this.category = category;
    this.severity = severity;
    this.endpoint = endpoint;
    this.description = description;
  }

  isBlocking() {
    return this.severity >= SEVERITY.HIGH;
  }
}

class ReviewComment {
  constructor(reviewer, filePath, line, body) {
    assertNonEmpty(reviewer, "reviewer");
    assertNonEmpty(filePath, "filePath");

    if (!Number.isInteger(line) || line < 1) {
      throw new ValidationError("line must be a positive integer.");
    }

    assertNonEmpty(body, "body");

    this.reviewer = reviewer;
    this.filePath = filePath;
    this.line = line;
    this.body = body;
    this.resolved = false;
  }
}

class Review {
  constructor(reviewer, state, commitSha, comments = []) {
    assertNonEmpty(reviewer, "reviewer");

    if (!Object.values(REVIEW_STATE).includes(state)) {
      throw new ValidationError("Invalid review state.");
    }

    this.reviewer = reviewer;
    this.state = state;
    this.commitSha = commitSha;
    this.comments = comments;
  }
}

class PullRequest {
  constructor(number, author, title, source, target, baseSha, headSha, draft) {
    assertNonEmpty(title, "title");
    assertNonEmpty(source, "source");
    assertNonEmpty(target, "target");

    this.number = number;
    this.author = author;
    this.title = title;
    this.sourceBranch = source;
    this.targetBranch = target;
    this.baseSha = baseSha;
    this.headSha = headSha;
    this.state = draft ? PR_STATE.DRAFT : PR_STATE.OPEN;
    this.draft = draft;
    this.commits = [];
    this.reviews = [];
    this.comments = [];
    this.checks = new Map();
    this.findings = [];
    this.mergeCommit = null;
  }

  addCommit(author, message, files) {
    if (![PR_STATE.OPEN, PR_STATE.DRAFT].includes(this.state)) {
      throw new DomainError("Commits cannot be added to this Pull Request.");
    }

    if (!Array.isArray(files) || files.length === 0) {
      throw new ValidationError("A commit must modify at least one file.");
    }

    const sha = createSha([
      author,
      message,
      files.join(","),
      this.headSha,
    ]);

    this.commits.push({
      sha,
      author,
      message,
      files: [...files],
    });

    this.headSha = sha;

    // Review approvals apply to a reviewed commit. A new commit makes
    // previous approvals stale rather than silently preserving them.
    for (const review of this.reviews) {
      if (review.state === REVIEW_STATE.APPROVED) {
        review.state = REVIEW_STATE.DISMISSED;
      }
    }

    return sha;
  }

  addCheck(name, state, details) {
    if (!Object.values(CHECK_STATE).includes(state)) {
      throw new ValidationError("Invalid check state.");
    }

    this.checks.set(name, {
      name,
      state,
      details,
    });
  }

  addFinding(finding) {
    this.findings.push(finding);
  }

  addReview(review) {
    if (this.state !== PR_STATE.OPEN) {
      throw new DomainError("Reviews require an open Pull Request.");
    }

    if (review.reviewer === this.author) {
      throw new DomainError("Self-approval is not allowed.");
    }

    this.reviews.push(review);
    this.comments.push(...review.comments);
  }

  resolveComment(reviewer, filePath, line) {
    const comment = this.comments.find(
      (item) =>
        item.reviewer === reviewer &&
        item.filePath === filePath &&
        item.line === line
    );

    if (!comment) {
      throw new DomainError("Review conversation was not found.");
    }

    comment.resolved = true;
  }
}

class BranchProtectionPolicy {
  constructor() {
    this.requiredApprovals = 2;
    this.requiredChecks = new Set([
      "unit-tests",
      "api-security-scan",
      "authorization-tests",
    ]);
    this.requireConversationResolution = true;
    this.requireCodeOwnerReview = true;
    this.requireLinearHistory = true;
    this.allowForcePush = false;
    this.allowBranchDeletion = false;
    this.administratorBypass = false;
  }
}

class GovernanceEngine {
  constructor(policy, codeOwners) {
    this.policy = policy;
    this.codeOwners = codeOwners;
  }

  evaluate(pr, targetBranch) {
    const reasons = [];

    if (pr.state !== PR_STATE.OPEN) {
      reasons.push(`Pull Request state is ${pr.state}.`);
    }

    if (pr.draft) {
      reasons.push("Draft Pull Requests cannot be merged.");
    }

    if (targetBranch.protected) {
      if (pr.baseSha !== targetBranch.headSha) {
        reasons.push("Pull Request base branch is stale.");
      }

      for (const requiredCheck of this.policy.requiredChecks) {
        const check = pr.checks.get(requiredCheck);
        if (!check || check.state !== CHECK_STATE.PASSED) {
          reasons.push(`Required check is not passing: ${requiredCheck}`);
        }
      }

      if (this.policy.requireConversationResolution) {
        const unresolved = pr.comments.filter(
          (comment) => !comment.resolved
        );

        if (unresolved.length > 0) {
          reasons.push(
            `${unresolved.length} unresolved review conversation(s).`
          );
        }
      }

      const blockingFindings = pr.findings.filter((finding) =>
        finding.isBlocking()
      );

      for (const finding of blockingFindings) {
        reasons.push(
          `${finding.category} ${this.severityName(
            finding.severity
          )} at ${finding.endpoint}`
        );
      }

      const approvals = this.latestEligibleApprovals(pr);

      if (approvals.size < this.policy.requiredApprovals) {
        reasons.push(
          `${approvals.size} current approval(s); ` +
            `${this.policy.requiredApprovals} required.`
        );
      }

      if (
        this.policy.requireCodeOwnerReview &&
        !this.hasCodeOwnerApproval(pr, approvals)
      ) {
        reasons.push("Required API security code-owner approval is missing.");
      }
    }

    return {
      eligible: reasons.length === 0,
      reasons,
    };
  }

  latestEligibleApprovals(pr) {
    const latest = new Map();

    for (const review of pr.reviews) {
      if (review.reviewer === pr.author) {
        continue;
      }

      if (review.state === REVIEW_STATE.DISMISSED) {
        latest.delete(review.reviewer);
        continue;
      }

      latest.set(review.reviewer, review);
    }

    const approvals = new Set();

    for (const [reviewer, review] of latest.entries()) {
      if (
        review.state === REVIEW_STATE.APPROVED &&
        review.commitSha === pr.headSha
      ) {
        approvals.add(reviewer);
      }
    }

    return approvals;
  }

  hasCodeOwnerApproval(pr, approvals) {
    const touchedFiles = new Set(
      pr.commits.flatMap((commit) => commit.files)
    );

    const requiredOwners = new Set();

    for (const [prefix, owners] of Object.entries(this.codeOwners)) {
      for (const file of touchedFiles) {
        if (file.startsWith(prefix)) {
          for (const owner of owners) {
            requiredOwners.add(owner);
          }
        }
      }
    }

    return [...requiredOwners].some((owner) => approvals.has(owner));
  }

  severityName(value) {
    return Object.entries(SEVERITY)
      .find(([, numeric]) => numeric === value)?.[0]
      ?.toLowerCase() ?? "unknown";
  }
}

class Repository {
  constructor(name) {
    assertNonEmpty(name, "name");

    this.name = name;
    this.branches = new Map();
    this.pullRequests = new Map();
    this.nextPullRequestNumber = 1;
    this.events = new RepositoryEventBus();
    this.policy = new BranchProtectionPolicy();
    this.codeOwners = {
      "api/": new Set(["security-lead"]),
      "auth/": new Set(["security-lead"]),
    };
    this.governance = new GovernanceEngine(
      this.policy,
      this.codeOwners
    );
  }

  addBranch(name, headSha, protectedBranch = false) {
    if (this.branches.has(name)) {
      throw new ValidationError(`Branch already exists: ${name}`);
    }

    this.branches.set(name, {
      name,
      headSha,
      protected: protectedBranch,
    });
  }

  openPullRequest(author, title, source, target, draft = false) {
    const sourceBranch = this.branches.get(source);
    const targetBranch = this.branches.get(target);

    if (!sourceBranch || !targetBranch) {
      throw new ValidationError("Both branches must exist.");
    }

    if (source === target) {
      throw new ValidationError("Source and target must differ.");
    }

    const pr = new PullRequest(
      this.nextPullRequestNumber++,
      author,
      title,
      source,
      target,
      targetBranch.headSha,
      sourceBranch.headSha,
      draft
    );

    this.pullRequests.set(pr.number, pr);
    return pr;
  }

  merge(pr) {
    const target = this.branches.get(pr.targetBranch);

    if (!target) {
      throw new ValidationError("Target branch does not exist.");
    }

    const result = this.governance.evaluate(pr, target);

    if (!result.eligible) {
      throw new MergeBlockedError(result.reasons);
    }

    const mergeSha = createSha([
      this.name,
      String(pr.number),
      pr.headSha,
      target.headSha,
    ]);

    target.headSha = mergeSha;
    pr.mergeCommit = mergeSha;
    pr.state = PR_STATE.MERGED;

    this.events.emitMerge(pr);

    return mergeSha;
  }
}

async function runSecurityPipeline(repository, pr) {
  await Promise.resolve();

  const securityScan = pr.findings.every(
    (finding) => !finding.isBlocking()
  );

  pr.addCheck(
    "api-security-scan",
    securityScan ? CHECK_STATE.PASSED : CHECK_STATE.FAILED,
    securityScan
      ? "No high or critical API security findings."
      : "Blocking security findings detected."
  );

  pr.addCheck(
    "unit-tests",
    CHECK_STATE.PASSED,
    "624 unit tests passed."
  );

  pr.addCheck(
    "authorization-tests",
    CHECK_STATE.PASSED,
    "Object-level authorization tests passed."
  );

  return securityScan;
}

async function main() {
  const repository = new Repository("payments-api");

  repository.events.on("review.submitted", (event) => {
    console.log(
      `Review event: PR #${event.pullRequest}, ` +
        `${event.review.reviewer}, ${event.review.state}`
    );
  });

  repository.events.on("security.finding.created", (event) => {
    console.log(
      `Security finding event: PR #${event.pullRequest}, ` +
        `${event.finding.category}`
    );
  });

  repository.events.on("pull_request.merged", (event) => {
    console.log(
      `Merge event: PR #${event.pullRequest}, ` +
        `commit ${event.mergeCommit}`
    );
  });

  repository.addBranch("main", "main-001", true);
  repository.addBranch(
    "feature/api-authorization",
    "feature-001",
    false
  );

  const pr = repository.openPullRequest(
    "developer",
    "Harden API authorization and outbound requests",
    "feature/api-authorization",
    "main"
  );

  pr.addCommit(
    "developer",
    "Enforce tenant ownership and outbound URL validation",
    [
      "api/orders.js",
      "api/http-client.js",
      "auth/authorization.js",
    ]
  );

  const finding = new SecurityFinding(
    "broken_authorization",
    SEVERITY.LOW,
    "GET /api/orders/:id",
    "Object ownership is checked before serialization."
  );

  pr.addFinding(finding);
  repository.events.emitSecurityFinding(pr, finding);

  await runSecurityPipeline(repository, pr);

  const reviewOne = new Review(
    "backend-reviewer",
    REVIEW_STATE.APPROVED,
    pr.headSha,
    [
      new ReviewComment(
        "backend-reviewer",
        "api/orders.js",
        42,
        "Confirm the tenant identifier comes from the authenticated principal."
      ),
    ]
  );

  const reviewTwo = new Review(
    "security-lead",
    REVIEW_STATE.APPROVED,
    pr.headSha
  );

  pr.addReview(reviewOne);
  repository.events.emitReview(pr, reviewOne);

  pr.addReview(reviewTwo);
  repository.events.emitReview(pr, reviewTwo);

  try {
    repository.merge(pr);
  } catch (error) {
    console.log("\nExpected governance block:");
    console.log(error.message);

    pr.resolveComment(
      "backend-reviewer",
      "api/orders.js",
      42
    );
  }

  const mergeSha = repository.merge(pr);

  console.log("\nMerged:", {
    pullRequest: pr.number,
    state: pr.state,
    mergeSha,
  });

  repository.addBranch(
    "feature/ssrf-hardening",
    "feature-002",
    false
  );

  const blockedPr = repository.openPullRequest(
    "developer",
    "Harden outbound webhook validation",
    "feature/ssrf-hardening",
    "main"
  );

  blockedPr.addCommit(
    "developer",
    "Reject private network targets",
    ["api/webhooks.js"]
  );

  const blockingFinding = new SecurityFinding(
    "ssrf",
    SEVERITY.HIGH,
    "POST /api/webhooks/test",
    "Untrusted URLs can reach internal network destinations."
  );

  blockedPr.addFinding(blockingFinding);
  repository.events.emitSecurityFinding(
    blockedPr,
    blockingFinding
  );

  await runSecurityPipeline(repository, blockedPr);

  const blockedReview = new Review(
    "security-lead",
    REVIEW_STATE.APPROVED,
    blockedPr.headSha
  );

  blockedPr.addReview(blockedReview);

  try {
    repository.merge(blockedPr);
  } catch (error) {
    console.log("\nExpected security block:");
    console.log(error.message);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

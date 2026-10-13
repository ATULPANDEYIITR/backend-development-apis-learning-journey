'use strict';

/*
 * SQLAlchemy is a Python ORM, so JavaScript cannot directly execute these
 * declarative models. This complementary implementation models the same
 * relational concepts using JavaScript classes and object references.
 *
 * The emphasis is on understanding what an ORM model represents:
 * entities, primary keys, foreign-key relationships, collections, and
 * business-state validation.
 */

class Entity {
    constructor(id) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new Error('Primary key must be a positive integer');
        }
        this.id = id;
    }
}


class User extends Entity {
    constructor(id, username, email) {
        super(id);

        if (!username.trim()) {
            throw new Error('Username cannot be empty');
        }

        if (!email.includes('@')) {
            throw new Error('Email must contain @');
        }

        this.username = username;
        this.email = email;
        this.reviews = [];
        this.assignedPullRequests = [];
    }
}


class Repository extends Entity {
    constructor(id, name) {
        super(id);

        if (!name.trim()) {
            throw new Error('Repository name cannot be empty');
        }

        this.name = name;
        this.branches = [];
        this.pullRequests = [];
    }

    addBranch(branch) {
        if (branch.repositoryId !== this.id) {
            throw new Error('Branch belongs to a different repository');
        }

        this.branches.push(branch);
    }

    addPullRequest(pullRequest) {
        if (pullRequest.repositoryId !== this.id) {
            throw new Error('Pull Request belongs to a different repository');
        }

        this.pullRequests.push(pullRequest);
    }
}


class Branch {
    constructor(id, repositoryId, name) {
        if (!Number.isInteger(id) || !Number.isInteger(repositoryId)) {
            throw new Error('Branch identifiers must be integers');
        }

        this.id = id;
        this.repositoryId = repositoryId;
        this.name = name;
        this.protection = null;
    }

    protect(policy) {
        this.protection = policy;
    }
}


class PullRequest {
    constructor(
        id,
        repositoryId,
        authorId,
        title,
        sourceBranch,
        targetBranch
    ) {
        if (sourceBranch === targetBranch) {
            throw new Error('Source and target branches must differ');
        }

        this.id = id;
        this.repositoryId = repositoryId;
        this.authorId = authorId;
        this.title = title;
        this.sourceBranch = sourceBranch;
        this.targetBranch = targetBranch;
        this.state = 'open';

        this.commitIds = [];
        this.reviewerIds = [];
        this.reviews = [];
        this.statusChecks = [];
    }

    assignReviewer(userId) {
        if (userId === this.authorId) {
            throw new Error('A Pull Request author cannot approve their own change');
        }

        if (!this.reviewerIds.includes(userId)) {
            this.reviewerIds.push(userId);
        }
    }

    addCommit(commit) {
        if (commit.pullRequestId !== this.id) {
            throw new Error('Commit does not belong to this Pull Request');
        }

        this.commitIds.push(commit.id);
    }

    addReview(review) {
        if (review.pullRequestId !== this.id) {
            throw new Error('Review does not belong to this Pull Request');
        }

        this.reviews.push(review);
    }

    addStatusCheck(check) {
        this.statusChecks.push(check);
    }
}


class Commit extends Entity {
    constructor(id, pullRequestId, sha, message) {
        super(id);

        if (!/^[a-f0-9]{40}$/i.test(sha)) {
            throw new Error('Commit SHA must contain 40 hexadecimal characters');
        }

        this.pullRequestId = pullRequestId;
        this.sha = sha;
        this.message = message;
    }
}


class Review extends Entity {
    constructor(id, pullRequestId, reviewerId, state, body = '') {
        super(id);

        const validStates = new Set([
            'pending',
            'commented',
            'approved',
            'changes_requested'
        ]);

        if (!validStates.has(state)) {
            throw new Error(`Invalid review state: ${state}`);
        }

        this.pullRequestId = pullRequestId;
        this.reviewerId = reviewerId;
        this.state = state;
        this.body = body;
    }
}


class StatusCheck {
    constructor(name, passed) {
        this.name = name;
        this.passed = Boolean(passed);
    }
}


class BranchProtection {
    constructor({
        requiredReviews = 1,
        requiredStatusChecks = [],
        allowForcePush = false,
        allowDeletion = false
    } = {}) {
        if (requiredReviews < 0) {
            throw new Error('Required review count cannot be negative');
        }

        this.requiredReviews = requiredReviews;
        this.requiredStatusChecks = new Set(requiredStatusChecks);
        this.allowForcePush = allowForcePush;
        this.allowDeletion = allowDeletion;
    }
}


class MergePolicy {
    constructor(repository, users) {
        this.repository = repository;
        this.users = new Map(users.map(user => [user.id, user]));
    }

    evaluate(pullRequest) {
        const target = this.repository.branches.find(
            branch => branch.name === pullRequest.targetBranch
        );

        if (!target) {
            return {
                eligible: false,
                reasons: ['Target branch does not exist']
            };
        }

        const policy = target.protection;

        if (!policy) {
            return {
                eligible: false,
                reasons: ['Target branch has no explicit protection policy']
            };
        }

        const reasons = [];

        const approvalsByReviewer = new Set(
            pullRequest.reviews
                .filter(review => review.state === 'approved')
                .map(review => review.reviewerId)
        );

        const validApprovals = [...approvalsByReviewer].filter(
            reviewerId =>
                reviewerId !== pullRequest.authorId &&
                pullRequest.reviewerIds.includes(reviewerId)
        );

        if (validApprovals.length < policy.requiredReviews) {
            reasons.push(
                `Requires ${policy.requiredReviews} valid approval(s); ` +
                `found ${validApprovals.length}`
            );
        }

        for (const requiredCheck of policy.requiredStatusChecks) {
            const result = pullRequest.statusChecks.find(
                check => check.name === requiredCheck
            );

            if (!result || !result.passed) {
                reasons.push(`Required status check failed: ${requiredCheck}`);
            }
        }

        const hasRequestedChanges = pullRequest.reviews.some(
            review => review.state === 'changes_requested'
        );

        if (hasRequestedChanges) {
            reasons.push('At least one reviewer requested changes');
        }

        return {
            eligible: reasons.length === 0,
            reasons
        };
    }
}


function runDemo() {
    const alice = new User(1, 'alice', 'alice@example.com');
    const bob = new User(2, 'bob', 'bob@example.com');
    const carol = new User(3, 'carol', 'carol@example.com');

    const repository = new Repository(1, 'payment-service');

    const main = new Branch(1, repository.id, 'main');
    const feature = new Branch(
        2,
        repository.id,
        'feature/payment-validation'
    );

    main.protect(
        new BranchProtection({
            requiredReviews: 2,
            requiredStatusChecks: ['unit-tests', 'security-scan'],
            allowForcePush: false,
            allowDeletion: false
        })
    );

    repository.addBranch(main);
    repository.addBranch(feature);

    const pullRequest = new PullRequest(
        100,
        repository.id,
        alice.id,
        'Add payment validation',
        feature.name,
        main.name
    );

    repository.addPullRequest(pullRequest);

    pullRequest.assignReviewer(bob.id);
    pullRequest.assignReviewer(carol.id);

    const commit = new Commit(
        500,
        pullRequest.id,
        '0123456789abcdef0123456789abcdef01234567',
        'Add payment validation'
    );

    pullRequest.addCommit(commit);

    const bobReview = new Review(
        900,
        pullRequest.id,
        bob.id,
        'approved',
        'Validation logic is correct.'
    );

    const carolReview = new Review(
        901,
        pullRequest.id,
        carol.id,
        'approved',
        'Security checks are covered.'
    );

    pullRequest.addReview(bobReview);
    pullRequest.addReview(carolReview);

    pullRequest.addStatusCheck(new StatusCheck('unit-tests', true));
    pullRequest.addStatusCheck(new StatusCheck('security-scan', true));

    const policy = new MergePolicy(repository, [
        alice,
        bob,
        carol
    ]);

    const decision = policy.evaluate(pullRequest);

    console.log({
        repository: repository.name,
        pullRequest: pullRequest.title,
        source: pullRequest.sourceBranch,
        target: pullRequest.targetBranch,
        approvals: pullRequest.reviews.filter(
            review => review.state === 'approved'
        ).length,
        mergeEligible: decision.eligible,
        reasons: decision.reasons
    });

    // A failed required status check immediately changes merge eligibility.
    pullRequest.statusChecks[1].passed = false;

    const blockedDecision = policy.evaluate(pullRequest);

    console.log({
        afterSecurityFailure: blockedDecision
    });
}


runDemo();

'use strict';

const crypto = require('crypto');

class AuthenticationError extends Error {}
class AuthorizationError extends Error {}

const AccountStatus = Object.freeze({
    ACTIVE: 'active',
    LOCKED: 'locked',
    DISABLED: 'disabled'
});

const SessionStatus = Object.freeze({
    ACTIVE: 'active',
    REVOKED: 'revoked',
    EXPIRED: 'expired'
});

class CredentialService {
    constructor(iterations = 210000) {
        this.iterations = iterations;
        this.users = new Map();
    }

    createPasswordRecord(password) {
        if (typeof password !== 'string' || password.length < 12) {
            throw new Error('Password must contain at least 12 characters.');
        }

        const salt = crypto.randomBytes(16);
        const digest = crypto.pbkdf2Sync(
            password,
            salt,
            this.iterations,
            32,
            'sha256'
        );

        return Object.freeze({
            algorithm: 'PBKDF2-HMAC-SHA256',
            iterations: this.iterations,
            salt: salt.toString('base64'),
            digest: digest.toString('base64')
        });
    }

    verifyPassword(password, record) {
        const salt = Buffer.from(record.salt, 'base64');
        const expected = Buffer.from(record.digest, 'base64');

        const actual = crypto.pbkdf2Sync(
            password,
            salt,
            record.iterations,
            expected.length,
            'sha256'
        );

        return crypto.timingSafeEqual(actual, expected);
    }
}

class AuthenticationService {
    constructor() {
        this.credentials = new CredentialService();
        this.users = new Map();
        this.sessions = new Map();
        this.nextUserId = 1;
        this.maxFailures = 5;
        this.sessionLifetimeMs = 30 * 60 * 1000;
    }

    register(username, password, roles = []) {
        const normalized = String(username).trim().toLowerCase();

        if (!normalized) {
            throw new Error('Username is required.');
        }

        if (this.users.has(normalized)) {
            throw new Error('Username already exists.');
        }

        const user = {
            id: this.nextUserId++,
            username: normalized,
            credential: this.credentials.createPasswordRecord(password),
            roles: new Set(roles),
            status: AccountStatus.ACTIVE,
            failedAttempts: 0
        };

        this.users.set(normalized, user);
        return user;
    }

    authenticate(username, password) {
        const normalized = String(username).trim().toLowerCase();
        const user = this.users.get(normalized);

        if (!user) {
            throw new AuthenticationError('Invalid credentials.');
        }

        if (user.status !== AccountStatus.ACTIVE) {
            throw new AuthenticationError('Account is not active.');
        }

        const valid = this.credentials.verifyPassword(
            password,
            user.credential
        );

        if (!valid) {
            user.failedAttempts += 1;

            if (user.failedAttempts >= this.maxFailures) {
                user.status = AccountStatus.LOCKED;
            }

            throw new AuthenticationError('Invalid credentials.');
        }

        user.failedAttempts = 0;

        const now = Date.now();
        const session = {
            id: crypto.randomBytes(32).toString('base64url'),
            userId: user.id,
            createdAt: now,
            expiresAt: now + this.sessionLifetimeMs,
            status: SessionStatus.ACTIVE
        };

        this.sessions.set(session.id, session);
        return session;
    }

    authenticateRequest(sessionId) {
        const session = this.sessions.get(sessionId);

        if (!session) {
            throw new AuthenticationError('Unknown session.');
        }

        if (session.status !== SessionStatus.ACTIVE) {
            throw new AuthenticationError('Session is not active.');
        }

        if (Date.now() >= session.expiresAt) {
            session.status = SessionStatus.EXPIRED;
            throw new AuthenticationError('Session expired.');
        }

        const user = [...this.users.values()]
            .find(candidate => candidate.id === session.userId);

        if (!user || user.status !== AccountStatus.ACTIVE) {
            throw new AuthenticationError('Identity is not active.');
        }

        return user;
    }

    authorize(sessionId, role) {
        const user = this.authenticateRequest(sessionId);

        if (!user.roles.has(role)) {
            throw new AuthorizationError(
                `Role '${role}' is required.`
            );
        }

        return user;
    }

    logout(sessionId) {
        const session = this.sessions.get(sessionId);

        if (session) {
            session.status = SessionStatus.REVOKED;
        }
    }
}

function printIdentity(user) {
    console.log(`Authenticated identity: ${user.username}`);
    console.log(`Roles: ${[...user.roles].join(', ')}`);
}

async function simulateProtectedRequest(
    service,
    sessionId,
    requiredRole
) {
    await new Promise(resolve => setTimeout(resolve, 10));

    try {
        const user = service.authorize(sessionId, requiredRole);
        return {
            allowed: true,
            username: user.username,
            resource: 'administrative-report'
        };
    } catch (error) {
        return {
            allowed: false,
            reason: error.message
        };
    }
}

async function main() {
    const service = new AuthenticationService();

    const user = service.register(
        'alice',
        'CorrectHorseBattery9!',
        ['user']
    );

    console.log('Identity created.');
    printIdentity(user);

    const session = service.authenticate(
        'alice',
        'CorrectHorseBattery9!'
    );

    console.log('\nAuthentication succeeded.');
    console.log(`Session: ${session.id.slice(0, 12)}...`);

    const normalAccess = await simulateProtectedRequest(
        service,
        session.id,
        'user'
    );

    console.log('\nAuthorization for user role:', normalAccess);

    const adminAccess = await simulateProtectedRequest(
        service,
        session.id,
        'administrator'
    );

    console.log('Authorization for administrator role:', adminAccess);

    user.roles.add('administrator');

    const upgradedAccess = await simulateProtectedRequest(
        service,
        session.id,
        'administrator'
    );

    console.log('Authorization after role assignment:', upgradedAccess);

    service.logout(session.id);

    try {
        service.authenticateRequest(session.id);
    } catch (error) {
        console.log('\nRevoked session rejected:', error.message);
    }

    const lockoutUser = service.register(
        'blocked',
        'StrongBlockedPassword9!',
        ['user']
    );

    for (let attempt = 1; attempt <= 5; attempt++) {
        try {
            service.authenticate('blocked', 'incorrect-password');
        } catch (error) {
            console.log(`Failed attempt ${attempt}: ${error.message}`);
        }
    }

    console.log(
        'Locked account status:',
        lockoutUser.status
    );
}

main().catch(error => {
    console.error('Application failure:', error.message);
    process.exitCode = 1;
});

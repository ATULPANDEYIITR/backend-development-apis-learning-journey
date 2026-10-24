'use strict';

const crypto = require('node:crypto');

class AuthenticationError extends Error {}
class TokenValidationError extends AuthenticationError {}
class AuthorizationError extends AuthenticationError {}

function base64urlEncode(value) {
    return Buffer.from(value)
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/g, '');
}

function base64urlDecode(value) {
    try {
        const normalized = value
            .replace(/-/g, '+')
            .replace(/_/g, '/')
            .padEnd(Math.ceil(value.length / 4) * 4, '=');

        return Buffer.from(normalized, 'base64');
    } catch (error) {
        throw new TokenValidationError('Invalid Base64URL data');
    }
}

function canonicalJson(value) {
    return JSON.stringify(value);
}

class JWTManager {
    constructor({
        secret,
        issuer,
        audience,
        accessTtlSeconds = 900,
    }) {
        if (!Buffer.isBuffer(secret) || secret.length < 32) {
            throw new Error('JWT secret must contain at least 32 bytes');
        }

        if (!issuer || !audience || accessTtlSeconds <= 0) {
            throw new Error('Invalid JWT configuration');
        }

        this.secret = secret;
        this.issuer = issuer;
        this.audience = audience;
        this.accessTtlSeconds = accessTtlSeconds;
    }

    sign(input) {
        return base64urlEncode(
            crypto
                .createHmac('sha256', this.secret)
                .update(input)
                .digest(),
        );
    }

    issueAccessToken({ subject, roles, scopes }) {
        if (!subject || !Array.isArray(roles) || roles.length === 0) {
            throw new Error('Invalid token subject or roles');
        }

        const now = Math.floor(Date.now() / 1000);

        const header = {
            alg: 'HS256',
            typ: 'JWT',
        };

        const payload = {
            iss: this.issuer,
            sub: subject,
            aud: this.audience,
            iat: now,
            nbf: now,
            exp: now + this.accessTtlSeconds,
            jti: crypto.randomBytes(18).toString('hex'),
            typ: 'access',
            roles: [...new Set(roles)].sort(),
            scope: [...new Set(scopes)].sort().join(' '),
        };

        const encodedHeader = base64urlEncode(canonicalJson(header));
        const encodedPayload = base64urlEncode(canonicalJson(payload));
        const input = `${encodedHeader}.${encodedPayload}`;
        const signature = this.sign(input);

        return `${input}.${signature}`;
    }

    validateAccessToken(token, requiredScope = null) {
        if (typeof token !== 'string') {
            throw new TokenValidationError('Token must be a string');
        }

        const parts = token.split('.');
        if (parts.length !== 3) {
            throw new TokenValidationError('JWT must have three segments');
        }

        const [encodedHeader, encodedPayload, encodedSignature] = parts;

        let header;
        let payload;

        try {
            header = JSON.parse(
                base64urlDecode(encodedHeader).toString('utf8'),
            );
            payload = JSON.parse(
                base64urlDecode(encodedPayload).toString('utf8'),
            );
        } catch {
            throw new TokenValidationError('Invalid JWT encoding');
        }

        if (header.alg !== 'HS256' || header.typ !== 'JWT') {
            throw new TokenValidationError('Unsupported JWT header');
        }

        const expectedSignature = this.sign(
            `${encodedHeader}.${encodedPayload}`,
        );

        const providedBuffer = Buffer.from(encodedSignature);
        const expectedBuffer = Buffer.from(expectedSignature);

        if (
            providedBuffer.length !== expectedBuffer.length ||
            !crypto.timingSafeEqual(providedBuffer, expectedBuffer)
        ) {
            throw new TokenValidationError('Invalid token signature');
        }

        const requiredClaims = [
            'iss',
            'sub',
            'aud',
            'iat',
            'nbf',
            'exp',
            'jti',
            'typ',
        ];

        for (const claim of requiredClaims) {
            if (!(claim in payload)) {
                throw new TokenValidationError(`Missing claim: ${claim}`);
            }
        }

        const now = Math.floor(Date.now() / 1000);

        if (payload.iss !== this.issuer) {
            throw new TokenValidationError('Invalid issuer');
        }

        if (payload.aud !== this.audience) {
            throw new TokenValidationError('Invalid audience');
        }

        if (payload.typ !== 'access') {
            throw new TokenValidationError('Invalid token type');
        }

        if (!Number.isInteger(payload.iat) ||
            !Number.isInteger(payload.nbf) ||
            !Number.isInteger(payload.exp)) {
            throw new TokenValidationError('Invalid time claims');
        }

        if (payload.iat > now + 30) {
            throw new TokenValidationError('Token issued in the future');
        }

        if (payload.nbf > now) {
            throw new TokenValidationError('Token is not active');
        }

        if (payload.exp <= now) {
            throw new TokenValidationError('Token has expired');
        }

        if (payload.exp <= payload.iat) {
            throw new TokenValidationError('Invalid token lifetime');
        }

        if (!Array.isArray(payload.roles)) {
            throw new TokenValidationError('Invalid roles claim');
        }

        const scopes = new Set(
            typeof payload.scope === 'string' && payload.scope.trim()
                ? payload.scope.trim().split(/\s+/)
                : [],
        );

        if (requiredScope && !scopes.has(requiredScope)) {
            throw new AuthorizationError('Required scope is missing');
        }

        return {
            ...payload,
            scopes: [...scopes],
        };
    }
}

class UserStore {
    constructor() {
        this.users = new Map();
    }

    addUser({ username, password, roles, scopes }) {
        if (this.users.has(username)) {
            throw new Error('Username already exists');
        }

        if (password.length < 12) {
            throw new Error('Password must contain at least 12 characters');
        }

        const salt = crypto.randomBytes(16);
        const derivedKey = crypto.pbkdf2Sync(
            password,
            salt,
            310000,
            32,
            'sha256',
        );

        const user = Object.freeze({
            userId: crypto.randomBytes(12).toString('hex'),
            username,
            salt: salt.toString('base64url'),
            passwordHash: derivedKey.toString('base64url'),
            roles: [...new Set(roles)].sort(),
            scopes: [...new Set(scopes)].sort(),
            active: true,
        });

        this.users.set(username, user);
        return user;
    }

    authenticate(username, password) {
        const user = this.users.get(username);

        if (!user || !user.active) {
            throw new AuthenticationError('Invalid credentials');
        }

        const salt = Buffer.from(user.salt, 'base64url');
        const expected = Buffer.from(user.passwordHash, 'base64url');
        const actual = crypto.pbkdf2Sync(
            password,
            salt,
            310000,
            32,
            'sha256',
        );

        if (
            expected.length !== actual.length ||
            !crypto.timingSafeEqual(expected, actual)
        ) {
            throw new AuthenticationError('Invalid credentials');
        }

        return user;
    }
}

class AuthenticationService {
    constructor(userStore, jwtManager) {
        this.userStore = userStore;
        this.jwtManager = jwtManager;
    }

    async login(username, password) {
        try {
            const user = this.userStore.authenticate(username, password);

            const accessToken = this.jwtManager.issueAccessToken({
                subject: user.userId,
                roles: user.roles,
                scopes: user.scopes,
            });

            return {
                status: 200,
                body: {
                    access_token: accessToken,
                    token_type: 'Bearer',
                    expires_in: this.jwtManager.accessTtlSeconds,
                },
            };
        } catch {
            return {
                status: 401,
                body: { error: 'invalid_credentials' },
            };
        }
    }

    protectedRoute(request, requiredScope) {
        const authorization = request.headers?.authorization ?? '';

        if (!authorization.startsWith('Bearer ')) {
            return {
                status: 401,
                body: { error: 'missing_bearer_token' },
            };
        }

        const token = authorization.slice(7).trim();

        try {
            const claims = this.jwtManager.validateAccessToken(
                token,
                requiredScope,
            );

            return {
                status: 200,
                body: {
                    message: 'Protected resource accessed',
                    subject: claims.sub,
                    scopes: claims.scopes,
                },
            };
        } catch (error) {
            if (error instanceof AuthorizationError) {
                return {
                    status: 403,
                    body: { error: 'insufficient_scope' },
                };
            }

            return {
                status: 401,
                body: { error: 'invalid_token' },
            };
        }
    }
}

async function main() {
    const jwtManager = new JWTManager({
        secret: crypto.randomBytes(32),
        issuer: 'https://auth.example.internal',
        audience: 'orders-api',
        accessTtlSeconds: 900,
    });

    const users = new UserStore();

    users.addUser({
        username: 'alice',
        password: 'correct-horse-battery-staple',
        roles: ['customer'],
        scopes: ['orders:read', 'profile:read'],
    });

    const service = new AuthenticationService(users, jwtManager);

    const login = await service.login(
        'alice',
        'correct-horse-battery-staple',
    );

    console.log('Login:', login.status);
    if (login.status !== 200) {
        throw new Error('Expected successful login');
    }

    const token = login.body.access_token;

    const authorized = service.protectedRoute(
        {
            method: 'GET',
            path: '/orders',
            headers: {
                authorization: `Bearer ${token}`,
            },
        },
        'orders:read',
    );

    console.log('Authorized request:', authorized);
    if (authorized.status !== 200) {
        throw new Error('Expected authorized request');
    }

    const insufficientScope = service.protectedRoute(
        {
            method: 'GET',
            path: '/orders',
            headers: {
                authorization: `Bearer ${token}`,
            },
        },
        'orders:write',
    );

    console.log('Insufficient scope:', insufficientScope);
    if (insufficientScope.status !== 403) {
        throw new Error('Expected authorization failure');
    }

    const tamperedToken =
        token.slice(0, -1) + (token.endsWith('A') ? 'B' : 'A');

    const tampered = service.protectedRoute(
        {
            method: 'GET',
            path: '/orders',
            headers: {
                authorization: `Bearer ${tamperedToken}`,
            },
        },
        'orders:read',
    );

    console.log('Tampered token:', tampered);
    if (tampered.status !== 401) {
        throw new Error('Expected token validation failure');
    }
}

main().catch((error) => {
    console.error('Application failure:', error.message);
    process.exitCode = 1;
});

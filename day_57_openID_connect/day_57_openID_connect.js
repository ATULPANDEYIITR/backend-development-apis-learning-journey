"use strict";

const crypto = require("node:crypto");

class AuthenticationError extends Error {}
class TokenValidationError extends AuthenticationError {}
class AuthorizationError extends AuthenticationError {}

const TokenType = Object.freeze({
    ID_TOKEN: "id_token",
    ACCESS_TOKEN: "access_token",
});

function base64UrlEncode(value) {
    return Buffer.from(value)
        .toString("base64")
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/g, "");
}

function base64UrlDecode(value) {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    return Buffer.from(
        normalized + "=".repeat((4 - (normalized.length % 4)) % 4),
        "base64"
    );
}

function stableJson(object) {
    const ordered = {};
    for (const key of Object.keys(object).sort()) {
        ordered[key] = object[key];
    }
    return JSON.stringify(ordered);
}

function createJwt(secret, header, payload) {
    const encodedHeader = base64UrlEncode(stableJson(header));
    const encodedPayload = base64UrlEncode(stableJson(payload));
    const signingInput = `${encodedHeader}.${encodedPayload}`;

    const signature = crypto
        .createHmac("sha256", secret)
        .update(signingInput)
        .digest();

    return `${signingInput}.${base64UrlEncode(signature)}`;
}

function verifyHmacSignature(secret, signingInput, encodedSignature) {
    const expected = crypto
        .createHmac("sha256", secret)
        .update(signingInput)
        .digest();

    const actual = base64UrlDecode(encodedSignature);

    return (
        actual.length === expected.length &&
        crypto.timingSafeEqual(actual, expected)
    );
}

function generateState() {
    return base64UrlEncode(crypto.randomBytes(24));
}

function generateNonce() {
    return base64UrlEncode(crypto.randomBytes(24));
}

function createPkcePair() {
    const verifier = base64UrlEncode(crypto.randomBytes(32));
    const challenge = base64UrlEncode(
        crypto.createHash("sha256").update(verifier).digest()
    );

    return { verifier, challenge };
}

class OIDCProvider {
    constructor({
        issuer,
        authorizationEndpoint,
        tokenEndpoint,
        userInfoEndpoint,
        signingSecret,
    }) {
        if (!issuer.startsWith("https://")) {
            throw new TypeError("OIDC issuer must use HTTPS");
        }

        this.issuer = issuer;
        this.authorizationEndpoint = authorizationEndpoint;
        this.tokenEndpoint = tokenEndpoint;
        this.userInfoEndpoint = userInfoEndpoint;
        this.signingSecret = signingSecret;
        this.users = new Map();
        this.authorizationCodes = new Map();
    }

    registerUser(user) {
        if (!user.sub || !user.email) {
            throw new TypeError("subject and email are required");
        }

        this.users.set(user.sub, Object.freeze({ ...user }));
    }

    authorize(request, authenticatedUser) {
        this.validateAuthorizationRequest(request);

        if (!this.users.has(authenticatedUser)) {
            throw new AuthorizationError("user authentication is required");
        }

        const code = base64UrlEncode(crypto.randomBytes(32));

        this.authorizationCodes.set(code, {
            code,
            clientId: request.clientId,
            redirectUri: request.redirectUri,
            subject: authenticatedUser,
            nonce: request.nonce,
            scope: new Set(request.scope),
            codeChallenge: request.codeChallenge,
            expiresAt: Date.now() + 120_000,
            consumed: false,
        });

        return code;
    }

    exchangeCode({ client, code, redirectUri, codeVerifier }) {
        const authorization = this.authorizationCodes.get(code);

        if (!authorization) {
            throw new AuthorizationError("unknown authorization code");
        }

        if (authorization.consumed) {
            throw new AuthorizationError("authorization code already used");
        }

        if (Date.now() >= authorization.expiresAt) {
            throw new AuthorizationError("authorization code expired");
        }

        if (authorization.clientId !== client.clientId) {
            throw new AuthorizationError("client mismatch");
        }

        if (authorization.redirectUri !== redirectUri) {
            throw new AuthorizationError("redirect URI mismatch");
        }

        if (authorization.codeChallenge) {
            if (!codeVerifier) {
                throw new AuthorizationError("PKCE verifier missing");
            }

            const calculated = base64UrlEncode(
                crypto.createHash("sha256").update(codeVerifier).digest()
            );

            if (
                !crypto.timingSafeEqual(
                    Buffer.from(calculated),
                    Buffer.from(authorization.codeChallenge)
                )
            ) {
                throw new AuthorizationError("PKCE validation failed");
            }
        }

        authorization.consumed = true;

        const issuedAt = Math.floor(Date.now() / 1000);

        const idToken = createJwt(
            this.signingSecret,
            {
                alg: "HS256",
                typ: "JWT",
            },
            {
                iss: this.issuer,
                sub: authorization.subject,
                aud: client.clientId,
                iat: issuedAt,
                exp: issuedAt + 3600,
                auth_time: issuedAt,
                nonce: authorization.nonce,
            }
        );

        return {
            token_type: "Bearer",
            access_token: base64UrlEncode(crypto.randomBytes(32)),
            id_token: idToken,
            expires_in: 3600,
        };
    }

    userInfo(accessToken, subject) {
        if (!accessToken) {
            throw new AuthenticationError("access token required");
        }

        const user = this.users.get(subject);

        if (!user) {
            throw new AuthenticationError("subject not found");
        }

        return {
            sub: user.sub,
            name: user.name,
            preferred_username: user.username,
            email: user.email,
            email_verified: user.emailVerified,
        };
    }

    validateAuthorizationRequest(request) {
        const requiredFields = [
            "state",
            "nonce",
            "clientId",
            "redirectUri",
        ];

        for (const field of requiredFields) {
            if (!request[field]) {
                throw new AuthorizationError(`${field} is required`);
            }
        }

        if (request.clientId !== "web-client") {
            throw new AuthorizationError("unknown client");
        }

        if (request.redirectUri !== "https://app.example.com/callback") {
            throw new AuthorizationError("redirect URI is not registered");
        }

        if (!request.scope.includes("openid")) {
            throw new AuthorizationError("openid scope is mandatory");
        }

        const supportedScopes = new Set([
            "openid",
            "profile",
            "email",
        ]);

        for (const scope of request.scope) {
            if (!supportedScopes.has(scope)) {
                throw new AuthorizationError(`unsupported scope: ${scope}`);
            }
        }
    }
}

class OIDCClient {
    constructor(provider, registration) {
        this.provider = provider;
        this.registration = registration;
        this.session = new Map();
    }

    createAuthorizationRequest() {
        const state = generateState();
        const nonce = generateNonce();
        const pkce = createPkcePair();

        const request = {
            responseType: "code",
            clientId: this.registration.clientId,
            redirectUri: "https://app.example.com/callback",
            scope: ["openid", "profile", "email"],
            state,
            nonce,
            codeChallenge: pkce.challenge,
            codeChallengeMethod: "S256",
        };

        this.session.set("state", state);
        this.session.set("nonce", nonce);
        this.session.set("codeVerifier", pkce.verifier);

        return request;
    }

    async authenticate(provider) {
        const request = this.createAuthorizationRequest();

        // In a browser this step is an actual redirect to the provider.
        // The simulator represents the authenticated provider session.
        const code = await Promise.resolve(
            provider.authorize(request, "user-42")
        );

        const tokenResponse = await Promise.resolve(
            provider.exchangeCode({
                client: this.registration,
                code,
                redirectUri: request.redirectUri,
                codeVerifier: this.session.get("codeVerifier"),
            })
        );

        if (request.state !== this.session.get("state")) {
            throw new AuthenticationError("state mismatch");
        }

        const claims = this.validateIdToken(
            tokenResponse.id_token,
            this.session.get("nonce")
        );

        this.session.set("authenticated", true);
        this.session.set("subject", claims.sub);
        this.session.set("accessToken", tokenResponse.access_token);

        return {
            claims,
            userInfo: provider.userInfo(
                tokenResponse.access_token,
                claims.sub
            ),
        };
    }

    validateIdToken(token, expectedNonce) {
        const parts = token.split(".");

        if (parts.length !== 3) {
            throw new TokenValidationError("invalid JWT structure");
        }

        const [encodedHeader, encodedPayload, encodedSignature] = parts;
        const signingInput = `${encodedHeader}.${encodedPayload}`;

        if (
            !verifyHmacSignature(
                this.provider.signingSecret,
                signingInput,
                encodedSignature
            )
        ) {
            throw new TokenValidationError("signature verification failed");
        }

        let header;
        let claims;

        try {
            header = JSON.parse(
                base64UrlDecode(encodedHeader).toString("utf8")
            );
            claims = JSON.parse(
                base64UrlDecode(encodedPayload).toString("utf8")
            );
        } catch {
            throw new TokenValidationError("malformed JWT");
        }

        if (header.alg !== "HS256" || header.typ !== "JWT") {
            throw new TokenValidationError("unexpected JWT header");
        }

        if (claims.iss !== this.provider.issuer) {
            throw new TokenValidationError("issuer mismatch");
        }

        if (claims.aud !== this.registration.clientId) {
            throw new TokenValidationError("audience mismatch");
        }

        if (claims.nonce !== expectedNonce) {
            throw new TokenValidationError("nonce mismatch");
        }

        const now = Math.floor(Date.now() / 1000);

        if (!Number.isInteger(claims.exp) || claims.exp <= now) {
            throw new TokenValidationError("token expired");
        }

        if (!Number.isInteger(claims.iat) || claims.iat > now + 60) {
            throw new TokenValidationError("invalid issued-at claim");
        }

        if (typeof claims.sub !== "string" || claims.sub.length === 0) {
            throw new TokenValidationError("invalid subject");
        }

        return claims;
    }
}

async function main() {
    const provider = new OIDCProvider({
        issuer: "https://id.example.com",
        authorizationEndpoint: "https://id.example.com/authorize",
        tokenEndpoint: "https://id.example.com/token",
        userInfoEndpoint: "https://id.example.com/userinfo",
        signingSecret: "development-signing-secret",
    });

    provider.registerUser({
        sub: "user-42",
        username: "atul",
        email: "atul@example.com",
        name: "Atul Pandey",
        emailVerified: true,
    });

    const registration = {
        clientId: "web-client",
        clientSecret: "client-secret",
        redirectUris: new Set([
            "https://app.example.com/callback",
        ]),
    };

    const client = new OIDCClient(provider, registration);

    const result = await client.authenticate(provider);

    console.log("Authentication succeeded");
    console.log("ID Token claims:", result.claims);
    console.log("UserInfo:", result.userInfo);

    try {
        client.validateIdToken(
            result.claims.invalidToken || "not-a-jwt",
            "incorrect-nonce"
        );
    } catch (error) {
        console.log("Expected validation failure:", error.message);
    }

    console.log("OIDC event flow completed.");
}

main().catch((error) => {
    console.error("Fatal authentication error:", error.message);
    process.exitCode = 1;
});

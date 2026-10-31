"use strict";

/*
 * Web Security Fundamentals
 *
 * This Node.js program provides an event-driven security assessment model.
 * It combines:
 *   - CIA asset classification
 *   - attack-surface discovery
 *   - threat scoring
 *   - secure input validation
 *   - authentication and authorization
 *   - rate limiting
 *   - security-header generation
 *   - security events
 *
 * No external npm dependencies are required.
 */

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");
const { URL } = require("node:url");

const SecurityLevel = Object.freeze({
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
});

const ThreatCategory = Object.freeze({
  SPOOFING: "Spoofing",
  TAMPERING: "Tampering",
  REPUDIATION: "Repudiation",
  INFORMATION_DISCLOSURE: "Information Disclosure",
  DENIAL_OF_SERVICE: "Denial of Service",
  ELEVATION_OF_PRIVILEGE: "Elevation of Privilege",
});

class SecurityError extends Error {}
class ValidationError extends SecurityError {}
class AuthenticationError extends SecurityError {}
class AuthorizationError extends SecurityError {}
class RateLimitError extends SecurityError {}

class Asset {
  constructor(name, confidentiality, integrity, availability, owner) {
    this.name = name;
    this.confidentiality = confidentiality;
    this.integrity = integrity;
    this.availability = availability;
    this.owner = owner;
    Object.freeze(this);
  }
}

class Threat {
  constructor(name, category, asset, likelihood, impact, mitigation) {
    this.name = name;
    this.category = category;
    this.asset = asset;
    this.likelihood = likelihood;
    this.impact = impact;
    this.mitigation = mitigation;
  }

  get riskScore() {
    return this.likelihood * this.impact;
  }
}

class AttackSurface {
  constructor() {
    this.endpoints = new Map();
    this.dataStores = new Map();
    this.trustBoundaries = new Set();
  }

  addEndpoint(path, methods, exposure) {
    if (!path.startsWith("/")) {
      throw new ValidationError("Endpoint must use an absolute path.");
    }

    this.endpoints.set(path, {
      methods: new Set(methods.map((m) => m.toUpperCase())),
      exposure,
    });
  }

  addDataStore(name, sensitivity) {
    this.dataStores.set(name, sensitivity);
  }

  addTrustBoundary(name) {
    this.trustBoundaries.add(name);
  }

  describe() {
    return {
      endpoints: [...this.endpoints.entries()].map(
        ([path, value]) => ({
          path,
          methods: [...value.methods],
          exposure: value.exposure,
        })
      ),
      dataStores: [...this.dataStores.entries()].map(
        ([name, sensitivity]) => ({ name, sensitivity })
      ),
      trustBoundaries: [...this.trustBoundaries],
    };
  }
}

class PasswordService {
  static async hash(password) {
    if (typeof password !== "string" || password.length < 12) {
      throw new ValidationError("Password must contain at least 12 characters.");
    }

    const salt = crypto.randomBytes(16);

    const derivedKey = await new Promise((resolve, reject) => {
      crypto.pbkdf2(
        password,
        salt,
        310000,
        32,
        "sha256",
        (error, key) => (error ? reject(error) : resolve(key))
      );
    });

    return [
      "pbkdf2_sha256",
      "310000",
      salt.toString("hex"),
      derivedKey.toString("hex"),
    ].join("$");
  }

  static async verify(password, encoded) {
    try {
      const [algorithm, iterationText, saltHex, digestHex] =
        encoded.split("$");

      if (algorithm !== "pbkdf2_sha256") return false;

      const iterations = Number(iterationText);
      const salt = Buffer.from(saltHex, "hex");
      const expected = Buffer.from(digestHex, "hex");

      const actual = await new Promise((resolve, reject) => {
        crypto.pbkdf2(
          password,
          salt,
          iterations,
          expected.length,
          "sha256",
          (error, key) => (error ? reject(error) : resolve(key))
        );
      });

      return (
        actual.length === expected.length &&
        crypto.timingSafeEqual(actual, expected)
      );
    } catch {
      return false;
    }
  }
}

class SessionStore {
  #sessions = new Map();

  create(username) {
    const token = crypto.randomBytes(32).toString("base64url");
    this.#sessions.set(token, {
      username,
      createdAt: Date.now(),
    });
    return token;
  }

  get(token) {
    return this.#sessions.get(token) ?? null;
  }

  revoke(token) {
    this.#sessions.delete(token);
  }
}

class RateLimiter {
  #windows = new Map();

  constructor(limit = 10, windowMs = 60000) {
    if (limit <= 0 || windowMs <= 0) {
      throw new ValidationError("Invalid rate-limit configuration.");
    }
    this.limit = limit;
    this.windowMs = windowMs;
  }

  check(identity) {
    const now = Date.now();
    const previous = this.#windows.get(identity);

    if (!previous || now - previous.startedAt >= this.windowMs) {
      this.#windows.set(identity, {
        startedAt: now,
        count: 1,
      });
      return;
    }

    if (previous.count >= this.limit) {
      throw new RateLimitError("Rate limit exceeded.");
    }

    previous.count += 1;
  }
}

class InputPolicy {
  static username(value) {
    if (
      typeof value !== "string" ||
      !/^[A-Za-z0-9_.-]{3,32}$/.test(value)
    ) {
      throw new ValidationError("Invalid username.");
    }
    return value;
  }

  static path(value) {
    if (typeof value !== "string" || !value.startsWith("/")) {
      throw new ValidationError("Invalid request path.");
    }

    if (value.includes("\0")) {
      throw new ValidationError("NUL byte rejected.");
    }

    const parsed = new URL(value, "https://security.invalid");

    if (parsed.origin !== "https://security.invalid") {
      throw new ValidationError("Absolute URLs are not accepted.");
    }

    if (parsed.pathname.split("/").includes("..")) {
      throw new ValidationError("Path traversal rejected.");
    }

    return value;
  }

  static requestBody(body) {
    if (typeof body !== "string") {
      throw new ValidationError("Request body must be text.");
    }

    if (Buffer.byteLength(body, "utf8") > 1024 * 1024) {
      throw new ValidationError("Request body exceeds 1 MiB.");
    }

    return body;
  }
}

class SecurityHeaders {
  static create() {
    return Object.freeze({
      "Content-Security-Policy":
        "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy":
        "camera=(), microphone=(), geolocation=()",
      "Cache-Control": "no-store",
    });
  }
}

class SecureWebService extends EventEmitter {
  #users = new Map();
  #roles = new Map();
  #sessions = new SessionStore();
  #rateLimiter = new RateLimiter(5, 60000);

  constructor() {
    super();
    this.on("security-event", (event) => {
      if (event.type === "authorization-failure") {
        console.warn(
          `[SECURITY] authorization failure for ${event.username}`
        );
      }
    });
  }

  async register(username, password) {
    username = InputPolicy.username(username);

    if (this.#users.has(username)) {
      throw new ValidationError("Username already exists.");
    }

    const passwordHash = await PasswordService.hash(password);

    this.#users.set(username, passwordHash);
    this.#roles.set(username, "user");
  }

  async login(username, password, clientIdentity) {
    this.#rateLimiter.check(clientIdentity);
    username = InputPolicy.username(username);

    const passwordHash = this.#users.get(username);

    if (
      !passwordHash ||
      !(await PasswordService.verify(password, passwordHash))
    ) {
      this.emit("security-event", {
        type: "authentication-failure",
        username,
        clientIdentity,
      });
      throw new AuthenticationError("Invalid credentials.");
    }

    const token = this.#sessions.create(username);

    this.emit("security-event", {
      type: "authentication-success",
      username,
      clientIdentity,
    });

    return token;
  }

  authorize(token, requiredRole) {
    const session = this.#sessions.get(token);

    if (!session) {
      throw new AuthenticationError("Session is invalid.");
    }

    const role = this.#roles.get(session.username);

    if (role !== requiredRole) {
      this.emit("security-event", {
        type: "authorization-failure",
        username: session.username,
        requiredRole,
      });
      throw new AuthorizationError("Required role is missing.");
    }

    return session.username;
  }

  setAdministrativeRoleForControlledTest(username) {
    if (!this.#users.has(username)) {
      throw new ValidationError("Unknown user.");
    }
    this.#roles.set(username, "admin");
  }

  handleRequest({ method, path, body = "", clientIdentity }) {
    const headers = SecurityHeaders.create();

    try {
      this.#rateLimiter.check(clientIdentity);
      InputPolicy.path(path);
      InputPolicy.requestBody(body);

      const allowedMethods = new Set([
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
      ]);

      method = method.toUpperCase();

      if (!allowedMethods.has(method)) {
        return {
          status: 405,
          allowed: false,
          reason: "HTTP method not allowed.",
          headers,
        };
      }

      return {
        status: 200,
        allowed: true,
        reason: "Security checks passed.",
        headers,
      };
    } catch (error) {
      if (error instanceof RateLimitError) {
        return {
          status: 429,
          allowed: false,
          reason: error.message,
          headers,
        };
      }

      if (error instanceof ValidationError) {
        return {
          status: 400,
          allowed: false,
          reason: error.message,
          headers,
        };
      }

      return {
        status: 500,
        allowed: false,
        reason: "Internal security processing failure.",
        headers,
      };
    }
  }
}

function buildThreatModel() {
  const assets = [
    new Asset(
      "credential-store",
      SecurityLevel.CRITICAL,
      SecurityLevel.HIGH,
      SecurityLevel.MEDIUM,
      "identity-service"
    ),
    new Asset(
      "session-store",
      SecurityLevel.CRITICAL,
      SecurityLevel.CRITICAL,
      SecurityLevel.HIGH,
      "web-service"
    ),
    new Asset(
      "customer-data",
      SecurityLevel.HIGH,
      SecurityLevel.HIGH,
      SecurityLevel.HIGH,
      "data-service"
    ),
    new Asset(
      "public-api",
      SecurityLevel.MEDIUM,
      SecurityLevel.HIGH,
      SecurityLevel.CRITICAL,
      "platform-team"
    ),
  ];

  const assetNames = new Set(assets.map((asset) => asset.name));

  const threats = [
    new Threat(
      "Credential stuffing",
      ThreatCategory.SPOOFING,
      "credential-store",
      SecurityLevel.HIGH,
      SecurityLevel.CRITICAL,
      "Rate limiting, strong password hashing, MFA and compromised-password screening."
    ),
    new Threat(
      "Session theft",
      ThreatCategory.SPOOFING,
      "session-store",
      SecurityLevel.HIGH,
      SecurityLevel.CRITICAL,
      "TLS, Secure and HttpOnly cookies, token rotation and short lifetimes."
    ),
    new Threat(
      "SQL injection",
      ThreatCategory.TAMPERING,
      "customer-data",
      SecurityLevel.HIGH,
      SecurityLevel.CRITICAL,
      "Parameterized queries and least-privilege database accounts."
    ),
    new Threat(
      "Cross-site scripting",
      ThreatCategory.INFORMATION_DISCLOSURE,
      "customer-data",
      SecurityLevel.HIGH,
      SecurityLevel.HIGH,
      "Contextual output encoding and restrictive Content Security Policy."
    ),
    new Threat(
      "Resource exhaustion",
      ThreatCategory.DENIAL_OF_SERVICE,
      "public-api",
      SecurityLevel.MEDIUM,
      SecurityLevel.CRITICAL,
      "Rate limits, request-size limits, timeouts and bounded work."
    ),
    new Threat(
      "Broken access control",
      ThreatCategory.ELEVATION_OF_PRIVILEGE,
      "customer-data",
      SecurityLevel.HIGH,
      SecurityLevel.CRITICAL,
      "Server-side authorization and deny-by-default access decisions."
    ),
  ];

  for (const threat of threats) {
    if (!assetNames.has(threat.asset)) {
      throw new Error(`Threat references unknown asset: ${threat.asset}`);
    }
  }

  return { assets, threats };
}

function buildAttackSurface() {
  const surface = new AttackSurface();

  surface.addEndpoint("/login", ["POST"], "internet");
  surface.addEndpoint("/profile", ["GET", "PATCH"], "authenticated");
  surface.addEndpoint("/admin/users", ["GET", "POST"], "administrator");
  surface.addEndpoint("/health", ["GET"], "internet");

  surface.addDataStore("credential-store", "critical");
  surface.addDataStore("customer-data", "high");
  surface.addDataStore("audit-log", "high");

  surface.addTrustBoundary("browser -> web application");
  surface.addTrustBoundary("web application -> database");
  surface.addTrustBoundary("web application -> external identity provider");

  return surface;
}

async function selfTest() {
  const service = new SecureWebService();

  await service.register(
    "alice",
    "CorrectHorseBatteryStaple!"
  );

  const token = await service.login(
    "alice",
    "CorrectHorseBatteryStaple!",
    "192.0.2.10"
  );

  if (!token || typeof token !== "string") {
    throw new Error("Session token generation failed.");
  }

  try {
    service.authorize(token, "admin");
    throw new Error("Authorization incorrectly succeeded.");
  } catch (error) {
    if (!(error instanceof AuthorizationError)) {
      throw error;
    }
  }

  service.setAdministrativeRoleForControlledTest("alice");
  if (service.authorize(token, "admin") !== "alice") {
    throw new Error("Administrative authorization failed.");
  }

  const valid = service.handleRequest({
    method: "GET",
    path: "/profile",
    body: "",
    clientIdentity: "198.51.100.10",
  });

  if (!valid.allowed || valid.status !== 200) {
    throw new Error("Valid request was rejected.");
  }

  const traversal = service.handleRequest({
    method: "GET",
    path: "/files/../secret",
    body: "",
    clientIdentity: "198.51.100.11",
  });

  if (traversal.status !== 400) {
    throw new Error("Path traversal was not rejected.");
  }

  const oversized = service.handleRequest({
    method: "POST",
    path: "/upload",
    body: "x".repeat(1024 * 1024 + 1),
    clientIdentity: "198.51.100.12",
  });

  if (oversized.status !== 400) {
    throw new Error("Oversized request was not rejected.");
  }

  console.log("All self-tests passed.");
}

async function main() {
  const { assets, threats } = buildThreatModel();
  const attackSurface = buildAttackSurface();

  console.log("WEB SECURITY FUNDAMENTALS");
  console.log("=".repeat(70));

  console.log("\nCIA asset model");
  for (const asset of assets) {
    console.log(
      `${asset.name}: C=${asset.confidentiality}, ` +
      `I=${asset.integrity}, A=${asset.availability}`
    );
  }

  console.log("\nAttack surface");
  console.table(attackSurface.describe().endpoints);

  console.log("\nHigh-risk threats");
  for (const threat of threats
    .filter((item) => item.riskScore >= 9)
    .sort((a, b) => b.riskScore - a.riskScore)) {
    console.log(
      `${threat.name}: ${threat.category}, ` +
      `risk=${threat.riskScore}, mitigation=${threat.mitigation}`
    );
  }

  await selfTest();

  const service = new SecureWebService();

  const requests = [
    {
      method: "GET",
      path: "/dashboard",
      body: "",
      clientIdentity: "203.0.113.10",
    },
    {
      method: "TRACE",
      path: "/debug",
      body: "",
      clientIdentity: "203.0.113.11",
    },
    {
      method: "GET",
      path: "/../../etc/passwd",
      body: "",
      clientIdentity: "203.0.113.12",
    },
  ];

  console.log("\nRequest security decisions");
  for (const request of requests) {
    const result = service.handleRequest(request);
    console.log(
      `${request.method} ${request.path} -> ` +
      `${result.status}: ${result.reason}`
    );
  }
}

main().catch((error) => {
  console.error(`Fatal error: ${error.message}`);
  process.exitCode = 1;
});

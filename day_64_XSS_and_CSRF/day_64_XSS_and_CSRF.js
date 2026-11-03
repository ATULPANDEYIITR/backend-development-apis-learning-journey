import { EventEmitter } from "node:events";
import { randomBytes, timingSafeEqual } from "node:crypto";

const SameSite = Object.freeze({
  STRICT: "Strict",
  LAX: "Lax",
  NONE: "None",
});

class SecurityError extends Error {
  constructor(message, code = "SECURITY_POLICY_REJECTED") {
    super(message);
    this.name = "SecurityError";
    this.code = code;
  }
}

function escapeHtmlText(value) {
  if (typeof value !== "string") {
    throw new TypeError("HTML content must be a string");
  }

  return value.replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function constantTimeEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string") {
    return false;
  }

  const a = Buffer.from(left, "utf8");
  const b = Buffer.from(right, "utf8");

  // timingSafeEqual requires equal-length buffers.
  return a.length === b.length && timingSafeEqual(a, b);
}

class CookiePolicy {
  constructor({
    name = "__Host-session",
    secure = true,
    httpOnly = true,
    sameSite = SameSite.LAX,
    path = "/",
    maxAge = 1800,
  } = {}) {
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name)) {
      throw new TypeError("Invalid cookie name");
    }
    if (!Object.values(SameSite).includes(sameSite)) {
      throw new TypeError("Unsupported SameSite value");
    }
    if (sameSite === SameSite.NONE && !secure) {
      throw new TypeError("SameSite=None requires Secure");
    }
    if (!path.startsWith("/") || path.includes(";")) {
      throw new TypeError("Invalid cookie path");
    }
    if (!Number.isSafeInteger(maxAge) || maxAge < 0) {
      throw new TypeError("maxAge must be a non-negative safe integer");
    }

    Object.assign(this, { name, secure, httpOnly, sameSite, path, maxAge });
    Object.freeze(this);
  }

  serialize(value) {
    if (
      typeof value !== "string" ||
      value.length === 0 ||
      /[\r\n;]/.test(value)
    ) {
      throw new TypeError("Invalid cookie value");
    }

    const attributes = [
      `${this.name}=${value}`,
      `Path=${this.path}`,
      `Max-Age=${this.maxAge}`,
      `SameSite=${this.sameSite}`,
    ];

    if (this.httpOnly) attributes.push("HttpOnly");
    if (this.secure) attributes.push("Secure");

    return attributes.join("; ");
  }
}

function cookieWillBeSent(policy, context) {
  const method = String(context.method).toUpperCase();

  if (policy.secure && !context.isTls) return false;
  if (!context.crossSite) return true;

  switch (policy.sameSite) {
    case SameSite.STRICT:
      return false;
    case SameSite.LAX:
      return context.topLevelNavigation && ["GET", "HEAD"].includes(method);
    case SameSite.NONE:
      return policy.secure;
    default:
      return false;
  }
}

class SecurityGateway extends EventEmitter {
  constructor(appOrigin, { sessionLifetimeMs = 30 * 60 * 1000 } = {}) {
    super();

    let parsedOrigin;
    try {
      parsedOrigin = new URL(appOrigin);
    } catch {
      throw new TypeError("Application origin must be a valid URL");
    }

    if (
      parsedOrigin.protocol !== "https:" ||
      parsedOrigin.origin !== appOrigin ||
      parsedOrigin.username ||
      parsedOrigin.password
    ) {
      throw new TypeError("Use a canonical HTTPS application origin");
    }

    if (!Number.isSafeInteger(sessionLifetimeMs) || sessionLifetimeMs <= 0) {
      throw new TypeError("Session lifetime must be positive");
    }

    this.appOrigin = appOrigin;
    this.sessionLifetimeMs = sessionLifetimeMs;
    this.sessions = new Map();
    this.comments = new Map();
    this.nextCommentId = 1;
    this.maxInputLength = 5000;
  }

  issueSession(userId) {
    if (typeof userId !== "string" || !userId.trim()) {
      throw new TypeError("A user ID is required");
    }

    const session = Object.freeze({
      id: randomBytes(32).toString("base64url"),
      userId,
      csrfToken: randomBytes(32).toString("base64url"),
      expiresAt: Date.now() + this.sessionLifetimeMs,
      revoked: false,
    });

    this.sessions.set(session.id, session);
    this.emit("session:issued", { userId });
    return session;
  }

  revokeSession(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return false;

    this.sessions.set(
      sessionId,
      Object.freeze({ ...session, revoked: true }),
    );
    this.emit("session:revoked", { userId: session.userId });
    return true;
  }

  validateInput(value, label = "Input") {
    if (typeof value !== "string") {
      throw new TypeError(`${label} must be a string`);
    }
    if (!value.trim() || value.length > this.maxInputLength) {
      throw new TypeError(`${label} is empty or exceeds the size limit`);
    }
    if (value.includes("\0")) {
      throw new TypeError(`${label} contains a null character`);
    }
  }

  renderReflectedQuery(query) {
    this.validateInput(query, "Search query");
    return `<main><p>Search results for: ${escapeHtmlText(query)}</p></main>`;
  }

  verifyStateChangingRequest({ sessionId, csrfToken, origin, method }) {
    const normalizedMethod = String(method).toUpperCase();

    if (!["POST", "PUT", "PATCH", "DELETE"].includes(normalizedMethod)) {
      throw new SecurityError(
        "A state-changing HTTP method is required",
        "INVALID_METHOD",
      );
    }

    const session = this.sessions.get(sessionId);

    let reason = null;
    if (!session || session.revoked || session.expiresAt <= Date.now()) {
      reason = "missing, expired, or revoked session";
    } else if (origin !== this.appOrigin) {
      reason = "origin mismatch";
    } else if (!constantTimeEqual(session.csrfToken, csrfToken)) {
      reason = "CSRF token mismatch";
    }

    if (reason) {
      this.emit("csrf:rejected", {
        reason,
        method: normalizedMethod,
        origin,
      });
      throw new SecurityError(`Request rejected: ${reason}`, "CSRF_REJECTED");
    }

    this.emit("csrf:accepted", { userId: session.userId });
    return session;
  }

  async submitComment(request, body) {
    this.validateInput(body, "Comment");

    const session = this.verifyStateChangingRequest(request);

    // Persistence stores the original text. Encoding is applied when rendered.
    const comment = Object.freeze({
      id: this.nextCommentId++,
      userId: session.userId,
      body,
      createdAt: new Date().toISOString(),
    });

    this.comments.set(comment.id, comment);
    this.emit("comment:created", { id: comment.id, userId: session.userId });
    return comment.id;
  }

  renderStoredComment(commentId) {
    const comment = this.comments.get(commentId);
    if (!comment) {
      throw new RangeError("Comment was not found");
    }

    return `<article>${escapeHtmlText(comment.body)}</article>`;
  }

  responseHeaders() {
    return Object.freeze({
      "Content-Security-Policy":
        "default-src 'self'; object-src 'none'; base-uri 'self'; " +
        "frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Cache-Control": "no-store",
    });
  }
}

async function main() {
  const gateway = new SecurityGateway("https://portal.example.test");

  gateway.on("csrf:rejected", (event) => {
    console.log("AUDIT: rejected request:", event.reason);
  });

  gateway.on("comment:created", (event) => {
    console.log("AUDIT: comment created:", event.id);
  });

  const session = gateway.issueSession("customer-208");

  const cookiePolicy = new CookiePolicy();
  console.log("SET-COOKIE:", cookiePolicy.serialize(session.id));

  console.log(
    "Lax cross-site POST sends cookie:",
    cookieWillBeSent(cookiePolicy, {
      crossSite: true,
      topLevelNavigation: false,
      method: "POST",
      isTls: true,
    }),
  );

  console.log(
    "Lax cross-site top-level GET sends cookie:",
    cookieWillBeSent(cookiePolicy, {
      crossSite: true,
      topLevelNavigation: true,
      method: "GET",
      isTls: true,
    }),
  );

  const untrusted = '<img src=x onerror="alert(1)">';
  const reflected = gateway.renderReflectedQuery(untrusted);
  console.log("\nREFLECTED OUTPUT:", reflected);

  const validRequest = {
    sessionId: session.id,
    csrfToken: session.csrfToken,
    origin: "https://portal.example.test",
    method: "POST",
  };

  const commentId = await gateway.submitComment(validRequest, untrusted);
  console.log("STORED OUTPUT:", gateway.renderStoredComment(commentId));

  try {
    await gateway.submitComment(
      { ...validRequest, csrfToken: "incorrect-token" },
      "This must not be stored",
    );
  } catch (error) {
    if (!(error instanceof SecurityError)) throw error;
    console.log("Invalid token rejected:", error.code);
  }

  try {
    await gateway.submitComment(
      { ...validRequest, origin: "https://external.example" },
      "This must not be stored",
    );
  } catch (error) {
    if (!(error instanceof SecurityError)) throw error;
    console.log("Foreign origin rejected:", error.code);
  }

  console.log("\nRESPONSE HEADERS:", gateway.responseHeaders());

  const strictCookie = new CookiePolicy({ sameSite: SameSite.STRICT });
  const noneCookie = new CookiePolicy({ sameSite: SameSite.NONE, secure: true });

  console.log(
    "Strict cookie on cross-site GET:",
    cookieWillBeSent(strictCookie, {
      crossSite: true,
      topLevelNavigation: true,
      method: "GET",
      isTls: true,
    }),
  );

  console.log(
    "None cookie on cross-site POST:",
    cookieWillBeSent(noneCookie, {
      crossSite: true,
      topLevelNavigation: false,
      method: "POST",
      isTls: true,
    }),
  );
}

main().catch((error) => {
  console.error("Application failure:", error.message);
  process.exitCode = 1;
});

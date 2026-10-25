'use strict';

/**
 * Event-driven refresh-token lifecycle and policy evaluation.
 * Run with Node.js 18 or later.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

class AuthenticationError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'AuthenticationError';
    this.code = code;
  }
}

const TokenState = Object.freeze({
  ACTIVE: 'active',
  ROTATED: 'rotated',
  REVOKED: 'revoked',
  EXPIRED: 'expired',
});

class TokenLedger extends EventEmitter {
  constructor({
    accessTtlSeconds = 300,
    refreshTtlSeconds = 86400,
    clock = () => Date.now(),
  } = {}) {
    super();

    if (
      !Number.isSafeInteger(accessTtlSeconds) ||
      !Number.isSafeInteger(refreshTtlSeconds) ||
      accessTtlSeconds <= 0 ||
      refreshTtlSeconds <= accessTtlSeconds
    ) {
      throw new RangeError('Invalid token lifetime configuration');
    }

    this.accessTtlMs = accessTtlSeconds * 1000;
    this.refreshTtlMs = refreshTtlSeconds * 1000;
    this.clock = clock;

    this.sessions = new Map();
    this.refreshIndex = new Map();
    this.accessIndex = new Map();
    this.mutex = Promise.resolve();
  }

  static hash(token) {
    return crypto.createHash('sha256').update(token).digest('hex');
  }

  static newToken() {
    return crypto.randomBytes(48).toString('base64url');
  }

  emitAudit(type, session, details = {}) {
    // Audit records never include raw credentials.
    this.emit('audit', Object.freeze({
      type,
      sessionId: session.id,
      userId: session.userId,
      generation: session.generation,
      timestamp: this.clock(),
      ...details,
    }));
  }

  async exclusive(operation) {
    // Serialize mutations in this process. This is not a substitute for
    // database transactions when multiple application instances are used.
    const previous = this.mutex;
    let release;
    this.mutex = new Promise((resolve) => {
      release = resolve;
    });

    await previous;
    try {
      return await operation();
    } finally {
      release();
    }
  }

  issuePair(session) {
    const now = this.clock();
    const accessToken = TokenLedger.newToken();
    const refreshToken = TokenLedger.newToken();
    const accessHash = TokenLedger.hash(accessToken);
    const refreshHash = TokenLedger.hash(refreshToken);

    session.currentRefreshHash = refreshHash;
    session.generation += 1;

    this.refreshIndex.set(refreshHash, {
      sessionId: session.id,
      state: TokenState.ACTIVE,
      expiresAt: session.expiresAt,
      generation: session.generation,
    });

    this.accessIndex.set(accessHash, {
      sessionId: session.id,
      expiresAt: Math.min(now + this.accessTtlMs, session.expiresAt),
    });

    return Object.freeze({
      accessToken,
      refreshToken,
      accessExpiresAt: Math.min(now + this.accessTtlMs, session.expiresAt),
      refreshExpiresAt: session.expiresAt,
      generation: session.generation,
    });
  }

  async login(userId) {
    if (typeof userId !== 'string' || !userId.trim()) {
      throw new TypeError('A non-empty user ID is required');
    }

    return this.exclusive(async () => {
      const now = this.clock();
      const session = {
        id: crypto.randomUUID(),
        userId: userId.trim(),
        createdAt: now,
        expiresAt: now + this.refreshTtlMs,
        currentRefreshHash: null,
        generation: 0,
        status: TokenState.ACTIVE,
      };

      this.sessions.set(session.id, session);
      const pair = this.issuePair(session);
      this.emitAudit('session.created', session);
      return pair;
    });
  }

  authenticateAccess(accessToken) {
    if (typeof accessToken !== 'string' || !accessToken) {
      throw new AuthenticationError('Missing access token', 'MISSING_TOKEN');
    }

    const entry = this.accessIndex.get(TokenLedger.hash(accessToken));
    if (!entry) {
      throw new AuthenticationError('Unknown access token', 'INVALID_TOKEN');
    }

    const session = this.sessions.get(entry.sessionId);
    const now = this.clock();

    if (!session || session.status === TokenState.REVOKED) {
      throw new AuthenticationError('Session revoked', 'REVOKED');
    }
    if (now >= entry.expiresAt || now >= session.expiresAt) {
      throw new AuthenticationError('Access token expired', 'EXPIRED');
    }

    return Object.freeze({
      userId: session.userId,
      sessionId: session.id,
      expiresAt: entry.expiresAt,
    });
  }

  async refresh(refreshToken) {
    if (typeof refreshToken !== 'string' || !refreshToken) {
      throw new AuthenticationError('Missing refresh token', 'MISSING_TOKEN');
    }

    return this.exclusive(async () => {
      const hash = TokenLedger.hash(refreshToken);
      const entry = this.refreshIndex.get(hash);

      if (!entry) {
        throw new AuthenticationError('Unknown refresh token', 'INVALID_TOKEN');
      }

      const session = this.sessions.get(entry.sessionId);
      const now = this.clock();

      if (!session || session.status === TokenState.REVOKED) {
        throw new AuthenticationError('Session revoked', 'REVOKED');
      }

      if (now >= entry.expiresAt || now >= session.expiresAt) {
        entry.state = TokenState.EXPIRED;
        session.status = TokenState.EXPIRED;
        this.emitAudit('refresh.expired', session);
        throw new AuthenticationError('Refresh token expired', 'EXPIRED');
      }

      if (
        entry.state !== TokenState.ACTIVE ||
        session.currentRefreshHash !== hash
      ) {
        // Reuse of a previously rotated credential is treated as a possible
        // theft signal. Revoke the session to prevent further rotation.
        session.status = TokenState.REVOKED;
        for (const [knownHash, knownEntry] of this.refreshIndex) {
          if (knownEntry.sessionId === session.id) {
            knownEntry.state = TokenState.REVOKED;
          }
        }
        this.emitAudit('refresh.replay_detected', session);
        throw new AuthenticationError('Refresh-token reuse detected', 'REPLAY');
      }

      entry.state = TokenState.ROTATED;
      this.emitAudit('refresh.rotated', session);

      return this.issuePair(session);
    });
  }

  async revokeSession(sessionId) {
    return this.exclusive(async () => {
      const session = this.sessions.get(sessionId);
      if (!session || session.status === TokenState.REVOKED) {
        return false;
      }

      session.status = TokenState.REVOKED;

      for (const entry of this.refreshIndex.values()) {
        if (entry.sessionId === sessionId) {
          entry.state = TokenState.REVOKED;
        }
      }

      this.emitAudit('session.revoked', session);
      return true;
    });
  }

  async revokeRefreshToken(refreshToken) {
    if (typeof refreshToken !== 'string' || !refreshToken) {
      throw new AuthenticationError('Missing refresh token', 'MISSING_TOKEN');
    }

    const entry = this.refreshIndex.get(TokenLedger.hash(refreshToken));
    if (!entry) return false;
    return this.revokeSession(entry.sessionId);
  }

  policyReport(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return { eligible: false, reason: 'unknown_session' };

    const now = this.clock();
    if (session.status !== TokenState.ACTIVE) {
      return { eligible: false, reason: session.status };
    }
    if (now >= session.expiresAt) {
      return { eligible: false, reason: 'expired' };
    }

    return {
      eligible: true,
      reason: 'active',
      generation: session.generation,
      expiresAt: session.expiresAt,
    };
  }
}

async function main() {
  const ledger = new TokenLedger({
    accessTtlSeconds: 300,
    refreshTtlSeconds: 3600,
  });

  ledger.on('audit', (event) => {
    console.log('AUDIT', JSON.stringify(event));
  });

  const initial = await ledger.login('employee-204');
  console.log('Authenticated:', ledger.authenticateAccess(initial.accessToken));

  const rotated = await ledger.refresh(initial.refreshToken);
  console.log('Generation after rotation:', rotated.generation);

  try {
    await ledger.refresh(initial.refreshToken);
  } catch (error) {
    console.log('Reuse rejected:', error.code);
  }

  console.log('Session policy:', ledger.policyReport(
    ledger.authenticateAccess(rotated.accessToken).sessionId,
  ));
}

if (require.main === module) {
  main().catch((error) => {
    console.error('Authentication workflow failed:', error.message);
    process.exitCode = 1;
  });
}

module.exports = { TokenLedger, AuthenticationError, TokenState };

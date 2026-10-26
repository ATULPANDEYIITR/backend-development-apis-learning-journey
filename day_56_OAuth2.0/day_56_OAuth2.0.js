'use strict';

/*
 * OAuth 2.0 event-driven policy model.
 *
 * This implementation focuses on:
 * - authorization code + PKCE
 * - client registration
 * - scopes
 * - access and refresh tokens
 * - resource-server authorization
 * - event-driven audit records
 * - refresh-token rotation
 * - revocation
 *
 * Tokens are opaque random values in this executable model.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

class OAuthError extends Error {
  constructor(code, description) {
    super(description);
    this.name = 'OAuthError';
    this.code = code;
  }
}

function randomToken(bytes = 32) {
  return crypto.randomBytes(bytes).toString('base64url');
}

function pkceChallenge(verifier) {
  return crypto
    .createHash('sha256')
    .update(verifier, 'ascii')
    .digest('base64url');
}

function safeEqual(a, b) {
  const left = Buffer.from(a);
  const right = Buffer.from(b);

  return left.length === right.length &&
    crypto.timingSafeEqual(left, right);
}

function assertString(value, field) {
  if (typeof value !== 'string' || value.length === 0) {
    throw new OAuthError('invalid_request', `${field} is required`);
  }
}

class OAuthAudit extends EventEmitter {
  record(event, details) {
    this.emit('audit', {
      event,
      timestamp: new Date().toISOString(),
      ...details,
    });
  }
}

class AuthorizationServer {
  constructor(issuer) {
    this.issuer = issuer;
    this.clients = new Map();
    this.codes = new Map();
    this.accessTokens = new Map();
    this.refreshTokens = new Map();
    this.audit = new OAuthAudit();
  }

  registerClient(client) {
    assertString(client.clientId, 'clientId');

    if (!Array.isArray(client.redirectUris) ||
        client.redirectUris.length === 0) {
      throw new OAuthError(
        'invalid_client',
        'at least one redirect URI is required'
      );
    }

    if (!(client.allowedScopes instanceof Set) ||
        client.allowedScopes.size === 0) {
      throw new OAuthError(
        'invalid_client',
        'at least one allowed scope is required'
      );
    }

    if (client.confidential && !client.clientSecret) {
      throw new OAuthError(
        'invalid_client',
        'confidential clients require credentials'
      );
    }

    this.clients.set(client.clientId, Object.freeze({
      ...client,
      redirectUris: new Set(client.redirectUris),
      allowedScopes: new Set(client.allowedScopes),
    }));

    this.audit.record('client_registered', {
      clientId: client.clientId,
    });
  }

  authorize({
    clientId,
    redirectUri,
    resourceOwner,
    scopes,
    codeChallenge,
    expiresInSeconds = 120,
  }) {
    const client = this.clients.get(clientId);

    if (!client) {
      throw new OAuthError('invalid_client', 'unknown client');
    }

    if (!client.redirectUris.has(redirectUri)) {
      throw new OAuthError(
        'invalid_request',
        'redirect URI is not registered'
      );
    }

    if (!resourceOwner) {
      throw new OAuthError(
        'invalid_request',
        'resource owner is required'
      );
    }

    assertString(codeChallenge, 'codeChallenge');

    if (!(scopes instanceof Set) || scopes.size === 0) {
      throw new OAuthError(
        'invalid_scope',
        'at least one scope is required'
      );
    }

    for (const scope of scopes) {
      if (!client.allowedScopes.has(scope)) {
        throw new OAuthError(
          'invalid_scope',
          `scope is not permitted: ${scope}`
        );
      }
    }

    const code = randomToken();

    this.codes.set(code, {
      clientId,
      redirectUri,
      resourceOwner,
      scopes: new Set(scopes),
      codeChallenge,
      expiresAt: Date.now() + expiresInSeconds * 1000,
      used: false,
    });

    this.audit.record('authorization_code_issued', {
      clientId,
      resourceOwner,
      scopes: [...scopes],
    });

    return code;
  }

  token({
    clientId,
    code,
    redirectUri,
    codeVerifier,
    clientSecret,
  }) {
    const client = this.clients.get(clientId);

    if (!client) {
      throw new OAuthError('invalid_client', 'unknown client');
    }

    if (client.confidential) {
      if (!clientSecret ||
          !safeEqual(client.clientSecret, clientSecret)) {
        throw new OAuthError(
          'invalid_client',
          'client authentication failed'
        );
      }
    }

    const record = this.codes.get(code);

    if (!record) {
      throw new OAuthError(
        'invalid_grant',
        'authorization code is invalid'
      );
    }

    if (record.used) {
      throw new OAuthError(
        'invalid_grant',
        'authorization code has already been used'
      );
    }

    if (Date.now() >= record.expiresAt) {
      throw new OAuthError(
        'invalid_grant',
        'authorization code has expired'
      );
    }

    if (record.clientId !== clientId ||
        record.redirectUri !== redirectUri) {
      throw new OAuthError(
        'invalid_grant',
        'authorization request does not match token request'
      );
    }

    if (pkceChallenge(codeVerifier) !== record.codeChallenge) {
      throw new OAuthError(
        'invalid_grant',
        'PKCE verification failed'
      );
    }

    record.used = true;

    const accessToken = {
      value: randomToken(),
      clientId,
      resourceOwner: record.resourceOwner,
      scopes: new Set(record.scopes),
      expiresAt: Date.now() + 15 * 60 * 1000,
      revoked: false,
    };

    const refreshToken = {
      value: randomToken(),
      clientId,
      resourceOwner: record.resourceOwner,
      scopes: new Set(record.scopes),
      expiresAt: Date.now() + 24 * 60 * 60 * 1000,
      revoked: false,
    };

    this.accessTokens.set(accessToken.value, accessToken);
    this.refreshTokens.set(refreshToken.value, refreshToken);

    this.audit.record('tokens_issued', {
      clientId,
      resourceOwner: record.resourceOwner,
      scopes: [...record.scopes],
    });

    return {
      tokenType: 'Bearer',
      accessToken,
      refreshToken,
    };
  }

  refresh({ clientId, refreshToken, clientSecret }) {
    const client = this.clients.get(clientId);

    if (!client) {
      throw new OAuthError('invalid_client', 'unknown client');
    }

    if (client.confidential) {
      if (!clientSecret ||
          !safeEqual(client.clientSecret, clientSecret)) {
        throw new OAuthError(
          'invalid_client',
          'client authentication failed'
        );
      }
    }

    const oldToken = this.refreshTokens.get(refreshToken);

    if (!oldToken ||
        oldToken.revoked ||
        Date.now() >= oldToken.expiresAt) {
      throw new OAuthError(
        'invalid_grant',
        'refresh token is invalid'
      );
    }

    if (oldToken.clientId !== clientId) {
      throw new OAuthError(
        'invalid_grant',
        'refresh token belongs to another client'
      );
    }

    // Rotation means the old token cannot be replayed.
    oldToken.revoked = true;

    const accessToken = {
      value: randomToken(),
      clientId,
      resourceOwner: oldToken.resourceOwner,
      scopes: new Set(oldToken.scopes),
      expiresAt: Date.now() + 15 * 60 * 1000,
      revoked: false,
    };

    const newRefreshToken = {
      value: randomToken(),
      clientId,
      resourceOwner: oldToken.resourceOwner,
      scopes: new Set(oldToken.scopes),
      expiresAt: Date.now() + 24 * 60 * 60 * 1000,
      revoked: false,
    };

    this.accessTokens.set(accessToken.value, accessToken);
    this.refreshTokens.set(newRefreshToken.value, newRefreshToken);

    this.audit.record('refresh_rotated', { clientId });

    return {
      tokenType: 'Bearer',
      accessToken,
      refreshToken: newRefreshToken,
    };
  }

  revoke(tokenValue) {
    const token = this.accessTokens.get(tokenValue);

    if (token) {
      token.revoked = true;
      this.audit.record('access_token_revoked', {
        clientId: token.clientId,
      });
    }
  }

  validateAccessToken(tokenValue, requiredScope) {
    const token = this.accessTokens.get(tokenValue);

    if (!token || token.revoked) {
      throw new OAuthError(
        'invalid_token',
        'access token is invalid or revoked'
      );
    }

    if (Date.now() >= token.expiresAt) {
      throw new OAuthError(
        'invalid_token',
        'access token has expired'
      );
    }

    if (!token.scopes.has(requiredScope)) {
      throw new OAuthError(
        'insufficient_scope',
        `scope required: ${requiredScope}`
      );
    }

    return token;
  }
}

class ResourceServer {
  constructor(authorizationServer) {
    this.authorizationServer = authorizationServer;
    this.resources = new Map();
  }

  addResource(resource) {
    if (this.resources.has(resource.id)) {
      throw new Error(`resource already exists: ${resource.id}`);
    }

    this.resources.set(resource.id, Object.freeze({ ...resource }));
  }

  async fetchResource(tokenValue, resourceId) {
    // Promise-based API models an actual asynchronous resource-server boundary.
    await new Promise(resolve => setImmediate(resolve));

    const resource = this.resources.get(resourceId);

    if (!resource) {
      throw new OAuthError(
        'invalid_request',
        'resource does not exist'
      );
    }

    const token = this.authorizationServer.validateAccessToken(
      tokenValue,
      resource.requiredScope
    );

    if (token.resourceOwner !== resource.owner) {
      throw new OAuthError(
        'forbidden',
        'token subject cannot access this resource'
      );
    }

    return {
      id: resource.id,
      owner: resource.owner,
      data: { ...resource.data },
    };
  }
}

async function main() {
  const auth = new AuthorizationServer(
    'https://authorization.example.test'
  );

  auth.audit.on('audit', event => {
    console.log(`[AUDIT] ${event.event}`, event);
  });

  const resourceServer = new ResourceServer(auth);

  auth.registerClient({
    clientId: 'orders-web',
    redirectUris: ['https://orders.example.test/oauth/callback'],
    allowedScopes: new Set(['orders:read', 'profile:read']),
    confidential: true,
    clientSecret: 'replace-with-managed-secret',
  });

  resourceServer.addResource({
    id: 'orders:alice',
    owner: 'alice',
    requiredScope: 'orders:read',
    data: {
      orderCount: 3,
      latestOrder: 'ORD-1003',
    },
  });

  const verifier = randomToken(48);
  const challenge = pkceChallenge(verifier);

  const code = auth.authorize({
    clientId: 'orders-web',
    redirectUri: 'https://orders.example.test/oauth/callback',
    resourceOwner: 'alice',
    scopes: new Set(['orders:read']),
    codeChallenge: challenge,
  });

  const tokens = auth.token({
    clientId: 'orders-web',
    code,
    redirectUri: 'https://orders.example.test/oauth/callback',
    codeVerifier: verifier,
    clientSecret: 'replace-with-managed-secret',
  });

  const data = await resourceServer.fetchResource(
    tokens.accessToken.value,
    'orders:alice'
  );

  console.log('Protected resource:', data);

  const refreshed = auth.refresh({
    clientId: 'orders-web',
    refreshToken: tokens.refreshToken.value,
    clientSecret: 'replace-with-managed-secret',
  });

  console.log(
    'Refresh token rotated:',
    refreshed.refreshToken.value !== tokens.refreshToken.value
  );

  try {
    auth.refresh({
      clientId: 'orders-web',
      refreshToken: tokens.refreshToken.value,
      clientSecret: 'replace-with-managed-secret',
    });
  } catch (error) {
    console.log('Refresh replay rejected:', error.code);
  }

  try {
    await resourceServer.fetchResource(
      refreshed.accessToken.value,
      'orders:alice'
    );
  } catch (error) {
    console.log('Unexpected resource failure:', error.code);
  }

  auth.revoke(refreshed.accessToken.value);

  try {
    await resourceServer.fetchResource(
      refreshed.accessToken.value,
      'orders:alice'
    );
  } catch (error) {
    console.log('Revoked token rejected:', error.code);
  }

  try {
    auth.authorize({
      clientId: 'orders-web',
      redirectUri: 'https://evil.example.test/callback',
      resourceOwner: 'alice',
      scopes: new Set(['orders:read']),
      codeChallenge: challenge,
    });
  } catch (error) {
    console.log('Unregistered redirect URI rejected:', error.code);
  }

  try {
    auth.authorize({
      clientId: 'orders-web',
      redirectUri: 'https://orders.example.test/oauth/callback',
      resourceOwner: 'alice',
      scopes: new Set(['admin:write']),
      codeChallenge: challenge,
    });
  } catch (error) {
    console.log('Unauthorized scope rejected:', error.code);
  }
}

main().catch(error => {
  console.error('Fatal error:', error);
  process.exitCode = 1;
});

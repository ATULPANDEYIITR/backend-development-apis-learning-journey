'use strict';

/*
 * JWT Fundamentals
 *
 * A dependency-free Node.js implementation of HS256 JWT issuance and
 * verification. The example models an API that authenticates users and
 * authorizes repository operations using claims.
 */

const crypto = require('node:crypto');

class JWTError extends Error {}
class JWTFormatError extends JWTError {}
class JWTSignatureError extends JWTError {}
class JWTClaimsError extends JWTError {}

function base64urlEncode(value) {
  return Buffer.from(value).toString('base64url');
}

function base64urlDecode(value) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new JWTFormatError('Invalid Base64URL segment');
  }

  try {
    return Buffer.from(value, 'base64url');
  } catch (error) {
    throw new JWTFormatError('Invalid Base64URL encoding');
  }
}

function compactJson(value) {
  return Buffer.from(JSON.stringify(value), 'utf8');
}

function parseJsonSegment(segment) {
  try {
    const value = JSON.parse(base64urlDecode(segment).toString('utf8'));

    if (value === null || Array.isArray(value) || typeof value !== 'object') {
      throw new JWTFormatError('JWT JSON segment must be an object');
    }

    return value;
  } catch (error) {
    if (error instanceof JWTError) {
      throw error;
    }

    throw new JWTFormatError('Invalid JWT JSON segment');
  }
}

function safeEqual(left, right) {
  if (left.length !== right.length) {
    return false;
  }

  return crypto.timingSafeEqual(left, right);
}

class JWTService {
  constructor({ secret, issuer, audience, clockSkewSeconds = 30 }) {
    if (!Buffer.isBuffer(secret) || secret.length < 32) {
      throw new Error('HS256 secret must contain at least 32 bytes');
    }

    this.secret = secret;
    this.issuer = issuer;
    this.audience = audience;
    this.algorithm = 'HS256';
    this.clockSkewSeconds = clockSkewSeconds;
  }

  sign(input) {
    return crypto
      .createHmac('sha256', this.secret)
      .update(input)
      .digest();
  }

  issue({ subject, roles = [], expiresInSeconds = 900, extraClaims = {} }) {
    if (!subject || typeof subject !== 'string') {
      throw new TypeError('subject must be a non-empty string');
    }

    if (!Number.isInteger(expiresInSeconds) || expiresInSeconds <= 0) {
      throw new TypeError('expiresInSeconds must be a positive integer');
    }

    const now = Math.floor(Date.now() / 1000);

    const protectedClaims = new Set([
      'iss',
      'sub',
      'aud',
      'iat',
      'exp',
      'jti'
    ]);

    for (const claim of Object.keys(extraClaims)) {
      if (protectedClaims.has(claim)) {
        throw new TypeError(`Cannot overwrite registered claim: ${claim}`);
      }
    }

    const header = {
      alg: this.algorithm,
      typ: 'JWT'
    };

    const payload = {
      iss: this.issuer,
      sub: subject,
      aud: this.audience,
      iat: now,
      exp: now + expiresInSeconds,
      jti: crypto.randomBytes(18).toString('base64url'),
      roles: [...new Set(roles)].sort(),
      ...extraClaims
    };

    const encodedHeader = base64urlEncode(compactJson(header));
    const encodedPayload = base64urlEncode(compactJson(payload));
    const signingInput = `${encodedHeader}.${encodedPayload}`;
    const signature = base64urlEncode(this.sign(signingInput));

    return `${signingInput}.${signature}`;
  }

  verify(token) {
    if (typeof token !== 'string') {
      throw new JWTFormatError('Token must be a string');
    }

    const parts = token.split('.');

    if (parts.length !== 3) {
      throw new JWTFormatError('JWT must contain three segments');
    }

    const [encodedHeader, encodedPayload, encodedSignature] = parts;
    const header = parseJsonSegment(encodedHeader);
    const payload = parseJsonSegment(encodedPayload);

    // The accepted algorithm is fixed by server configuration. Never trust
    // an unverified "alg" value to choose a cryptographic implementation.
    if (header.typ !== 'JWT') {
      throw new JWTFormatError('Unexpected token type');
    }

    if (header.alg !== this.algorithm) {
      throw new JWTFormatError('Unexpected signing algorithm');
    }

    const expectedSignature = this.sign(
      `${encodedHeader}.${encodedPayload}`
    );
    const suppliedSignature = base64urlDecode(encodedSignature);

    if (!safeEqual(expectedSignature, suppliedSignature)) {
      throw new JWTSignatureError('Signature verification failed');
    }

    this.validateClaims(payload);

    return payload;
  }

  validateClaims(payload) {
    const requiredClaims = ['iss', 'sub', 'aud', 'iat', 'exp', 'jti'];

    for (const claim of requiredClaims) {
      if (!(claim in payload)) {
        throw new JWTClaimsError(`Missing claim: ${claim}`);
      }
    }

    if (payload.iss !== this.issuer) {
      throw new JWTClaimsError('Invalid issuer');
    }

    if (typeof payload.sub !== 'string' || payload.sub.length === 0) {
      throw new JWTClaimsError('Invalid subject');
    }

    const audienceMatches =
      payload.aud === this.audience ||
      (Array.isArray(payload.aud) && payload.aud.includes(this.audience));

    if (!audienceMatches) {
      throw new JWTClaimsError('Invalid audience');
    }

    if (!Number.isInteger(payload.iat) || !Number.isInteger(payload.exp)) {
      throw new JWTClaimsError('iat and exp must be integer timestamps');
    }

    const now = Math.floor(Date.now() / 1000);

    if (payload.iat > now + this.clockSkewSeconds) {
      throw new JWTClaimsError('Token issued in the future');
    }

    if (payload.exp <= now - this.clockSkewSeconds) {
      throw new JWTClaimsError('Token has expired');
    }

    if (typeof payload.jti !== 'string' || payload.jti.length === 0) {
      throw new JWTClaimsError('Invalid token identifier');
    }
  }
}

class AuthenticationGateway {
  constructor(jwtService) {
    this.jwtService = jwtService;
    this.revokedTokens = new Set();
  }

  revoke(jti) {
    this.revokedTokens.add(jti);
  }

  authorize(token, requiredScope) {
    const claims = this.jwtService.verify(token);

    if (this.revokedTokens.has(claims.jti)) {
      throw new JWTClaimsError('Token has been revoked');
    }

    const scopes = typeof claims.scope === 'string'
      ? claims.scope.split(/\s+/).filter(Boolean)
      : [];

    if (requiredScope && !scopes.includes(requiredScope)) {
      throw new Error(`Missing required scope: ${requiredScope}`);
    }

    return claims;
  }
}

async function simulateApiRequest(gateway, token, scope) {
  // Async behavior represents the boundary where a real API would perform
  // request parsing, token verification, authorization, and business work.
  await new Promise(resolve => setImmediate(resolve));

  try {
    const claims = gateway.authorize(token, scope);

    return {
      status: 200,
      subject: claims.sub,
      scopes: claims.scope
    };
  } catch (error) {
    return {
      status: 401,
      error: error.message
    };
  }
}

async function main() {
  const secret = crypto.randomBytes(32);

  const jwt = new JWTService({
    secret,
    issuer: 'repository-api',
    audience: 'repository-client'
  });

  const gateway = new AuthenticationGateway(jwt);

  const token = jwt.issue({
    subject: 'user-1042',
    roles: ['developer', 'reviewer'],
    expiresInSeconds: 300,
    extraClaims: {
      scope: 'repository:read repository:write',
      email_verified: true
    }
  });

  console.log('JWT:', token);

  const [headerSegment, payloadSegment, signatureSegment] = token.split('.');

  console.log('\nJWT segments:');
  console.log('Header:', headerSegment);
  console.log('Payload:', payloadSegment);
  console.log('Signature:', signatureSegment);

  console.log('\nDecoded header:');
  console.log(parseJsonSegment(headerSegment));

  console.log('\nDecoded payload:');
  console.log(parseJsonSegment(payloadSegment));

  const requestResult = await simulateApiRequest(
    gateway,
    token,
    'repository:write'
  );

  console.log('\nAuthorized API request:');
  console.log(requestResult);

  // Changing a signed claim without recomputing the signature invalidates
  // the token. This illustrates integrity protection, not confidentiality.
  const modifiedPayload = {
    ...parseJsonSegment(payloadSegment),
    roles: ['admin']
  };

  const modifiedPayloadSegment = base64urlEncode(
    compactJson(modifiedPayload)
  );

  const tamperedToken =
    `${headerSegment}.${modifiedPayloadSegment}.${signatureSegment}`;

  try {
    jwt.verify(tamperedToken);
  } catch (error) {
    console.log('\nTampering rejected:', error.message);
  }

  const verifiedClaims = jwt.verify(token);
  gateway.revoke(verifiedClaims.jti);

  const revokedResult = await simulateApiRequest(
    gateway,
    token,
    'repository:read'
  );

  console.log('\nRevoked token request:');
  console.log(revokedResult);

  for (const invalidToken of ['', 'not.a.jwt', 'one.two']) {
    try {
      jwt.verify(invalidToken);
    } catch (error) {
      console.log(`Invalid token rejected (${JSON.stringify(invalidToken)}): ${error.message}`);
    }
  }
}

main().catch(error => {
  console.error('Fatal error:', error.message);
  process.exitCode = 1;
});

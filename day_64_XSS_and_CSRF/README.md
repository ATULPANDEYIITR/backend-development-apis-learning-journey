# XSS and CSRF Security Engineering

## Scope

This project models defensive controls for two different classes of web application vulnerability:

- Cross-Site Scripting (XSS): untrusted content is interpreted as executable browser content.
- Cross-Site Request Forgery (CSRF): a browser is induced to send an authenticated request that the user did not intend.

The implementations distinguish input validation, output encoding, session management, request verification, cookie configuration, and browser cookie behavior. They use local demonstration data and standard language facilities rather than depending on an external web framework.

## Cross-Site Scripting

XSS occurs when an application places untrusted data into a browser response without applying the encoding required by its output context. A browser may interpret the data as markup, script, or another active content type.

XSS is not prevented reliably by removing a few characters from input. The appropriate control is context-aware output encoding, supported by safe templating and DOM APIs.

### Reflected XSS

Reflected XSS occurs when an application uses request data in a response without safe handling. A search term, query parameter, or other request value may be reflected immediately in the returned page.

The Python, JavaScript, C++17, and Java 17 implementations provide search-response functions that encode untrusted text before inserting it into an HTML text node. Their examples use markup-like input to demonstrate that the browser receives encoded characters rather than executable markup.

The encoding functions handle the following characters:

| Character | HTML representation |
|---|---|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&#39;` |

The encoders are intended for HTML text contexts. HTML text encoding is not a universal encoding method. JavaScript strings, CSS values, URL components, and HTML attributes have different parsing rules. Applications should avoid building executable contexts from untrusted strings and use context-aware output handling.

### Stored XSS

Stored XSS occurs when untrusted content is persisted and later displayed to users. Examples include comments, profile descriptions, support messages, and discussion posts.

The implementations deliberately store the original comment text and encode it when producing HTML. This separates data persistence from presentation:

1. Validate the input's type, length, and basic structural requirements.
2. Store the original text as untrusted data.
3. Retrieve it when constructing a response.
4. Encode it for the destination output context.
5. Return the encoded content to the browser.

Storing original text preserves its data meaning and allows different presentation formats to apply their own encoding rules. Encoding at storage time can cause double encoding or make the stored representation unsuitable for other output formats.

The PostgreSQL schema follows this separation. `user_comments.body` stores submitted text without claiming that it is safe HTML. The `untrusted_comment_inventory` view identifies records containing a less-than character as a review aid. This is not an XSS detector: markup characters alone do not establish whether content is executable or malicious.

### Content Security Policy

The examples provide a restrictive Content Security Policy response header. Its directives include:

| Directive | Purpose |
|---|---|
| `default-src 'self'` | Restricts resource loading to the application's origin by default |
| `object-src 'none'` | Blocks embedded plugin content |
| `base-uri 'self'` | Restricts the document base URL |
| `frame-ancestors 'none'` | Prevents the page from being embedded in frames |
| `form-action 'self'` | Restricts form submission destinations |

Content Security Policy is a defense-in-depth control. It does not replace output encoding, safe DOM operations, or secure application design.

## Cross-Site Request Forgery

CSRF exploits the browser's automatic inclusion of credentials, such as session cookies. An attacker attempts to cause a browser with an authenticated session to submit a request to a target application.

A typical risk scenario involves a user authenticated to an application visiting an untrusted website. That website attempts to make the browser submit a state-changing request to the authenticated application.

The request may carry the user's session cookie even though the user did not intend the operation.

### Synchronizer token pattern

The Python, JavaScript, C++17, and Java 17 programs demonstrate server-side CSRF token validation. The server creates a random token associated with an authenticated session. A legitimate application request supplies that token separately from the session cookie, usually through a form field or request header.

The server verifies:

- The session exists.
- The session has not expired.
- The session has not been revoked.
- The request uses a state-changing method.
- The request Origin matches the configured application origin.
- The submitted CSRF token matches the token associated with the session.

A missing or incorrect token, foreign Origin, expired session, revoked session, or unsupported method causes rejection.

The token must be unpredictable and protected from disclosure. The Python and JavaScript implementations use operating-system-backed cryptographic randomness. Java uses `SecureRandom`. The C++17 demonstration supplies fixed test data because the C++ standard library does not provide a portable cryptographic random-number generator. Its comparison routine is explicitly educational rather than a hardened constant-time cryptographic primitive.

The PostgreSQL implementation stores a SHA-256-sized digest of the CSRF token rather than the original token. The application must generate the token and calculate its digest using an appropriate cryptographic implementation. The database compares the submitted digest against the digest associated with the session.

### Origin validation

Origin validation checks the origin from which a browser request was initiated. The examples compare the supplied Origin with a configured HTTPS application origin.

A production implementation should use a trusted framework or carefully validated origin-parsing logic. It should not accept arbitrary origins based on substring matching, suffix matching, or unvalidated `Host` headers.

Origin validation is an additional CSRF control, not a replacement for a token-based defense where one is required. Applications must also account for legitimate deployments involving trusted subdomains, reverse proxies, and multiple application origins.

### Request methods

State-changing operations should use methods such as `POST`, `PUT`, `PATCH`, or `DELETE`, rather than `GET`.

A safe HTTP method should not perform an operation that changes account state, transfers funds, changes permissions, or modifies persistent data. Using `POST` alone does not prevent CSRF. The application must still validate the request's authorization and CSRF defenses.

## Cookies and Session Management

A session cookie allows a browser to present an identifier associated with server-side authentication state. The session identifier is a bearer credential: anyone who obtains a valid identifier may be able to act as the authenticated user.

The examples configure cookies with these attributes:

| Attribute | Security role |
|---|---|
| `Secure` | Restricts cookie transmission to secure transport |
| `HttpOnly` | Prevents ordinary client-side JavaScript from reading the cookie |
| `SameSite` | Controls cookie inclusion in cross-site requests |
| `Path` | Defines the cookie's URL path scope |
| `Max-Age` | Defines its maximum lifetime |

The `__Host-` cookie prefix is used in the examples. Browsers that enforce this prefix require a secure cookie, a root path, and no Domain attribute. It helps restrict the cookie to the host that set it.

`HttpOnly` reduces direct session-cookie theft through JavaScript access. It does not prevent XSS from performing actions through the victim's authenticated browser. An XSS vulnerability may still issue requests or read information available to the page.

The server must enforce session expiration and revocation. Cookie expiration alone is not sufficient because a copied cookie may remain usable unless the server rejects its associated session.

## SameSite Cookie Behavior

SameSite controls whether a browser includes a cookie in a request initiated from a different site.

| Setting | Typical cross-site behavior |
|---|---|
| `Strict` | Cookie is withheld from cross-site requests |
| `Lax` | Cookie is generally withheld from cross-site subrequests and unsafe navigations, but can accompany qualifying top-level safe navigations |
| `None` | Cookie can accompany cross-site requests and must use `Secure` |

The language implementations model common cases: same-site requests, cross-site top-level GET or HEAD navigation, and cross-site state-changing requests. Browser behavior contains additional details, and the models are not complete browser implementations.

SameSite is a useful layer of CSRF defense, but it should not be treated as a universal replacement for CSRF tokens and appropriate Origin validation. Same-site and same-origin are different concepts. Two subdomains can be same-site while still being different origins.

A cookie configured with `SameSite=None` is appropriate only when cross-site cookie use is required and the cookie is protected with `Secure`. It should not be selected merely to avoid application integration problems.

## Implementation Design

### Python

The Python script models a small web application using dataclasses, enums, dictionaries, and standard-library security features.

- `CookiePolicy` validates cookie attributes and creates a `Set-Cookie` header.
- `cookie_would_be_sent` evaluates common SameSite request cases.
- `SessionStore` issues unpredictable session identifiers and CSRF tokens.
- `WebSecurityLab` implements reflected rendering, stored comments, and CSRF verification.
- `response_security_headers` supplies defensive response headers.
- `run_demo` exercises valid requests and rejection cases with assertions.

The `html` module performs HTML escaping. The `hmac.compare_digest` function compares CSRF token values without ordinary early-exit string comparison. Session state is in memory, so the script is a learning model rather than a distributed session service.

### JavaScript

The JavaScript file uses Node.js standard-library modules and an event-driven design.

- `SecurityGateway` manages sessions and stored comments with `Map`.
- `EventEmitter` publishes session, comment, and CSRF audit events.
- `randomBytes` creates unpredictable token values.
- `timingSafeEqual` performs constant-time comparison for equal-length buffers.
- `CookiePolicy` validates and serializes cookie attributes.
- `cookieWillBeSent` models the common SameSite cases.

The comment submission method is asynchronous and verifies the session, method, Origin, and token before storing content. Rendering is a separate operation, allowing the stored representation to remain untrusted.

### C++17

The C++17 program uses explicit domain types and separate classes for cookie configuration, sessions, CSRF verification, and comment persistence.

`CookiePolicy` rejects invalid cookie configuration, while `BrowserRequestContext` represents the browser request characteristics needed for SameSite evaluation. `CsrfGuard` checks session state, expiration, request method, Origin, and token.

The HTML encoder handles text-node encoding. `CommentStore` retains raw content and encodes it when generating the response.

The comparison function is included to show that a security-sensitive equality check must avoid ordinary early-exit comparison. Standard C++ does not promise constant-time behavior, so production systems should use a vetted cryptographic library rather than rely on this demonstration routine. The program also uses fixed session and CSRF values only for repeatable local testing.

### Java 17

The Java implementation uses records for immutable domain data and concurrent collections for session and comment storage.

- `WebSession` represents authenticated session state.
- `CookiePolicy` validates cookie configuration.
- `CsrfPolicy` evaluates requests and returns a `SecurityDecision`.
- `SessionService` issues tokens using `SecureRandom`.
- `CommentRepository` stores untrusted comment text.
- `HtmlOutputEncoder` encodes content at the response boundary.
- `WebSecurityService` coordinates the application workflow.

`MessageDigest.isEqual` is used for token comparison. The policy evaluation returns an explicit reason for rejection, which makes decisions easier to audit and test.

The example is single-process in-memory application logic. A production enterprise service would need durable or shared session storage, centralized configuration, appropriate key and secret management, request-level logging, and integration with the application's authentication framework.

### PostgreSQL

The SQL script models the data and audit portions of a web security workflow.

| Database object | Responsibility |
|---|---|
| `app_users` | Application identities and roles |
| `app_sessions` | Session ownership, token digests, expiry, revocation, and expected Origin |
| `cookie_policies` | Approved cookie configuration |
| `user_comments` | Persisted untrusted user content |
| `security_events` | Security decisions and application audit events |
| `csrf_request_allowed` | Session, Origin, and token-digest validation |
| `cookie_would_be_sent` | SameSite policy evaluation |
| `try_add_comment` | Validates a comment request before persistence |
| `enforce_comment_session` | Ensures the comment author owns a valid session |
| `audit_comment_insert` | Records successful comment creation |
| `revoke_expired_sessions` | Revokes expired sessions and records events |
| Reporting views | Expose active sessions, moderation work, untrusted content, and event counts |

The `try_add_comment` function returns a rejection decision and writes an audit event instead of raising an exception for an invalid CSRF request. This allows the caller's transaction to commit the rejection record. The comment trigger provides a separate integrity check to prevent a comment from being associated with another user's session.

The SQL database does not render HTML or create browser cookies. Those responsibilities remain with the application. Database constraints and functions protect stored state and support reporting; they do not replace secure HTTP response construction.

## Security Workflow

The combined application workflow is:

1. The server authenticates a user and creates a session.
2. The server generates a random CSRF token associated with that session.
3. The browser receives a protected session cookie.
4. A state-changing request includes the CSRF token separately from the cookie.
5. The server checks the session, request method, Origin, and CSRF token.
6. The application validates basic input constraints and stores accepted content as untrusted data.
7. When content is returned to a browser, the application encodes it for the output context.
8. The server applies appropriate response headers and records relevant security events.
9. Expired or revoked sessions are rejected.

This workflow addresses two independent trust boundaries. CSRF checks whether a state-changing request was intentionally initiated through the application's expected interaction flow. XSS defenses ensure that stored or reflected data is not interpreted as executable browser content. Passing one set of checks does not establish that the other vulnerability class has been prevented.

## Edge Cases and Operational Limits

The implementations include checks for empty input, excessive input length, null characters, invalid cookie values, insecure `SameSite=None` configuration, missing sessions, expired sessions, revoked sessions, wrong Origins, incorrect tokens, and unexpected HTTP methods.

Several additional production considerations remain important:

- Use TLS throughout the authenticated application.
- Rotate session identifiers after authentication and privilege changes.
- Revoke sessions on logout and relevant account-security events.
- Keep session identifiers inaccessible to ordinary JavaScript.
- Do not place CSRF tokens in URLs or expose them through logs.
- Use framework-supported CSRF protection where available.
- Apply output encoding at every browser response boundary.
- Prefer safe DOM APIs such as `textContent` rather than inserting untrusted strings through `innerHTML`.
- Validate redirect destinations and URL schemes separately from HTML text.
- Configure Content Security Policy according to the application's actual scripts, styles, and resource requirements.
- Treat audit records as sensitive operational data and restrict access to them.
- Apply appropriate retention, indexing, and access-control policies to session and security-event tables.

The code examples demonstrate security mechanisms and their interactions. They do not implement a complete HTTP server, a production identity provider, a full browser cookie engine, or a complete HTML sanitizer.

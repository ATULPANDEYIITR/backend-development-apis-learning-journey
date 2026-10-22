# Password Security: Hashing, Salting, Brute-Force Resistance, and Secure Password Storage

## Scope

This project models password security as an authentication and credential-storage problem.

The central rule is simple:

> A password database should contain password-derived values, not recoverable plaintext passwords.

The five implementations use different mechanisms while preserving the same security objectives:

| Implementation | Primary mechanism | Security perspective |
|---|---|---|
| Python | PBKDF2-HMAC-SHA256 | Explicit password-derivation workflow |
| JavaScript | Node.js `crypto.scrypt` | Asynchronous, memory-hard password derivation |
| C++17 | PBKDF2-HMAC-SHA256 with self-contained SHA-256 | Low-level derivation and constant-time verification |
| Java 17 | `PBKDF2WithHmacSHA256` | Enterprise-oriented policy and authentication states |
| PostgreSQL | `pgcrypto` bcrypt | Database-enforced password hashing and authentication workflow |

The implementations deliberately distinguish four related mechanisms:

**Hashing** transforms a password into a derived value that is computationally difficult to reverse.

**Salting** adds unique random data to each password before derivation so identical passwords do not produce identical stored values.

**Brute-force resistance** makes each password guess computationally expensive, increasing the cost of offline attacks.

**Secure password storage** combines a password-specific derivation function, a unique salt, appropriate work parameters, protected storage, verification controls, and operational defenses.

---

## Password hashing

A conventional cryptographic hash such as SHA-256 is fast by design. That property is useful for integrity checks but undesirable for password storage.

An attacker who obtains a database containing fast password hashes can test a large number of candidate passwords quickly.

Password storage therefore uses dedicated password-based key derivation functions or password hashing algorithms.

The project uses:

- PBKDF2-HMAC-SHA256 in Python
- scrypt in JavaScript
- PBKDF2-HMAC-SHA256 in C++17
- PBKDF2-HMAC-SHA256 in Java
- bcrypt through PostgreSQL `pgcrypto`

A simplified derivation model is:

`derived_key = KDF(password, salt, work_factor, parameters)`

The stored record needs enough information to reproduce the derivation during authentication.

---

## Salting

A salt is random, non-secret data associated with a password.

A secure record can conceptually be represented as:

`algorithm | parameters | salt | derived_password_value`

The salt does not need to be hidden. Its purpose is uniqueness rather than secrecy.

For example, two accounts could use the same password:

`CorrectHorseBatteryStaple!2026`

Without salts, a deterministic hash or derived value would be identical for both accounts.

With independent random salts:

`KDF(password, salt_A) != KDF(password, salt_B)`

The Python, JavaScript, Java, and C++ implementations explicitly generate random salts. PostgreSQL's `gen_salt()` performs the corresponding database-side operation for bcrypt.

The examples also hash the same password twice and compare the resulting salts and derived values. This demonstrates why a password database should not contain a single global salt shared by every account.

---

## Brute-force resistance

A password attacker may perform an offline attack after obtaining password records.

The attacker repeatedly evaluates:

`candidate password -> password derivation -> comparison`

The security objective is not to make guessing mathematically impossible. It is to make each guess sufficiently expensive.

### PBKDF2

PBKDF2 repeatedly applies a pseudorandom function to increase computation cost.

The Python implementation uses 600,000 PBKDF2-HMAC-SHA256 iterations and a 256-bit derived value.

The Java implementation uses the same conceptual construction through Java's `PBKDF2WithHmacSHA256` implementation.

The C++ implementation explicitly implements HMAC-SHA256 and the PBKDF2 iteration process to expose the underlying construction.

### scrypt

The JavaScript implementation uses Node.js `crypto.scrypt`.

Unlike a purely CPU-focused derivation, scrypt deliberately consumes memory as well as computation. This makes large-scale password guessing more resource-intensive and reduces the advantage of highly parallel computation.

The example uses a cost parameter of `2^15`, block size `8`, and parallelization value `1`.

### bcrypt

The PostgreSQL implementation uses bcrypt through `pgcrypto`.

The bcrypt work factor controls the computational cost of password verification. The sample production policy uses cost `12`, while the legacy record uses cost `10` to demonstrate migration detection.

The exact production work factor should be calibrated against the hardware and authentication workload rather than selected solely from a fixed example.

---

## Secure password storage model

A useful password record contains:

| Field | Purpose |
|---|---|
| Algorithm | Identifies the password derivation mechanism |
| Salt | Makes each password derivation unique |
| Work factor | Controls computational cost |
| Derived value | Stored representation used for verification |
| Version or policy | Allows future parameter upgrades |

The password itself should not be present in the record.

The storage layer should also restrict access to password records. Hashing does not make a database harmless after compromise. Strong password derivation reduces the attacker's rate of guessing, but weak user passwords can still eventually be recovered.

---

## Python implementation

The Python script models password storage with a `PasswordRecord` dataclass and a `PasswordSecurity` service.

`hash_password()`:

- validates the password
- generates a cryptographically secure random salt
- derives a 256-bit value using PBKDF2-HMAC-SHA256
- stores the salt and derived value using Base64
- records the derivation parameters

`verify_password()`:

- validates the candidate
- decodes the stored salt and derived value
- repeats the same derivation
- uses `hmac.compare_digest()` for comparison

The constant-time comparison is important because ordinary equality operations are not the preferred primitive for comparing authentication secrets.

`needs_rehash()` provides a migration mechanism. When a policy becomes stronger, an existing password can be re-derived after the user successfully authenticates.

The Python example also demonstrates that identical passwords receive different salts and therefore different stored derived values.

---

## JavaScript implementation

The JavaScript implementation uses Node.js's built-in `crypto` module.

The important distinction from the Python implementation is the asynchronous password derivation model.

`scrypt()` is computationally expensive. The example exposes it through a Promise-based interface so authentication work can participate in an event-driven Node.js application without being represented as a synchronous utility call.

The password record contains:

- algorithm
- salt
- scrypt cost
- block size
- parallelization
- derived value

`crypto.randomBytes()` supplies the salt.

`crypto.timingSafeEqual()` performs the final comparison after both values have been derived.

The `authenticate()` function separates authentication outcome from policy state. A valid password can therefore produce an authentication result that also indicates whether the stored parameters should be upgraded.

This is useful when migrating from an older password policy.

---

## C++17 implementation

The C++ program treats password security as a low-level cryptographic processing pipeline.

It contains:

- SHA-256 compression
- HMAC-SHA256
- PBKDF2
- random salt generation
- password verification
- constant-time byte comparison
- password-record validation

The SHA-256 implementation is included because standard C++17 does not provide a general-purpose cryptographic hash API.

The PBKDF2 implementation derives a 256-bit value using one PBKDF2 block because SHA-256 produces a 256-bit HMAC output.

The authentication comparison does not stop at the first differing byte. It accumulates byte differences and returns the final result after processing the complete value.

This is a deliberately low-level implementation for studying the mechanism. A production C++ service should normally use a well-maintained, audited cryptographic library rather than maintaining application-level cryptographic primitives.

---

## Java 17 implementation

The Java implementation represents password handling as an enterprise service.

`PasswordRecord` is an immutable record containing the algorithm, salt, derived value, iteration count, and key length.

`PasswordPolicy` separates validation policy from password derivation.

`PasswordService` owns the workflow:

`validate -> generate salt -> derive -> store`

Authentication follows:

`validate -> retrieve parameters -> derive -> constant-time comparison -> policy evaluation`

The `AuthenticationState` enum explicitly represents:

- `AUTHENTICATED`
- `INVALID_CREDENTIALS`
- `REHASH_REQUIRED`

The third state is important for credential migration. Authentication and policy compliance are related but not identical decisions.

The Java implementation uses `SecureRandom` for salt generation, `PBEKeySpec` for password derivation, and Java's cryptographic comparison support for the final derived-value comparison.

---

## PostgreSQL implementation

The PostgreSQL implementation treats password storage as part of a relational authentication system.

The schema separates:

- application users
- password policies
- password records
- authentication events

The relationship is:

`application_users -> user_passwords -> password_policies`

Authentication events reference the user when the username exists but retain the attempted username for unknown-user attempts.

The `user_passwords` table does not contain a plaintext password column.

The password hash is generated using:

`crypt(password, gen_salt('bf', work_factor))`

The `bf` identifier selects bcrypt in PostgreSQL's `pgcrypto` extension.

Because bcrypt stores the salt and cost information inside its encoded password representation, `crypt(candidate, stored_hash)` can reproduce the appropriate derivation during verification.

---

## Database constraints

The PostgreSQL schema uses database-level constraints rather than relying entirely on application validation.

Examples include:

- unique usernames
- unique email addresses
- valid account states
- non-negative failed-attempt counters
- valid password-policy lengths
- supported password algorithms
- positive work factors
- mandatory password hashes

These constraints prevent invalid credential-management state from entering the database through an alternate application path.

---

## Authentication failure handling

The PostgreSQL function `authenticate_user()` implements a complete authentication transaction at the database layer.

The workflow is:

`username lookup`

→ `account-status validation`

→ `lockout validation`

→ `password-hash retrieval`

→ `bcrypt verification`

→ `success or failure recording`

→ `failure-counter update`

The example locks an account after five failed attempts and establishes a temporary lock period.

This is an application-specific example rather than a universal security policy. Real systems should calibrate lockout behavior carefully because aggressive lockouts can themselves become a denial-of-service mechanism.

Authentication failures are recorded in `password_authentication_events`, allowing operational analysis without storing the submitted password.

---

## Password rotation and rehashing

Password security policies change.

A service may increase:

- PBKDF2 iteration count
- bcrypt work factor
- scrypt cost
- derived-key size
- password policy requirements

Existing passwords cannot normally be rehashed without knowing the plaintext password.

The common migration pattern is:

`user authenticates successfully`

→ `verify existing password`

→ `detect obsolete parameters`

→ `derive using the new policy`

→ `replace stored record`

The Python and JavaScript examples expose `needs_rehash()` behavior. The Java implementation represents rehashing as an explicit authentication state. The PostgreSQL data model records the password policy associated with each stored password so weaker records can be identified.

---

## Edge cases and failure conditions

### Empty passwords

All application implementations reject empty passwords.

The PostgreSQL password function also returns failure when required authentication inputs are missing.

### Excessively large passwords

Python, JavaScript, and Java enforce an input-size boundary. This prevents an application from accepting arbitrarily large authentication inputs and consuming disproportionate resources.

A maximum length should be selected carefully. Password managers can generate long credentials, so arbitrary small limits can damage usability and security.

### Incorrect passwords

An incorrect candidate is independently derived and compared with the stored derived value.

The plaintext candidate is not written to authentication records.

### Unknown users

The PostgreSQL authentication function records an unknown-username attempt without creating a user record.

Production systems should also consider response uniformity so that authentication behavior does not reveal whether a username exists.

### Compromised records

The PostgreSQL schema includes a `compromised` flag. A password record marked compromised cannot be used by the authentication function.

This models credential invalidation after a security incident.

---

## Security boundaries

Password hashing is not encryption.

Encryption is designed so authorized parties can recover the original plaintext using a key.

Password hashing and password derivation are designed so the stored representation can be verified without recovering the original password.

The intended flow is:

`password`

→ `salt + password derivation`

→ `stored derived value`

and during login:

`candidate password`

→ `same salt + same derivation parameters`

→ `candidate derived value`

→ `constant-time comparison`

The system does not need to recover the original password.

---

## Security properties and limitations

### What salting solves

Salting prevents identical passwords from producing identical stored derived values when independent salts are used.

It also makes precomputed tables based on a fixed salt ineffective against the database as a whole.

### What salting does not solve

A salt does not make a weak password strong.

An attacker who possesses a password record can still try:

`123456`

`password`

`qwerty`

and other candidates.

The purpose of the password KDF is to make each such attempt expensive.

### What work factors solve

Work factors reduce the number of password guesses an attacker can perform per unit of computational resources.

### What work factors do not solve

A sufficiently weak password may remain guessable even when a strong KDF is used.

Password derivation must therefore be combined with sensible password policies, multi-factor authentication where appropriate, rate limiting, account protection, monitoring, and restricted access to credential databases.

---

## Comparison of derivation mechanisms

| Property | PBKDF2 | bcrypt | scrypt |
|---|---|---|---|
| Repeated computation | Yes | Yes | Yes |
| Random salt | Required | Built into password format | Required |
| Memory-hard design | No | Limited | Yes |
| Configurable cost | Iterations | Work factor | Cost parameters |
| Python example | Yes | No | No |
| JavaScript example | No | No | Yes |
| Java example | Yes | No | No |
| PostgreSQL example | No | Yes | No |

The algorithms should not be compared only by their numeric cost parameters. Their parameters represent different computational models and must be calibrated independently.

---

## Operational workflow

A production authentication system should conceptually maintain this separation:

`Credential input`

→ `Input validation`

→ `Credential lookup`

→ `Password derivation`

→ `Constant-time verification`

→ `Authentication decision`

→ `Audit event`

→ `Session or token issuance`

Password records should be accessible to as few components and database roles as practical.

Authentication logs should contain operational information such as timestamps, user identifiers, result states, and source metadata when appropriate, but never plaintext passwords or password-derived secrets unnecessarily.

---

## Performance considerations

Password derivation is intentionally expensive.

For ordinary application traffic, this means authentication capacity must be measured rather than assuming that password verification has negligible cost.

Increasing the work factor improves resistance to offline guessing but increases legitimate login cost as well.

A practical system should benchmark authentication on its actual deployment hardware and choose parameters that provide strong resistance while keeping legitimate authentication within acceptable latency and capacity limits.

The asynchronous JavaScript implementation is particularly relevant to event-driven applications because expensive password derivation should be handled without turning the authentication path into unnecessary synchronous application work.

---

## Repository contents

| File | Implemented capability |
|---|---|
| `password_security.py` | Salt generation, PBKDF2 hashing, constant-time verification, rehash detection, validation |
| `password_security.js` | Node.js scrypt, asynchronous derivation, timing-safe comparison, authentication state |
| `password_security.cpp` | SHA-256, HMAC, PBKDF2, random salts, constant-time verification |
| `PasswordSecurityDemo.java` | Java 17 PBKDF2 service, immutable records, policies, authentication states |
| `password_security.sql` | PostgreSQL users, policies, password hashes, authentication events, bcrypt verification, lockout, reporting |

The five implementations address the same password-security problem from different system layers rather than presenting the same source code in different languages.

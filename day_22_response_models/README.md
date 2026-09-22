# Substitution Ciphers

## Topic introduction

A substitution cipher is a classical cryptographic technique in which each plaintext symbol is replaced by another symbol according to a predefined mapping. In the simplest case, the symbols are letters of an alphabet. The original readable message is called the **plaintext**, the transformed message is called the **ciphertext**, and the rule or secret information controlling the transformation is called the **key**.

The central idea is simple: if plaintext letter `A` is mapped to ciphertext letter `D`, every occurrence of `A` is replaced by `D`. A corresponding inverse mapping is required for decryption. A valid general monoalphabetic substitution therefore needs to be a one-to-one mapping, or permutation, of the alphabet.

Substitution ciphers are historically important because they introduce several concepts that remain fundamental to cryptography: keys, encryption, decryption, modular arithmetic, permutations, key spaces, statistical leakage, cryptanalysis, and the difference between a transformation being mathematically reversible and being secure against an attacker.

The implementations in this study use the English alphabet `A-Z`. Nonalphabetic characters are generally preserved, and case is preserved where practical. This makes the examples easier to read while allowing the cryptographic transformation to focus on the alphabetic symbols.

## Fundamental terminology

### Plaintext

Plaintext is the original information before encryption. For example:

`ATTACK AT DAWN`

is plaintext.

### Ciphertext

Ciphertext is the transformed representation produced by an encryption algorithm and a key.

For a Caesar shift of three:

`ATTACK`

becomes:

`DWWDFN`

### Encryption

Encryption converts plaintext into ciphertext.

For a Caesar cipher, the transformation can be represented as:

`C = (P + k) mod 26`

where `P` is the plaintext letter number, `C` is the ciphertext letter number, and `k` is the shift.

### Decryption

Decryption reverses encryption.

For a Caesar cipher:

`P = (C - k) mod 26`

A correct implementation must satisfy the round-trip property:

`decrypt(encrypt(plaintext, key), key) = plaintext`

### Key

A key controls the transformation. Different cipher families use keys differently.

A Caesar cipher uses a shift value. An affine cipher uses two parameters. A general monoalphabetic substitution uses a permutation of the alphabet.

### Alphabet

The implementations use:

`ABCDEFGHIJKLMNOPQRSTUVWXYZ`

Each letter can be represented numerically as:

`A = 0, B = 1, ..., Z = 25`

This numerical representation makes modular arithmetic straightforward.

## Core principle of substitution

A substitution cipher defines a mapping:

`plaintext symbol -> ciphertext symbol`

For a general monoalphabetic substitution, the mapping must be bijective. Every plaintext symbol has exactly one ciphertext representation, and every ciphertext symbol corresponds to exactly one plaintext symbol.

For example, a key such as:

`QWERTYUIOPASDFGHJKLZXCVBNM`

means:

`A -> Q`

`B -> W`

`C -> E`

and so forth.

The inverse mapping is required for decryption:

`Q -> A`

`W -> B`

`E -> C`

A key containing duplicate ciphertext letters is invalid for ordinary reversible monoalphabetic substitution because two plaintext letters would map to the same ciphertext symbol.

## Caesar cipher

The Caesar cipher is one of the simplest substitution ciphers. It shifts every alphabetic symbol by the same fixed amount.

With a shift of three:

`A -> D`

`B -> E`

`C -> F`

and:

`X -> A`

`Y -> B`

`Z -> C`

The wraparound occurs because the alphabet is treated modulo 26.

The Python implementation uses `caesar_encrypt()` and `caesar_decrypt()`. The JavaScript implementation provides equivalent functions, while the C++ implementation incorporates the Caesar mechanism into a larger case study.

An important implementation detail is normalization of the shift. A shift of `29` is equivalent to a shift of `3`, because:

`29 mod 26 = 3`

Negative shifts are also supported.

The implementations preserve punctuation and spaces. Therefore:

`Attack at Dawn!`

remains structurally similar after encryption, rather than becoming a sequence containing only alphabetic characters.

## General monoalphabetic substitution

A general substitution cipher replaces every plaintext letter using an arbitrary permutation of the alphabet.

A key must therefore:

- Contain exactly 26 letters.
- Contain only alphabetic symbols from `A-Z`.
- Contain every alphabetic symbol exactly once.

The Python implementation explicitly validates these conditions through `validate_substitution_key()`.

The JavaScript implementation performs equivalent validation using `Set` and string operations.

The C++ implementation uses an `array<bool, 26>` to efficiently detect duplicate symbols.

The distinction between a substitution key and a shift is important. A Caesar cipher has only 26 possible shifts, while a general monoalphabetic substitution can theoretically use:

`26!`

different permutations.

This produces a vastly larger mathematical key space, but a large key space alone does not guarantee security.

## Atbash

Atbash is a fixed substitution in which the alphabet is reversed:

`A <-> Z`

`B <-> Y`

`C <-> X`

and so forth.

Atbash is self-inverse. Applying it twice returns the original message.

The implementations therefore do not need a separate mathematical decryption algorithm. The same transformation can be applied twice:

`Atbash(Atbash(message)) = message`

This demonstrates an important distinction between encryption algorithms that require an explicit inverse operation and transformations that are their own inverses.

## Keyword substitution

A keyword substitution cipher can construct a substitution alphabet from a keyword.

For example, the keyword:

`CRYPTOGRAPHY`

contains repeated letters. The repeated symbols are removed while preserving their first occurrence. The remaining unused alphabet letters are then appended.

The resulting sequence becomes a substitution alphabet.

This approach demonstrates how a human-readable keyword can be converted into a full substitution key.

The implementations use `keyword_substitution_key()` in Python and JavaScript and an equivalent function in C++.

Keyword construction must be deterministic if the same key is expected to produce the same ciphertext.

## Affine cipher

The affine cipher combines multiplication and addition in modular arithmetic.

Encryption is:

`C = (aP + b) mod 26`

where:

- `P` is the plaintext number.
- `C` is the ciphertext number.
- `a` is the multiplicative parameter.
- `b` is the additive parameter.

The critical mathematical restriction is:

`gcd(a, 26) = 1`

This condition guarantees that `a` has a modular inverse modulo 26.

Decryption is:

`P = a^-1(C - b) mod 26`

where `a^-1` is the modular multiplicative inverse.

The Python, JavaScript, and C++ implementations explicitly reject invalid affine multipliers.

For example, `a = 5` is valid because:

`gcd(5, 26) = 1`

while `a = 13` is invalid because:

`gcd(13, 26) = 13`

There is no multiplicative inverse of 13 modulo 26, so a reversible affine transformation cannot be constructed with that parameter.

## Modular arithmetic

Modular arithmetic is central to classical substitution algorithms.

The `%` operator performs the basic remainder operation in all three implementations.

A common implementation issue occurs with negative values. Some programming languages return a negative remainder for negative operands. The implementations therefore normalize values when necessary using a form equivalent to:

`((value % modulus) + modulus) % modulus`

This ensures a result in the desired interval.

The modular inverse is calculated using the extended Euclidean algorithm. The inverse exists when the number and modulus are coprime.

For example:

`5^-1 mod 26 = 21`

because:

`5 × 21 = 105`

and:

`105 mod 26 = 1`

## Python implementation

The Python program is designed as a comprehensive study file rather than a minimal encryption utility.

It begins with fundamental alphabet manipulation and modular arithmetic and progressively introduces larger abstractions.

The `letter_to_number()` and `number_to_letter()` functions establish the numerical representation of the alphabet.

The Caesar implementation demonstrates the simplest substitution mechanism. The general substitution implementation then introduces a complete 26-character key and creates both encryption and decryption mappings.

The `SubstitutionCipher` dataclass provides an object-oriented interface. It validates the key during initialization and exposes reusable `encrypt()` and `decrypt()` methods.

The Python implementation also demonstrates keyword substitution, Atbash, affine encryption, random key generation, frequency analysis, index of coincidence, text scoring, known-plaintext relationships, structural word patterns, benchmarking, and self-tests.

A major design principle is separation of concerns. Key validation, transformation, frequency analysis, cryptanalysis, demonstrations, and testing are implemented as separate functions rather than placing every operation inside one large procedure.

## JavaScript implementation

The JavaScript implementation complements the Python implementation by emphasizing application-level behavior and JavaScript-specific mechanisms.

The `Map` object is used for substitution mappings. This is useful because it provides direct association between plaintext and ciphertext symbols without requiring repeated searches.

The `Set` object is used to detect duplicate key characters efficiently.

The JavaScript implementation also introduces the `SubstitutionCipher` class, which encapsulates the validated key and its forward and reverse mappings.

The implementation uses JavaScript string iteration to process characters while preserving nonalphabetic content.

An asynchronous example is included through `asynchronousEncryption()`. The substitution algorithm itself does not require asynchronous execution, but the example demonstrates how a cryptographic transformation could participate in an event-driven application architecture.

The JavaScript program also uses `process.hrtime.bigint()` for high-resolution performance measurement. This is appropriate for Node.js performance experiments because it provides much finer timing resolution than ordinary wall-clock timing functions.

A deterministic pseudo-random generator is used for reproducible educational examples. It is explicitly not intended to provide cryptographically secure randomness.

## C++ case study

The C++ implementation models an industry-style message-processing scenario called a message router.

The system contains a `SubstitutionCipher` class responsible for validating a substitution key and constructing encryption and decryption mappings.

A `MessageRouter` class represents an application layer that receives messages, encrypts them, and records processing metadata.

This separation is intentional. The routing layer should not need to understand the mathematical details of every letter transformation. It delegates encryption to the cipher abstraction.

Each processed message records:

- Sender identifier.
- Plaintext.
- Ciphertext.
- Character count.
- Processing time.

This provides a practical example of how an algorithm can be integrated into a larger application rather than being implemented as an isolated demonstration.

The C++ implementation also includes Caesar encryption, affine encryption, Atbash, keyword substitution, frequency analysis, index of coincidence, Caesar cryptanalysis, validation, performance testing, modular inverse calculation, and self-tests.

## C++ data structures

Several standard library data structures are appropriate for the problem.

The `array<char, 26>` structure is used for substitution maps because the alphabet has a fixed size. Direct array indexing makes the transformation efficient.

The `array<bool, 26>` structure is used for key validation. Each position corresponds to an alphabet symbol and records whether it has already appeared.

The `vector<Candidate>` structure stores possible Caesar decryption candidates during brute-force analysis.

The `vector<MessageRecord>` structure stores message-processing records in the message router.

These choices illustrate an important implementation principle: data structures should match the known constraints of the problem.

Since the alphabet is fixed at 26 symbols, an array provides simple constant-time access and avoids unnecessary dynamic lookup structures.

## Frequency analysis

Frequency analysis is one of the most important cryptanalytic techniques associated with monoalphabetic substitution.

Natural languages do not use letters uniformly. In English, letters such as `E`, `T`, `A`, and `O` occur substantially more often than letters such as `Q`, `X`, and `Z`.

A monoalphabetic substitution changes the identities of the letters but preserves their frequencies.

If plaintext `E` is replaced by ciphertext `Q`, every occurrence of `E` becomes `Q`. Therefore, a sufficiently long ciphertext still reveals the statistical frequency of the original plaintext alphabet under a renamed symbol.

The implementations calculate letter counts and percentages.

This demonstrates a key security principle:

**Reversibility is not the same as secrecy.**

A cipher can be mathematically reversible while still leaking enough statistical structure for an attacker to recover its plaintext.

## Chi-squared analysis

The Python, JavaScript, and C++ implementations use chi-squared scoring to evaluate Caesar candidates.

The method compares observed letter counts with expected English frequencies.

The general form is:

`χ² = Σ((observed - expected)² / expected)`

A smaller value means the observed distribution is closer to the expected English distribution.

This works particularly well for Caesar ciphers because every candidate key produces a complete candidate plaintext using a simple alphabet rotation.

The technique becomes much less sufficient for arbitrary monoalphabetic substitution because the attacker must determine a complete permutation rather than merely choose one of 26 shifts.

## Caesar cryptanalysis

A Caesar cipher has only 26 possible keys.

Therefore, an attacker can simply decrypt the ciphertext with every possible key and rank the resulting plaintext candidates.

The implementations use frequency scoring to automate this process.

This is an example of a brute-force attack combined with statistical analysis.

The computational cost is:

`O(26n)`

where `n` is the message length.

Because the alphabet size is fixed, 26 is effectively a constant for practical complexity analysis, making the process effectively linear in message length.

The important lesson is that a small key space makes exhaustive search straightforward.

## Index of coincidence

The index of coincidence measures how likely two randomly selected symbols are to be the same.

For a text containing `N` symbols and symbol frequencies `f_i`, the calculation is:

`IC = Σ f_i(f_i - 1) / N(N - 1)`

It provides a statistical view of the distribution of symbols.

English text tends to have a higher index of coincidence than uniformly random text because English letters are not uniformly distributed.

Monoalphabetic substitution does not eliminate this statistical structure because it merely renames the symbols.

The implementations calculate the index of coincidence for educational comparison between different types of text.

## Pattern preservation

Substitution ciphers preserve repeated-letter patterns.

For example, if a plaintext word has the structural pattern:

`0 1 2 2 3`

then its ciphertext representation under a one-to-one substitution will have the same equality pattern.

This provides another cryptanalytic clue.

Word length, repeated symbols, punctuation, and spaces can also remain visible when a conventional substitution implementation preserves formatting.

This is why simply increasing the number of possible substitution keys does not automatically solve the cryptanalytic problem.

## Known-plaintext relationships

A known-plaintext situation occurs when an attacker knows or strongly suspects some plaintext and its corresponding ciphertext.

If the plaintext contains:

`A`

and the ciphertext contains:

`Q`

at the corresponding position, the attacker obtains:

`A -> Q`

A sufficiently large collection of such relationships can reveal substantial portions of the substitution alphabet.

The Python implementation includes an explicit known-plaintext demonstration.

This illustrates why encryption systems must be designed under the assumption that attackers may know some plaintext and may have access to multiple ciphertext samples.

## Edge cases

The implementations deliberately handle several edge cases.

An empty message should not cause an error.

A one-character message should still transform correctly.

A message containing only numbers and punctuation should remain unchanged.

Mixed uppercase and lowercase text should preserve its case pattern.

A Caesar shift larger than 26 should wrap correctly.

Negative Caesar shifts should also wrap correctly.

Invalid substitution keys should be rejected rather than silently accepted.

Affine keys with a multiplier that is not coprime with 26 must be rejected because their transformation cannot be inverted.

These cases are important because cryptographic software must define behavior for invalid and unusual inputs rather than relying on idealized examples.

## Common mistakes

### Using duplicate symbols in a substitution key

A key such as:

`AAAAAAAAAAAAAAAAAAAAAAAAAA`

does not define a reversible substitution because multiple plaintext letters would map to the same ciphertext symbol.

### Forgetting modular wraparound

A shift applied to `Z` must wrap back to the beginning of the alphabet.

### Using an invalid affine multiplier

The affine multiplier must be coprime with 26.

### Forgetting the modular inverse

Affine decryption requires the inverse of the multiplicative parameter.

### Modifying punctuation unintentionally

A practical implementation should explicitly define whether spaces and punctuation are preserved or transformed.

### Assuming a large key space means strong security

A general substitution cipher has `26!` possible permutations, but statistical characteristics of natural language remain visible.

### Treating frequency analysis as universally reliable

Frequency analysis requires sufficient ciphertext. Very short messages can produce distributions that differ significantly from typical English frequencies.

### Using educational random generation as cryptographic randomness

The deterministic random generator in the JavaScript implementation is included only for reproducible demonstrations. It must not be interpreted as a secure key-generation mechanism.

## Important distinctions

### Caesar versus general substitution

Caesar uses a single shift parameter.

General substitution uses a complete permutation of the alphabet.

### Atbash versus keyed substitution

Atbash uses a fixed reversed alphabet. There is no independent secret key.

A general substitution cipher can use a secret permutation.

### Affine versus Caesar

Caesar can be represented as a special case of affine transformation with:

`a = 1`

and:

`b = shift`

Affine therefore generalizes Caesar by introducing a multiplicative component.

### Key space versus effective security

Key space describes how many possible keys exist.

Security depends on much more than key-space size. Structural leakage, statistical properties, implementation weaknesses, key management, and attack models all matter.

## Complexity considerations

For a message containing `n` characters, ordinary substitution encryption requires one lookup per alphabetic character.

Therefore:

- Caesar encryption: `O(n)`
- Caesar decryption: `O(n)`
- General substitution encryption: `O(n)`
- General substitution decryption: `O(n)`
- Frequency analysis: `O(n)`
- Index of coincidence: `O(n)`
- Caesar brute-force analysis: `O(26n)`

Since 26 is constant, Caesar brute force is effectively linear in message length.

The substitution key itself always contains only 26 symbols, so key validation and map construction are effectively constant-time with respect to message size.

The primary memory requirement for transformation is the output message, giving approximately `O(n)` additional storage when a new string is constructed.

## Security considerations

Classical substitution ciphers should not be used to protect modern confidential information.

Their main educational value is that they expose fundamental cryptographic concepts without the complexity of modern cryptographic systems.

A monoalphabetic substitution preserves important information about the plaintext:

- Letter-frequency relationships.
- Repeated-letter patterns.
- Word lengths.
- Word boundaries when spaces are preserved.
- Punctuation positions when punctuation is preserved.
- Language-level statistical structure.

These properties make classical substitution vulnerable to cryptanalysis.

Modern encryption systems use substantially different designs, including mechanisms intended to resist statistical analysis, brute-force attacks, known-plaintext attacks, chosen-plaintext attacks, and other modern threat models.

Another important security distinction is confidentiality versus authenticity. A reversible substitution transformation does not automatically provide integrity or authentication. A recipient needs a way to determine whether a ciphertext has been modified.

## Implementation considerations

A practical implementation should clearly define its supported alphabet.

The three implementations deliberately use ASCII English letters rather than silently attempting to transform every Unicode character. This avoids ambiguity around alphabet size and Unicode normalization.

Key validation is performed before encryption.

The forward and reverse mappings are constructed once and reused for multiple messages.

For fixed alphabets, arrays and direct indexing provide efficient implementations.

Formatting behavior is explicitly defined. Alphabetic characters are transformed while spaces, numbers, and punctuation remain unchanged.

Error handling is explicit. Invalid keys and invalid affine parameters generate errors instead of producing ambiguous results.

Self-tests verify round-trip behavior. This is particularly important for reversible transformations because a transformation can appear correct on encryption while still containing a bug in decryption.

## Python, JavaScript, and C++ comparison

Python is particularly useful for expressing mathematical ideas, cryptanalysis experiments, statistical calculations, and rapid experimentation. Its dictionaries, counters, dataclasses, and high-level string operations make the underlying algorithms easy to inspect.

JavaScript is useful for demonstrating how substitution processing can exist inside application-level and event-driven environments. `Map`, `Set`, classes, asynchronous functions, and Node.js timing facilities provide useful application-oriented perspectives.

C++ provides a lower-level implementation perspective. Fixed-size arrays, explicit types, classes, exception handling, standard containers, and high-resolution timing make it suitable for examining memory representation, data structures, performance, and architectural decomposition.

All three languages implement the same underlying mathematical concepts, but they expose different engineering trade-offs.

## Practical applications and historical relevance

Classical substitution ciphers are primarily useful for education, historical cryptography, puzzle systems, introductory cryptanalysis, and demonstrations of information leakage.

They provide a compact environment for studying:

- Modular arithmetic.
- Permutations.
- Inverse functions.
- Key spaces.
- Statistical analysis.
- Brute-force search.
- Pattern recognition.
- Cryptanalytic reasoning.
- Algorithmic complexity.
- Software validation.

They also provide an accessible bridge between mathematical cryptography and modern security engineering.

## Advanced conceptual implications

The most important lesson from substitution ciphers is that encryption should be evaluated against an attacker model rather than only against successful decryption.

A transformation may satisfy:

`decrypt(encrypt(P, K), K) = P`

and still provide weak confidentiality.

Substitution ciphers demonstrate this distinction clearly. Their transformations are reversible, their keys can be mathematically well defined, and their implementations can be correct, yet their preserved statistical properties allow attackers to infer information.

This concept extends far beyond classical cryptography. Security engineering requires examining what information remains observable after a transformation, what assumptions the attacker can make, how much information is leaked, and whether the system remains secure under realistic attack conditions.

## Implementation coverage

The Python implementation covers the broadest educational range, including fundamental transformations, mathematical operations, frequency analysis, cryptanalysis, object-oriented design, testing, edge cases, and performance measurement.

The JavaScript implementation emphasizes reusable application-level abstractions, `Map` and `Set` data structures, class-based design, asynchronous execution, and Node.js performance measurement.

The C++ implementation develops a larger message-routing case study with classes, fixed-size arrays, validation, exception handling, statistical analysis, performance measurement, message records, and explicit complexity considerations.

Together, the three implementations demonstrate that substitution ciphers are not merely historical algorithms. They are compact examples through which mathematical modeling, algorithm design, software architecture, testing, performance analysis, and security reasoning can all be studied.

# URLs and URIs in Python

## Introduction

A Uniform Resource Identifier (URI) is a standardized identifier used to identify a resource. A Uniform Resource Locator (URL) is a commonly used type of URI that identifies a resource and provides information about how or where it can be accessed.

These concepts are fundamental to web development, networking, APIs, distributed systems, browser behavior, security engineering, logging systems, and application integration.

The accompanying Python script develops URL and URI concepts from basic terminology through structured parsing, query manipulation, encoding, validation, normalization, relative reference resolution, security analysis, and production-oriented design.

The script uses Python's standard library, particularly `urllib.parse`, so all examples can run without external packages.

## URI and URL

### URI

A URI is a general-purpose identifier for a resource.

Examples include:

    https://example.com/products
    mailto:person@example.com
    urn:isbn:9780132350884

The `mailto` URI identifies an email address using the `mailto` scheme. A URN identifies a resource by name rather than necessarily describing a network location.

### URL

A URL is commonly understood as a URI that identifies a resource and provides a location or access mechanism.

Examples include:

    https://example.com
    https://api.example.com/v1/users
    ftp://files.example.com/archive.zip

A useful practical relationship is:

    URL ⊆ URI

The terminology has historical and standards-related subtleties, but in ordinary software engineering a URL is generally treated as a specific kind of URI.

## General URL Structure

A common hierarchical URL can be represented conceptually as:

    scheme://userinfo@host:port/path?query#fragment

Not every component is required.

For example:

    https://alice:secret@example.com:8443/products/books?category=python&page=2#reviews

The components are:

- `https` is the scheme.
- `alice:secret` is user information.
- `example.com` is the host.
- `8443` is the port.
- `/products/books` is the path.
- `category=python&page=2` is the query.
- `reviews` is the fragment.

The exact meaning of many components depends on the scheme and the application processing the URI.

## Scheme

The scheme identifies the interpretation mechanism associated with a URI.

Common schemes include:

- `http` for Hypertext Transfer Protocol.
- `https` for HTTP protected by TLS.
- `ftp` for File Transfer Protocol.
- `file` for local file references.
- `mailto` for email address references.
- `data` for inline data.
- `urn` for persistent names.

Examples:

    https://example.com
    ftp://files.example.com/archive.zip
    mailto:person@example.com
    urn:isbn:9780132350884

The Python script parses multiple schemes and demonstrates that URI parsing is not limited to HTTP and HTTPS.

## Authority and Network Location

For many hierarchical URLs, the authority portion appears after the scheme separator.

Example:

    https://example.com:8443/path

The authority includes:

    example.com:8443

Python's `urllib.parse` exposes this as the `netloc` component.

The authority may contain:

- user information
- host
- port

The `netloc` string should not always be interpreted manually. Python provides derived attributes such as `username`, `password`, `hostname`, and `port`.

## User Information

A URL can syntactically contain user information before the host.

Example:

    https://username:password@example.com/private

Python can extract:

- username
- password
- hostname

Although this syntax exists, sensitive credentials should generally not be placed in URLs.

URLs can appear in:

- browser history
- server logs
- proxy logs
- analytics systems
- monitoring systems
- screenshots
- copied messages
- error reports

Passwords, access tokens, API keys, and secrets should generally be transmitted using mechanisms specifically designed for authentication rather than embedding them in URLs.

## Host

The host identifies the server associated with a network resource.

A host can commonly be represented by:

- a domain name
- an IPv4 address
- an IPv6 address

Examples:

    example.com
    api.example.com
    192.168.1.10
    [2001:db8::1]

Python's parsed `hostname` property removes IPv6 brackets from the logical hostname representation.

The script demonstrates host classification using the `ipaddress` module and conservative domain-name validation.

## Domain Names

A domain name is composed of labels separated by periods.

Examples:

    example.com
    api.example.com
    service.department.example.com

A basic domain validator can check structural properties such as:

- labels must not be empty
- labels must not begin with a hyphen
- labels must not end with a hyphen
- labels must contain only permitted characters
- labels have length limits

Syntactic validation does not prove that the domain exists or resolves through DNS.

A string can be structurally valid while no corresponding server exists.

## Internationalized Domain Names

Domain names can contain non-ASCII characters.

For DNS compatibility, internationalized domain names commonly use an ASCII representation produced through IDNA encoding.

The script demonstrates conversion using Python's built-in `idna` codec.

For example, a Unicode domain can be encoded into an ASCII-compatible representation suitable for DNS processing.

Internationalized domain names require careful handling because visual similarity between Unicode characters can create security and phishing concerns.

## IPv4 and IPv6

IPv4 addresses contain four numeric components separated by periods.

Example:

    192.168.1.10

IPv6 addresses contain colon-separated hexadecimal components.

Example:

    2001:db8::1

When an IPv6 address appears in the authority portion together with a port, brackets are used.

Example:

    http://[2001:db8::1]:8080

The brackets prevent ambiguity between IPv6 colons and the colon that separates the host from the port.

## Port

A port identifies a communication endpoint associated with a host.

Common conventional ports include:

- HTTP: 80
- HTTPS: 443
- FTP: 21

Examples:

    http://example.com
    http://example.com:80
    https://example.com
    https://example.com:443
    http://localhost:8080

A URL does not need to explicitly specify a conventional port.

The script defines an `effective_port` function that returns:

- the explicit port when one is present
- a conventional default for selected schemes when no port is explicitly present

The port range is normally from 1 through 65535 for ordinary application-level validation.

Python may raise `ValueError` when accessing `.port` if the port syntax is malformed or outside the supported numeric range.

This is an important subtle behavior: parsing a URL object and accessing its derived port value are not always equivalent operations.

## Path

The path identifies a hierarchical location associated with the resource.

Examples:

    /
    /products
    /products/42
    /users/alice/settings

A URL path does not necessarily map directly to a physical file or directory.

A web application may interpret:

    /products/42

as:

- a database lookup
- an API route
- a dynamically generated page
- a reverse-proxy rule
- a serverless function route

The script demonstrates splitting paths into logical non-empty segments.

For example:

    /products/books/python/

becomes:

    products
    books
    python

## URL Paths Are Not Filesystem Paths

URL paths and operating-system filesystem paths are different concepts.

URL paths use `/` as their structural separator.

Filesystem paths can use different conventions depending on the operating system.

A web URL should therefore be manipulated using URL-aware utilities rather than generic filesystem path functions.

The script uses `urllib.parse` and `urljoin` for URL-oriented operations.

## Trailing Slashes

The following paths may look similar:

    /products

and:

    /products/

They are not guaranteed to represent the same resource.

Depending on server configuration, one may:

- redirect to the other
- represent the same application route
- represent a different resource
- map to different cache keys

Applications should define their own canonical path conventions rather than assuming trailing slashes are universally interchangeable.

## Query

The query begins after `?`.

Example:

    https://example.com/search?q=python&page=2

The query is frequently used to transmit parameters.

A common convention is:

    key=value&another=value

Examples:

    q=python
    page=2
    sort=recent

The exact meaning of query parameters is application-defined.

A query is not inherently a Python dictionary. Parameters can repeat, be blank, or have ordering that matters.

## Parsing Query Parameters

Python provides:

- `parse_qs`
- `parse_qsl`

### `parse_qs`

`parse_qs` returns a dictionary where each value is a list.

For:

    category=python&category=security

the result is conceptually:

    {
        "category": ["python", "security"]
    }

This representation preserves repeated values.

### `parse_qsl`

`parse_qsl` returns a sequence of key-value pairs.

For:

    category=python&category=security

the result is conceptually:

    [
        ("category", "python"),
        ("category", "security")
    ]

This representation is useful when preserving parameter order or repeated keys is important.

## Blank Query Values

Queries may contain blank values.

Example:

    q=&page=2

A parameter can also appear without an explicit value depending on the query syntax.

The script demonstrates `keep_blank_values=True`.

This matters because applications can distinguish between:

- parameter absent
- parameter present with an empty value

For example:

    ?filter=

may have different meaning from:

    no filter parameter at all

## Repeated Query Parameters

Repeated parameters are common.

Example:

    ?tag=python&tag=web&tag=security

This may represent:

- multiple selected categories
- multiple filters
- multiple values for one field

Using a plain dictionary can accidentally lose repeated values.

The script demonstrates `urlencode(..., doseq=True)` and ordered sequences of tuples for repeated query parameters.

## Query Parameter Ordering

Some applications treat:

    a=1&b=2

and:

    b=2&a=1

as equivalent.

Other systems may preserve ordering or assign application-specific meaning to it.

For this reason, automatic query sorting should not be performed unless the application's semantics explicitly allow it.

The normalization function in the script intentionally does not sort query parameters.

## Fragment

The fragment begins after `#`.

Example:

    https://example.com/document#section-2

The fragment identifies a location or subresource associated with the resource representation.

Common examples include:

    #introduction
    #section-2
    #reviews

In many ordinary browser interactions, fragments are handled by the client and are not transmitted to the server as part of the HTTP request target.

Fragments and queries are conceptually different:

- query parameters often influence server-side resource selection
- fragments commonly identify a location within the returned representation

The exact behavior depends on the protocol and application.

## Percent-Encoding

URLs contain characters with structural meaning.

Examples include:

    :
    /
    ?
    #
    @

When data contains characters that would otherwise be interpreted structurally, percent-encoding can represent bytes using:

    %HH

where `HH` is a hexadecimal byte representation.

Python provides:

- `quote`
- `unquote`

Example data:

    Python programming & data analysis

can be encoded safely when inserted into an appropriate URL component.

## `quote` and `quote_plus`

Python provides both `quote` and `quote_plus`.

`quote` commonly represents spaces as:

    %20

`quote_plus` commonly represents spaces as:

    +

The plus convention is frequently associated with form-style query encoding.

Python also provides:

- `unquote`
- `unquote_plus`

These should be used according to the component and encoding convention being processed.

## Component-Aware Encoding

Encoding should be performed according to the URL component receiving the data.

A common mistake is encoding an entire URL as one string.

For example, encoding:

    https://example.com/search?q=python data

as a single opaque value can encode structural separators that should remain structural.

A safer approach is:

1. keep the scheme, host, and path as URL structure
2. encode the query value as query data
3. construct the final URL

The script demonstrates this using `urlencode`.

## Path Segment Encoding

Path segments can contain data that requires encoding.

For example:

    Python & Data

can be encoded as a path segment so that the ampersand is interpreted as data rather than an unrelated structural character.

The script uses:

    quote(value, safe="")

for a path-segment example.

Encoding rules should be chosen carefully because different URL components permit and interpret characters differently.

## URL Parsing with `urllib.parse`

The central parser used in the script is:

    urlparse

A parsed result exposes components including:

- scheme
- netloc
- path
- params
- query
- fragment

Derived properties include:

- username
- password
- hostname
- port

The parser separates syntax. It does not automatically establish network connectivity, verify DNS, verify TLS certificates, or prove that the resource exists.

## `urlparse` Versus `urlsplit`

Python provides both `urlparse` and `urlsplit`.

`urlparse` separates:

- scheme
- netloc
- path
- params
- query
- fragment

`urlsplit` separates:

- scheme
- netloc
- path
- query
- fragment

The difference involves handling of the historical `params` component.

For many modern web URLs, `urlsplit` is simpler because applications frequently work primarily with:

- scheme
- authority
- path
- query
- fragment

The script demonstrates both functions.

## Reconstructing URLs

Python provides:

- `urlunparse`
- `urlunsplit`

These reconstruct URLs from structured components.

This is preferable to manual string concatenation when an application already has parsed or structured URL components.

Structured reconstruction reduces errors involving:

- missing separators
- duplicate question marks
- malformed fragments
- incorrectly placed ports

## Absolute URLs

An absolute URL contains sufficient information to identify the resource without depending on a base URI.

Example:

    https://example.com/products

It includes a scheme and, for common network URLs, an authority containing a host.

## Relative References

A relative reference depends on a base URL.

Examples:

    introduction.html
    ../images/logo.png
    /products

Python's `urljoin` resolves relative references against a base URL.

For example, a base such as:

    https://example.com/docs/tutorials/

can resolve:

    introduction.html

into:

    https://example.com/docs/tutorials/introduction.html

Relative resolution is a structured operation and should generally use URL-aware utilities rather than manual string concatenation.

## Dot Segments

Relative references can use:

    .

for the current location and:

    ..

for a parent location.

Examples:

    ./page.html
    ../page.html
    ../../page.html

The script demonstrates how `urljoin` resolves these references.

## Scheme-Relative References

A reference such as:

    //cdn.example/library.js

contains an authority but omits the scheme.

When resolved against:

    https://origin.example/page

it can inherit the scheme from the base context.

This behavior must be understood when validating untrusted references because a scheme-relative reference can still direct a client to another host.

## Security Risk: `urljoin` Base Replacement

`urljoin` follows URI reference resolution rules.

If a base URL is trusted:

    https://trusted.example/account/

and the user supplies:

    https://attacker.example/steal

the result is the attacker-controlled URL.

This creates a risk when an application assumes all user input will remain under the trusted base.

The script demonstrates a safer helper that rejects references containing:

- a scheme
- an authority

before calling `urljoin`.

## URL Validation

URL validation depends on application requirements.

There is no single universal definition of "valid URL" for every application.

A parser may successfully separate components from a string that an application should reject.

The script's basic HTTP/HTTPS validator checks:

- the input is a string
- the value is not empty
- surrounding whitespace is rejected
- the scheme is HTTP or HTTPS
- a hostname exists
- malformed or invalid ports are rejected

This is intentionally conservative and educational rather than a universal validation system.

## Syntax Validation Versus Reachability

A URL can be syntactically valid while the resource is unavailable.

Successful parsing does not prove:

- the domain exists
- DNS resolution succeeds
- the network route is available
- the server is running
- the port accepts connections
- TLS validation succeeds
- authentication succeeds
- the requested resource exists

These are different stages of processing.

A robust system separates:

1. syntax parsing
2. application validation
3. network resolution
4. connection
5. protocol processing
6. application response handling

## Host Validation

The script classifies hosts as:

- IPv4
- IPv6
- domain
- invalid

It uses the standard-library `ipaddress` module for literal IP addresses.

The domain validator is intentionally conservative and syntactic.

It does not:

- query DNS
- verify domain ownership
- verify server reachability

## Case Sensitivity

URL components do not all have identical case rules.

Scheme comparisons are commonly case-insensitive.

Hostnames are commonly treated case-insensitively.

Paths may be case-sensitive depending on server and application configuration.

For example:

    /Products

and:

    /products

may refer to different resources.

A normalizer should therefore avoid blindly changing path case.

## URL Normalization

Normalization transforms a URL into a preferred canonical form.

The script demonstrates conservative normalization that:

- lowercases the scheme
- lowercases the hostname
- removes conventional default HTTP and HTTPS ports
- converts an empty hierarchical path to `/`
- preserves query parameters
- preserves fragments

Examples include converting:

    HTTPS://EXAMPLE.COM:443

into a normalized HTTP/HTTPS representation.

Normalization must be application-specific.

Potentially unsafe transformations include:

- sorting query parameters without knowing their semantics
- changing path case
- removing trailing slashes
- decoding and re-encoding without understanding the original data
- removing parameters that affect resource behavior

## URL Equivalence

Two URLs can differ as strings while an application treats them as equivalent.

For example:

    https://example.com

and:

    https://example.com/

may resolve to the same resource on a particular server.

That equivalence is not guaranteed by simple syntax.

The script compares:

- strict string equality
- equality after a defined normalization process

This illustrates an important principle: URL equality depends on the equivalence rules being used.

## Programmatic URL Construction

URLs should generally be constructed from components.

For example:

- define a base path
- represent query data as structured values
- encode query values using `urlencode`

This is safer than concatenating untrusted strings directly.

The script includes:

- a search URL builder
- a dataclass-based web URL builder
- an API request example
- pagination URL generation

## Updating Query Parameters

Applications frequently need to modify existing URLs.

Examples include:

- changing page numbers
- updating search terms
- adding filters
- removing tracking values

The script parses existing query pairs, modifies the structured representation, re-encodes the query, and reconstructs the URL.

This avoids fragile operations such as searching for text fragments inside a raw URL.

## Removing Query Parameters

Removing a parameter should preserve other parameters.

The script demonstrates filtering query pairs by key and rebuilding the query.

This approach correctly handles:

- multiple parameters
- repeated values
- blank values

## Pagination URLs

Pagination often uses a parameter such as:

    ?page=1

The script generates multiple pagination URLs while preserving existing query parameters.

For example:

    https://example.com/products?category=books

can become logically equivalent to:

    https://example.com/products?category=books&page=1
    https://example.com/products?category=books&page=2
    https://example.com/products?category=books&page=3

The implementation removes existing `page` parameters before inserting the desired page value.

This prevents accidental accumulation of multiple page values.

## Query Parsing Should Not Be Performed Manually

A fragile approach is:

    query.split("&")

followed by:

    item.split("=")

This can fail conceptually because:

- values may contain encoded separators
- keys can repeat
- blank values may matter
- percent-encoded data requires decoding
- splitting rules can become more complex than expected

Python's `parse_qs` and `parse_qsl` are designed for query parsing and should be preferred for ordinary form-style query strings.

## Common Mistake: Unsafe String Concatenation

Consider a search term:

    Python & security

Direct concatenation can produce:

    https://example.com/search?q=Python & security

The ampersand may be interpreted structurally.

Using `urlencode` correctly represents the value as query data.

The distinction is:

- raw string concatenation mixes data with syntax
- component-aware encoding keeps data and syntax separate

## Common Mistake: Double Encoding

Double encoding occurs when already-encoded data is encoded again.

For example:

    hello world

may first become:

    hello%20world

and encoding that value again can transform `%` itself.

The result can contain:

    %2520

instead of the intended:

    %20

Applications should track whether a value is:

- raw application data
- an encoded component
- a complete URL

Encoding should normally occur at a clearly defined boundary.

## Common Mistake: Encoding an Entire URL

A complete URL contains structural characters such as:

- `:`
- `/`
- `?`
- `#`

Encoding the entire URL as if it were one data value can destroy its structure.

Encoding should target the appropriate component rather than treating the complete URL as a single parameter value.

## Same Origin

In web security, an origin is commonly associated with:

- scheme
- host
- port

Examples:

    https://example.com

and:

    https://example.com:443

can have the same effective conventional HTTPS origin.

By contrast:

    http://example.com

differs in scheme from HTTPS.

The script creates a simplified origin tuple using effective default ports.

Origin comparisons are important in browser security, cross-origin policies, and application isolation.

## Host Comparison

Host comparison should generally use parsed hostname values rather than raw string operations.

The script demonstrates case-normalized hostname comparison.

Comparing raw URL strings can produce misleading results because URLs can differ in:

- scheme
- path
- port
- case
- query
- fragment

while sharing the same host.

## Open Redirect Risks

Applications sometimes accept a destination such as:

    /dashboard

or:

    https://example.com/profile

for post-login or navigation redirects.

If untrusted absolute URLs are accepted without validation, an attacker may supply:

    https://attacker.example/login

and cause a user to be redirected outside the intended application.

The script demonstrates a basic safe redirect policy that:

- permits relative paths
- permits selected absolute HTTP/HTTPS URLs
- checks hosts against an allowlist
- rejects unknown schemes
- rejects scheme-relative attacker-controlled authorities

Production redirect policies should be defined according to the application's actual trust boundaries.

## Server-Side Request Forgery Considerations

Server-Side Request Forgery, commonly called SSRF, can occur when a server fetches user-controlled URLs.

A simple rule such as:

    URL starts with https://

is not sufficient protection.

A robust SSRF defense can involve:

- scheme allowlists
- hostname allowlists
- DNS resolution controls
- blocking loopback addresses
- blocking private addresses
- blocking link-local and special-purpose addresses
- controlling redirects
- connection timeouts
- response size limits
- network-level restrictions

The script demonstrates the `ipaddress` module's classification capabilities for literal addresses.

A complete SSRF defense is a system-level problem and cannot be reduced safely to one string check.

## User Information and Host Confusion

A URL such as:

    https://trusted.example@attacker.example/path

may visually confuse users.

The portion before `@` is user information.

The actual host is:

    attacker.example

Security-sensitive code should inspect parsed components such as `hostname` rather than relying on visual inspection or substring checks.

## Sensitive URL Logging

URLs may contain sensitive information.

Examples include:

    ?token=...
    ?api_key=...
    ?access_token=...
    ?password=...

The script implements a redaction function that masks selected sensitive query values before logging.

It also masks passwords contained in URL user information.

Real systems should define redaction rules based on their actual parameter names and security requirements.

Logging policies should assume that URLs can be retained and distributed through monitoring infrastructure.

## URLs and Caching

URLs often influence cache keys.

For example:

    /product?id=1

and:

    /product?id=2

can represent different resources.

Tracking parameters can create unnecessary cache fragmentation:

    ?utm_source=newsletter
    ?utm_source=search

The script demonstrates removal of selected tracking parameters.

This should only be done when those parameters do not affect application behavior.

Removing arbitrary query parameters can cause incorrect cache reuse.

## Performance Considerations

URL parsing is generally lightweight for ordinary applications.

Performance becomes more important when processing:

- crawler datasets
- API gateway traffic
- access logs
- security telemetry
- large collections of URLs

Useful practices include:

- parse once when multiple components are needed
- avoid repeated parsing of the same value
- preserve structured components when possible
- avoid unnecessary reconstruction
- separate cheap syntax checks from expensive network checks

DNS resolution and network access are significantly different operations from local URL parsing.

## Debugging URLs

The script includes a structured debugging helper that exposes:

- original URL
- scheme
- network location
- username
- password presence
- hostname
- port
- path
- parameters
- raw query
- parsed query pairs
- fragment

Structured debugging is preferable to manually guessing which part of a URL caused a problem.

When debugging, inspect components independently.

Common problems include:

- missing scheme
- missing host
- malformed ports
- incorrectly encoded query values
- accidental double encoding
- fragment confusion
- repeated query parameters
- user information being mistaken for the host

## Dataclass-Based URL Construction

The script defines a `WebURL` dataclass.

It stores:

- scheme
- host
- path
- optional port
- optional query parameters
- fragment

The `build` method validates important values and constructs the final URL from components.

This pattern is useful when URLs are treated as structured application objects rather than repeatedly manipulated as raw strings.

Structured representations improve clarity and reduce accidental mixing of:

- trusted syntax
- user data
- encoded values
- complete URLs

## Comprehensive URL Analysis

The script combines parsing concepts into a `URLAnalysis` dataclass.

The analysis records:

- original value
- scheme
- host
- host classification
- explicit port
- effective port
- path
- path segments
- query pairs
- fragment
- whether the reference is absolute
- whether the value is a basic HTTP/HTTPS URL

This demonstrates a useful architectural principle: parsing can be centralized into a structured analysis layer rather than repeatedly reimplementing component extraction throughout an application.

## Production Design Principles

URL handling in production systems benefits from several principles.

### Treat URLs as Structured Data

Do not treat every URL operation as arbitrary string manipulation.

Use:

- parsers
- structured components
- dedicated encoders
- dedicated query parsers

### Encode at Component Boundaries

Encode application data when inserting it into:

- query values
- path segments
- other appropriate URI components

Do not encode an entire structured URL as one opaque string.

### Validate According to Context

A URL acceptable for:

- a browser link

may not be acceptable for:

- a server-side fetcher
- a redirect destination
- a webhook target
- an internal API client

Validation rules should match the threat model and use case.

### Use Scheme Allowlists

When only web URLs are expected, explicitly allow:

    http
    https

rather than accepting arbitrary schemes.

### Avoid Secrets in URLs

Use appropriate authentication mechanisms rather than placing credentials in URLs.

### Treat User-Controlled URLs as Security-Sensitive

This is especially important for:

- redirects
- server-side fetching
- callback destinations
- webhook configuration
- embedded resources

### Preserve Semantics During Normalization

Normalization can improve consistency but can also change meaning.

Do not assume that:

- path case is irrelevant
- trailing slashes are irrelevant
- query ordering is irrelevant
- duplicate parameters are irrelevant

### Redact Sensitive Information

Logging and monitoring systems should not expose secrets contained in URLs.

## Practical Applications

URL and URI handling is important in:

- web applications
- REST APIs
- API clients
- web crawlers
- browser software
- proxy servers
- reverse proxies
- API gateways
- authentication systems
- analytics systems
- logging pipelines
- security scanners
- cache systems
- distributed services

Common operations include:

- parsing incoming links
- generating API endpoints
- adding search parameters
- building pagination links
- resolving relative resources
- validating redirect destinations
- filtering external URLs
- redacting sensitive query parameters
- comparing origins
- normalizing selected URL forms

## Limitations of Generic URL Handling

No generic parser can determine all application semantics.

A parser can determine:

- syntactic components
- host strings
- paths
- query values
- fragments

A parser cannot determine automatically:

- whether the server exists
- whether the resource exists
- whether two URLs are semantically equivalent
- whether a redirect is safe for a specific business workflow
- whether a query parameter changes server behavior
- whether a host is trusted
- whether a remote resource is safe to fetch

These decisions require application-specific rules and, in security-sensitive systems, defense mechanisms beyond parsing.

## Final Integrated Processing Model

The final example in the script demonstrates a conservative processing sequence:

1. Confirm the value is a string.
2. Reject empty values and surrounding whitespace.
3. Parse the URL.
4. Restrict schemes to an allowed set.
5. Require a hostname.
6. Access the port so malformed values are detected.
7. Apply conservative normalization.

This model illustrates the difference between:

- parsing
- validation
- normalization
- security policy

A robust URL-handling design keeps these concerns conceptually separate.

Parsing determines structure.

Validation determines whether a structure is acceptable for a specific use.

Normalization transforms an accepted value according to explicit rules.

Security policy determines which destinations and operations are permitted.

Understanding these distinctions is essential for correct URL construction, reliable API communication, safe navigation, secure redirection, and production-quality networked applications.

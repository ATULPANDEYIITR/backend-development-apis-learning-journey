"""
URLs and URIs: A Comprehensive Python Study Script

Topics covered:
- URI vs URL
- URL structure
- Scheme
- Authority
- User information
- Host
- Domain names and IP addresses
- Ports
- Paths
- Query parameters
- Fragments
- Absolute and relative references
- URL parsing with urllib.parse
- URL construction and normalization
- Percent-encoding
- Query encoding and decoding
- Validation
- Common mistakes
- Security considerations
- Performance considerations
- Real-world applications
- Advanced URL handling patterns

This script uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import (
    ParseResult,
    parse_qs,
    parse_qsl,
    quote,
    quote_plus,
    unquote,
    unquote_plus,
    urlencode,
    urljoin,
    urlparse,
    urlsplit,
    urlunparse,
    urlunsplit,
)
import ipaddress
import re


# =============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# =============================================================================

# URI = Uniform Resource Identifier
#
# A URI is a general identifier for a resource.
#
# Examples:
#   https://example.com/products
#   mailto:person@example.com
#   urn:isbn:9780132350884
#
# URL = Uniform Resource Locator
#
# A URL is a URI that identifies a resource and describes how or where it can
# generally be accessed.
#
# Examples:
#   https://example.com
#   ftp://files.example.com/archive.zip
#
# Practical relationship:
#
#   URL is generally treated as a type of URI.
#
# Not every URI is necessarily a network URL. For example:
#
#   urn:isbn:9780132350884
#
# identifies a resource but does not provide a network location using a host.


def print_section(title: str) -> None:
    """Print a visually separated section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


print_section("1. URI VS URL")

uri_examples = [
    "https://example.com/products?id=10",
    "mailto:person@example.com",
    "urn:isbn:9780132350884",
    "file:///home/user/document.txt",
]

for uri in uri_examples:
    print(uri)


# =============================================================================
# 2. BASIC URL STRUCTURE
# =============================================================================

# A common hierarchical URL can be represented conceptually as:
#
# scheme://userinfo@host:port/path?query#fragment
#
# Not every component is required.
#
# Example:
#
# https://alice:secret@example.com:8443/products/books?category=python&page=2#reviews
#
# Components:
#
# https                 -> scheme
# alice:secret          -> user information
# example.com           -> host
# 8443                  -> port
# /products/books       -> path
# category=python&page=2 -> query
# reviews               -> fragment


print_section("2. URL STRUCTURE")

example_url = (
    "https://alice:secret@example.com:8443/products/books"
    "?category=python&page=2#reviews"
)

print("Complete URL:")
print(example_url)


# =============================================================================
# 3. PARSING URLs WITH urllib.parse
# =============================================================================

print_section("3. PARSING A URL")

parsed = urlparse(example_url)

print("Scheme:", parsed.scheme)
print("Network location (netloc):", parsed.netloc)
print("Path:", parsed.path)
print("Parameters:", parsed.params)
print("Query:", parsed.query)
print("Fragment:", parsed.fragment)

# ParseResult also provides useful derived attributes.
print("Username:", parsed.username)
print("Password:", parsed.password)
print("Hostname:", parsed.hostname)
print("Port:", parsed.port)


# =============================================================================
# 4. SCHEMES
# =============================================================================

print_section("4. URL SCHEMES")

# The scheme identifies the interpretation mechanism or protocol associated
# with the URI.
#
# Common examples:
#
# http   -> Hypertext Transfer Protocol
# https  -> HTTP protected by TLS
# ftp    -> File Transfer Protocol
# file   -> Local file resource
# mailto -> Email address reference
# data   -> Inline data
# urn    -> Uniform Resource Name

scheme_examples = [
    "http://example.com",
    "https://example.com",
    "ftp://files.example.com/archive.zip",
    "file:///home/user/report.txt",
    "mailto:person@example.com",
    "data:text/plain,Hello",
    "urn:isbn:9780132350884",
]

for value in scheme_examples:
    result = urlparse(value)
    print(f"{value!r} -> scheme={result.scheme!r}")


# =============================================================================
# 5. HOSTS
# =============================================================================

print_section("5. HOSTS")

# A host commonly identifies the server associated with a network resource.
#
# Hosts may be:
# - Domain names
# - IPv4 addresses
# - IPv6 addresses
#
# Examples:
# - example.com
# - api.example.com
# - 192.168.1.10
# - [2001:db8::1]

host_examples = [
    "https://example.com",
    "https://api.example.com",
    "http://192.168.1.10:8080",
    "http://[2001:db8::1]:8080",
]

for value in host_examples:
    result = urlparse(value)
    print(
        f"{value}\n"
        f"  hostname={result.hostname!r}\n"
        f"  port={result.port!r}"
    )


# =============================================================================
# 6. PORTS
# =============================================================================

print_section("6. PORTS")

# A port identifies a communication endpoint on a host.
#
# Common conventional ports:
#
# HTTP  -> 80
# HTTPS -> 443
# FTP   -> 21
#
# A port is optional in many URLs. When omitted, software may use the default
# associated with the scheme.

port_examples = [
    "http://example.com",
    "http://example.com:80",
    "https://example.com",
    "https://example.com:443",
    "http://localhost:8000",
]

for value in port_examples:
    result = urlparse(value)

    print(
        f"{value}\n"
        f"  scheme={result.scheme!r}\n"
        f"  hostname={result.hostname!r}\n"
        f"  explicit port={result.port!r}"
    )


DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ftp": 21,
}


def effective_port(parsed_url: ParseResult) -> int | None:
    """
    Return the explicit port if present.

    Otherwise return a conventional default for selected schemes.
    """
    if parsed_url.port is not None:
        return parsed_url.port

    return DEFAULT_PORTS.get(parsed_url.scheme.lower())


for value in [
    "http://example.com",
    "https://example.com",
    "http://localhost:3000",
]:
    result = urlparse(value)
    print(value, "-> effective port:", effective_port(result))


# =============================================================================
# 7. PATHS
# =============================================================================

print_section("7. PATHS")

# The path identifies a location within the hierarchical structure of a
# resource.
#
# Examples:
#
# /
# /products
# /products/42
# /users/alice/settings
#
# Path interpretation is application-specific. A path does not necessarily
# correspond directly to a physical directory or file.

path_examples = [
    "https://example.com/",
    "https://example.com/products",
    "https://example.com/products/42",
    "https://example.com/users/alice/settings",
]

for value in path_examples:
    result = urlparse(value)
    print(f"{value} -> path={result.path!r}")


# =============================================================================
# 8. QUERY PARAMETERS
# =============================================================================

print_section("8. QUERY PARAMETERS")

# A query begins after '?'.
#
# Example:
#
# https://example.com/search?q=python&page=2
#
# Query syntax is often represented as key=value pairs separated by '&',
# but interpretation is defined by the receiving application.

query_url = "https://example.com/search?q=python&page=2&sort=recent"

result = urlparse(query_url)

print("Raw query:", result.query)

# parse_qs returns a dictionary whose values are lists.
query_as_lists = parse_qs(result.query)

print("parse_qs result:", query_as_lists)

# parse_qsl returns a list of (key, value) pairs and preserves repeated keys.
query_as_pairs = parse_qsl(result.query)

print("parse_qsl result:", query_as_pairs)


# =============================================================================
# 9. REPEATED QUERY PARAMETERS
# =============================================================================

print_section("9. REPEATED QUERY PARAMETERS")

repeated_query_url = (
    "https://example.com/products?"
    "category=books&category=programming&category=python"
)

result = urlparse(repeated_query_url)

print("Raw query:", result.query)
print("parse_qs:", parse_qs(result.query))
print("parse_qsl:", parse_qsl(result.query))


# =============================================================================
# 10. EMPTY AND UNUSUAL QUERY VALUES
# =============================================================================

print_section("10. EMPTY QUERY VALUES")

unusual_query = (
    "https://example.com/search?"
    "q=&page=2&flag&empty=&duplicate=1&duplicate=2"
)

result = urlparse(unusual_query)

print("Raw query:", result.query)

print(
    "parse_qs without keep_blank_values:",
    parse_qs(result.query),
)

print(
    "parse_qs with keep_blank_values=True:",
    parse_qs(result.query, keep_blank_values=True),
)

print(
    "parse_qsl with keep_blank_values=True:",
    parse_qsl(result.query, keep_blank_values=True),
)


# =============================================================================
# 11. FRAGMENTS
# =============================================================================

print_section("11. FRAGMENTS")

# A fragment begins after '#'.
#
# Example:
#
# https://example.com/document#section-2
#
# The fragment usually identifies a subresource or location within the
# representation. For many web interactions, the fragment is handled by the
# client and is not sent to the server as part of the HTTP request target.

fragment_url = "https://example.com/document#section-2"

result = urlparse(fragment_url)

print("URL:", fragment_url)
print("Path:", result.path)
print("Fragment:", result.fragment)


# =============================================================================
# 12. URLPARSE VS URLSPLIT
# =============================================================================

print_section("12. urlparse VS urlsplit")

# urlparse:
# - returns scheme, netloc, path, params, query, fragment
#
# urlsplit:
# - returns scheme, netloc, path, query, fragment
#
# urlsplit does not separate the historical "params" component.

comparison_url = "http://example.com/path;parameters?query=value#fragment"

parsed_result = urlparse(comparison_url)
split_result = urlsplit(comparison_url)

print("urlparse:", parsed_result)
print("urlsplit:", split_result)


# =============================================================================
# 13. REBUILDING URLs
# =============================================================================

print_section("13. REBUILDING URLs")

parts = (
    "https",
    "example.com",
    "/products",
    "",
    "category=python&page=2",
    "reviews",
)

rebuilt = urlunparse(parts)

print("Rebuilt URL:", rebuilt)


split_parts = (
    "https",
    "example.com",
    "/products",
    "category=python&page=2",
    "reviews",
)

rebuilt_split = urlunsplit(split_parts)

print("Rebuilt split URL:", rebuilt_split)


# =============================================================================
# 14. PERCENT-ENCODING
# =============================================================================

print_section("14. PERCENT-ENCODING")

# URLs contain characters with structural meaning:
#
# : / ? # [ ] @
#
# Other characters may need percent-encoding when they are data rather than
# structural separators.
#
# Percent-encoding represents bytes using:
#
# %HH
#
# where HH is a hexadecimal byte value.

text = "Python programming & data analysis"

encoded = quote(text)
decoded = unquote(encoded)

print("Original:", text)
print("quote:", encoded)
print("unquote:", decoded)


# =============================================================================
# 15. quote VS quote_plus
# =============================================================================

print_section("15. quote VS quote_plus")

# quote encodes spaces as %20.
# quote_plus encodes spaces as +.
#
# The '+' convention is commonly used for form-style query encoding.

text = "hello world + python"

print("quote:", quote(text))
print("quote_plus:", quote_plus(text))

encoded_plus = quote_plus(text)

print("unquote:", unquote(encoded_plus))
print("unquote_plus:", unquote_plus(encoded_plus))


# =============================================================================
# 16. ENCODING QUERY PARAMETERS SAFELY
# =============================================================================

print_section("16. ENCODING QUERY PARAMETERS")

query_parameters = {
    "q": "python tutorials",
    "category": "programming & technology",
    "page": 2,
    "include_archived": False,
}

encoded_query = urlencode(query_parameters)

print("Encoded query:", encoded_query)

search_url = f"https://example.com/search?{encoded_query}"

print("Complete URL:", search_url)


# =============================================================================
# 17. ENCODING REPEATED QUERY PARAMETERS
# =============================================================================

print_section("17. REPEATED QUERY PARAMETERS WITH DOSEQ")

parameters_with_lists = {
    "category": ["python", "data-science", "security"],
    "page": 1,
}

print(
    "Without doseq:",
    urlencode(parameters_with_lists),
)

print(
    "With doseq=True:",
    urlencode(parameters_with_lists, doseq=True),
)


# =============================================================================
# 18. ABSOLUTE VS RELATIVE URL REFERENCES
# =============================================================================

print_section("18. ABSOLUTE VS RELATIVE REFERENCES")

# Absolute reference:
#
# https://example.com/products
#
# Relative references:
#
# products
# /products
# ../images/logo.png

base_url = "https://example.com/docs/tutorials/"

relative_references = [
    "introduction.html",
    "../images/logo.png",
    "/products",
    "https://other.example/path",
]

for reference in relative_references:
    resolved = urljoin(base_url, reference)
    print(f"Base:     {base_url}")
    print(f"Reference:{reference}")
    print(f"Resolved: {resolved}\n")


# =============================================================================
# 19. IMPORTANT urljoin SECURITY CONSIDERATION
# =============================================================================

print_section("19. urljoin SECURITY CONSIDERATION")

# urljoin can produce an absolute URL controlled by an attacker.
#
# If an application expects a user input to be only a relative path but passes
# an absolute URL, the base can be replaced.

trusted_base = "https://trusted.example/account/"
user_input = "https://attacker.example/steal"

resolved = urljoin(trusted_base, user_input)

print("Trusted base:", trusted_base)
print("User input:", user_input)
print("Result:", resolved)


def join_relative_path_safely(base: str, reference: str) -> str:
    """
    Join a reference only when it does not define its own scheme or authority.

    This prevents a user-provided absolute URL from replacing the trusted base.
    """
    reference_parts = urlsplit(reference)

    if reference_parts.scheme or reference_parts.netloc:
        raise ValueError("Only relative references are allowed")

    return urljoin(base, reference)


safe_reference = "settings/profile"

print(
    "Safe result:",
    join_relative_path_safely(trusted_base, safe_reference),
)

try:
    join_relative_path_safely(trusted_base, "https://attacker.example")
except ValueError as error:
    print("Blocked unsafe reference:", error)


# =============================================================================
# 20. URL COMPONENT DATA CLASS
# =============================================================================

print_section("20. STRUCTURED URL COMPONENTS")


@dataclass(frozen=True)
class URLComponents:
    """
    A structured representation of selected URL components.

    This class is useful when an application wants to inspect URLs using named
    fields instead of repeatedly indexing tuples.
    """

    scheme: str
    host: str | None
    port: int | None
    path: str
    query: str
    fragment: str

    @classmethod
    def from_url(cls, url: str) -> "URLComponents":
        result = urlparse(url)

        return cls(
            scheme=result.scheme,
            host=result.hostname,
            port=result.port,
            path=result.path,
            query=result.query,
            fragment=result.fragment,
        )


components = URLComponents.from_url(
    "https://api.example.com:8443/v1/users?id=42#details"
)

print(components)


# =============================================================================
# 21. SIMPLE URL VALIDATION
# =============================================================================

print_section("21. URL VALIDATION")

# URL validation depends on application requirements.
#
# "Can this string be parsed?" and "Is this URL acceptable for my application?"
# are different questions.
#
# A parser can split many strings that should still be rejected by a particular
# application.

ALLOWED_WEB_SCHEMES = {"http", "https"}


def is_valid_web_url(value: str) -> bool:
    """
    Perform basic validation for an HTTP or HTTPS URL.

    Rules used here:
    - value must be a string
    - scheme must be http or https
    - hostname must exist
    - malformed ports must be rejected

    This is intentionally not a complete universal URL validator.
    """
    if not isinstance(value, str):
        return False

    if not value:
        return False

    if value != value.strip():
        return False

    try:
        result = urlparse(value)

        if result.scheme.lower() not in ALLOWED_WEB_SCHEMES:
            return False

        if not result.hostname:
            return False

        # Accessing .port can raise ValueError for malformed ports.
        if result.port is not None:
            if not 1 <= result.port <= 65535:
                return False

        return True

    except (ValueError, TypeError):
        return False


validation_examples: list[Any] = [
    "https://example.com",
    "http://localhost:8080",
    "ftp://example.com/file.txt",
    "example.com",
    "https://",
    "https://example.com:99999",
    " https://example.com",
    "",
    None,
]

for candidate in validation_examples:
    print(f"{candidate!r} -> {is_valid_web_url(candidate)}")


# =============================================================================
# 22. HOST VALIDATION
# =============================================================================

print_section("22. HOST VALIDATION")

# Hosts can be domain names, IPv4 addresses, or IPv6 addresses.
#
# Domain validation can become complex because internationalized domain names,
# local development names, and DNS rules may have different requirements.

DOMAIN_LABEL_PATTERN = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$"
)


def is_valid_domain_name(host: str) -> bool:
    """
    Perform basic ASCII domain-name validation.

    This function does not verify DNS existence.
    It only checks a conservative syntactic form.
    """
    if not host:
        return False

    if len(host) > 253:
        return False

    if host.endswith("."):
        host = host[:-1]

    labels = host.split(".")

    return all(DOMAIN_LABEL_PATTERN.fullmatch(label) for label in labels)


def classify_host(host: str) -> str:
    """
    Classify a host as IPv4, IPv6, domain, or invalid.
    """
    try:
        address = ipaddress.ip_address(host)

        if address.version == 4:
            return "IPv4"

        return "IPv6"

    except ValueError:
        if is_valid_domain_name(host):
            return "domain"

        return "invalid"


hosts_to_classify = [
    "example.com",
    "api.example.com",
    "192.168.1.1",
    "2001:db8::1",
    "-invalid.com",
    "invalid-.com",
    "invalid..com",
]

for host in hosts_to_classify:
    print(f"{host!r} -> {classify_host(host)}")


# =============================================================================
# 23. USER INFORMATION
# =============================================================================

print_section("23. USER INFORMATION")

# URL syntax can contain user information:
#
# scheme://username:password@host/path
#
# Embedding passwords or other secrets in URLs is generally dangerous because
# URLs can be logged, stored in browser history, copied, cached, or exposed in
# diagnostic output.

credential_url = "https://username:password@example.com/private"

result = urlparse(credential_url)

print("Username:", result.username)
print("Password:", result.password)
print("Host:", result.hostname)

print(
    "\nSecurity principle: avoid placing passwords, API keys, access tokens, "
    "or other secrets in URLs."
)


# =============================================================================
# 24. PATH SEGMENTS
# =============================================================================

print_section("24. PATH SEGMENTS")


def path_segments(path: str) -> list[str]:
    """
    Split a path into non-empty segments.

    Example:
        /products/books/python/
    becomes:
        ['products', 'books', 'python']
    """
    return [segment for segment in path.split("/") if segment]


example_path = "/products/books/python/"

print("Path:", example_path)
print("Segments:", path_segments(example_path))


# =============================================================================
# 25. TRAILING SLASH DISTINCTIONS
# =============================================================================

print_section("25. TRAILING SLASHES")

# Depending on the server and application:
#
# /products
#
# and:
#
# /products/
#
# may refer to:
# - the same resource
# - different resources
# - one resource redirecting to the other
#
# A client should not assume equivalence unless application rules define it.

for value in [
    "https://example.com/products",
    "https://example.com/products/",
]:
    result = urlparse(value)
    print(value, "-> path:", repr(result.path))


# =============================================================================
# 26. DOT SEGMENTS
# =============================================================================

print_section("26. DOT SEGMENTS")

# Relative references can contain:
#
# .   -> current location
# ..  -> parent location

base = "https://example.com/a/b/c/"

references = [
    "./page.html",
    "../page.html",
    "../../page.html",
    "../../../page.html",
]

for reference in references:
    print(reference, "->", urljoin(base, reference))


# =============================================================================
# 27. CASE SENSITIVITY
# =============================================================================

print_section("27. CASE SENSITIVITY")

# Scheme and host comparisons are commonly case-insensitive.
#
# Paths can be case-sensitive depending on the server and application.

case_url = "HTTPS://EXAMPLE.COM/Products/Python"

result = urlparse(case_url)

print("Original:", case_url)
print("Scheme:", result.scheme)
print("Hostname:", result.hostname)
print("Path:", result.path)


# =============================================================================
# 28. URL NORMALIZATION
# =============================================================================

print_section("28. URL NORMALIZATION")

# Normalization means transforming a URL into a preferred canonical form.
#
# Possible transformations depend on application rules:
# - Lowercase scheme
# - Lowercase hostname
# - Remove conventional default ports
# - Ensure a path exists
#
# Normalization is context-dependent. A transformation that is correct for one
# application may be incorrect for another.


def normalize_basic_http_url(url: str) -> str:
    """
    Perform conservative normalization for HTTP and HTTPS URLs.

    Transformations:
    - lowercase scheme
    - lowercase hostname
    - remove default HTTP/HTTPS port
    - ensure an empty hierarchical path becomes '/'
    - preserve query and fragment

    This function does not sort query parameters because parameter ordering may
    have application-specific meaning.
    """
    result = urlparse(url)

    scheme = result.scheme.lower()

    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported")

    if not result.hostname:
        raise ValueError("URL must contain a host")

    host = result.hostname.lower()

    port = result.port

    if port is not None:
        if (scheme == "http" and port == 80) or (
            scheme == "https" and port == 443
        ):
            port = None

    if ":" in host:
        host_display = f"[{host}]"
    else:
        host_display = host

    netloc = host_display

    if port is not None:
        netloc += f":{port}"

    path = result.path or "/"

    return urlunparse(
        (
            scheme,
            netloc,
            path,
            result.params,
            result.query,
            result.fragment,
        )
    )


normalization_examples = [
    "HTTPS://EXAMPLE.COM:443",
    "http://Example.COM:80/products",
    "https://Example.COM:8443/path?x=1#section",
]

for value in normalization_examples:
    print(value)
    print(" ->", normalize_basic_http_url(value))


# =============================================================================
# 29. BUILDING URLs PROGRAMMATICALLY
# =============================================================================

print_section("29. BUILDING URLs PROGRAMMATICALLY")


def build_search_url(
    base_url: str,
    search_term: str,
    page: int = 1,
    tags: Iterable[str] = (),
) -> str:
    """
    Construct a search URL using safe query encoding.

    Repeated tags become repeated query parameters.
    """
    parameters: list[tuple[str, str | int]] = [
        ("q", search_term),
        ("page", page),
    ]

    for tag in tags:
        parameters.append(("tag", tag))

    query = urlencode(parameters)

    result = urlparse(base_url)

    return urlunparse(
        (
            result.scheme,
            result.netloc,
            result.path,
            result.params,
            query,
            result.fragment,
        )
    )


built_url = build_search_url(
    "https://example.com/search",
    search_term="Python & URL parsing",
    page=2,
    tags=["python", "web", "networking"],
)

print(built_url)


# =============================================================================
# 30. MODIFYING EXISTING QUERY PARAMETERS
# =============================================================================

print_section("30. MODIFYING EXISTING QUERY PARAMETERS")


def update_query_parameter(
    url: str,
    key: str,
    value: str,
) -> str:
    """
    Replace all occurrences of a query parameter with one new value.

    Existing parameter ordering is mostly preserved except for replacement
    behavior.
    """
    result = urlparse(url)

    pairs = parse_qsl(
        result.query,
        keep_blank_values=True,
    )

    updated_pairs = [
        (existing_key, existing_value)
        for existing_key, existing_value in pairs
        if existing_key != key
    ]

    updated_pairs.append((key, value))

    updated_query = urlencode(updated_pairs)

    return result._replace(query=updated_query).geturl()


original = "https://example.com/search?q=python&page=1&page=2"

updated = update_query_parameter(
    original,
    "page",
    "5",
)

print("Original:", original)
print("Updated:", updated)


# =============================================================================
# 31. REMOVING QUERY PARAMETERS
# =============================================================================

print_section("31. REMOVING QUERY PARAMETERS")


def remove_query_parameter(url: str, key: str) -> str:
    """
    Remove all query parameters with the specified key.
    """
    result = urlparse(url)

    pairs = parse_qsl(
        result.query,
        keep_blank_values=True,
    )

    filtered_pairs = [
        (existing_key, existing_value)
        for existing_key, existing_value in pairs
        if existing_key != key
    ]

    updated_query = urlencode(filtered_pairs)

    return result._replace(query=updated_query).geturl()


original = (
    "https://example.com/products?"
    "category=books&page=2&tracking=abc123"
)

cleaned = remove_query_parameter(
    original,
    "tracking",
)

print("Original:", original)
print("Cleaned:", cleaned)


# =============================================================================
# 32. QUERY PARAMETER ORDERING
# =============================================================================

print_section("32. QUERY PARAMETER ORDERING")

# Query parameter ordering may or may not matter.
#
# Some applications interpret:
#
# a=1&b=2
#
# and:
#
# b=2&a=1
#
# identically.
#
# Others can treat order as meaningful.
#
# Therefore sorting parameters for normalization should only be done when the
# application explicitly defines ordering as irrelevant.

ordered_query = [
    ("first", "1"),
    ("second", "2"),
    ("first", "3"),
]

print(urlencode(ordered_query))


# =============================================================================
# 33. FRAGMENTS ARE DISTINCT FROM QUERIES
# =============================================================================

print_section("33. QUERY VS FRAGMENT")

value = "https://example.com/page?search=python#installation"

result = urlparse(value)

print("Query:", result.query)
print("Fragment:", result.fragment)

# Conceptual distinction:
#
# Query:
#   Often participates in resource selection by the server.
#
# Fragment:
#   Identifies a location or subresource from the perspective of the client.
#
# Exact behavior depends on protocols and applications.


# =============================================================================
# 34. URI REFERENCES WITHOUT A SCHEME
# =============================================================================

print_section("34. REFERENCES WITHOUT A SCHEME")

references_without_scheme = [
    "//example.com/path",
    "/absolute-path",
    "relative-path",
    "../parent-path",
    "?query=value",
    "#fragment",
]

for reference in references_without_scheme:
    result = urlparse(reference)

    print(
        f"{reference!r}\n"
        f"  scheme={result.scheme!r}\n"
        f"  netloc={result.netloc!r}\n"
        f"  path={result.path!r}\n"
        f"  query={result.query!r}\n"
        f"  fragment={result.fragment!r}"
    )


# =============================================================================
# 35. SCHEME-RELATIVE REFERENCES
# =============================================================================

print_section("35. SCHEME-RELATIVE REFERENCES")

# A reference such as:
#
# //example.com/resource
#
# specifies an authority but omits the scheme.
#
# The scheme may be inherited from a base context.

base_https = "https://origin.example/page"
scheme_relative = "//cdn.example/library.js"

print(urljoin(base_https, scheme_relative))


# =============================================================================
# 36. INTERNATIONALIZED DOMAIN NAMES
# =============================================================================

print_section("36. INTERNATIONALIZED DOMAIN NAMES")

# Internationalized domain names can contain non-ASCII characters.
#
# DNS-compatible forms commonly use an ASCII representation based on IDNA.
#
# Python can encode Unicode domain names using the "idna" codec.

unicode_domain = "münich.example"

try:
    ascii_domain = unicode_domain.encode("idna").decode("ascii")

    print("Unicode domain:", unicode_domain)
    print("IDNA ASCII form:", ascii_domain)

except UnicodeError as error:
    print("IDNA conversion failed:", error)


# =============================================================================
# 37. URLS ARE NOT FILESYSTEM PATHS
# =============================================================================

print_section("37. URL PATHS VS FILESYSTEM PATHS")

# URL paths use '/' as their separator.
#
# Operating-system filesystem paths may use platform-specific conventions.
#
# Do not use generic filesystem path utilities to manipulate web URLs.

web_url = "https://example.com/a/b/c"

print("Web URL:", web_url)

# Correct URL-oriented operations use urllib.parse.
print(
    "Modified URL:",
    urljoin(web_url + "/", "../d"),
)


# =============================================================================
# 38. PARSING MALFORMED OR AMBIGUOUS INPUT
# =============================================================================

print_section("38. MALFORMED OR AMBIGUOUS INPUT")

inputs = [
    "example.com/path",
    "https://example.com",
    "https:///missing-host",
    "http://example.com:bad-port",
    "://missing-scheme",
]

for value in inputs:
    print("\nInput:", repr(value))

    try:
        result = urlparse(value)

        print("Parsed:", result)
        print("Hostname:", result.hostname)

        try:
            print("Port:", result.port)
        except ValueError as error:
            print("Port error:", error)

    except ValueError as error:
        print("Parsing error:", error)


# =============================================================================
# 39. URL PARSING IS NOT URL REACHABILITY
# =============================================================================

print_section("39. PARSING VS REACHABILITY")

# A syntactically valid URL does not guarantee that:
#
# - DNS resolves
# - the server exists
# - the server is reachable
# - the resource exists
# - authentication succeeds
# - TLS validation succeeds
#
# Parsing is syntax analysis.
# Network access requires separate network operations.

candidate = "https://example.com/resource"

print(
    f"{candidate} can be parsed, but parsing alone does not verify "
    "that the resource is reachable."
)


# =============================================================================
# 40. SAFE REDIRECTION VALIDATION
# =============================================================================

print_section("40. SAFE REDIRECTION VALIDATION")

# Applications often accept a "next" or "redirect" parameter.
#
# A dangerous implementation may redirect users to an attacker-controlled
# external website.


def is_safe_redirect(
    destination: str,
    allowed_hosts: set[str],
) -> bool:
    """
    Allow:
    - relative paths
    - absolute HTTP/HTTPS URLs whose host is explicitly allowed

    Reject:
    - other schemes
    - unknown hosts
    - malformed ports
    """
    try:
        result = urlparse(destination)

        if result.scheme:
            if result.scheme.lower() not in {"http", "https"}:
                return False

            if not result.hostname:
                return False

            _ = result.port

            return result.hostname.lower() in {
                host.lower()
                for host in allowed_hosts
            }

        if result.netloc:
            return False

        return result.path.startswith("/")

    except ValueError:
        return False


allowed = {
    "example.com",
    "www.example.com",
}

redirect_candidates = [
    "/dashboard",
    "/account/settings",
    "https://example.com/profile",
    "https://attacker.example/login",
    "//attacker.example/login",
    "javascript:alert(1)",
]

for candidate in redirect_candidates:
    print(
        f"{candidate!r} -> "
        f"{is_safe_redirect(candidate, allowed)}"
    )


# =============================================================================
# 41. SSRF-RELATED CONSIDERATIONS
# =============================================================================

print_section("41. SERVER-SIDE REQUEST CONSIDERATIONS")

# Server-Side Request Forgery (SSRF) risks can occur when a server fetches a URL
# supplied by an untrusted user.
#
# A simplistic rule such as:
#
# "The URL starts with https://"
#
# is not sufficient protection.
#
# A production system may need:
#
# - scheme allowlists
# - hostname allowlists
# - DNS resolution controls
# - checks for private and loopback IP addresses
# - redirect restrictions
# - connection timeouts
# - response size limits
# - network-layer controls


def is_public_ip_address(host: str) -> bool:
    """
    Return True when a literal IP address is globally routable enough for this
    educational demonstration.

    Domain names require DNS resolution, which is outside this standard-library
    syntax example.
    """
    try:
        address = ipaddress.ip_address(host)

        return address.is_global

    except ValueError:
        return False


ip_examples = [
    "127.0.0.1",
    "192.168.1.1",
    "10.0.0.5",
    "8.8.8.8",
    "::1",
]

for host in ip_examples:
    print(host, "-> public:", is_public_ip_address(host))


# =============================================================================
# 42. USERINFO AND HOST CONFUSION
# =============================================================================

print_section("42. USERINFO AND HOST CONFUSION")

# The '@' symbol separates user information from the host.
#
# Consider:
#
# https://trusted.example@attacker.example/path
#
# The host is attacker.example, not trusted.example.

confusing_url = "https://trusted.example@attacker.example/path"

result = urlparse(confusing_url)

print("URL:", confusing_url)
print("Username:", result.username)
print("Host:", result.hostname)


# =============================================================================
# 43. HOST COMPARISON
# =============================================================================

print_section("43. HOST COMPARISON")


def same_host(url_a: str, url_b: str) -> bool:
    """
    Compare normalized hostnames.

    This compares hostnames only, not schemes, ports, paths, or resources.
    """
    first = urlparse(url_a).hostname
    second = urlparse(url_b).hostname

    if first is None or second is None:
        return False

    return first.lower() == second.lower()


print(
    same_host(
        "https://EXAMPLE.com/path",
        "http://example.COM/other",
    )
)


# =============================================================================
# 44. SAME ORIGIN CONCEPT
# =============================================================================

print_section("44. SAME ORIGIN")

# In web security, an origin is commonly defined using:
#
# scheme + host + port
#
# Examples:
#
# https://example.com
# https://example.com:443
#
# may represent the same effective conventional HTTPS origin.
#
# http://example.com
#
# has a different scheme and therefore a different origin from HTTPS.


def origin(url: str) -> tuple[str, str, int | None]:
    """
    Return a simplified origin tuple using conventional default ports.
    """
    result = urlparse(url)

    if not result.scheme or not result.hostname:
        raise ValueError("Absolute URL with scheme and host required")

    return (
        result.scheme.lower(),
        result.hostname.lower(),
        effective_port(result),
    )


origin_examples = [
    "https://example.com",
    "https://example.com:443",
    "http://example.com",
    "https://example.com:8443",
]

for value in origin_examples:
    print(value, "->", origin(value))


# =============================================================================
# 45. CACHE KEYS AND URL DIFFERENCES
# =============================================================================

print_section("45. URLS AND CACHING")

# Small URL differences can create distinct cache keys:
#
# /product?id=1
# /product?id=2
#
# Tracking parameters can also cause cache fragmentation:
#
# /page?utm_source=a
# /page?utm_source=b
#
# Removing parameters is only safe when they do not affect resource behavior.

tracking_parameters = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
}


def remove_known_tracking_parameters(url: str) -> str:
    """
    Remove selected tracking parameters while preserving all others.
    """
    result = urlparse(url)

    pairs = parse_qsl(
        result.query,
        keep_blank_values=True,
    )

    filtered = [
        (key, value)
        for key, value in pairs
        if key.lower() not in tracking_parameters
    ]

    return result._replace(
        query=urlencode(filtered)
    ).geturl()


tracking_url = (
    "https://example.com/article?"
    "id=42&utm_source=newsletter&utm_medium=email"
)

print("Original:", tracking_url)
print(
    "Without known tracking parameters:",
    remove_known_tracking_parameters(tracking_url),
)


# =============================================================================
# 46. QUERY PARAMETERS SHOULD NOT BE PARSED MANUALLY
# =============================================================================

print_section("46. MANUAL QUERY PARSING PROBLEMS")

# Manual splitting is error-prone because:
#
# - values can contain encoded separators
# - keys can repeat
# - blank values exist
# - percent-encoding must be decoded correctly

manual_example = "q=python%20url&filter=a%26b"

print("Raw query:", manual_example)

print(
    "Naive split:",
    [part.split("=") for part in manual_example.split("&")],
)

print(
    "Correct parser result:",
    parse_qsl(manual_example),
)


# =============================================================================
# 47. COMMON MISTAKE: STRING CONCATENATION
# =============================================================================

print_section("47. UNSAFE STRING CONCATENATION")

search_term = "Python & security"

unsafe_url = (
    "https://example.com/search?q="
    + search_term
)

safe_url = (
    "https://example.com/search?"
    + urlencode({"q": search_term})
)

print("Unsafe:", unsafe_url)
print("Safe:", safe_url)


# =============================================================================
# 48. COMMON MISTAKE: DOUBLE ENCODING
# =============================================================================

print_section("48. DOUBLE ENCODING")

original_text = "hello world"

encoded_once = quote(original_text)
encoded_twice = quote(encoded_once)

print("Original:", original_text)
print("Encoded once:", encoded_once)
print("Encoded twice:", encoded_twice)

# Double encoding can occur when already-encoded data is passed to an encoder
# without understanding whether the input is raw text or encoded URL content.


# =============================================================================
# 49. COMMON MISTAKE: ENCODING AN ENTIRE URL AS ONE VALUE
# =============================================================================

print_section("49. COMPONENT-AWARE ENCODING")

full_url = "https://example.com/search?q=python data"

wrong = quote(full_url)

print("Original URL:", full_url)
print("Encoding entire URL:", wrong)

# Encoding should generally be applied to data placed inside a specific component,
# such as a path segment or query value.

correct = (
    "https://example.com/search?"
    + urlencode({"q": "python data"})
)

print("Component-aware construction:", correct)


# =============================================================================
# 50. PATH SEGMENT ENCODING
# =============================================================================

print_section("50. PATH SEGMENT ENCODING")

product_name = "Python & Data"

# A path segment may need encoding.
encoded_segment = quote(
    product_name,
    safe="",
)

product_url = (
    "https://example.com/products/"
    + encoded_segment
)

print("Product name:", product_name)
print("Encoded segment:", encoded_segment)
print("URL:", product_url)


# =============================================================================
# 51. DATACLASS-BASED URL BUILDER
# =============================================================================

print_section("51. DATACLASS URL BUILDER")


@dataclass
class WebURL:
    """
    A small structured URL builder for HTTP and HTTPS URLs.
    """

    scheme: str
    host: str
    path: str = "/"
    port: int | None = None
    query_parameters: list[tuple[str, str]] | None = None
    fragment: str = ""

    def build(self) -> str:
        scheme = self.scheme.lower()

        if scheme not in {"http", "https"}:
            raise ValueError("Unsupported web scheme")

        if not self.host:
            raise ValueError("Host cannot be empty")

        host = self.host.lower()

        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        netloc = host

        if self.port is not None:
            if not 1 <= self.port <= 65535:
                raise ValueError("Port must be between 1 and 65535")

            netloc += f":{self.port}"

        path = self.path

        if not path.startswith("/"):
            path = "/" + path

        query = ""

        if self.query_parameters:
            query = urlencode(self.query_parameters)

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                query,
                self.fragment,
            )
        )


api_url = WebURL(
    scheme="HTTPS",
    host="API.EXAMPLE.COM",
    path="v1/products",
    port=443,
    query_parameters=[
        ("category", "books"),
        ("limit", "20"),
    ],
    fragment="results",
)

print(api_url.build())


# =============================================================================
# 52. PRACTICAL API URL EXAMPLE
# =============================================================================

print_section("52. PRACTICAL API URL CONSTRUCTION")

api_base = "https://api.example.com/v1/search"

api_parameters = {
    "query": "Python URL parsing",
    "page": 1,
    "page_size": 20,
    "include_metadata": "true",
}

api_request_url = (
    api_base
    + "?"
    + urlencode(api_parameters)
)

print(api_request_url)


# =============================================================================
# 53. PAGINATION URL GENERATION
# =============================================================================

print_section("53. PAGINATION URLS")


def pagination_urls(
    base_url: str,
    pages: int,
) -> list[str]:
    """
    Generate URLs with page parameters.
    """
    if pages < 1:
        raise ValueError("pages must be at least 1")

    result = urlparse(base_url)

    existing_pairs = parse_qsl(
        result.query,
        keep_blank_values=True,
    )

    existing_pairs = [
        pair
        for pair in existing_pairs
        if pair[0] != "page"
    ]

    urls: list[str] = []

    for page_number in range(1, pages + 1):
        query_pairs = existing_pairs + [
            ("page", str(page_number))
        ]

        page_url = result._replace(
            query=urlencode(query_pairs)
        ).geturl()

        urls.append(page_url)

    return urls


for page_url in pagination_urls(
    "https://example.com/products?category=books",
    3,
):
    print(page_url)


# =============================================================================
# 54. URL DEBUGGING HELPER
# =============================================================================

print_section("54. URL DEBUGGING HELPER")


def explain_url(url: str) -> dict[str, Any]:
    """
    Return a structured dictionary useful for debugging URL interpretation.
    """
    result = urlparse(url)

    try:
        port = result.port
    except ValueError as error:
        port = f"Invalid port: {error}"

    return {
        "original": url,
        "scheme": result.scheme,
        "netloc": result.netloc,
        "username": result.username,
        "password_present": result.password is not None,
        "hostname": result.hostname,
        "port": port,
        "path": result.path,
        "params": result.params,
        "query": result.query,
        "query_pairs": parse_qsl(
            result.query,
            keep_blank_values=True,
        ),
        "fragment": result.fragment,
    }


debug_information = explain_url(
    "https://user:secret@example.com:8443/"
    "products?q=python&page=2#details"
)

for key, value in debug_information.items():
    print(f"{key}: {value}")


# =============================================================================
# 55. REDACTING SENSITIVE URL INFORMATION
# =============================================================================

print_section("55. REDACTING SENSITIVE URL INFORMATION")

# URLs may contain sensitive information in:
#
# - userinfo
# - query parameters
#
# Logging complete URLs can accidentally expose secrets.


SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "api_key",
    "key",
    "password",
    "secret",
}


def redact_url(url: str) -> str:
    """
    Redact selected sensitive information before logging.

    Passwords in userinfo are replaced.
    Sensitive query parameter values are replaced.

    This function is an example. Production systems should define redaction
    rules based on their application's actual data model.
    """
    result = urlparse(url)

    hostname = result.hostname or ""

    if ":" in hostname:
        hostname = f"[{hostname}]"

    netloc = hostname

    if result.username:
        if result.password is not None:
            userinfo = f"{quote(result.username, safe='')}:[REDACTED]"
        else:
            userinfo = quote(
                result.username,
                safe="",
            )

        netloc = userinfo + "@" + netloc

    try:
        if result.port is not None:
            netloc += f":{result.port}"
    except ValueError:
        pass

    query_pairs = parse_qsl(
        result.query,
        keep_blank_values=True,
    )

    redacted_pairs = []

    for key, value in query_pairs:
        if key.lower() in SENSITIVE_QUERY_KEYS:
            redacted_pairs.append(
                (key, "[REDACTED]")
            )
        else:
            redacted_pairs.append(
                (key, value)
            )

    return result._replace(
        netloc=netloc,
        query=urlencode(redacted_pairs),
    ).geturl()


sensitive_url = (
    "https://alice:secret@example.com/api?"
    "query=python&api_key=abc123&token=xyz"
)

print("Original:", sensitive_url)
print("Redacted:", redact_url(sensitive_url))


# =============================================================================
# 56. PRODUCTION URL DESIGN PRINCIPLES
# =============================================================================

print_section("56. PRODUCTION URL DESIGN PRINCIPLES")

principles = [
    "Use meaningful, stable resource paths.",
    "Encode user-controlled values using component-aware functions.",
    "Avoid secrets in URLs.",
    "Validate URLs according to application requirements.",
    "Use explicit scheme allowlists when fetching remote URLs.",
    "Treat redirects and user-supplied URLs as security-sensitive.",
    "Do not assume parsed URLs are reachable or trustworthy.",
    "Preserve repeated query parameters when application semantics require them.",
    "Avoid unnecessary URL normalization that can change meaning.",
    "Redact sensitive values before logging.",
]

for number, principle in enumerate(principles, start=1):
    print(f"{number}. {principle}")


# =============================================================================
# 57. COMPREHENSIVE URL ANALYZER
# =============================================================================

print_section("57. COMPREHENSIVE URL ANALYZER")


@dataclass(frozen=True)
class URLAnalysis:
    """
    Structured analysis of a URI reference.
    """

    original: str
    scheme: str
    host: str | None
    host_type: str | None
    port: int | None
    effective_port: int | None
    path: str
    path_segments: tuple[str, ...]
    query_pairs: tuple[tuple[str, str], ...]
    fragment: str
    is_absolute: bool
    is_web_url: bool


def analyze_url(url: str) -> URLAnalysis:
    """
    Analyze a URL or URI reference.

    This function demonstrates how multiple URL concepts can be combined into
    one structured operation.
    """
    result = urlparse(url)

    try:
        explicit_port = result.port
    except ValueError as error:
        raise ValueError(
            f"Malformed URL port: {error}"
        ) from error

    host_type: str | None = None

    if result.hostname is not None:
        host_type = classify_host(
            result.hostname
        )

    is_absolute = bool(
        result.scheme
    )

    is_web_url = (
        result.scheme.lower()
        in {"http", "https"}
        and result.hostname is not None
    )

    return URLAnalysis(
        original=url,
        scheme=result.scheme,
        host=result.hostname,
        host_type=host_type,
        port=explicit_port,
        effective_port=effective_port(result),
        path=result.path,
        path_segments=tuple(
            path_segments(result.path)
        ),
        query_pairs=tuple(
            parse_qsl(
                result.query,
                keep_blank_values=True,
            )
        ),
        fragment=result.fragment,
        is_absolute=is_absolute,
        is_web_url=is_web_url,
    )


analysis_target = (
    "https://api.example.com:8443/"
    "v1/products/books?"
    "category=programming&tag=python&tag=web#reviews"
)

analysis = analyze_url(
    analysis_target
)

print(analysis)


# =============================================================================
# 58. URL EQUIVALENCE TRADE-OFFS
# =============================================================================

print_section("58. URL EQUIVALENCE")

# Determining whether two URLs refer to the "same" resource is difficult.
#
# Syntactic equality:
#
# URL A == URL B
#
# is simple but strict.
#
# Semantic equivalence depends on server and application behavior.
#
# For example:
#
# https://example.com
# https://example.com/
#
# may refer to the same resource but this is not guaranteed by simple string
# comparison.

url_a = "https://example.com"
url_b = "https://example.com/"

print("String equality:", url_a == url_b)

print(
    "Normalized equality:",
    normalize_basic_http_url(url_a)
    == normalize_basic_http_url(url_b),
)


# =============================================================================
# 59. PERFORMANCE CONSIDERATIONS
# =============================================================================

print_section("59. PERFORMANCE CONSIDERATIONS")

# URL parsing with urllib.parse is lightweight for ordinary application use.
#
# Performance considerations become more important when processing:
#
# - very large URL datasets
# - crawlers
# - log analysis pipelines
# - API gateways
# - high-volume security filtering
#
# Practical considerations:
#
# - Parse once when multiple components are required.
# - Avoid repeatedly reconstructing identical URLs.
# - Preserve structured components where possible.
# - Apply expensive DNS or network validation only when necessary.
# - Define normalization rules carefully to avoid incorrect cache merging.

large_sample = [
    f"https://example.com/items/{index}?page={index % 10}"
    for index in range(5)
]

for value in large_sample:
    result = urlparse(value)
    print(
        result.path,
        "->",
        parse_qs(result.query),
    )


# =============================================================================
# 60. FINAL INTEGRATED EXAMPLE
# =============================================================================

print_section("60. FINAL INTEGRATED EXAMPLE")


def prepare_external_web_url(
    url: str,
    allowed_schemes: set[str] | None = None,
) -> str:
    """
    Perform a conservative preparation process for an external web URL.

    Steps:
    1. Validate basic syntax.
    2. Restrict schemes.
    3. Require a host.
    4. Access the port to detect malformed values.
    5. Normalize scheme and host.
    6. Preserve path, query, and fragment.

    This is an educational utility, not a universal production security policy.
    """
    if allowed_schemes is None:
        allowed_schemes = {"http", "https"}

    if not isinstance(url, str):
        raise TypeError("URL must be a string")

    if not url or url != url.strip():
        raise ValueError("URL cannot be empty or contain surrounding whitespace")

    result = urlparse(url)

    scheme = result.scheme.lower()

    if scheme not in {
        allowed_scheme.lower()
        for allowed_scheme in allowed_schemes
    }:
        raise ValueError(
            f"Scheme {scheme!r} is not allowed"
        )

    if result.hostname is None:
        raise ValueError("URL must contain a hostname")

    port = result.port

    if port is not None:
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")

    return normalize_basic_http_url(
        url
    )


urls_to_prepare = [
    "HTTPS://Example.COM:443/products?q=Python%20URLs#details",
    "http://localhost:8080/api/status",
    "ftp://example.com/file.txt",
]

for candidate in urls_to_prepare:
    print("\nCandidate:", candidate)

    try:
        prepared = prepare_external_web_url(
            candidate
        )
        print("Prepared:", prepared)

    except (
        TypeError,
        ValueError,
    ) as error:
        print("Rejected:", error)


print_section("END OF SCRIPT")

print(
    "The examples demonstrated URI and URL concepts, component parsing, "
    "encoding, query handling, fragments, relative resolution, validation, "
    "normalization, security concerns, and practical URL construction."
)

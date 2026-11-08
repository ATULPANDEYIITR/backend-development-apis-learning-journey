#!/usr/bin/env python3
"""
HTTPS and TLS: Encryption, Certificates, TLS Handshake and HTTPS Termination.

Uses only the Python standard library.
Supports:
- TLS version and cipher-suite inspection
- Certificate inspection and hostname validation
- HTTPS endpoint verification
- TLS handshake execution
- Certificate expiry monitoring
- HTTPS termination policy evaluation
- Structured audit reports
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import tempfile
import unittest

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class TLSVersion(Enum):
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class CertificateStatus(Enum):
    VALID = "valid"
    EXPIRED = "expired"
    EXPIRING = "expiring"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class TerminationMode(Enum):
    EDGE = "edge"
    REVERSE_PROXY = "reverse_proxy"
    PASSTHROUGH = "passthrough"


@dataclass
class TLSConfiguration:
    hostname: str
    port: int = 443
    minimum_version: TLSVersion = TLSVersion.TLS_1_2
    verify_certificate: bool = True
    verify_hostname: bool = True
    timeout: float = 5.0

    def validate(self) -> None:
        if not self.hostname or not self.hostname.strip():
            raise ValueError("Hostname cannot be empty")

        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535")

        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")

        if self.verify_hostname and not self.verify_certificate:
            raise ValueError(
                "Hostname verification requires certificate verification"
            )


@dataclass
class CertificateInfo:
    subject: str
    issuer: str
    not_before: str
    not_after: str
    subject_alt_names: list[str]
    days_remaining: int
    status: CertificateStatus


@dataclass
class TLSHandshakeResult:
    hostname: str
    port: int
    success: bool
    tls_version: Optional[str] = None
    cipher_suite: Optional[str] = None
    certificate: Optional[CertificateInfo] = None
    error: Optional[str] = None


@dataclass
class TerminationPolicy:
    mode: TerminationMode
    frontend_tls_required: bool = True
    backend_tls_required: bool = True
    minimum_backend_version: TLSVersion = TLSVersion.TLS_1_2
    forward_proto_header: bool = True
    secure_cookies: bool = True

    def validate(self) -> list[str]:
        problems = []

        if not self.frontend_tls_required:
            problems.append("Frontend HTTPS is not enforced")

        if self.mode == TerminationMode.PASSTHROUGH:
            if self.forward_proto_header:
                problems.append(
                    "Application-level forwarded protocol header "
                    "is not configured by this termination layer"
                )

        if self.mode in (
            TerminationMode.EDGE,
            TerminationMode.REVERSE_PROXY,
        ):
            if not self.backend_tls_required:
                problems.append(
                    "Backend communication is unencrypted"
                )

        if not self.secure_cookies:
            problems.append("Secure cookie protection is disabled")

        return problems


class TLSInspector:
    """Performs real TLS connections using certificate verification."""

    def __init__(self, configuration: TLSConfiguration):
        configuration.validate()
        self.configuration = configuration

    def create_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH
        )

        context.minimum_version = (
            ssl.TLSVersion.TLSv1_2
            if self.configuration.minimum_version == TLSVersion.TLS_1_2
            else ssl.TLSVersion.TLSv1_3
        )

        if self.configuration.verify_certificate:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = (
                self.configuration.verify_hostname
            )
        else:
            # Diagnostic-only mode. Never use for production traffic.
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        return context

    @staticmethod
    def extract_certificate(
        certificate: dict,
        expiry_warning_days: int = 30,
    ) -> CertificateInfo:

        if expiry_warning_days < 0:
            raise ValueError("Expiry warning days cannot be negative")

        expiry = datetime.strptime(
            certificate["notAfter"],
            "%b %d %H:%M:%S %Y %Z",
        ).replace(tzinfo=timezone.utc)

        remaining = (
            expiry - datetime.now(timezone.utc)
        ).days

        if remaining < 0:
            status = CertificateStatus.EXPIRED
        elif remaining <= expiry_warning_days:
            status = CertificateStatus.EXPIRING
        else:
            status = CertificateStatus.VALID

        return CertificateInfo(
            subject=str(certificate.get("subject", ())),
            issuer=str(certificate.get("issuer", ())),
            not_before=certificate.get("notBefore", ""),
            not_after=certificate["notAfter"],
            subject_alt_names=[
                value
                for kind, value in certificate.get(
                    "subjectAltName", ()
                )
                if kind in ("DNS", "IP Address")
            ],
            days_remaining=remaining,
            status=status,
        )

    def inspect(self) -> TLSHandshakeResult:
        config = self.configuration

        try:
            context = self.create_context()

            with socket.create_connection(
                (config.hostname, config.port),
                timeout=config.timeout,
            ) as raw_socket:

                with context.wrap_socket(
                    raw_socket,
                    server_hostname=(
                        config.hostname
                        if config.verify_hostname
                        else None
                    ),
                ) as tls_socket:

                    certificate = tls_socket.getpeercert()
                    cipher = tls_socket.cipher()

                    if not cipher:
                        raise ssl.SSLError(
                            "No negotiated cipher suite"
                        )

                    certificate_info = None

                    if certificate:
                        certificate_info = self.extract_certificate(
                            certificate
                        )

                    return TLSHandshakeResult(
                        hostname=config.hostname,
                        port=config.port,
                        success=True,
                        tls_version=tls_socket.version(),
                        cipher_suite=cipher[0],
                        certificate=certificate_info,
                    )

        except (
            OSError,
            ssl.SSLError,
            ValueError,
            KeyError,
        ) as error:

            return TLSHandshakeResult(
                hostname=config.hostname,
                port=config.port,
                success=False,
                error=f"{type(error).__name__}: {error}",
            )


@dataclass
class EndpointAudit:
    results: list[TLSHandshakeResult] = field(
        default_factory=list
    )

    def add(self, result: TLSHandshakeResult) -> None:
        self.results.append(result)

    def summary(self) -> dict:
        successful = [
            item for item in self.results if item.success
        ]

        return {
            "total_endpoints": len(self.results),
            "successful_handshakes": len(successful),
            "failed_handshakes": (
                len(self.results) - len(successful)
            ),
            "tls_versions": sorted({
                item.tls_version
                for item in successful
                if item.tls_version
            }),
            "cipher_suites": sorted({
                item.cipher_suite
                for item in successful
                if item.cipher_suite
            }),
        }

    def to_json(self) -> str:
        def serialize(value):
            if isinstance(value, Enum):
                return value.value
            return value

        return json.dumps(
            asdict(self),
            default=serialize,
            indent=2,
        )


def evaluate_termination(
    policy: TerminationPolicy,
) -> dict:
    problems = policy.validate()

    return {
        "mode": policy.mode.value,
        "compliant": not problems,
        "violations": problems,
    }


def save_report(
    audit: EndpointAudit,
    output_path: str,
) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Avoid partially written reports.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary.write(audit.to_json())
        temporary_path = Path(temporary.name)

    try:
        temporary_path.replace(destination)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


class TLSInspectorTests(unittest.TestCase):

    def test_configuration_validation(self):
        with self.assertRaises(ValueError):
            TLSConfiguration(hostname="").validate()

        with self.assertRaises(ValueError):
            TLSConfiguration(
                hostname="example.com",
                verify_certificate=False,
                verify_hostname=True,
            ).validate()

    def test_termination_policy(self):
        policy = TerminationPolicy(
            mode=TerminationMode.REVERSE_PROXY,
            backend_tls_required=False,
        )

        violations = policy.validate()

        self.assertTrue(
            any("Backend" in item for item in violations)
        )

    def test_valid_termination_policy(self):
        policy = TerminationPolicy(
            mode=TerminationMode.EDGE,
            backend_tls_required=True,
        )

        self.assertEqual(policy.validate(), [])

    def test_empty_audit(self):
        audit = EndpointAudit()
        self.assertEqual(
            audit.summary()["total_endpoints"],
            0,
        )


def run_tests() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TLSInspectorTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HTTPS and TLS endpoint security auditor"
    )

    parser.add_argument(
        "hosts",
        nargs="*",
        help="HTTPS hostnames to inspect",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=443,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--minimum-tls",
        choices=["1.2", "1.3"],
        default="1.2",
    )

    parser.add_argument(
        "--output",
        default="tls_audit.json",
    )

    parser.add_argument(
        "--insecure-diagnostic",
        action="store_true",
        help="Disable certificate verification for diagnostics only",
    )

    parser.add_argument(
        "--test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    if not args.hosts:
        parser.error("Provide at least one hostname or use --test")

    audit = EndpointAudit()

    minimum = (
        TLSVersion.TLS_1_3
        if args.minimum_tls == "1.3"
        else TLSVersion.TLS_1_2
    )

    for hostname in dict.fromkeys(args.hosts):
        configuration = TLSConfiguration(
            hostname=hostname,
            port=args.port,
            minimum_version=minimum,
            verify_certificate=not args.insecure_diagnostic,
            verify_hostname=not args.insecure_diagnostic,
            timeout=args.timeout,
        )

        result = TLSInspector(configuration).inspect()
        audit.add(result)

        print(json.dumps(
            asdict(result),
            default=lambda value: (
                value.value
                if isinstance(value, Enum)
                else value
            ),
            indent=2,
        ))

    print("\nAUDIT SUMMARY")
    print(json.dumps(audit.summary(), indent=2))

    save_report(audit, args.output)
    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()

"""
Network diagnostics: DNS resolution and TCP reachability.

All network I/O uses explicit timeouts.  Failures are classified into
distinct categories (NXDOMAIN, SERVFAIL, timeout, connection-refused, etc.)
so that the caller can provide accurate remediation advice.
"""

from __future__ import annotations

import logging
import socket
from enum import StrEnum

import dns.exception
import dns.resolver

from faultline.models import DNS_TIMEOUT_SECONDS, TCP_TIMEOUT_SECONDS, CheckResult, Severity

logger = logging.getLogger(__name__)


class DNSFailureReason(StrEnum):
    NXDOMAIN = "nxdomain"
    SERVFAIL = "servfail"
    NO_ANSWER = "no_answer"
    TIMEOUT = "timeout"
    OTHER = "other"


class TCPFailureReason(StrEnum):
    REFUSED = "connection_refused"
    TIMEOUT = "timeout"
    NO_ROUTE = "no_route"
    OTHER = "other"


def check_dns(
    hostname: str,
    record_type: str = "A",
    timeout: float = DNS_TIMEOUT_SECONDS,
    nameserver: str | None = None,
) -> CheckResult:
    """
    Resolve *hostname* and return a :class:`CheckResult`.

    :param hostname: FQDN to resolve.
    :param record_type: DNS record type (default ``"A"``).
    :param timeout: resolver timeout in seconds.
    :param nameserver: explicit nameserver IP; defaults to system resolver.
    """
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    if nameserver:
        resolver.nameservers = [nameserver]

    evidence: dict = {
        "hostname": hostname,
        "record_type": record_type,
        "nameserver": nameserver or "system default",
    }

    try:
        answers = resolver.resolve(hostname, record_type)
        records = [r.to_text() for r in answers]
        evidence["records"] = records
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.OK,
            message=f"DNS OK — {hostname} resolves to: {', '.join(records)}",
            evidence=evidence,
        )

    except dns.resolver.NXDOMAIN:
        evidence["failure_reason"] = DNSFailureReason.NXDOMAIN.value
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.CRITICAL,
            message=f"DNS CRITICAL — {hostname} does not exist (NXDOMAIN).",
            evidence=evidence,
            remediation=(
                f"The domain '{hostname}' was not found. "
                "Check for typos, confirm DNS records exist, "
                "and verify zone delegation is correct."
            ),
        )

    except dns.resolver.NoAnswer:
        evidence["failure_reason"] = DNSFailureReason.NO_ANSWER.value
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.WARNING,
            message=f"DNS WARNING — {hostname} exists but has no {record_type} record.",
            evidence=evidence,
            remediation=(
                f"The domain '{hostname}' exists but returned no {record_type} records. "
                f"Verify that the expected {record_type} record has been published."
            ),
        )

    except dns.resolver.NoNameservers:
        evidence["failure_reason"] = DNSFailureReason.SERVFAIL.value
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.CRITICAL,
            message=f"DNS CRITICAL — No nameservers could be reached for {hostname}.",
            evidence=evidence,
            remediation=(
                "All nameservers failed. "
                "Check /etc/resolv.conf and network connectivity to the DNS servers."
            ),
        )

    except dns.exception.Timeout:
        evidence["failure_reason"] = DNSFailureReason.TIMEOUT.value
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.CRITICAL,
            message=f"DNS CRITICAL — resolution timed out after {timeout}s for {hostname}.",
            evidence=evidence,
            remediation=(
                "DNS queries are timing out. "
                "Test with `dig @8.8.8.8 " + hostname + "` to isolate the resolver. "
                "Check firewall rules on UDP/TCP port 53."
            ),
        )

    except Exception as exc:
        evidence["failure_reason"] = DNSFailureReason.OTHER.value
        evidence["exception"] = str(exc)
        return CheckResult(
            check_name=f"dns:{hostname}",
            severity=Severity.ERROR,
            message=f"DNS ERROR — unexpected failure resolving {hostname}: {exc}",
            evidence=evidence,
            remediation="Inspect the exception details and check resolver configuration.",
        )


def check_tcp(
    host: str,
    port: int,
    timeout: float = TCP_TIMEOUT_SECONDS,
) -> CheckResult:
    """
    Attempt a TCP connection to *host*:*port* within *timeout* seconds.

    :param host: target hostname or IP address.
    :param port: target TCP port.
    :param timeout: connection timeout in seconds.
    """
    evidence: dict = {"host": host, "port": port, "timeout_seconds": timeout}

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return CheckResult(
            check_name=f"tcp:{host}:{port}",
            severity=Severity.OK,
            message=f"TCP OK — {host}:{port} is reachable.",
            evidence=evidence,
        )

    except ConnectionRefusedError:
        evidence["failure_reason"] = TCPFailureReason.REFUSED.value
        return CheckResult(
            check_name=f"tcp:{host}:{port}",
            severity=Severity.CRITICAL,
            message=f"TCP CRITICAL — Connection refused to {host}:{port}.",
            evidence=evidence,
            remediation=(
                f"The target {host}:{port} actively refused the connection. "
                "Confirm the service is running and bound to the expected interface. "
                f"Check firewall rules: `ss -tlnp | grep {port}`."
            ),
        )

    except TimeoutError:
        evidence["failure_reason"] = TCPFailureReason.TIMEOUT.value
        return CheckResult(
            check_name=f"tcp:{host}:{port}",
            severity=Severity.CRITICAL,
            message=f"TCP CRITICAL — Connection to {host}:{port} timed out after {timeout}s.",
            evidence=evidence,
            remediation=(
                f"Connection to {host}:{port} is silently dropped. "
                "Likely a firewall or routing issue. "
                f"Try `traceroute {host}` and inspect iptables/nftables rules."
            ),
        )

    except OSError as exc:
        # Covers EHOSTUNREACH, ENETUNREACH, socket.gaierror, etc.
        reason = (
            TCPFailureReason.NO_ROUTE
            if "No route to host" in str(exc) or "Network unreachable" in str(exc)
            else TCPFailureReason.OTHER
        )
        evidence["failure_reason"] = reason.value
        evidence["exception"] = str(exc)
        return CheckResult(
            check_name=f"tcp:{host}:{port}",
            severity=Severity.CRITICAL,
            message=f"TCP CRITICAL — Cannot reach {host}:{port}: {exc}",
            evidence=evidence,
            remediation=(
                f"Network error reaching {host}:{port}. "
                "Check routing tables (`ip route show`) and interface status (`ip link`)."
            ),
        )

    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_name=f"tcp:{host}:{port}",
            severity=Severity.ERROR,
            message=f"TCP ERROR — unexpected failure connecting to {host}:{port}: {exc}",
            evidence=evidence,
        )


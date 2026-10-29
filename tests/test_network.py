"""
Tests for network diagnostics (DNS and TCP).

All tests use mocks — no real network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import dns.exception
import dns.resolver

from faultline.checks.network import check_dns, check_tcp
from faultline.models import Severity

# ---------------------------------------------------------------------------
# DNS tests
# ---------------------------------------------------------------------------

class TestDNSOK:
    def test_ok_severity(self, mocker):
        answer = MagicMock()
        answer.to_text.return_value = "93.184.216.34"
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            return_value=[answer],
        )
        result = check_dns("example.com")
        assert result.severity == Severity.OK

    def test_ok_message_contains_ip(self, mocker):
        answer = MagicMock()
        answer.to_text.return_value = "1.2.3.4"
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            return_value=[answer],
        )
        result = check_dns("example.com")
        assert "1.2.3.4" in result.message

    def test_ok_evidence_has_records(self, mocker):
        answer = MagicMock()
        answer.to_text.return_value = "1.2.3.4"
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            return_value=[answer],
        )
        result = check_dns("example.com")
        assert "records" in result.evidence
        assert result.evidence["records"] == ["1.2.3.4"]


class TestDNSFailures:
    def test_nxdomain_is_critical(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.resolver.NXDOMAIN(),
        )
        result = check_dns("nonexistent.invalid")
        assert result.severity == Severity.CRITICAL
        assert result.evidence["failure_reason"] == "nxdomain"

    def test_no_answer_is_warning(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.resolver.NoAnswer(),
        )
        result = check_dns("example.com", record_type="AAAA")
        assert result.severity == Severity.WARNING

    def test_no_nameservers_is_critical(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.resolver.NoNameservers(),
        )
        result = check_dns("example.com")
        assert result.severity == Severity.CRITICAL

    def test_timeout_is_critical(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.exception.Timeout(),
        )
        result = check_dns("slow.example.com", timeout=1.0)
        assert result.severity == Severity.CRITICAL
        assert result.evidence["failure_reason"] == "timeout"

    def test_check_name_includes_hostname(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.resolver.NXDOMAIN(),
        )
        result = check_dns("myhostname.example.com")
        assert "myhostname.example.com" in result.check_name

    def test_nxdomain_remediation_not_empty(self, mocker):
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver.resolve",
            side_effect=dns.resolver.NXDOMAIN(),
        )
        result = check_dns("bad.example.com")
        assert result.remediation != ""

    def test_custom_nameserver_set(self, mocker):
        """Ensure the nameserver parameter is applied to the resolver."""
        resolver_instance = MagicMock()
        answer = MagicMock()
        answer.to_text.return_value = "1.1.1.1"
        resolver_instance.resolve.return_value = [answer]
        mocker.patch(
            "faultline.checks.network.dns.resolver.Resolver",
            return_value=resolver_instance,
        )
        result = check_dns("example.com", nameserver="8.8.8.8")
        assert resolver_instance.nameservers == ["8.8.8.8"]
        assert result.severity == Severity.OK


# ---------------------------------------------------------------------------
# TCP tests
# ---------------------------------------------------------------------------

class TestTCPOK:
    def test_ok_severity(self, mocker):
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mocker.patch("socket.create_connection", return_value=mock_sock)

        result = check_tcp("google.com", 443)
        assert result.severity == Severity.OK

    def test_ok_message(self, mocker):
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mocker.patch("socket.create_connection", return_value=mock_sock)

        result = check_tcp("google.com", 443)
        assert "reachable" in result.message


class TestTCPFailures:
    def test_connection_refused_is_critical(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=ConnectionRefusedError("refused"),
        )
        result = check_tcp("localhost", 9999)
        assert result.severity == Severity.CRITICAL
        assert result.evidence["failure_reason"] == "connection_refused"

    def test_timeout_is_critical(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=TimeoutError("timed out"),
        )
        result = check_tcp("10.0.0.1", 80)
        assert result.severity == Severity.CRITICAL
        assert result.evidence["failure_reason"] == "timeout"

    def test_no_route_classified(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=OSError("No route to host"),
        )
        result = check_tcp("192.168.99.99", 22)
        assert result.severity == Severity.CRITICAL
        assert result.evidence["failure_reason"] == "no_route"

    def test_check_name_includes_host_and_port(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=ConnectionRefusedError(),
        )
        result = check_tcp("db.example.com", 5432)
        assert "db.example.com" in result.check_name
        assert "5432" in result.check_name

    def test_refused_remediation_mentions_ss(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=ConnectionRefusedError(),
        )
        result = check_tcp("db.example.com", 5432)
        assert "ss" in result.remediation

    def test_evidence_records_timeout(self, mocker):
        mocker.patch(
            "socket.create_connection",
            side_effect=TimeoutError(),
        )
        result = check_tcp("slow.host", 8080, timeout=3.0)
        assert result.evidence["timeout_seconds"] == 3.0


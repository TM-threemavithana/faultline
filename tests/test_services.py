"""
Tests for service status diagnostics.
"""

from __future__ import annotations

from faultline.checks.services import check_services
from faultline.models import Severity


class TestSystemctlUnavailable:
    def test_warns_when_no_systemctl(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=False)
        results = check_services(["sshd"])
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING

    def test_warning_message_mentions_systemctl(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=False)
        results = check_services(["sshd"])
        assert "systemctl" in results[0].message

    def test_warning_evidence_contains_requested_services(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=False)
        results = check_services(["nginx", "mysql"])
        assert results[0].evidence["requested_services"] == ["nginx", "mysql"]

    def test_remediation_mentions_wsl2(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=False)
        results = check_services(["sshd"])
        assert "WSL2" in results[0].remediation

    def test_empty_services_returns_empty(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=True)
        results = check_services([])
        assert results == []


class TestSystemctlAvailable:
    def _make_query(self, mocker, state: str):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=True)
        mocker.patch(
            "faultline.checks.services._query_service",
            return_value=(state, state),
        )

    def test_active_service_is_ok(self, mocker):
        self._make_query(mocker, "active")
        results = check_services(["sshd"])
        assert results[0].severity == Severity.OK

    def test_inactive_service_is_warning(self, mocker):
        self._make_query(mocker, "inactive")
        results = check_services(["nginx"])
        assert results[0].severity == Severity.WARNING

    def test_failed_service_is_critical(self, mocker):
        self._make_query(mocker, "failed")
        results = check_services(["nginx"])
        assert results[0].severity == Severity.CRITICAL

    def test_failed_remediation_mentions_journalctl(self, mocker):
        self._make_query(mocker, "failed")
        results = check_services(["myapp"])
        assert "journalctl" in results[0].remediation

    def test_unknown_state_is_unknown_severity(self, mocker):
        self._make_query(mocker, "unknown")
        results = check_services(["oddservice"])
        assert results[0].severity == Severity.UNKNOWN

    def test_check_name_includes_service_name(self, mocker):
        self._make_query(mocker, "active")
        results = check_services(["postgresql"])
        assert "postgresql" in results[0].check_name

    def test_multiple_services_produce_multiple_results(self, mocker):
        mocker.patch("faultline.checks.services._systemctl_available", return_value=True)
        states = {"sshd": ("active", "active"), "nginx": ("failed", "failed")}
        mocker.patch(
            "faultline.checks.services._query_service",
            side_effect=lambda name: states[name],
        )
        results = check_services(["sshd", "nginx"])
        assert len(results) == 2
        severities = {r.check_name: r.severity for r in results}
        assert severities["service:sshd"] == Severity.OK
        assert severities["service:nginx"] == Severity.CRITICAL


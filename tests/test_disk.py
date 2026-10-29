"""
Tests for disk usage diagnostics.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from faultline.checks.disk import check_disk_usage
from faultline.models import Severity


class TestDiskUsageOK:
    def test_ok_severity_below_warning(self, mock_disk_usage_ok):
        results = check_disk_usage(paths=["/"])
        assert len(results) == 1
        assert results[0].severity == Severity.OK

    def test_ok_message_contains_percent(self, mock_disk_usage_ok):
        results = check_disk_usage(paths=["/"])
        assert "50.0%" in results[0].message

    def test_ok_evidence_keys(self, mock_disk_usage_ok):
        results = check_disk_usage(paths=["/"])
        ev = results[0].evidence
        assert "total_gb" in ev
        assert "used_gb" in ev
        assert "free_gb" in ev
        assert "used_pct" in ev

    def test_ok_no_remediation(self, mock_disk_usage_ok):
        results = check_disk_usage(paths=["/"])
        assert results[0].remediation == ""


class TestDiskUsageWarning:
    def test_warning_severity(self, mocker):
        usage = MagicMock()
        usage.total = 100 * 1024**3
        usage.used = 83 * 1024**3
        usage.free = 17 * 1024**3
        usage.percent = 83.0
        mocker.patch("psutil.disk_usage", return_value=usage)

        results = check_disk_usage(paths=["/"], warning_pct=80.0, critical_pct=90.0)
        assert results[0].severity == Severity.WARNING

    def test_warning_has_remediation(self, mocker):
        usage = MagicMock()
        usage.percent = 83.0
        usage.total = usage.used = usage.free = 1024**3
        mocker.patch("psutil.disk_usage", return_value=usage)

        results = check_disk_usage(paths=["/"], warning_pct=80.0, critical_pct=90.0)
        assert results[0].remediation != ""


class TestDiskUsageCritical:
    def test_critical_severity(self, mock_disk_usage_critical):
        results = check_disk_usage(paths=["/"], warning_pct=80.0, critical_pct=90.0)
        assert results[0].severity == Severity.CRITICAL

    def test_critical_message(self, mock_disk_usage_critical):
        results = check_disk_usage(paths=["/"], warning_pct=80.0, critical_pct=90.0)
        assert "CRITICAL" in results[0].message

    def test_critical_remediation_contains_du(self, mock_disk_usage_critical):
        results = check_disk_usage(paths=["/"], warning_pct=80.0, critical_pct=90.0)
        assert "du" in results[0].remediation


class TestDiskUsageErrors:
    def test_permission_error_returns_error_severity(self, mocker):
        mocker.patch("psutil.disk_usage", side_effect=PermissionError("denied"))
        results = check_disk_usage(paths=["/secret"])
        assert results[0].severity == Severity.ERROR
        assert "Permission" in results[0].message

    def test_file_not_found_returns_error_severity(self, mocker):
        mocker.patch("psutil.disk_usage", side_effect=FileNotFoundError("gone"))
        results = check_disk_usage(paths=["/nonexistent"])
        assert results[0].severity == Severity.ERROR

    def test_multiple_paths_independent(self, mocker):
        """Each path should produce its own CheckResult."""
        call_count = 0
        def fake_usage(path):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.total = 100 * 1024**3
            m.used = 50 * 1024**3
            m.free = 50 * 1024**3
            m.percent = 50.0
            return m

        mocker.patch("psutil.disk_usage", side_effect=fake_usage)
        results = check_disk_usage(paths=["/", "/home", "/var"])
        assert len(results) == 3
        assert call_count == 3

    def test_check_name_includes_mount(self, mock_disk_usage_ok):
        results = check_disk_usage(paths=["/data"])
        assert "/data" in results[0].check_name

    def test_custom_thresholds_respected(self, mocker):
        """Warning at 50% if threshold is set to 40%."""
        usage = MagicMock()
        usage.percent = 50.0
        usage.total = usage.used = usage.free = 1024**3
        mocker.patch("psutil.disk_usage", return_value=usage)

        results = check_disk_usage(paths=["/"], warning_pct=40.0, critical_pct=70.0)
        assert results[0].severity == Severity.WARNING

    def test_auto_detect_partitions(self, mocker, mock_disk_usage_ok):
        p1 = MagicMock(mountpoint="/", opts="rw,relatime", fstype="ext4")
        p2 = MagicMock(mountpoint="/data", opts="rw,relatime", fstype="ext4")
        mocker.patch("psutil.disk_partitions", return_value=[p1, p2])

        results = check_disk_usage(paths=None)
        assert len(results) == 2
        names = [r.check_name for r in results]
        assert "disk_usage:/" in names
        assert "disk_usage:/data" in names

    def test_auto_detect_skips_readonly_mounts(self, mocker, mock_disk_usage_ok):
        p_rw = MagicMock(mountpoint="/", opts="rw,relatime", fstype="ext4")
        p_ro = MagicMock(mountpoint="/usr/src/headers", opts="ro,relatime", fstype="ext4")
        p_squash = MagicMock(mountpoint="/snap/core", opts="ro", fstype="squashfs")
        mocker.patch("psutil.disk_partitions", return_value=[p_rw, p_ro, p_squash])

        results = check_disk_usage(paths=None)
        assert len(results) == 1
        assert results[0].check_name == "disk_usage:/"


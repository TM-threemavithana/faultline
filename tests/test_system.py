"""
Tests for CPU and memory diagnostics.
"""

from __future__ import annotations

from faultline.checks.system import check_cpu_usage, check_memory_usage
from faultline.models import Severity


class TestCPUUsage:
    def test_ok_severity(self, mock_cpu_ok):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert result.severity == Severity.OK

    def test_ok_evidence_keys(self, mock_cpu_ok):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert "cpu_percent" in result.evidence
        assert "logical_cores" in result.evidence

    def test_warning_severity(self, mock_cpu_warning):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert result.severity == Severity.WARNING

    def test_warning_message(self, mock_cpu_warning):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert "WARNING" in result.message

    def test_warning_remediation_mentions_top(self, mock_cpu_warning):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert "top" in result.remediation

    def test_custom_threshold(self, mocker):
        mocker.patch("psutil.cpu_percent", return_value=60.0)
        mocker.patch("psutil.cpu_count", return_value=2)
        # At 60% with warning at 55%, should be WARNING
        result = check_cpu_usage(warning_pct=55.0, sample_interval=0)
        assert result.severity == Severity.WARNING

    def test_check_name(self, mock_cpu_ok):
        result = check_cpu_usage(warning_pct=85.0, sample_interval=0)
        assert result.check_name == "cpu_usage"


class TestMemoryUsage:
    def test_ok_severity(self, mock_memory_ok):
        result = check_memory_usage(warning_pct=85.0, critical_pct=95.0)
        assert result.severity == Severity.OK

    def test_ok_has_swap_evidence(self, mock_memory_ok):
        result = check_memory_usage()
        assert "swap_used_pct" in result.evidence

    def test_critical_severity(self, mock_memory_critical):
        result = check_memory_usage(warning_pct=85.0, critical_pct=95.0)
        assert result.severity == Severity.CRITICAL

    def test_critical_message(self, mock_memory_critical):
        result = check_memory_usage(warning_pct=85.0, critical_pct=95.0)
        assert "CRITICAL" in result.message

    def test_critical_remediation_mentions_ps(self, mock_memory_critical):
        result = check_memory_usage(warning_pct=85.0, critical_pct=95.0)
        assert "ps" in result.remediation

    def test_warning_severity(self, mocker):
        from unittest.mock import MagicMock
        vm = MagicMock()
        vm.total = 16 * 1024**3
        vm.available = 3 * 1024**3
        vm.percent = 88.0
        swap = MagicMock()
        swap.total = 4 * 1024**3
        swap.percent = 10.0
        mocker.patch("psutil.virtual_memory", return_value=vm)
        mocker.patch("psutil.swap_memory", return_value=swap)

        result = check_memory_usage(warning_pct=85.0, critical_pct=95.0)
        assert result.severity == Severity.WARNING

    def test_check_name(self, mock_memory_ok):
        result = check_memory_usage()
        assert result.check_name == "memory_usage"


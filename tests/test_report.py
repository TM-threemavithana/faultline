"""
Tests for incident report generation.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from faultline.models import CheckResult, Severity
from faultline.report.builder import (
    build_report,
    format_report_text,
    report_to_json,
    save_report,
)


def make_result(name: str, severity: Severity, message: str = "test") -> CheckResult:
    return CheckResult(check_name=name, severity=severity, message=message)


class TestBuildReport:
    def test_overall_severity_worst(self):
        results = [
            make_result("a", Severity.OK),
            make_result("b", Severity.WARNING),
            make_result("c", Severity.CRITICAL),
        ]
        report = build_report(results)
        assert report["overall_severity"] == Severity.CRITICAL.value

    def test_critical_overrides_unknown_and_error(self):
        results = [
            make_result("a", Severity.CRITICAL),
            make_result("b", Severity.UNKNOWN),
            make_result("c", Severity.ERROR),
            make_result("d", Severity.WARNING),
        ]
        report = build_report(results)
        assert report["overall_severity"] == Severity.CRITICAL.value

    def test_warning_overrides_unknown(self):
        results = [
            make_result("a", Severity.WARNING),
            make_result("b", Severity.UNKNOWN),
        ]
        report = build_report(results)
        assert report["overall_severity"] == Severity.WARNING.value

    def test_overall_severity_all_ok(self):
        results = [make_result("a", Severity.OK), make_result("b", Severity.OK)]
        report = build_report(results)
        assert report["overall_severity"] == Severity.OK.value

    def test_empty_results_unknown(self):
        report = build_report([])
        assert report["overall_severity"] == Severity.UNKNOWN.value

    def test_total_checks_count(self):
        results = [make_result(f"check{i}", Severity.OK) for i in range(5)]
        report = build_report(results)
        assert report["total_checks"] == 5

    def test_suppress_ok_results(self):
        results = [
            make_result("ok_check", Severity.OK),
            make_result("warn_check", Severity.WARNING),
        ]
        report = build_report(results, include_ok=False)
        names = [c["check_name"] for c in report["checks"]]
        assert "ok_check" not in names
        assert "warn_check" in names

    def test_include_ok_results_by_default(self):
        results = [make_result("ok_check", Severity.OK)]
        report = build_report(results, include_ok=True)
        assert len(report["checks"]) == 1

    def test_severity_counts_accurate(self):
        results = [
            make_result("a", Severity.OK),
            make_result("b", Severity.OK),
            make_result("c", Severity.WARNING),
            make_result("d", Severity.CRITICAL),
        ]
        report = build_report(results)
        assert report["severity_summary"]["ok"] == 2
        assert report["severity_summary"]["warning"] == 1
        assert report["severity_summary"]["critical"] == 1

    def test_report_has_generated_at(self):
        report = build_report([])
        assert "generated_at" in report
        # Should be parseable as ISO 8601
        datetime.fromisoformat(report["generated_at"])

    def test_report_has_host_and_platform(self):
        report = build_report([])
        assert "host" in report
        assert "platform" in report

    def test_custom_title(self):
        report = build_report([], title="My Custom Title")
        assert report["report_title"] == "My Custom Title"

    def test_no_credentials_in_report(self):
        """Ensure no environment variables that could be credentials appear."""
        import os
        # Put a fake credential in the environment
        os.environ["FAKE_SECRET_TOKEN"] = "super-secret-value"
        try:
            results = [make_result("a", Severity.OK)]
            report = build_report(results)
            report_str = json.dumps(report)
            assert "super-secret-value" not in report_str
        finally:
            del os.environ["FAKE_SECRET_TOKEN"]


class TestFormatReportText:
    def test_text_contains_severity(self):
        results = [make_result("a", Severity.CRITICAL, "disk full")]
        report = build_report(results)
        text = format_report_text(report)
        assert "CRITICAL" in text

    def test_text_contains_check_name(self):
        results = [make_result("disk_usage:/", Severity.WARNING)]
        report = build_report(results)
        text = format_report_text(report)
        assert "disk_usage:/" in text

    def test_text_contains_report_title(self):
        report = build_report([], title="Test Report Title")
        text = format_report_text(report)
        assert "Test Report Title" in text


class TestReportToJSON:
    def test_valid_json(self):
        report = build_report([make_result("a", Severity.OK)])
        json_str = report_to_json(report)
        parsed = json.loads(json_str)
        assert "overall_severity" in parsed

    def test_json_indented(self):
        report = build_report([])
        json_str = report_to_json(report, indent=4)
        assert "\n    " in json_str  # 4-space indent


class TestSaveReport:
    def test_save_json(self, tmp_path):
        report = build_report([make_result("a", Severity.OK)])
        out = str(tmp_path / "report.json")
        save_report(report, out, fmt="json")
        with open(out) as f:
            parsed = json.load(f)
        assert "overall_severity" in parsed

    def test_save_text(self, tmp_path):
        report = build_report([make_result("a", Severity.CRITICAL)])
        out = str(tmp_path / "report.txt")
        save_report(report, out, fmt="text")
        with open(out) as f:
            content = f.read()
        assert "CRITICAL" in content

    def test_unsupported_format_raises(self, tmp_path):
        report = build_report([])
        with pytest.raises(ValueError, match="Unsupported"):
            save_report(report, str(tmp_path / "out.xml"), fmt="xml")


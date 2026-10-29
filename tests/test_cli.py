"""
Tests for the CLI layer (click runner, exit codes, JSON output).
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from faultline.cli import EXIT_CRITICAL, EXIT_ERROR, EXIT_OK, EXIT_WARNING, main
from faultline.models import CheckResult, Severity


def make_ok_result(name: str = "test") -> CheckResult:
    return CheckResult(check_name=name, severity=Severity.OK, message="all good")


def make_critical_result(name: str = "test") -> CheckResult:
    return CheckResult(check_name=name, severity=Severity.CRITICAL, message="bad thing")


def make_warning_result(name: str = "test") -> CheckResult:
    return CheckResult(check_name=name, severity=Severity.WARNING, message="watch out")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def patch_all_ok(mocker):
    """Patch all check functions to return a single OK result."""
    ok = make_ok_result()
    mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
    mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
    mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
    mocker.patch("faultline.cli.check_services", return_value=[])
    mocker.patch("faultline.cli.check_dns", return_value=ok)
    mocker.patch("faultline.cli.check_tcp", return_value=ok)
    return ok


@pytest.fixture
def patch_critical(mocker):
    """Patch all check functions to return a single CRITICAL result."""
    crit = make_critical_result()
    mocker.patch("faultline.cli.check_disk_usage", return_value=[crit])
    mocker.patch("faultline.cli.check_cpu_usage", return_value=crit)
    mocker.patch("faultline.cli.check_memory_usage", return_value=crit)
    return crit


class TestCLIRunExitCodes:
    def test_all_ok_exits_zero(self, runner, patch_all_ok):
        result = runner.invoke(main, ["run"])
        assert result.exit_code == EXIT_OK

    def test_critical_exits_two(self, runner, patch_critical):
        result = runner.invoke(main, ["run"])
        assert result.exit_code == EXIT_CRITICAL

    def test_warning_exits_one(self, runner, mocker):
        warn = make_warning_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[warn])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=warn)
        mocker.patch("faultline.cli.check_memory_usage", return_value=warn)
        result = runner.invoke(main, ["run"])
        assert result.exit_code == EXIT_WARNING


class TestCLIJSONOutput:
    def test_json_flag_outputs_json(self, runner, patch_all_ok):
        result = runner.invoke(main, ["run", "--json"])
        assert result.exit_code == EXIT_OK
        parsed = json.loads(result.output)
        assert "overall_severity" in parsed
        assert "checks" in parsed

    def test_json_overall_severity_ok(self, runner, patch_all_ok):
        result = runner.invoke(main, ["run", "--json"])
        parsed = json.loads(result.output)
        assert parsed["overall_severity"] == "ok"

    def test_json_overall_severity_critical(self, runner, patch_critical):
        result = runner.invoke(main, ["run", "--json"])
        parsed = json.loads(result.output)
        assert parsed["overall_severity"] == "critical"


class TestCLIFlags:
    def test_disk_path_passed_to_check(self, runner, mocker):
        ok = make_ok_result()
        mock_disk = mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        runner.invoke(main, ["run", "--disk", "/data", "--disk", "/home"])
        mock_disk.assert_called_once_with(
            paths=["/data", "/home"],
            warning_pct=80.0,
            critical_pct=90.0,
        )

    def test_service_flag_passed(self, runner, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        mock_svc = mocker.patch("faultline.cli.check_services", return_value=[ok])
        runner.invoke(main, ["run", "--service", "nginx", "--service", "sshd"])
        mock_svc.assert_called_once_with(["nginx", "sshd"])

    def test_dns_flag_invoked(self, runner, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        mock_dns = mocker.patch("faultline.cli.check_dns", return_value=ok)
        runner.invoke(main, ["run", "--dns", "google.com"])
        mock_dns.assert_called_once_with("google.com")

    def test_tcp_flag_invoked(self, runner, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        mock_tcp = mocker.patch("faultline.cli.check_tcp", return_value=ok)
        runner.invoke(main, ["run", "--tcp", "google.com:443"])
        mock_tcp.assert_called_once_with("google.com", 443)

    def test_invalid_tcp_target_exits_error(self, runner, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        result = runner.invoke(main, ["run", "--tcp", "badformat"])
        assert result.exit_code == EXIT_ERROR

    def test_no_ok_flag_suppresses_ok(self, runner, mocker):
        ok = make_ok_result("disk_usage:/")
        warn = make_warning_result("cpu_usage")
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=warn)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        result = runner.invoke(main, ["run", "--no-ok", "--json"])
        parsed = json.loads(result.output)
        check_names = [c["check_name"] for c in parsed["checks"]]
        assert "disk_usage:/" not in check_names
        assert "cpu_usage" in check_names

    def test_save_report_creates_file(self, runner, mocker, tmp_path):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)
        out = str(tmp_path / "test_report.json")
        runner.invoke(main, ["run", "--output", out])
        assert (tmp_path / "test_report.json").exists()
        with open(out) as f:
            parsed = json.load(f)
        assert "overall_severity" in parsed


class TestCLIVersion:
    def test_version_option(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIReportCommand:
    def test_report_cmd_renders_json(self, runner, tmp_path, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)

        report_file = str(tmp_path / "r.json")
        runner.invoke(main, ["run", "--output", report_file])

        result = runner.invoke(main, ["report", report_file])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "overall_severity" in parsed

    def test_report_cmd_text_flag(self, runner, tmp_path, mocker):
        ok = make_ok_result()
        mocker.patch("faultline.cli.check_disk_usage", return_value=[ok])
        mocker.patch("faultline.cli.check_cpu_usage", return_value=ok)
        mocker.patch("faultline.cli.check_memory_usage", return_value=ok)

        report_file = str(tmp_path / "r.json")
        runner.invoke(main, ["run", "--output", report_file])

        result = runner.invoke(main, ["report", report_file, "--text"])
        assert result.exit_code == 0
        assert "Faultline Diagnostic Report" in result.output


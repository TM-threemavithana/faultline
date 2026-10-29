"""
Linux service status diagnostics.

Queries systemd via `systemctl is-active` for each requested service.
Gracefully handles environments where systemd is unavailable (e.g. WSL1,
containers, non-systemd distros).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Literal

from faultline.models import CheckResult, Severity

logger = logging.getLogger(__name__)

ServiceState = Literal["active", "inactive", "failed", "activating", "unknown"]


def _systemctl_available() -> bool:
    """Return True if systemctl is on PATH and responds to --version."""
    if shutil.which("systemctl") is None:
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _query_service(name: str) -> tuple[ServiceState, str]:
    """
    Return (state, raw_output) for the named systemd service.

    *state* will be one of the :data:`ServiceState` literals.
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        state = result.stdout.strip()
        if state not in ("active", "inactive", "failed", "activating"):
            state = "unknown"
        return state, result.stdout.strip()  # type: ignore[return-value]
    except subprocess.TimeoutExpired:
        return "unknown", "timeout"
    except OSError as exc:
        return "unknown", str(exc)


def check_services(services: list[str]) -> list[CheckResult]:
    """
    Check the runtime status of each named Linux service.

    If systemd is unavailable the check returns a single WARNING result
    explaining why service inspection is skipped — rather than raising an
    exception or returning a misleading OK.

    :param services: list of systemd service unit names (e.g. ``["sshd", "nginx"]``).
    """
    if not services:
        return []

    if not _systemctl_available():
        return [
            CheckResult(
                check_name="services",
                severity=Severity.WARNING,
                message=(
                    "systemctl is not available in this environment "
                    "(WSL2 without systemd, container, or non-systemd distro). "
                    "Service checks skipped."
                ),
                evidence={"requested_services": services},
                remediation=(
                    "To enable systemd in WSL2 add `[boot] systemd=true` to /etc/wsl.conf "
                    "and restart the WSL instance."
                ),
            )
        ]

    results: list[CheckResult] = []
    for svc in services:
        state, raw = _query_service(svc)
        evidence = {"service": svc, "state": state, "raw_output": raw}

        if state == "active":
            results.append(
                CheckResult(
                    check_name=f"service:{svc}",
                    severity=Severity.OK,
                    message=f"Service '{svc}' is active.",
                    evidence=evidence,
                )
            )
        elif state == "inactive":
            results.append(
                CheckResult(
                    check_name=f"service:{svc}",
                    severity=Severity.WARNING,
                    message=f"Service '{svc}' is inactive (not running).",
                    evidence=evidence,
                    remediation=f"Start the service: `sudo systemctl start {svc}`",
                )
            )
        elif state == "failed":
            results.append(
                CheckResult(
                    check_name=f"service:{svc}",
                    severity=Severity.CRITICAL,
                    message=f"Service '{svc}' has FAILED.",
                    evidence=evidence,
                    remediation=(
                        f"Inspect logs: `journalctl -u {svc} -n 50 --no-pager`. "
                        f"Attempt restart: `sudo systemctl restart {svc}`."
                    ),
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"service:{svc}",
                    severity=Severity.UNKNOWN,
                    message=f"Service '{svc}' status is unknown (state={state!r}).",
                    evidence=evidence,
                    remediation=f"Check manually: `systemctl status {svc}`",
                )
            )

    return results

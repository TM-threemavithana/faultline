"""
CPU and memory diagnostics.

Samples CPU utilisation over a short interval and inspects virtual-memory
stats via psutil.  All calls are read-only.
"""

from __future__ import annotations

import logging

import psutil

from faultline.models import (
    CPU_WARNING_PCT,
    CPU_WARNING_SECONDS,
    MEM_CRITICAL_PCT,
    MEM_WARNING_PCT,
    CheckResult,
    Severity,
)

logger = logging.getLogger(__name__)


def check_cpu_usage(
    warning_pct: float = CPU_WARNING_PCT,
    sample_interval: float = CPU_WARNING_SECONDS,
) -> CheckResult:
    """
    Sample CPU utilisation over *sample_interval* seconds and classify it.

    :param warning_pct: utilisation percentage that triggers WARNING.
    :param sample_interval: seconds to block while sampling CPU.
    """
    try:
        pct = psutil.cpu_percent(interval=sample_interval)
        count_logical = psutil.cpu_count(logical=True)
        count_physical = psutil.cpu_count(logical=False)
    except Exception as exc:  # pragma: no cover
        return CheckResult(
            check_name="cpu_usage",
            severity=Severity.ERROR,
            message=f"Failed to sample CPU: {exc}",
            remediation="Ensure psutil can access /proc/stat.",
        )

    evidence = {
        "cpu_percent": pct,
        "logical_cores": count_logical,
        "physical_cores": count_physical,
    }

    if pct >= warning_pct:
        return CheckResult(
            check_name="cpu_usage",
            severity=Severity.WARNING,
            message=f"CPU usage WARNING: {pct:.1f}% (threshold {warning_pct}%)",
            evidence=evidence,
            remediation=(
                "High CPU detected. Identify the top consumer: `top -bn1 | head -20` "
                "or `ps aux --sort=-%cpu | head -10`. "
                "Investigate runaway processes or schedule resource-intensive tasks off-peak."
            ),
        )

    return CheckResult(
        check_name="cpu_usage",
        severity=Severity.OK,
        message=f"CPU usage OK: {pct:.1f}%",
        evidence=evidence,
    )


def check_memory_usage(
    warning_pct: float = MEM_WARNING_PCT,
    critical_pct: float = MEM_CRITICAL_PCT,
) -> CheckResult:
    """
    Inspect virtual memory usage and classify it.

    :param warning_pct: percentage that triggers WARNING.
    :param critical_pct: percentage that triggers CRITICAL.
    """
    try:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
    except Exception as exc:  # pragma: no cover
        return CheckResult(
            check_name="memory_usage",
            severity=Severity.ERROR,
            message=f"Failed to read memory stats: {exc}",
            remediation="Ensure psutil can access /proc/meminfo.",
        )

    pct = vm.percent
    evidence = {
        "total_gb": round(vm.total / 1024**3, 2),
        "available_gb": round(vm.available / 1024**3, 2),
        "used_pct": pct,
        "swap_total_gb": round(swap.total / 1024**3, 2),
        "swap_used_pct": swap.percent,
    }

    if pct >= critical_pct:
        return CheckResult(
            check_name="memory_usage",
            severity=Severity.CRITICAL,
            message=f"Memory usage CRITICAL: {pct:.1f}% (threshold {critical_pct}%)",
            evidence=evidence,
            remediation=(
                "System is critically low on memory. "
                "Identify the top consumer: `ps aux --sort=-%mem | head -10`. "
                "Consider restarting non-essential services or adding swap."
            ),
        )

    if pct >= warning_pct:
        return CheckResult(
            check_name="memory_usage",
            severity=Severity.WARNING,
            message=f"Memory usage WARNING: {pct:.1f}% (threshold {warning_pct}%)",
            evidence=evidence,
            remediation=(
                "Memory is under pressure. "
                "Monitor memory trends: `vmstat -s`. "
                "Review recent deployments for memory leaks."
            ),
        )

    return CheckResult(
        check_name="memory_usage",
        severity=Severity.OK,
        message=f"Memory usage OK: {pct:.1f}%",
        evidence=evidence,
    )

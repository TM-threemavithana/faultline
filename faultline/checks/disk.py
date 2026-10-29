"""
Disk usage diagnostics.

Uses psutil to inspect mounted filesystems and compares usage against
configurable warning / critical thresholds.  Read-only; no writes made.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psutil

from faultline.models import (
    DISK_CRITICAL_PCT,
    DISK_WARNING_PCT,
    CheckResult,
    Severity,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def check_disk_usage(
    paths: list[str] | None = None,
    warning_pct: float = DISK_WARNING_PCT,
    critical_pct: float = DISK_CRITICAL_PCT,
) -> list[CheckResult]:
    """
    Check disk usage for each specified mount point (defaults to all local mounts).

    Returns one :class:`CheckResult` per partition checked.

    :param paths: explicit list of mount-point paths, or ``None`` for auto-detect.
    :param warning_pct: usage percentage that triggers a WARNING.
    :param critical_pct: usage percentage that triggers a CRITICAL.
    """
    results: list[CheckResult] = []

    if paths is None:
        try:
            partitions = psutil.disk_partitions(all=False)
            # Filter out read-only mounts in auto-detection to avoid false-positive alerts
            # on read-only system images (e.g. WSL2 kernel headers, snap packages, live media).
            rw = [
                p.mountpoint
                for p in partitions
                if "ro" not in p.opts.split(",") and p.fstype not in ("squashfs", "iso9660")
            ]
            paths = rw if rw else [p.mountpoint for p in partitions]
        except Exception as exc:  # pragma: no cover
            logger.warning("Cannot enumerate disk partitions: %s", exc)
            return [
                CheckResult(
                    check_name="disk_usage",
                    severity=Severity.ERROR,
                    message=f"Failed to enumerate partitions: {exc}",
                    remediation="Ensure psutil can access /proc/mounts.",
                )
            ]

    for mount in paths:
        try:
            usage = psutil.disk_usage(mount)
        except PermissionError as exc:
            results.append(
                CheckResult(
                    check_name=f"disk_usage:{mount}",
                    severity=Severity.ERROR,
                    message=f"Permission denied reading {mount}: {exc}",
                    remediation="Run with sufficient privileges to read all mount points.",
                )
            )
            continue
        except FileNotFoundError:
            results.append(
                CheckResult(
                    check_name=f"disk_usage:{mount}",
                    severity=Severity.ERROR,
                    message=f"Mount point not found: {mount}",
                    remediation="Verify the mount point exists and is accessible.",
                )
            )
            continue
        except Exception as exc:
            results.append(
                CheckResult(
                    check_name=f"disk_usage:{mount}",
                    severity=Severity.ERROR,
                    message=f"Unexpected error reading {mount}: {exc}",
                )
            )
            continue

        pct = usage.percent
        evidence = {
            "mount": mount,
            "total_gb": round(usage.total / 1024**3, 2),
            "used_gb": round(usage.used / 1024**3, 2),
            "free_gb": round(usage.free / 1024**3, 2),
            "used_pct": pct,
        }

        if pct >= critical_pct:
            sev = Severity.CRITICAL
            msg = f"Disk usage CRITICAL on {mount}: {pct:.1f}% used (threshold {critical_pct}%)"
            rem = (
                f"Disk at {mount} is nearly full. "
                "Identify and remove large files: `du -sh /* | sort -rh | head -20`. "
                "Consider archiving or expanding the volume."
            )
        elif pct >= warning_pct:
            sev = Severity.WARNING
            msg = f"Disk usage WARNING on {mount}: {pct:.1f}% used (threshold {warning_pct}%)"
            rem = (
                f"Disk at {mount} is filling up. "
                "Monitor trends and schedule cleanup before threshold is breached."
            )
        else:
            sev = Severity.OK
            msg = f"Disk usage OK on {mount}: {pct:.1f}% used"
            rem = ""

        results.append(
            CheckResult(
                check_name=f"disk_usage:{mount}",
                severity=sev,
                message=msg,
                evidence=evidence,
                remediation=rem,
            )
        )

    return results


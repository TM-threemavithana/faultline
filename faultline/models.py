"""
Shared types and constants used across all Faultline modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Ordered severity levels for diagnostic results."""

    OK = "ok"
    UNKNOWN = "unknown"
    WARNING = "warning"
    ERROR = "error"  # check itself failed (not the target system)
    CRITICAL = "critical"

    def __lt__(self, other: Severity) -> bool:  # noqa: D105
        order = [self.OK, self.UNKNOWN, self.WARNING, self.ERROR, self.CRITICAL]
        return order.index(self) < order.index(other)


@dataclass
class CheckResult:
    """The outcome of a single diagnostic check."""

    check_name: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "timestamp": self.timestamp.isoformat(),
        }


# Default thresholds (override via CLI flags or env vars in future versions)
DISK_WARNING_PCT: float = 80.0
DISK_CRITICAL_PCT: float = 90.0
CPU_WARNING_PCT: float = 85.0
CPU_WARNING_SECONDS: float = 1.0  # interval used for psutil cpu_percent sampling
MEM_WARNING_PCT: float = 85.0
MEM_CRITICAL_PCT: float = 95.0
TCP_TIMEOUT_SECONDS: float = 5.0
DNS_TIMEOUT_SECONDS: float = 5.0


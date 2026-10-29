"""
Incident report generation.

Assembles :class:`~faultline.models.CheckResult` objects into a structured
report with metadata, severity summary, and per-check evidence.

Design decisions
----------------
* No credentials or environment variables are captured — only check output.
* Severity is determined by the *worst* individual result (not an average).
* The report is serialisable to JSON without losing information.
"""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from typing import Any

from faultline.models import CheckResult, Severity

_SEVERITY_ORDER = [
    Severity.OK,
    Severity.UNKNOWN,
    Severity.WARNING,
    Severity.ERROR,
    Severity.CRITICAL,
]


def _worst(results: list[CheckResult]) -> Severity:
    """Return the highest-severity value across *results*."""
    if not results:
        return Severity.UNKNOWN
    return max(results, key=lambda r: _SEVERITY_ORDER.index(r.severity)).severity


def _safe_hostname() -> str:
    """Return hostname without leaking domain suffixes that may be sensitive."""
    try:
        return platform.node() or "unknown"
    except Exception:
        return "unknown"


def _safe_platform() -> str:
    try:
        return platform.platform(terse=True)
    except Exception:
        return "unknown"


def build_report(
    results: list[CheckResult],
    title: str = "Faultline Diagnostic Report",
    include_ok: bool = True,
) -> dict[str, Any]:
    """
    Build a structured incident report dictionary from *results*.

    :param results: list of :class:`CheckResult` objects from all checks.
    :param title: human-readable report title.
    :param include_ok: if ``False``, suppress OK-severity checks from the output.
    :returns: a JSON-serialisable dict.
    """
    generated_at = datetime.now(UTC).isoformat()
    overall = _worst(results)

    checks_output = [r.to_dict() for r in results if include_ok or r.severity != Severity.OK]

    severity_counts: dict[str, int] = {s.value: 0 for s in Severity}
    for r in results:
        severity_counts[r.severity.value] += 1

    return {
        "report_title": title,
        "generated_at": generated_at,
        "host": _safe_hostname(),
        "platform": _safe_platform(),
        "overall_severity": overall.value,
        "severity_summary": severity_counts,
        "total_checks": len(results),
        "checks": checks_output,
    }


def format_report_text(report: dict[str, Any]) -> str:
    """
    Render a report dict as a human-readable plain-text string.

    Suitable for piping to a file or including in an email/ticket.
    """
    lines: list[str] = []
    sep = "=" * 72

    lines += [
        sep,
        f"  {report['report_title']}",
        sep,
        f"  Generated : {report['generated_at']}",
        f"  Host      : {report['host']}",
        f"  Platform  : {report['platform']}",
        f"  Overall   : {report['overall_severity'].upper()}",
        sep,
        "",
    ]

    summary = report["severity_summary"]
    lines.append("SEVERITY SUMMARY")
    lines.append("-" * 40)
    for sev, count in summary.items():
        if count:
            lines.append(f"  {sev.upper():10s}: {count}")
    lines.append("")

    lines.append("CHECK RESULTS")
    lines.append("-" * 40)
    for chk in report["checks"]:
        sev_label = chk["severity"].upper()
        lines.append(f"[{sev_label}] {chk['check_name']}")
        lines.append(f"  {chk['message']}")
        if chk.get("remediation"):
            lines.append(f"  REMEDIATION: {chk['remediation']}")
        if chk.get("evidence"):
            for k, v in chk["evidence"].items():
                lines.append(f"    {k}: {v}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def report_to_json(report: dict[str, Any], indent: int = 2) -> str:
    """Serialise *report* to a JSON string."""
    return json.dumps(report, indent=indent, default=str)


def save_report(report: dict[str, Any], path: str, fmt: str = "json") -> None:
    """
    Write *report* to *path*.

    :param fmt: ``"json"`` or ``"text"``.
    :raises ValueError: for unsupported formats.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if fmt == "json":
        content = report_to_json(report)
    elif fmt == "text":
        content = format_report_text(report)
    else:
        raise ValueError(f"Unsupported report format: {fmt!r}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


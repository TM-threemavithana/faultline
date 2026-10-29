"""
report package — re-export convenience symbols.
"""

from faultline.report.builder import (
    build_report,
    format_report_text,
    report_to_json,
    save_report,
)

__all__ = ["build_report", "format_report_text", "report_to_json", "save_report"]

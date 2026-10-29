"""
Faultline CLI entry point.

Usage examples
--------------
  faultline run
  faultline run --disk / --disk /home --service nginx --service sshd
  faultline run --dns example.com --tcp google.com:443
  faultline run --json
  faultline run --output report.json
  faultline run --no-ok
"""

from __future__ import annotations

import sys

import click
from rich import box
from rich.console import Console
from rich.table import Table

from faultline import __version__
from faultline.checks import (
    check_cpu_usage,
    check_disk_usage,
    check_dns,
    check_memory_usage,
    check_services,
    check_tcp,
)
from faultline.models import CheckResult, Severity
from faultline.report.builder import (
    build_report,
    format_report_text,
    report_to_json,
    save_report,
)

console = Console(stderr=False)
err_console = Console(stderr=True)

# Map severity to rich colour tags
_SEVERITY_COLOUR: dict[Severity, str] = {
    Severity.OK: "green",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "bold red",
    Severity.ERROR: "red",
    Severity.UNKNOWN: "dim",
}

# Exit codes
EXIT_OK = 0
EXIT_WARNING = 1
EXIT_CRITICAL = 2
EXIT_ERROR = 3


def _exit_code(overall: Severity) -> int:
    mapping = {
        Severity.OK: EXIT_OK,
        Severity.WARNING: EXIT_WARNING,
        Severity.CRITICAL: EXIT_CRITICAL,
        Severity.ERROR: EXIT_ERROR,
        Severity.UNKNOWN: EXIT_ERROR,
    }
    return mapping.get(overall, EXIT_ERROR)


def _print_results_table(results: list[CheckResult], show_ok: bool) -> None:
    table = Table(
        title="Faultline Diagnostic Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Check", style="dim", width=30)
    table.add_column("Message")

    for r in results:
        if not show_ok and r.severity == Severity.OK:
            continue
        colour = _SEVERITY_COLOUR[r.severity]
        table.add_row(
            f"[{colour}]{r.severity.value.upper()}[/{colour}]",
            r.check_name,
            r.message,
        )

    console.print(table)


def _parse_tcp_target(raw: str) -> tuple[str, int]:
    """Parse 'host:port' into (host, port). Raises UsageError on invalid input."""
    parts = raw.rsplit(":", 1)
    if len(parts) != 2:
        raise click.UsageError(
            f"TCP target must be in host:port format, got: {raw!r}"
        )
    host = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        raise click.UsageError(f"Port must be an integer, got: {parts[1]!r}") from None
    if not (1 <= port <= 65535):
        raise click.UsageError(f"Port must be 1-65535, got: {port}")
    return host, port


@click.group()
@click.version_option(__version__, prog_name="faultline")
def main() -> None:
    """Faultline — Linux infrastructure diagnostics and incident reporting."""


@main.command("run")
@click.option(
    "--disk",
    "disk_paths",
    multiple=True,
    metavar="PATH",
    help="Mount point to check (repeatable). Defaults to all local mounts.",
)
@click.option(
    "--disk-warn",
    default=80.0,
    show_default=True,
    metavar="PCT",
    help="Disk usage warning threshold (%).",
)
@click.option(
    "--disk-crit",
    default=90.0,
    show_default=True,
    metavar="PCT",
    help="Disk usage critical threshold (%).",
)
@click.option(
    "--cpu-warn",
    default=85.0,
    show_default=True,
    metavar="PCT",
    help="CPU usage warning threshold (%).",
)
@click.option(
    "--mem-warn",
    default=85.0,
    show_default=True,
    metavar="PCT",
    help="Memory usage warning threshold (%).",
)
@click.option(
    "--mem-crit",
    default=95.0,
    show_default=True,
    metavar="PCT",
    help="Memory usage critical threshold (%).",
)
@click.option(
    "--service",
    "services",
    multiple=True,
    metavar="NAME",
    help="Systemd service to check (repeatable).",
)
@click.option(
    "--dns",
    "dns_hosts",
    multiple=True,
    metavar="HOST",
    help="Hostname to resolve (repeatable).",
)
@click.option(
    "--tcp",
    "tcp_targets",
    multiple=True,
    metavar="HOST:PORT",
    help="TCP endpoint to probe, e.g. google.com:443 (repeatable).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON instead of human-readable tables.",
)
@click.option(
    "--no-ok",
    "suppress_ok",
    is_flag=True,
    help="Suppress OK-severity results from output.",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    metavar="FILE",
    help="Save report to FILE (JSON format).",
)
@click.option(
    "--title",
    default="Faultline Diagnostic Report",
    show_default=True,
    help="Report title embedded in the generated report.",
)
def run_cmd(
    disk_paths: tuple[str, ...],
    disk_warn: float,
    disk_crit: float,
    cpu_warn: float,
    mem_warn: float,
    mem_crit: float,
    services: tuple[str, ...],
    dns_hosts: tuple[str, ...],
    tcp_targets: tuple[str, ...],
    output_json: bool,
    suppress_ok: bool,
    output_path: str | None,
    title: str,
) -> None:
    """Run all requested diagnostic checks and produce a report."""

    all_results: list[CheckResult] = []

    # --- Disk ---
    all_results.extend(
        check_disk_usage(
            paths=list(disk_paths) or None,
            warning_pct=disk_warn,
            critical_pct=disk_crit,
        )
    )

    # --- CPU ---
    all_results.append(check_cpu_usage(warning_pct=cpu_warn))

    # --- Memory ---
    all_results.append(check_memory_usage(warning_pct=mem_warn, critical_pct=mem_crit))

    # --- Services ---
    if services:
        all_results.extend(check_services(list(services)))

    # --- DNS ---
    for host in dns_hosts:
        all_results.append(check_dns(host))

    # --- TCP ---
    for raw in tcp_targets:
        try:
            host, port = _parse_tcp_target(raw)
        except click.UsageError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            sys.exit(EXIT_ERROR)
        all_results.append(check_tcp(host, port))

    # --- Build report dict ---
    report = build_report(all_results, title=title, include_ok=not suppress_ok)
    overall = Severity(report["overall_severity"])

    # --- Output ---
    if output_json:
        click.echo(report_to_json(report))
    else:
        _print_results_table(all_results, show_ok=not suppress_ok)
        colour = _SEVERITY_COLOUR[overall]
        console.print(
            f"\nOverall severity: [{colour}]{overall.value.upper()}[/{colour}]"
        )

    if output_path:
        try:
            save_report(report, output_path, fmt="json")
            if not output_json:
                console.print(f"[dim]Report saved to {output_path}[/dim]")
        except OSError as exc:
            err_console.print(f"[red]Failed to save report to {output_path}: {exc}[/red]")
            sys.exit(EXIT_ERROR)

    sys.exit(_exit_code(overall))


@main.command("report")
@click.argument("report_file", type=click.Path(exists=True))
@click.option("--text", "as_text", is_flag=True, help="Render as plain text.")
def report_cmd(report_file: str, as_text: bool) -> None:
    """Pretty-print an existing JSON report file."""
    import json

    with open(report_file, encoding="utf-8") as fh:
        report = json.load(fh)

    if as_text:
        click.echo(format_report_text(report))
    else:
        click.echo(report_to_json(report))


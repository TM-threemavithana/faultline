# Faultline — Linux Infrastructure Diagnostics & Incident Reporting

[![CI](https://github.com/TM-threemavithana/faultline/actions/workflows/ci.yml/badge.svg)](https://github.com/TM-threemavithana/faultline/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, focused Python CLI for diagnosing Linux infrastructure problems and generating structured incident reports.

---

## Features

| Category | Checks |
|---|---|
| **Disk** | Usage per mount, configurable warn/crit thresholds |
| **CPU** | Sampled utilisation, configurable threshold |
| **Memory** | Virtual + swap usage, configurable thresholds |
| **Services** | systemd unit status (graceful degradation in WSL2/containers) |
| **DNS** | A/AAAA record resolution, failure classification (NXDOMAIN, timeout, SERVFAIL) |
| **TCP** | Reachability with explicit timeout, failure classification (refused, timeout, no-route) |
| **Reports** | JSON + plain-text incident reports with severity, evidence, remediation |

---

## Installation

### Prerequisites

- Python 3.11+ (tested on 3.11, 3.12, 3.13)
- WSL2 Ubuntu (or any Linux environment) for service checks

### Install in a virtual environment

```bash
git clone https://github.com/TM-threemavithana/faultline.git
cd faultline
python -m venv .venv
source .venv/bin/activate          # Linux / WSL2
# or: .venv\Scripts\activate       # Windows PowerShell

pip install -e .
```

### Install with dev/test dependencies

```bash
pip install -e ".[dev]"
```

---

## Usage

### Basic run (all local mounts + CPU + memory)

```bash
faultline run
```

### Check specific disk paths

```bash
faultline run --disk / --disk /home --disk /var
```

### Check services (requires systemd; gracefully skipped in WSL2 without systemd)

```bash
faultline run --service nginx --service sshd --service postgresql
```

### Network diagnostics

```bash
faultline run --dns example.com --dns google.com --tcp example.com:443 --tcp 10.0.0.5:22
```

### JSON output (for pipeline consumption)

```bash
faultline run --json
faultline run --json | jq '.overall_severity'
```

### Save report to file

```bash
faultline run --output /tmp/incident-$(date +%Y%m%d-%H%M%S).json
```

### Suppress OK results (show only problems)

```bash
faultline run --no-ok
```

### Render an existing report

```bash
faultline report /tmp/incident.json
faultline report /tmp/incident.json --text
```

### Custom thresholds

```bash
faultline run --disk-warn 70 --disk-crit 85 --mem-warn 80 --mem-crit 90 --cpu-warn 75
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All checks OK |
| 1 | At least one WARNING |
| 2 | At least one CRITICAL |
| 3 | Internal ERROR (check itself failed) |

---

## Running Tests

```bash
pytest                                        # all tests
pytest --cov=faultline --cov-report=term     # with coverage
pytest -k "disk"                              # filter by name
pytest -m "not integration"                  # skip integration tests
```

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for design decisions and tradeoffs.

---

## Limitations

See [docs/architecture.md#limitations](docs/architecture.md#known-limitations).

---

## Demo

See [docs/demo.md](docs/demo.md) for a reproducible healthy/failing scenario walkthrough.

---

## Example Incident Report

See [examples/example_report.json](examples/example_report.json) for a sample customer handover report (synthetic demonstration data).

---

## License

MIT

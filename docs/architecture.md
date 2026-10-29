# Faultline — Architecture & Engineering Tradeoffs

## Overview

Faultline is a modular Python CLI that collects point-in-time diagnostic data
from a Linux host and produces a structured incident report. It is intentionally
**small, read-only, and dependency-light**.

---

## Directory Structure

```
faultline/
├── faultline/
│   ├── __init__.py          # version
│   ├── cli.py               # Click entry point, argument parsing, output
│   ├── models.py            # Severity enum, CheckResult dataclass, constants
│   ├── checks/
│   │   ├── disk.py          # psutil disk diagnostics
│   │   ├── system.py        # psutil CPU / memory diagnostics
│   │   ├── services.py      # systemd via subprocess
│   │   └── network.py       # dnspython + socket TCP
│   ├── report/
│   │   └── builder.py       # report assembly, text/JSON rendering, save
│   └── adapters/            # (reserved) OpenStack / Ceph adapters
├── tests/
│   ├── conftest.py          # shared fixtures
│   ├── test_disk.py
│   ├── test_system.py
│   ├── test_network.py
│   ├── test_services.py
│   ├── test_report.py
│   └── test_cli.py
├── docs/
├── examples/
├── .github/workflows/ci.yml
└── pyproject.toml
```

---

## Design Decisions

### 1. `CheckResult` as a universal value object

Every check — disk, CPU, DNS, TCP, service — returns the same
`CheckResult` dataclass. This means the report builder, CLI renderer, and
tests all work with a single, predictable type rather than ad-hoc dicts.

**Tradeoff:** slightly more boilerplate per check function vs. the flexibility
of raw dicts. Accepted: the type safety and testability payoff is worth it.

### 2. `Severity` as an ordered enum

`Severity` has an explicit ordering (`OK < WARNING < CRITICAL < ERROR < UNKNOWN`)
so that `build_report` can find the worst result with a simple `max()` rather
than imperative comparisons.

### 3. `psutil` for system metrics

`psutil` is cross-platform and avoids parsing `/proc` files directly.
This also means the same unit test mocks work on Windows (the CI runner).

**Tradeoff:** adds a dependency; the alternative (direct `/proc` parsing)
would be fragile across kernel versions.

### 4. `dnspython` for DNS resolution

`dnspython` gives explicit failure-reason exceptions (`NXDOMAIN`, `NoAnswer`,
`NoNameservers`, `Timeout`) rather than the opaque `socket.gaierror` returned
by the stdlib. This is essential for accurate failure classification.

**Tradeoff:** one more dependency vs. using `socket.getaddrinfo` and losing
failure granularity.

### 5. `subprocess` for `systemctl`

Service status is read via `systemctl is-active <name>`. This is the canonical
interface; parsing unit files directly would be brittle. The availability of
`systemctl` is checked first, and the result degrades gracefully with a
`WARNING` (not an exception) when it is absent.

**Tradeoff:** subprocess is slower than a D-Bus library (`dbus-python`,
`dasbus`). Accepted: service checks are not in a hot path, and avoiding a
D-Bus dependency keeps the install surface small.

### 6. Explicit TCP timeouts via `socket.create_connection`

`socket.create_connection(addr, timeout)` blocks for at most `timeout`
seconds. We do **not** use `socket.setdefaulttimeout()` because that is a
process-global side-effect. All timeouts are passed explicitly.

### 7. Exit codes follow Nagios convention

`0=OK`, `1=WARNING`, `2=CRITICAL`, `3=UNKNOWN/ERROR`. This is the industry
standard for monitoring-compatible CLIs and enables direct integration with
Nagios, Icinga, and similar tools.

### 8. No credentials captured in reports

`build_report` only serialises check outputs and platform metadata (`hostname`,
`platform.platform(terse=True)`). It does **not** call `os.environ`,
read config files, or inspect process environment variables.

---

## Known Limitations

1. **Point-in-time only.** Faultline takes a snapshot; it has no daemon mode,
   trending, or alerting. Use Prometheus + Alertmanager for continuous monitoring.

2. **CPU sampling interval.** The default 1-second sampling interval means the
   `faultline run` command always blocks for at least ~1 second.

3. **Service checks require systemd.** WSL2 without `[boot] systemd=true`,
   Docker containers, and non-systemd distros (e.g. Alpine) will see a WARNING
   and skip service checks.

4. **No authentication.** There is no mechanism to check services requiring
   credentials (databases, APIs). Only unauthenticated TCP reachability is tested.

5. **Not a replacement for purpose-built monitoring.** Faultline is a
   diagnostic aid and incident report generator, not an observability platform.

6. **Windows host limitations.** On Windows (outside WSL2), disk checks work
   via psutil but service checks and DNS via dnspython behave differently.
   Primary supported environment is WSL2 Ubuntu.

7. **No persistent state or baselining.** Faultline cannot tell you whether
   disk usage *increased* since yesterday; only what it is now.

# Faultline — Reproducible Demo

> [!NOTE]
> All incident data, hostnames, and IP addresses in these demonstration scenarios are synthetic.

## Prerequisites

```bash
cd /mnt/c/Project/Faultline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Scenario 1: Healthy System

Run against real local mounts + a reachable public host:

```bash
faultline run --disk / --dns google.com --tcp google.com:443
```

Expected output: table with all `OK` rows; exit code 0.

Save a JSON report:

```bash
faultline run --disk / --dns google.com --tcp google.com:443 \
  --output examples/healthy_report.json
```

Render it as plain text:

```bash
faultline report examples/healthy_report.json --text
```

---

## Scenario 2: Simulated Failure

Use environment-level mocking to simulate a failing DNS and a full disk.

```bash
python - <<'EOF'
from faultline.checks.network import check_dns
from faultline.checks.disk import check_disk_usage
from faultline.report.builder import build_report, format_report_text
from unittest.mock import patch, MagicMock
import dns.resolver

# Simulate NXDOMAIN
with patch("faultline.checks.network.dns.resolver.Resolver.resolve",
           side_effect=dns.resolver.NXDOMAIN()):
    dns_result = check_dns("nonexistent.broken-domain.invalid")

# Simulate critical disk
usage = MagicMock()
usage.total = 100 * 1024**3
usage.used  = 95 * 1024**3
usage.free  = 5  * 1024**3
usage.percent = 95.0
with patch("psutil.disk_usage", return_value=usage):
    disk_results = check_disk_usage(paths=["/data"])

results = [dns_result] + disk_results
report = build_report(results, title="Simulated Failure Demo")
print(format_report_text(report))
EOF
```

Expected: report showing CRITICAL for both DNS and disk, with remediation steps.

---

## Scenario 3: Service Check (systemd not available in WSL2 default)

```bash
faultline run --service nginx --service sshd --json | jq '.checks[0]'
```

Expected: single WARNING result explaining systemd is unavailable, with
remediation instructions for enabling it in WSL2.

---

## Scenario 4: TCP Connection Refused

```bash
# Port 9 is typically closed; adjust if 9 is open on your host
faultline run --tcp 127.0.0.1:9 --json | jq '.checks[] | select(.severity == "critical")'
```

Expected: CRITICAL with `failure_reason: "connection_refused"`.

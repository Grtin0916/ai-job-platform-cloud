# Week18 lifecycle live alerts

This runbook verifies the local Java lifecycle metrics and four Prometheus
alert rules. It does not claim production Prometheus, Alertmanager, notification
routing, or production alerting.

## Preconditions

- Start `W18TaskLifecycleLiveApplication` on `127.0.0.1:18081`.
- Call `POST /api/week18/lifecycle/bootstrap`.
- Confirm `/actuator/prometheus` exposes six
  `media_week18_lifecycle_snapshot` series.

## Static rule validation

Run:

```bash
promtool check rules \
  observability/prometheus/rules/week18-lifecycle-alerts.yml

cd observability/prometheus/rules
promtool test rules week18-lifecycle-alerts.test.yml
```

Expected results are `SUCCESS: 4 rules found` and `SUCCESS` for the unit
tests. The tests cover a healthy input plus target-down, result-binding-gap,
missing-asset, and repair-incomplete conditions.

## Live rule loading

When Docker is healthy:

```bash
scripts/run_week18_live_alert_gate.sh
```

If Docker Desktop is unavailable, use an independently installed Prometheus
binary:

```bash
PROMETHEUS_BIN=/path/to/prometheus \
  scripts/run_week18_live_alert_gate.sh
```

The script uses Docker when available and otherwise runs the supplied host
binary. It writes:

- `artifacts/demo/week18_live_alert_gate/rules.json`
- `artifacts/demo/week18_live_alert_gate/summary.json`

The gate passes only when all four expected rules are loaded, healthy,
inactive, and have no active alerts under the healthy Java input.

## Claim boundary

- `localLiveAlertRulesVerified=true` means only this local runtime was checked.
- `productionPrometheusVerified=false`.
- `alertmanagerConfigured=false`.
- `productionAlertingVerified=false`.

# Week17 Demo Release Cloud Gate Runbook

## Purpose

Aggregate Mainbase demo release and Java handoff into a Cloud-side release gate.

## Current decision

- releaseGateReady: `True`
- dashboardReady: `True`
- prometheusSampleReady: `True`
- alertRulesDraftReady: `True`

## Claim boundary

The gate may claim:

- Mainbase release ZIP is valid.
- Release contains `index.html`.
- Release contains at least one WAV fallback.
- Java handoff artifact is available.
- Cloud has dashboard-ready and Prometheus-sample artifacts.

The gate must not claim:

- production SLO verification
- k6 threshold pass
- live Grafana import
- live service availability

## Known limitation

Java RANDOM_PORT IT explicit summary detection:

`{'logExists': True, 'logPath': '/home/GRT/work/grt_work/media-task-platform-java/artifacts/logs/week17_demo_release_handoff_api_it_20260703.log', 'logSizeBytes': 8820, 'summaryDetected': True, 'failureKeywordDetected': False, 'buildSuccessDetected': True, 'testsRunLineDetected': True, 'zeroFailureLineDetected': True, 'verified': True}`

If the Maven log is quiet because of `-q`, the gate does not upgrade it to verified automatically. This is intentional: evidence is separated from inference.

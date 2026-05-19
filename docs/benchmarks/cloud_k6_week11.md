# Week11 Cloud k6 Benchmark Gate

## Verdict

**PASS**

This report summarizes the authenticated k6 smoke result for the Week11 seeded media-task query path.

## Source

- Source summary JSON: loadtest/reports/week11_k6_smoke_summary_docker_seeded_authenticated_20260518_205831.json
- Expected task id: week11-k6-seed-created-001
- Java commit: 8bf3971
- Cloud commit: d03f9fb
- Generated at UTC: 2026-05-19T03:09:19.368476+00:00

## Derived Gate Criteria

| Metric | Observed | Required | Result |
|---|---:|---:|---|
| http_req_failed.rate | 0.0 | <= 0.0 | PASS |
| http_req_duration.p95_ms | 133.39465279999993 | < 750.0 | PASS |
| checks.rate | 1.0 | >= 1.0 | PASS |

## Native k6 Threshold Status

- Native k6 threshold status in source summary: not detected in source summary JSON
- This report uses a Week11 derived gate because the source summary may not expose native threshold metadata in a stable shape.
- The derived gate is based on observed k6 metrics: HTTP failure rate, p95 latency, and check pass rate.

## Failure Reasons

- None

## Interpretation Boundary

This is a Week11 smoke benchmark gate. It verifies that the authenticated Java media-task read path can be queried through the k6 script and linked to the seeded task used by the cross-repo eval bridge.

It does not verify production SLO, long-duration load, database saturation, multi-instance Kubernetes behavior, write-path orchestration, or real alert routing.

## Machine-readable Output

See artifacts/benchmarks/week11_k6_gate_summary.json for the machine-readable gate and threshold details.

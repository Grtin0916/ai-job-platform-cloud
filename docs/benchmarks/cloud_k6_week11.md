# Week11 Cloud k6 SLO Summary

## Scope

This document summarizes existing Week11 k6 reports into a local smoke reliability gate. It does not claim production SLO coverage.

## Aggregate

- Report count: 2
- Report kinds: `{'boundary_smoke': 1, 'business_smoke': 1}`
- All reports passed local smoke gate: `True`
- Max p95 latency ms: `133.39465279999993`
- Max http_req_failed rate: `0.0`
- Min checks rate: `1.0`

## Local Gate Rule

- `http_req_failed_rate == 0` when present.
- `checks_rate == 1` when present.
- `http_req_duration p95 < 200ms` when present.
- Boundary/negative smoke may intentionally receive HTTP 400, but it must be configured as an expected status in k6 so `http_req_failed` remains zero.

## Reports

| file | kind | p95_ms | failed_rate | checks_rate | missing_metrics | passed | failed_reasons |
|---|---|---:|---:|---:|---|---|---|
| loadtest/reports/week11_k6_query_boundary_2026-05-19T08-10-03-514Z.json | boundary_smoke | 131.9524367 | 0.0 | 1.0 | none | True | none |
| loadtest/reports/week11_k6_smoke_summary_docker_seeded_authenticated_20260518_205831.json | business_smoke | 133.39465279999993 | 0.0 | 1.0 | none | True | none |

## Interpretation

Week11 evidence shows whether the local Java task query path can be consumed by k6 under authenticated and/or boundary smoke conditions. This summary is a decision artifact for W11/W12 demo preparation, not a substitute for long-running load tests or production alerting.

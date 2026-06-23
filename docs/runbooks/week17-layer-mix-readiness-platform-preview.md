# Week17 Layer-Mix Readiness Platform Preview

## Purpose

Consume the Java/Mainbase readiness artifact and render platform-preview evidence for W17 layer-mix input gating.

## Boundary

- This is metrics-ready and dashboard-ready evidence only.
- It does not claim live Prometheus scrape.
- It does not claim live Grafana import.
- It does not claim production SLO.
- It does not execute a real layer mixer.

## Expected gate

- 2 candidates blocked from automatic mix as P1 regression fixtures.
- 1 candidate monitored as P2 threshold-margin fixture.
- 7 candidates available as P4 control-only inputs.

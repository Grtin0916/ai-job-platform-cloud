# Week17 Layer Mix V0 Result Platform Preview Runbook

## Purpose

Consume the Java Week17 layer mix v0 result preview evidence and render Cloud-side platform preview artifacts.

## Inputs

- Java HEAD: `d6928dc`
- Mainbase HEAD: `d9a6df0`
- Java report: `artifacts/manifests/week17_layer_mix_v0_result_preview_api_report.json`
- Mainbase manifest: `artifacts/evals/week17_layer_mix_v0_manifest.json`

## Outputs

- Platform preview JSON: `loadtest/reports/week17_layer_mix_v0_result_platform_preview.json`
- Prometheus metrics-ready text: `observability/prometheus/week17_layer_mix_v0_result_platform_preview.prom`
- Grafana dashboard-ready JSON: `observability/grafana/dashboards/week17_layer_mix_v0_result_platform_preview.json`

## Boundary

- This is not a live Prometheus scrape.
- This is not a live Grafana import.
- This is not a production SLO.
- This is not real generated candidate audio.
- This is not semantic audio quality pass.
- This is not human review pass.
- This is not final mix readiness.
- This is not production mixer availability.

## Operator decision

- Decision: `PASS_WEEK17_LAYER_MIX_V0_PLATFORM_PREVIEW`
- Alert decision: `NO_ALERT_PLACEHOLDER_CONTROL_MIX_HEALTHY`
- Track total: `7`
- Clip rate before clip: `0.0`

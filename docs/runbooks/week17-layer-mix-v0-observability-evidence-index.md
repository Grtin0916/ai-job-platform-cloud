# Week17 Layer Mix V0 Observability Evidence Index

Generated at UTC: 2026-06-26T07:22:20+00:00

## Decision

`PASS_WEEK17_LAYER_MIX_V0_OBSERVABILITY_EVIDENCE_INDEX`

## What this proves

This proves that Mainbase layer mix v0 evidence, Java result preview evidence, Cloud action gate evidence, local semantic fallback evidence, and metrics-ready evidence can be read as one offline observability contract.

## What this does not prove

- It does not prove official promtool pass unless a real promtool test rules report exists and records a pass.
- It does not prove live Prometheus scrape.
- It does not prove live Grafana import.
- It does not prove Alertmanager routing.
- It does not prove production alerting or production SLO.
- It does not prove semantic audio quality pass, human review pass, or final mix readiness.

## Key derived signals

- officialPromtoolPassed: `False`
- promtoolBlocked: `True`
- semanticFallbackPassed: `True`
- metricsReady: `True`
- blockedClaimsPreserved: `True`
- unsafeClaimDetected: `False`
- allRequiredInputsPresent: `True`
- cloudWorktreeOnlyExpectedOutputs: `True`

## Next Week17 usage

Use `loadtest/reports/week17_layer_mix_v0_observability_evidence_index.json` as the single entry point for dashboard-ready aggregation, k6 threshold smoke, and SLO boundary explanation.

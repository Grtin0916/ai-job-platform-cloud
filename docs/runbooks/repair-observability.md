# Repair release observability

This view separates acoustic proxy evidence, workflow decisions, and artifact
integrity. `MANUAL_REVIEW` is pending work, not success. `FINAL_SELECTED=0` is
the current truthful state. Onset metrics remain unavailable when the sample
count is zero.

Investigate integrity and source-consistency alerts first. A review queue alert
fires only after 24 hours without completion. Demo-pack failure is actionable
only after a build attempt. Production Prometheus, Alertmanager, and live
Grafana import are not verified by this local release.

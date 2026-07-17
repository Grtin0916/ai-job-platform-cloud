# W18 experiment dashboard

This dashboard joins the real W18 model experiment, Java lifecycle, and local
Prometheus alert evidence into one nine-panel view. Generate it with:

```bash
python3 scripts/build_w18_experiment_dashboard.py \
  --mainbase-root ../audio_engineering_repo_skeleton_v1 \
  --java-root ../media-task-platform-java \
  --cloud-root . \
  --out-aggregation loadtest/reports/w18_experiment_aggregation_20260710.json \
  --out-summary loadtest/reports/w18_experiment_aggregation_summary_20260710.json \
  --out-prom observability/prometheus/w18_experiment_metrics_20260710.prom \
  --out-dashboard observability/grafana/dashboards/w18_experiment_dashboard.json
```

The file provider polls every 30 seconds to avoid depending on filesystem
events. Mount the dashboard JSON under
`/var/lib/grafana/dashboards/w18`.

The dashboard is a versioned provisioning artifact, not proof of a live
Grafana import. The current claim boundary is:

- `productionPrometheusVerified=false`
- `liveGrafanaImportVerified=false`
- `alertmanagerConfigured=false`
- `productionAlertingVerified=false`
- `dockerDesktopEngineHealthy=false`

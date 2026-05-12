# Week10 SLO / SLI Draft Runbook

Date: 2026-05-11
Scope: local Docker Desktop + kind dev-cluster evidence only.

## 1. Why this exists

Week09 verified local Kubernetes rollout semantics for the Java service: Deployment, Service, rollout status, rollout history, rollback dry-run, health endpoint, and Prometheus metrics through port-forward.

Week10 starts the reliability layer. The goal is not to claim production SLOs. The goal is to define local SLI / SLO semantics and create a first Prometheus alert-rule draft that can be checked locally.

## 2. Current service boundary

Current verified service boundary:

- Runtime: local Docker Desktop
- Cluster: kind dev cluster
- Namespace: dev-platform
- Java backend Deployment: media-task-platform-java
- Service: media-task-platform-java
- Health endpoint: /actuator/health
- Metrics endpoint: /actuator/prometheus
- Evidence logs:
  - artifacts/logs/week09_k8s_media_task_rollout_final_20260508.log
  - artifacts/logs/week09_port_forward_20260508.stdout

## 3. SLI candidates

| SLI | Definition | Candidate source | Current boundary |
|---|---|---|---|
| availability | good health responses / total health probes | /actuator/health, Kubernetes readiness, Prometheus up | local-only |
| scrape availability | successful Prometheus scrape / total scrapes | up{job=...} | local-only |
| error ratio | 5xx requests / total HTTP requests | http_server_requests_seconds_count if available | metric name must be verified |
| latency mean | Mean HTTP request latency | http_server_requests_seconds_sum / http_server_requests_seconds_count | verified by live Actuator evidence on 2026-05-12 |
| rollout success | successful rollout status / rollout attempts | kubectl rollout status logs | manual evidence only |
| rollback dry-run success | dry-run rollback command success | scripts/rollout_undo.sh / kubectl logs | manual evidence only |

## 4. Week10 local SLO draft

| SLO | Draft target | Window | Why not 100 percent |
|---|---:|---|---|
| local scrape availability | >= 99.0% | 30m | local Docker / kind / port-forward may restart |
| local HTTP error ratio | < 5.0% | 10m | Week10 has no production traffic model |
| local p95 latency | < 1s | 10m | development cluster and laptop/server contention may affect latency |
| local rollout recoverability | rollout status succeeds and rollback dry-run command remains available | per rollout test | manual release evidence, not a continuous SLO |

## 5. First alert-rule draft

The first alert rules live in:

- observability/prometheus/alerts.yaml

Initial alerts:

- JavaAppTargetDown
- JavaAppHighErrorRatio
- JavaAppHighMeanLatency

These rules are local draft rules. They are intended for syntax validation and later metric-name refinement. They do not imply Alertmanager routing, paging, on-call ownership, or production severity.

## 6. Validation command

Preferred validation command if promtool is available locally:

    promtool check rules observability/prometheus/alerts.yaml

Docker-based validation if Prometheus image is available:

    docker run --rm -v "$PWD:/work" -w /work prom/prometheus:latest promtool check rules observability/prometheus/alerts.yaml

## 7. Not yet verified

- No production SLO.
- No real cloud-provider workload.
- No Alertmanager routing.
- No paging policy.
- No on-call workflow.
- No burn-rate alerting.
- No production traffic SLI.
- No confirmed long-window error budget.
- No verified metric-name mapping for all HTTP request metrics.

## 8. Next steps

1. Check which exact Spring Boot Actuator Prometheus metrics are exposed in the local Java service.
2. Tighten labels in alerts.yaml to match real metric labels.
3. Add recording rules only after metric names and label cardinality are stable.
4. Add Alertmanager only after local alert rules are meaningful.
5. Keep README Verified Scope synchronized with actual validated evidence.

## 2026-05-12 Live Actuator Metrics Alignment

Live recapture source:

- `artifacts/logs/week10_actuator_prometheus_live_20260512.txt`
- `artifacts/logs/week10_actuator_prometheus_live_recapture_20260512.log`
- `artifacts/logs/week10_actuator_metric_label_audit_20260512.log`

Observed HTTP metric labels:

- `error`
- `exception`
- `method`
- `outcome`
- `status`
- `uri`

Observed HTTP request metrics:

- `http_server_requests_seconds_count`
- `http_server_requests_seconds_sum`
- `http_server_requests_seconds_max`
- `http_server_requests_active_seconds_count`
- `http_server_requests_active_seconds_sum`
- `http_server_requests_active_seconds_max`

Current decision:

- `JavaAppHighErrorRatio` is backed by live `http_server_requests_seconds_count{status=...}` evidence.
- `JavaAppHighMeanLatency` is backed by live `http_server_requests_seconds_sum/count` evidence.
- Previous P95 latency expression based on `http_server_requests_seconds_bucket` is deferred because the live Actuator evidence does not expose `http_server_requests_seconds_bucket`.

Boundary:

- This remains a local Docker Desktop + kind development SLO / alert draft.
- This is not a production SLO.
- This is not Alertmanager routing.
- This is not paging or on-call policy.
- The currently deployed Java image in kind may lag behind the latest Java repository security-contract commit; the live metrics recapture is used for metric-name and label validation, not for Java API auth-contract validation.

# OTel Pipeline Runbook

## Goal

Bring up a minimal OpenTelemetry Collector pipeline for local development and verify first trace evidence from a Java service.

## Scope

Current scope is intentionally minimal:

- Java agent -> OTLP -> Collector -> debug exporter
- No Tempo / Jaeger / Grafana dependency yet
- Focus on first trace evidence and reproducible local commands

## Prerequisites

- Docker available
- Java service can run locally
- OpenTelemetry Java agent jar available locally

## Collector Config

- File: `observability/otel/otelcol-config.yaml`
- Receiver: OTLP gRPC `4317`, OTLP HTTP `4318`
- Exporter: `debug`
- Pipelines: traces / metrics / logs

## Start Collector

    docker rm -f week06-otelcol 2>/dev/null || true

    docker run --name week06-otelcol --rm \
      -p 4317:4317 \
      -p 4318:4318 \
      -p 13133:13133 \
      -v "$(pwd)/observability/otel/otelcol-config.yaml:/etc/otelcol/config.yaml:ro" \
      otel/opentelemetry-collector:0.150.0 \
      --config=/etc/otelcol/config.yaml

## Verify Collector Health

    curl -s http://127.0.0.1:13133/ | cat

## Expected Success

- Collector starts without config error
- Health endpoint responds
- After Java app sends telemetry, collector stdout shows spans / metrics / logs via `debug` exporter

## Evidence Capture

    mkdir -p artifacts/logs

    docker logs week06-otelcol > artifacts/logs/week06_otel_collector_trace_001.log 2>&1

For a second reproducible check after Java is started with the OTel agent:

    curl -sS http://127.0.0.1:8080/actuator/health
    curl -sS http://127.0.0.1:8080/health
    curl -i http://127.0.0.1:8080/auth/me || true
    curl -i http://127.0.0.1:8080/api/media-tasks || true

    docker logs week06-otelcol > artifacts/logs/week06_otel_collector_trace_002.log 2>&1

## Reproducible Local Evidence

Current reproducible local evidence includes:

- `artifacts/logs/week06_otel_collector_trace_001.log`
- `artifacts/logs/week06_otel_collector_trace_002.log`

The second trace evidence should show at least these HTTP spans from `media-task-platform-java`:

- `GET /actuator/health` -> `200`
- `GET /health` -> `200`
- `GET /auth/me` -> `401`
- `GET /api/media-tasks` -> `401`

## Next Step

- Keep the current Java agent -> OTLP -> Collector -> debug exporter path as the stable Week06 baseline
- If needed, add a richer backend such as Tempo only after the current reproducible trace path is documented and stable
- Later extend the runbook with K8s collector deployment and a stronger multi-round validation procedure

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
      otel/opentelemetry-collector:latest \
      --config=/etc/otelcol/config.yaml

## Verify Collector Health

    curl -s http://127.0.0.1:13133/ | cat

## Expected Success

- Collector starts without config error
- Health endpoint responds
- After Java app sends telemetry, collector stdout shows spans / metrics / logs via `debug` exporter

## Evidence Capture

    mkdir -p artifacts/logs

    docker logs week06-otelcol > artifacts/logs/week06_otel_collector_smoke.log 2>&1

## Next Step

- Add a captured smoke log under `artifacts/logs/`
- Wire Java zero-code agent against this collector
- Only after first trace evidence is stable, consider Tempo or another richer backend

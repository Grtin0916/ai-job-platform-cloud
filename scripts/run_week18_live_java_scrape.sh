#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

CONFIG="$ROOT/observability/prometheus/week18-live-java-scrape.yml"
CHECKER="$ROOT/scripts/check_week18_live_java_scrape.py"

OUT_DIR="$ROOT/artifacts/demo/week18_live_java_scrape"
TARGETS_JSON="$OUT_DIR/targets.json"
QUERY_JSON="$OUT_DIR/lifecycle_query.json"
SUMMARY_JSON="$OUT_DIR/summary.json"

CONTAINER="week18-prometheus-live"
PROMETHEUS_PORT="19091"

mkdir -p "$OUT_DIR"

if ! curl -fsS \
  http://127.0.0.1:18081/actuator/health \
  >/dev/null; then
  echo "[FAIL] Java lifecycle service is not reachable on port 18081" >&2
  exit 1
fi

docker info >/dev/null

docker rm -f "$CONTAINER" \
  >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER" \
  -p "${PROMETHEUS_PORT}:9090" \
  -v "$CONFIG:/etc/prometheus/prometheus.yml:ro" \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  >/dev/null

PROM_READY=0

for attempt in $(seq 1 30); do
  if curl -fsS \
    "http://127.0.0.1:${PROMETHEUS_PORT}/-/ready" \
    >/dev/null 2>&1; then
    PROM_READY=1
    echo "[OK] Prometheus ready after attempt $attempt"
    break
  fi

  sleep 1
done

if [ "$PROM_READY" -ne 1 ]; then
  echo "[FAIL] Prometheus did not become ready" >&2
  docker logs "$CONTAINER" >&2 || true
  exit 2
fi

GATE_PASSED=0

for attempt in $(seq 1 30); do
  curl -fsS \
    "http://127.0.0.1:${PROMETHEUS_PORT}/api/v1/targets" \
    > "$TARGETS_JSON"

  curl -fsS -G \
    "http://127.0.0.1:${PROMETHEUS_PORT}/api/v1/query" \
    --data-urlencode \
    "query=media_week18_lifecycle_snapshot" \
    > "$QUERY_JSON"

  if python3 "$CHECKER" \
    --targets "$TARGETS_JSON" \
    --query "$QUERY_JSON" \
    --summary "$SUMMARY_JSON" \
    --quiet; then

    GATE_PASSED=1
    echo "[OK] live scrape passed after attempt $attempt"
    break
  fi

  sleep 2
done

python3 "$CHECKER" \
  --targets "$TARGETS_JSON" \
  --query "$QUERY_JSON" \
  --summary "$SUMMARY_JSON"

if [ "$GATE_PASSED" -ne 1 ]; then
  echo "[FAIL] Prometheus live scrape gate failed" >&2
  exit 3
fi
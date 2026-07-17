#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

CONFIG="$ROOT/observability/prometheus/week18-live-java-alerts.yml"
RULES="$ROOT/observability/prometheus/rules/week18-lifecycle-alerts.yml"
CHECKER="$ROOT/scripts/check_week18_live_alert_rules.py"

OUT_DIR="$ROOT/artifacts/demo/week18_live_alert_gate"
RULES_JSON="$OUT_DIR/rules.json"
SUMMARY_JSON="$OUT_DIR/summary.json"

CONTAINER="week18-prometheus-alerts"
PORT="19092"
PROMETHEUS_BIN="${PROMETHEUS_BIN:-}"
RUNTIME_MODE="docker"
HOST_CONFIG=""
HOST_STORAGE=""
HOST_PID=""

mkdir -p "$OUT_DIR"

curl -fsS \
  http://127.0.0.1:18081/actuator/health \
  >/dev/null

cleanup() {
  if [ "$RUNTIME_MODE" = "host" ] && [ -n "$HOST_PID" ]; then
    kill "$HOST_PID" >/dev/null 2>&1 || true
    wait "$HOST_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

if docker info >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" \
    >/dev/null 2>&1 || true

  docker run -d \
    --name "$CONTAINER" \
    -p "${PORT}:9090" \
    -v "$CONFIG:/etc/prometheus/prometheus.yml:ro" \
    -v "$RULES:/etc/prometheus/rules/week18-lifecycle-alerts.yml:ro" \
    prom/prometheus:latest \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/prometheus \
    >/dev/null
else
  RUNTIME_MODE="host"

  if [ -z "$PROMETHEUS_BIN" ]; then
    PROMETHEUS_BIN="$(command -v prometheus || true)"
  fi

  if [ ! -x "$PROMETHEUS_BIN" ]; then
    echo "[FAIL] Docker is unavailable and PROMETHEUS_BIN is not executable" >&2
    exit 4
  fi

  HOST_CONFIG="$(mktemp)"
  HOST_STORAGE="$(mktemp -d)"

  sed \
    -e 's#host.docker.internal:18081#127.0.0.1:18081#' \
    -e "s#/etc/prometheus/rules/week18-lifecycle-alerts.yml#$RULES#" \
    "$CONFIG" > "$HOST_CONFIG"

  "$PROMETHEUS_BIN" \
    --config.file="$HOST_CONFIG" \
    --storage.tsdb.path="$HOST_STORAGE" \
    --web.listen-address="127.0.0.1:${PORT}" \
    >/dev/null 2>&1 &
  HOST_PID="$!"
fi

READY=0

for attempt in $(seq 1 30); do
  if curl -fsS \
    "http://127.0.0.1:${PORT}/-/ready" \
    >/dev/null 2>&1; then
    READY=1
    echo "[OK] Prometheus alert runtime ready after attempt $attempt"
    break
  fi

  sleep 1
done

if [ "$READY" -ne 1 ]; then
  if [ "$RUNTIME_MODE" = "docker" ]; then
    docker logs "$CONTAINER" >&2 || true
  fi
  echo "[FAIL] Prometheus alert runtime did not become ready" >&2
  exit 1
fi

sleep 6

curl -fsS \
  "http://127.0.0.1:${PORT}/api/v1/rules?type=alert" \
  > "$RULES_JSON"

python3 "$CHECKER" \
  --rules "$RULES_JSON" \
  --summary "$SUMMARY_JSON"

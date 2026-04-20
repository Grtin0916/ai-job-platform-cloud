#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] required files"
required_files=(
  "README.md"
  "docker-compose.observability.yml"
  "scripts/bootstrap_dev_env.sh"
  "observability/otel/otelcol-config.yaml"
)

for f in "${required_files[@]}"; do
  test -f "$f" || { echo "missing file: $f" >&2; exit 1; }
done

echo "[2/5] required directories"
required_dirs=(
  "k8s/base"
  "infra/terraform"
  "docs/runbooks"
)

for d in "${required_dirs[@]}"; do
  test -d "$d" || { echo "missing dir: $d" >&2; exit 1; }
done

echo "[3/5] shell syntax"
bash -n scripts/bootstrap_dev_env.sh
bash -n scripts/ci_validate.sh

echo "[4/5] docker compose config"
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.observability.yml config >/dev/null
else
  echo "skip docker compose config: docker not found"
fi

echo "[5/5] kubectl dry-run"
if command -v kubectl >/dev/null 2>&1; then
  kubectl apply --dry-run=client -f k8s/base >/dev/null
else
  echo "skip kubectl dry-run: kubectl not found"
fi

echo "ci_validate.sh passed"

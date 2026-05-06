#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] required files"
required_files=(
  "README.md"
  "docker-compose.observability.yml"
  "scripts/bootstrap_dev_env.sh"
  "observability/otel/otelcol-config.yaml"
)

for f in "${required_files[@]}"; do
  test -f "$f" || { echo "missing file: $f" >&2; exit 1; }
done

echo "[2/6] required directories"
required_dirs=(
  "k8s/base"
  "infra/terraform"
  "docs/runbooks"
)

for d in "${required_dirs[@]}"; do
  test -d "$d" || { echo "missing dir: $d" >&2; exit 1; }
done

echo "[3/6] shell syntax"
bash -n scripts/bootstrap_dev_env.sh
bash -n scripts/ci_validate.sh

echo "[4/6] docker compose config"
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.observability.yml config >/dev/null
else
  echo "skip docker compose config: docker not found"
fi

echo "[5/6] kubectl dry-run"
if command -v kubectl >/dev/null 2>&1; then
  kubectl create --dry-run=client --validate=false -f k8s/base >/dev/null
else
  echo "skip kubectl dry-run: kubectl not found"
fi

echo "[6/6] terraform local validation"
if command -v terraform >/dev/null 2>&1; then
  (
    cd infra/terraform/envs/dev
    trap 'rm -rf .terraform .terraform.lock.hcl' EXIT
    rm -rf .terraform .terraform.lock.hcl
    terraform fmt -recursive -check ../..
    terraform init -backend=false -input=false >/dev/null
    terraform validate >/dev/null
  )
else
  echo "skip terraform validation: terraform not found"
fi

echo "ci_validate.sh passed"

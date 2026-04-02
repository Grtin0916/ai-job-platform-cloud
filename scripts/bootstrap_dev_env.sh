#!/usr/bin/env bash
set -euo pipefail

echo "[bootstrap] checking local cloud dev tools"

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "[ok] $name -> $(command -v "$name")"
  else
    echo "[missing] $name"
    return 1
  fi
}

check_cmd docker
docker --version

if docker compose version >/dev/null 2>&1; then
  echo "[ok] docker compose"
  docker compose version
else
  echo "[missing] docker compose"
  exit 1
fi

check_cmd kind
kind version

check_cmd kubectl
kubectl version --client --output=yaml

check_cmd terraform
terraform version

echo "[bootstrap] all required tools are available"

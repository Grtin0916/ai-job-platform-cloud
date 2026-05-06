#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-dev-platform}"
DEPLOYMENT="${DEPLOYMENT:-media-task-platform-java}"
MODE="${MODE:-dry-run}"

echo "namespace: ${NS}"
echo "deployment: ${DEPLOYMENT}"
echo "mode: ${MODE}"

echo
echo "===== rollout status ====="
kubectl -n "${NS}" rollout status "deployment/${DEPLOYMENT}" --timeout=120s

echo
echo "===== rollout history ====="
kubectl -n "${NS}" rollout history "deployment/${DEPLOYMENT}"

echo
echo "===== rollback dry-run ====="
if [ "${MODE}" = "apply" ]; then
  kubectl -n "${NS}" rollout undo "deployment/${DEPLOYMENT}"
else
  kubectl -n "${NS}" rollout undo "deployment/${DEPLOYMENT}" --dry-run=server
fi

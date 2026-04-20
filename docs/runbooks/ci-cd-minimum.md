# CI/CD Minimum Runbook

## Purpose
本文件用于说明 Week07 Cloud 仓的最小 CI 骨架，只验证仓库结构、Compose 配置与 K8s client dry-run，不把它伪装成完整发布流水线。

## Current scope
- `.github/workflows/ci.yml`
- `scripts/ci_validate.sh`

## What is validated
1. required files and directories exist
2. shell scripts pass `bash -n`
3. `docker compose -f docker-compose.observability.yml config`
4. `kubectl apply --dry-run=client -f k8s/base`

## What is not yet validated
- real image build / push
- Terraform init / validate / plan
- real cluster deployment
- rollout / rollback
- alerts / SLO / release policy

## Local run
    chmod +x scripts/ci_validate.sh
    ./scripts/ci_validate.sh

## Notes
- 如果本地缺少 `docker` 或 `kubectl`，当前脚本会打印 skip；Week07 第一拍的目标是先建立 CI 入口。
- 后续 Week07 / W8 再把工具安装、真实 dry-run 和更严格检查补齐。

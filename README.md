# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。

## Verified Scope

当前仓库已完成并留有证据的范围如下：

- 已完成 OpenTelemetry Collector 最小链路接入
- 已保留两轮本地 trace evidence 日志
- 已补 OTel pipeline runbook
- 已完成 Week06 的 OTel 第二次本地可复现证据收口
- 已新增 `.github/workflows/ci.yml`，建立最小 GitHub Actions CI 入口
- 已新增 `scripts/ci_validate.sh`，用于仓库结构校验、Compose 配置校验与 K8s client dry-run
- 已新增 `docs/runbooks/ci-cd-minimum.md`，说明当前最小 CI/CD 骨架范围
- 已完成至少 2 次本地最小验证链复验：`scripts/ci_validate.sh` 通过，`docker compose -f docker-compose.observability.yml config` 通过，`kubectl apply --dry-run=client -f k8s/base` 通过
- 已保留 Week07 rerun 日志：`week07_ci_validate_local_rerun.log`、`week07_compose_config_rerun.log`、`week07_k8s_dry_run_rerun.log`

一句话说，当前仓库已经从“OTel 本地可复现”推进到“OTel 证据 + 最小 CI 骨架 + 本地验证链已再次复验”阶段；Week07 的 Cloud 主线已经不再只是观测实验，而是已经具备可引用的交付入口证据。

## Not Yet Verified

以下内容仍未进入“已验证”范围，当前不能写满：

- 真实 image build / push
- Terraform init / validate / plan
- 真实集群部署、rollout 与 rollback
- 更系统的 alerts / SLO / release policy
- 更完整的 CI/CD 发布闭环

这些方向已经进入路线规划，但截至当前仓库状态，还不应写成“已完成”。

## Next Hard Milestone

接下来的硬里程碑按顺序是：

1. Week07：收口最小 CI 骨架证据与 README / runbook / weekly / 日志入口
   - 固定 `.github/workflows/ci.yml`
   - 固定 `scripts/ci_validate.sh`
   - 固定 `docs/runbooks/ci-cd-minimum.md`
   - 固定 rerun 日志与 `docs/weekly/2026-04-23_week07_day04_cloud.md`

2. W8 预热：明确 Terraform 布局与更真实的交付对象边界
   - 为后续 image build、Terraform 与部署流水线预留入口
   - 为后续 K8s 发布与 SLO 草案做衔接

3. S1 阶段验收预热
   - 同步 README / workflow / runbook / 日志证据
   - 为 W8 阶段验收准备可直接引用的 Cloud 证据链

## Tech Stack

- Docker
- Docker Compose
- kind
- kubectl
- Terraform
- Kubernetes YAML

## Local Bootstrap

    chmod +x scripts/bootstrap_dev_env.sh
    ./scripts/bootstrap_dev_env.sh

## Local Cluster Quickstart

    kind create cluster --name cloud-dev --wait 60s
    kubectl cluster-info --context kind-cloud-dev
    kubectl apply -f k8s/base
    kubectl get ns
    kubectl get deploy,svc -n dev-platform

## Project Structure

    .
    ├── README.md
    ├── artifacts
    │   └── logs
    ├── docs
    │   ├── runbooks
    │   │   ├── local-observability.md
    │   │   └── otel-pipeline.md
    │   └── weekly
    ├── infra
    │   └── terraform
    │       ├── envs
    │       └── modules
    ├── k8s
    │   └── base
    ├── observability
    │   ├── grafana
    │   │   ├── dashboards
    │   │   └── provisioning
    │   ├── otel
    │   │   └── otelcol-config.yaml
    │   └── prometheus
    │       └── prometheus.yml
    └── scripts
        └── bootstrap_dev_env.sh


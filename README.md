# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。

## Verified Scope

- 已完成 S1 阶段总结：`docs/weekly/2026-05-01_stage_s1_cloud.md` 已收口 W4-W8 的 Kubernetes base、observability scaffold、CI/local validation 与 Week08 Terraform local-only validation 证据，并明确当前未验证真实 cloud provider、remote state、Terraform apply 和 provider-backed infrastructure resources。

当前仓库已完成并留有证据的范围如下：

- 已完成 OpenTelemetry Collector 最小链路接入
- 已保留两轮本地 trace evidence 日志
- 已完成 `docs/runbooks/otel-pipeline.md` 与 `docs/runbooks/local-observability.md`
- 已完成 Week07 最小 CI/CD 骨架：`.github/workflows/ci.yml`、`scripts/ci_validate.sh`、`docs/runbooks/ci-cd-minimum.md`
- 已完成至少 2 次本地最小验证链复验：`scripts/ci_validate.sh` 通过，`docker compose -f docker-compose.observability.yml config` 通过，`kubectl apply --dry-run=client -f k8s/base` 通过
- 已保留 Week07 rerun 日志：`week07_ci_validate_local_rerun.log`、`week07_compose_config_rerun.log`、`week07_k8s_dry_run_rerun.log`
- 已完成 Week08 Terraform layout ADR：`docs/adr/0001-terraform-layout.md`
- 已完成 Week08 Terraform root/child module 最小骨架：`infra/terraform/envs/dev/main.tf` 调用 `infra/terraform/modules/local_placeholder`
- 已完成 Week08 Terraform 本地结构验证：`terraform fmt -recursive -check`、`terraform init -backend=false`、`terraform validate`、`terraform plan -input=false`
- 已保留 Week08 Terraform 证据日志：`artifacts/logs/week08_terraform_fmt.log`、`artifacts/logs/week08_terraform_init_validate.log`、`artifacts/logs/week08_terraform_plan.log`

一句话说，当前 Cloud 仓库已经从 Week07 的 CI skeleton / local validation 阶段，推进到 Week08 的 Terraform layout、root/child module 语义与本地-only Terraform validation 阶段。

* * *

## Not Yet Verified

以下内容尚未验证，不能写成已完成：

- 真实 cloud provider 接入
- remote backend / remote state
- Terraform apply
- 真实云资源创建、变更或销毁
- image build / push
- 真实集群部署
- rollout / rollback
- 生产级 SLO / alerting policy
- Terraform plan against real cloud infrastructure
- secrets / credentials 管理流程

当前 `terraform plan` 只验证了 local placeholder module 的 output 变化，不代表真实基础设施部署完成。

* * *

## Next Hard Milestone

接下来的硬里程碑按顺序是：

1. Week08：收口 Terraform local validation
   - 将 Terraform layout ADR、runbook、root/child module 与 evidence logs 固定为可复查证据
   - 将 `scripts/ci_validate.sh` 扩展为可选 Terraform validation 入口
   - 明确当前只完成 local-only validation，不接真实云账号

2. Week08：为后续真实交付对象预热
   - 明确 provider / backend / state 的引入条件
   - 设计 image build 与 Terraform plan 的 CI 边界
   - 保持 Kubernetes base、observability 与 Terraform 三条线的职责分离


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


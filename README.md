# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。

## Verified Scope

当前已验证：

- 本地开发工具链可用：
  - Docker
  - Docker Compose
  - kind
  - kubectl
  - Terraform
- `scripts/bootstrap_dev_env.sh` 可运行并完成本地工具检查
- 本地集群方案已冻结为 `kind`
- Terraform 基础目录已建立：
  - `infra/terraform/envs/dev`
  - `infra/terraform/modules`
- Kubernetes base 目录已建立：
  - `k8s/base`

## Not Yet Verified

当前尚未验证或尚未接入：

- kind 集群上的完整服务部署
- Prometheus / Grafana / OpenTelemetry
- Helm / Kustomize / Argo CD
- Terraform 真实资源创建
- GitHub Actions / CI/CD
- 发布 / 回滚脚本
- SLO / 告警规则
- Java 服务正式部署到 dev K8s 集群

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
    ├── scripts
    │   └── bootstrap_dev_env.sh
    ├── infra
    │   └── terraform
    │       ├── README.md
    │       ├── envs
    │       │   └── dev
    │       └── modules
    ├── k8s
    │   └── base
    │       ├── namespace.yaml
    │       └── gateway-deployment.yaml
    └── docs
        └── weekly
            └── 2026-04-03_week01_cloud.md

## Next Hard Milestone

1. 用 kind 创建本地 dev 集群并验证 `k8s/base` 样板
2. 完成 Terraform `envs/dev` 的最小入口文件
3. 把 Java 服务部署到 dev K8s
4. 接入 Prometheus / Grafana
5. 增加 rollout / rollback / runbook

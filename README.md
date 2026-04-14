# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。

## Verified Scope

当前仓库已完成并留有证据的范围如下：

- 已完成本地 kind / Docker / kubectl / compose 开发环境自检
- 已完成 `docker-compose.observability.yml`
- 已完成 Prometheus 最小抓取配置（`observability/prometheus/prometheus.yml`）
- 已完成 Grafana dashboard 初版（`observability/grafana/dashboards/app-overview.json`）
- 已完成本地 observability runbook（`docs/runbooks/local-observability.md`）
- 已完成 Java `/actuator/prometheus` 接入本地观测基线

一句话说，当前仓库已经具备“本地 observability 最小链路”这一条 Week05 基线，Prometheus / Grafana 已经不是待办，而是已验证资产。

## Not Yet Verified

以下内容仍未进入“已验证”范围，当前不能写满：

- OpenTelemetry Collector 真正跑通后的 trace 证据
- Java agent + Collector 的最小 trace 闭环
- richer backend / Tempo / tracing UI
- Kubernetes 下的 OTel Collector 部署验证
- 更完整的 runbook 与故障排查文档

这些方向已经进入 Week06 路线，但截至当前仓库状态，还不应写成“已完成”。

## Next Hard Milestone

下一阶段目标：

1. 建立 `observability/otel/otelcol-config.yaml`
2. 建立 `docs/runbooks/otel-pipeline.md`
3. 采用 Java agent + Collector 路线跑通至少 1 条 trace
4. 在 README / runbook / 日志中同步证据，避免仓库叙事落后于代码现实

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


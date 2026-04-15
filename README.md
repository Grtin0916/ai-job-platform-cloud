# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。

## Verified Scope

当前仓库已完成并留有证据的范围如下：

- 已完成 `scripts/bootstrap_dev_env.sh`，可检查 Docker、Compose、kind、kubectl 等本地开发依赖
- 已建立 `infra/terraform/` 基础目录与说明
- 已建立 `k8s/base/` 基础目录与最小资源清单
- 已补 `observability/otel/otelcol-config.yaml`
- 已补 `docs/runbooks/otel-pipeline.md`
- 已起通 OpenTelemetry Collector 最小链路
- 已通过 Collector health check 验证 `13133` 可访问
- 已通过 Collector debug exporter 看到来自 `media-task-platform-java` 的 traces
- 已形成 Cloud Week06 的 first trace evidence 日志：
  - `artifacts/logs/week06_otel_collector_trace_001.log`

一句话说，当前 Cloud 仓库已经从“本地环境地基”推进到“OTel Collector + Java agent 最小 trace 证据”阶段，Week06 的 Cloud 主线已经真正落地。

## Not Yet Verified

以下内容仍未进入“已验证”范围，当前不能写满：

- Tempo / Grafana 的可视化 trace 闭环
- Java agent + Collector 的更稳定、可重复、多轮验证说明
- K8s 下的 OTel Collector 部署
- 更完整的 Prometheus / Grafana / tracing 一体化基线
- CI/CD、回滚、告警、SLO 等后续平台化闭环

这些方向已经进入路线规划，但截至当前仓库状态，还不应写成“已完成”。

## Next Hard Milestone

下一阶段目标：

1. 把当前 OTel baseline 从 debug exporter 推进到更稳定的 trace 展示或 richer backend
2. 把 Java 服务接入 Collector 的复现路径写实、写稳，补更清晰的 runbook 与日志证据
3. 视情况补 `k8s/base/otel-collector` 的最小部署入口
4. 同步 README / runbook / 日志证据，避免代码推进快于仓库叙事

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


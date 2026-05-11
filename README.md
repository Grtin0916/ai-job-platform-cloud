# ai-job-platform-cloud

一个面向云原生 / SRE / 平台工程方向的最小 Cloud 工程骨架仓库。

当前阶段目标不是立刻做成完整平台，而是先冻结本地开发脚手架选型、Terraform 目录约定、Kubernetes base 样板和可执行的环境检查入口，为后续 observability、CI/CD、发布回滚与 IaC 扩展打底。


### Week10 Cloud SLO / alert draft verified update - 2026-05-11

Verified in local Docker Desktop + kind scope only:

- Added `docs/runbooks/slo.md` as the Week10 local SLO / SLI draft runbook.
- Added `observability/prometheus/alerts.yaml` as the first Prometheus alert-rule draft.
- Added local validation log: `artifacts/logs/week10_prometheus_alerts_check_20260511.log`.
- The alert draft currently defines `JavaAppTargetDown`, `JavaAppHighErrorRatio`, and `JavaAppHighLatencyP95`.
- `alerts.yaml` passed fallback YAML structure validation.
- Docker-based `promtool check rules` did not complete because pulling `prom/prometheus:latest` failed with unexpected EOF / short read.

Evidence:

- `docs/runbooks/slo.md`
- `observability/prometheus/alerts.yaml`
- `artifacts/logs/week10_prometheus_alerts_check_20260511.log`

Boundary:

- This is not a production SLO.
- This is not production alerting.
- This is not Alertmanager routing.
- This is not an on-call or paging policy.
- `promtool check rules` has not yet passed.
- HTTP metric names and labels still need to be verified against the real Spring Boot Actuator Prometheus output.


### Week09 Cloud K8s rollout verified update - 2026-05-08

Verified in local Docker Desktop + kind dev cluster only:

- Docker context: `desktop-linux`.
- kind cluster: `cloud-dev`; kubectl context: `kind-cloud-dev`.
- Namespace: `dev-platform`.
- Java backend Deployment: `media-task-platform-java`, image `media-task-platform-java:week09-dev`, status `1/1 READY`.
- Local dependencies: `week09-postgres` and `week09-redis`, both `1/1 READY`.
- Service endpoint verified: `service/media-task-platform-java` -> `10.244.0.16:8080` in the captured run.
- Rollout status verified: `deployment "media-task-platform-java" successfully rolled out`.
- Rollout history verified: revisions `1` and `2` observed.
- Rollback dry-run verified: `deployment.apps/media-task-platform-java rolled back (server dry run)`.
- Health probe verified through port-forward: `/actuator/health` returned HTTP 200 with `{"status":"UP"}`.
- Prometheus scrape verified through port-forward: `/actuator/prometheus` returned application, executor, disk and HikariCP metrics.

Evidence:

- `artifacts/logs/week09_k8s_media_task_rollout_final_20260508.log`
- `artifacts/logs/week09_port_forward_20260508.stdout`

Boundary:

- This is not a real cloud-provider deployment.
- This is not provider-backed Terraform apply.
- This is not a production rollout or production rollback drill.
- It verifies the Week09 local dev K8s release semantics: Deployment, Service, rollout status, rollout history, rollback dry-run, health and Prometheus metrics.

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

1. Week10：补强 Prometheus alert 规则校验
   - 在 Docker 镜像拉取恢复后，复验 `promtool check rules observability/prometheus/alerts.yaml`
   - 将当前 fallback YAML structure validation 升级为 promtool 语法级校验
   - 不把当前 fallback 校验写成 promtool success

2. Week10：用真实 Actuator metrics 收紧告警表达式
   - 对照 `artifacts/logs/week09_port_forward_20260508.stdout` 或重新抓取 `/actuator/prometheus`
   - 校正 `http_server_requests_seconds_count` 与 `http_server_requests_seconds_bucket` 的真实 label
   - 避免写出无法命中真实时序的空转 alert

3. Week10：保持本地 SLO / alert 草案边界
   - 当前仅验证 local Docker Desktop + kind dev scope
   - 不声明生产 SLO、Alertmanager、paging、on-call 或真实云账号部署
   - 下一步再考虑 README、runbook、alerts.yaml 与证据日志的同步复验

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


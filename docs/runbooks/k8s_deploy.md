# Week09 K8s Deploy Runbook

## Scope

This runbook records the Week09 local Kubernetes deployment baseline for the Java service.

## Target

- Namespace: `dev-platform`
- Deployment: `media-task-platform-java`
- Service: `media-task-platform-java`
- Image: `media-task-platform-java:week09-dev`
- Cluster context: `kind-cloud-dev`

## Evidence boundary

This is a local kind-based dev deployment.

Verified in this step:
- Kubernetes manifests can pass client dry-run.
- Java service image can be loaded into the local kind cluster.
- Deployment can reach rollout status.
- Rollout history can be queried.
- Rollback dry-run can be executed.

Not verified in this step:
- Real cloud provider deployment.
- Remote state.
- Terraform apply against real infrastructure.
- Production-grade secrets handling.
- Multi-replica HA behavior.
- Real ingress / gateway exposure.

## Commands

Build Java image from the Java repository:

    ./mvnw -DskipTests package
    docker build -t media-task-platform-java:week09-dev -f - . < Dockerfile input
    kind load docker-image media-task-platform-java:week09-dev --name cloud-dev

Apply Kubernetes manifests:

    kubectl apply -f k8s/base/namespace.yaml
    kubectl apply -f k8s/base/media-task-platform-java-deployment.yaml
    kubectl apply -f k8s/base/media-task-platform-java-service.yaml

Check rollout:

    kubectl -n dev-platform rollout status deployment/media-task-platform-java
    kubectl -n dev-platform rollout history deployment/media-task-platform-java

Rollback dry-run:

    MODE=dry-run scripts/rollout_undo.sh

## Week09 verified local rollout - 2026-05-08

Verified target:

- Namespace: `dev-platform`
- Deployment: `media-task-platform-java`
- Service: `media-task-platform-java`
- Image: `media-task-platform-java:week09-dev`
- Dependencies: `week09-postgres`, `week09-redis`

Verification commands:

    kubectl -n dev-platform get deploy,rs,pod,svc,endpoints -o wide
    kubectl -n dev-platform rollout status deployment/media-task-platform-java --timeout=120s
    kubectl -n dev-platform rollout history deployment/media-task-platform-java
    kubectl -n dev-platform rollout undo deployment/media-task-platform-java --dry-run=server
    kubectl -n dev-platform port-forward svc/media-task-platform-java 18080:8080
    curl -i http://127.0.0.1:18080/actuator/health
    curl http://127.0.0.1:18080/actuator/prometheus | head -40

Observed result:

- `deployment "media-task-platform-java" successfully rolled out`
- Rollout history showed revisions `1` and `2`
- Server-side rollback dry-run succeeded
- `/actuator/health` returned HTTP 200 and `{"status":"UP"}`
- `/actuator/prometheus` returned Prometheus scrape output including application startup, executor and HikariCP metrics

Evidence file:

- `artifacts/logs/week09_k8s_media_task_rollout_final_20260508.log`

Boundary:

This runbook currently covers Docker Desktop + kind local dev verification only. It does not claim real cloud provider deployment, remote state, production-grade ingress, autoscaling, alerting or production rollback completion.

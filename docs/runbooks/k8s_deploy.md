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
    kubectl apply -f k8s/base/java-app-deployment.yaml
    kubectl apply -f k8s/base/java-app-service.yaml

Check rollout:

    kubectl -n dev-platform rollout status deployment/media-task-platform-java
    kubectl -n dev-platform rollout history deployment/media-task-platform-java

Rollback dry-run:

    MODE=dry-run scripts/rollout_undo.sh

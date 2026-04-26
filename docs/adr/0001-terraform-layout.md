# ADR 0001: Terraform Layout for Week08 S1 Baseline

Date: 2026-04-27  
Status: Accepted  
Repo: ai-job-platform-cloud  
Stage: Week08 / S1 pre-acceptance

## Context

The cloud repo already has a minimal Terraform root module at `infra/terraform/envs/dev/main.tf`.

Before adding real cloud providers, remote state, image build, deploy, rollout, or rollback behavior, the repo needs a stable IaC layout. The goal is to make later work easier to validate, not to pretend that real infrastructure has already been provisioned.

## Decision

Use this Terraform layout:

    infra/terraform/
      envs/
        dev/
          main.tf
      modules/
        local_placeholder/
          main.tf
          variables.tf
          outputs.tf

Responsibilities:

- `envs/dev` is the root module for the local dev environment.
- `modules/local_placeholder` is a local child module used to prove module wiring without creating real cloud resources.
- Real providers, backend configuration, and remote state are intentionally excluded from this ADR.
- `terraform fmt`, `terraform init -backend=false`, and `terraform validate` are the first validation gates.
- `terraform plan` may be used later, but only as a no-resource or local-only validation until real cloud scope is explicitly approved.

## Rationale

This keeps Week08 focused on structure and semantics:

- root module semantics are visible;
- child module semantics are visible;
- no cloud account or credential is required;
- no real resource is created;
- CI can later add Terraform validation without expanding deployment scope.

## Consequences

Positive:

- The repository now has a stable place for environment-specific Terraform entrypoints.
- Reusable module boundaries are explicit.
- Future provider/backend work has a predictable landing zone.

Trade-offs:

- This does not validate real cloud permissions.
- This does not validate remote state.
- This does not produce a deployable platform.
- The placeholder module must not be mistaken for production infrastructure.

## Current Non-goals

- No real cloud provider.
- No remote backend.
- No image build or push.
- No Kubernetes rollout or rollback.
- No production SLO or alerting policy.
- No claim that `terraform plan` against real infrastructure has passed.

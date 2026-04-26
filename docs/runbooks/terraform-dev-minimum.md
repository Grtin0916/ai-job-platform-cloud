# Terraform Dev Minimum Runbook

Date: 2026-04-27  
Repo: ai-job-platform-cloud  
Stage: Week08 / S1 pre-acceptance  
Status: Draft

## 1. Purpose

This runbook defines the minimum local Terraform validation flow for the cloud repo.

The goal is to validate Terraform layout and root/child module semantics without creating real cloud resources.

## 2. Current Scope

Current files:

- `docs/adr/0001-terraform-layout.md`
- `infra/terraform/envs/dev/main.tf`
- `infra/terraform/modules/local_placeholder/main.tf`
- `infra/terraform/modules/local_placeholder/variables.tf`
- `infra/terraform/modules/local_placeholder/outputs.tf`

Current behavior:

- `envs/dev` acts as the root module.
- `modules/local_placeholder` acts as a local child module.
- No provider is configured.
- No backend is configured.
- No remote state is configured.
- No real resource is created.

## 3. Commands

From repository root:

    cd infra/terraform/envs/dev

Format Terraform files:

    terraform fmt -recursive ../..

Initialize without backend:

    terraform init -backend=false

Validate configuration:

    terraform validate

Optional local-only plan:

    terraform plan

Return to repository root:

    cd ../../..

## 4. Expected Result

Expected validation result:

    Success! The configuration is valid.

The optional plan should not propose real cloud resources because the current configuration contains no real provider-backed resource.

## 5. Evidence to Save

Save validation logs under:

- `artifacts/logs/week08_terraform_fmt.log`
- `artifacts/logs/week08_terraform_init_validate.log`
- `artifacts/logs/week08_terraform_plan.log`

## 6. Current Non-goals

- Do not connect a real cloud account.
- Do not configure remote state.
- Do not add credentials.
- Do not add provider-backed resources.
- Do not claim real infrastructure deployment.
- Do not replace Kubernetes or observability validation from Week07.

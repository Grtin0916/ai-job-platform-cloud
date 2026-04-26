terraform {
  required_version = ">= 1.6.0"
}

# Week08 S1 baseline:
# This root module intentionally does not configure a real cloud provider,
# backend, or remote state. It only proves root/child module wiring.

locals {
  project     = "ai-job-platform-cloud"
  environment = "dev"
}

module "local_placeholder" {
  source = "../../modules/local_placeholder"

  project     = local.project
  environment = local.environment
}

output "env_summary" {
  value = {
    project     = local.project
    environment = local.environment
    module      = module.local_placeholder.module_name
    labels      = module.local_placeholder.labels
  }
}

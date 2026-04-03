terraform {
  required_version = ">= 1.6.0"
}

# Week04 / Week05 过渡期的最小入口文件
# 当前阶段不接真实云账号，不创建真实资源。
# 目标只是让 envs/dev 具备一个明确的 Terraform root module 入口，
# 后续可以自然接 provider、backend、module 组合与 validate/plan。

locals {
  project     = "ai-job-platform-cloud"
  environment = "dev"
}

output "env_summary" {
  value = {
    project     = local.project
    environment = local.environment
  }
}
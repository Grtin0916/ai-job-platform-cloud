locals {
  module_name = "local_placeholder"

  labels = {
    project     = var.project
    environment = var.environment
    module      = local.module_name
    managed_by  = "terraform"
    stage       = "week08"
  }
}

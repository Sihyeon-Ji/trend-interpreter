output "workload_identity_provider" { value = google_iam_workload_identity_pool_provider.github.name }
output "deploy_service_account" { value = google_service_account.deploy.email }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "image_repository" { value = "${var.region}-docker.pkg.dev/${var.project_id}/builder-cup/app" }

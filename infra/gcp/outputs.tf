output "workload_identity_provider" { value = google_iam_workload_identity_pool_provider.github.name }
output "deploy_service_account" { value = google_service_account.deploy.email }
output "image_push_service_account" { value = google_service_account.image_push.email }
output "alert_relay_service_account" { value = google_service_account.alert_relay.email }
output "alert_push_service_account" { value = google_service_account.alert_push.email }
output "alert_relay_url" { value = local.alert_relay_url }
output "monitoring_alert_topic" { value = google_pubsub_topic.monitoring_alerts.id }
output "image_repository" { value = "${var.region}-docker.pkg.dev/${var.project_id}/builder-cup/app" }

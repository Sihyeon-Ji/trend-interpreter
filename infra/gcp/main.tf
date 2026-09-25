data "google_project" "current" {}

locals {
  alert_relay_service = "builder-cup-alert-relay"
  alert_relay_url     = "https://${local.alert_relay_service}-${data.google_project.current.number}.${var.region}.run.app"
  alert_channels = concat(
    [google_monitoring_notification_channel.discord_pubsub.name],
    google_monitoring_notification_channel.email[*].name,
  )
  dashboard_definition = {
    displayName = "Builder Cup operations"
    gridLayout = { columns = 2, widgets = [
      { title = "Cloud Run requests", xyChart = { dataSets = [{ timeSeriesQuery = {
        timeSeriesFilter = {
          filter      = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"builder-cup\""
          aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE" }
        }
      } }] } },
      { title = "Application errors", xyChart = { dataSets = [{ timeSeriesQuery = {
        timeSeriesFilter = {
          filter      = "metric.type=\"logging.googleapis.com/user/builder_cup_api_errors\" resource.type=\"cloud_run_revision\""
          aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE" }
        }
      } }] } },
      { title = "Discord relay errors", xyChart = { dataSets = [{ timeSeriesQuery = {
        timeSeriesFilter = {
          filter      = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.service_name=\"${local.alert_relay_service}\" metric.label.response_code_class=\"5xx\""
          aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE" }
        }
      } }] } },
      { title = "Alert dead-letter backlog", xyChart = { dataSets = [{ timeSeriesQuery = {
        timeSeriesFilter = {
          filter      = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" resource.type=\"pubsub_subscription\" resource.label.subscription_id=\"builder-cup-monitoring-alerts-dlq-inspect\""
          aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MAX" }
        }
      } }] } }
    ] }
  }
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com", "artifactregistry.googleapis.com", "aiplatform.googleapis.com",
    "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com",
    "secretmanager.googleapis.com", "logging.googleapis.com", "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "cloudbilling.googleapis.com", "billingbudgets.googleapis.com"
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "app" {
  location               = var.region
  repository_id          = "builder-cup"
  format                 = "DOCKER"
  description            = "Application images tagged by Git commit"
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-images-older-than-30-days"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "30d"
    }
  }

  cleanup_policies {
    id     = "keep-10-most-recent-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id   = "builder-cup-runtime"
  display_name = "Builder Cup application runtime"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "deploy" {
  account_id   = "builder-cup-deploy"
  display_name = "Builder Cup GitHub deployer"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "alert_relay" {
  account_id   = "builder-cup-alert-relay"
  display_name = "Builder Cup Discord alert relay"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "alert_push" {
  account_id   = "builder-cup-alert-push"
  display_name = "Builder Cup authenticated alert push"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# run.admin is needed to create the service and set its public invoker policy.
# This dedicated deployer can be assumed only by a release/gcp push in this repo.
resource "google_project_iam_member" "deploy_run" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_read_alert_logs" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_artifact_registry_repository_iam_member" "writer" {
  location   = var.region
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "act_as_alert_relay" {
  service_account_id = google_service_account.alert_relay.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_secret_manager_secret" "demo_key" {
  secret_id = "builder-cup-demo-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# Secret value is provisioned by bootstrap, never placed in Terraform state.
resource "google_secret_manager_secret_iam_member" "runtime_key" {
  secret_id = google_secret_manager_secret.demo_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "deploy_demo_key_viewer" {
  secret_id = google_secret_manager_secret.demo_key.id
  role      = "roles/secretmanager.viewer"
  member    = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_secret_manager_secret" "discord_webhook" {
  secret_id = "discord-webhook"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "alert_relay_webhook" {
  secret_id = google_secret_manager_secret.discord_webhook.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.alert_relay.email}"
}

resource "google_secret_manager_secret_iam_member" "alert_deploy_viewer" {
  secret_id = google_secret_manager_secret.discord_webhook.id
  role      = "roles/secretmanager.viewer"
  member    = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "pubsub_push_token" {
  service_account_id = google_service_account.alert_push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "builder-cup-github"
  display_name              = "Builder Cup GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "release"
  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.repository"    = "assertion.repository"
  }
  attribute_condition = "assertion.repository_id == '${var.github_repository_id}' && assertion.repository_owner_id == '${var.github_owner_id}' && assertion.ref == 'refs/heads/release/gcp' && assertion.event_name == 'push'"
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

resource "google_logging_metric" "api_errors" {
  name   = "builder_cup_api_errors"
  filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"builder-cup\" AND jsonPayload.status>=500"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
  depends_on = [google_project_service.apis]
}

resource "terraform_data" "dashboard_definition" {
  input = sha256(jsonencode(local.dashboard_definition))
}

resource "google_monitoring_dashboard" "app" {
  dashboard_json = jsonencode(local.dashboard_definition)
  depends_on     = [google_logging_metric.api_errors]
  # Cloud Monitoring injects output-only fields and chart defaults into the stored JSON.
  # Replace only when the desired chart definition changes, not on API normalization.
  lifecycle {
    ignore_changes       = [dashboard_json]
    replace_triggered_by = [terraform_data.dashboard_definition]
  }
}

resource "google_pubsub_topic" "monitoring_alerts" {
  name       = "builder-cup-monitoring-alerts"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "monitoring_alerts_dead_letter" {
  name       = "builder-cup-monitoring-alerts-dlq"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic_iam_member" "monitoring_publisher" {
  topic      = google_pubsub_topic.monitoring_alerts.name
  role       = "roles/pubsub.publisher"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
  depends_on = [google_monitoring_notification_channel.discord_pubsub]
}

resource "google_pubsub_topic_iam_member" "deploy_smoke_publisher" {
  topic  = google_pubsub_topic.monitoring_alerts.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  topic  = google_pubsub_topic.monitoring_alerts_dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "discord_relay" {
  name                       = "builder-cup-discord-relay"
  topic                      = google_pubsub_topic.monitoring_alerts.id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  expiration_policy { ttl = "" }

  push_config {
    push_endpoint = "${local.alert_relay_url}/"
    oidc_token {
      service_account_email = google_service_account.alert_push.email
      audience              = local.alert_relay_url
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.monitoring_alerts_dead_letter.id
    max_delivery_attempts = 5
  }

  depends_on = [
    google_pubsub_topic_iam_member.dead_letter_publisher,
    google_service_account_iam_member.pubsub_push_token,
  ]
}

resource "google_pubsub_subscription_iam_member" "dead_letter_subscriber" {
  subscription = google_pubsub_subscription.discord_relay.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "dead_letter_inspect" {
  name                       = "builder-cup-monitoring-alerts-dlq-inspect"
  topic                      = google_pubsub_topic.monitoring_alerts_dead_letter.id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  expiration_policy { ttl = "" }
}

resource "google_monitoring_notification_channel" "discord_pubsub" {
  display_name = "Builder Cup Discord relay"
  description  = "Routes Cloud Monitoring incidents through Pub/Sub to the Discord relay"
  type         = "pubsub"
  labels = {
    topic = google_pubsub_topic.monitoring_alerts.id
  }
}

resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email_address == "" ? 0 : 1
  display_name = "Builder Cup operations email"
  description  = "Fallback channel when the Discord delivery path is unavailable"
  type         = "email"
  labels = {
    email_address = var.alert_email_address
  }
}

resource "google_monitoring_uptime_check_config" "api_health" {
  display_name       = "Builder Cup API health"
  timeout            = "10s"
  period             = "300s"
  checker_type       = "STATIC_IP_CHECKERS"
  selected_regions   = ["USA", "EUROPE", "ASIA_PACIFIC"]
  log_check_failures = true

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = "builder-cup-${data.google_project.current.number}.${var.region}.run.app"
    }
  }

  http_check {
    path           = "/api/health"
    port           = 443
    request_method = "GET"
    use_ssl        = true
    validate_ssl   = true
    accepted_response_status_codes {
      status_value = 200
    }
  }

  content_matchers {
    content = "\"status\":\"ok\""
    matcher = "CONTAINS_STRING"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "api_unavailable" {
  display_name          = "Builder Cup API unavailable"
  combiner              = "OR"
  severity              = "CRITICAL"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Health check failed for 10 minutes"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.api_health.uptime_check_id}\" AND resource.type=\"uptime_url\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "600s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_FRACTION_TRUE"
        cross_series_reducer = "REDUCE_MEAN"
      }
      trigger { count = 1 }
    }
  }

  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }
  depends_on = [google_pubsub_topic_iam_member.monitoring_publisher]
}

resource "google_monitoring_alert_policy" "api_errors" {
  display_name          = "Builder Cup API server errors"
  combiner              = "OR"
  severity              = "ERROR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "At least one API server error in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/builder_cup_api_errors\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }

  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }
  depends_on = [
    google_logging_metric.api_errors,
    google_pubsub_topic_iam_member.monitoring_publisher,
  ]
}

resource "google_monitoring_alert_policy" "relay_errors" {
  count                 = var.alert_email_address == "" ? 0 : 1
  display_name          = "Builder Cup Discord relay errors"
  combiner              = "OR"
  severity              = "ERROR"
  notification_channels = google_monitoring_notification_channel.email[*].name

  conditions {
    display_name = "At least one relay 5xx response in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${local.alert_relay_service}\" AND metric.label.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }

  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }
}

resource "google_monitoring_alert_policy" "dead_letter_backlog" {
  count                 = var.alert_email_address == "" ? 0 : 1
  display_name          = "Builder Cup alert dead-letter backlog"
  combiner              = "OR"
  severity              = "ERROR"
  notification_channels = google_monitoring_notification_channel.email[*].name

  conditions {
    display_name = "Undelivered alert reached the dead-letter subscription"
    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"${google_pubsub_subscription.dead_letter_inspect.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_MAX"
      }
      trigger { count = 1 }
    }
  }

  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }
}

resource "google_billing_budget" "project" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "Builder Cup monthly budget"
  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.monthly_budget)
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }
  depends_on = [google_project_service.apis]
}

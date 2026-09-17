data "google_project" "current" {}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com", "artifactregistry.googleapis.com", "aiplatform.googleapis.com",
    "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com",
    "secretmanager.googleapis.com", "logging.googleapis.com", "monitoring.googleapis.com",
    "cloudbilling.googleapis.com", "billingbudgets.googleapis.com"
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = "builder-cup"
  format        = "DOCKER"
  description   = "Application images tagged by Git commit"
  depends_on    = [google_project_service.apis]
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

resource "google_monitoring_dashboard" "app" {
  dashboard_json = jsonencode({
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
      } }] } }
    ] }
  })
  depends_on = [google_logging_metric.api_errors]
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

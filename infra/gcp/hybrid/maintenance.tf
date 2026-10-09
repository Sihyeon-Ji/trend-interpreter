locals {
  maintenance_enabled = local.services_enabled
  # The production database is refreshed every few days (Plan 19), so a publication older than eight days means a missed refresh.
  maintenance_stale_after_hours = 192
}
resource "google_project_iam_member" "maintenance_sql" {
  count   = local.maintenance_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime["maintenance"].email}"
}
# Runs apps/trend-api/scripts/maintenance.py from the API image: user-text retention and the publication age check.
resource "google_cloud_run_v2_job" "maintenance" {
  count               = local.maintenance_enabled ? 1 : 0
  name                = "${local.prefix}-maintenance"
  location            = var.region
  deletion_protection = true
  lifecycle {
    # scripts/deploy-trend.sh moves the image with each API release.
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }
  template {
    task_count = 1
    template {
      service_account       = google_service_account.runtime["maintenance"].email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = "300s"
      # A stale publication does not fix itself on retry; the next scheduled run checks again.
      max_retries = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.services.sql_connection_name]
        }
      }
      containers {
        image   = var.services.api_image
        command = ["python", "scripts/maintenance.py"]
        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name  = "STALE_AFTER_HOURS"
          value = tostring(local.maintenance_stale_after_hours)
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = split("/versions/", var.services.database_secret_version)[0]
              version = split("/versions/", var.services.database_secret_version)[1]
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.runtime, google_project_iam_member.maintenance_sql]
}
resource "google_cloud_run_v2_job_iam_member" "maintenance_runs_itself" {
  count    = local.maintenance_enabled ? 1 : 0
  name     = google_cloud_run_v2_job.maintenance[0].name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime["maintenance"].email}"
}
resource "google_cloud_scheduler_job" "maintenance" {
  count            = local.maintenance_enabled ? 1 : 0
  name             = "${local.prefix}-maintenance-daily"
  region           = var.region
  schedule         = "0 4 * * *"
  time_zone        = "Asia/Seoul"
  attempt_deadline = "60s"
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/${google_cloud_run_v2_job.maintenance[0].id}:run"
    oauth_token {
      service_account_email = google_service_account.runtime["maintenance"].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_project_service.scheduler, google_cloud_run_v2_job_iam_member.maintenance_runs_itself]
}

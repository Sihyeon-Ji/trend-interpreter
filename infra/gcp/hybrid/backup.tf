locals {
  backup_enabled = local.services_enabled
  # Same PostgreSQL major as Cloud SQL; pinned so a tag move cannot change the dump format.
  backup_image          = "docker.io/library/postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
  backup_retention_days = 14
  # Only the public schema: Cloud SQL adds a managed extension schema that a plain PostgreSQL cannot restore.
  backup_script = <<-SH
    set -eu
    name="trend-$(date -u +%Y%m%dT%H%M%SZ).dump"
    pg_dump --format=custom --no-owner --no-privileges --schema=public -d "$DATABASE_URL" -f /tmp/trend.dump
    pg_restore --list /tmp/trend.dump >/dev/null
    cp /tmp/trend.dump "/backups/$name"
    echo "backup written object=$name bytes=$(stat -c %s /tmp/trend.dump)"
  SH
}
resource "google_project_service" "scheduler" {
  count              = local.backup_enabled ? 1 : 0
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}
resource "google_storage_bucket" "backups" {
  count                       = local.backup_enabled ? 1 : 0
  name                        = "${var.project_id}-${local.prefix}-backups"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
  lifecycle_rule {
    condition {
      age = local.backup_retention_days
    }
    action {
      type = "Delete"
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}
# The Cloud Storage volume mount needs object read and write; soft delete keeps removed dumps for seven days.
resource "google_storage_bucket_iam_member" "backup_writer" {
  count  = local.backup_enabled ? 1 : 0
  bucket = google_storage_bucket.backups[0].name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.runtime["backup"].email}"
}
resource "google_project_iam_member" "backup_sql" {
  count   = local.backup_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime["backup"].email}"
}
resource "google_cloud_run_v2_job" "backup" {
  count               = local.backup_enabled ? 1 : 0
  name                = "${local.prefix}-backup"
  location            = var.region
  deletion_protection = true
  template {
    task_count = 1
    template {
      service_account       = google_service_account.runtime["backup"].email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = "900s"
      max_retries           = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.services.sql_connection_name]
        }
      }
      volumes {
        name = "backups"
        gcs {
          bucket    = google_storage_bucket.backups[0].name
          read_only = false
        }
      }
      containers {
        image   = local.backup_image
        command = ["/bin/sh", "-c", local.backup_script]
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        volume_mounts {
          name       = "backups"
          mount_path = "/backups"
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
  depends_on = [google_secret_manager_secret_iam_member.runtime, google_storage_bucket_iam_member.backup_writer, google_project_iam_member.backup_sql]
}
resource "google_cloud_run_v2_job_iam_member" "backup_runs_itself" {
  count    = local.backup_enabled ? 1 : 0
  name     = google_cloud_run_v2_job.backup[0].name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime["backup"].email}"
}
resource "google_cloud_scheduler_job" "backup" {
  count            = local.backup_enabled ? 1 : 0
  name             = "${local.prefix}-backup-daily"
  region           = var.region
  schedule         = "0 3 * * *"
  time_zone        = "Asia/Seoul"
  attempt_deadline = "60s"
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/${google_cloud_run_v2_job.backup[0].id}:run"
    oauth_token {
      service_account_email = google_service_account.runtime["backup"].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_project_service.scheduler, google_cloud_run_v2_job_iam_member.backup_runs_itself]
}
output "backup" {
  value = local.backup_enabled ? {
    bucket = google_storage_bucket.backups[0].name
    job    = google_cloud_run_v2_job.backup[0].name
  } : null
}

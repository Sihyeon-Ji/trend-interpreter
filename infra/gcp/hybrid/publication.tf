locals {
  publication_enabled = local.services_enabled && var.publisher != null
}

resource "google_secret_manager_secret_iam_member" "publisher_database" {
  count     = local.publication_enabled ? 1 : 0
  secret_id = split("/versions/", var.publisher.database_secret_version)[0]
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime["publisher"].email}"
}

resource "google_project_iam_member" "publisher_sql" {
  count   = local.publication_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime["publisher"].email}"
}

# Explicit execution selects one batch through PUBLICATION_BATCH_ID; no automatic schedule.
resource "google_cloud_run_v2_job" "publication" {
  count               = local.publication_enabled ? 1 : 0
  name                = "${local.prefix}-publication"
  location            = var.region
  deletion_protection = true
  template {
    task_count = 1
    template {
      service_account       = google_service_account.runtime["publisher"].email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = "300s"
      max_retries           = 0
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.hybrid[0].id
          subnetwork = google_compute_subnetwork.api[0].id
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.services.sql_connection_name]
        }
      }
      containers {
        image   = var.services.api_image
        command = ["python", "scripts/publication_job.py"]
        resources {
          limits = { cpu = "1", memory = "2Gi" }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name  = "PUBLICATION_BATCH_ID"
          value = ""
        }
        env {
          name  = "MODEL_PROVIDER"
          value = "mock"
        }
        env {
          name  = "MODEL_REQUESTS_ENABLED"
          value = "false"
        }
        env {
          name  = "GPU_GATEWAY_REQUESTS_ENABLED"
          value = "false"
        }
        env {
          name  = "PGOPTIONS"
          value = "-c statement_timeout=240000 -c lock_timeout=10000"
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = split("/versions/", var.publisher.database_secret_version)[0]
              version = split("/versions/", var.publisher.database_secret_version)[1]
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.publisher_database, google_project_iam_member.publisher_sql]
}

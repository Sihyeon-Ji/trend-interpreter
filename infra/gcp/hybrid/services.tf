locals {
  services_enabled    = var.enabled && var.services != null
  gpu_service_enabled = local.services_enabled ? (var.services.gpu != null && var.gpu != null) : false
  api_secret_versions = local.services_enabled ? {
    DATABASE_URL       = var.services.database_secret_version
    ACCOUNTS           = var.services.accounts_secret_version
    FRONTEND_API_TOKEN = var.services.frontend_token_secret_version
  } : {}
  web_secret_versions = local.services_enabled ? {
    FRONTEND_API_TOKEN = var.services.frontend_token_secret_version
    SESSION_SECRET     = var.services.session_secret_version
  } : {}
  # Without services.gemini the API answers from rules and mocks and never calls Vertex AI.
  gemini_env = local.services_enabled ? (var.services.gemini == null ? {
    MODEL_PROVIDER         = "mock"
    MODEL_REQUESTS_ENABLED = "false"
    } : {
    MODEL_PROVIDER         = "vertex"
    MODEL_REQUESTS_ENABLED = "true"
    GOOGLE_CLOUD_LOCATION  = "global"
    GEMINI_MONTHLY_USD     = tostring(var.services.gemini.monthly_usd)
    REQUEST_GEMINI_DAILY   = tostring(var.services.gemini.request_daily)
    GEMINI_DAILY_BUDGET    = tostring(var.services.gemini.pipeline_daily)
    GEMINI_MODELS          = join(",", var.services.gemini.models)
  }) : {}
  secret_access = local.services_enabled ? merge(
    { for name, version in local.api_secret_versions : "api-${name}" => { account = "api", version = version } },
    { for name, version in local.web_secret_versions : "web-${name}" => { account = "web", version = version } },
    { "backup-DATABASE_URL" = { account = "backup", version = var.services.database_secret_version } },
    local.gpu_service_enabled ? { "api-gpu-ca" = { account = "api", version = var.services.gpu.ca_secret_version } } : {}
  ) : {}
}
resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = local.secret_access
  secret_id = split("/versions/", each.value.version)[0]
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[each.value.account].email}"
}
resource "google_logging_project_exclusion" "trend_requests" {
  count       = local.services_enabled ? 1 : 0
  name        = "${local.prefix}-request-urls"
  project     = var.project_id
  description = "Keep query strings out of the default log bucket for Trend services."
  filter      = "logName=\"projects/${var.project_id}/logs/run.googleapis.com%2Frequests\" AND resource.type=\"cloud_run_revision\" AND (resource.labels.service_name=\"${local.prefix}-api\" OR resource.labels.service_name=\"${local.prefix}-web\")"
  lifecycle {
    prevent_destroy = true
  }
}
resource "google_cloud_run_v2_service" "api" {
  count                = local.services_enabled ? 1 : 0
  name                 = "${local.prefix}-api"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = true
  # A fixed audience lets one ID token reach the service and its tagged candidate revisions during deployment.
  custom_audiences = ["${local.prefix}-api"]
  lifecycle {
    prevent_destroy = true
    # scripts/deploy-trend.sh rolls images and traffic after checking candidates; Terraform owns the rest.
    ignore_changes = [template[0].containers[0].image, traffic, client, client_version]
    precondition {
      condition = var.services.gpu == null ? true : (
        var.gpu == null ? false : var.services.gpu.release_sha256 == var.gpu.release_sha256
      )
      error_message = "API GPU mode requires the matching approved VM release."
    }
  }
  template {
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    service_account                  = google_service_account.runtime["api"].email
    max_instance_request_concurrency = 8
    timeout                          = "90s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
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
    dynamic "volumes" {
      for_each = local.gpu_service_enabled ? [var.services.gpu.ca_secret_version] : []
      content {
        name = "gpu-ca"
        secret {
          secret = split("/versions/", volumes.value)[0]
          items {
            version = split("/versions/", volumes.value)[1]
            path    = "ca.pem"
            mode    = 292
          }
        }
      }
    }
    containers {
      image = var.services.api_image
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "2Gi" }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      dynamic "volume_mounts" {
        for_each = local.gpu_service_enabled ? [1] : []
        content {
          name       = "gpu-ca"
          mount_path = "/secrets/gpu"
        }
      }
      dynamic "env" {
        for_each = local.gemini_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GPU_GATEWAY_REQUESTS_ENABLED"
        value = local.gpu_service_enabled ? "true" : "false"
      }
      dynamic "env" {
        for_each = local.gpu_service_enabled ? {
          GPU_GATEWAY_URL          = "https://${google_compute_address.gpu[0].address}:8443"
          GPU_GATEWAY_MODEL        = var.services.gpu.model
          GPU_GATEWAY_MODEL_DIGEST = var.services.gpu.digest
          GPU_GATEWAY_CA_FILE      = "/secrets/gpu/ca.pem"
          AUDIT_MODEL              = var.services.gpu.model
        } : {}
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.api_secret_versions
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = split("/versions/", env.value)[0]
              version = split("/versions/", env.value)[1]
            }
          }
        }
      }
      dynamic "env" {
        for_each = local.gpu_service_enabled ? [var.gpu.token_version] : []
        content {
          name = "GPU_GATEWAY_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gateway[0].id
              version = tostring(env.value)
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime, google_secret_manager_secret_iam_member.gateway, google_logging_project_exclusion.trend_requests]
}
resource "google_cloud_run_v2_service" "web" {
  count                = local.services_enabled ? 1 : 0
  name                 = "${local.prefix}-web"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = true
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [template[0].containers[0].image, traffic, client, client_version]
  }
  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    service_account       = google_service_account.runtime["web"].email
    timeout               = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.services.web_image
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      env {
        name  = "DATA_MODE"
        value = "api"
      }
      env {
        name  = "TREND_API_AUTH"
        value = "google-id-token"
      }
      env {
        name  = "TREND_API_URL"
        value = google_cloud_run_v2_service.api[0].uri
      }
      dynamic "env" {
        for_each = local.web_secret_versions
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = split("/versions/", env.value)[0]
              version = split("/versions/", env.value)[1]
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime, google_logging_project_exclusion.trend_requests]
}
resource "google_cloud_run_v2_service_iam_member" "web_invokes_api" {
  count    = local.services_enabled ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime["web"].email}"
}
resource "google_cloud_run_v2_service_iam_member" "public_web" {
  count      = local.services_enabled ? 1 : 0
  name       = google_cloud_run_v2_service.web[0].name
  location   = var.region
  project    = var.project_id
  role       = "roles/run.invoker"
  member     = "allUsers"
  depends_on = [google_cloud_run_v2_service_iam_member.web_invokes_api]
}
resource "google_service_account_iam_member" "deploy_act_as" {
  for_each           = local.services_enabled ? toset(["api", "web"]) : toset([])
  service_account_id = google_service_account.runtime[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:builder-cup-deploy@${var.project_id}.iam.gserviceaccount.com"
}
output "service_urls" {
  value = local.services_enabled ? {
    api = google_cloud_run_v2_service.api[0].uri
    web = google_cloud_run_v2_service.web[0].uri
  } : null
}

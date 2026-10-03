locals {
  prefix     = "trend-${var.environment}"
  api_cidr   = var.environment == "staging" ? "10.40.0.0/26" : "10.41.0.0/26"
  gpu_cidr   = var.environment == "staging" ? "10.40.1.0/28" : "10.41.1.0/28"
  identities = var.enabled ? toset(["web", "api", "gpu", "publisher", "maintenance", "backup"]) : toset([])
}
resource "google_project_service" "apis" {
  for_each           = var.enabled ? toset(["compute.googleapis.com", "iam.googleapis.com", "secretmanager.googleapis.com"]) : toset([])
  service            = each.value
  disable_on_destroy = false
}
resource "google_compute_network" "hybrid" {
  lifecycle {
    prevent_destroy = true
  }
  count                   = var.enabled ? 1 : 0
  name                    = "${local.prefix}-private"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}
resource "google_compute_subnetwork" "api" {
  lifecycle {
    prevent_destroy = true
  }
  count                    = var.enabled ? 1 : 0
  name                     = "${local.prefix}-api"
  ip_cidr_range            = local.api_cidr
  region                   = var.region
  network                  = google_compute_network.hybrid[0].id
  private_ip_google_access = true
}
resource "google_compute_subnetwork" "gpu" {
  lifecycle {
    prevent_destroy = true
  }
  count                    = var.enabled ? 1 : 0
  name                     = "${local.prefix}-gpu"
  ip_cidr_range            = local.gpu_cidr
  region                   = var.region
  network                  = google_compute_network.hybrid[0].id
  private_ip_google_access = true
}
resource "google_service_account" "runtime" {
  lifecycle {
    prevent_destroy = true
  }
  for_each     = local.identities
  account_id   = "${local.prefix}-${each.key}"
  display_name = "Trend ${var.environment} ${each.key}"
  depends_on   = [google_project_service.apis]
}
resource "google_compute_firewall" "gateway" {
  count                   = var.enabled ? 1 : 0
  name                    = "${local.prefix}-gateway"
  network                 = google_compute_network.hybrid[0].id
  source_ranges           = [local.api_cidr]
  target_service_accounts = [google_service_account.runtime["gpu"].email]
  allow {
    protocol = "tcp"
    ports    = [tostring(var.gateway_port)]
  }
}
resource "google_compute_firewall" "iap" {
  count                   = var.enabled ? 1 : 0
  name                    = "${local.prefix}-iap-ssh"
  network                 = google_compute_network.hybrid[0].id
  source_ranges           = ["35.235.240.0/20"]
  target_service_accounts = [google_service_account.runtime["gpu"].email]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
resource "google_secret_manager_secret" "gateway" {
  lifecycle {
    prevent_destroy = true
  }
  count     = var.enabled ? 1 : 0
  secret_id = "${local.prefix}-gateway-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
resource "google_secret_manager_secret_iam_member" "gateway" {
  for_each  = var.enabled ? toset(["api", "gpu"]) : toset([])
  secret_id = google_secret_manager_secret.gateway[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[each.key].email}"
}
resource "google_project_iam_member" "api_vertex" {
  count   = var.enabled ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime["api"].email}"
}
resource "google_project_iam_member" "api_sql" {
  count   = var.enabled ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime["api"].email}"
}

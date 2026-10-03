locals {
  gpu_enabled = var.enabled && var.gpu != null
}
resource "google_compute_disk" "models" {
  count = local.gpu_enabled ? 1 : 0
  name  = "${local.prefix}-models"
  zone  = var.gpu.zone
  type  = "pd-balanced"
  size  = 200
  lifecycle {
    prevent_destroy = true
  }
  depends_on = [google_project_service.apis]
}
resource "google_compute_address" "gpu" {
  count        = local.gpu_enabled ? 1 : 0
  name         = "${local.prefix}-gpu-internal"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = google_compute_subnetwork.gpu[0].id
  address      = cidrhost(local.gpu_cidr, 4)
  lifecycle {
    prevent_destroy = true
  }
}
resource "google_compute_instance" "gpu" {
  count               = local.gpu_enabled ? 1 : 0
  name                = "${local.prefix}-gpu"
  zone                = var.gpu.zone
  machine_type        = "g2-standard-8"
  deletion_protection = true
  boot_disk {
    initialize_params {
      image = var.gpu.boot_image
      size  = 50
      type  = "pd-balanced"
    }
  }
  attached_disk {
    source      = google_compute_disk.models[0].id
    device_name = "trend-models"
  }
  network_interface {
    subnetwork = google_compute_subnetwork.gpu[0].id
    network_ip = google_compute_address.gpu[0].address
  }
  service_account {
    email  = google_service_account.runtime["gpu"].email
    scopes = ["cloud-platform"]
  }
  guest_accelerator {
    type  = "nvidia-l4"
    count = 1
  }
  scheduling {
    automatic_restart           = false
    on_host_maintenance         = "TERMINATE"
    provisioning_model          = "STANDARD"
    instance_termination_action = "STOP"
    max_run_duration {
      seconds = 7200
    }
  }
  shielded_instance_config {
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
    trend-runtime = jsonencode({
      format_model_disk    = var.gpu.format_model_disk
      release_uri          = var.gpu.release_uri
      release_generation   = var.gpu.release_generation
      release_sha256       = var.gpu.release_sha256
      models_bucket        = var.gpu.models_bucket
      models_prefix        = var.gpu.models_prefix
      tls_secret_version   = var.gpu.tls_secret_version
      token_secret_version = "projects/${var.project_id}/secrets/${google_secret_manager_secret.gateway[0].secret_id}/versions/${var.gpu.token_version}"
    })
  }
  metadata_startup_script = "#!/bin/sh\nset -eu\n/opt/trend-gateway/bin/python -m model_gateway.install\n"
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = startswith(var.gpu.zone, "${var.region}-")
      error_message = "GPU zone must match the selected region."
    }
  }
  depends_on = [google_storage_bucket_iam_member.model_reader, google_secret_manager_secret_iam_member.tls, google_secret_manager_secret_iam_member.gateway]
}
resource "google_storage_bucket_iam_member" "model_reader" {
  count  = local.gpu_enabled ? 1 : 0
  bucket = var.gpu.models_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime["gpu"].email}"
  condition {
    title      = "approved-model-prefix"
    expression = "resource.name.startsWith('projects/_/buckets/${var.gpu.models_bucket}/objects/${var.gpu.models_prefix}')"
  }
}
resource "google_secret_manager_secret_iam_member" "tls" {
  count     = local.gpu_enabled ? 1 : 0
  secret_id = split("/versions/", var.gpu.tls_secret_version)[0]
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime["gpu"].email}"
}
output "gpu_internal_ip" {
  value = local.gpu_enabled ? google_compute_instance.gpu[0].network_interface[0].network_ip : null
}

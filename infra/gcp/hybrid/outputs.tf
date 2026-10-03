output "foundation" {
  value = var.enabled ? {
    network        = google_compute_network.hybrid[0].id
    api_subnet     = google_compute_subnetwork.api[0].id
    gpu_subnet     = google_compute_subnetwork.gpu[0].id
    identities     = { for name, account in google_service_account.runtime : name => account.email }
    gateway_secret = google_secret_manager_secret.gateway[0].id
  } : null
}

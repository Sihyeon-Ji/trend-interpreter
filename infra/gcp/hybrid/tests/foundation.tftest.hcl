mock_provider "google" {}

run "disabled_has_no_resources" {
  command = plan
  assert {
    condition     = length(google_compute_network.hybrid) == 0 && length(google_service_account.runtime) == 0 && length(google_secret_manager_secret.gateway) == 0
    error_message = "Default configuration must not create infrastructure."
  }
}
run "staging_is_private_and_scoped" {
  command = plan
  variables {
    enabled = true
  }
  assert {
    condition     = google_compute_network.hybrid[0].auto_create_subnetworks == false && google_compute_subnetwork.api[0].private_ip_google_access
    error_message = "Use a private custom network."
  }
  assert {
    condition     = google_compute_firewall.gateway[0].source_ranges == toset(["10.40.0.0/26"]) && toset(one(google_compute_firewall.gateway[0].allow).ports) == toset(["8443"])
    error_message = "Only the API subnet may access TLS inference."
  }
  assert {
    condition     = length(google_service_account.runtime) == 6 && length(google_secret_manager_secret_iam_member.gateway) == 2
    error_message = "Keep runtime identities separate and token access limited."
  }
}
run "production_is_separate" {
  command = plan
  variables {
    enabled     = true
    environment = "production"
  }
  assert {
    condition     = google_compute_subnetwork.api[0].ip_cidr_range == "10.41.0.0/26" && google_service_account.runtime["web"].account_id == "trend-production-web"
    error_message = "Production must have separate addresses and identities."
  }
}

mock_provider "google" {}

run "disabled_has_no_resources" {
  command = plan
  assert {
    condition     = length(google_compute_network.hybrid) == 0 && length(google_service_account.runtime) == 0 && length(google_secret_manager_secret.gateway) == 0 && length(google_compute_instance.gpu) == 0 && length(google_compute_disk.models) == 0
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
run "gpu_is_private_persistent_and_time_limited" {
  command = plan
  variables {
    enabled = true
    gpu = {
      zone               = "asia-northeast1-a"
      boot_image         = "projects/test-project/global/images/prepared-image"
      release_uri        = "gs://approved-models/releases/release.json"
      release_generation = "123"
      release_sha256     = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      models_bucket      = "approved-models"
      models_prefix      = "releases/"
      tls_secret_version = "projects/test-project/secrets/test-tls/versions/1"
      token_version      = 1
    }
  }
  assert {
    condition     = length(google_compute_instance.gpu[0].network_interface[0].access_config) == 0 && google_compute_disk.models[0].size == 200 && google_compute_instance.gpu[0].network_interface[0].network_ip == "10.40.1.4"
    error_message = "GPU must have no external IP and a persistent model disk."
  }
  assert {
    condition     = google_compute_instance.gpu[0].scheduling[0].max_run_duration[0].seconds == 7200 && google_compute_instance.gpu[0].scheduling[0].instance_termination_action == "STOP" && google_compute_instance.gpu[0].scheduling[0].automatic_restart == false
    error_message = "The first validation session must stop after two hours without restart."
  }
}

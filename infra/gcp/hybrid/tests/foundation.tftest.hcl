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
  assert {
    condition     = length(google_cloud_run_v2_service.api) == 0 && length(google_cloud_run_v2_service.web) == 0
    error_message = "Enabling the foundation alone must not publish web or API services."
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

run "private_api_and_public_web_are_separate" {
  command = plan
  override_resource {
    target          = google_service_account.runtime["web"]
    override_during = plan
    values = {
      email = "trend-staging-web@stunning-crane-508614-c1.iam.gserviceaccount.com"
      name  = "projects/stunning-crane-508614-c1/serviceAccounts/trend-staging-web@stunning-crane-508614-c1.iam.gserviceaccount.com"
    }
  }
  variables {
    enabled = true
    services = {
      api_image                     = "asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/trend-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      web_image                     = "asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/trend-web@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      sql_connection_name           = "stunning-crane-508614-c1:asia-northeast1:trend-project"
      database_secret_version       = "projects/stunning-crane-508614-c1/secrets/trend-staging-db/versions/1"
      accounts_secret_version       = "projects/stunning-crane-508614-c1/secrets/trend-staging-accounts/versions/1"
      frontend_token_secret_version = "projects/stunning-crane-508614-c1/secrets/trend-staging-frontend/versions/1"
      session_secret_version        = "projects/stunning-crane-508614-c1/secrets/trend-staging-session/versions/1"
    }
  }
  assert {
    condition     = google_cloud_run_v2_service.api[0].invoker_iam_disabled == false && google_cloud_run_v2_service.web[0].invoker_iam_disabled == false
    error_message = "Keep Cloud Run IAM invoker checks enabled."
  }
  assert {
    condition     = google_cloud_run_v2_service_iam_member.public_web[0].member == "allUsers" && google_cloud_run_v2_service_iam_member.web_invokes_api[0].member == "serviceAccount:trend-staging-web@stunning-crane-508614-c1.iam.gserviceaccount.com"
    error_message = "Only the web service is public, and its identity invokes the private API."
  }
  assert {
    condition     = length(google_secret_manager_secret_iam_member.runtime) == 5 && length(google_compute_instance.gpu) == 0
    error_message = "Web/API need scoped secrets and must not start a GPU VM."
  }
  assert {
    condition     = strcontains(google_logging_project_exclusion.trend_requests[0].filter, "trend-staging-api") && strcontains(google_logging_project_exclusion.trend_requests[0].filter, "trend-staging-web")
    error_message = "Exclude both service request URLs from the default log bucket."
  }
  assert {
    condition     = one(google_cloud_run_v2_service.api[0].template).vpc_access[0].egress == "PRIVATE_RANGES_ONLY" && toset(one(google_cloud_run_v2_service.api[0].template).volumes[0].cloud_sql_instance[0].instances) == toset(["stunning-crane-508614-c1:asia-northeast1:trend-project"])
    error_message = "The API must use VPC egress and the existing Cloud SQL attachment."
  }
}

run "gpu_api_requires_matching_vm_release" {
  command = plan
  variables {
    enabled = true
    services = {
      api_image                     = "asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/trend-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      web_image                     = "asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/trend-web@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      sql_connection_name           = "stunning-crane-508614-c1:asia-northeast1:trend-project"
      database_secret_version       = "projects/stunning-crane-508614-c1/secrets/trend-staging-db/versions/1"
      accounts_secret_version       = "projects/stunning-crane-508614-c1/secrets/trend-staging-accounts/versions/1"
      frontend_token_secret_version = "projects/stunning-crane-508614-c1/secrets/trend-staging-frontend/versions/1"
      session_secret_version        = "projects/stunning-crane-508614-c1/secrets/trend-staging-session/versions/1"
      gpu = {
        model             = "audit:approved"
        digest            = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
        release_sha256    = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
        ca_secret_version = "projects/stunning-crane-508614-c1/secrets/trend-staging-gpu-ca/versions/1"
      }
    }
  }
  expect_failures = [google_cloud_run_v2_service.api]
}

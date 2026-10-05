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
    condition     = length(google_cloud_run_v2_service.api) == 0 && length(google_cloud_run_v2_service.web) == 0 && length(google_cloud_run_v2_job.backup) == 0 && length(google_storage_bucket.backups) == 0 && length(google_cloud_run_v2_job.maintenance) == 0
    error_message = "Enabling the foundation alone must not publish web or API services or create backups."
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
    target          = google_cloud_run_v2_job.backup
    override_during = plan
    values = {
      id = "projects/stunning-crane-508614-c1/locations/asia-northeast1/jobs/trend-staging-backup"
    }
  }
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
    condition     = length(google_secret_manager_secret_iam_member.runtime) == 7 && google_secret_manager_secret_iam_member.runtime["backup-DATABASE_URL"].secret_id == "projects/stunning-crane-508614-c1/secrets/trend-staging-db" && google_secret_manager_secret_iam_member.runtime["maintenance-DATABASE_URL"].secret_id == "projects/stunning-crane-508614-c1/secrets/trend-staging-db" && length(google_compute_instance.gpu) == 0
    error_message = "Web/API and the backup and maintenance jobs need scoped secrets and must not start a GPU VM."
  }
  assert {
    condition     = one(one(google_cloud_run_v2_service.api[0].template).containers).resources[0].cpu_idle && one(one(google_cloud_run_v2_service.web[0].template).containers).resources[0].cpu_idle
    error_message = "Web and API use request-based CPU billing."
  }
  assert {
    condition     = google_storage_bucket.backups[0].public_access_prevention == "enforced" && google_storage_bucket.backups[0].uniform_bucket_level_access && one(one(google_storage_bucket.backups[0].lifecycle_rule).condition).age == 14
    error_message = "Backups stay in a private bucket and expire after 14 days."
  }
  assert {
    condition     = strcontains(one(one(one(google_cloud_run_v2_job.backup[0].template).template).containers).command[2], "--schema=public") && contains([for e in one(one(one(google_cloud_run_v2_job.backup[0].template).template).containers).env : one(one(e.value_source).secret_key_ref).secret], "projects/stunning-crane-508614-c1/secrets/trend-staging-db")
    error_message = "The backup job dumps the public schema with the service database secret."
  }
  assert {
    condition     = one(one(one(google_cloud_run_v2_job.maintenance[0].template).template).containers).command == tolist(["python", "scripts/maintenance.py"]) && one(one(google_cloud_run_v2_job.maintenance[0].template).template).max_retries == 0 && contains([for e in one(one(one(google_cloud_run_v2_job.maintenance[0].template).template).containers).env : "${e.name}=${e.value != null ? e.value : ""}"], "STALE_AFTER_HOURS=192")
    error_message = "The maintenance job runs the retention script once with the refresh-based staleness threshold."
  }
  assert {
    condition     = google_cloud_scheduler_job.backup[0].time_zone == "Asia/Seoul" && google_cloud_scheduler_job.backup[0].http_target[0].uri == "https://run.googleapis.com/v2/projects/stunning-crane-508614-c1/locations/asia-northeast1/jobs/trend-staging-backup:run"
    error_message = "A daily schedule runs the backup job."
  }
  assert {
    condition     = strcontains(google_logging_project_exclusion.trend_requests[0].filter, "trend-staging-api") && strcontains(google_logging_project_exclusion.trend_requests[0].filter, "trend-staging-web")
    error_message = "Exclude both service request URLs from the default log bucket."
  }
  assert {
    condition     = one(google_cloud_run_v2_service.api[0].template).vpc_access[0].egress == "PRIVATE_RANGES_ONLY" && toset(one(google_cloud_run_v2_service.api[0].template).volumes[0].cloud_sql_instance[0].instances) == toset(["stunning-crane-508614-c1:asia-northeast1:trend-project"])
    error_message = "The API must use VPC egress and the existing Cloud SQL attachment."
  }
  assert {
    condition     = contains([for e in one(google_cloud_run_v2_service.api[0].template).containers[0].env : "${e.name}=${e.value != null ? e.value : ""}"], "MODEL_PROVIDER=mock") && contains([for e in one(google_cloud_run_v2_service.api[0].template).containers[0].env : "${e.name}=${e.value != null ? e.value : ""}"], "MODEL_REQUESTS_ENABLED=false")
    error_message = "Without services.gemini the API must not call Vertex AI."
  }
}

run "gemini_is_opt_in_and_bounded" {
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
      gemini = {
        monthly_usd    = 20
        request_daily  = 150
        pipeline_daily = 50
        models         = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
      }
    }
  }
  assert {
    condition = alltrue([for pair in ["MODEL_PROVIDER=vertex", "MODEL_REQUESTS_ENABLED=true", "GEMINI_MONTHLY_USD=20", "REQUEST_GEMINI_DAILY=150", "GEMINI_MODELS=gemini-3.8-flash,gemini-3.5-flash-lite"] :
    contains([for e in one(google_cloud_run_v2_service.api[0].template).containers[0].env : "${e.name}=${e.value != null ? e.value : ""}"], pair)])
    error_message = "Gemini must be enabled only with an explicit monthly cap, daily limits and model list."
  }
}

run "gemini_without_a_cap_is_rejected" {
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
      gemini = {
        monthly_usd    = 0
        request_daily  = 150
        pipeline_daily = 50
        models         = ["gemini-3.8-flash"]
      }
    }
  }
  expect_failures = [var.services]
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

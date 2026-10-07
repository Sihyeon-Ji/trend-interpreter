variable "project_id" {
  type    = string
  default = "stunning-crane-508614-c1"
}
variable "region" {
  type    = string
  default = "asia-northeast1"
}
variable "enabled" {
  type    = bool
  default = false
}
variable "environment" {
  type    = string
  default = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Use separate staging or production state."
  }
}
variable "gateway_port" {
  type    = number
  default = 8443
  validation {
    condition     = var.gateway_port == 8443
    error_message = "The private TLS gateway uses port 8443."
  }
}
variable "gpu" {
  description = "Approved GPU deployment inputs; null creates no VM or disk."
  type = object({
    zone               = string
    boot_image         = string
    release_uri        = string
    release_generation = string
    release_sha256     = string
    models_bucket      = string
    models_prefix      = string
    tls_secret_version = string
    token_version      = number
    format_model_disk  = optional(bool, false)
  })
  default = null
  validation {
    condition = var.gpu == null ? true : (
      can(regex("^projects/[a-z0-9-]+/global/images/[a-z0-9-]+$", var.gpu.boot_image)) &&
      can(regex("^[1-9][0-9]*$", var.gpu.release_generation)) &&
      can(regex("^[a-f0-9]{64}$", var.gpu.release_sha256)) &&
      can(regex("^[a-z0-9][a-z0-9._-]+$", var.gpu.models_bucket)) &&
      can(regex("^[A-Za-z0-9][A-Za-z0-9._/-]*/$", var.gpu.models_prefix)) &&
      startswith(var.gpu.release_uri, "gs://${var.gpu.models_bucket}/${var.gpu.models_prefix}") &&
      can(regex("^projects/[a-z0-9-]+/secrets/[A-Za-z0-9_-]+/versions/[1-9][0-9]*$", var.gpu.tls_secret_version)) &&
      var.gpu.token_version >= 1 && floor(var.gpu.token_version) == var.gpu.token_version
    )
    error_message = "Pin boot image, release generation/hash, object scope and numeric secret versions."
  }
}
variable "publisher" {
  description = "Opt-in publication Job with a separate restricted database credential; null creates no Job."
  type = object({
    database_secret_version = string
  })
  default = null
  validation {
    condition = var.publisher == null ? true : can(regex(
      "^projects/${var.project_id}/secrets/trend-${var.environment}-publisher-database/versions/[1-9][0-9]*$",
      var.publisher.database_secret_version
    ))
    error_message = "Use the dedicated publisher database secret with a numeric pinned version."
  }
}

variable "services" {
  description = "Pinned web/API images, existing Cloud SQL, and numeric secret versions. Null creates no Cloud Run services."
  type = object({
    api_image                     = string
    web_image                     = string
    sql_connection_name           = string
    database_secret_version       = string
    accounts_secret_version       = string
    frontend_token_secret_version = string
    session_secret_version        = string
    gpu = optional(object({
      model             = string
      digest            = string
      release_sha256    = string
      ca_secret_version = string
    }), null)
    gemini = optional(object({
      monthly_usd    = number
      request_daily  = number
      pipeline_daily = number
      models         = list(string)
    }), null)
  })
  default = null
  validation {
    condition = var.services == null ? true : (
      can(regex("^${var.region}-docker[.]pkg[.]dev/${var.project_id}/builder-cup/trend-api@sha256:[a-f0-9]{64}$", var.services.api_image)) &&
      can(regex("^${var.region}-docker[.]pkg[.]dev/${var.project_id}/builder-cup/trend-web@sha256:[a-f0-9]{64}$", var.services.web_image)) &&
      can(regex("^${var.project_id}:${var.region}:[a-z][a-z0-9-]+$", var.services.sql_connection_name)) &&
      alltrue([for version in [var.services.database_secret_version, var.services.accounts_secret_version, var.services.frontend_token_secret_version, var.services.session_secret_version] : can(regex("^projects/${var.project_id}/secrets/trend-${var.environment}-[A-Za-z0-9_-]+/versions/[1-9][0-9]*$", version))]) &&
      (var.services.gemini == null ? true : (
        var.services.gemini.monthly_usd > 0 && var.services.gemini.monthly_usd <= 100 &&
        var.services.gemini.request_daily >= 0 && var.services.gemini.pipeline_daily >= 0 &&
        length(var.services.gemini.models) > 0 &&
        alltrue([for model in var.services.gemini.models : can(regex("^gemini-[0-9a-z.-]+$", model))])
      )) &&
      (var.services.gpu == null ? true : (
        can(regex("^[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+$", var.services.gpu.model)) &&
        can(regex("^[a-f0-9]{64}$", var.services.gpu.digest)) &&
        can(regex("^[a-f0-9]{64}$", var.services.gpu.release_sha256)) &&
        can(regex("^projects/${var.project_id}/secrets/trend-${var.environment}-gpu-ca/versions/[1-9][0-9]*$", var.services.gpu.ca_secret_version))
      ))
    )
    error_message = "Pin immutable images, an existing Cloud SQL instance, numeric secret versions, and a bounded Gemini budget."
  }
}

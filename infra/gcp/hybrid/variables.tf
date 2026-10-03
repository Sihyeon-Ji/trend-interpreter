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

variable "project_id" {
  type    = string
  default = "stunning-crane-508614-c1"
}
variable "region" {
  type    = string
  default = "asia-northeast1"
}
variable "github_repository" {
  type    = string
  default = "Sihyeon-Ji/2026-google-ai-builder-cup"
}
variable "github_repository_id" { type = string }
variable "github_owner_id" { type = string }
variable "billing_account" {
  type    = string
  default = ""
}
variable "monthly_budget" {
  type    = number
  default = 20
}
variable "budget_currency" {
  type    = string
  default = "USD"
}

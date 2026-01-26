variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "service_account_id" {
  description = "The ID of the service account to create (must be 6-30 chars, lowercase, connection-dashes)"
  type        = string
}

variable "display_name" {
  description = "Display name for the service account"
  type        = string
  default     = "Canary Service Account"
}

provider "google" {
  project = var.project_id
}

terraform {
  backend "pg" {}
  required_providers {
    google = {
      source = "registry.opentofu.org/hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_service_account" "canary" {
  account_id   = var.service_account_id
  display_name = var.display_name
}

resource "google_service_account_key" "canary_key" {
  service_account_id = google_service_account.canary.name
}

output "service_account_email" {
  value = google_service_account.canary.email
}

output "service_account_key" {
  value     = google_service_account_key.canary_key.private_key
  sensitive = true
}

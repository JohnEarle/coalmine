variable "bucket_name" {
  description = "The name of the bucket"
  type        = string
}

variable "labels" {
  description = "Labels to apply to the bucket"
  type        = map(string)
  default     = {}
}

variable "project" {
  description = "GCP Project ID"
  type        = string
  default     = "" # Picked up from env if empty
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "US"
}

provider "google" {
  project = var.project != "" ? var.project : null
}

resource "google_storage_bucket" "canary" {
  name          = var.bucket_name
  location      = var.region
  labels        = var.labels
  force_destroy = true # Allow deletion even if objects exist, careful with this in prod but good for canary
}

# Note: GCP Data Access logs must be enabled at the Project level for "Google Cloud Storage".
# Configuring them per-bucket via Terraform is not standard without Policy bindings which can be destructive.
# We rely on the user having enabled Audit Logs for Storage.
#
# IMPORTANT: To make this a true honeypot canary, you may want to add IAM bindings separately.
# For example, to make the bucket public:
#   resource "google_storage_bucket_iam_member" "public_viewer" {
#     bucket = google_storage_bucket.canary.name
#     role   = "roles/storage.objectViewer"
#     member = "allUsers"
#   }
# However, this is NOT done here by default to keep the canary private.
# GCP Project Audit Config is the place to ensure reads are captured.

output "self_link" {
  value = google_storage_bucket.canary.self_link
}

output "url" {
  value = google_storage_bucket.canary.url
}

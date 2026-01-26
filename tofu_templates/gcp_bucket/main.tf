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
  name     = var.bucket_name
  location = var.region
  labels   = var.labels
  labels   = var.labels
  force_destroy = true # Allow deletion even if objects exist, careful with this in prod but good for canary
}

# Note: GCP Data Access logs must be enabled at the Project level for "Google Cloud Storage".
# Configuring them per-bucket via Terraform is not standard without Policy bindings which can be destructive.
# We rely on the user having enabled Audit Logs for Storage.
  role   = "roles/storage.objectViewer"
  member = "allUsers" # Makes it public! A true canary.
                      # If we want private canary, we don't do this.
                      # But to ENABLE logging, we use audit_config or just rely on project level logging.
                      # Creating a specific audit config resource is safer.
}
# Actually, Audit Config is usually set on the project or valid resource.
# For Storage, it's often enabled by default for Admin/Delegated types.
# To ensure we capture Reads, we should trust the project config or document it.
# IMPORTANT: Setting 'allUsers' to objectViewer makes the bucket PUBLIC.
# Canaries are often public honeytokens. If not, remove this.
# Let's assume PRIVATE canary, but we want logs.
# GCP Project Audit Config is the place. Setting it via Terraform on the Bucket resource isn't directly supported simpler than just assuming it.
# Let's stick to the bucket resource but rely on the user having Data Access logs enabled on the Project or Folder.
# Warning the user is better than force-enabling access.


output "self_link" {
  value = google_storage_bucket.canary.self_link
}

output "url" {
  value = google_storage_bucket.canary.url
}

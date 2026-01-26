terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "name" {
  type        = string
  description = "Name for the logging resource (used for bucket and sink)"
}

provider "google" {
  project = var.project_id
}

# 0. Enable Required Services (Service Usage & Cloud Resource Manager)
# Assuming these are enabled by the setup script, but good to be aware.

# 1. Enable Data Access Logs for Project
# We want ADMIN_READ, DATA_WRITE, DATA_READ for Storage and IAM
resource "google_project_iam_audit_config" "storage_audit" {
  project = var.project_id
  service = "storage.googleapis.com"
  
  audit_log_config {
    log_type = "ADMIN_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
  audit_log_config {
    log_type = "DATA_READ"
  }
}

resource "google_project_iam_audit_config" "iam_audit" {
  project = var.project_id
  service = "iam.googleapis.com"
  
  audit_log_config {
    log_type = "ADMIN_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
  audit_log_config {
    log_type = "DATA_READ"
  }
}

# 2. Create Storage Bucket for Logs
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "log_bucket" {
  name          = "${var.name}-logs-${random_id.bucket_suffix.hex}"
  location      = "US"
  force_destroy = true 
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

# 3. Create Log Sink
# Filters for logs where principalEmail OR resourceName contains "canary"
# This captures both actions BY the canary and actions ON the canary.
resource "google_logging_project_sink" "canary_sink" {
  name = "${var.name}-sink"
  
  # Export to the bucket
  destination = "storage.googleapis.com/${google_storage_bucket.log_bucket.name}"
  
  # Filter for Canary related audit logs
  # Note: "cloudaudit.googleapis.com" covers both activity and data_access
  filter = <<EOT
resource.type="project" OR resource.type="gcs_bucket" OR resource.type="service_account"
AND log_id("cloudaudit.googleapis.com/activity") OR log_id("cloudaudit.googleapis.com/data_access")
AND (
  protoPayload.authenticationInfo.principalEmail:"canary"
  OR protoPayload.resourceName:"canary"
)
EOT

  unique_writer_identity = true
}

# 4. Grant Sink Identity permission to write to bucket
resource "google_storage_bucket_iam_binding" "log_writer" {
  bucket = google_storage_bucket.log_bucket.name
  role   = "roles/storage.objectCreator"
  
  members = [
    google_logging_project_sink.canary_sink.writer_identity,
  ]
}

output "bucket_name" {
  value = google_storage_bucket.log_bucket.name
}

output "sink_name" {
  value = google_logging_project_sink.canary_sink.name
}

output "writer_identity" {
  value = google_logging_project_sink.canary_sink.writer_identity
}

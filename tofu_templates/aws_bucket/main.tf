variable "bucket_name" {
  description = "The name of the bucket"
  type        = string
}

variable "tags" {
  description = "Tags to apply to the bucket"
  type        = map(string)
  default     = {}
}

variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

provider "aws" {
  region = var.region
}

terraform {
  backend "pg" {}
}

resource "aws_s3_bucket" "canary" {
  bucket = var.bucket_name
  tags   = var.tags
  force_destroy = true
}

output "bucket_domain_name" {
  value = aws_s3_bucket.canary.bucket_domain_name
}

output "bucket_arn" {
  value = aws_s3_bucket.canary.arn
}

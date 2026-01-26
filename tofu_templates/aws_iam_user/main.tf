variable "user_name" {
  description = "The name of the IAM user"
  type        = string
}

variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Tags to apply"
  type        = map(string)
  default     = {}
}

provider "aws" {
  region = var.region
}

terraform {
  backend "pg" {}
}

# The Canary User
resource "aws_iam_user" "canary" {
  name = var.user_name
  tags = var.tags
  force_destroy = true 
}

# The Canary Access Key (HoneyToken)
resource "aws_iam_access_key" "canary" {
  user = aws_iam_user.canary.name
}

# Output creds so we can eventually store/leak them
output "access_key_id" {
  value = aws_iam_access_key.canary.id
}

output "secret_access_key" {
  value     = aws_iam_access_key.canary.secret
  sensitive = true
}

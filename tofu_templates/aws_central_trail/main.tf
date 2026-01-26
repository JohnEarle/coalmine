variable "name" {
  description = "The name of the central trail resource"
  type        = string
}

variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Tags"
  type        = map(string)
  default     = {}
}

provider "aws" {
  region = var.region
}

terraform {
  backend "pg" {}
}

# 0. Random Suffix for Uniqueness
resource "random_id" "suffix" {
  byte_length = 4
}

# 1. CloudWatch Log Group
resource "aws_cloudwatch_log_group" "central_logs" {
  name = "/aws/cloudtrail/${var.name}"
  retention_in_days = 90
  tags = var.tags
}

# 2. S3 Bucket for Trail Storage
# Central trail needs a dedicated bucket for long term storage
resource "aws_s3_bucket" "trail_bucket" {
  bucket        = "${var.name}-logs-${random_id.suffix.hex}"
  force_destroy = true
  tags          = var.tags
}

resource "aws_s3_bucket_policy" "trail_bucket_policy" {
  bucket = aws_s3_bucket.trail_bucket.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck",
        Effect = "Allow",
        Principal = { Service = "cloudtrail.amazonaws.com" },
        Action   = "s3:GetBucketAcl",
        Resource = aws_s3_bucket.trail_bucket.arn
      },
      {
        Sid    = "AWSCloudTrailWrite",
        Effect = "Allow",
        Principal = { Service = "cloudtrail.amazonaws.com" },
        Action   = "s3:PutObject",
        Resource = "${aws_s3_bucket.trail_bucket.arn}/prefix/AWSLogs/*",
        Condition = {
          StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
        }
      }
    ]
  })
}

# 3. IAM Role for CloudWatch Logs
resource "aws_iam_role" "cloudtrail_cw_role" {
  name = "central-trail-role-${random_id.suffix.hex}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = { Service = "cloudtrail.amazonaws.com" },
      Effect = "Allow"
    }]
  })
}

resource "aws_iam_role_policy" "cloudtrail_cw_policy" {
  name = "central-trail-policy"
  role = aws_iam_role.cloudtrail_cw_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
      Resource = "${aws_cloudwatch_log_group.central_logs.arn}:*"
    }]
  })
}

variable "resource_prefix" {
  description = "Prefix for resources to log (cost optimization)"
  type        = string
  default     = "canary-"
}

data "aws_caller_identity" "current" {}

# 4. The Central CloudTrail
resource "aws_cloudtrail" "central_trail" {
  name                          = var.name
  s3_bucket_name                = aws_s3_bucket.trail_bucket.id
  s3_key_prefix                 = "prefix"
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  
  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.central_logs.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cw_role.arn

  tags = var.tags

  # Log S3 Data Events for Canaries Only
  advanced_event_selector {
    name = "Log Canary S3 Events"
    
    field_selector {
      field  = "eventCategory"
      equals = ["Data"]
    }

    field_selector {
      field = "resources.type"
      equals = ["AWS::S3::Object"]
    }
    
    field_selector {
      field = "resources.ARN"
      starts_with = ["arn:aws:s3:::${var.resource_prefix}"]
    }
  }

  # Log Lambda Data Events for Canaries Only
  advanced_event_selector {
    name = "Log Canary Lambda Events"
    
    field_selector {
      field  = "eventCategory"
      equals = ["Data"]
    }

    field_selector {
      field = "resources.type"
      equals = ["AWS::Lambda::Function"]
    }

    field_selector {
      field = "resources.ARN"
      starts_with = ["arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:${var.resource_prefix}"]
    }
  }
  
  # Log DynamoDB Data Events for Canaries Only
  advanced_event_selector {
    name = "Log Canary DynamoDB Events"

    field_selector {
      field  = "eventCategory"
      equals = ["Data"]
    }
    
    field_selector {
      field = "resources.type"
      equals = ["AWS::DynamoDB::Table"]
    }

    field_selector {
      field = "resources.ARN"
      starts_with = ["arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.resource_prefix}"]
    }
  }

  # Ensure Management Events are still captured (Important for IAM Users, etc)
  advanced_event_selector {
     name = "Log Management Events"
     
     field_selector {
       field = "eventCategory"
       equals = ["Management"]
     }
  }

  lifecycle {
    ignore_changes = [advanced_event_selector]
  }
}

output "log_group_name" {
    value = aws_cloudwatch_log_group.central_logs.name
}

output "trail_arn" {
    value = aws_cloudtrail.central_trail.arn
}

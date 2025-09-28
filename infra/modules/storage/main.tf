# Storage Module for Archon
# Manages S3 buckets and DynamoDB tables

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Local values
locals {
  artifacts_bucket_name = "${var.project_name}-artifacts-${var.environment}-${random_id.bucket_suffix.hex}"
  runs_table_name      = "${var.project_name}-runs-${var.environment}"
  common_tags = merge(var.common_tags, {
    Module = "storage"
  })
}

# Variables
variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "enable_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "enable_lifecycle" {
  description = "Enable S3 lifecycle rules"
  type        = bool
  default     = true
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

# Random ID for bucket suffix
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 bucket for artifacts
resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket_name

  tags = local.common_tags
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "artifacts" {
  count  = var.enable_versioning ? 1 : 0
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy      = true
  ignore_public_acls       = true
  restrict_public_buckets  = true
}

# S3 bucket lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  count  = var.enable_lifecycle ? 1 : 0
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "cleanup_old_versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    expiration {
      days = 90
    }
  }
}

# DynamoDB table for runs
resource "aws_dynamodb_table" "runs" {
  name           = local.runs_table_name
  billing_mode   = var.dynamodb_billing_mode
  hash_key       = "run_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  attribute {
    name = "repo"
    type = "S"
  }

  attribute {
    name = "pr_number"
    type = "N"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  global_secondary_index {
    name     = "repo-pr-index"
    hash_key = "repo"
    range_key = "pr_number"
  }

  global_secondary_index {
    name     = "timestamp-index"
    hash_key = "repo"
    range_key = "timestamp"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.common_tags
}

# DynamoDB table for knowledge base cache
resource "aws_dynamodb_table" "kb_cache" {
  name           = "${var.project_name}-kb-cache-${var.environment}"
  billing_mode   = var.dynamodb_billing_mode
  hash_key       = "query_hash"

  attribute {
    name = "query_hash"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  global_secondary_index {
    name     = "timestamp-index"
    hash_key = "query_hash"
    range_key = "timestamp"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = local.common_tags
}

# Outputs
output "artifacts_bucket_name" {
  description = "S3 artifacts bucket name"
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifacts_bucket_arn" {
  description = "S3 artifacts bucket ARN"
  value       = aws_s3_bucket.artifacts.arn
}

output "runs_table_name" {
  description = "DynamoDB runs table name"
  value       = aws_dynamodb_table.runs.name
}

output "runs_table_arn" {
  description = "DynamoDB runs table ARN"
  value       = aws_dynamodb_table.runs.arn
}

output "kb_cache_table_name" {
  description = "DynamoDB KB cache table name"
  value       = aws_dynamodb_table.kb_cache.name
}

output "kb_cache_table_arn" {
  description = "DynamoDB KB cache table ARN"
  value       = aws_dynamodb_table.kb_cache.arn
}

# Archon Infrastructure - Main Configuration
# Autonomous AI Agent for CI/CD PR Review

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  project_name = "archon"
  environment  = var.environment
  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "github_webhook_secret" {
  description = "GitHub webhook secret for signature verification"
  type        = string
  sensitive   = true
}

variable "github_token_secret_name" {
  description = "AWS Secrets Manager secret name for GitHub token"
  type        = string
  default     = "archon/github/token"
}

# Outputs
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = module.api_gateway.api_gateway_url
}

output "lambda_function_name" {
  description = "Webhook Lambda function name"
  value       = module.lambda.webhook_function_name
}

output "artifacts_bucket_name" {
  description = "S3 bucket for artifacts"
  value       = module.storage.artifacts_bucket_name
}

output "runs_table_name" {
  description = "DynamoDB runs table name"
  value       = module.storage.runs_table_name
}

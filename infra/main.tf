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

# Module calls
module "networking" {
  source = "./modules/networking"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  vpc_cidr                = var.vpc_cidr
  public_subnet_cidrs     = var.public_subnet_cidrs
  private_subnet_cidrs    = var.private_subnet_cidrs
  enable_nat_gateway      = var.enable_nat_gateway
  enable_vpc_endpoints    = var.enable_vpc_endpoints
}

module "secrets" {
  source = "./modules/secrets"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  github_token_secret_name = var.github_token_secret_name
  github_token_value       = var.github_token_value
  bedrock_agent_id        = var.bedrock_agent_id
  bedrock_agent_alias_id   = var.bedrock_agent_alias_id
  knowledge_base_id        = var.knowledge_base_id
}

module "storage" {
  source = "./modules/storage"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  enable_versioning = true
  enable_lifecycle  = true
}

module "iam" {
  source = "./modules/iam"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  artifacts_bucket_arn     = module.storage.artifacts_bucket_arn
  runs_table_arn          = module.storage.runs_table_arn
  kb_cache_table_arn      = module.storage.kb_cache_table_arn
  github_token_secret_arn  = module.secrets.github_token_secret_arn
}

module "ecs" {
  source = "./modules/ecs"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  vpc_id                    = module.networking.vpc_id
  private_subnet_ids         = module.networking.private_subnet_ids
  security_group_ids         = [module.networking.security_group_ids.ecs]
  ecs_task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  ecs_task_role_arn         = module.iam.ecs_task_role_arn
  artifacts_bucket_name     = module.storage.artifacts_bucket_name
  github_token_secret_arn    = module.secrets.github_token_secret_arn
}

module "lambda" {
  source = "./modules/lambda"
  
  project_name = local.project_name
  environment  = local.environment
  common_tags  = local.common_tags
  
  lambda_source_path        = "../lambda"
  github_webhook_secret     = var.github_webhook_secret
  bedrock_agent_id         = var.bedrock_agent_id
  bedrock_agent_alias_id    = var.bedrock_agent_alias_id
  runs_table_name          = module.storage.runs_table_name
  artifacts_bucket_name    = module.storage.artifacts_bucket_name
  lambda_execution_role_arn = module.iam.lambda_execution_role_arn
}

# Outputs
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = module.lambda.api_gateway_url
}

output "webhook_function_name" {
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

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_task_definition_arn" {
  description = "ECS task definition ARN"
  value       = module.ecs.task_definition_arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "security_group_ids" {
  description = "Security group IDs"
  value       = module.networking.security_group_ids
}

output "iam_role_arns" {
  description = "IAM role ARNs"
  value       = module.iam.role_arns
}

output "secrets_manager_arn" {
  description = "Secrets Manager secret ARN"
  value       = module.secrets.github_token_secret_arn
}

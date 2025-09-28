# Archon Infrastructure - Variables
# Centralized variable definitions

variable "aws_region" {
  description = "AWS region for resources"
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

variable "bedrock_agent_id" {
  description = "Bedrock Agent ID"
  type        = string
  default     = ""
}

variable "bedrock_agent_alias_id" {
  description = "Bedrock Agent Alias ID"
  type        = string
  default     = "TSTALIASID"
}

variable "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  type        = string
  default     = ""
}

variable "ecs_cluster_name" {
  description = "ECS cluster name for IaC execution"
  type        = string
  default     = "archon-iac-cluster"
}

variable "ecs_task_definition_name" {
  description = "ECS task definition name"
  type        = string
  default     = "archon-iac-task"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints for AWS services"
  type        = bool
  default     = true
}

variable "github_token_value" {
  description = "GitHub token value (optional - can be set later)"
  type        = string
  sensitive   = true
  default     = ""
}

# Redis/ElastiCache variables
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 2
}

variable "redis_snapshot_retention_days" {
  description = "Number of days to retain Redis snapshots"
  type        = number
  default     = 7
}

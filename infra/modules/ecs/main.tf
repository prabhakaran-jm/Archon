# ECS Module for Archon
# Manages ECS Fargate cluster and task definitions for IaC execution

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
  cluster_name = "${var.project_name}-${var.environment}"
  common_tags = merge(var.common_tags, {
    Module = "ecs"
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

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs"
  type        = list(string)
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ECS task role ARN"
  type        = string
}

variable "artifacts_bucket_name" {
  description = "S3 artifacts bucket name"
  type        = string
}

variable "github_token_secret_arn" {
  description = "GitHub token secret ARN"
  type        = string
}

variable "task_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 2048
}

# ECS cluster
resource "aws_ecs_cluster" "archon" {
  name = local.cluster_name

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs.name
      }
    }
  }

  tags = local.common_tags
}

# CloudWatch log group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.cluster_name}"
  retention_in_days = 7

  tags = local.common_tags
}

# ECS task definition
resource "aws_ecs_task_definition" "iac_runner" {
  family                   = "${var.project_name}-iac-runner-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name  = "iac-runner-container"
      image = "public.ecr.aws/docker/library/python:3.11-slim"
      
      essential = true
      
      environment = [
        {
          name  = "ARTIFACTS_BUCKET"
          value = var.artifacts_bucket_name
        },
        {
          name  = "GITHUB_TOKEN_SECRET_NAME"
          value = "archon/github/token"
        }
      ]
      
      secrets = [
        {
          name      = "GITHUB_TOKEN"
          valueFrom = var.github_token_secret_arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
      
      mountPoints = []
      volumesFrom = []
    }
  ])

  tags = local.common_tags
}

# Data source for current region
data "aws_region" "current" {}

# ECS service (optional - for long-running tasks)
resource "aws_ecs_service" "iac_runner" {
  count           = var.enable_service ? 1 : 0
  name            = "${var.project_name}-iac-runner-${var.environment}"
  cluster         = aws_ecs_cluster.archon.id
  task_definition  = aws_ecs_task_definition.iac_runner.arn
  desired_count   = 0  # Start with 0, scale as needed
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }

  tags = local.common_tags
}

variable "enable_service" {
  description = "Enable ECS service (for long-running tasks)"
  type        = bool
  default     = false
}

# Outputs
output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.archon.name
}

output "cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.archon.arn
}

output "task_definition_arn" {
  description = "ECS task definition ARN"
  value       = aws_ecs_task_definition.iac_runner.arn
}

output "task_definition_family" {
  description = "ECS task definition family"
  value       = aws_ecs_task_definition.iac_runner.family
}

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.ecs.name
}

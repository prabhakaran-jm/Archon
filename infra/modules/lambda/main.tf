# Lambda Module for Archon
# Manages Lambda functions and API Gateway integration

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  function_name = "${var.project_name}-webhook-${var.environment}"
  common_tags = merge(var.common_tags, {
    Module = "lambda"
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

variable "lambda_source_path" {
  description = "Path to Lambda source code"
  type        = string
  default     = "../lambda"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
}

variable "github_webhook_secret" {
  description = "GitHub webhook secret"
  type        = string
  sensitive   = true
}

variable "bedrock_agent_id" {
  description = "Bedrock Agent ID"
  type        = string
}

variable "bedrock_agent_alias_id" {
  description = "Bedrock Agent Alias ID"
  type        = string
  default     = "TSTALIASID"
}

variable "runs_table_name" {
  description = "DynamoDB runs table name"
  type        = string
}

variable "artifacts_bucket_name" {
  description = "S3 artifacts bucket name"
  type        = string
}

variable "lambda_execution_role_arn" {
  description = "Lambda execution role ARN"
  type        = string
}

# Lambda function
resource "aws_lambda_function" "webhook_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = local.function_name
  role            = var.lambda_execution_role_arn
  handler         = "webhook_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size

  environment {
    variables = {
      GITHUB_WEBHOOK_SECRET = var.github_webhook_secret
      BEDROCK_AGENT_ID      = var.bedrock_agent_id
      BEDROCK_AGENT_ALIAS_ID = var.bedrock_agent_alias_id
      RUNS_TABLE_NAME       = var.runs_table_name
      ARTIFACTS_BUCKET      = var.artifacts_bucket_name
      AWS_REGION           = data.aws_region.current.name
    }
  }

  tags = local.common_tags
}

# Lambda deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.lambda_source_path
  output_path = "${path.module}/lambda-deployment.zip"
  excludes    = ["__pycache__", "*.pyc", ".git", ".gitignore"]
}

# API Gateway
resource "aws_api_gateway_rest_api" "archon_api" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "Archon webhook API"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

# API Gateway resource
resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.archon_api.id
  parent_id   = aws_api_gateway_rest_api.archon_api.root_resource_id
  path_part   = "webhook"
}

# API Gateway method
resource "aws_api_gateway_method" "webhook_post" {
  rest_api_id   = aws_api_gateway_rest_api.archon_api.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway integration
resource "aws_api_gateway_integration" "webhook_lambda" {
  rest_api_id = aws_api_gateway_rest_api.archon_api.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.webhook_handler.invoke_arn
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.archon_api.execution_arn}/*/*"
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "archon_deployment" {
  depends_on = [
    aws_api_gateway_integration.webhook_lambda,
  ]

  rest_api_id = aws_api_gateway_rest_api.archon_api.id
  stage_name  = var.environment

  lifecycle {
    create_before_destroy = true
  }
}

# Health check endpoint
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.archon_api.id
  parent_id   = aws_api_gateway_rest_api.archon_api.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.archon_api.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health_lambda" {
  rest_api_id = aws_api_gateway_rest_api.archon_api.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.webhook_handler.invoke_arn
}

# Outputs
output "webhook_function_name" {
  description = "Webhook Lambda function name"
  value       = aws_lambda_function.webhook_handler.function_name
}

output "webhook_function_arn" {
  description = "Webhook Lambda function ARN"
  value       = aws_lambda_function.webhook_handler.arn
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = "https://${aws_api_gateway_rest_api.archon_api.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${var.environment}"
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.archon_api.id
}

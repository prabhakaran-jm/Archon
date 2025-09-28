# Archon Infrastructure - Outputs
# Centralized output definitions

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = module.api_gateway.api_gateway_url
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

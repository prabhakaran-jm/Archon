# Multi-Region Configuration Module for Archon
# Provides cross-region deployment and failover capabilities

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Data sources for all regions
data "aws_region" "primary" {
  provider = aws.primary
}

data "aws_region" "secondary" {
  provider = aws.secondary
}

# Multi-region configuration stored in DynamoDB
resource "aws_dynamodb_table" "multi_region_config" {
  provider = aws.primary
  
  name           = "${var.name_prefix}-multi-region-config"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "region_name"
  
  attribute {
    name = "region_name"
    type = "S"
  }
  
  attribute {
    name = "status"
    type = "S"
  }
  
  global_secondary_index {
    name     = "status-index"
    hash_key = "status"
  }
  
  point_in_time_recovery {
    enabled = true
  }
  
  server_side_encryption {
    enabled = true
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-multi-region-config"
  })
}

# Cross-region replication for DynamoDB
resource "aws_dynamodb_table" "multi_region_config_replica" {
  provider = aws.secondary
  
  name           = "${var.name_prefix}-multi-region-config"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "region_name"
  
  attribute {
    name = "region_name"
    type = "S"
  }
  
  attribute {
    name = "status"
    type = "S"
  }
  
  global_secondary_index {
    name     = "status-index"
    hash_key = "status"
  }
  
  point_in_time_recovery {
    enabled = true
  }
  
  server_side_encryption {
    enabled = true
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-multi-region-config-replica"
  })
}

# Lambda function for health checks
resource "aws_lambda_function" "health_checker" {
  provider = aws.primary
  
  filename         = data.archive_file.health_checker_zip.output_path
  function_name    = "${var.name_prefix}-health-checker"
  role            = aws_iam_role.health_checker.arn
  handler         = "health_checker.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  
  environment {
    variables = {
      PRIMARY_REGION   = data.aws_region.primary.name
      SECONDARY_REGION = data.aws_region.secondary.name
      CONFIG_TABLE    = aws_dynamodb_table.multi_region_config.name
    }
  }
  
  vpc_config {
    subnet_ids         = var.primary_subnet_ids
    security_group_ids = [aws_security_group.health_checker.id]
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-health-checker"
  })
}

# Lambda function code
data "archive_file" "health_checker_zip" {
  type        = "zip"
  output_path = "/tmp/health_checker.zip"
  
  source {
    content = templatefile("${path.module}/health_checker.py", {
      primary_region   = data.aws_region.primary.name
      secondary_region = data.aws_region.secondary.name
    })
    filename = "health_checker.py"
  }
}

# Health checker Lambda source code
resource "local_file" "health_checker_source" {
  content = templatefile("${path.module}/health_checker.py", {
    primary_region   = data.aws_region.primary.name
    secondary_region = data.aws_region.secondary.name
  })
  filename = "${path.module}/health_checker.py"
}

# IAM role for health checker
resource "aws_iam_role" "health_checker" {
  provider = aws.primary
  
  name = "${var.name_prefix}-health-checker-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-health-checker-role"
  })
}

# IAM policy for health checker
resource "aws_iam_policy" "health_checker" {
  provider = aws.primary
  
  name        = "${var.name_prefix}-health-checker-policy"
  description = "Policy for health checker Lambda function"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.multi_region_config.arn,
          "${aws_dynamodb_table.multi_region_config.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "lambda:GetFunction"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "apigateway:GET"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-health-checker-policy"
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "health_checker" {
  provider = aws.primary
  
  role       = aws_iam_role.health_checker.name
  policy_arn = aws_iam_policy.health_checker.arn
}

# Security group for health checker
resource "aws_security_group" "health_checker" {
  provider = aws.primary
  
  name_prefix = "${var.name_prefix}-health-checker-"
  vpc_id      = var.primary_vpc_id
  description = "Security group for health checker Lambda"
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-health-checker-sg"
  })
}

# EventBridge rule for health checks
resource "aws_cloudwatch_event_rule" "health_check" {
  provider = aws.primary
  
  name                = "${var.name_prefix}-health-check"
  description         = "Trigger health checks every 5 minutes"
  schedule_expression = "rate(5 minutes)"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-health-check-rule"
  })
}

# EventBridge target
resource "aws_cloudwatch_event_target" "health_check" {
  provider = aws.primary
  
  rule      = aws_cloudwatch_event_rule.health_check.name
  target_id = "HealthCheckTarget"
  arn       = aws_lambda_function.health_checker.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "health_check" {
  provider = aws.primary
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_checker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_check.arn
}

# CloudWatch alarms for multi-region health
resource "aws_cloudwatch_metric_alarm" "primary_region_down" {
  provider = aws.primary
  
  alarm_name          = "${var.name_prefix}-primary-region-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthyRegions"
  namespace           = "Archon/MultiRegion"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Primary region is down"
  alarm_actions       = var.alarm_actions
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-primary-region-down-alarm"
  })
}

# SNS topic for multi-region notifications
resource "aws_sns_topic" "multi_region_alerts" {
  provider = aws.primary
  
  name = "${var.name_prefix}-multi-region-alerts"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-multi-region-alerts"
  })
}

# Outputs
output "config_table_name" {
  description = "Multi-region configuration table name"
  value       = aws_dynamodb_table.multi_region_config.name
}

output "health_checker_function_name" {
  description = "Health checker Lambda function name"
  value       = aws_lambda_function.health_checker.function_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for multi-region alerts"
  value       = aws_sns_topic.multi_region_alerts.arn
}

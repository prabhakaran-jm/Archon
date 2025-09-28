# ElastiCache Redis Cluster for Archon Advanced Caching
# Provides high-performance caching layer with Redis

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

# Security group for Redis
resource "aws_security_group" "redis" {
  name_prefix = "${var.name_prefix}-redis-"
  vpc_id      = var.vpc_id
  description = "Security group for Redis ElastiCache cluster"

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "Redis access from Lambda functions"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-sg"
  })
}

# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.name_prefix}-redis-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-subnet-group"
  })
}

# ElastiCache parameter group
resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7.x"
  name   = "${var.name_prefix}-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-params"
  })
}

# ElastiCache Redis cluster
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id         = "${var.name_prefix}-redis"
  description                  = "Redis cluster for Archon caching"
  
  # Node configuration
  node_type                    = var.node_type
  port                         = 6379
  parameter_group_name         = aws_elasticache_parameter_group.redis.name
  
  # Cluster configuration
  num_cache_clusters           = var.num_cache_nodes
  automatic_failover_enabled   = var.num_cache_nodes > 1
  multi_az_enabled            = var.num_cache_nodes > 1
  
  # Network configuration
  subnet_group_name           = aws_elasticache_subnet_group.redis.name
  security_group_ids          = [aws_security_group.redis.id]
  
  # Backup configuration
  snapshot_retention_limit    = var.snapshot_retention_days
  snapshot_window             = var.snapshot_window
  maintenance_window          = var.maintenance_window
  
  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  
  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis"
  })
}

# CloudWatch log group for Redis logs
resource "aws_cloudwatch_log_group" "redis" {
  name              = "/aws/elasticache/redis/${var.name_prefix}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-logs"
  })
}

# CloudWatch alarms for Redis
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${var.name_prefix}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Redis CPU utilization is high"
  alarm_actions       = var.alarm_actions

  dimensions = {
    CacheClusterId = aws_elasticache_replication_group.redis.id
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-cpu-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${var.name_prefix}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "Redis memory usage is high"
  alarm_actions       = var.alarm_actions

  dimensions = {
    CacheClusterId = aws_elasticache_replication_group.redis.id
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-memory-alarm"
  })
}

# IAM role for Lambda functions to access Redis
resource "aws_iam_role" "redis_access" {
  name = "${var.name_prefix}-redis-access-role"

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
    Name = "${var.name_prefix}-redis-access-role"
  })
}

# IAM policy for Redis access
resource "aws_iam_policy" "redis_access" {
  name        = "${var.name_prefix}-redis-access-policy"
  description = "Policy for Lambda functions to access Redis"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "elasticache:DescribeReplicationGroups",
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeCacheSubnetGroups"
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
    Name = "${var.name_prefix}-redis-access-policy"
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "redis_access" {
  role       = aws_iam_role.redis_access.name
  policy_arn = aws_iam_policy.redis_access.arn
}

# VPC endpoint for ElastiCache (if needed)
resource "aws_vpc_endpoint" "elasticache" {
  count = var.create_vpc_endpoint ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.elasticache"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.redis.id]
  
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-elasticache-endpoint"
  })
}

# Data source for current region
data "aws_region" "current" {}

# Outputs
output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis cluster port"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_security_group_id" {
  description = "Security group ID for Redis"
  value       = aws_security_group.redis.id
}

output "redis_access_role_arn" {
  description = "IAM role ARN for Redis access"
  value       = aws_iam_role.redis_access.arn
}

output "redis_cluster_id" {
  description = "Redis cluster ID"
  value       = aws_elasticache_replication_group.redis.id
}

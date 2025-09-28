# Archon Scripts

This directory contains deployment, configuration, and monitoring scripts for Archon.

## Scripts Overview

### Deployment Scripts

#### `deploy.sh` 
Automated deployment script for Archon infrastructure.

**Features:**
- Prerequisites checking (AWS CLI, Terraform)
- S3 backend bucket creation
- DynamoDB state locking table creation
- Terraform initialization and deployment
- Environment-specific configuration
- Output generation

**Usage:**
```bash
# Deploy to development environment
./deploy.sh deploy dev

# Deploy to production environment
./deploy.sh deploy prod

# Plan changes without applying
./deploy.sh plan staging

# Destroy infrastructure
./deploy.sh destroy dev

# Show deployment status
./deploy.sh status prod
```

### Configuration Scripts

#### `config.sh`
Configuration management script for environment variables and secrets.

**Features:**
- Configuration template generation
- Environment variable loading
- Configuration validation
- Multi-component configuration export
- Secrets management

**Usage:**
```bash
# Initialize configuration templates
./config.sh dev init

# Load and validate configuration
./config.sh dev load

# Export configuration to all components
./config.sh dev export

# Show current configuration
./config.sh dev show

# Validate configuration only
./config.sh dev validate
```

### Monitoring Scripts

#### `health-check.sh`
Health check and monitoring script for Archon components.

**Features:**
- API Gateway health checks
- Lambda function status monitoring
- S3 bucket status verification
- DynamoDB table status checking
- ECS cluster monitoring
- CloudWatch metrics analysis
- Continuous monitoring mode

**Usage:**
```bash
# Run comprehensive health check
./health-check.sh dev health

# Monitor API Gateway continuously
./health-check.sh dev monitor api

# Check specific components
./health-check.sh dev lambda
./health-check.sh dev s3
./health-check.sh dev dynamodb
./health-check.sh dev ecs
./health-check.sh dev metrics
```

## Environment Configuration

### Required Environment Variables

#### AWS Configuration
- `AWS_REGION`: AWS region (default: us-east-1)
- `AWS_ACCESS_KEY_ID`: AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key

#### GitHub Configuration
- `GITHUB_WEBHOOK_SECRET`: GitHub webhook secret
- `GITHUB_TOKEN`: GitHub personal access token

#### Bedrock Configuration
- `BEDROCK_AGENT_ID`: Bedrock Agent ID
- `BEDROCK_AGENT_ALIAS_ID`: Bedrock Agent Alias ID
- `KNOWLEDGE_BASE_ID`: Bedrock Knowledge Base ID

### Configuration Files

#### `config/secrets.env`
Contains sensitive configuration values:
```bash
# GitHub Configuration
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_TOKEN=your-github-token

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Bedrock Configuration
BEDROCK_AGENT_ID=your-agent-id
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
KNOWLEDGE_BASE_ID=your-kb-id
```

#### `config/config.env`
Contains non-sensitive configuration:
```bash
# Application Configuration
APP_NAME=Archon
APP_VERSION=1.0.0
ENVIRONMENT=dev

# Feature Flags
ENABLE_DEEP_SCAN=true
ENABLE_AUTO_FIX=true
ENABLE_METRICS=true

# Performance Configuration
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30
CACHE_TTL=3600
```

## Deployment Workflow

### 1. Initial Setup
```bash
# Initialize configuration templates
./config.sh dev init

# Copy and customize configuration files
cp config/secrets.env.template config/secrets.env
cp config/config.env.template config/config.env

# Edit configuration files with actual values
vim config/secrets.env
vim config/config.env
```

### 2. Deploy Infrastructure
```bash
# Load configuration
./config.sh dev load

# Export configuration to components
./config.sh dev export

# Deploy infrastructure
./deploy.sh deploy dev
```

### 3. Verify Deployment
```bash
# Run health checks
./health-check.sh dev health

# Monitor specific components
./health-check.sh dev monitor api
```

## Troubleshooting

### Common Issues

#### AWS Credentials Not Configured
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
```

#### Terraform State Lock Issues
```bash
# Force unlock Terraform state
terraform force-unlock <lock-id>

# Or destroy and recreate
./deploy.sh destroy dev
./deploy.sh deploy dev
```

#### Configuration Validation Errors
```bash
# Validate configuration
./config.sh dev validate

# Check specific environment variables
./config.sh dev show
```

### Log Files
- Terraform logs: `infra/terraform.log`
- Deployment logs: `deploy.log`
- Health check logs: `health-check.log`

## Security Considerations

### Secrets Management
- Never commit `secrets.env` to version control
- Use AWS Secrets Manager for production secrets
- Rotate secrets regularly
- Use least privilege IAM policies

### Access Control
- Use IAM roles instead of access keys when possible
- Implement proper VPC security groups
- Enable CloudTrail for audit logging
- Use AWS Config for compliance monitoring

## Contributing

### Adding New Scripts
1. Follow the existing naming convention
2. Include proper error handling
3. Add logging functions
4. Document usage and examples
5. Test on multiple environments

### Script Standards
- Use `set -e` for error handling
- Include proper logging functions
- Validate prerequisites
- Provide usage information
- Support multiple environments

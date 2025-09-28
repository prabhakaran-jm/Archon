#!/bin/bash

# Archon Configuration Management Script
# Manages environment variables, secrets, and configuration

set -e

# Configuration
ENVIRONMENT=${1:-dev}
CONFIG_DIR="config"
SECRETS_FILE="${CONFIG_DIR}/secrets.env"
CONFIG_FILE="${CONFIG_DIR}/config.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create config directory
create_config_dir() {
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
        log_info "Created config directory: $CONFIG_DIR"
    fi
}

# Create secrets template
create_secrets_template() {
    log_info "Creating secrets template..."
    
    cat > "${SECRETS_FILE}.template" << 'EOF'
# Archon Secrets Configuration
# Copy this file to secrets.env and fill in the actual values

# GitHub Configuration
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret-here
GITHUB_TOKEN=your-github-token-here

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# Bedrock Configuration
BEDROCK_AGENT_ID=your-bedrock-agent-id
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
KNOWLEDGE_BASE_ID=your-knowledge-base-id

# Database Configuration
DATABASE_URL=your-database-url
REDIS_URL=your-redis-url

# Monitoring Configuration
SENTRY_DSN=your-sentry-dsn
LOG_LEVEL=INFO
EOF
    
    log_info "Secrets template created: ${SECRETS_FILE}.template"
}

# Create configuration template
create_config_template() {
    log_info "Creating configuration template..."
    
    cat > "${CONFIG_FILE}.template" << 'EOF'
# Archon Configuration
# Environment-specific configuration

# Application Configuration
APP_NAME=Archon
APP_VERSION=1.0.0
ENVIRONMENT=dev

# API Configuration
API_PORT=8080
API_HOST=0.0.0.0
CORS_ORIGINS=*

# Feature Flags
ENABLE_DEEP_SCAN=true
ENABLE_AUTO_FIX=true
ENABLE_METRICS=true

# Performance Configuration
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30
CACHE_TTL=3600

# Logging Configuration
LOG_FORMAT=json
LOG_OUTPUT=stdout

# Monitoring Configuration
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL=30
EOF
    
    log_info "Configuration template created: ${CONFIG_FILE}.template"
}

# Load environment variables
load_env() {
    if [ -f "$SECRETS_FILE" ]; then
        log_info "Loading secrets from $SECRETS_FILE"
        set -a
        source "$SECRETS_FILE"
        set +a
    else
        log_warn "Secrets file not found: $SECRETS_FILE"
        log_info "Please copy ${SECRETS_FILE}.template to $SECRETS_FILE and fill in the values"
    fi
    
    if [ -f "$CONFIG_FILE" ]; then
        log_info "Loading configuration from $CONFIG_FILE"
        set -a
        source "$CONFIG_FILE"
        set +a
    else
        log_warn "Configuration file not found: $CONFIG_FILE"
        log_info "Please copy ${CONFIG_FILE}.template to $CONFIG_FILE and customize"
    fi
}

# Validate configuration
validate_config() {
    log_info "Validating configuration..."
    
    local errors=0
    
    # Check required environment variables
    if [ -z "$GITHUB_WEBHOOK_SECRET" ]; then
        log_error "GITHUB_WEBHOOK_SECRET is not set"
        ((errors++))
    fi
    
    if [ -z "$GITHUB_TOKEN" ]; then
        log_error "GITHUB_TOKEN is not set"
        ((errors++))
    fi
    
    if [ -z "$AWS_REGION" ]; then
        log_error "AWS_REGION is not set"
        ((errors++))
    fi
    
    if [ -z "$BEDROCK_AGENT_ID" ]; then
        log_warn "BEDROCK_AGENT_ID is not set (optional for testing)"
    fi
    
    if [ $errors -eq 0 ]; then
        log_info "Configuration validation passed"
    else
        log_error "Configuration validation failed with $errors errors"
        exit 1
    fi
}

# Export configuration for Terraform
export_terraform_config() {
    log_info "Exporting configuration for Terraform..."
    
    # Create terraform.tfvars from environment variables
    cat > "infra/terraform.tfvars" << EOF
# Generated from configuration management script
aws_region = "${AWS_REGION:-us-east-1}"
environment = "${ENVIRONMENT}"

# GitHub Configuration
github_webhook_secret = "${GITHUB_WEBHOOK_SECRET}"
github_token_value = "${GITHUB_TOKEN}"

# Bedrock Configuration
bedrock_agent_id = "${BEDROCK_AGENT_ID:-}"
bedrock_agent_alias_id = "${BEDROCK_AGENT_ALIAS_ID:-TSTALIASID}"
knowledge_base_id = "${KNOWLEDGE_BASE_ID:-}"

# Networking Configuration
vpc_cidr = "10.0.0.0/16"
public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
enable_nat_gateway = true
enable_vpc_endpoints = true

# ECS Configuration
ecs_cluster_name = "archon-iac-cluster"
ecs_task_definition_name = "archon-iac-task"

# Secrets Configuration
github_token_secret_name = "archon/github/token"
EOF
    
    log_info "Terraform configuration exported to infra/terraform.tfvars"
}

# Export configuration for Lambda
export_lambda_config() {
    log_info "Exporting configuration for Lambda..."
    
    # Create .env file for Lambda
    cat > "lambda/.env" << EOF
# Lambda Environment Configuration
GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET}
BEDROCK_AGENT_ID=${BEDROCK_AGENT_ID:-}
BEDROCK_AGENT_ALIAS_ID=${BEDROCK_AGENT_ALIAS_ID:-TSTALIASID}
RUNS_TABLE_NAME=archon-runs-${ENVIRONMENT}
ARTIFACTS_BUCKET=archon-artifacts-${ENVIRONMENT}
AWS_REGION=${AWS_REGION:-us-east-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}
EOF
    
    log_info "Lambda configuration exported to lambda/.env"
}

# Export configuration for ECS
export_ecs_config() {
    log_info "Exporting configuration for ECS..."
    
    # Create ECS task environment file
    cat > "tools/run_iac_plan/.env" << EOF
# ECS Task Environment Configuration
ARTIFACTS_BUCKET=archon-artifacts-${ENVIRONMENT}
GITHUB_TOKEN_SECRET_NAME=archon/github/token
AWS_REGION=${AWS_REGION:-us-east-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}
EOF
    
    log_info "ECS configuration exported to tools/run_iac_plan/.env"
}

# Show current configuration
show_config() {
    log_info "Current configuration for $ENVIRONMENT environment:"
    echo ""
    echo "=== Application Configuration ==="
    echo "APP_NAME: ${APP_NAME:-Archon}"
    echo "APP_VERSION: ${APP_VERSION:-1.0.0}"
    echo "ENVIRONMENT: $ENVIRONMENT"
    echo "AWS_REGION: ${AWS_REGION:-us-east-1}"
    echo ""
    echo "=== Feature Flags ==="
    echo "ENABLE_DEEP_SCAN: ${ENABLE_DEEP_SCAN:-true}"
    echo "ENABLE_AUTO_FIX: ${ENABLE_AUTO_FIX:-true}"
    echo "ENABLE_METRICS: ${ENABLE_METRICS:-true}"
    echo ""
    echo "=== Performance Configuration ==="
    echo "MAX_CONCURRENT_REQUESTS: ${MAX_CONCURRENT_REQUESTS:-100}"
    echo "REQUEST_TIMEOUT: ${REQUEST_TIMEOUT:-30}"
    echo "CACHE_TTL: ${CACHE_TTL:-3600}"
    echo ""
    echo "=== Logging Configuration ==="
    echo "LOG_LEVEL: ${LOG_LEVEL:-INFO}"
    echo "LOG_FORMAT: ${LOG_FORMAT:-json}"
    echo "LOG_OUTPUT: ${LOG_OUTPUT:-stdout}"
}

# Main script logic
case "${2:-init}" in
    init)
        create_config_dir
        create_secrets_template
        create_config_template
        log_info "Configuration templates created. Please customize them and run 'config load'"
        ;;
    load)
        create_config_dir
        load_env
        validate_config
        log_info "Configuration loaded successfully"
        ;;
    export)
        load_env
        export_terraform_config
        export_lambda_config
        export_ecs_config
        log_info "Configuration exported to all components"
        ;;
    show)
        load_env
        show_config
        ;;
    validate)
        load_env
        validate_config
        ;;
    *)
        echo "Usage: $0 [ENVIRONMENT] [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  init     Create configuration templates"
        echo "  load     Load and validate configuration"
        echo "  export   Export configuration to all components"
        echo "  show     Show current configuration"
        echo "  validate Validate configuration only"
        echo ""
        echo "Environment:"
        echo "  dev      Development environment (default)"
        echo "  staging  Staging environment"
        echo "  prod     Production environment"
        echo ""
        echo "Examples:"
        echo "  $0 dev init"
        echo "  $0 prod load"
        echo "  $0 staging export"
        ;;
esac

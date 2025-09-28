#!/bin/bash

# Archon Deployment Script
# Automated deployment script for Archon infrastructure

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
TERRAFORM_DIR="infra"
BACKEND_BUCKET="archon-terraform-state-${ENVIRONMENT}"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Create S3 backend bucket
create_backend_bucket() {
    log_info "Creating S3 backend bucket: ${BACKEND_BUCKET}"
    
    if aws s3 ls "s3://${BACKEND_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
        aws s3 mb "s3://${BACKEND_BUCKET}" --region ${AWS_REGION}
        aws s3api put-bucket-versioning --bucket "${BACKEND_BUCKET}" --versioning-configuration Status=Enabled
        aws s3api put-bucket-encryption --bucket "${BACKEND_BUCKET}" --server-side-encryption-configuration '{
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        }'
        log_info "Backend bucket created successfully"
    else
        log_info "Backend bucket already exists"
    fi
}

# Create terraform.tfvars
create_tfvars() {
    log_info "Creating terraform.tfvars for ${ENVIRONMENT} environment"
    
    cat > ${TERRAFORM_DIR}/terraform.tfvars << EOF
# Archon Infrastructure Configuration - ${ENVIRONMENT}
aws_region = "${AWS_REGION}"
environment = "${ENVIRONMENT}"

# GitHub Configuration
github_webhook_secret = "${GITHUB_WEBHOOK_SECRET:-your-webhook-secret}"
github_token_value = "${GITHUB_TOKEN:-your-github-token}"

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
    
    log_info "terraform.tfvars created"
}

# Initialize Terraform
init_terraform() {
    log_info "Initializing Terraform..."
    
    cd ${TERRAFORM_DIR}
    
    # Create backend configuration
    cat > backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "${BACKEND_BUCKET}"
    key            = "archon-${ENVIRONMENT}.tfstate"
    region         = "${AWS_REGION}"
    encrypt        = true
    dynamodb_table = "archon-terraform-locks-${ENVIRONMENT}"
  }
}
EOF
    
    terraform init
    log_info "Terraform initialized"
}

# Create DynamoDB table for state locking
create_dynamodb_table() {
    log_info "Creating DynamoDB table for state locking"
    
    TABLE_NAME="archon-terraform-locks-${ENVIRONMENT}"
    
    if ! aws dynamodb describe-table --table-name "${TABLE_NAME}" &> /dev/null; then
        aws dynamodb create-table \
            --table-name "${TABLE_NAME}" \
            --attribute-definitions AttributeName=LockID,AttributeType=S \
            --key-schema AttributeName=LockID,KeyType=HASH \
            --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
        
        log_info "Waiting for DynamoDB table to be created..."
        aws dynamodb wait table-exists --table-name "${TABLE_NAME}"
        log_info "DynamoDB table created successfully"
    else
        log_info "DynamoDB table already exists"
    fi
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure for ${ENVIRONMENT} environment..."
    
    cd ${TERRAFORM_DIR}
    
    # Plan deployment
    log_info "Planning deployment..."
    terraform plan -var-file=terraform.tfvars -out=tfplan
    
    # Apply deployment
    log_info "Applying deployment..."
    terraform apply tfplan
    
    log_info "Infrastructure deployed successfully"
}

# Get deployment outputs
get_outputs() {
    log_info "Getting deployment outputs..."
    
    cd ${TERRAFORM_DIR}
    
    API_URL=$(terraform output -raw api_gateway_url)
    ARTIFACTS_BUCKET=$(terraform output -raw artifacts_bucket_name)
    RUNS_TABLE=$(terraform output -raw runs_table_name)
    ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
    
    echo ""
    log_info "=== Deployment Outputs ==="
    echo "API Gateway URL: ${API_URL}"
    echo "Artifacts Bucket: ${ARTIFACTS_BUCKET}"
    echo "Runs Table: ${RUNS_TABLE}"
    echo "ECS Cluster: ${ECS_CLUSTER}"
    echo ""
    
    log_info "Please update the following GitHub secrets:"
    echo "- API_GATEWAY_URL: ${API_URL}"
    echo "- ARTIFACTS_BUCKET: ${ARTIFACTS_BUCKET}"
    echo "- RUNS_TABLE: ${RUNS_TABLE}"
    echo "- ECS_CLUSTER: ${ECS_CLUSTER}"
}

# Main deployment function
deploy() {
    log_info "Starting Archon deployment for ${ENVIRONMENT} environment"
    
    check_prerequisites
    create_backend_bucket
    create_dynamodb_table
    create_tfvars
    init_terraform
    deploy_infrastructure
    get_outputs
    
    log_info "Deployment completed successfully!"
}

# Destroy infrastructure
destroy() {
    log_warn "Destroying infrastructure for ${ENVIRONMENT} environment"
    
    cd ${TERRAFORM_DIR}
    
    terraform destroy -var-file=terraform.tfvars -auto-approve
    
    log_info "Infrastructure destroyed"
}

# Show usage
usage() {
    echo "Usage: $0 [COMMAND] [ENVIRONMENT]"
    echo ""
    echo "Commands:"
    echo "  deploy   Deploy infrastructure (default)"
    echo "  destroy  Destroy infrastructure"
    echo "  plan     Plan infrastructure changes"
    echo "  status   Show deployment status"
    echo ""
    echo "Environment:"
    echo "  dev      Development environment (default)"
    echo "  staging  Staging environment"
    echo "  prod     Production environment"
    echo ""
    echo "Examples:"
    echo "  $0 deploy dev"
    echo "  $0 destroy prod"
    echo "  $0 plan staging"
}

# Plan infrastructure
plan() {
    log_info "Planning infrastructure changes for ${ENVIRONMENT} environment"
    
    cd ${TERRAFORM_DIR}
    terraform plan -var-file=terraform.tfvars
}

# Show status
status() {
    log_info "Showing deployment status for ${ENVIRONMENT} environment"
    
    cd ${TERRAFORM_DIR}
    terraform output
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    destroy)
        destroy
        ;;
    plan)
        plan
        ;;
    status)
        status
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac

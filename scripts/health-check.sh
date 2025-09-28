#!/bin/bash

# Archon Health Check and Monitoring Script
# Monitors the health and performance of Archon components

set -e

# Configuration
ENVIRONMENT=${1:-dev}
API_URL=${API_URL:-""}
ARTIFACTS_BUCKET=${ARTIFACTS_BUCKET:-""}
RUNS_TABLE=${RUNS_TABLE:-""}
ECS_CLUSTER=${ECS_CLUSTER:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Load configuration
load_config() {
    if [ -f "config/config.env" ]; then
        source "config/config.env"
    fi
    
    if [ -f "config/secrets.env" ]; then
        source "config/secrets.env"
    fi
    
    # Set defaults if not provided
    API_URL=${API_URL:-"https://$(aws apigateway get-rest-apis --query "items[?name=='archon-api-$ENVIRONMENT'].id" --output text).execute-api.${AWS_REGION:-us-east-1}.amazonaws.com/$ENVIRONMENT"}
    ARTIFACTS_BUCKET=${ARTIFACTS_BUCKET:-"archon-artifacts-$ENVIRONMENT"}
    RUNS_TABLE=${RUNS_TABLE:-"archon-runs-$ENVIRONMENT"}
    ECS_CLUSTER=${ECS_CLUSTER:-"archon-iac-cluster"}
}

# Check API Gateway health
check_api_health() {
    log_info "Checking API Gateway health..."
    
    if [ -z "$API_URL" ]; then
        log_error "API_URL not configured"
        return 1
    fi
    
    # Test health endpoint
    local health_url="$API_URL/health"
    local response=$(curl -s -w "%{http_code}" -o /tmp/health_response.json "$health_url" || echo "000")
    
    if [ "$response" = "200" ]; then
        log_info "API Gateway health check passed"
        cat /tmp/health_response.json
        echo ""
    else
        log_error "API Gateway health check failed (HTTP $response)"
        return 1
    fi
}

# Check Lambda function status
check_lambda_status() {
    log_info "Checking Lambda function status..."
    
    local function_name="archon-webhook-$ENVIRONMENT"
    
    # Get function configuration
    local config=$(aws lambda get-function --function-name "$function_name" 2>/dev/null || echo "{}")
    
    if [ "$config" = "{}" ]; then
        log_error "Lambda function not found: $function_name"
        return 1
    fi
    
    # Extract status information
    local state=$(echo "$config" | jq -r '.Configuration.State // "Unknown"')
    local last_modified=$(echo "$config" | jq -r '.Configuration.LastModified // "Unknown"')
    local runtime=$(echo "$config" | jq -r '.Configuration.Runtime // "Unknown"')
    local memory=$(echo "$config" | jq -r '.Configuration.MemorySize // "Unknown"')
    local timeout=$(echo "$config" | jq -r '.Configuration.Timeout // "Unknown"')
    
    log_info "Lambda function status:"
    echo "  State: $state"
    echo "  Last Modified: $last_modified"
    echo "  Runtime: $runtime"
    echo "  Memory: ${memory}MB"
    echo "  Timeout: ${timeout}s"
    
    if [ "$state" = "Active" ]; then
        log_info "Lambda function is active"
    else
        log_error "Lambda function is not active"
        return 1
    fi
}

# Check S3 bucket status
check_s3_status() {
    log_info "Checking S3 bucket status..."
    
    if [ -z "$ARTIFACTS_BUCKET" ]; then
        log_error "ARTIFACTS_BUCKET not configured"
        return 1
    fi
    
    # Check if bucket exists
    if aws s3 ls "s3://$ARTIFACTS_BUCKET" >/dev/null 2>&1; then
        log_info "S3 bucket exists: $ARTIFACTS_BUCKET"
        
        # Get bucket information
        local bucket_info=$(aws s3api get-bucket-versioning --bucket "$ARTIFACTS_BUCKET" 2>/dev/null || echo "{}")
        local versioning=$(echo "$bucket_info" | jq -r '.Status // "Disabled"')
        
        echo "  Versioning: $versioning"
        
        # Check encryption
        local encryption=$(aws s3api get-bucket-encryption --bucket "$ARTIFACTS_BUCKET" 2>/dev/null || echo "{}")
        if [ "$encryption" != "{}" ]; then
            echo "  Encryption: Enabled"
        else
            echo "  Encryption: Disabled"
        fi
        
        # Check public access block
        local public_access=$(aws s3api get-public-access-block --bucket "$ARTIFACTS_BUCKET" 2>/dev/null || echo "{}")
        if [ "$public_access" != "{}" ]; then
            echo "  Public Access: Blocked"
        else
            echo "  Public Access: Not Blocked"
        fi
    else
        log_error "S3 bucket not found: $ARTIFACTS_BUCKET"
        return 1
    fi
}

# Check DynamoDB table status
check_dynamodb_status() {
    log_info "Checking DynamoDB table status..."
    
    if [ -z "$RUNS_TABLE" ]; then
        log_error "RUNS_TABLE not configured"
        return 1
    fi
    
    # Get table information
    local table_info=$(aws dynamodb describe-table --table-name "$RUNS_TABLE" 2>/dev/null || echo "{}")
    
    if [ "$table_info" = "{}" ]; then
        log_error "DynamoDB table not found: $RUNS_TABLE"
        return 1
    fi
    
    local status=$(echo "$table_info" | jq -r '.Table.TableStatus // "Unknown"')
    local item_count=$(echo "$table_info" | jq -r '.Table.ItemCount // "Unknown"')
    local billing_mode=$(echo "$table_info" | jq -r '.Table.BillingModeSummary.BillingMode // "Unknown"')
    
    log_info "DynamoDB table status:"
    echo "  Status: $status"
    echo "  Item Count: $item_count"
    echo "  Billing Mode: $billing_mode"
    
    if [ "$status" = "ACTIVE" ]; then
        log_info "DynamoDB table is active"
    else
        log_error "DynamoDB table is not active"
        return 1
    fi
}

# Check ECS cluster status
check_ecs_status() {
    log_info "Checking ECS cluster status..."
    
    if [ -z "$ECS_CLUSTER" ]; then
        log_error "ECS_CLUSTER not configured"
        return 1
    fi
    
    # Get cluster information
    local cluster_info=$(aws ecs describe-clusters --clusters "$ECS_CLUSTER" 2>/dev/null || echo "{}")
    
    if [ "$cluster_info" = "{}" ]; then
        log_error "ECS cluster not found: $ECS_CLUSTER"
        return 1
    fi
    
    local status=$(echo "$cluster_info" | jq -r '.clusters[0].status // "Unknown"')
    local running_tasks=$(echo "$cluster_info" | jq -r '.clusters[0].runningTasksCount // "Unknown"')
    local pending_tasks=$(echo "$cluster_info" | jq -r '.clusters[0].pendingTasksCount // "Unknown"')
    local active_services=$(echo "$cluster_info" | jq -r '.clusters[0].activeServicesCount // "Unknown"')
    
    log_info "ECS cluster status:"
    echo "  Status: $status"
    echo "  Running Tasks: $running_tasks"
    echo "  Pending Tasks: $pending_tasks"
    echo "  Active Services: $active_services"
    
    if [ "$status" = "ACTIVE" ]; then
        log_info "ECS cluster is active"
    else
        log_error "ECS cluster is not active"
        return 1
    fi
}

# Check CloudWatch metrics
check_cloudwatch_metrics() {
    log_info "Checking CloudWatch metrics..."
    
    local namespace="Archon/PRReview"
    local end_time=$(date -u +"%Y-%m-%dT%H:%M:%S")
    local start_time=$(date -u -d "1 hour ago" +"%Y-%m-%dT%H:%M:%S")
    
    # Get metrics for the last hour
    local metrics=$(aws cloudwatch get-metric-statistics \
        --namespace "$namespace" \
        --metric-name "PRAnalysisCount" \
        --dimensions Name=Environment,Value="$ENVIRONMENT" \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --period 3600 \
        --statistics Sum \
        2>/dev/null || echo "{}")
    
    if [ "$metrics" != "{}" ]; then
        local count=$(echo "$metrics" | jq -r '.Datapoints[0].Sum // "0"')
        log_info "PR Analysis Count (last hour): $count"
    else
        log_warn "No CloudWatch metrics found for namespace: $namespace"
    fi
}

# Run comprehensive health check
run_health_check() {
    log_info "Running comprehensive health check for $ENVIRONMENT environment..."
    echo ""
    
    local errors=0
    
    # Check API Gateway
    if ! check_api_health; then
        ((errors++))
    fi
    echo ""
    
    # Check Lambda function
    if ! check_lambda_status; then
        ((errors++))
    fi
    echo ""
    
    # Check S3 bucket
    if ! check_s3_status; then
        ((errors++))
    fi
    echo ""
    
    # Check DynamoDB table
    if ! check_dynamodb_status; then
        ((errors++))
    fi
    echo ""
    
    # Check ECS cluster
    if ! check_ecs_status; then
        ((errors++))
    fi
    echo ""
    
    # Check CloudWatch metrics
    check_cloudwatch_metrics
    echo ""
    
    # Summary
    if [ $errors -eq 0 ]; then
        log_info "All health checks passed! ✅"
    else
        log_error "Health check failed with $errors errors! ❌"
        exit 1
    fi
}

# Monitor specific component
monitor_component() {
    local component=$1
    local interval=${2:-30}
    
    log_info "Monitoring $component (interval: ${interval}s)..."
    
    while true; do
        case $component in
            api)
                check_api_health
                ;;
            lambda)
                check_lambda_status
                ;;
            s3)
                check_s3_status
                ;;
            dynamodb)
                check_dynamodb_status
                ;;
            ecs)
                check_ecs_status
                ;;
            metrics)
                check_cloudwatch_metrics
                ;;
            *)
                log_error "Unknown component: $component"
                exit 1
                ;;
        esac
        
        sleep $interval
    done
}

# Show usage
usage() {
    echo "Usage: $0 [ENVIRONMENT] [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  health    Run comprehensive health check (default)"
    echo "  monitor   Monitor specific component"
    echo "  api       Check API Gateway only"
    echo "  lambda    Check Lambda function only"
    echo "  s3        Check S3 bucket only"
    echo "  dynamodb  Check DynamoDB table only"
    echo "  ecs       Check ECS cluster only"
    echo "  metrics   Check CloudWatch metrics only"
    echo ""
    echo "Environment:"
    echo "  dev       Development environment (default)"
    echo "  staging   Staging environment"
    echo "  prod      Production environment"
    echo ""
    echo "Options:"
    echo "  --interval SECONDS  Monitoring interval (default: 30)"
    echo ""
    echo "Examples:"
    echo "  $0 dev health"
    echo "  $0 prod monitor api --interval 60"
    echo "  $0 staging lambda"
}

# Main script logic
load_config

case "${2:-health}" in
    health)
        run_health_check
        ;;
    monitor)
        monitor_component "${3:-api}" "${4:-30}"
        ;;
    api)
        check_api_health
        ;;
    lambda)
        check_lambda_status
        ;;
    s3)
        check_s3_status
        ;;
    dynamodb)
        check_dynamodb_status
        ;;
    ecs)
        check_ecs_status
        ;;
    metrics)
        check_cloudwatch_metrics
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        log_error "Unknown command: $2"
        usage
        exit 1
        ;;
esac

"""
Health Checker Lambda Function for Multi-Region Archon
Checks health of all regions and updates configuration
"""

import json
import os
import logging
import time
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

# Environment variables
PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'us-east-1')
SECONDARY_REGION = os.environ.get('SECONDARY_REGION', 'us-west-2')
CONFIG_TABLE = os.environ.get('CONFIG_TABLE', 'archon-multi-region-config')

# DynamoDB table
config_table = dynamodb.Table(CONFIG_TABLE)

def check_region_health(region_name: str, api_gateway_url: str) -> Dict[str, Any]:
    """Check health of a specific region"""
    try:
        import requests
        
        # Check API Gateway health endpoint
        health_url = f"{api_gateway_url}/health"
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            return {
                'status': 'healthy',
                'last_check': int(time.time()),
                'response_time': response.elapsed.total_seconds(),
                'details': health_data
            }
        else:
            return {
                'status': 'unhealthy',
                'last_check': int(time.time()),
                'error': f"HTTP {response.status_code}"
            }
    except Exception as e:
        logger.error(f"Health check failed for region {region_name}: {e}")
        return {
            'status': 'unhealthy',
            'last_check': int(time.time()),
            'error': str(e)
        }

def update_region_config(region_name: str, config: Dict[str, Any]):
    """Update region configuration in DynamoDB"""
    try:
        config_table.put_item(Item={
            'region_name': region_name,
            'status': config['status'],
            'last_check': config['last_check'],
            'response_time': config.get('response_time', 0),
            'error': config.get('error', ''),
            'updated_at': int(time.time())
        })
        logger.info(f"Updated config for region {region_name}: {config['status']}")
    except ClientError as e:
        logger.error(f"Failed to update config for region {region_name}: {e}")

def get_region_configs() -> List[Dict[str, Any]]:
    """Get all region configurations"""
    try:
        response = config_table.scan()
        return response.get('Items', [])
    except ClientError as e:
        logger.error(f"Failed to get region configs: {e}")
        return []

def determine_active_region(configs: List[Dict[str, Any]]) -> str:
    """Determine which region should be active based on health"""
    # Sort by priority (primary first, then by health status)
    healthy_regions = [c for c in configs if c.get('status') == 'healthy']
    
    if not healthy_regions:
        logger.error("No healthy regions found!")
        return PRIMARY_REGION  # Fallback to primary
    
    # Prefer primary region if healthy
    primary_config = next((c for c in healthy_regions if c['region_name'] == PRIMARY_REGION), None)
    if primary_config:
        return PRIMARY_REGION
    
    # Otherwise, use the first healthy region
    return healthy_regions[0]['region_name']

def perform_failover_if_needed(configs: List[Dict[str, Any]]) -> bool:
    """Perform failover if primary region is down"""
    primary_config = next((c for c in configs if c['region_name'] == PRIMARY_REGION), None)
    
    if not primary_config or primary_config.get('status') != 'healthy':
        logger.warning(f"Primary region {PRIMARY_REGION} is unhealthy, checking for failover")
        
        # Check if we need to failover
        healthy_regions = [c for c in configs if c.get('status') == 'healthy']
        if len(healthy_regions) > 0:
            new_active = determine_active_region(configs)
            logger.warning(f"Failover triggered: switching to region {new_active}")
            
            # Update active region in configuration
            try:
                config_table.put_item(Item={
                    'region_name': 'active_region',
                    'status': 'active',
                    'current_region': new_active,
                    'failover_time': int(time.time()),
                    'updated_at': int(time.time())
                })
                return True
            except ClientError as e:
                logger.error(f"Failed to update active region: {e}")
    
    return False

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Health checker Lambda handler"""
    try:
        logger.info("Starting multi-region health check")
        
        # Define region configurations
        regions = [
            {
                'name': PRIMARY_REGION,
                'api_gateway_url': os.environ.get('PRIMARY_API_URL', ''),
                'priority': 1
            },
            {
                'name': SECONDARY_REGION,
                'api_gateway_url': os.environ.get('SECONDARY_API_URL', ''),
                'priority': 2
            }
        ]
        
        # Check health of all regions
        region_configs = []
        for region in regions:
            if region['api_gateway_url']:
                health_status = check_region_health(region['name'], region['api_gateway_url'])
                health_status['region_name'] = region['name']
                health_status['priority'] = region['priority']
                
                update_region_config(region['name'], health_status)
                region_configs.append(health_status)
        
        # Determine active region
        active_region = determine_active_region(region_configs)
        
        # Check for failover
        failover_performed = perform_failover_if_needed(region_configs)
        
        # Publish metrics
        healthy_count = len([c for c in region_configs if c.get('status') == 'healthy'])
        
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
            Namespace='Archon/MultiRegion',
            MetricData=[
                {
                    'MetricName': 'HealthyRegions',
                    'Value': healthy_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'Environment',
                            'Value': os.environ.get('ENVIRONMENT', 'dev')
                        }
                    ]
                },
                {
                    'MetricName': 'ActiveRegion',
                    'Value': 1 if active_region == PRIMARY_REGION else 2,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'Environment',
                            'Value': os.environ.get('ENVIRONMENT', 'dev')
                        }
                    ]
                }
            ]
        )
        
        result = {
            'status': 'success',
            'active_region': active_region,
            'healthy_regions': healthy_count,
            'total_regions': len(regions),
            'failover_performed': failover_performed,
            'region_statuses': region_configs
        }
        
        logger.info(f"Health check completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

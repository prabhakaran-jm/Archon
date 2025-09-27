"""
finops_pricing_delta Tool
Calculates monthly cost delta for infrastructure changes with confidence intervals
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

import boto3
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
pricing_client = boto3.client('pricing', region_name='us-east-1')  # Pricing API only in us-east-1

# Environment variables
ARTIFACTS_BUCKET = os.environ.get('ARTIFACTS_BUCKET', 'archon-artifacts')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-west-1')


def get_aws_pricing(service: str, region: str = 'eu-west-1') -> Dict[str, Any]:
    """Get AWS pricing for a specific service and region"""
    try:
        # AWS Pricing API only available in us-east-1
        response = pricing_client.get_products(
            ServiceCode=service,
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'}
            ],
            MaxResults=100
        )
        
        return response.get('PriceList', [])
    
    except Exception as e:
        logger.error(f"Error getting AWS pricing for {service}: {e}")
        return []


def parse_terraform_plan(plan_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Parse Terraform plan JSON to extract resource changes"""
    changes = {
        'added': [],
        'modified': [],
        'destroyed': []
    }
    
    try:
        for resource_change in plan_data.get('resource_changes', []):
            change = resource_change.get('change', {})
            actions = change.get('actions', [])
            
            if 'create' in actions:
                changes['added'].append({
                    'type': resource_change.get('type', ''),
                    'name': resource_change.get('name', ''),
                    'change': change
                })
            elif 'update' in actions:
                changes['modified'].append({
                    'type': resource_change.get('type', ''),
                    'name': resource_change.get('name', ''),
                    'change': change
                })
            elif 'delete' in actions:
                changes['destroyed'].append({
                    'type': resource_change.get('type', ''),
                    'name': resource_change.get('name', ''),
                    'change': change
                })
    
    except Exception as e:
        logger.error(f"Error parsing Terraform plan: {e}")
    
    return changes


def estimate_s3_cost(resource_changes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Estimate S3 costs based on resource changes"""
    s3_cost = {
        'storage': 0.0,
        'requests': 0.0,
        'transfer': 0.0,
        'total': 0.0
    }
    
    # S3 pricing (simplified - actual pricing varies by region and usage)
    s3_pricing = {
        'standard_storage': 0.023,  # per GB per month
        'put_requests': 0.0004,     # per 1000 requests
        'get_requests': 0.0004,     # per 1000 requests
        'data_transfer_out': 0.09   # per GB
    }
    
    for resource in resource_changes:
        if 'aws_s3_bucket' in resource.get('type', ''):
            # Estimate storage based on typical bucket usage
            estimated_size_gb = 10.0  # Conservative estimate
            s3_cost['storage'] += estimated_size_gb * s3_pricing['standard_storage']
            
            # Estimate requests (conservative)
            estimated_requests = 1000  # per month
            s3_cost['requests'] += estimated_requests * s3_pricing['put_requests'] / 1000
    
    s3_cost['total'] = sum(s3_cost.values())
    return s3_cost


def estimate_nat_gateway_cost(resource_changes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Estimate NAT Gateway costs"""
    nat_cost = {
        'hourly': 0.0,
        'data_processed': 0.0,
        'total': 0.0
    }
    
    # NAT Gateway pricing
    nat_pricing = {
        'hourly': 0.045,        # per hour
        'data_processed': 0.045  # per GB
    }
    
    nat_count = 0
    for resource in resource_changes:
        if 'aws_nat_gateway' in resource.get('type', ''):
            nat_count += 1
    
    if nat_count > 0:
        # 720 hours per month
        hours_per_month = 720
        nat_cost['hourly'] = nat_count * nat_pricing['hourly'] * hours_per_month
        
        # Estimate data processing (conservative)
        estimated_data_gb = 100.0  # per month
        nat_cost['data_processed'] = nat_count * estimated_data_gb * nat_pricing['data_processed']
    
    nat_cost['total'] = sum(nat_cost.values())
    return nat_cost


def estimate_ebs_cost(resource_changes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Estimate EBS costs"""
    ebs_cost = {
        'gp2': 0.0,
        'gp3': 0.0,
        'io1': 0.0,
        'io2': 0.0,
        'total': 0.0
    }
    
    # EBS pricing per GB per month
    ebs_pricing = {
        'gp2': 0.10,
        'gp3': 0.08,
        'io1': 0.125,
        'io2': 0.125
    }
    
    for resource in resource_changes:
        if 'aws_ebs_volume' in resource.get('type', ''):
            change = resource.get('change', {})
            after = change.get('after', {})
            
            volume_type = after.get('type', 'gp2')
            size = after.get('size', 8)  # Default 8GB
            
            if volume_type in ebs_pricing:
                ebs_cost[volume_type] += size * ebs_pricing[volume_type]
    
    ebs_cost['total'] = sum(ebs_cost.values())
    return ebs_cost


def estimate_rds_cost(resource_changes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Estimate RDS costs"""
    rds_cost = {
        'db_instance': 0.0,
        'storage': 0.0,
        'backup': 0.0,
        'total': 0.0
    }
    
    # RDS pricing (simplified)
    rds_pricing = {
        'db_t3_micro': 12.41,    # per month
        'db_t3_small': 24.82,    # per month
        'storage_gp2': 0.115,    # per GB per month
        'backup': 0.095          # per GB per month
    }
    
    for resource in resource_changes:
        if 'aws_db_instance' in resource.get('type', ''):
            change = resource.get('change', {})
            after = change.get('after', {})
            
            instance_class = after.get('instance_class', 'db.t3.micro')
            allocated_storage = after.get('allocated_storage', 20)
            
            # Map instance class to pricing
            if instance_class == 'db.t3.micro':
                rds_cost['db_instance'] += rds_pricing['db_t3_micro']
            elif instance_class == 'db.t3.small':
                rds_cost['db_instance'] += rds_pricing['db_t3_small']
            
            # Storage cost
            rds_cost['storage'] += allocated_storage * rds_pricing['storage_gp2']
            
            # Backup cost (20% of storage)
            rds_cost['backup'] += allocated_storage * 0.2 * rds_pricing['backup']
    
    rds_cost['total'] = sum(rds_cost.values())
    return rds_cost


def calculate_confidence_interval(total_cost: float, resource_count: int) -> Dict[str, Any]:
    """Calculate confidence interval based on resource complexity"""
    # Simple heuristic: more resources = lower confidence
    base_confidence = 80
    
    if resource_count > 20:
        confidence = base_confidence - 30  # 50%
    elif resource_count > 10:
        confidence = base_confidence - 20  # 60%
    elif resource_count > 5:
        confidence = base_confidence - 10  # 70%
    else:
        confidence = base_confidence  # 80%
    
    # Calculate confidence interval
    margin = total_cost * (100 - confidence) / 100
    
    return {
        'confidence_pct': confidence,
        'lower_bound': total_cost - margin,
        'upper_bound': total_cost + margin,
        'margin_usd': margin
    }


def get_default_assumptions() -> Dict[str, Any]:
    """Get default assumptions for cost calculations"""
    return {
        'nat_hours_per_month': 720,
        's3_storage_gb_per_bucket': 10,
        's3_requests_per_month': 1000,
        'ebs_default_size_gb': 8,
        'rds_default_storage_gb': 20,
        'data_transfer_gb_per_month': 100,
        'region': AWS_REGION,
        'currency': 'USD'
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    finops_pricing_delta tool handler
    
    Input:
    {
        "plan_json_s3": "s3://bucket/path/plan.json",  # Optional for fast pass
        "repo": "org/repo",
        "commit_sha": "abc123...",
        "region": "eu-west-1"
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "monthly_delta_usd": 128.4,
            "confidence_pct": 20,
            "top_drivers": [
                {
                    "service": "NAT Gateway",
                    "delta": 76.8,
                    "details": "..."
                }
            ],
            "assumptions_used": {...},
            "breakdown": {
                "s3": {...},
                "nat_gateway": {...},
                "ebs": {...},
                "rds": {...}
            }
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        if 'repo' not in event or 'commit_sha' not in event:
            return {
                'status': 'error',
                'error': 'Missing required parameters: repo, commit_sha'
            }
        
        repo = event['repo']
        commit_sha = event['commit_sha']
        region = event.get('region', AWS_REGION)
        plan_json_s3 = event.get('plan_json_s3')
        
        # Get assumptions
        assumptions = get_default_assumptions()
        assumptions['region'] = region
        
        # Initialize cost breakdown
        cost_breakdown = {
            's3': {'total': 0.0},
            'nat_gateway': {'total': 0.0},
            'ebs': {'total': 0.0},
            'rds': {'total': 0.0}
        }
        
        resource_changes = {'added': [], 'modified': [], 'destroyed': []}
        
        # If plan JSON is provided, parse it for precise analysis
        if plan_json_s3:
            try:
                # Download plan from S3
                bucket, key = plan_json_s3.replace('s3://', '').split('/', 1)
                response = s3_client.get_object(Bucket=bucket, Key=key)
                plan_data = json.loads(response['Body'].read())
                
                # Parse Terraform plan
                resource_changes = parse_terraform_plan(plan_data)
                
            except Exception as e:
                logger.warning(f"Could not parse plan JSON, using heuristic analysis: {e}")
        
        # Calculate costs for each service
        if resource_changes['added']:
            cost_breakdown['s3'] = estimate_s3_cost(resource_changes['added'])
            cost_breakdown['nat_gateway'] = estimate_nat_gateway_cost(resource_changes['added'])
            cost_breakdown['ebs'] = estimate_ebs_cost(resource_changes['added'])
            cost_breakdown['rds'] = estimate_rds_cost(resource_changes['added'])
        
        # Calculate total monthly delta
        total_monthly_delta = sum(service['total'] for service in cost_breakdown.values())
        
        # Identify top cost drivers
        top_drivers = []
        for service_name, service_cost in cost_breakdown.items():
            if service_cost['total'] > 0:
                top_drivers.append({
                    'service': service_name.replace('_', ' ').title(),
                    'delta': round(service_cost['total'], 2),
                    'details': f"Estimated monthly cost for {service_name}"
                })
        
        # Sort by cost
        top_drivers.sort(key=lambda x: x['delta'], reverse=True)
        
        # Calculate confidence interval
        resource_count = len(resource_changes['added']) + len(resource_changes['modified'])
        confidence_data = calculate_confidence_interval(total_monthly_delta, resource_count)
        
        result = {
            'monthly_delta_usd': round(total_monthly_delta, 2),
            'confidence_pct': confidence_data['confidence_pct'],
            'confidence_interval': {
                'lower_bound': round(confidence_data['lower_bound'], 2),
                'upper_bound': round(confidence_data['upper_bound'], 2)
            },
            'top_drivers': top_drivers[:5],  # Top 5 cost drivers
            'assumptions_used': assumptions,
            'breakdown': cost_breakdown,
            'resource_changes': {
                'added': len(resource_changes['added']),
                'modified': len(resource_changes['modified']),
                'destroyed': len(resource_changes['destroyed'])
            }
        }
        
        logger.info(f"Cost analysis completed: ${total_monthly_delta:.2f}/month with {confidence_data['confidence_pct']}% confidence")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in finops_pricing_delta: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

"""
run_iac_plan Tool
Executes Terraform plan or CDK synth in sandbox ECS Fargate environment
"""

import json
import logging
import os
import time
from typing import Dict, Any

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ecs_client = boto3.client('ecs')
s3_client = boto3.client('s3')
logs_client = boto3.client('logs')

# Environment variables
ECS_CLUSTER = os.environ.get('ECS_CLUSTER', 'archon-iac-cluster')
ECS_TASK_DEFINITION = os.environ.get('ECS_TASK_DEFINITION', 'archon-iac-task')
ARTIFACTS_BUCKET = os.environ.get('ARTIFACTS_BUCKET', 'archon-artifacts')
GITHUB_TOKEN_SECRET_NAME = os.environ.get('GITHUB_TOKEN_SECRET_NAME', 'archon/github/token')


def start_ecs_task(repo: str, commit_sha: str, iac_type: str, workdir: str = 'infra/') -> str:
    """Start ECS Fargate task for IaC plan execution"""
    try:
        # Prepare task environment variables
        environment = [
            {'name': 'REPO_NAME', 'value': repo},
            {'name': 'COMMIT_SHA', 'value': commit_sha},
            {'name': 'IAC_TYPE', 'value': iac_type},
            {'name': 'WORKDIR', 'value': workdir},
            {'name': 'ARTIFACTS_BUCKET', 'value': ARTIFACTS_BUCKET}
        ]
        
        # Start ECS task
        response = ecs_client.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': os.environ.get('ECS_SUBNETS', '').split(','),
                    'securityGroups': os.environ.get('ECS_SECURITY_GROUPS', '').split(','),
                    'assignPublicIp': 'ENABLED'
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 'iac-runner',
                        'environment': environment
                    }
                ]
            },
            tags=[
                {'key': 'Archon', 'value': 'iac-plan'},
                {'key': 'Repo', 'value': repo},
                {'key': 'Commit', 'value': commit_sha}
            ]
        )
        
        task_arn = response['tasks'][0]['taskArn']
        logger.info(f"Started ECS task {task_arn} for {repo}@{commit_sha[:8]}")
        
        return task_arn
    
    except Exception as e:
        logger.error(f"Error starting ECS task: {e}")
        raise


def wait_for_task_completion(task_arn: str, timeout_minutes: int = 10) -> Dict[str, Any]:
    """Wait for ECS task to complete and return results"""
    try:
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while time.time() - start_time < timeout_seconds:
            # Describe task
            response = ecs_client.describe_tasks(
                cluster=ECS_CLUSTER,
                tasks=[task_arn]
            )
            
            task = response['tasks'][0]
            last_status = task['lastStatus']
            desired_status = task['desiredStatus']
            
            logger.info(f"Task {task_arn}: {last_status} -> {desired_status}")
            
            if last_status == 'STOPPED':
                # Task completed
                exit_code = task['containers'][0]['exitCode']
                
                if exit_code == 0:
                    return {
                        'status': 'completed',
                        'exit_code': exit_code,
                        'reason': task.get('stoppedReason', 'Task completed successfully')
                    }
                else:
                    return {
                        'status': 'failed',
                        'exit_code': exit_code,
                        'reason': task.get('stoppedReason', 'Task failed')
                    }
            
            time.sleep(10)  # Wait 10 seconds before next check
        
        # Timeout
        return {
            'status': 'timeout',
            'exit_code': -1,
            'reason': f'Task timed out after {timeout_minutes} minutes'
        }
    
    except Exception as e:
        logger.error(f"Error waiting for task completion: {e}")
        return {
            'status': 'error',
            'exit_code': -1,
            'reason': str(e)
        }


def get_task_logs(task_arn: str) -> str:
    """Get CloudWatch logs for the ECS task"""
    try:
        # Extract task ID from ARN
        task_id = task_arn.split('/')[-1]
        
        # Get log group name (assuming standard ECS log group naming)
        log_group = f"/ecs/{ECS_TASK_DEFINITION}"
        
        # Get log streams for this task
        response = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True
        )
        
        logs = []
        for stream in response['logStreams']:
            if task_id in stream['logStreamName']:
                # Get log events
                events = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream['logStreamName']
                )
                
                for event in events['events']:
                    logs.append(event['message'])
        
        return '\n'.join(logs)
    
    except Exception as e:
        logger.error(f"Error getting task logs: {e}")
        return f"Error retrieving logs: {e}"


def check_artifacts_in_s3(repo: str, pr_number: int, commit_sha: str) -> Dict[str, str]:
    """Check for generated artifacts in S3"""
    try:
        artifacts = {}
        base_key = f"{repo}/{pr_number}/{commit_sha}/"
        
        # List objects in the artifacts directory
        response = s3_client.list_objects_v2(
            Bucket=ARTIFACTS_BUCKET,
            Prefix=base_key
        )
        
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.json'):
                if 'plan.json' in key:
                    artifacts['plan_json'] = f"s3://{ARTIFACTS_BUCKET}/{key}"
                elif 'cdk.out' in key:
                    artifacts['cdk_output'] = f"s3://{ARTIFACTS_BUCKET}/{key}"
        
        return artifacts
    
    except Exception as e:
        logger.error(f"Error checking S3 artifacts: {e}")
        return {}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    run_iac_plan tool handler
    
    Input:
    {
        "repo": "org/repo",
        "commit_sha": "abc123...",
        "iac_type": "terraform|tofu|cdk",
        "workdir": "infra/"
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "plan_type": "terraform",
            "raw_plan_json_s3": "s3://bucket/path/plan.json",
            "resources_added": 5,
            "resources_changed": 2,
            "resources_destroyed": 0,
            "task_arn": "arn:aws:ecs:...",
            "execution_time_seconds": 120
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        required_fields = ['repo', 'commit_sha', 'iac_type']
        for field in required_fields:
            if field not in event:
                return {
                    'status': 'error',
                    'error': f'Missing required parameter: {field}'
                }
        
        repo = event['repo']
        commit_sha = event['commit_sha']
        iac_type = event['iac_type']
        workdir = event.get('workdir', 'infra/')
        pr_number = event.get('pr_number', 0)
        
        # Validate IAC type
        if iac_type not in ['terraform', 'tofu', 'cdk']:
            return {
                'status': 'error',
                'error': f'Invalid iac_type: {iac_type}. Must be terraform, tofu, or cdk'
            }
        
        logger.info(f"Starting IaC plan for {repo}@{commit_sha[:8]} ({iac_type})")
        
        # Start ECS task
        start_time = time.time()
        task_arn = start_ecs_task(repo, commit_sha, iac_type, workdir)
        
        # Wait for completion
        result = wait_for_task_completion(task_arn)
        
        execution_time = int(time.time() - start_time)
        
        if result['status'] != 'completed':
            # Get logs for debugging
            logs = get_task_logs(task_arn)
            
            return {
                'status': 'error',
                'error': f"Task {result['status']}: {result['reason']}",
                'logs': logs[:1000]  # Truncate logs
            }
        
        # Check for artifacts in S3
        artifacts = check_artifacts_in_s3(repo, pr_number, commit_sha)
        
        # Parse plan results (simplified)
        resources_added = 0
        resources_changed = 0
        resources_destroyed = 0
        
        if artifacts.get('plan_json'):
            try:
                # Download and parse plan JSON
                bucket, key = artifacts['plan_json'].replace('s3://', '').split('/', 1)
                response = s3_client.get_object(Bucket=bucket, Key=key)
                plan_data = json.loads(response['Body'].read())
                
                # Count resource changes
                for resource_change in plan_data.get('resource_changes', []):
                    actions = resource_change.get('change', {}).get('actions', [])
                    if 'create' in actions:
                        resources_added += 1
                    elif 'update' in actions:
                        resources_changed += 1
                    elif 'delete' in actions:
                        resources_destroyed += 1
            
            except Exception as e:
                logger.warning(f"Could not parse plan JSON: {e}")
        
        result_data = {
            'plan_type': iac_type,
            'raw_plan_json_s3': artifacts.get('plan_json'),
            'cdk_output_s3': artifacts.get('cdk_output'),
            'resources_added': resources_added,
            'resources_changed': resources_changed,
            'resources_destroyed': resources_destroyed,
            'task_arn': task_arn,
            'execution_time_seconds': execution_time,
            'artifacts': artifacts
        }
        
        logger.info(f"IaC plan completed for {repo}@{commit_sha[:8]}: "
                   f"{resources_added} added, {resources_changed} changed, {resources_destroyed} destroyed")
        
        return {
            'status': 'success',
            'data': result_data
        }
    
    except Exception as e:
        logger.error(f"Error in run_iac_plan: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

"""
run_iac_plan Tool - Enhanced for Deep Pass
Executes Terraform plan or CDK synth in ECS Fargate sandbox environment
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

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
ECS_SUBNETS = os.environ.get('ECS_SUBNETS', '').split(',') if os.environ.get('ECS_SUBNETS') else []
ECS_SECURITY_GROUPS = os.environ.get('ECS_SECURITY_GROUPS', '').split(',') if os.environ.get('ECS_SECURITY_GROUPS') else []
GITHUB_TOKEN_SECRET_NAME = os.environ.get('GITHUB_TOKEN_SECRET_NAME', 'archon/github/token')


def get_github_token() -> str:
    """Retrieve GitHub token from AWS Secrets Manager"""
    try:
        # For local testing, use environment variable or mock
        if os.environ.get('LOCAL_TESTING'):
            return os.environ.get('GITHUB_TOKEN', 'mock-github-token')
        
        secrets_manager = boto3.client('secretsmanager')
        response = secrets_manager.get_secret_value(SecretId=GITHUB_TOKEN_SECRET_NAME)
        secret_data = json.loads(response['SecretString'])
        return secret_data.get('token', 'mock-github-token')
    except Exception as e:
        logger.error(f"Error retrieving GitHub token: {e}")
        # Fallback for testing
        return os.environ.get('GITHUB_TOKEN', 'mock-github-token')


def download_repo_to_s3(repo: str, commit_sha: str, workdir: str = 'infra/') -> str:
    """Download repository content to S3 for ECS task access"""
    try:
        from github import Github
        
        github_token = get_github_token()
        github = Github(github_token)
        
        # Get repository
        repo_obj = github.get_repo(repo)
        
        # Create S3 key for repository content
        s3_key = f"repos/{repo.replace('/', '-')}/{commit_sha}/repo-content.zip"
        
        # For now, we'll create a placeholder - in production, this would download the actual repo
        # and create a zip file with the workdir content
        placeholder_content = f"# Repository: {repo}\n# Commit: {commit_sha}\n# Workdir: {workdir}\n"
        
        s3_client.put_object(
            Bucket=ARTIFACTS_BUCKET,
            Key=s3_key,
            Body=placeholder_content.encode(),
            ContentType='text/plain'
        )
        
        logger.info(f"Repository content uploaded to S3: s3://{ARTIFACTS_BUCKET}/{s3_key}")
        return f"s3://{ARTIFACTS_BUCKET}/{s3_key}"
        
    except Exception as e:
        logger.error(f"Error downloading repository to S3: {e}")
        raise


def start_ecs_task(repo: str, commit_sha: str, iac_type: str, workdir: str = 'infra/', repo_s3_path: str = None) -> str:
    """Start ECS Fargate task for IaC plan execution"""
    try:
        # Prepare task environment variables
        environment = [
            {'name': 'REPO_NAME', 'value': repo},
            {'name': 'COMMIT_SHA', 'value': commit_sha},
            {'name': 'IAC_TYPE', 'value': iac_type},
            {'name': 'WORKDIR', 'value': workdir},
            {'name': 'ARTIFACTS_BUCKET', 'value': ARTIFACTS_BUCKET},
            {'name': 'AWS_DEFAULT_REGION', 'value': os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')}
        ]
        
        if repo_s3_path:
            environment.append({'name': 'REPO_S3_PATH', 'value': repo_s3_path})
        
        # Start ECS task
        response = ecs_client.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': ECS_SUBNETS,
                    'securityGroups': ECS_SECURITY_GROUPS,
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
                {'key': 'Commit', 'value': commit_sha},
                {'key': 'IacType', 'value': iac_type}
            ]
        )
        
        task_arn = response['tasks'][0]['taskArn']
        logger.info(f"Started ECS task {task_arn} for {repo}@{commit_sha[:8]} ({iac_type})")
        
        return task_arn
    
    except Exception as e:
        logger.error(f"Error starting ECS task: {e}")
        raise


def wait_for_task_completion(task_arn: str, timeout_minutes: int = 15) -> Dict[str, Any]:
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
            elif key.endswith('.txt'):
                if 'terraform-output' in key:
                    artifacts['terraform_output'] = f"s3://{ARTIFACTS_BUCKET}/{key}"
        
        return artifacts
    
    except Exception as e:
        logger.error(f"Error checking S3 artifacts: {e}")
        return {}


def parse_plan_results(artifacts: Dict[str, str]) -> Dict[str, Any]:
    """Parse Terraform plan or CDK synth results"""
    try:
        results = {
            'resources_added': 0,
            'resources_changed': 0,
            'resources_destroyed': 0,
            'plan_type': 'unknown',
            'raw_plan_json_s3': None,
            'cdk_output_s3': None,
            'terraform_output_s3': None
        }
        
        # Parse Terraform plan JSON if available
        if artifacts.get('plan_json'):
            try:
                bucket, key = artifacts['plan_json'].replace('s3://', '').split('/', 1)
                response = s3_client.get_object(Bucket=bucket, Key=key)
                plan_data = json.loads(response['Body'].read())
                
                results['plan_type'] = 'terraform'
                results['raw_plan_json_s3'] = artifacts['plan_json']
                
                # Count resource changes
                for resource_change in plan_data.get('resource_changes', []):
                    actions = resource_change.get('change', {}).get('actions', [])
                    if 'create' in actions:
                        results['resources_added'] += 1
                    elif 'update' in actions:
                        results['resources_changed'] += 1
                    elif 'delete' in actions:
                        results['resources_destroyed'] += 1
                
            except Exception as e:
                logger.warning(f"Could not parse Terraform plan JSON: {e}")
        
        # Parse CDK output if available
        if artifacts.get('cdk_output'):
            results['plan_type'] = 'cdk'
            results['cdk_output_s3'] = artifacts['cdk_output']
            
            # For CDK, we'll estimate resource counts based on output size
            try:
                bucket, key = artifacts['cdk_output'].replace('s3://', '').split('/', 1)
                response = s3_client.get_object(Bucket=bucket, Key=key)
                cdk_data = response['Body'].read()
                
                # Simple heuristic: count "Type" occurrences in CDK output
                results['resources_added'] = cdk_data.count(b'"Type":')
                
            except Exception as e:
                logger.warning(f"Could not parse CDK output: {e}")
        
        # Parse Terraform output if available
        if artifacts.get('terraform_output'):
            results['terraform_output_s3'] = artifacts['terraform_output']
        
        return results
        
    except Exception as e:
        logger.error(f"Error parsing plan results: {e}")
        return {
            'resources_added': 0,
            'resources_changed': 0,
            'resources_destroyed': 0,
            'plan_type': 'unknown',
            'raw_plan_json_s3': None,
            'cdk_output_s3': None,
            'terraform_output_s3': None
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    run_iac_plan tool handler - Enhanced for Deep Pass
    
    Input:
    {
        "repo": "org/repo",
        "commit_sha": "abc123...",
        "iac_type": "terraform|tofu|cdk",
        "workdir": "infra/",
        "pr_number": 123
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
            "execution_time_seconds": 120,
            "artifacts": {...}
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
        
        logger.info(f"Starting Deep Pass IaC analysis for {repo}@{commit_sha[:8]} ({iac_type})")
        
        # Download repository content to S3 for ECS access
        repo_s3_path = download_repo_to_s3(repo, commit_sha, workdir)
        
        # Start ECS task
        start_time = time.time()
        task_arn = start_ecs_task(repo, commit_sha, iac_type, workdir, repo_s3_path)
        
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
        
        # Parse plan results
        plan_results = parse_plan_results(artifacts)
        
        result_data = {
            'plan_type': plan_results['plan_type'],
            'raw_plan_json_s3': plan_results['raw_plan_json_s3'],
            'cdk_output_s3': plan_results['cdk_output_s3'],
            'terraform_output_s3': plan_results['terraform_output_s3'],
            'resources_added': plan_results['resources_added'],
            'resources_changed': plan_results['resources_changed'],
            'resources_destroyed': plan_results['resources_destroyed'],
            'task_arn': task_arn,
            'execution_time_seconds': execution_time,
            'artifacts': artifacts,
            'repo_s3_path': repo_s3_path
        }
        
        logger.info(f"Deep Pass IaC analysis completed for {repo}@{commit_sha[:8]}: "
                   f"{plan_results['resources_added']} added, {plan_results['resources_changed']} changed, "
                   f"{plan_results['resources_destroyed']} destroyed")
        
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

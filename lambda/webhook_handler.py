"""
GitHub Webhook Handler for Archon
Handles PR events and routes to Bedrock AgentCore
"""

import json
import hmac
import hashlib
import os
import logging
from typing import Dict, Any, Optional
from urllib.parse import unquote

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

# Environment variables
GITHUB_WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET')
BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')
RUNS_TABLE_NAME = os.environ.get('RUNS_TABLE_NAME', 'archon_runs')

# DynamoDB table
runs_table = dynamodb.Table(RUNS_TABLE_NAME)


def verify_github_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature using HMAC-SHA256
    """
    if not signature or not secret:
        return False
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    # Create expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison
    return hmac.compare_digest(signature, expected_signature)


def get_pr_key(event_data: Dict[str, Any]) -> str:
    """Extract repository and PR number from GitHub event"""
    repo = event_data['repository']['full_name']
    pr_number = event_data['pull_request']['number']
    return f"{repo}#{pr_number}"


def get_commit_sha(event_data: Dict[str, Any]) -> str:
    """Extract commit SHA from GitHub event"""
    return event_data['pull_request']['head']['sha']


def should_process_event(event_data: Dict[str, Any]) -> bool:
    """
    Determine if we should process this PR event
    Only process: opened, synchronize, reopened, labeled events
    """
    action = event_data.get('action')
    
    # Process PR events
    if action in ['opened', 'synchronize', 'reopened']:
        return True
    
    # Process label events for deep-scan
    if action == 'labeled' and event_data.get('label', {}).get('name') == 'deep-scan':
        return True
    
    return False


def is_duplicate_run(repo: str, pr_number: int, commit_sha: str) -> bool:
    """
    Check if we've already processed this exact PR + commit combination
    """
    try:
        pr_key = f"{repo}#{pr_number}"
        response = runs_table.get_item(
            Key={
                'pr_key': pr_key,
                'commit_sha': commit_sha
            }
        )
        
        return 'Item' in response and response['Item'].get('status') in ['COMPLETED', 'IN_PROGRESS']
    
    except ClientError as e:
        logger.error(f"Error checking for duplicate run: {e}")
        return False


def store_run_record(repo: str, pr_number: int, commit_sha: str, run_type: str = 'FAST') -> None:
    """
    Store run record in DynamoDB to prevent duplicates
    """
    try:
        pr_key = f"{repo}#{pr_number}"
        runs_table.put_item(
            Item={
                'pr_key': pr_key,
                'commit_sha': commit_sha,
                'status': 'IN_PROGRESS',
                'run_type': run_type,
                'created_at': boto3.datetime.datetime.utcnow().isoformat(),
                'repo': repo,
                'pr_number': pr_number
            }
        )
    except ClientError as e:
        logger.error(f"Error storing run record: {e}")


def emit_metric(metric_name: str, value: float, unit: str = 'Count', dimensions: Optional[Dict[str, str]] = None):
    """Emit CloudWatch metric"""
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Namespace': 'Archon'
        }
        
        if dimensions:
            metric_data['Dimensions'] = [{'Name': k, 'Value': v} for k, v in dimensions.items()]
        
        cloudwatch.put_metric_data(
            Namespace='Archon',
            MetricData=[metric_data]
        )
    except ClientError as e:
        logger.error(f"Error emitting metric {metric_name}: {e}")


def invoke_bedrock_agent(repo: str, pr_number: int, commit_sha: str, run_type: str = 'FAST') -> Dict[str, Any]:
    """
    Invoke Bedrock AgentCore to analyze the PR
    """
    try:
        # Determine run type based on labels or thresholds
        if run_type == 'DEEP':
            instruction = f"Perform deep analysis on PR #{pr_number} in {repo} (commit: {commit_sha[:8]}). Use run_iac_plan for full infrastructure analysis."
        else:
            instruction = f"Perform fast analysis on PR #{pr_number} in {repo} (commit: {commit_sha[:8]}). Focus on security scanning and heuristic cost analysis."
        
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=f"{repo}#{pr_number}#{commit_sha}",
            inputText=instruction,
            enableTrace=True
        )
        
        # Process streaming response
        result = ""
        for event in response['completion']:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    result += chunk['bytes'].decode('utf-8')
        
        return {
            'status': 'success',
            'result': result,
            'session_id': f"{repo}#{pr_number}#{commit_sha}"
        }
    
    except ClientError as e:
        logger.error(f"Error invoking Bedrock agent: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for GitHub webhook events
    """
    try:
        # Parse the event
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        # Handle health check
        if path == '/health':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'status': 'healthy',
                    'service': 'Archon',
                    'version': '1.0.0'
                })
            }
        
        # Only process POST requests to webhook endpoint
        if http_method != 'POST' or path != '/webhook':
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        # Get request body and headers
        body = event.get('body', '')
        headers = event.get('headers', {})
        
        # Verify content type
        content_type = headers.get('content-type', '')
        if 'application/json' not in content_type:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Invalid content type'})
            }
        
        # Verify GitHub signature
        github_signature = headers.get('x-hub-signature-256', '')
        if not verify_github_signature(body, github_signature, GITHUB_WEBHOOK_SECRET):
            logger.warning("Invalid GitHub signature")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Parse event data
        event_data = json.loads(body)
        event_type = headers.get('x-github-event', '')
        
        # Only process pull_request events
        if event_type != 'pull_request':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'message': 'Event type not processed'})
            }
        
        # Check if we should process this event
        if not should_process_event(event_data):
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'message': 'Event action not processed'})
            }
        
        # Extract PR information
        repo = event_data['repository']['full_name']
        pr_number = event_data['pull_request']['number']
        commit_sha = event_data['pull_request']['head']['sha']
        action = event_data.get('action')
        
        # Check for deep-scan label
        labels = [label['name'] for label in event_data['pull_request'].get('labels', [])]
        run_type = 'DEEP' if 'deep-scan' in labels else 'FAST'
        
        # Check for duplicate runs
        if is_duplicate_run(repo, pr_number, commit_sha):
            logger.info(f"Skipping duplicate run for {repo}#{pr_number}@{commit_sha[:8]}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'message': 'Duplicate run skipped'})
            }
        
        # Store run record
        store_run_record(repo, pr_number, commit_sha, run_type)
        
        # Emit metrics
        emit_metric('webhook_events_received', 1, dimensions={'repo': repo})
        emit_metric('pr_analysis_started', 1, dimensions={'run_type': run_type})
        
        # Invoke Bedrock AgentCore
        start_time = context.aws_request_id  # Use request ID as timestamp proxy
        result = invoke_bedrock_agent(repo, pr_number, commit_sha, run_type)
        
        # Update run record with completion
        try:
            pr_key = f"{repo}#{pr_number}"
            runs_table.update_item(
                Key={
                    'pr_key': pr_key,
                    'commit_sha': commit_sha
                },
                UpdateExpression='SET #status = :status, #result = :result',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#result': 'result'
                },
                ExpressionAttributeValues={
                    ':status': 'COMPLETED' if result['status'] == 'success' else 'FAILED',
                    ':result': result
                }
            )
        except ClientError as e:
            logger.error(f"Error updating run record: {e}")
        
        # Emit completion metrics
        emit_metric('pr_analysis_completed', 1, dimensions={'run_type': run_type, 'status': result['status']})
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'PR analysis completed',
                'repo': repo,
                'pr_number': pr_number,
                'commit_sha': commit_sha,
                'run_type': run_type,
                'result': result['status']
            })
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        emit_metric('webhook_errors', 1)
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }

"""
GitHub Webhook Handler for Archon - Enhanced for Deep Pass
Handles PR events and routes to Bedrock AgentCore with deep-scan label trigger
"""

import json
import hmac
import hashlib
import os
import logging
import time
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
    
    # Compare signatures securely
    return hmac.compare_digest(signature, expected_signature)


def determine_analysis_type(pull_request: Dict[str, Any]) -> str:
    """
    Determine analysis type based on PR labels and content
    Enhanced for Deep Pass with deep-scan label trigger
    """
    try:
        labels = [label['name'] for label in pull_request.get('labels', [])]
        
        # Check for deep-scan label
        if 'deep-scan' in labels:
            logger.info("Deep-scan label detected - triggering full analysis")
            return 'DEEP'
        
        # Check for fast-pass label
        if 'fast-pass' in labels:
            logger.info("Fast-pass label detected - triggering quick analysis")
            return 'FAST'
        
        # Auto-detect based on file changes
        changed_files = pull_request.get('changed_files', 0)
        additions = pull_request.get('additions', 0)
        deletions = pull_request.get('deletions', 0)
        
        # Large changes trigger deep scan
        if changed_files > 10 or additions > 500 or deletions > 500:
            logger.info(f"Large changes detected ({changed_files} files, {additions}+{deletions} lines) - triggering deep scan")
            return 'DEEP'
        
        # Check for infrastructure-related files
        pr_title = pull_request.get('title', '').lower()
        pr_body = pull_request.get('body', '').lower()
        
        infra_keywords = ['terraform', 'cdk', 'cloudformation', 'infrastructure', 'iac', 'aws', 'deploy']
        if any(keyword in pr_title or keyword in pr_body for keyword in infra_keywords):
            logger.info("Infrastructure changes detected - triggering deep scan")
            return 'DEEP'
        
        # Default to fast pass for smaller changes
        logger.info("Small changes detected - triggering fast pass")
        return 'FAST'
    
    except Exception as e:
        logger.error(f"Error determining analysis type: {e}")
        return 'FAST'  # Default to fast pass on error


def create_run_record(repo: str, pr_number: int, commit_sha: str, analysis_type: str) -> str:
    """
    Create a run record in DynamoDB
    Enhanced for Deep Pass with additional metadata
    """
    try:
        run_id = f"{repo.replace('/', '-')}-{pr_number}-{commit_sha[:8]}"
        
        run_record = {
            'run_id': run_id,
            'repo': repo,
            'pr_number': pr_number,
            'commit_sha': commit_sha,
            'analysis_type': analysis_type,
            'status': 'started',
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'metadata': {
                'phase': 'deep_pass' if analysis_type == 'DEEP' else 'fast_pass',
                'tools_used': [],
                'artifacts': {},
                'cost_analysis': {},
                'security_findings': {},
                'waf_guidance': {}
            }
        }
        
        runs_table.put_item(Item=run_record)
        logger.info(f"Created run record: {run_id} ({analysis_type})")
        
        return run_id
    
    except Exception as e:
        logger.error(f"Error creating run record: {e}")
        raise


def invoke_bedrock_agent(repo: str, pr_number: int, commit_sha: str, analysis_type: str, run_id: str) -> Dict[str, Any]:
    """
    Invoke Bedrock AgentCore with enhanced context for Deep Pass
    """
    try:
        # Prepare enhanced context for Deep Pass
        context = {
            'repo': repo,
            'pr_number': pr_number,
            'commit_sha': commit_sha,
            'analysis_type': analysis_type,
            'run_id': run_id,
            'phase': 'deep_pass' if analysis_type == 'DEEP' else 'fast_pass',
            'tools': {
                'fetch_pr_context': True,
                'security_static_scan': True,
                'finops_pricing_delta': True,
                'post_pr_comment': True,
                'run_iac_plan': analysis_type == 'DEEP',  # Only for deep scans
                'kb_lookup': analysis_type == 'DEEP'  # Only for deep scans
            }
        }
        
        # Create session for this run
        session_id = f"archon-{run_id}"
        
        # Invoke Bedrock Agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=f"Analyze PR {pr_number} in {repo} with {analysis_type} analysis. Context: {json.dumps(context)}"
        )
        
        # Process response
        result = ""
        for event in response['completion']:
            if 'chunk' in event:
                result += event['chunk']['bytes'].decode('utf-8')
        
        logger.info(f"Bedrock Agent invoked for {run_id}: {len(result)} characters")
        
        return {
            'status': 'success',
            'result': result,
            'session_id': session_id
        }
    
    except Exception as e:
        logger.error(f"Error invoking Bedrock Agent: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


def update_run_status(run_id: str, status: str, metadata: Dict[str, Any] = None):
    """
    Update run status in DynamoDB
    """
    try:
        update_expression = "SET #status = :status, updated_at = :updated_at"
        expression_attribute_names = {'#status': 'status'}
        expression_attribute_values = {
            ':status': status,
            ':updated_at': int(time.time())
        }
        
        if metadata:
            update_expression += ", metadata = :metadata"
            expression_attribute_values[':metadata'] = metadata
        
        runs_table.update_item(
            Key={'run_id': run_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        logger.info(f"Updated run status: {run_id} -> {status}")
    
    except Exception as e:
        logger.error(f"Error updating run status: {e}")


def send_cloudwatch_metrics(repo: str, analysis_type: str, duration_ms: int, success: bool):
    """
    Send CloudWatch metrics for monitoring
    Enhanced for Deep Pass with additional metrics
    """
    try:
        metrics = [
            {
                'MetricName': 'scan_duration_ms',
                'Value': duration_ms,
                'Unit': 'Milliseconds',
                'Dimensions': [
                    {'Name': 'AnalysisType', 'Value': analysis_type},
                    {'Name': 'Repo', 'Value': repo.replace('/', '-')}
                ]
            },
            {
                'MetricName': 'scan_count',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'AnalysisType', 'Value': analysis_type},
                    {'Name': 'Status', 'Value': 'success' if success else 'error'}
                ]
            }
        ]
        
        cloudwatch.put_metric_data(
            Namespace='Archon/DeepPass',
            MetricData=metrics
        )
        
        logger.info(f"Sent CloudWatch metrics for {analysis_type} scan")
    
    except Exception as e:
        logger.error(f"Error sending CloudWatch metrics: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enhanced webhook handler for Deep Pass
    
    Handles GitHub PR events and routes to appropriate analysis type:
    - FAST: Quick analysis with basic tools
    - DEEP: Full analysis with ECS Fargate and Knowledge Base
    """
    try:
        # Extract request details
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Verify GitHub signature
        signature = headers.get('X-Hub-Signature-256', '')
        if not verify_github_signature(body, signature, GITHUB_WEBHOOK_SECRET):
            logger.warning("Invalid GitHub signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Parse webhook payload
        payload = json.loads(body)
        action = payload.get('action')
        
        # Only process relevant PR events
        if action not in ['opened', 'synchronize', 'reopened', 'labeled']:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event action not processed'})
            }
        
        # Extract PR information
        pull_request = payload.get('pull_request', {})
        if not pull_request:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No pull request data'})
            }
        
        repo = payload['repository']['full_name']
        pr_number = pull_request['number']
        commit_sha = pull_request['head']['sha']
        
        # Determine analysis type (enhanced for Deep Pass)
        analysis_type = determine_analysis_type(pull_request)
        
        logger.info(f"Processing {analysis_type} analysis for {repo}#{pr_number}@{commit_sha[:8]}")
        
        # Create run record
        run_id = create_run_record(repo, pr_number, commit_sha, analysis_type)
        
        # Invoke Bedrock Agent with enhanced context
        agent_result = invoke_bedrock_agent(repo, pr_number, commit_sha, analysis_type, run_id)
        
        if agent_result['status'] == 'success':
            # Update run status
            update_run_status(run_id, 'completed', {
                'phase': 'deep_pass' if analysis_type == 'DEEP' else 'fast_pass',
                'analysis_type': analysis_type,
                'result': agent_result['result']
            })
            
            # Send metrics
            duration_ms = (context.get_remaining_time_in_millis() or 0)
            send_cloudwatch_metrics(repo, analysis_type, duration_ms, True)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'{analysis_type} analysis completed',
                    'repo': repo,
                    'pr_number': pr_number,
                    'commit_sha': commit_sha,
                    'run_id': run_id,
                    'analysis_type': analysis_type
                })
            }
        else:
            # Update run status
            update_run_status(run_id, 'failed', {
                'error': agent_result['error']
            })
            
            # Send metrics
            duration_ms = (context.get_remaining_time_in_millis() or 0)
            send_cloudwatch_metrics(repo, analysis_type, duration_ms, False)
            
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Analysis failed',
                    'run_id': run_id,
                    'details': agent_result['error']
                })
            }
    
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


# Health check endpoint
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for the webhook handler
    """
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'healthy',
            'service': 'Archon Deep Pass Webhook Handler',
            'version': '2.0.0',
            'phase': 'deep_pass'
        })
    }

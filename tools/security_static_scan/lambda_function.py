"""
security_static_scan Tool
Runs static security analysis using Checkov/tfsec and emits SARIF to S3
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Dict, Any, List
from pathlib import Path

import boto3
from github import Github

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
secrets_manager = boto3.client('secretsmanager')

# Environment variables
ARTIFACTS_BUCKET = os.environ.get('ARTIFACTS_BUCKET', 'archon-artifacts')
GITHUB_TOKEN_SECRET_NAME = os.environ.get('GITHUB_TOKEN_SECRET_NAME', 'archon/github/token')
GITHUB_TOKEN_SECRET_KEY = os.environ.get('GITHUB_TOKEN_SECRET_KEY', 'token')


def get_github_token() -> str:
    """Retrieve GitHub token from AWS Secrets Manager"""
    try:
        response = secrets_manager.get_secret_value(SecretId=GITHUB_TOKEN_SECRET_NAME)
        secret_data = json.loads(response['SecretString'])
        return secret_data[GITHUB_TOKEN_SECRET_KEY]
    except Exception as e:
        logger.error(f"Error retrieving GitHub token: {e}")
        raise


def download_repo_files(github: Github, repo_name: str, commit_sha: str, workdir: str = 'infra/') -> List[str]:
    """Download changed IaC files from GitHub repository"""
    try:
        repo = github.get_repo(repo_name)
        
        # Get repository contents
        contents = repo.get_contents(workdir, ref=commit_sha)
        
        downloaded_files = []
        temp_dir = tempfile.mkdtemp()
        
        for content in contents:
            if content.type == 'file' and content.name.endswith(('.tf', '.tfvars', '.yaml', '.yml', '.json')):
                # Download file content
                file_content = content.decoded_content.decode('utf-8')
                file_path = os.path.join(temp_dir, content.name)
                
                # Create directory structure
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Write file
                with open(file_path, 'w') as f:
                    f.write(file_content)
                
                downloaded_files.append(file_path)
        
        return downloaded_files
    
    except Exception as e:
        logger.error(f"Error downloading repo files: {e}")
        return []


def run_checkov(files: List[str]) -> Dict[str, Any]:
    """Run Checkov static analysis"""
    try:
        if not files:
            return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}}
        
        # Create temporary directory for Checkov output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        # Run Checkov
        cmd = [
            'checkov',
            '-f', ','.join(files),
            '--output', 'json',
            '--output-file-path', output_file,
            '--framework', 'terraform',
            '--quiet'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Parse results
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                checkov_results = json.load(f)
        else:
            checkov_results = {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}}
        
        # Clean up
        os.unlink(output_file)
        
        return checkov_results
    
    except subprocess.TimeoutExpired:
        logger.error("Checkov scan timed out")
        return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}, 'error': 'timeout'}
    except Exception as e:
        logger.error(f"Error running Checkov: {e}")
        return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}, 'error': str(e)}


def run_tfsec(files: List[str]) -> Dict[str, Any]:
    """Run tfsec static analysis"""
    try:
        if not files:
            return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}}
        
        # Create temporary directory for tfsec output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        # Run tfsec
        cmd = [
            'tfsec',
            '--format', 'json',
            '--out', output_file,
            '--no-color'
        ] + files
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Parse results
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                tfsec_results = json.load(f)
        else:
            tfsec_results = {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}}
        
        # Clean up
        os.unlink(output_file)
        
        return tfsec_results
    
    except subprocess.TimeoutExpired:
        logger.error("tfsec scan timed out")
        return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}, 'error': 'timeout'}
    except Exception as e:
        logger.error(f"Error running tfsec: {e}")
        return {'results': [], 'summary': {'failed': 0, 'passed': 0, 'skipped': 0}, 'error': str(e)}


def convert_to_sarif(checkov_results: Dict[str, Any], tfsec_results: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Checkov and tfsec results to SARIF format"""
    
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Checkov",
                        "version": "3.0.0",
                        "informationUri": "https://www.checkov.io/"
                    }
                },
                "results": []
            },
            {
                "tool": {
                    "driver": {
                        "name": "tfsec",
                        "version": "1.0.0",
                        "informationUri": "https://tfsec.dev/"
                    }
                },
                "results": []
            }
        ]
    }
    
    # Convert Checkov results
    for result in checkov_results.get('results', []):
        for check in result.get('check_results', []):
            if check.get('result') == 'FAILED':
                sarif['runs'][0]['results'].append({
                    "ruleId": check.get('check_id', ''),
                    "message": {
                        "text": check.get('evaluated_iam_statement', '') or check.get('resource', '')
                    },
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": result.get('file_path', '')
                                },
                                "region": {
                                    "startLine": check.get('file_line_range', [0])[0]
                                }
                            }
                        }
                    ],
                    "level": "error" if check.get('severity') == 'HIGH' else "warning"
                })
    
    # Convert tfsec results
    for result in tfsec_results.get('results', []):
        if result.get('status') == 'FAILED':
            sarif['runs'][1]['results'].append({
                "ruleId": result.get('rule_id', ''),
                "message": {
                    "text": result.get('description', '')
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": result.get('location', {}).get('filename', '')
                            },
                            "region": {
                                "startLine": result.get('location', {}).get('start_line', 1)
                            }
                        }
                    }
                ],
                "level": "error" if result.get('severity') == 'HIGH' else "warning"
            })
    
    return sarif


def upload_sarif_to_s3(sarif_data: Dict[str, Any], repo: str, pr_number: int, commit_sha: str) -> str:
    """Upload SARIF results to S3"""
    try:
        s3_key = f"{repo}/{pr_number}/{commit_sha}/sarif.json"
        
        s3_client.put_object(
            Bucket=ARTIFACTS_BUCKET,
            Key=s3_key,
            Body=json.dumps(sarif_data, indent=2),
            ContentType='application/json'
        )
        
        return f"s3://{ARTIFACTS_BUCKET}/{s3_key}"
    
    except Exception as e:
        logger.error(f"Error uploading SARIF to S3: {e}")
        raise


def count_findings_by_severity(sarif_data: Dict[str, Any]) -> Dict[str, int]:
    """Count findings by severity level"""
    counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    
    for run in sarif_data.get('runs', []):
        for result in run.get('results', []):
            level = result.get('level', 'warning')
            if level == 'error':
                counts['HIGH'] += 1
            elif level == 'warning':
                counts['MEDIUM'] += 1
            else:
                counts['LOW'] += 1
    
    return counts


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    security_static_scan tool handler
    
    Input:
    {
        "repo": "org/repo",
        "commit_sha": "abc123...",
        "workdir": "infra/"
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "sarif_s3": "s3://bucket/path/sarif.json",
            "counts": {
                "HIGH": 1,
                "MEDIUM": 1,
                "LOW": 1
            },
            "summary": {
                "total_files_scanned": 5,
                "checkov_results": {...},
                "tfsec_results": {...}
            }
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        required_fields = ['repo', 'commit_sha']
        for field in required_fields:
            if field not in event:
                return {
                    'status': 'error',
                    'error': f'Missing required parameter: {field}'
                }
        
        repo = event['repo']
        commit_sha = event['commit_sha']
        workdir = event.get('workdir', 'infra/')
        
        # Get GitHub token and initialize client
        github_token = get_github_token()
        github = Github(github_token)
        
        # Extract PR number from repo if available
        pr_number = event.get('pr_number', 0)
        
        # Download repository files
        logger.info(f"Downloading files from {repo}@{commit_sha[:8]} in {workdir}")
        files = download_repo_files(github, repo, commit_sha, workdir)
        
        if not files:
            logger.warning(f"No IaC files found in {workdir}")
            return {
                'status': 'success',
                'data': {
                    'sarif_s3': None,
                    'counts': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
                    'summary': {
                        'total_files_scanned': 0,
                        'checkov_results': {},
                        'tfsec_results': {}
                    }
                }
            }
        
        # Run static analysis tools
        logger.info(f"Running Checkov on {len(files)} files")
        checkov_results = run_checkov(files)
        
        logger.info(f"Running tfsec on {len(files)} files")
        tfsec_results = run_tfsec(files)
        
        # Convert to SARIF format
        sarif_data = convert_to_sarif(checkov_results, tfsec_results)
        
        # Upload SARIF to S3
        sarif_s3_path = upload_sarif_to_s3(sarif_data, repo, pr_number, commit_sha)
        
        # Count findings by severity
        counts = count_findings_by_severity(sarif_data)
        
        result = {
            'sarif_s3': sarif_s3_path,
            'counts': counts,
            'summary': {
                'total_files_scanned': len(files),
                'checkov_results': checkov_results,
                'tfsec_results': tfsec_results
            }
        }
        
        logger.info(f"Security scan completed: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW findings")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in security_static_scan: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

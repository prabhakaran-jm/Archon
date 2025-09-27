"""
fetch_pr_context Tool
Retrieves PR metadata, changed files, and labels from GitHub API
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

import boto3
from github import Github
from github.GithubException import GithubException

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
secrets_manager = boto3.client('secretsmanager')

# Environment variables
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


def get_changed_files(github: Github, repo_name: str, pr_number: int) -> List[str]:
    """Get list of changed files in the PR"""
    try:
        repo = github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        changed_files = []
        for file in pr.get_files():
            if file.filename.endswith(('.tf', '.tfvars', '.ts', '.js', '.py', '.yaml', '.yml', '.json')):
                changed_files.append(file.filename)
        
        return changed_files
    except GithubException as e:
        logger.error(f"Error fetching changed files: {e}")
        return []


def get_pr_labels(github: Github, repo_name: str, pr_number: int) -> List[str]:
    """Get PR labels"""
    try:
        repo = github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        return [label.name for label in pr.get_labels()]
    except GithubException as e:
        logger.error(f"Error fetching PR labels: {e}")
        return []


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    fetch_pr_context tool handler
    
    Input:
    {
        "repo": "org/repo",
        "pr_number": 123
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "commit_sha": "abc123...",
            "changed_files": ["infra/s3.tf", "infra/main.tf"],
            "url": "https://github.com/org/repo/pull/123",
            "labels": ["deep-scan"],
            "title": "Add S3 bucket configuration",
            "author": "username",
            "created_at": "2025-01-27T10:36:00Z",
            "updated_at": "2025-01-27T10:36:00Z"
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        if 'repo' not in event or 'pr_number' not in event:
            return {
                'status': 'error',
                'error': 'Missing required parameters: repo, pr_number'
            }
        
        repo_name = event['repo']
        pr_number = event['pr_number']
        
        # Get GitHub token and initialize client
        github_token = get_github_token()
        github = Github(github_token)
        
        # Get repository and PR
        repo = github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # Extract PR information
        result = {
            'commit_sha': pr.head.sha,
            'changed_files': get_changed_files(github, repo_name, pr_number),
            'url': pr.html_url,
            'labels': get_pr_labels(github, repo_name, pr_number),
            'title': pr.title,
            'author': pr.user.login,
            'created_at': pr.created_at.isoformat(),
            'updated_at': pr.updated_at.isoformat(),
            'base_branch': pr.base.ref,
            'head_branch': pr.head.ref,
            'state': pr.state,
            'mergeable': pr.mergeable,
            'additions': pr.additions,
            'deletions': pr.deletions,
            'changed_files_count': pr.changed_files
        }
        
        logger.info(f"Fetched PR context for {repo_name}#{pr_number}: {len(result['changed_files'])} files changed")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in fetch_pr_context: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

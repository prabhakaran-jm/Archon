"""
create_remediation_pr Tool
Creates auto-fix PR with minimal diffs for common issues
"""

import json
import logging
import os
from typing import Dict, Any, List

import boto3
from github import Github, InputGitTreeElement
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


def create_branch(github: Github, repo_name: str, base_branch: str, new_branch: str) -> None:
    """Create a new branch from base branch"""
    try:
        repo = github.get_repo(repo_name)
        
        # Get base branch reference
        base_ref = repo.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha
        
        # Create new branch
        repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=base_sha)
        logger.info(f"Created branch {new_branch} from {base_branch}")
    
    except GithubException as e:
        if e.status == 422:  # Branch already exists
            logger.info(f"Branch {new_branch} already exists")
        else:
            raise


def apply_patches(github: Github, repo_name: str, branch: str, patches: List[Dict[str, Any]]) -> List[str]:
    """Apply patches to files in the repository"""
    try:
        repo = github.get_repo(repo_name)
        
        # Get current commit
        ref = repo.get_git_ref(f"heads/{branch}")
        commit = repo.get_git_commit(ref.object.sha)
        tree = repo.get_git_tree(commit.tree.sha, recursive=True)
        
        # Prepare tree elements for updates
        tree_elements = []
        modified_files = []
        
        for patch in patches:
            file_path = patch['file']
            diff = patch['diff']
            
            # Parse diff to get new content (simplified)
            # In a real implementation, you'd properly parse the unified diff
            new_content = apply_unified_diff(diff)
            
            # Add to tree elements
            blob = repo.create_git_blob(new_content, 'utf-8')
            tree_elements.append(InputGitTreeElement(
                path=file_path,
                mode='100644',
                type='blob',
                sha=blob.sha
            ))
            
            modified_files.append(file_path)
        
        # Create new tree
        new_tree = repo.create_git_tree(tree_elements, base_tree=tree)
        
        # Create new commit
        new_commit = repo.create_git_commit(
            message="🤖 Archon auto-remediation: Apply security and reliability fixes",
            tree=new_tree,
            parents=[commit]
        )
        
        # Update branch reference
        ref.edit(sha=new_commit.sha)
        
        logger.info(f"Applied {len(patches)} patches to branch {branch}")
        return modified_files
    
    except GithubException as e:
        logger.error(f"Error applying patches: {e}")
        raise


def apply_unified_diff(diff: str) -> str:
    """Apply unified diff to get new file content (simplified)"""
    # This is a simplified implementation
    # In production, you'd use a proper diff parser
    lines = diff.split('\n')
    new_lines = []
    
    for line in lines:
        if line.startswith('+') and not line.startswith('+++'):
            new_lines.append(line[1:])
        elif not line.startswith('-') and not line.startswith('@@') and not line.startswith('---') and not line.startswith('+++'):
            if line.startswith(' '):
                new_lines.append(line[1:])
    
    return '\n'.join(new_lines)


def create_pull_request(github: Github, repo_name: str, base_branch: str, head_branch: str, 
                       title: str, body: str, base_pr_number: int = None) -> int:
    """Create pull request"""
    try:
        repo = github.get_repo(repo_name)
        
        # Create PR
        pr = repo.create_pull(
            title=title,
            body=body,
            base=base_branch,
            head=head_branch
        )
        
        # Add label if base PR number is provided
        if base_pr_number:
            try:
                pr.add_to_labels('archon-autofix')
                pr.add_to_labels(f'fixes-pr-{base_pr_number}')
            except GithubException:
                pass  # Labels might not exist
        
        logger.info(f"Created PR #{pr.number}: {title}")
        return pr.number
    
    except GithubException as e:
        logger.error(f"Error creating pull request: {e}")
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    create_remediation_pr tool handler
    
    Input:
    {
        "repo": "org/repo",
        "base_pr_number": 123,
        "patches": [
            {
                "file": "infra/s3.tf",
                "diff": "@@ -1,3 +1,6 @@\n resource \"aws_s3_bucket\" \"example\" {\n   bucket = \"my-bucket\"\n+  \n+  server_side_encryption_configuration {\n+    rule {\n+      apply_server_side_encryption_by_default {\n+        sse_algorithm = \"AES256\"\n+      }\n+    }\n+  }\n }"
            }
        ],
        "title": "Archon auto-remediation",
        "body": "Automated fixes for security and reliability issues..."
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "new_pr_number": 124,
            "url": "https://github.com/org/repo/pull/124",
            "modified_files": ["infra/s3.tf"]
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        required_fields = ['repo', 'patches']
        for field in required_fields:
            if field not in event:
                return {
                    'status': 'error',
                    'error': f'Missing required parameter: {field}'
                }
        
        repo = event['repo']
        base_pr_number = event.get('base_pr_number')
        patches = event['patches']
        title = event.get('title', '🤖 Archon auto-remediation')
        body = event.get('body', 'Automated fixes for security and reliability issues detected by Archon.')
        
        if not patches:
            return {
                'status': 'error',
                'error': 'No patches provided'
            }
        
        # Get GitHub token and initialize client
        github_token = get_github_token()
        github = Github(github_token)
        
        # Get base PR info if provided
        base_branch = 'main'  # Default
        if base_pr_number:
            try:
                repo_obj = github.get_repo(repo)
                base_pr = repo_obj.get_pull(base_pr_number)
                base_branch = base_pr.base.ref
            except GithubException as e:
                logger.warning(f"Could not get base PR info: {e}")
        
        # Generate branch name
        import time
        timestamp = int(time.time())
        head_branch = f"archon-autofix-{timestamp}"
        
        # Create branch
        create_branch(github, repo, base_branch, head_branch)
        
        # Apply patches
        modified_files = apply_patches(github, repo, head_branch, patches)
        
        # Enhance PR body with evidence
        if base_pr_number:
            body += f"\n\n**Related to**: #{base_pr_number}\n"
            body += f"**Auto-generated by**: Archon\n"
            body += f"**Modified files**: {', '.join(modified_files)}\n"
            body += "\nThis PR contains automated fixes for security and reliability issues detected in the original PR."
        
        # Create pull request
        new_pr_number = create_pull_request(
            github, repo, base_branch, head_branch, title, body, base_pr_number
        )
        
        pr_url = f"https://github.com/{repo}/pull/{new_pr_number}"
        
        result = {
            'new_pr_number': new_pr_number,
            'url': pr_url,
            'modified_files': modified_files,
            'branch': head_branch
        }
        
        logger.info(f"Created auto-fix PR #{new_pr_number} for {repo}: {pr_url}")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in create_remediation_pr: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

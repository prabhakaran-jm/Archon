"""
post_pr_comment Tool
Posts unified analysis comment to GitHub PR with 💰🛡️⚙️ sections
"""

import json
import logging
import os
from typing import Dict, Any, Optional

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
        # For local testing, use environment variable or mock
        if os.environ.get('LOCAL_TESTING'):
            return os.environ.get('GITHUB_TOKEN', 'mock-github-token')
        
        response = secrets_manager.get_secret_value(SecretId=GITHUB_TOKEN_SECRET_NAME)
        secret_data = json.loads(response['SecretString'])
        return secret_data[GITHUB_TOKEN_SECRET_KEY]
    except Exception as e:
        logger.error(f"Error retrieving GitHub token: {e}")
        # Fallback for testing
        return os.environ.get('GITHUB_TOKEN', 'mock-github-token')


def format_cost_section(cost_data: Dict[str, Any]) -> str:
    """Format the cost impact section"""
    if not cost_data or cost_data.get('monthly_delta_usd', 0) == 0:
        return "💰 **Cost Impact**: No significant cost changes detected."
    
    delta = cost_data['monthly_delta_usd']
    confidence = cost_data['confidence_pct']
    
    if delta > 0:
        cost_emoji = "📈"
        cost_text = f"increase of ${delta:.2f}/month"
    else:
        cost_emoji = "📉"
        cost_text = f"decrease of ${abs(delta):.2f}/month"
    
    section = f"💰 **Cost Impact**: {cost_emoji} Estimated {cost_text} "
    section += f"(±{100-confidence}% confidence)\n\n"
    
    # Add top cost drivers
    if cost_data.get('top_drivers'):
        section += "**Top Cost Drivers:**\n"
        for driver in cost_data['top_drivers'][:3]:
            section += f"- {driver['service']}: ${driver['delta']:.2f}/month\n"
    
    # Add assumptions
    assumptions = cost_data.get('assumptions_used', {})
    if assumptions:
        section += f"\n**Assumptions:**\n"
        section += f"- NAT Gateway: {assumptions.get('nat_hours_per_month', 720)} hours/month\n"
        section += f"- S3 Storage: {assumptions.get('s3_storage_gb_per_bucket', 10)} GB per bucket\n"
        section += f"- Region: {assumptions.get('region', 'eu-west-1')}\n"
    
    return section


def format_security_section(security_data: Dict[str, Any]) -> str:
    """Format the security findings section"""
    if not security_data or not security_data.get('counts'):
        return "🛡️ **Security**: No security issues detected."
    
    counts = security_data['counts']
    total_issues = sum(counts.values())
    
    if total_issues == 0:
        return "🛡️ **Security**: ✅ No security issues detected."
    
    section = f"🛡️ **Security**: Found {total_issues} security issue(s)\n\n"
    
    # Add severity breakdown
    if counts.get('HIGH', 0) > 0:
        section += f"🚨 **HIGH**: {counts['HIGH']} critical issue(s)\n"
    if counts.get('MEDIUM', 0) > 0:
        section += f"⚠️ **MEDIUM**: {counts['MEDIUM']} issue(s)\n"
    if counts.get('LOW', 0) > 0:
        section += f"ℹ️ **LOW**: {counts['LOW']} issue(s)\n"
    
    # Add SARIF link if available
    if security_data.get('sarif_s3'):
        section += f"\n📋 [View detailed security report]({security_data['sarif_s3']})\n"
    
    return section


def format_reliability_section(reliability_data: Dict[str, Any]) -> str:
    """Format the reliability section"""
    if not reliability_data:
        return "⚙️ **Reliability**: No reliability issues detected."
    
    section = "⚙️ **Reliability**: Well-Architected Framework Compliance\n\n"
    
    # Add reliability recommendations
    recommendations = reliability_data.get('recommendations', [])
    if recommendations:
        section += "**Recommendations:**\n"
        for rec in recommendations[:5]:  # Top 5 recommendations
            section += f"- {rec}\n"
    else:
        section += "✅ No reliability issues detected.\n"
    
    return section


def format_suggested_fixes(fixes_data: Dict[str, Any]) -> str:
    """Format the suggested fixes section"""
    if not fixes_data or not fixes_data.get('fixes'):
        return ""
    
    section = "🔧 **Suggested Fixes**:\n\n"
    
    fixes = fixes_data['fixes']
    for i, fix in enumerate(fixes[:3], 1):  # Top 3 fixes
        section += f"{i}. **{fix.get('title', 'Fix')}**\n"
        section += f"   {fix.get('description', '')}\n"
        
        if fix.get('code_snippet'):
            section += f"   ```hcl\n{fix['code_snippet']}\n   ```\n\n"
    
    # Add auto-fix PR if available
    if fixes_data.get('auto_fix_available'):
        section += "🤖 **Auto-Fix Available**: This issue can be automatically resolved. "
        section += "Comment with `/archon fix` to create a remediation PR.\n"
    
    return section


def generate_comment_markdown(analysis_data: Dict[str, Any]) -> str:
    """Generate unified PR comment markdown"""
    
    # Header
    markdown = "## 🤖 Archon Analysis Report\n\n"
    
    # Summary
    summary = analysis_data.get('summary', 'Analysis completed successfully.')
    markdown += f"**Summary**: {summary}\n\n"
    
    # Cost Impact
    cost_data = analysis_data.get('cost_analysis', {})
    markdown += format_cost_section(cost_data) + "\n\n"
    
    # Security
    security_data = analysis_data.get('security_analysis', {})
    markdown += format_security_section(security_data) + "\n\n"
    
    # Reliability
    reliability_data = analysis_data.get('reliability_analysis', {})
    markdown += format_reliability_section(reliability_data) + "\n\n"
    
    # Suggested Fixes
    fixes_data = analysis_data.get('suggested_fixes', {})
    fixes_section = format_suggested_fixes(fixes_data)
    if fixes_section:
        markdown += fixes_section + "\n"
    
    # Footer
    markdown += "---\n"
    markdown += "*Generated by Archon - Autonomous Principal Architect for CI/CD*\n"
    
    return markdown


def find_existing_comment(github: Github, repo_name: str, pr_number: int) -> Optional[int]:
    """Find existing Archon comment to update"""
    try:
        repo = github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        for comment in pr.get_issue_comments():
            if "🤖 Archon Analysis Report" in comment.body:
                return comment.id
        
        return None
    
    except GithubException as e:
        logger.error(f"Error finding existing comment: {e}")
        return None


def post_comment(github: Github, repo_name: str, pr_number: int, body: str, update_existing: bool = True) -> int:
    """Post comment to GitHub PR"""
    try:
        repo = github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # Try to update existing comment if requested
        if update_existing:
            existing_comment_id = find_existing_comment(github, repo_name, pr_number)
            if existing_comment_id:
                comment = repo.get_issue_comment(existing_comment_id)
                comment.edit(body)
                logger.info(f"Updated existing comment {existing_comment_id}")
                return existing_comment_id
        
        # Create new comment
        comment = pr.create_issue_comment(body)
        logger.info(f"Created new comment {comment.id}")
        return comment.id
    
    except GithubException as e:
        logger.error(f"Error posting comment: {e}")
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    post_pr_comment tool handler
    
    Input:
    {
        "repo": "org/repo",
        "pr_number": 123,
        "body_markdown": "## Analysis Report...",
        "update_existing": true
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "comment_id": 456,
            "comment_url": "https://github.com/org/repo/pull/123#issuecomment-456",
            "updated_existing": true
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        required_fields = ['repo', 'pr_number']
        for field in required_fields:
            if field not in event:
                return {
                    'status': 'error',
                    'error': f'Missing required parameter: {field}'
                }
        
        repo = event['repo']
        pr_number = event['pr_number']
        body_markdown = event.get('body_markdown', '')
        update_existing = event.get('update_existing', True)
        
        # If no markdown provided, generate from analysis data
        if not body_markdown:
            analysis_data = event.get('analysis_data', {})
            body_markdown = generate_comment_markdown(analysis_data)
        
        # Get GitHub token and initialize client
        github_token = get_github_token()
        github = Github(github_token)
        
        # Post comment
        comment_id = post_comment(github, repo, pr_number, body_markdown, update_existing)
        
        # Generate comment URL
        comment_url = f"https://github.com/{repo}/pull/{pr_number}#issuecomment-{comment_id}"
        
        result = {
            'comment_id': comment_id,
            'comment_url': comment_url,
            'updated_existing': update_existing and find_existing_comment(github, repo, pr_number) is not None
        }
        
        logger.info(f"Posted comment to {repo}#{pr_number}: {comment_url}")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in post_pr_comment: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

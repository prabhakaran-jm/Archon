#!/usr/bin/env python3
"""
Script to seed demo repositories with sample PRs for Archon testing
"""

import json
import requests
import os
from typing import Dict, Any


def create_sample_pr_webhook_payload() -> Dict[str, Any]:
    """Create a sample GitHub webhook payload for testing"""
    return {
        "action": "opened",
        "number": 123,
        "pull_request": {
            "id": 123456789,
            "number": 123,
            "state": "open",
            "title": "Add S3 bucket configuration with security improvements",
            "user": {
                "login": "testuser",
                "id": 12345
            },
            "head": {
                "sha": "abc123def456789",
                "ref": "feature/s3-security",
                "repo": {
                    "full_name": "demo-org/sample-terraform",
                    "name": "sample-terraform",
                    "owner": {
                        "login": "demo-org"
                    }
                }
            },
            "base": {
                "sha": "def456ghi789012",
                "ref": "main",
                "repo": {
                    "full_name": "demo-org/sample-terraform",
                    "name": "sample-terraform",
                    "owner": {
                        "login": "demo-org"
                    }
                }
            },
            "html_url": "https://github.com/demo-org/sample-terraform/pull/123",
            "created_at": "2025-01-27T10:36:00Z",
            "updated_at": "2025-01-27T10:36:00Z",
            "additions": 45,
            "deletions": 12,
            "changed_files": 2,
            "labels": []
        },
        "repository": {
            "id": 987654321,
            "name": "sample-terraform",
            "full_name": "demo-org/sample-terraform",
            "owner": {
                "login": "demo-org",
                "id": 54321
            },
            "html_url": "https://github.com/demo-org/sample-terraform"
        }
    }


def create_deep_scan_webhook_payload() -> Dict[str, Any]:
    """Create a webhook payload for deep scan testing"""
    payload = create_sample_pr_webhook_payload()
    
    # Add deep-scan label
    payload["pull_request"]["labels"] = [
        {
            "id": 1,
            "name": "deep-scan",
            "color": "0075ca"
        }
    ]
    
    # Change action to labeled
    payload["action"] = "labeled"
    payload["label"] = {
        "id": 1,
        "name": "deep-scan",
        "color": "0075ca"
    }
    
    return payload


def send_webhook_payload(payload: Dict[str, Any], webhook_url: str, secret: str = None):
    """Send webhook payload to Archon endpoint"""
    headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': 'pull_request'
    }
    
    if secret:
        import hmac
        import hashlib
        
        payload_str = json.dumps(payload)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers['X-Hub-Signature-256'] = f'sha256={signature}'
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    
    except Exception as e:
        print(f"Error sending webhook: {e}")
        return False


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed demo PRs for Archon testing')
    parser.add_argument('--webhook-url', required=True, help='Archon webhook URL')
    parser.add_argument('--secret', help='GitHub webhook secret')
    parser.add_argument('--test-type', choices=['fast', 'deep'], default='fast', 
                       help='Type of test to run')
    
    args = parser.parse_args()
    
    print(f"Seeding {args.test_type} pass test PR...")
    
    if args.test_type == 'fast':
        payload = create_sample_pr_webhook_payload()
    else:
        payload = create_deep_scan_webhook_payload()
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    success = send_webhook_payload(payload, args.webhook_url, args.secret)
    
    if success:
        print("✅ Webhook sent successfully")
    else:
        print("❌ Failed to send webhook")
        exit(1)


if __name__ == '__main__':
    main()

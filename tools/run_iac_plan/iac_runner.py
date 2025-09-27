#!/usr/bin/env python3
"""
IaC Runner for ECS Fargate
Executes Terraform plan, OpenTofu plan, or CDK synth in sandbox environment
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
s3_client = boto3.client('s3')

# Environment variables
REPO_NAME = os.environ.get('REPO_NAME')
COMMIT_SHA = os.environ.get('COMMIT_SHA')
IAC_TYPE = os.environ.get('IAC_TYPE')
WORKDIR = os.environ.get('WORKDIR', 'infra/')
ARTIFACTS_BUCKET = os.environ.get('ARTIFACTS_BUCKET')


def clone_repository(repo_name: str, commit_sha: str) -> str:
    """Clone repository to temporary directory"""
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Clone repository (using GitHub's archive API for public repos)
        archive_url = f"https://github.com/{repo_name}/archive/{commit_sha}.zip"
        
        logger.info(f"Downloading repository archive: {archive_url}")
        
        # Download archive
        subprocess.run([
            'curl', '-L', '-o', f'{temp_dir}/repo.zip', archive_url
        ], check=True)
        
        # Extract archive
        subprocess.run([
            'unzip', f'{temp_dir}/repo.zip', '-d', temp_dir
        ], check=True)
        
        # Find the extracted directory
        extracted_dir = None
        for item in os.listdir(temp_dir):
            if item.endswith('.zip'):
                continue
            extracted_dir = os.path.join(temp_dir, item)
            break
        
        if not extracted_dir:
            raise Exception("Could not find extracted repository directory")
        
        logger.info(f"Repository cloned to: {extracted_dir}")
        return extracted_dir
    
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        raise


def run_terraform_plan(workdir: str) -> Dict[str, Any]:
    """Run Terraform plan"""
    try:
        logger.info("Running Terraform plan")
        
        # Initialize Terraform
        subprocess.run(['terraform', 'init'], cwd=workdir, check=True, capture_output=True)
        
        # Run plan
        result = subprocess.run([
            'terraform', 'plan', '-json'
        ], cwd=workdir, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Terraform plan failed: {result.stderr}")
            return {'error': result.stderr}
        
        # Parse JSON output
        plan_data = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    plan_data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        # Extract resource changes
        resource_changes = []
        for item in plan_data:
            if item.get('type') == 'resource_change':
                resource_changes.append(item)
        
        return {
            'plan_type': 'terraform',
            'resource_changes': resource_changes,
            'raw_output': result.stdout
        }
    
    except Exception as e:
        logger.error(f"Error running Terraform plan: {e}")
        return {'error': str(e)}


def run_tofu_plan(workdir: str) -> Dict[str, Any]:
    """Run OpenTofu plan"""
    try:
        logger.info("Running OpenTofu plan")
        
        # Initialize OpenTofu
        subprocess.run(['tofu', 'init'], cwd=workdir, check=True, capture_output=True)
        
        # Run plan
        result = subprocess.run([
            'tofu', 'plan', '-json'
        ], cwd=workdir, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"OpenTofu plan failed: {result.stderr}")
            return {'error': result.stderr}
        
        # Parse JSON output
        plan_data = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    plan_data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        # Extract resource changes
        resource_changes = []
        for item in plan_data:
            if item.get('type') == 'resource_change':
                resource_changes.append(item)
        
        return {
            'plan_type': 'tofu',
            'resource_changes': resource_changes,
            'raw_output': result.stdout
        }
    
    except Exception as e:
        logger.error(f"Error running OpenTofu plan: {e}")
        return {'error': str(e)}


def run_cdk_synth(workdir: str) -> Dict[str, Any]:
    """Run CDK synth"""
    try:
        logger.info("Running CDK synth")
        
        # Install dependencies
        if os.path.exists(os.path.join(workdir, 'package.json')):
            subprocess.run(['npm', 'install'], cwd=workdir, check=True, capture_output=True)
        
        # Run CDK synth
        result = subprocess.run([
            'cdk', 'synth', '--json'
        ], cwd=workdir, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"CDK synth failed: {result.stderr}")
            return {'error': result.stderr}
        
        # Parse JSON output
        try:
            synth_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            # CDK synth might not always output valid JSON
            synth_data = {'raw_output': result.stdout}
        
        return {
            'plan_type': 'cdk',
            'synth_data': synth_data,
            'raw_output': result.stdout
        }
    
    except Exception as e:
        logger.error(f"Error running CDK synth: {e}")
        return {'error': str(e)}


def upload_artifacts_to_s3(artifacts: Dict[str, Any], repo_name: str, pr_number: int, commit_sha: str) -> Dict[str, str]:
    """Upload artifacts to S3"""
    try:
        s3_paths = {}
        base_key = f"{repo_name}/{pr_number}/{commit_sha}/"
        
        # Upload plan JSON
        if 'resource_changes' in artifacts or 'synth_data' in artifacts:
            plan_key = f"{base_key}plan.json"
            s3_client.put_object(
                Bucket=ARTIFACTS_BUCKET,
                Key=plan_key,
                Body=json.dumps(artifacts, indent=2),
                ContentType='application/json'
            )
            s3_paths['plan_json'] = f"s3://{ARTIFACTS_BUCKET}/{plan_key}"
        
        # Upload raw output
        if 'raw_output' in artifacts:
            output_key = f"{base_key}raw_output.txt"
            s3_client.put_object(
                Bucket=ARTIFACTS_BUCKET,
                Key=output_key,
                Body=artifacts['raw_output'],
                ContentType='text/plain'
            )
            s3_paths['raw_output'] = f"s3://{ARTIFACTS_BUCKET}/{output_key}"
        
        logger.info(f"Uploaded artifacts to S3: {s3_paths}")
        return s3_paths
    
    except Exception as e:
        logger.error(f"Error uploading artifacts to S3: {e}")
        raise


def main():
    """Main execution function"""
    try:
        logger.info(f"Starting IaC execution for {REPO_NAME}@{COMMIT_SHA[:8]} ({IAC_TYPE})")
        
        # Validate environment variables
        if not all([REPO_NAME, COMMIT_SHA, IAC_TYPE]):
            logger.error("Missing required environment variables")
            sys.exit(1)
        
        # Clone repository
        repo_dir = clone_repository(REPO_NAME, COMMIT_SHA)
        
        # Set work directory
        workdir = os.path.join(repo_dir, WORKDIR)
        if not os.path.exists(workdir):
            logger.error(f"Work directory not found: {workdir}")
            sys.exit(1)
        
        # Run appropriate IaC tool
        if IAC_TYPE == 'terraform':
            artifacts = run_terraform_plan(workdir)
        elif IAC_TYPE == 'tofu':
            artifacts = run_tofu_plan(workdir)
        elif IAC_TYPE == 'cdk':
            artifacts = run_cdk_synth(workdir)
        else:
            logger.error(f"Unsupported IAC type: {IAC_TYPE}")
            sys.exit(1)
        
        # Check for errors
        if 'error' in artifacts:
            logger.error(f"IaC execution failed: {artifacts['error']}")
            sys.exit(1)
        
        # Upload artifacts to S3
        pr_number = os.environ.get('PR_NUMBER', 0)
        s3_paths = upload_artifacts_to_s3(artifacts, REPO_NAME, pr_number, COMMIT_SHA)
        
        logger.info("IaC execution completed successfully")
        logger.info(f"Artifacts uploaded: {s3_paths}")
        
        # Clean up
        shutil.rmtree(repo_dir)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

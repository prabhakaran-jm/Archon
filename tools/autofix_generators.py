"""
Auto-Fix Generators for Phase 3
Generates specific fixes for common security and cost optimization issues
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Evidence database for compliance references
EVIDENCE_DB = {
    's3_encryption': [
        'AWS Well-Architected Security Pillar: Data Protection',
        'CIS AWS Foundations Benchmark 3.1: Enable S3 bucket encryption',
        'NIST Cybersecurity Framework: Protect Function',
        'SOC 2 Type II: Data Encryption at Rest'
    ],
    's3_public_access': [
        'AWS Well-Architected Security Pillar: Network Security',
        'CIS AWS Foundations Benchmark 3.2: Block S3 public access',
        'NIST Cybersecurity Framework: Protect Function',
        'SOC 2 Type II: Access Controls'
    ],
    's3_lifecycle': [
        'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
        'FinOps Foundation: Storage Cost Management',
        'AWS Cost Optimization Best Practices: Storage Optimization'
    ],
    'ebs_gp3': [
        'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
        'AWS Storage Optimization Guide: EBS Volume Types',
        'AWS Cost Optimization Best Practices: Compute Optimization'
    ],
    'vpc_endpoints': [
        'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
        'AWS Networking Best Practices: NAT Gateway Optimization',
        'AWS Cost Optimization Guide: Network Optimization'
    ],
    'security_groups': [
        'AWS Well-Architected Security Pillar: Network Security',
        'CIS AWS Foundations Benchmark 4.1: Restrict Security Groups',
        'NIST Cybersecurity Framework: Protect Function'
    ]
}

# Fix templates for different resource types
FIX_TEMPLATES = {
    'aws_s3_bucket': {
        'encryption': {
            'title': 'Enable S3 bucket server-side encryption',
            'description': 'Add server-side encryption configuration to S3 bucket for data protection at rest.',
            'terraform': '''
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }''',
            'cdk': '''
  encryption: s3.BucketEncryption.S3_MANAGED,''',
            'evidence': EVIDENCE_DB['s3_encryption']
        },
        'block_public_access': {
            'title': 'Block S3 bucket public access',
            'description': 'Enable public access block settings to prevent accidental public exposure.',
            'terraform': '''
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true''',
            'cdk': '''
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,''',
            'evidence': EVIDENCE_DB['s3_public_access']
        },
        'lifecycle': {
            'title': 'Add S3 bucket lifecycle management',
            'description': 'Implement lifecycle policies to automatically transition objects to cheaper storage classes.',
            'terraform': '''
  lifecycle_rule {
    id     = "transition_to_ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }''',
            'cdk': '''
  lifecycleRules: [{
    transitions: [{
      storageClass: s3.StorageClass.INFREQUENT_ACCESS,
      transitionAfter: cdk.Duration.days(30)
    }, {
      storageClass: s3.StorageClass.GLACIER,
      transitionAfter: cdk.Duration.days(90)
    }]
  }],''',
            'evidence': EVIDENCE_DB['s3_lifecycle']
        }
    },
    'aws_ebs_volume': {
        'gp3_optimization': {
            'title': 'Optimize EBS volume to gp3',
            'description': 'Convert gp2 volume to gp3 for better price-performance ratio with 20% cost savings.',
            'terraform': '''
  type              = "gp3"
  iops              = 3000
  throughput        = 125''',
            'cdk': '''
  volumeType: ec2.EbsDeviceVolumeType.GP3,
  iops: 3000,
  throughput: 125,''',
            'evidence': EVIDENCE_DB['ebs_gp3']
        }
    },
    'aws_security_group': {
        'restrict_cidr': {
            'title': 'Restrict security group CIDR blocks',
            'description': 'Replace 0.0.0.0/0 with specific CIDR blocks for better security.',
            'terraform': '''
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]  # Replace with specific CIDR
  }''',
            'cdk': '''
  webSecurityGroup.addIngressRule(
    ec2.Peer.ipv4('10.0.0.0/16'),  // Replace with specific CIDR
    ec2.Port.tcp(80),
    'Allow HTTP from VPC'
  );''',
            'evidence': EVIDENCE_DB['security_groups']
        }
    },
    'aws_nat_gateway': {
        'vpc_endpoints': {
            'title': 'Add VPC endpoints to reduce NAT Gateway costs',
            'description': 'Create VPC endpoints for AWS services to reduce NAT Gateway data transfer costs.',
            'terraform': '''
# Add VPC endpoints for AWS services
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = var.vpc_id
  service_name = "com.amazonaws.${var.aws_region}.s3"
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoint.id]
}''',
            'cdk': '''
// Add VPC endpoints for AWS services
new ec2.VpcEndpoint(this, 'S3Endpoint', {
  vpc: vpc,
  service: ec2.VpcEndpointService.S3
});

new ec2.VpcEndpoint(this, 'ECRDockerEndpoint', {
  vpc: vpc,
  service: ec2.VpcEndpointService.ECR_DOCKER,
  subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
});''',
            'evidence': EVIDENCE_DB['vpc_endpoints']
        }
    }
}


def generate_s3_encryption_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate S3 encryption fix"""
    fix_template = FIX_TEMPLATES['aws_s3_bucket']['encryption']
    
    # Check if encryption is already configured
    if 'server_side_encryption_configuration' in resource_config:
        return None
    
    return {
        'file_path': file_path,
        'fix_type': 's3_encryption',
        'title': fix_template['title'],
        'description': fix_template['description'],
        'evidence': fix_template['evidence'],
        'changes': [
            {
                'line_number': None,
                'old_content': '',
                'new_content': fix_template['terraform'].strip()
            }
        ]
    }


def generate_s3_public_access_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate S3 public access block fix"""
    fix_template = FIX_TEMPLATES['aws_s3_bucket']['block_public_access']
    
    # Check if public access block is already configured
    if all(key in resource_config for key in ['block_public_acls', 'block_public_policy', 'ignore_public_acls', 'restrict_public_buckets']):
        return None
    
    return {
        'file_path': file_path,
        'fix_type': 's3_public_access',
        'title': fix_template['title'],
        'description': fix_template['description'],
        'evidence': fix_template['evidence'],
        'changes': [
            {
                'line_number': None,
                'old_content': '',
                'new_content': fix_template['terraform'].strip()
            }
        ]
    }


def generate_s3_lifecycle_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate S3 lifecycle management fix"""
    fix_template = FIX_TEMPLATES['aws_s3_bucket']['lifecycle']
    
    # Check if lifecycle is already configured
    if 'lifecycle_rule' in resource_config or 'lifecycle_rules' in resource_config:
        return None
    
    return {
        'file_path': file_path,
        'fix_type': 's3_lifecycle',
        'title': fix_template['title'],
        'description': fix_template['description'],
        'evidence': fix_template['evidence'],
        'changes': [
            {
                'line_number': None,
                'old_content': '',
                'new_content': fix_template['terraform'].strip()
            }
        ]
    }


def generate_ebs_gp3_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate EBS gp3 optimization fix"""
    fix_template = FIX_TEMPLATES['aws_ebs_volume']['gp3_optimization']
    
    # Check if already using gp3
    if resource_config.get('type') == 'gp3':
        return None
    
    return {
        'file_path': file_path,
        'fix_type': 'ebs_gp3',
        'title': fix_template['title'],
        'description': fix_template['description'],
        'evidence': fix_template['evidence'],
        'changes': [
            {
                'line_number': None,
                'old_content': f'type = "{resource_config.get("type", "gp2")}"',
                'new_content': fix_template['terraform'].strip()
            }
        ]
    }


def generate_security_group_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate security group CIDR restriction fix"""
    fix_template = FIX_TEMPLATES['aws_security_group']['restrict_cidr']
    
    # Check for overly permissive rules
    ingress_rules = resource_config.get('ingress', [])
    for rule in ingress_rules:
        if rule.get('cidr_blocks') == ['0.0.0.0/0']:
            return {
                'file_path': file_path,
                'fix_type': 'security_group_cidr',
                'title': fix_template['title'],
                'description': fix_template['description'],
                'evidence': fix_template['evidence'],
                'changes': [
                    {
                        'line_number': None,
                        'old_content': 'cidr_blocks = ["0.0.0.0/0"]',
                        'new_content': 'cidr_blocks = ["10.0.0.0/16"]  # Replace with specific CIDR'
                    }
                ]
            }
    
    return None


def generate_vpc_endpoints_fix(resource_config: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Generate VPC endpoints fix for NAT Gateway cost optimization"""
    fix_template = FIX_TEMPLATES['aws_nat_gateway']['vpc_endpoints']
    
    return {
        'file_path': file_path,
        'fix_type': 'vpc_endpoints',
        'title': fix_template['title'],
        'description': fix_template['description'],
        'evidence': fix_template['evidence'],
        'changes': [
            {
                'line_number': None,
                'old_content': '',
                'new_content': fix_template['terraform'].strip()
            }
        ]
    }


def analyze_and_generate_fixes(plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze plan data and generate appropriate fixes"""
    fixes = []
    
    try:
        # Parse resource changes from plan
        resource_changes = plan_data.get('resource_changes', [])
        
        for resource_change in resource_changes:
            resource_type = resource_change.get('type', '')
            resource_name = resource_change.get('name', '')
            change = resource_change.get('change', {})
            actions = change.get('actions', [])
            
            # Only generate fixes for resources being created or modified
            if 'create' not in actions and 'update' not in actions:
                continue
            
            after = change.get('after', {})
            file_path = f"infra/{resource_name}.tf"  # Default file path
            
            # Generate fixes based on resource type
            if resource_type.startswith('aws_s3_bucket'):
                # S3 encryption fix
                encryption_fix = generate_s3_encryption_fix(after, file_path)
                if encryption_fix:
                    fixes.append(encryption_fix)
                
                # S3 public access block fix
                public_access_fix = generate_s3_public_access_fix(after, file_path)
                if public_access_fix:
                    fixes.append(public_access_fix)
                
                # S3 lifecycle fix
                lifecycle_fix = generate_s3_lifecycle_fix(after, file_path)
                if lifecycle_fix:
                    fixes.append(lifecycle_fix)
            
            elif resource_type.startswith('aws_ebs_volume'):
                # EBS gp3 optimization fix
                gp3_fix = generate_ebs_gp3_fix(after, file_path)
                if gp3_fix:
                    fixes.append(gp3_fix)
            
            elif resource_type.startswith('aws_security_group'):
                # Security group CIDR restriction fix
                sg_fix = generate_security_group_fix(after, file_path)
                if sg_fix:
                    fixes.append(sg_fix)
            
            elif resource_type.startswith('aws_nat_gateway'):
                # VPC endpoints fix
                vpc_endpoints_fix = generate_vpc_endpoints_fix(after, file_path)
                if vpc_endpoints_fix:
                    fixes.append(vpc_endpoints_fix)
        
        logger.info(f"Generated {len(fixes)} auto-fixes from plan analysis")
        return fixes
    
    except Exception as e:
        logger.error(f"Error analyzing plan data for fixes: {e}")
        return []


def build_evidence_section(fixes: List[Dict[str, Any]]) -> str:
    """Build evidence section for PR body"""
    if not fixes:
        return ""
    
    evidence_items = set()
    for fix in fixes:
        evidence_items.update(fix.get('evidence', []))
    
    if not evidence_items:
        return ""
    
    evidence_list = "\n".join([f"- {item}" for item in sorted(evidence_items)])
    return f"\n\n## Evidence & Compliance\n\n{evidence_list}\n"


def build_pr_body(fixes: List[Dict[str, Any]], base_pr_number: int = None) -> str:
    """Build comprehensive PR body with evidence"""
    body_parts = [
        "🤖 **Archon Auto-Fix PR**",
        "",
        "This PR contains automated fixes for security and reliability issues detected by Archon.",
        ""
    ]
    
    if base_pr_number:
        body_parts.append(f"**Related to**: #{base_pr_number}")
        body_parts.append("")
    
    # Add fix descriptions
    body_parts.append("## Applied Fixes")
    body_parts.append("")
    
    for fix in fixes:
        body_parts.append(f"### {fix['title']}")
        body_parts.append(f"{fix['description']}")
        body_parts.append("")
    
    # Add evidence section
    evidence_section = build_evidence_section(fixes)
    if evidence_section:
        body_parts.append(evidence_section)
    
    # Add footer
    body_parts.extend([
        "---",
        "",
        "**Auto-generated by**: Archon AI Agent",
        "**Review**: Please review these changes before merging",
        "**Testing**: Ensure changes work as expected in your environment"
    ])
    
    return "\n".join(body_parts)

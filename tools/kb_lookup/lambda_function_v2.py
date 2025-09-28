"""
kb_lookup Tool - Enhanced for Deep Pass
Retrieves Well-Architected Framework guidance and evidence from Knowledge Base
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# Environment variables
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', 'archon-waf-kb')

# Well-Architected Framework Pillars
WAF_PILLARS = {
    'operational_excellence': {
        'name': 'Operational Excellence',
        'description': 'Focus on running and monitoring systems to deliver business value',
        'key_topics': ['monitoring', 'logging', 'automation', 'deployment', 'incident_response']
    },
    'security': {
        'name': 'Security',
        'description': 'Protect information and systems through security best practices',
        'key_topics': ['encryption', 'access_control', 'network_security', 'data_protection', 'compliance']
    },
    'reliability': {
        'name': 'Reliability',
        'description': 'Ensure systems recover from failures and meet business requirements',
        'key_topics': ['fault_tolerance', 'disaster_recovery', 'scaling', 'monitoring', 'testing']
    },
    'performance_efficiency': {
        'name': 'Performance Efficiency',
        'description': 'Use computing resources efficiently to meet system requirements',
        'key_topics': ['compute_optimization', 'storage_optimization', 'network_optimization', 'caching', 'monitoring']
    },
    'cost_optimization': {
        'name': 'Cost Optimization',
        'description': 'Avoid unnecessary costs while maintaining business value',
        'key_topics': ['right_sizing', 'reserved_capacity', 'monitoring', 'governance', 'pricing_models']
    },
    'sustainability': {
        'name': 'Sustainability',
        'description': 'Minimize environmental impact of cloud workloads',
        'key_topics': ['energy_efficiency', 'carbon_footprint', 'resource_optimization', 'renewable_energy']
    }
}

# Enhanced Knowledge Base content for Deep Pass
WAF_GUIDANCE_DB = {
    's3_encryption': {
        'pillar': 'security',
        'title': 'S3 Server-Side Encryption',
        'description': 'Enable server-side encryption for S3 buckets to protect data at rest',
        'guidance': [
            'Use S3 managed keys (SSE-S3) for general use cases',
            'Use AWS KMS (SSE-KMS) for enhanced security and audit requirements',
            'Enable encryption by default for all new buckets',
            'Use bucket policies to enforce encryption requirements'
        ],
        'evidence': [
            'AWS Well-Architected Security Pillar: Data Protection',
            'AWS Security Best Practices: Encryption at Rest',
            'NIST Cybersecurity Framework: Protect Function'
        ],
        'implementation': {
            'terraform': '''
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}''',
            'cdk': '''
new s3.Bucket(this, 'MyBucket', {
  encryption: s3.BucketEncryption.S3_MANAGED
});'''
        }
    },
    's3_lifecycle': {
        'pillar': 'cost_optimization',
        'title': 'S3 Lifecycle Management',
        'description': 'Implement lifecycle policies to automatically transition objects to cheaper storage classes',
        'guidance': [
            'Transition to IA after 30 days for infrequently accessed data',
            'Transition to Glacier after 90 days for archival data',
            'Delete incomplete multipart uploads after 7 days',
            'Use intelligent tiering for unpredictable access patterns'
        ],
        'evidence': [
            'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
            'AWS Cost Optimization Best Practices: Storage Optimization',
            'FinOps Foundation: Storage Cost Management'
        ],
        'implementation': {
            'terraform': '''
resource "aws_s3_bucket_lifecycle_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    id     = "transition_to_ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}''',
            'cdk': '''
new s3.Bucket(this, 'MyBucket', {
  lifecycleRules: [{
    transitions: [{
      storageClass: s3.StorageClass.INFREQUENT_ACCESS,
      transitionAfter: cdk.Duration.days(30)
    }]
  }]
});'''
        }
    },
    'ebs_optimization': {
        'pillar': 'cost_optimization',
        'title': 'EBS Volume Optimization',
        'description': 'Use gp3 volumes instead of gp2 for better price-performance ratio',
        'guidance': [
            'Migrate from gp2 to gp3 for 20% cost savings',
            'Right-size IOPS and throughput based on workload requirements',
            'Use provisioned IOPS (io1/io2) only for high-performance workloads',
            'Monitor volume performance metrics to optimize configuration'
        ],
        'evidence': [
            'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
            'AWS Storage Optimization Guide: EBS Volume Types',
            'AWS Cost Optimization Best Practices: Compute Optimization'
        ],
        'implementation': {
            'terraform': '''
resource "aws_ebs_volume" "example" {
  availability_zone = "us-west-2a"
  size              = 100
  type              = "gp3"
  iops              = 3000
  throughput        = 125
}''',
            'cdk': '''
new ec2.Volume(this, 'MyVolume', {
  availabilityZone: 'us-west-2a',
  size: cdk.Size.gibibytes(100),
  volumeType: ec2.EbsDeviceVolumeType.GP3,
  iops: 3000,
  throughput: 125
});'''
        }
    },
    'nat_gateway_optimization': {
        'pillar': 'cost_optimization',
        'title': 'NAT Gateway Cost Optimization',
        'description': 'Optimize NAT Gateway usage to reduce costs',
        'guidance': [
            'Use NAT Instance for development environments',
            'Implement VPC endpoints for AWS services to reduce NAT Gateway traffic',
            'Monitor NAT Gateway data transfer costs',
            'Consider using NAT Gateway with multiple availability zones for redundancy'
        ],
        'evidence': [
            'AWS Well-Architected Cost Optimization Pillar: Right Sizing',
            'AWS Networking Best Practices: NAT Gateway Optimization',
            'AWS Cost Optimization Guide: Network Optimization'
        ],
        'implementation': {
            'terraform': '''
# Use VPC endpoints to reduce NAT Gateway traffic
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.aws_region}.s3"
}''',
            'cdk': '''
// Use VPC endpoints to reduce NAT Gateway traffic
new ec2.VpcEndpoint(this, 'S3Endpoint', {
  vpc: vpc,
  service: ec2.VpcEndpointService.S3
});'''
        }
    },
    'monitoring_best_practices': {
        'pillar': 'operational_excellence',
        'title': 'CloudWatch Monitoring Best Practices',
        'description': 'Implement comprehensive monitoring and alerting',
        'guidance': [
            'Enable detailed monitoring for all critical resources',
            'Set up CloudWatch alarms for key metrics',
            'Use CloudWatch Logs for centralized logging',
            'Implement custom metrics for business KPIs'
        ],
        'evidence': [
            'AWS Well-Architected Operational Excellence Pillar: Monitoring',
            'AWS Monitoring Best Practices Guide',
            'Site Reliability Engineering: Monitoring and Alerting'
        ],
        'implementation': {
            'terraform': '''
resource "aws_cloudwatch_metric_alarm" "example" {
  alarm_name          = "high-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ec2 cpu utilization"
}''',
            'cdk': '''
new cloudwatch.Alarm(this, 'HighCPUUtilization', {
  metric: ec2.metricCPUUtilization(),
  threshold: 80,
  evaluationPeriods: 2,
  treatMissingData: cloudwatch.TreatMissingData.BREACHING
});'''
        }
    },
    'security_groups': {
        'pillar': 'security',
        'title': 'Security Group Best Practices',
        'description': 'Implement least privilege access with security groups',
        'guidance': [
            'Use specific port ranges instead of 0.0.0.0/0',
            'Implement security group rules with specific source IPs',
            'Use separate security groups for different tiers',
            'Regularly audit and review security group rules'
        ],
        'evidence': [
            'AWS Well-Architected Security Pillar: Network Security',
            'AWS Security Best Practices: Network Security',
            'CIS AWS Foundations Benchmark: Security Groups'
        ],
        'implementation': {
            'terraform': '''
resource "aws_security_group" "web" {
  name_prefix = "web-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}''',
            'cdk': '''
new ec2.SecurityGroup(this, 'WebSecurityGroup', {
  vpc: vpc,
  description: 'Security group for web servers',
  allowOutbound: true
});

webSecurityGroup.addIngressRule(
  ec2.Peer.ipv4('10.0.0.0/16'),
  ec2.Port.tcp(80),
  'Allow HTTP from VPC'
);'''
        }
    }
}


def search_knowledge_base_enhanced(topic: str, pillar: str = None, resource_type: str = None) -> List[Dict[str, Any]]:
    """Enhanced knowledge base search with Well-Architected Framework integration"""
    try:
        # Construct enhanced query
        query_parts = [topic]
        if pillar:
            query_parts.append(pillar)
        if resource_type:
            query_parts.append(resource_type)
        
        query = " ".join(query_parts) + " Well-Architected Framework"
        
        # Search knowledge base
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5
                }
            }
        )
        
        results = []
        for result in response.get('retrievalResults', []):
            results.append({
                'content': result.get('content', {}).get('text', ''),
                'location': result.get('location', {}),
                'score': result.get('score', 0.0),
                'metadata': result.get('metadata', {})
            })
        
        logger.info(f"Found {len(results)} knowledge base results for: {query}")
        return results
    
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return []


def get_waf_guidance(topic: str, pillar: str = None) -> Dict[str, Any]:
    """Get Well-Architected Framework guidance for a specific topic"""
    try:
        # Search in local guidance database first
        for key, guidance in WAF_GUIDANCE_DB.items():
            if topic.lower() in key.lower() or key.lower() in topic.lower():
                if not pillar or guidance['pillar'] == pillar:
                    return guidance
        
        # Fallback to knowledge base search
        kb_results = search_knowledge_base_enhanced(topic, pillar)
        
        if kb_results:
            return {
                'pillar': pillar or 'general',
                'title': f"Well-Architected Guidance for {topic}",
                'description': f"Best practices for {topic}",
                'guidance': [result['content'][:200] + "..." for result in kb_results[:3]],
                'evidence': [result['location'].get('uri', 'Knowledge Base') for result in kb_results],
                'implementation': {}
            }
        
        # Default guidance
        return {
            'pillar': pillar or 'general',
            'title': f"General Guidance for {topic}",
            'description': f"Consider implementing best practices for {topic}",
            'guidance': [
                "Review AWS Well-Architected Framework documentation",
                "Implement monitoring and alerting",
                "Follow security best practices",
                "Optimize for cost and performance"
            ],
            'evidence': [
                "AWS Well-Architected Framework",
                "AWS Best Practices Documentation"
            ],
            'implementation': {}
        }
    
    except Exception as e:
        logger.error(f"Error getting WAF guidance: {e}")
        return {
            'pillar': 'general',
            'title': 'Error retrieving guidance',
            'description': 'Unable to retrieve guidance at this time',
            'guidance': ['Please check AWS documentation'],
            'evidence': ['AWS Documentation'],
            'implementation': {}
        }


def analyze_resource_compliance(resource_type: str, resource_config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze resource configuration against Well-Architected Framework"""
    try:
        compliance_issues = []
        recommendations = []
        
        # S3 bucket analysis
        if resource_type.startswith('aws_s3_bucket'):
            if not resource_config.get('server_side_encryption_configuration'):
                compliance_issues.append({
                    'issue': 'S3 bucket lacks server-side encryption',
                    'severity': 'high',
                    'pillar': 'security',
                    'guidance': get_waf_guidance('s3_encryption', 'security')
                })
            
            if not resource_config.get('lifecycle_configuration'):
                compliance_issues.append({
                    'issue': 'S3 bucket lacks lifecycle management',
                    'severity': 'medium',
                    'pillar': 'cost_optimization',
                    'guidance': get_waf_guidance('s3_lifecycle', 'cost_optimization')
                })
        
        # EBS volume analysis
        elif resource_type.startswith('aws_ebs_volume'):
            if resource_config.get('type') == 'gp2':
                compliance_issues.append({
                    'issue': 'EBS volume using gp2 instead of gp3',
                    'severity': 'medium',
                    'pillar': 'cost_optimization',
                    'guidance': get_waf_guidance('ebs_optimization', 'cost_optimization')
                })
        
        # Security group analysis
        elif resource_type.startswith('aws_security_group'):
            ingress_rules = resource_config.get('ingress', [])
            for rule in ingress_rules:
                if rule.get('cidr_blocks') == ['0.0.0.0/0']:
                    compliance_issues.append({
                        'issue': f"Security group allows access from anywhere (0.0.0.0/0) on port {rule.get('from_port', 'unknown')}",
                        'severity': 'high',
                        'pillar': 'security',
                        'guidance': get_waf_guidance('security_groups', 'security')
                    })
        
        # NAT Gateway analysis
        elif resource_type.startswith('aws_nat_gateway'):
            compliance_issues.append({
                'issue': 'NAT Gateway detected - consider cost optimization',
                'severity': 'low',
                'pillar': 'cost_optimization',
                'guidance': get_waf_guidance('nat_gateway_optimization', 'cost_optimization')
            })
        
        return {
            'resource_type': resource_type,
            'compliance_score': max(0, 100 - len(compliance_issues) * 20),
            'issues': compliance_issues,
            'recommendations': recommendations
        }
    
    except Exception as e:
        logger.error(f"Error analyzing resource compliance: {e}")
        return {
            'resource_type': resource_type,
            'compliance_score': 0,
            'issues': [],
            'recommendations': []
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enhanced kb_lookup tool handler for Deep Pass
    
    Input:
    {
        "topic": "s3_encryption",
        "pillar": "security",
        "resource_type": "aws_s3_bucket",
        "resource_config": {...},
        "plan_data": {...}
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "guidance": {...},
            "compliance_analysis": {...},
            "evidence": [...],
            "recommendations": [...]
        },
        "error": "error message if status is error"
    }
    """
    try:
        topic = event.get('topic', 'general')
        pillar = event.get('pillar')
        resource_type = event.get('resource_type')
        resource_config = event.get('resource_config', {})
        plan_data = event.get('plan_data', {})
        
        # Get Well-Architected Framework guidance
        guidance = get_waf_guidance(topic, pillar)
        
        # Analyze resource compliance if resource type provided
        compliance_analysis = None
        if resource_type and resource_config:
            compliance_analysis = analyze_resource_compliance(resource_type, resource_config)
        
        # Extract evidence and recommendations
        evidence = guidance.get('evidence', [])
        recommendations = []
        
        # Add implementation recommendations
        if guidance.get('implementation'):
            recommendations.append({
                'type': 'implementation',
                'title': 'Implementation Example',
                'description': 'Code example for implementing this guidance',
                'code': guidance['implementation']
            })
        
        # Add compliance recommendations if available
        if compliance_analysis and compliance_analysis.get('issues'):
            for issue in compliance_analysis['issues']:
                recommendations.append({
                    'type': 'compliance',
                    'title': issue['issue'],
                    'severity': issue['severity'],
                    'pillar': issue['pillar'],
                    'guidance': issue['guidance']
                })
        
        result_data = {
            'guidance': guidance,
            'compliance_analysis': compliance_analysis,
            'evidence': evidence,
            'recommendations': recommendations,
            'pillar_info': WAF_PILLARS.get(pillar, {}) if pillar else {}
        }
        
        logger.info(f"Retrieved WAF guidance for {topic} with {len(recommendations)} recommendations")
        
        return {
            'status': 'success',
            'data': result_data
        }
    
    except Exception as e:
        logger.error(f"Error in enhanced kb_lookup: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

# AWS EBS Volume Optimization

## Overview
Amazon EBS provides persistent block storage volumes for EC2 instances. Proper configuration and optimization can significantly reduce costs while improving performance.

## Volume Types

### General Purpose SSD (gp2)
- **Performance**: 3 IOPS per GB, up to 16,000 IOPS
- **Cost**: Higher cost per GB
- **Use Case**: Boot volumes, small to medium databases

### General Purpose SSD (gp3)
- **Performance**: 3,000 IOPS baseline, up to 16,000 IOPS
- **Cost**: 20% lower cost than gp2
- **Use Case**: Most workloads, cost optimization

### Provisioned IOPS SSD (io1/io2)
- **Performance**: Up to 64,000 IOPS
- **Cost**: Highest cost
- **Use Case**: High-performance databases

### Throughput Optimized HDD (st1)
- **Performance**: High throughput, low IOPS
- **Cost**: Lower cost
- **Use Case**: Big data, data warehouses

### Cold HDD (sc1)
- **Performance**: Lowest cost
- **Use Case**: Infrequently accessed data

## Optimization Best Practices

### Volume Type Selection
- Use gp3 instead of gp2 for cost savings
- Use st1 for throughput-intensive workloads
- Use io1/io2 only when high IOPS required
- Right-size based on actual requirements

### Performance Optimization
- Enable EBS optimization for EC2 instances
- Use EBS-optimized instance types
- Implement proper I/O patterns
- Use EBS Multi-Attach for shared storage

### Cost Optimization
- Migrate from gp2 to gp3 for 20% savings
- Use st1 for large, sequential workloads
- Implement proper snapshot management
- Use EBS Fast Snapshot Restore for critical volumes

## Common EBS Issues

### Using gp2 Instead of gp3
- **Issue**: Higher cost with gp2 volumes
- **Severity**: MEDIUM
- **Fix**: Migrate to gp3 for cost savings
- **Evidence**: AWS Cost Optimization Guide

### Over-Provisioned IOPS
- **Issue**: Provisioning more IOPS than needed
- **Severity**: MEDIUM
- **Fix**: Right-size based on actual usage
- **Evidence**: AWS Compute Optimizer recommendations

### No Encryption
- **Issue**: EBS volumes not encrypted
- **Severity**: HIGH
- **Fix**: Enable encryption by default
- **Evidence**: NIST SP 800-53 SC-28

### No Snapshots
- **Issue**: No backup strategy for EBS volumes
- **Severity**: HIGH
- **Fix**: Implement automated snapshots
- **Evidence**: AWS Well-Architected Framework Reliability Pillar

## Terraform Configuration Examples

### Optimized EBS Volume
```hcl
resource "aws_ebs_volume" "optimized_volume" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  iops              = 3000
  throughput        = 125
  encrypted         = true

  tags = {
    Name = "optimized-volume"
  }
}

resource "aws_ebs_snapshot" "volume_snapshot" {
  volume_id = aws_ebs_volume.optimized_volume.id

  tags = {
    Name = "volume-snapshot"
  }
}
```

### EBS Volume with Lifecycle
```hcl
resource "aws_ebs_volume" "lifecycle_volume" {
  availability_zone = "us-east-1a"
  size              = 500
  type              = "st1"
  encrypted         = true

  tags = {
    Name = "lifecycle-volume"
  }
}

resource "aws_dlm_lifecycle_policy" "ebs_snapshot_policy" {
  description        = "EBS snapshot policy"
  execution_role_arn = aws_iam_role.dlm_lifecycle_role.arn
  state              = "ENABLED"

  policy_details {
    resource_types   = ["VOLUME"]
    target_tags = {
      Snapshot = "true"
    }

    schedule {
      name = "daily-snapshots"

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }

      retain_rule {
        count = 7
      }

      copy_tags = true
    }
  }
}
```

## Migration Strategies

### gp2 to gp3 Migration
1. Create gp3 volume with same size
2. Attach both volumes to instance
3. Copy data from gp2 to gp3
4. Detach gp2 volume
5. Attach gp3 volume to original mount point

### Performance Testing
- Use CloudWatch metrics for IOPS monitoring
- Test different volume types for workload
- Monitor cost impact of changes
- Implement proper alerting

## Compliance References
- **AWS Well-Architected Framework**: Cost Optimization Pillar
- **NIST SP 800-53 SC-28**: Protection of Information at Rest
- **AWS Cost Optimization Guide**: EBS Volume Types
- **SOC 2 Type II**: Data Protection Controls

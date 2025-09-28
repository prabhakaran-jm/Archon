# AWS S3 Security Best Practices

## Overview
Amazon S3 is a highly scalable object storage service. Proper security configuration is critical to prevent data breaches and unauthorized access.

## Security Configuration

### Encryption
- **Server-Side Encryption**: Enable SSE-S3 or SSE-KMS
- **Client-Side Encryption**: Encrypt data before uploading
- **Encryption in Transit**: Use HTTPS for all S3 operations
- **Key Management**: Use AWS KMS for encryption keys

### Access Control
- **Block Public Access**: Enable all four public access block settings
- **Bucket Policies**: Implement least privilege access
- **IAM Policies**: Use IAM roles instead of access keys
- **Access Logging**: Enable S3 access logging

### Lifecycle Management
- **Lifecycle Rules**: Automatically transition objects to cheaper storage classes
- **Expiration**: Automatically delete objects after specified time
- **Versioning**: Enable versioning for data protection
- **MFA Delete**: Require MFA for object deletion

## Common S3 Security Issues

### Public Access
- **Issue**: S3 bucket allows public read access
- **Severity**: HIGH
- **Fix**: Enable block public access settings
- **Evidence**: CIS AWS Foundations Benchmark 3.6

### No Encryption
- **Issue**: S3 bucket not encrypted
- **Severity**: HIGH
- **Fix**: Enable server-side encryption
- **Evidence**: NIST SP 800-53 SC-28

### No Lifecycle Rules
- **Issue**: No lifecycle management for cost optimization
- **Severity**: MEDIUM
- **Fix**: Implement lifecycle rules
- **Evidence**: AWS Well-Architected Framework Cost Optimization Pillar

### No Access Logging
- **Issue**: No access logging enabled
- **Severity**: MEDIUM
- **Fix**: Enable S3 access logging
- **Evidence**: CIS AWS Foundations Benchmark 3.1

## Terraform Configuration Examples

### Secure S3 Bucket
```hcl
resource "aws_s3_bucket" "secure_bucket" {
  bucket = "my-secure-bucket"
}

resource "aws_s3_bucket_versioning" "secure_bucket" {
  bucket = aws_s3_bucket.secure_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "secure_bucket" {
  bucket = aws_s3_bucket.secure_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "secure_bucket" {
  bucket = aws_s3_bucket.secure_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

resource "aws_s3_bucket_lifecycle_configuration" "secure_bucket" {
  bucket = aws_s3_bucket.secure_bucket.id

  rule {
    id     = "log"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 365
    }
  }
}
```

## Compliance References
- **CIS AWS Foundations Benchmark 3.1**: Ensure S3 Bucket Server Access Logging is Enabled
- **CIS AWS Foundations Benchmark 3.6**: Ensure S3 Bucket Public Access is Blocked
- **NIST SP 800-53 SC-28**: Protection of Information at Rest
- **AWS Well-Architected Framework**: Security Pillar
- **SOC 2 Type II**: Logical and Physical Access Controls

# Sample Terraform configuration with security issues for Archon testing

# S3 bucket without encryption (security issue)
resource "aws_s3_bucket" "example" {
  bucket = "archon-test-bucket-${random_id.bucket_suffix.hex}"
}

# Missing server-side encryption configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Missing block public access
resource "aws_s3_bucket_public_access_block" "example" {
  bucket = aws_s3_bucket.example.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Random suffix for bucket name
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# NAT Gateway (expensive resource)
resource "aws_nat_gateway" "example" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  tags = {
    Name = "archon-test-nat-gateway"
  }
}

# EIP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "archon-test-nat-eip"
  }
}

# VPC
resource "aws_vpc" "example" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "archon-test-vpc"
  }
}

# Public subnet
resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.example.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "eu-west-1a"

  tags = {
    Name = "archon-test-public-subnet"
  }
}

# EBS volume with gp2 (should be gp3)
resource "aws_ebs_volume" "example" {
  availability_zone = "eu-west-1a"
  size              = 20
  type              = "gp2"  # Should be gp3 for cost optimization

  tags = {
    Name = "archon-test-volume"
  }
}

# RDS instance without multi-AZ (reliability issue)
resource "aws_db_instance" "example" {
  identifier = "archon-test-db"
  engine     = "postgres"
  engine_version = "14.7"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  storage_type = "gp2"

  # Missing multi-AZ configuration
  # multi_az = true

  db_name  = "archontest"
  username = "postgres"
  password = "changeme123"  # Should use secrets manager

  skip_final_snapshot = true

  tags = {
    Name = "archon-test-rds"
  }
}

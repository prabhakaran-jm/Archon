# Archon Configuration

This directory contains configuration templates and environment-specific settings for Archon.

## Files

### Templates
- `secrets.env.template` - Template for sensitive configuration values
- `config.env.template` - Template for non-sensitive configuration values

### Usage

1. **Copy templates to create your environment files:**
   ```bash
   cp config/secrets.env.template config/secrets.env
   cp config/config.env.template config/config.env
   ```

2. **Edit the files with your actual values:**
   ```bash
   vim config/secrets.env
   vim config/config.env
   ```

3. **Use the configuration management script:**
   ```bash
   ./scripts/config.sh dev init    # Create templates
   ./scripts/config.sh dev load    # Load configuration
   ./scripts/config.sh dev export  # Export to components
   ```

## Configuration Values

### Required Secrets (`secrets.env`)

#### GitHub Configuration
- `GITHUB_WEBHOOK_SECRET`: Secret for webhook signature verification
- `GITHUB_TOKEN`: Personal access token with repository access

#### AWS Configuration
- `AWS_REGION`: Target AWS region (default: us-east-1)
- `AWS_ACCESS_KEY_ID`: AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key

#### Bedrock Configuration (Optional)
- `BEDROCK_AGENT_ID`: Bedrock Agent ID
- `BEDROCK_AGENT_ALIAS_ID`: Agent alias ID (default: TSTALIASID)
- `KNOWLEDGE_BASE_ID`: Knowledge Base ID

### Application Configuration (`config.env`)

#### Feature Flags
- `ENABLE_DEEP_SCAN`: Enable deep analysis mode (default: true)
- `ENABLE_AUTO_FIX`: Enable auto-fix PR generation (default: true)
- `ENABLE_METRICS`: Enable CloudWatch metrics (default: true)

#### Performance Settings
- `MAX_CONCURRENT_REQUESTS`: Maximum concurrent requests (default: 100)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 3600)

#### Deep Scan Configuration
- `DEEP_SCAN_LABEL`: Label to trigger deep analysis (default: deep-scan)
- `FAST_SCAN_CHANGED_FILES_THRESHOLD`: Files threshold for deep scan (default: 10)
- `FAST_SCAN_ADDITIONS_THRESHOLD`: Additions threshold for deep scan (default: 200)

## Security Notes

- **Never commit `secrets.env`** to version control
- Use AWS Secrets Manager for production secrets
- Rotate secrets regularly
- Use least privilege IAM policies
- Enable CloudTrail for audit logging

## Environment-Specific Configuration

### Development
```bash
ENVIRONMENT=dev
LOG_LEVEL=DEBUG
ENABLE_METRICS=false
```

### Staging
```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

### Production
```bash
ENVIRONMENT=prod
LOG_LEVEL=WARN
ENABLE_METRICS=true
AUTO_FIX_ENABLED=false  # Manual review required
```

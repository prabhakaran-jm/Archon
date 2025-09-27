# Archon

**Autonomous Principal Architect for CI/CD**

Archon prevents costly and insecure infrastructure-as-code (IaC) changes before merge by running autonomous FinOps, Security, and Well-Architected checks on pull requests, posting unified guidance, and (optionally) opening small auto-fix PRs.

## Quick Start

```bash
# Deploy Archon
make deploy

# Run local development
make dev

# Run tests
make test
```

## Features

- 🛡️ **Security Scanning**: Static analysis with Checkov/tfsec for AWS best practices
- 💰 **Cost Analysis**: Real-time pricing deltas with confidence intervals
- ⚙️ **Reliability Checks**: Well-Architected Framework compliance
- 🤖 **Auto-Fix PRs**: Automated remediation for common issues
- 📊 **Observability**: CloudWatch metrics and detailed reporting

## Architecture

See [docs/architecture-diagram.md](docs/architecture-diagram.md) for detailed system architecture.

## Development

### MVP Scope (Current Branch: `feat/mvp-fast-pass`)

1. ✅ Webhook endpoint with GitHub signature verification
2. ✅ Bedrock AgentCore with tool registry
3. ✅ Fast pass analysis (< 60s)
4. ✅ Basic FinOps pricing calculator
5. ✅ Security static scanning
6. ✅ Unified PR comments

### Deep Pass (Next: `feat/deep-pass-fargate`)

- ECS Fargate for Terraform/CDK plan execution
- Knowledge Base integration
- Enhanced pricing with plan analysis

### Auto-Fix (Future: `feat/autofix-pr`)

- Automated remediation PRs
- S3 SSE + lifecycle rules
- gp2 → gp3 migrations

## Contributing

1. Follow the branching strategy: `feat/mvp-fast-pass` → `feat/deep-pass-fargate` → `feat/autofix-pr`
2. Make small, vertical commits
3. Each commit must compile, run, and include tests
4. Prefer interfaces first, then stubs, then implementation

## License

MIT

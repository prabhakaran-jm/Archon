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

### MVP Scope (Current Branch: `feat/mvp-fast-pass`) ✅ COMPLETED

1. ✅ Repository structure and documentation
2. ✅ Webhook endpoint with GitHub signature verification
3. ✅ Bedrock AgentCore with tool registry
4. ✅ Core tool stubs with strict I/O JSON contracts
5. ✅ Local testing and validation framework
6. ✅ Fast pass analysis (< 60s) - *All tools working*
7. ✅ Basic FinOps pricing calculator - *Heuristic cost analysis*
8. ✅ Security static scanning - *Checkov/tfsec with SARIF*
9. ✅ Unified PR comments - *Markdown with 💰🛡️⚙️ sections*

**🎉 MVP Fast Pass Complete! Ready for Deep Pass implementation.**

### Deep Pass (Next: `feat/deep-pass-fargate`)

- ECS Fargate for Terraform/CDK plan execution
- Knowledge Base integration
- Enhanced pricing with plan analysis

### Auto-Fix (Future: `feat/autofix-pr`)

- Automated remediation PRs
- S3 SSE + lifecycle rules
- gp2 → gp3 migrations

## Contributing

### Branching Strategy

We follow a strict branching strategy for incremental development:

1. **`feat/mvp-fast-pass`** (Current) - Fast pass analysis with basic tools
2. **`feat/deep-pass-fargate`** - ECS Fargate integration for full IaC analysis  
3. **`feat/autofix-pr`** - Automated remediation PR generation

### Development Guidelines

1. Follow the branching strategy: `feat/mvp-fast-pass` → `feat/deep-pass-fargate` → `feat/autofix-pr`
2. Make small, vertical commits with clear messages
3. Each commit must compile, run, and include tests
4. Prefer interfaces first, then stubs, then implementation
5. Test locally before pushing to remote branches

## License

MIT

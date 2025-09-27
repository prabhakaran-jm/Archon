# Archon Makefile

.PHONY: help deploy dev test clean lint format

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deploy: ## Deploy Archon to AWS
	@echo "Deploying Archon..."
	cd infra && terraform init && terraform apply -auto-approve

dev: ## Start local development environment
	@echo "Starting development environment..."
	python -m venv venv
	. venv/bin/activate || . venv/Scripts/activate
	pip install -r requirements.txt
	@echo "Development environment ready"

test: ## Run all tests
	@echo "Running tests..."
	python -m pytest tests/ -v --cov=tools --cov=agent

lint: ## Run linters
	@echo "Running linters..."
	black --check .
	flake8 .
	mypy tools/ agent/

format: ## Format code
	@echo "Formatting code..."
	black .
	isort .

clean: ## Clean up build artifacts
	@echo "Cleaning up..."
	rm -rf venv/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	find . -name "*.pyc" -delete

# Docker targets
docker-build: ## Build Docker images
	@echo "Building Docker images..."
	docker build -t archon/agent:latest -f tools/run_iac_plan/Dockerfile .

# GitHub App setup
setup-github-app: ## Setup GitHub App configuration
	@echo "Setting up GitHub App..."
	@echo "Please configure your GitHub App with the following settings:"
	@echo "- Webhook URL: https://your-api-gateway-url/webhook"
	@echo "- Permissions: Read PRs, Write comments, Create branches/PRs"
	@echo "- Events: Pull requests, Issue comments"

# Sample data
seed-demo: ## Seed demo repositories with sample PRs
	@echo "Seeding demo repositories..."
	python demo/scripts/seed_prs.py

# Metrics and monitoring
metrics: ## Show CloudWatch metrics
	@echo "Fetching CloudWatch metrics..."
	aws cloudwatch get-metric-statistics \
		--namespace Archon \
		--metric-name ScanDuration \
		--start-time $(shell date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
		--end-time $(shell date -u +%Y-%m-%dT%H:%M:%S) \
		--period 300 \
		--statistics Average

# Security scanning
security-scan: ## Run security scan on the codebase
	@echo "Running security scan..."
	safety check
	bandit -r tools/ agent/

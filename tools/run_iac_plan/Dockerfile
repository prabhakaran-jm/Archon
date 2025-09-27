FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Install system dependencies
RUN dnf update -y && \
    dnf install -y \
    git \
    curl \
    unzip \
    python3 \
    python3-pip \
    jq \
    && dnf clean all

# Install Terraform
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip -o terraform.zip && \
    unzip terraform.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform.zip

# Install OpenTofu
RUN curl -fsSL https://github.com/opentofu/opentofu/releases/download/v1.6.0/tofu_1.6.0_linux_amd64.zip -o tofu.zip && \
    unzip tofu.zip && \
    mv tofu /usr/local/bin/ && \
    rm tofu.zip

# Install AWS CDK
RUN python3 -m pip install aws-cdk-lib constructs

# Install Node.js for CDK
RUN curl -fsSL https://rpm.nodesource.com/setup_18.x | bash - && \
    dnf install -y nodejs

# Install CDK globally
RUN npm install -g aws-cdk

# Create working directory
WORKDIR /workspace

# Copy the IaC runner script
COPY iac_runner.py /usr/local/bin/iac_runner.py
RUN chmod +x /usr/local/bin/iac_runner.py

# Set environment variables
ENV AWS_DEFAULT_REGION=eu-west-1

# Create non-root user
RUN useradd -m -s /bin/bash archon
USER archon

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/iac_runner.py"]

# Production-grade Dockerfile for Kubernetes Chaos Testing
# Supports: pytest automation, modular requirements, dynamic configuration
# Works with: podman, docker, and Docker-compatible runtimes
#
# Build: podman build -t chaos-test:latest .
# Run:   podman run --rm -e NAMESPACE=windows-bsod -e TARGET_NAME=win2022-vm chaos-test:latest

FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies (minimal, production-ready)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Download and install kubectl binary directly
RUN curl -L https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl && \
    kubectl version --client 2>/dev/null || echo "kubectl installed"

# Create symlink from kubectl to oc for compatibility with OpenShift CLI expectations
RUN ln -sf /usr/local/bin/kubectl /usr/local/bin/oc && \
    echo "✓ oc symlink created (kubectl → oc)"

# Download and install virtctl binary (KubeVirt CLI)
RUN curl -L https://github.com/kubevirt/kubevirt/releases/download/v1.1.1/virtctl-v1.1.1-linux-x86_64 -o /usr/local/bin/virtctl && \
    chmod +x /usr/local/bin/virtctl && \
    virtctl version --client 2>/dev/null || echo "virtctl installed"

# Copy project files
COPY . .

# Create and activate virtual environment
RUN python3.11 -m venv .venv

# Make venv Python executable available in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Upgrade pip, setuptools, wheel
RUN pip install --upgrade pip setuptools wheel

# Install base + vm requirements (always needed)
RUN pip install -r requirements/base.txt && \
    pip install -r requirements/vm.txt

# Stage 2: Runtime image with minimal footprint
FROM python:3.11-slim

WORKDIR /app

# Copy kubectl from base stage to runtime (needed for K8s operations)
COPY --from=base /usr/local/bin/kubectl /usr/local/bin/kubectl

# Create symlink for oc compatibility
RUN ln -sf /usr/local/bin/kubectl /usr/local/bin/oc

# Copy only necessary files from base stage
COPY --from=base /app .

# Set environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default configuration (can be overridden at runtime)
ENV NAMESPACE=windows-bsod \
    TARGET_NAME=win2022-vm-hjoshi1 \
    TARGET_TYPE=vm

# Health check: verify pytest can be imported
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pytest; print('pytest ready')" || exit 1

# Run tests with optional marker filtering
# If PYTEST_MARKER is set, run only tests matching that marker
# If PYTEST_MARKER is empty, run all tests
# Examples:
#   podman run -e PYTEST_MARKER=krkn chaos-test:latest        # Run only @pytest.mark.krkn tests
#   podman run -e PYTEST_MARKER="not benchmark" chaos-test    # Run all except benchmark
#   podman run chaos-test:latest                               # Run all tests (default)
ENV PYTEST_MARKER=""

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["pytest tests/ -v $([ -n \"$PYTEST_MARKER\" ] && echo \"-m '$PYTEST_MARKER'\" || echo '')"]

# Docker/Podman Setup for Chaos Testing

This document explains how to containerize and run chaos tests using **Podman** (RedHat's Docker) or Docker.

## Overview

The Docker setup provides:

- **Containerized test environment** (Python 3.11, pytest, all dependencies)
- **Multi-stage build** (optimized image size)
- **Environment variable configuration** (NAMESPACE, TARGET_NAME, TARGET_TYPE)
- **Health checks** (automatic verification)
- **Docker Compose** for multi-target testing
- **Production-ready** with best practices

## Prerequisites

### Podman (RedHat Docker)

```bash
# Install Podman on RHEL/CentOS/Fedora
sudo dnf install podman podman-compose

# Verify installation
podman --version
podman-compose --version
```

### Docker (alternative)

```bash
# Install Docker Desktop or Docker Engine
docker --version
docker-compose --version
```

## Quick Start

### 1. Build the image

```bash
# Using Podman (recommended for RedHat environments)
podman build -t chaos-test:latest .

# Using Docker (if you prefer)
docker build -t chaos-test:latest .
```

### 2. Run tests in container

```bash
# Chaos test with defaults
podman run --rm chaos-test:latest

# Chaos test with custom configuration
podman run --rm \
  -e NAMESPACE=windows-bsod \
  -e TARGET_NAME=win2022-vm-hjoshi1 \
  -e TARGET_TYPE=vm \
  chaos-test:latest

# Chaos test with cleanup
podman run --rm \
  -e NAMESPACE=windows-bsod \
  -e TARGET_NAME=win2022-vm-hjoshi1 \
  chaos-test:latest \
  tests/test_chaos.py -v --cleanup-all

# Interactive shell in container
podman run -it --rm chaos-test:latest bash

# Specific test file
podman run --rm chaos-test:latest tests/test_chaos.py -v
```

## Docker Compose Usage

### 1. Build image (via docker-compose)

```bash
# Using Podman
podman-compose build

# Using Docker
docker-compose build
```

### 2. Run all services

```bash
# Using Podman
podman-compose up

# Using Docker
docker-compose up
```

### 3. Run specific service

```bash
# Chaos test on VM
podman-compose run chaos-vm

# Interactive shell
podman-compose run chaos-vm bash

# Run with different command
podman-compose run chaos-vm pytest tests/ -v --cleanup-all
```

### 4. View logs

```bash
# All services
podman-compose logs -f

# Specific service
podman-compose logs -f chaos-vm
```

## Configuration via Environment Variables

### Method 1: CLI Environment Variables

```bash
# Using Podman
podman run --rm \
  -e NAMESPACE=staging-vms \
  -e TARGET_NAME=staging-vm-01 \
  -e TARGET_TYPE=vm \
  chaos-test:latest

# Using Docker
docker run --rm \
  -e NAMESPACE=staging-vms \
  -e TARGET_NAME=staging-vm-01 \
  -e TARGET_TYPE=vm \
  chaos-test:latest
```

### Method 2: Environment File

Create `env.prod`:

```bash
NAMESPACE=prod-vms
TARGET_NAME=prod-win-01
TARGET_TYPE=vm
```

Run with env file:

```bash
podman run --rm --env-file env.prod chaos-test:latest

docker run --rm --env-file env.prod chaos-test:latest
```

### Method 3: Docker Compose Environment

Edit `docker-compose.yml`:

```yaml
services:
  chaos-vm:
    environment:
      NAMESPACE: prod-vms
      TARGET_NAME: prod-win-01
      TARGET_TYPE: vm
```

## Running Tests Against Multiple Targets

### Sequential Execution

```bash
#!/bin/bash
# Run against multiple VMs sequentially

NAMESPACE="prod-vms"
TARGETS=("prod-win-01" "prod-win-02" "prod-linux-01")

for TARGET in "${TARGETS[@]}"; do
  echo "Testing $TARGET..."
  podman run --rm \
    -e NAMESPACE=$NAMESPACE \
    -e TARGET_NAME=$TARGET \
    -e TARGET_TYPE=vm \
    chaos-test:latest \
    tests/test_chaos.py -v --cleanup-all
done
```

### Parallel Execution (with Docker Compose)

```bash
# Create services in docker-compose.yml for each target
podman-compose up

# Or use -d for detached mode
podman-compose up -d

# View results
podman-compose logs
```

## Kubernetes Integration

### Running tests from Kubernetes Pod

Create `pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: chaos-test
spec:
  serviceAccountName: chaos-test  # Must have K8s API access
  containers:
  - name: chaos-test
    image: chaos-test:latest
    imagePullPolicy: Always
    env:
    - name: NAMESPACE
      value: "windows-bsod"
    - name: TARGET_NAME
      value: "win2022-vm-hjoshi1"
    - name: TARGET_TYPE
      value: "vm"
    volumeMounts:
    - name: kubeconfig
      mountPath: /root/.kube
      readOnly: true
  volumes:
  - name: kubeconfig
    secret:
      secretName: kubeconfig
  restartPolicy: Never
```

Run in Kubernetes:

```bash
# Create the pod
kubectl apply -f pod.yaml

# View logs
kubectl logs chaos-test

# Delete pod
kubectl delete pod chaos-test
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/chaos-tests.yml`:

```yaml
name: Chaos Tests

on: [push, pull_request]

jobs:
  chaos-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build image
        run: docker build -t chaos-test:latest .
      
      - name: Run chaos test
        run: |
          docker run --rm \
            -e NAMESPACE=${{ secrets.KRKN_NAMESPACE }} \
            -e TARGET_NAME=${{ secrets.KRKN_TARGET }} \
            chaos-test:latest \
            tests/test_chaos.py -v --cleanup-all
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - build
  - test

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t chaos-test:latest .
    - docker push $CI_REGISTRY_IMAGE:latest

test:
  stage: test
  image: chaos-test:latest
  variables:
    NAMESPACE: $KRKN_NAMESPACE
    TARGET_NAME: $KRKN_TARGET
    TARGET_TYPE: "vm"
  script:
    - pytest tests/test_chaos.py -v --cleanup-all
```

## Image Details

### Image Size Optimization

The Dockerfile uses **multi-stage builds** to keep image size small:

- **Stage 1 (build)**: Python 3.11, build dependencies
- **Stage 2 (runtime)**: Only runtime dependencies copied

Result: Smaller image, faster pulls, secure (no build tools in runtime)

### Base Image

- **Python 3.11-slim** (smallest official Python 3.11 image)
- **Debian-based** (compatible with Red Hat Podman)
- **~150MB** total image size

### Installed Packages

Required (from requirements/base.txt):
- pytest
- pytest-metadata
- pyyaml
- kubernetes client
- krkn-lib dependencies

## Troubleshooting

### Image won't build

```bash
# Check build logs
podman build -t chaos-test:latest . --log-level debug

# Clear build cache
podman builder prune

# Rebuild from scratch
podman build --no-cache -t chaos-test:latest .
```

### Tests fail in container

```bash
# Run with verbose logging
podman run --rm -e PYTHONUNBUFFERED=1 chaos-test:latest pytest tests/ -vv

# Interactive debugging
podman run -it --rm chaos-test:latest bash
# Inside container:
$ pytest tests/test_chaos.py -vv
```

### Kubernetes API access issues

```bash
# Mount kubeconfig
podman run --rm \
  -v ~/.kube/config:/root/.kube/config:ro \
  chaos-test:latest

# Or set KUBECONFIG env var
podman run --rm \
  -e KUBECONFIG=/kubeconfig/config \
  -v ~/.kube/config:/kubeconfig/config:ro \
  chaos-test:latest
```

### Network connectivity issues

```bash
# Run with host network (not recommended for security)
podman run --rm \
  --network host \
  chaos-test:latest

# Or specify custom network
podman network create chaos-net
podman run --rm \
  --network chaos-net \
  chaos-test:latest
```

## Advanced Usage

### Custom requirements

If you need additional packages, modify Dockerfile:

```dockerfile
# Before: RUN pip install -r requirements/base.txt

# Add this:
RUN pip install -r requirements/base.txt && \
    pip install -r requirements/krknlib.txt && \
    pip install -r requirements/benchmark.txt
```

Rebuild:

```bash
podman build -t chaos-test:latest .
```

### Running multiple test suites

```bash
# All tests
podman run --rm chaos-test:latest

# Chaos tests only
podman run --rm chaos-test:latest tests/test_chaos.py -v

# Benchmark tests only
podman run --rm chaos-test:latest tests/test_benchmark.py -v

# Specific test
podman run --rm chaos-test:latest tests/test_chaos.py::TestChaos::test_vmSurvivesVirtLauncherKill -v
```

### Volume mounts for development

```bash
# Mount entire project for live development
podman run -it --rm \
  -v $PWD:/app \
  chaos-test:latest \
  bash

# Inside container, changes are reflected live
$ pytest tests/ -v
```

## Best Practices

### 1. Always use `--rm` to cleanup containers

```bash
podman run --rm chaos-test:latest
```

### 2. Pin image versions in production

```bash
# Bad (latest is unstable)
podman run chaos-test:latest

# Good (explicit version)
podman run chaos-test:v1.0.0
```

### 3. Use readonly kubeconfig mount

```bash
podman run --rm \
  -v ~/.kube/config:/root/.kube/config:ro \
  chaos-test:latest
```

### 4. Set resource limits

```bash
podman run --rm \
  --memory 512m \
  --cpus 2 \
  chaos-test:latest
```

### 5. Use environment files for sensitive data

```bash
# Create env.secret (git-ignored)
NAMESPACE=prod-vms
TARGET_NAME=prod-win-01

# Use it
podman run --rm --env-file env.secret chaos-test:latest
```

## Production Deployment

### Push to registry

```bash
# Tag for registry
podman tag chaos-test:latest quay.io/myorg/chaos-test:latest

# Login to registry
podman login quay.io

# Push image
podman push quay.io/myorg/chaos-test:latest
```

### Deploy to Kubernetes

```bash
# Create secret with kubeconfig
kubectl create secret generic kubeconfig --from-file=$HOME/.kube/config

# Deploy pod
kubectl apply -f pod.yaml

# Monitor
kubectl logs -f chaos-test
```

## Related Files

- `Dockerfile` — Container image definition
- `.dockerignore` — Files to exclude from image
- `docker-compose.yml` — Multi-container orchestration
- `requirements/` — Python dependencies (installed in image)

## Quick Reference

| Task | Command |
|------|---------|
| Build image | `podman build -t chaos-test:latest .` |
| Run tests | `podman run --rm chaos-test:latest` |
| Run with config | `podman run --rm -e NAMESPACE=... chaos-test:latest` |
| Interactive shell | `podman run -it --rm chaos-test:latest bash` |
| View logs | `podman-compose logs -f` |
| Stop all containers | `podman-compose down` |
| View image info | `podman inspect chaos-test:latest` |
| View image size | `podman images chaos-test` |

## Next Steps

1. **Build image**: `podman build -t chaos-test:latest .`
2. **Test locally**: `podman run --rm chaos-test:latest`
3. **Configure**: Add environment variables
4. **Deploy**: Push to registry and deploy to Kubernetes
5. **Monitor**: Check logs and test results

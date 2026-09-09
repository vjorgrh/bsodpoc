# Podman Quick Start Guide

Complete step-by-step execution guide for running chaos tests with Podman.

## Prerequisites

```bash
# Install Podman (RedHat/CentOS/Fedora)
sudo dnf install podman podman-compose

# Or on Debian/Ubuntu
sudo apt install podman podman-compose

# Verify installation
podman --version
podman-compose --version
```

## Quick Start (5 Steps)

### STEP 1: Build the Image

```bash
cd /path/to/bsodpoc

podman build -t chaos-test:latest .
```

**Expected output:**
```
[1/15] STEP 1: FROM python:3.11-slim AS base
...
[2/15] STEP 15: COMMIT chaos-test:latest
--> sha256:abc123def456...
Successfully built chaos-test:latest
```

**Time:** ~2-3 minutes (first time), ~10 seconds (cached)

---

### STEP 2: Verify Image

```bash
podman images chaos-test
```

**Expected output:**
```
REPOSITORY       TAG       IMAGE ID      CREATED        SIZE
chaos-test       latest    abc123def456  2 minutes ago   150MB
```

---

### STEP 3a: Run with Defaults

```bash
podman run --rm chaos-test:latest
```

**What it does:**
- Uses defaults: NAMESPACE=windows-bsod, TARGET_NAME=win2022-vm-hjoshi1
- Runs: `pytest tests/ -v`
- Takes ~2 minutes

---

### STEP 3b: Run with Custom Configuration (RECOMMENDED)

```bash
podman run --rm \
  -e NAMESPACE=windows-bsod \
  -e TARGET_NAME=win2022-vm-hjoshi1 \
  chaos-test:latest \
  tests/test_chaos.py -v --cleanup-all
```

**What it does:**
- Override environment variables
- Run specific test file with cleanup
- Takes ~5 minutes, frees ~310MB

---

### STEP 3c: Run with Kubernetes Access

```bash
podman run --rm \
  -v ~/.kube/config:/root/.kube/config:ro \
  -e NAMESPACE=windows-bsod \
  -e TARGET_NAME=win2022-vm-hjoshi1 \
  chaos-test:latest
```

**What it does:**
- Mount kubeconfig for K8s API access
- Tests can interact with Kubernetes
- Must have valid kubeconfig at ~/.kube/config

---

### STEP 4: Interactive Debugging (Optional)

```bash
podman run -it --rm chaos-test:latest bash
```

**Now inside container:**
```bash
# Run tests manually
pytest tests/test_chaos.py -v

# Check configuration
python -c "from fixtures.config import get_config; cfg = get_config(); print(cfg.get_config_summary())"

# View installed packages
pip list

# Exit
exit
```

---

### STEP 5: Docker Compose (Multiple Targets)

```bash
# Build via docker-compose
podman-compose build

# Run all services
podman-compose up

# Or run specific service
podman-compose run chaos-vm
```

---

## Common Commands Reference

| Task | Command |
|------|---------|
| **Build** | `podman build -t chaos-test:latest .` |
| **Run default** | `podman run --rm chaos-test:latest` |
| **Run with config** | `podman run --rm -e NAMESPACE=... -e TARGET_NAME=... chaos-test:latest` |
| **Run with cleanup** | `podman run --rm -e NAMESPACE=... chaos-test:latest tests/test_chaos.py -v --cleanup-all` |
| **Interactive shell** | `podman run -it --rm chaos-test:latest bash` |
| **With K8s access** | `podman run --rm -v ~/.kube/config:/root/.kube/config:ro chaos-test:latest` |
| **View logs** | `podman-compose logs -f` |
| **Stop containers** | `podman-compose down` |
| **List images** | `podman images chaos-test` |
| **View image size** | `podman inspect chaos-test:latest --format='{{.Size}}'` |

---

## Configuration Cheat Sheet

### Environment Variables

```bash
NAMESPACE=windows-bsod         # Kubernetes namespace
TARGET_NAME=win2022-vm-hjoshi1 # Target resource (VM, benchmark, etc)
TARGET_TYPE=vm                 # Documentation (vm, benchmark, pod)
```

### Set via different methods:

**Method 1: CLI `-e` flag**
```bash
podman run --rm -e NAMESPACE=staging-vms -e TARGET_NAME=staging-vm-01 chaos-test:latest
```

**Method 2: Environment file**
```bash
# Create env.prod
echo "NAMESPACE=prod-vms" > env.prod
echo "TARGET_NAME=prod-win-01" >> env.prod
echo "TARGET_TYPE=vm" >> env.prod

# Use it
podman run --rm --env-file env.prod chaos-test:latest
```

**Method 3: Docker Compose**
Edit `docker-compose.yml`:
```yaml
services:
  chaos-vm:
    environment:
      NAMESPACE: staging-vms
      TARGET_NAME: staging-vm-01
      TARGET_TYPE: vm
```

---

## Real-World Examples

### Example 1: Quick Test Run

```bash
# Build once
podman build -t chaos-test:latest .

# Run tests
podman run --rm chaos-test:latest tests/test_chaos.py -v
```

### Example 2: Production Testing (Multiple VMs)

```bash
#!/bin/bash
# Save as test-all.sh

NAMESPACE="prod-vms"
TARGETS=("prod-win-01" "prod-win-02" "prod-linux-01")

for TARGET in "${TARGETS[@]}"; do
  echo "Testing $TARGET..."
  podman run --rm \
    -v ~/.kube/config:/root/.kube/config:ro \
    -e NAMESPACE=$NAMESPACE \
    -e TARGET_NAME=$TARGET \
    -e TARGET_TYPE=vm \
    chaos-test:latest \
    tests/test_chaos.py -v --cleanup-all
  
  echo "✅ $TARGET complete"
  echo "---"
done
```

Run it:
```bash
bash test-all.sh
```

### Example 3: Development Mode

```bash
# Mount entire project for live development
podman run -it --rm \
  -v $PWD:/app \
  -v ~/.kube/config:/root/.kube/config:ro \
  chaos-test:latest \
  bash

# Inside container
root@xxx:/app# pytest tests/ -v
root@xxx:/app# # Edit code in IDE, re-run pytest
```

### Example 4: Benchmark Testing

```bash
podman run --rm \
  -e NAMESPACE=benchmark-ns \
  -e TARGET_NAME=benchmark-runner-01 \
  -e TARGET_TYPE=benchmark \
  chaos-test:latest \
  tests/test_benchmark.py -v --cleanup-all
```

---

## Troubleshooting

### Issue: "Cannot connect to Kubernetes API"

**Solution:** Mount kubeconfig
```bash
podman run --rm \
  -v ~/.kube/config:/root/.kube/config:ro \
  chaos-test:latest
```

### Issue: Tests timeout or hang

**Solution:** Run in interactive mode to debug
```bash
podman run -it --rm chaos-test:latest bash
# Inside: pytest tests/test_chaos.py -vv
```

### Issue: Image build fails

**Solution:** Clear cache and rebuild
```bash
podman build --no-cache -t chaos-test:latest .
```

### Issue: Container runs out of memory

**Solution:** Set resource limits
```bash
podman run --rm \
  --memory 512m \
  --cpus 2 \
  chaos-test:latest
```

---

## Performance Tips

### Cache between runs:
```bash
# Avoid rebuilding (reuse image)
podman run --rm chaos-test:latest tests/test_chaos.py -v

# Same for multiple runs - image is cached
podman run --rm -e TARGET_NAME=vm-1 chaos-test:latest tests/test_chaos.py -v
podman run --rm -e TARGET_NAME=vm-2 chaos-test:latest tests/test_chaos.py -v
```

### Parallel execution:
```bash
#!/bin/bash
# Run multiple containers in parallel

podman run --rm -e TARGET_NAME=vm-1 chaos-test:latest tests/test_chaos.py -v &
podman run --rm -e TARGET_NAME=vm-2 chaos-test:latest tests/test_chaos.py -v &
podman run --rm -e TARGET_NAME=vm-3 chaos-test:latest tests/test_chaos.py -v &

wait  # Wait for all to complete
```

### Use docker-compose for orchestration:
```bash
podman-compose up  # Runs all services efficiently
```

---

## Next Steps

1. **Build:** `podman build -t chaos-test:latest .`
2. **Test:** `podman run --rm chaos-test:latest`
3. **Configure:** Add `-e` flags for your environment
4. **Automate:** Create bash scripts for batch testing
5. **Deploy:** Push to registry and use in Kubernetes

---

## File Reference

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image definition |
| `.dockerignore` | Files excluded from image |
| `docker-compose.yml` | Multi-container orchestration |
| `docs/DOCKER-PODMAN.md` | Detailed documentation |
| `PODMAN-QUICK-START.md` | This file |

---

## Support

For issues, see `docs/DOCKER-PODMAN.md` for comprehensive troubleshooting guide.

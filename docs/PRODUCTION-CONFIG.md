# Production-Grade Configuration (Generic & Scalable)

This document describes the production-grade configuration system using **generic environment variables** that work with any target type (VM, benchmark runner, pod, etc) and any namespace.

## Overview

The configuration system is **completely generic and production-ready**:

- **No hardcoded values** in code
- **Generic variable names** (NAMESPACE, TARGET_NAME, TARGET_TYPE)
- **Supports any target type** (VM, benchmark runner, pod, container, etc)
- **Works with any namespace**
- **CLI option override** support
- **Caching** for performance
- **Backwards compatible**

## Generic Environment Variables

| Variable | Example | Default | Purpose |
|----------|---------|---------|---------|
| `NAMESPACE` | `windows-bsod` | `windows-bsod` | Kubernetes namespace |
| `TARGET_NAME` | `win2022-vm-hjoshi1` | `win2022-vm-hjoshi1` | Target resource (VM, benchmark, pod, etc) |
| `TARGET_TYPE` | `vm` | Not set | Documentation: target type |

## Three Ways to Configure

### Method 1: Environment Variables (Recommended for CI/CD)

```bash
# Set environment variables
export NAMESPACE=windows-bsod
export TARGET_NAME=win2022-vm-hjoshi1
export TARGET_TYPE=vm

# Run pytest (uses env vars automatically)
pytest tests/test_chaos.py -v
```

### Method 2: CLI Options (Recommended for local testing)

```bash
# Override with CLI options (highest priority)
pytest tests/test_chaos.py -v \
  --namespace windows-bsod \
  --target-name win2022-vm-hjoshi1 \
  --target-type vm
```

### Method 3: Mix Both (CLI overrides env vars)

```bash
# Set default env vars
export NAMESPACE=windows-bsod
export TARGET_NAME=win2022-vm-hjoshi1

# Override specific values with CLI
pytest tests/test_chaos.py -v --target-name different-vm
# Uses: namespace=windows-bsod (from env), target=different-vm (from CLI)
```

## Configuration Priority Order

**Highest to Lowest:**

1. **CLI options** (`--namespace`, `--target-name`, `--target-type`)
2. **Environment variables** (`NAMESPACE`, `TARGET_NAME`, `TARGET_TYPE`)
3. **Code defaults** (windows-bsod, win2022-vm-hjoshi1, not set)

## Usage Examples

### Run Chaos Tests Against Different Targets

```bash
# VM in windows-bsod namespace
pytest tests/test_chaos.py -v --namespace windows-bsod --target-name win2022-vm-hjoshi1

# Different VM
pytest tests/test_chaos.py -v --target-name rhel9-vm

# Different namespace
pytest tests/test_chaos.py -v --namespace staging-vms
```

### Run Benchmark Tests

```bash
# Benchmark runner
pytest tests/test_benchmark.py -v \
  --namespace benchmark-ns \
  --target-name benchmark-runner-01 \
  --target-type benchmark
```

### Production Scenarios

```bash
# Testing VM 1
NAMESPACE=prod-vms TARGET_NAME=prod-win-01 TARGET_TYPE=vm pytest tests/ -v --cleanup-all

# Testing VM 2
NAMESPACE=prod-vms TARGET_NAME=prod-win-02 TARGET_TYPE=vm pytest tests/ -v --cleanup-all

# Testing benchmark runner
NAMESPACE=prod-bench TARGET_NAME=benchmark-prod-01 TARGET_TYPE=benchmark pytest tests/ -v
```

### Batch Testing Multiple Targets

```bash
#!/bin/bash
# Test multiple targets in production

TARGETS=("prod-win-01:vm" "prod-linux-01:pod" "benchmark-01:benchmark")
NAMESPACE="prod-targets"

for TARGET_INFO in "${TARGETS[@]}"; do
  TARGET_NAME="${TARGET_INFO%:*}"
  TARGET_TYPE="${TARGET_INFO#*:}"
  
  echo "Testing $TARGET_NAME ($TARGET_TYPE)..."
  NAMESPACE=$NAMESPACE \
  TARGET_NAME=$TARGET_NAME \
  TARGET_TYPE=$TARGET_TYPE \
  pytest tests/ -v --cleanup-all
done
```

## Implementation

### Configuration Engine (fixtures/config.py)

```python
from fixtures.config import get_config, get_namespace, get_target_name, get_target_type

# Get config instance
config = get_config()
ns = config.get_namespace()        # "windows-bsod"
target = config.get_target_name()  # "win2022-vm-hjoshi1"
target_type = config.get_target_type()  # "vm"

# Or use helper functions
from fixtures.common import get_namespace, get_target_name, get_target_type

ns = get_namespace()
target = get_target_name()
t_type = get_target_type()

# Backwards compatibility alias
from fixtures.common import get_vm_name
vm = get_vm_name()  # Same as get_target_name()
```

### How It Works

1. **CLI options are applied first** (via `pytest_configure` hook)
   - Sets environment variables before test collection
   - Ensures tests see the CLI values

2. **Environment variables are read** (via `get_namespace()` / `get_target_name()`)
   - Uses `@lru_cache` decorator for performance
   - Reads env var only once per pytest session
   - Falls back to code defaults if env var not set

3. **Tests use the configured values**
   - Pytest markers get namespace/target from configuration
   - Tests run against configured target

## Architecture

```
CLI options (--namespace, --target-name, --target-type)
  ↓
pytest_configure (sets env vars from CLI)
  ↓
Test collection
  ↓
get_namespace() / get_target_name() / get_target_type()
(read env vars with @lru_cache caching)
  ↓
Tests run with configured namespace/target
```

## Setting Environment Variables Persistently

### In shell config (.bashrc, .zshrc)

```bash
export NAMESPACE=windows-bsod
export TARGET_NAME=win2022-vm-hjoshi1
export TARGET_TYPE=vm
```

### In .env file (with `direnv`)

```bash
export NAMESPACE=windows-bsod
export TARGET_NAME=win2022-vm-hjoshi1
export TARGET_TYPE=vm
```

Then:
```bash
direnv allow
```

### In CI/CD (GitHub Actions)

```yaml
env:
  NAMESPACE: windows-bsod
  TARGET_NAME: win2022-vm-hjoshi1
  TARGET_TYPE: vm
```

### In CI/CD (GitLab CI)

```yaml
variables:
  NAMESPACE: windows-bsod
  TARGET_NAME: win2022-vm-hjoshi1
  TARGET_TYPE: vm
```

## Verifying Configuration

Check which values are configured:

```bash
# Python check
python -c "
from fixtures.config import get_config
cfg = get_config()
print(f'Namespace: {cfg.get_namespace()}')
print(f'Target: {cfg.get_target_name()}')
print(f'Type: {cfg.get_target_type()}')
print()
print(cfg.get_config_summary())
"
```

Or check environment variables:

```bash
echo "NAMESPACE: $NAMESPACE"
echo "TARGET_NAME: $TARGET_NAME"
echo "TARGET_TYPE: $TARGET_TYPE"
```

## Scaling to Production

This approach scales perfectly for any production scenario:

### Multiple target types in same namespace

```bash
# Chaos test on VM
pytest tests/test_chaos.py -v --namespace prod --target-name vm-01 --target-type vm

# Benchmark test on benchmark runner
pytest tests/test_benchmark.py -v --namespace prod --target-name benchmark-01 --target-type benchmark

# Stability test on pod
pytest tests/test_stability.py -v --namespace prod --target-name pod-01 --target-type pod
```

### Multiple namespaces with multiple targets

```bash
for NS in dev staging prod; do
  for TARGET in target-01 target-02 target-03; do
    NAMESPACE=$NS TARGET_NAME=$TARGET pytest tests/ -v
  done
done
```

### Tomorrow when you have N VMs, N namespaces, N target types

```bash
# Just change environment variables - NO CODE CHANGES!
pytest tests/ -v --namespace new-namespace --target-name new-vm-name
```

## Backwards Compatibility

Old code still works:

```python
from fixtures.common import DEFAULT_NAMESPACE, get_vm_name, get_namespace

# Use them as before
namespace = get_namespace()    # Now reads NAMESPACE env var
vm_name = get_vm_name()        # Alias for get_target_name()
```

New code can use generic names:

```python
from fixtures.config import get_target_name, get_target_type

target = get_target_name()     # Works for any target type
t_type = get_target_type()     # Identifies what kind of target
```

## Default Values

If no environment variables or CLI options are provided:

- **NAMESPACE**: `windows-bsod`
- **TARGET_NAME**: `win2022-vm-hjoshi1`
- **TARGET_TYPE**: (not set)

Change these in `fixtures/config.py` if needed:

```python
def get_namespace(self) -> str:
    return os.getenv("NAMESPACE", "windows-bsod")  # ← Change here

def get_target_name(self) -> str:
    return os.getenv("TARGET_NAME", "win2022-vm-hjoshi1")  # ← Change here
```

## Generic Variable Names

The variables are completely **generic** and not tied to any specific use case:

- **NAMESPACE** — Any Kubernetes namespace (vm, benchmark, pod, etc)
- **TARGET_NAME** — Any target resource (can be VM, benchmark runner, pod, container, etc)
- **TARGET_TYPE** — Optional documentation field (vm, benchmark, pod, container, etc)

This means:

✅ Works with chaos testing (VM targets)  
✅ Works with benchmark testing (benchmark runner targets)  
✅ Works with pod testing  
✅ Works with any future target type  
✅ No code changes needed to support new target types  

## Related Files

- `fixtures/config.py` — Configuration engine with generic variables
- `fixtures/common.py` — Backwards-compatible helpers
- `scripts/pytest_automation.py` — CLI option handlers
- `tests/test_chaos.py` — Tests using configuration
- `conftest.py` — Pytest entry point

## FAQ

**Q: Why not use KRKN_* variables?**  
A: KRKN_* is too specific. The system now works for any test type (chaos, benchmark, stability, etc).

**Q: What's the difference between TARGET_NAME and TARGET_TYPE?**  
A: TARGET_NAME is the actual resource name (win2022-vm-01), TARGET_TYPE is documentation (vm, benchmark, pod).

**Q: Can I skip TARGET_TYPE?**  
A: Yes, it's optional. It's just for documentation/logging.

**Q: How do I use this for benchmark runner?**  
A: `pytest tests/test_benchmark.py -v --namespace benchmark-ns --target-name benchmark-01 --target-type benchmark`

**Q: Can I mix target types in same test run?**  
A: Each pytest invocation uses one target. Run multiple times for multiple targets.

**Q: What if I need more configuration options?**  
A: Add them to `fixtures/config.py` as new environment variables with defaults.

**Q: Does caching cause issues if env vars change?**  
A: No. Each pytest session has fresh caching. For different configs, run pytest again.

## Example: Tomorrow with 100 VMs in Production

No code changes needed! Just use environment variables:

```bash
# Test all 100 production VMs
for i in {1..100}; do
  NAMESPACE=prod-vms \
  TARGET_NAME=prod-vm-$i \
  TARGET_TYPE=vm \
  pytest tests/test_chaos.py -v --cleanup-all
done
```

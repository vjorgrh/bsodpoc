# Environment Configuration for Tests

## Overview

The test suite now supports configuring the Kubernetes namespace and VM name via environment variables, making it easy to run tests against different clusters and VMs without modifying code.

## Configuration Methods

### Method 1: Command-Line Options (Recommended)
The easiest way — pass namespace and VM name directly to pytest:

**--krkn-namespace** — Kubernetes namespace  
**--krkn-vm-name** — Target VM name

```bash
pytest tests/test_chaos.py -v --krkn-namespace windows-bsod --krkn-vm-name win2022-vm-hjoshi1
```

### Method 2: Environment Variables
Set environment variables before running pytest:

**KRKN_NAMESPACE** — Kubernetes namespace (default: `windows-bsod`)  
**KRKN_VM_NAME** — Target VM name (default: `win2022-vm-hjoshi1`)

```bash
export KRKN_NAMESPACE=my-namespace
export KRKN_VM_NAME=my-vm-name
pytest tests/test_chaos.py -v
```

### Method 3: Constants in Code
Fallback to hardcoded defaults in `fixtures/common.py`:

```python
DEFAULT_NAMESPACE = "test123"  # Change this to your cluster
```

## Priority Order
When multiple configuration methods are used, they're applied in this order (highest to lowest priority):

1. **CLI options** (`--krkn-namespace`, `--krkn-vm-name`) ← Use this if you want to override
2. **Environment variables** (`KRKN_NAMESPACE`, `KRKN_VM_NAME`)
3. **Code defaults** (in `fixtures/common.py`)

## Usage Examples

### Quick: Pass namespace via CLI (Recommended)
```bash
pytest tests/test_chaos.py -v --krkn-namespace windows-bsod
```

### Quick: Pass both namespace and VM name via CLI
```bash
pytest tests/test_chaos.py -v --krkn-namespace windows-bsod --krkn-vm-name win2022-vm-hjoshi1
```

### With cleanup enabled
```bash
pytest tests/test_chaos.py -v --krkn-namespace windows-bsod --cleanup-all
```

### Using environment variables
```bash
export KRKN_NAMESPACE=prod-vms
export KRKN_VM_NAME=win2022-prod
pytest tests/test_chaos.py -v
```

### Mixed: CLI overrides environment variables
```bash
export KRKN_NAMESPACE=default-ns
pytest tests/test_chaos.py -v --krkn-namespace custom-ns  # CLI wins!
```

### Run with all defaults
```bash
pytest tests/test_chaos.py -v  # Uses test123 + win2022-vm-hjoshi1
```

## Implementation Details

### Pytest Hooks
**File:** `scripts/pytest_automation.py`

- `pytest_addoption()` — Registers `--krkn-namespace` and `--krkn-vm-name` CLI options
- `pytest_configure()` — Early hook that applies CLI options to environment variables before test collection

**File:** `conftest.py`

- Imports all automation hooks from `scripts/pytest_automation.py`

### Configuration Helpers
**File:** `fixtures/common.py`

- `get_namespace()` — Returns `KRKN_NAMESPACE` env var or defaults to `windows-bsod`
- `get_vm_name()` — Returns `KRKN_VM_NAME` env var or defaults to `win2022-vm-hjoshi1`
- `execOnNode()` — Helper function to execute commands on worker nodes

**File:** `tests/test_chaos.py`

- Imports: `from fixtures.common import get_namespace, get_vm_name, execOnNode`
- Uses `DEFAULT_NAMESPACE = get_namespace()` in pytest markers
- Uses `DEFAULT_VM_NAME = get_vm_name()` in pytest markers
- Dynamic label selector: `f"vm.kubevirt.io/name={DEFAULT_VM_NAME}"`

## Setting Environment Variables Persistently

### In `.bashrc` or `.zshrc`
```bash
export KRKN_NAMESPACE=windows-bsod
export KRKN_VM_NAME=win2022-vm-hjoshi1
```

### In a `.env` file (with `direnv`)
```bash
export KRKN_NAMESPACE=windows-bsod
export KRKN_VM_NAME=win2022-vm-hjoshi1
```

Then load it:
```bash
direnv allow
```

### In CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
```yaml
env:
  KRKN_NAMESPACE: windows-bsod
  KRKN_VM_NAME: win2022-vm-hjoshi1
```

## Verifying Configuration

Check which namespace and VM name are being used:

```bash
python -c "
from fixtures.common import get_namespace, get_vm_name
print(f'Namespace: {get_namespace()}')
print(f'VM Name: {get_vm_name()}')
"
```

Or with environment variables:
```bash
KRKN_NAMESPACE=my-ns KRKN_VM_NAME=my-vm python -c "
from fixtures.common import get_namespace, get_vm_name
print(f'Namespace: {get_namespace()}')
print(f'VM Name: {get_vm_name()}')
"
```

## Common Use Cases

### Multi-tenant cluster testing
```bash
# Test tenant A
KRKN_NAMESPACE=tenant-a-vms pytest tests/test_chaos.py -v

# Test tenant B
KRKN_NAMESPACE=tenant-b-vms pytest tests/test_chaos.py -v
```

### Testing different VM configurations
```bash
# Windows Server 2022
KRKN_VM_NAME=win2022-vm pytest tests/test_chaos.py -v

# Windows Server 2019
KRKN_VM_NAME=win2019-vm pytest tests/test_chaos.py -v
```

### CI/CD pipeline with matrix strategy
```yaml
strategy:
  matrix:
    namespace: [dev, staging, prod]
    vm: [win2022, win2019, rhel9]
env:
  KRKN_NAMESPACE: ${{ matrix.namespace }}-vms
  KRKN_VM_NAME: ${{ matrix.vm }}-vm
```

## Related Files

- `fixtures/common.py` — Helper functions for environment-based configuration
- `tests/test_chaos.py` — Chaos tests using environment-based config
- `fixtures/krknlib_fixtures.py` — Fixture that uses the configured namespace/VM

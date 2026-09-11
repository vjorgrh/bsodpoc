# Automated Cleanup Documentation

## Overview

The test suite automatically cleans up **all test-created Kubernetes resources** (VMs and DataVolumes) after each test run, regardless of pass/fail status.

## What Gets Cleaned Up

### Automatically Deleted (Test-Created Resources)

**Virtual Machines (VMs):**
- `win2022-vm-clone-*` (from clone tests)
- `win2022-vm-scale-*` (from scaling tests)
- `win2022-vm-multi-*` (from multi-VM tests)
- `win2022-vm-delete-*` (from deletion tests)
- `win2022-vm-lifecycle-*` (from lifecycle tests)

**DataVolumes (DVs):**
- `win2022-dv-clone-*` (from clone tests)
- `win2022-dv-scale-*` (from scaling tests)
- `win2022-dv-multi-*` (from multi-DV tests)
- `win2022-dv-delete-*` (from deletion tests)
- `win2022-dv-lifecycle-*` (from lifecycle tests)

### Preserved (User VMs - NOT Deleted)

These permanent VMs are **protected and never deleted**:
- `win2022-vm-hjoshi1` (primary test VM)
- `win2022-vm-vvijay1` (user VM)

## How Cleanup Works

### When Cleanup Happens

**Automatic cleanup runs:**
1. **Before tests start** - Removes any leftover resources from previous runs
2. **After tests complete** - Removes all test-created resources
3. **On test pass OR fail** - Cleanup always happens (no manual intervention needed)

### Cleanup Mechanism

The cleanup is implemented in `scripts/pytest_automation.py`:

```python
def cleanup_kubernetes_resources(namespace: str = "windows-bsod") -> bool:
    """
    Clean up only test-created Kubernetes resources (VMs and DVs).
    Preserves user VMs like 'win2022-vm-hjoshi1' and 'win2022-vm-vvijay1'.
    """
    # Gets list of test-created resource patterns
    test_resource_patterns = [
        "win2022-vm-clone",    # VM clones
        "win2022-vm-scale",    # Scaled VMs
        "win2022-vm-multi",    # Multi-VM tests
        "win2022-vm-delete",   # Deletion tests
        "win2022-vm-lifecycle",# Lifecycle tests
        "win2022-dv-clone",    # DV clones
        "win2022-dv-scale",    # Scaled DVs
        "win2022-dv-multi",    # Multi-DV tests
        "win2022-dv-delete",   # Deletion tests
        "win2022-dv-lifecycle",# Lifecycle tests
    ]
    
    # Queries cluster for matching resources
    # Deletes each matching resource
    # Logs results
```

### Integration with pytest

The cleanup is triggered in the `pytest_sessionfinish()` hook:

```python
def pytest_sessionfinish(session, exitstatus: int) -> None:
    """PHASE 4: Auto-cleanup (always runs)"""
    namespace = os.environ.get("NAMESPACE", "windows-bsod")
    cleanup_kubernetes_resources(namespace)  # ALWAYS runs
```

## Usage

### Run Tests with Auto-Cleanup

```bash
# Run all tests - cleanup happens automatically
podman-compose run --rm all-tests

# Run specific test suite
podman-compose run --rm crud-test      # CRUD tests + cleanup
podman-compose run --rm chaos-test     # Chaos tests + cleanup
podman-compose run --rm vut-test       # VUT tests + cleanup
```

### Custom Namespace

```bash
# Override namespace (cleanup still works)
NAMESPACE=custom-ns podman-compose run --rm all-tests
```

## Manual Cleanup (If Needed)

### Delete All Test-Created Resources

```bash
# Delete all test VMs
oc delete vm -n windows-bsod \
  win2022-vm-clone-1 \
  win2022-vm-scale-cpu-1 \
  win2022-vm-scale-mem-1 \
  win2022-vm-scale-both-1 \
  win2022-vm-multi-1 \
  win2022-vm-multi-2 \
  win2022-vm-multi-3 \
  --ignore-not-found=true

# Delete all test DVs
oc delete dv -n windows-bsod \
  win2022-dv-clone-1 \
  --ignore-not-found=true
```

### Delete All Non-Running Resources (Dynamic)

```bash
# Delete all VMs that are not in Running state
oc delete vm -n windows-bsod \
  $(oc get vm -n windows-bsod -o jsonpath='{range .items[?(@.status.ready!=true)]}{.metadata.name}{" "}{end}') \
  --ignore-not-found=true
```

### Check What Will Be Deleted

```bash
# List all test-created VMs
oc get vm -n windows-bsod -o wide | grep -E "clone|scale|multi|delete|lifecycle"

# List all test-created DVs
oc get dv -n windows-bsod -o wide | grep -E "clone|scale|multi|delete|lifecycle"
```

## Troubleshooting

### Cleanup Not Working?

**Check 1: kubeconfig access**
```bash
# Verify kubeconfig is readable
cat ~/.kube/config > /dev/null && echo "✅ kubeconfig OK" || echo "❌ kubeconfig error"
```

**Check 2: Cluster connectivity**
```bash
# Test cluster access
oc get nodes && echo "✅ Cluster accessible" || echo "❌ Cluster error"
```

**Check 3: Namespace exists**
```bash
# Verify namespace
oc get namespace windows-bsod && echo "✅ Namespace OK" || echo "❌ Namespace error"
```

**Check 4: Manual cleanup if auto-cleanup fails**
```bash
# Use the manual commands above to clean up manually
```

### Persistent VMs Accidentally Deleted?

If `win2022-vm-hjoshi1` or `win2022-vm-vvijay1` were accidentally deleted:

1. Restore from backup or recreate manually
2. The cleanup script is designed to protect these - if they were deleted, it's a separate issue
3. Report the incident for investigation

## Implementation Details

### File: `scripts/pytest_automation.py`

**Function:** `cleanup_kubernetes_resources(namespace: str) -> bool`
- **Location:** Lines 53-139
- **Called from:** `pytest_sessionfinish()` hook (line 446)
- **Timing:** Always runs after pytest completes
- **Returns:** True if cleanup succeeded, False if errors occurred

### Resource Pattern Matching

Cleanup uses **exact prefix matching** to identify test-created resources:

```
VM Patterns:
  win2022-vm-clone       → matches: win2022-vm-clone-1, win2022-vm-clone-test, etc.
  win2022-vm-scale       → matches: win2022-vm-scale-cpu-1, win2022-vm-scale-mem-1, etc.
  win2022-vm-multi       → matches: win2022-vm-multi-1, win2022-vm-multi-2, etc.

DV Patterns:
  win2022-dv-clone       → matches: win2022-dv-clone-1, etc.
  win2022-dv-scale       → matches: win2022-dv-scale-cpu-1, etc.
  win2022-dv-multi       → matches: win2022-dv-multi-1, etc.
```

### Protected Resources

These resources are **explicitly protected** from deletion:

```
Permanent VMs:
  - win2022-vm-hjoshi1   (Primary test VM)
  - win2022-vm-vvijay1   (User VM)
```

These are not matched by any test pattern, so they're never deleted.

## Best Practices

✅ **DO:**
- Let auto-cleanup run after tests
- Monitor cleanup logs for errors
- Preserve permanent VMs (hjoshi1, vvijay1)
- Use custom namespaces for isolation if needed

❌ **DON'T:**
- Manually delete resources before cleanup completes
- Create user VMs with test-pattern names (e.g., `win2022-vm-clone-myvm`)
- Assume cleanup runs on test failure (it does, but verify logs)
- Delete permanent VMs unless intentional

## Summary

| Aspect | Details |
|--------|---------|
| **When** | Before and after each test run |
| **What** | Test-created VMs and DVs matching patterns |
| **What's preserved** | User VMs: hjoshi1, vvijay1 |
| **Trigger** | pytest `pytest_sessionfinish()` hook (always) |
| **Manual override** | See manual cleanup commands above |
| **Logs** | Check pytest output for cleanup messages |

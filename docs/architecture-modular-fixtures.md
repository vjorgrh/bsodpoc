# bsodpoc Modular Fixture Architecture Analysis

**Version:** Current main branch (d3edf76)  
**Date:** 2026-09-08  
**Status:** ✅ Modular fixture approach implemented

---

## Executive Summary

The bsodpoc repository has successfully **evolved from monolithic conftest.py to a modular fixture library**. Fixtures are now organized by concern:

```
conftest.py                          (simple plugin loader)
├─ fixtures/vm_fixtures.py          (VM creation/teardown)
├─ fixtures/krknlib_fixtures.py      (krkn-lib chaos client)
├─ fixtures/tunnel_fixtures.py       (SSH tunnel factory)
├─ fixtures/benchmark_runner_fixtures.py  (benchmark-runner integration)
└─ fixtures/common.py                (shared constants)
```

---

## Architecture Pattern

### Old Pattern (Single conftest.py)

```python
# conftest.py
@pytest.fixture
def vm_create():
    ...

@pytest.fixture
def krknChaos():
    ...

@pytest.fixture
def ssh_tunnel_connection():
    ...
```

**Problems:**
- Single 150+ line file gets cluttered
- Hard to reuse fixtures across projects
- Mixing concerns (VM setup, krkn client, SSH tunnels)
- Difficult to test fixture code itself

---

### New Pattern (Modular Fixtures)

```python
# conftest.py (6 lines)
pytest_plugins = [
    "fixtures.vm_fixtures",
    "fixtures.krknlib_fixtures",
    "fixtures.tunnel_fixtures",
    "fixtures.benchmark_runner_fixtures",
]

# fixtures/vm_fixtures.py (62 lines - single responsibility)
# fixtures/krknlib_fixtures.py (61 lines - chaos only)
# fixtures/tunnel_fixtures.py (51 lines - SSH only)
# fixtures/benchmark_runner_fixtures.py (109 lines - benchmark-runner only)
```

**Benefits:**
- ✅ Separation of concerns
- ✅ Testable fixture code
- ✅ Reusable across projects
- ✅ Easy to add/remove fixture modules
- ✅ Clear dependency tree

---

## Fixture Modules Breakdown

### 1. fixtures/common.py

**Purpose:** Shared constants and defaults

```python
DEFAULT_NAMESPACE = "windows-bsod"
```

**Usage:** Imported by all fixture modules to avoid hardcoding namespace.

**Design:** Central configuration point — change once, affects all fixtures.

---

### 2. fixtures/vm_fixtures.py

**Fixture:** `vmCreate` (function scope)

**What it does:**
1. Creates N VMs from `config/vm-config-tlbflush-on.yaml`
2. Substitutes `${VM_NAME}` with generated names (`bsod-auto-NNN`)
3. Applies each to cluster via `oc apply`
4. Yields dict of `{vmName: CommandResult}` with status
5. **Teardown:** Deletes all VMs created

**Key Design:**
- **Factory pattern:** Accepts parameter `count` → creates N VMs
- **Parameter modes:** 
  - Bare int: `vm_create` with count=1
  - Tuple: `(count, namespace)` for custom namespace
- **Parametrization support:** Via `@pytest.mark.parametrize(..., indirect=True)`

**Example usage:**

```python
# Create 1 VM (default namespace)
def test_something(vmCreate):
    for vmName in vmCreate:
        print(vmName)  # "bsod-auto-742"

# Create 2 VMs (custom namespace)
@pytest.mark.parametrize("vmCreate", [(2, "custom-ns")], indirect=True)
def test_multi_vm(vmCreate):
    assert len(vmCreate) == 2
```

**Context:** None explicitly (but `yield` provides implicit context manager semantics)

---

### 3. fixtures/krknlib_fixtures.py

**Fixture:** `krknChaos` (function scope)

**What it does:**
1. Lazily imports `krkn_lib.k8s.KrknKubernetes`
2. Reads `@pytest.mark.krkn(...)` marker on test
3. Merges marker params with `KRKN_DEFAULTS`
4. Initializes krkn client from kubeconfig
5. Yields `KrknContext(client, params)` NamedTuple

**Key Design:**
- **Marker pattern:** Parameters declared in decorator, not code
- **Lazy import:** krkn-lib is optional (tests still collect if missing)
- **Defaults:** Centralized in `KRKN_DEFAULTS` dict
- **NamedTuple:** Type-safe context bundle

**KRKN_DEFAULTS:**
```python
{
    "namespace": "windows-bsod",
    "vmName": "hjoshi-win2022",
    "recoverTimeout": 300,
}
```

**Example usage:**

```python
@pytest.mark.krkn(recoverTimeout=600)  # Override default
def test_vm_chaos(krknChaos):
    client = krknChaos.client
    timeout = krknChaos.params["recoverTimeout"]  # 600 (from marker)
    vmName = krknChaos.params["vmName"]          # hjoshi-win2022 (default)
```

**Context:** None (stateless client, no cleanup needed)

---

### 4. fixtures/tunnel_fixtures.py

**Fixture 1:** `sshTunnelConnection` (function scope, factory pattern)

**What it does:**
1. Provides a factory function `_make(vmName, namespace)`
2. Each call creates a `VirtctlSshTunnel` and tracks it
3. **Teardown:** Closes all created tunnels

**Context:** Yes! Uses implicit context semantics with `yield`.

```python
@pytest.fixture
def sshTunnelConnection(request):
    tunnels = []
    
    def _make(vmName, namespace=DEFAULT_NAMESPACE):
        tunnel = VirtctlSshTunnel(...)
        tunnels.append(tunnel)
        return tunnel
    
    yield _make  # Factory function
    
    for tunnel in tunnels:
        tunnel.close()  # Cleanup
```

**Example usage:**

```python
def test_ssh(sshTunnelConnection):
    tunnel1 = sshTunnelConnection("hjoshi-win2022")
    tunnel2 = sshTunnelConnection("win2022-vm-vvijay1")
    
    tunnel1.runPowershell("Get-Date")  # Use tunnel
    
    # Cleanup happens automatically in teardown
```

**Fixture 2:** `vmWithTunnel` (composes two fixtures)

**What it does:**
- Combines `vmCreate` + `sshTunnelConnection`
- One tunnel per created VM
- Returns dict: `{vmName: tunnel}`

**Context:** Implicit (via composition)

```python
@pytest.fixture
def vmWithTunnel(vmCreate, sshTunnelConnection):
    return {vmName: sshTunnelConnection(vmName) for vmName in vmCreate}
```

---

### 5. fixtures/benchmark_runner_fixtures.py

**Purpose:** Integration with **benchmark-runner** (Red Hat's performance testing library)

**Context Manager Usage:** ✅ **YES! This is the best example.**

---

## ⭐ Context Manager Example: benchmark_runner_fixtures.py

### Fixture 1: `oc` (session scope)

```python
@pytest.fixture(scope="session")
def oc():
    """SingletonOCLogin logs in once per process."""
    from benchmark_runner.common.oc.oc import OC
    return OC(kubeadmin_password=os.environ["KUBEADMIN_PASSWORD"])
```

**No explicit context manager** — just returns an initialized client.

---

### Fixture 2: `windowsVM` (function scope, **with context manager**)

```python
@pytest.fixture
def windowsVM(oc):
    from benchmark_runner.main.temporary_environment_variables import TemporaryEnvironmentVariables
    from benchmark_runner.workloads.windows_vm import WindowsVM
    from benchmark_runner.workloads.workloads_operations import WorkloadsOperations
    
    with TemporaryEnvironmentVariables():  # ← CONTEXT MANAGER
        env = environment_variables.environment_variables_dict
        env['workload'] = 'windows_vm'
        env['run_type'] = 'test_ci'
        env['kubeadmin_password'] = os.environ["KUBEADMIN_PASSWORD"]
        env['windows_url'] = os.environ["WINDOWS_URL"]
        env['run_artifacts_path'] = tempfile.mkdtemp()
        
        vmops = WorkloadsOperations()
        vmops.initialize_workload()
        vm = WindowsVM()
        
        yield vm  # Test runs here
        
        # Cleanup: delete VM if still exists
        if oc.vm_exists(vm_name=vm._vm_name):
            oc.delete_vm_sync(vm_name=vm._vm_name)
```

**Key points:**

1. **`TemporaryEnvironmentVariables()`** — Context manager
   - Sets up environment (benchmark-runner config)
   - Restores original state on exit
   - Prevents cross-test pollution

2. **`with` statement** — Wraps the entire fixture setup
   - Guarantees cleanup even if `yield` test fails
   - Environment is automatically reset

3. **Fixture cleanup** after `yield`:
   - Best-effort VM deletion
   - Safe: checks if VM still exists before deleting

---

### Fixture 3: `windowsVMScale` (function scope, **with context manager**)

```python
@pytest.fixture
def windowsVMScale(oc):
    scale = int(os.environ.get("SCALE", "2"))
    workerNode0 = os.environ.get("WORKER_NODE_0")
    workerNode1 = os.environ.get("WORKER_NODE_1")
    
    scale_nodes = [workerNode0, workerNode1]
    dir_path = tempfile.mkdtemp()
    
    with TemporaryEnvironmentVariables():  # ← CONTEXT MANAGER
        env = environment_variables.environment_variables_dict
        env['workload'] = 'windows_vm_scale'
        env['scale'] = str(scale)
        env['scale_nodes'] = str(scale_nodes)
        env['threads_limit'] = os.environ.get("THREADS_LIMIT", "")
        env['bulk_sleep_time'] = os.environ.get("BULK_SLEEP_TIME", "30")
        
        vmops = WorkloadsOperations()
        vmops.initialize_workload()
        vm = WindowsVM()
        
        yield vm
        
        # Cleanup: delete all VMs (if delete_all was False)
        if not env.get('delete_all', True):
            for vm_num in range(scale * len(scale_nodes)):
                vm_name = f'{vm._workload_name}-{vm._trunc_uuid}-{vm_num}'
                if oc.vm_exists(vm_name=vm_name):
                    oc.delete_vm_sync(vm_name=vm_name)
```

**Why context manager?**
- benchmark-runner modifies global environment variables
- `TemporaryEnvironmentVariables()` ensures they're restored
- Multiple tests can run without interfering

---

## How `oc` is Used as Benchmark Runner

### Direct OC Client

```python
@pytest.fixture(scope="session")
def oc():
    from benchmark_runner.common.oc.oc import OC
    return OC(kubeadmin_password=os.environ["KUBEADMIN_PASSWORD"])
```

**This is NOT a context manager itself.** It's a **singleton** initialized once per test session:

- Login happens once (efficient)
- Cached for all tests
- Methods: `vm_exists()`, `delete_vm_sync()`, `delete_vm()`, etc.

### Benchmark-Runner WorkloadsOperations

```python
vmops = WorkloadsOperations()
vmops.initialize_workload()
```

**This internally:**
1. Reads environment dict
2. Initializes the correct workload (windows_vm, windows_vm_scale, etc.)
3. Uses the OC client to manage VMs on cluster

**Key design:** The `OC` fixture is **injected** as a dependency:

```python
def windowsVM(oc):  # ← Depends on oc fixture
    # vmops internally uses the oc client for operations
```

---

## Comparison: Three Approaches to Environment Setup

| Approach | Example | Cleanup | Context Manager |
|----------|---------|---------|---|
| **Fixture teardown** | `vmCreate` — `yield` then delete | After test | Implicit (via yield) |
| **Context manager** | `TemporaryEnvironmentVariables()` | On context exit | Explicit (with statement) |
| **Singleton fixture** | `oc` — session scope | After session | No (persistent) |

**Best practice:** Use **context manager inside fixture teardown** for guaranteed cleanup:

```python
@pytest.fixture
def my_fixture():
    with SomeContextManager():
        setup()
        yield resource
        # Context manager cleanup happens here automatically
```

---

## Fixture Dependency Tree

```
conftest.py (pytest_plugins loader)
    │
    ├─→ fixtures.vm_fixtures
    │   ├─ Imports: libs.command_runner, libs.yaml_parser, fixtures.common
    │   └─ Fixture: vmCreate
    │
    ├─→ fixtures.krknlib_fixtures
    │   ├─ Imports: fixtures.common, krkn_lib (lazy)
    │   └─ Fixture: krknChaos
    │
    ├─→ fixtures.tunnel_fixtures
    │   ├─ Imports: libs.command_runner, libs.ssh_tunnel, fixtures.common
    │   ├─ Fixture: sshTunnelConnection (factory)
    │   └─ Fixture: vmWithTunnel (composes vmCreate + sshTunnelConnection)
    │
    └─→ fixtures.benchmark_runner_fixtures
        ├─ Imports: benchmark_runner, tempfile, os
        ├─ Fixture: oc (session scope, singleton)
        ├─ Fixture: windowsVM (depends on oc, uses context manager)
        └─ Fixture: windowsVMScale (depends on oc, uses context manager)

Test modules can request any fixture:
    tests/test_chaos.py
        ├─ @pytest.mark.krkn(...) on test_vmSurvivesVirtLauncherKill
        └─ def test_vmSurvivesVirtLauncherKill(krknChaos):
```

---

## Scenario-Wise Fixture Design

### Test Scenario 1: Pod-Kill Recovery (test_chaos.py)

```python
@pytest.mark.krkn(
    vmName="hjoshi-win2022",
    namespace="windows-bsod",
    labelSelector="vm.kubevirt.io/name=hjoshi-win2022",
    recoverTimeout=300,
)
def test_vmSurvivesVirtLauncherKill(self, krknChaos):
    """Uses: krknChaos fixture + marker params."""
    client = krknChaos.client
    params = krknChaos.params
    ...
```

**Fixtures involved:** `krknChaos` (provides client + params)

**Context:** None (krkn-lib is stateless)

---

### Test Scenario 2: VM Creation with Tunnels (test_sample1.py)

```python
@pytest.mark.parametrize("vmCreate", [(2, "windows-bsod")], indirect=True)
def test_vm_create(vmCreate):
    """Uses: vmCreate fixture."""
    for vmName in vmCreate:
        print(vmName)
```

**Fixtures involved:** `vmCreate` (creates 2 VMs, cleans up after)

**Context:** Implicit (via yield)

---

### Test Scenario 3: Benchmark-Runner (hypothetical future)

```python
@pytest.mark.benchmark
def test_windows_vm_performance(windowsVM):
    """Uses: windowsVM fixture with context manager."""
    # Fixture setup:
    # 1. with TemporaryEnvironmentVariables() (context manager)
    # 2. Initialize benchmark-runner workload
    # 3. Yield vm
    
    # Test runs here with clean environment
    
    # Fixture teardown:
    # 1. Delete VM (cleanup)
    # 2. Context manager exits (environment restored)
```

**Fixtures involved:** `windowsVM` (provides VM, manages environment)

**Context:** Explicit (via `with` statement inside fixture)

---

## Key Architectural Decisions

### 1. **Plugin Registration** (conftest.py)

```python
pytest_plugins = [
    "fixtures.vm_fixtures",
    "fixtures.krknlib_fixtures",
    "fixtures.tunnel_fixtures",
    "fixtures.benchmark_runner_fixtures",
]
```

**Why:** Pytest's official way to load fixtures from external modules. Cleaner than importing directly.

---

### 2. **Factory Pattern** (sshTunnelConnection)

```python
@pytest.fixture
def sshTunnelConnection(request):
    tunnels = []
    def _make(vmName, namespace=DEFAULT_NAMESPACE):
        tunnel = VirtctlSshTunnel(...)
        tunnels.append(tunnel)
        return tunnel
    yield _make
    for tunnel in tunnels:
        tunnel.close()
```

**Why:** Tests can create 0, 1, or N tunnels. Cleanup handles all.

---

### 3. **Marker-Based Parametrization** (krknChaos)

```python
@pytest.mark.krkn(recoverTimeout=600)  # Declare params
def test_something(krknChaos):
    timeout = krknChaos.params["recoverTimeout"]  # Read params
```

**Why:** Parameters visible at test function top; reusable across tests; testable (params are just dicts).

---

### 4. **Context Manager Inside Fixture** (windowsVM)

```python
@pytest.fixture
def windowsVM(oc):
    with TemporaryEnvironmentVariables():
        setup()
        yield resource
        cleanup()  # Implicit via context manager
```

**Why:** Guarantees cleanup of transient environment even if test fails.

---

## Validation Checklist

- [x] **Modular approach:** Fixtures split into separate files by concern
- [x] **Fixture as library:** Each fixture module is self-contained and reusable
- [x] **Scenario-wise fixtures:** `krknChaos`, `vmCreate`, `sshTunnelConnection`, `windowsVM` each address a scenario
- [x] **Context managers:** `TemporaryEnvironmentVariables()` used in benchmark-runner fixtures
- [x] **OC as benchmark runner:** `oc` fixture initialized from benchmark-runner's OC client
- [x] **Environment setup:** `windowsVM` and `windowsVMScale` set up environment via context managers
- [x] **Separation of concerns:** VM creation ≠ SSH tunnels ≠ krkn chaos ≠ benchmark-runner
- [x] **Dependency injection:** Fixtures depend on each other cleanly (e.g., `vmWithTunnel` → `vmCreate` + `sshTunnelConnection`)

---

## Summary

bsodpoc has achieved a **mature, modular fixture architecture**:

1. **Fixtures as libraries** — Organized by concern, reusable, testable
2. **Context managers** — Proper setup/teardown with `TemporaryEnvironmentVariables`
3. **Scenario-wise design** — Each fixture serves a specific test scenario (VM creation, chaos, SSH, benchmarks)
4. **OC integration** — benchmark-runner's OC client cached in singleton fixture
5. **Separation of concerns** — VM setup, chaos injection, tunneling, and benchmarking are independent

This pattern is **production-ready** and **easily extensible** for new scenarios (e.g., memory hog, time-skew, CPU burn — each would add a new test that requests `krknChaos` + `vmCreate`, no new fixtures needed).

# bsodpoc Pytest Architecture — Complete Walkthrough

**For pytest newcomers:** This guide explains how bsodpoc uses pytest to test VM chaos scenarios.

---

## What is Pytest? (5-minute primer)

Pytest is a Python testing framework that makes it easy to write and run tests. Key concepts:

| Concept | What it does | Example |
|---------|-------------|---------|
| **Test function** | A function that runs one test; must start with `test_` | `def test_vm_create():` |
| **Fixture** | Reusable setup/teardown code; tests request it as a parameter | `def test_something(vm_create):` asks pytest to set up a VM |
| **Marker** | A label on a test; pytest can filter/select by marker | `@pytest.mark.bsod` marks this test as BSOD-related |
| **Parametrize** | Run the same test multiple times with different inputs | `@pytest.mark.parametrize("vm_create", [(2, "ns")], indirect=True)` creates 2 VMs |
| **Assertion** | Check if something is true; if false, test fails | `assert vm_recovered, "VM didn't come back"` |

---

## The bsodpoc File Structure

```
/home/hijoshi/bsodpoc/
├── conftest.py                 ← Fixtures (setup/teardown code shared by all tests)
├── pytest.ini                  ← Pytest configuration
├── tests/
│   ├── test_chaos.py          ← Pod-kill scenario + host-side reach test
│   └── test_sample1.py        ← VM creation + tunnel tests (mostly skipped)
├── libs/
│   ├── command_runner.py      ← Wrapper around `oc`/shell commands
│   ├── yaml_parser.py         ← Loads and renders YAML with variable substitution
│   ├── vm.py                  ← VirtctlSSH class for guest SSH access
│   └── ssh_tunnel.py          ← Persistent SSH ControlMaster tunnels
├── config/
│   └── vm-config-tlbflush-on.yaml  ← VM template (4 cores, 16Gi, full enlightenments)
└── docs/
    └── krknlib-guide.md       ← krkn-lib usage notes
```

---

## Part 1: conftest.py — The Fixture Foundation

**What is conftest.py?**  
A special pytest file where you define **fixtures** — reusable setup/teardown code. Every test that needs a VM, a chaos client, or a tunnel gets it from here.

### Fixture 1: `vm_create` (lines 20-65)

```python
@pytest.fixture(scope="function")
def vm_create(request):
    """Create N VMs and yield their names + status."""
    results = {}
    runner = CommandRunner()
    vm_config = request.config.rootpath / "config" / "vm-config-tlbflush-on.yaml"
    
    # Accept (count, namespace) or bare int
    param = getattr(request, "param", (1, DEFAULT_NAMESPACE))
    count, namespace = (param, DEFAULT_NAMESPACE) if isinstance(param, int) else param
    
    for _ in range(count):
        vm_name = f"bsod-auto-{random.randint(100, 999)}"
        context_variables = {"VM_NAME": vm_name}
        replaced_config = request.config.rootpath / "replaced_config" / Path(vm_name).with_suffix(".yaml")
        
        # Load YAML, substitute ${VM_NAME} with actual name
        ConfigLoader.loadAndSave(vm_config, replaced_config, context_variables)
        
        # Create the VM on the cluster
        create = runner.run(f"oc apply -f {replaced_config}", shell=True)
        if create.success:
            logs.info(f"VM created with name {vm_name}")
            time.sleep(10)  # Let boot progress
            results[vm_name] = runner.run(
                f"oc get vm/{vm_name} -n {namespace} -o custom-columns='STATUS:.status.printableStatus' --no-headers",
                shell=True,
            )
    
    yield results  # TEST RUNS HERE — receives dict of {vmName: CommandResult}
    
    # TEARDOWN: delete all VMs created above
    for vm_name in results:
        logs.info(f"Cleaning up VM {vm_name}")
        runner.run(f"oc delete vm {vm_name} -n {namespace}", shell=True)
```

**How to use it in a test:**
```python
def test_something(vm_create):
    # vm_create is now a dict: {"bsod-auto-742": CommandResult(...)}
    for vmName in vm_create:
        print(f"VM created: {vmName}")
    # After test completes, conftest.py automatically deletes the VMs
```

**`yield` keyword:**  
- Before `yield`: **setup** (create VMs)
- `yield results`: **give control to the test**
- After `yield`: **teardown** (delete VMs)

This guarantees cleanup even if the test fails — you always get a fresh cluster afterward.

---

### Fixture 2: `KRKN_DEFAULTS` (lines 70-74)

```python
KRKN_DEFAULTS: Dict[str, Any] = {
    "namespace": DEFAULT_NAMESPACE,      # "windows-bsod"
    "vmName": "hjoshi-win2022",          # The persistent VM we test against
    "recoverTimeout": 300,               # 5 minutes to recover
}
```

This is a **dictionary of defaults**. Any test can override these via a marker.

---

### Fixture 3: `krknChaos` (lines 83-116)

```python
@pytest.fixture(scope="function")
def krknChaos(request):
    """Provide a krkn-lib client + read the test's @pytest.mark.krkn(...) params."""
    
    # Lazily import krkn-lib (so tests still collect if krkn-lib is missing)
    from krkn_lib.k8s import KrknKubernetes
    
    # Read the @pytest.mark.krkn(...) marker on the test function
    marker = request.node.get_closest_marker("krkn")
    
    # Merge marker params with KRKN_DEFAULTS
    # Example: if test has @pytest.mark.krkn(recoverTimeout=600), 
    # it overrides the default 300
    params = {**KRKN_DEFAULTS, **(marker.kwargs if marker else {})}
    
    # Initialize the krkn-lib client from kubeconfig
    kubeconfigPath = os.environ.get("KUBECONFIG") or os.path.expanduser("~/.kube/config")
    logs.info(f"Initialising krkn-lib client with kubeconfig: {kubeconfigPath}")
    client = KrknKubernetes(kubeconfig_path=kubeconfigPath)
    
    # Yield both the client AND the merged params as a NamedTuple
    yield KrknContext(client=client, params=params)
    
    # Teardown (no cleanup needed; client is stateless)
    logs.info("krknChaos fixture teardown complete")
```

**How to use it in a test:**
```python
@pytest.mark.krkn(recoverTimeout=600)  # Override default 300 → 600
def test_something(krknChaos):
    client = krknChaos.client      # The krkn-lib KrknKubernetes instance
    params = krknChaos.params      # The merged dict with all params
    
    timeout = params["recoverTimeout"]  # 600 (from marker)
    vmName = params["vmName"]           # "hjoshi-win2022" (from KRKN_DEFAULTS)
```

**The Marker Pattern:**  
Instead of hardcoding test parameters in the test, you declare them in a marker above the function:

```python
# ❌ BAD: hardcoded
def test_vmKill():
    vmName = "hjoshi-win2022"
    timeout = 300
    ...

# ✅ GOOD: parametrized via marker
@pytest.mark.krkn(vmName="hjoshi-win2022", recoverTimeout=300)
def test_vmKill(krknChaos):
    vmName = krknChaos.params["vmName"]
    timeout = krknChaos.params["recoverTimeout"]
    ...
```

**Why?** It keeps parameters visible at the top of the test (no squinting into the function body). Easy to change without touching code.

---

### Fixture 4: `ssh_tunnel_connection` (lines 129-148)

```python
@pytest.fixture
def ssh_tunnel_connection(request):
    """Factory fixture: provides a function that creates SSH tunnels."""
    tunnels: list[VirtctlSshTunnel] = []
    
    def _make(vmName: str, namespace: str = DEFAULT_NAMESPACE) -> VirtctlSshTunnel:
        """Create one tunnel; add it to the list for cleanup."""
        tunnel = VirtctlSshTunnel(
            target=f"Administrator@vm/{vmName}",
            namespace=namespace,
            identityFile=str(Path.home() / ".ssh" / "id_ed25519"),
            binPath=findVirtctlPath(),
            kubeconfig=os.environ.get("KUBECONFIG"),
        )
        tunnels.append(tunnel)
        return tunnel
    
    yield _make  # Yield the FUNCTION, not the tunnel
    
    # Teardown: close all tunnels that were created
    for tunnel in tunnels:
        tunnel.close()
```

**Factory pattern:**  
Instead of creating one tunnel per test, this fixture yields a **function** (`_make`) that creates tunnels on demand.

```python
def test_something(ssh_tunnel_connection):
    # ssh_tunnel_connection is a function, not a tunnel
    tunnel1 = ssh_tunnel_connection("hjoshi-win2022")  # Create tunnel 1
    tunnel2 = ssh_tunnel_connection("win2022-vm-vvijay1")  # Create tunnel 2
    
    # Both tunnels are automatically closed after test completes
```

---

### Fixture 5: `vm_with_tunnel` (lines 151-154)

```python
@pytest.fixture
def vm_with_tunnel(vm_create, ssh_tunnel_connection):
    """Composes two fixtures: creates VMs, then one SSH tunnel per VM."""
    # vm_create is {"vm-name1": ..., "vm-name2": ...}
    # ssh_tunnel_connection is a function
    
    return {vmName: ssh_tunnel_connection(vmName) for vmName in vm_create}
    # Result: {"vm-name1": tunnel1, "vm-name2": tunnel2}
```

**Fixture composition:** This fixture *depends on* two other fixtures:
- `vm_create` — get the list of VMs
- `ssh_tunnel_connection` — tunnel factory

Pytest sees the dependencies and runs them in order.

---

## Part 2: pytest.ini — Configuration

```ini
[pytest]
log_cli = true                           # Print logs to console
log_cli_level = INFO                     # Show INFO level and above
testpaths = tests                        # Only look for tests in tests/ directory
python_files = test_*.py                 # Only run test_*.py files
addopts = -ra --strict-markers           # Show short summary; enforce marker declaration

markers =
    bsod: bsod tests
    krkn: krkn-lib chaos scenario
    tunnel: uses persistent virtctl ssh tunnel
    check: connectivity check over tunnel
```

**What this does:**
- Pytest only runs `test_*.py` files in the `tests/` directory
- `--strict-markers` means every marker used in tests (e.g., `@pytest.mark.bsod`) must be declared here
- Logs go to console as the test runs
- `-ra` prints a short summary at the end ("passed", "skipped", etc.)

---

## Part 3: test_chaos.py — The Actual Tests

### Test 1: `test_vmSurvivesVirtLauncherKill` (lines 86-137)

This is the **pod disruption scenario**. Here's what it does:

```python
@pytest.mark.krkn(
    vmName="hjoshi-win2022",
    namespace="windows-bsod",
    labelSelector="vm.kubevirt.io/name=hjoshi-win2022",
    recoverTimeout=300,
)
def test_vmSurvivesVirtLauncherKill(self, krknChaos):
    """
    SCENARIO: Kill the virt-launcher pod (simulates node/pod failure).
    ASSERTION: Verify KubeVirt reschedules it and the VM recovers.
    """
```

**Step-by-step execution:**

#### Step 1: Extract parameters from fixture
```python
client = krknChaos.client          # KrknKubernetes instance
params = krknChaos.params          # Dict with marker params
ns = params["namespace"]           # "windows-bsod"
vmName = params["vmName"]          # "hjoshi-win2022"
selector = params["labelSelector"] # "vm.kubevirt.io/name=hjoshi-win2022"
recoverTimeout = params.get("recoverTimeout", 300)  # 300s
runner = CommandRunner()           # Shell command wrapper
```

#### Step 2: Find the virt-launcher pod
```python
pods = client.list_pods(namespace=ns, label_selector=selector)
# Returns: ["virt-launcher-hjoshi-win2022-k928g"]

assert pods, f"no virt-launcher pod found..."
originalPod = pods[0]
logs.info(f"target virt-launcher pod: {originalPod}")
```

**What's a label selector?**  
Kubernetes labels are key=value pairs on resources. The label `vm.kubevirt.io/name=hjoshi-win2022` is on every pod backing that VM. `list_pods(..., label_selector=...)` filters pods by this label.

#### Step 3: Verify VM is running before chaos
```python
before = runner.run(
    f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", 
    shell=True
)
assert before.stdout == "Running", f"VM not Running before chaos: {before.stdout!r}"
```

**Why this check?**  
If the VM isn't running before you kill the pod, the recovery assertion below is meaningless. You want to prove that the chaos **caused** the failure and recovery, not that the VM was already broken.

#### Step 4: INJECT CHAOS — Delete the pod
```python
logs.info(f"CHAOS: deleting virt-launcher pod {originalPod}")
client.delete_pod(originalPod, ns)
```

This is the **stress injection**. The pod holding the qemu process vanishes instantly.

**What happens on the cluster:**
- The virt-launcher pod (`originalPod`) is deleted
- KubeVirt's virt-controller detects the pod is gone
- virt-controller spins up a **new** virt-launcher pod
- The new pod pulls the Windows boot disk (cached locally, ~10-30s)
- Windows boots, VMI reaches "Running" phase

#### Step 5: Poll for recovery
```python
deadline = time.time() + recoverTimeout  # Set a 300-second timeout
recovered = False

while time.time() < deadline:
    # Check if a NEW pod exists
    current = client.list_pods(namespace=ns, label_selector=selector)
    newPods = [p for p in current if p != originalPod]  # Pods that weren't there before
    
    # Check VMI phase
    vmiPhase = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
        shell=True
    ).stdout
    
    # TWO conditions must BOTH be true:
    # 1. A new pod exists
    # 2. That pod is running
    # 3. VMI is in "Running" phase
    if newPods and client.is_pod_running(newPods[0], ns) and vmiPhase == "Running":
        logs.info(f"recovered: new pod {newPods[0]} Running, VMI phase {vmiPhase}")
        recovered = True
        break
    
    logs.info(f"waiting for recovery ... (VMI phase={vmiPhase!r})")
    time.sleep(10)  # Check again in 10 seconds
```

#### Step 6: Assert recovery
```python
assert recovered, (
    f"VM {vmName} did not recover within {recoverTimeout}s after virt-launcher kill"
)
```

If `recovered == True`, **test passes** ✅  
If `recovered == False`, **test fails** ❌ with the error message

---

### Timeline of the test

```
t=0:00  Test starts
        ├─ Get virt-launcher pod: virt-launcher-hjoshi-win2022-k928g
        ├─ Verify VM is Running (✓)
        
t=0:01  CHAOS injected: delete pod
        ├─ Pod is gone
        ├─ KubeVirt virt-controller wakes up
        
t=0:02  virt-controller spins up new pod: virt-launcher-hjoshi-win2022-m8x2f
        
t=0:05  Poll: new pod exists, but still pulling image
        
t=0:15  Poll: new pod running, Windows booting
        
t=0:35  Poll: new pod running, Windows booted, VMI.phase == "Running"
        ├─ recovered = True
        ├─ BREAK from loop
        
t=0:36  Assert recovered (✓ PASS)
```

---

### Test 2: `test_hostSideKernelScanOnVmNode` (lines 143-197)

This test doesn't inject chaos — it's a **proof of concept** that host-side command execution works.

```python
@pytest.mark.krkn(
    vmName="hjoshi-win2022",
    namespace="windows-bsod",
)
def test_hostSideKernelScanOnVmNode(self, krknChaos):
    """
    SCENARIO: Prove we can run privileged commands on the worker node.
    ASSERTION: Execute `uname -r` and get kernel output back.
    """
```

**Steps:**

1. **Resolve the node** the VM runs on
   ```python
   nodeRes = runner.run(
       f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
       shell=True,
   )
   node = nodeRes.stdout.strip()  # "integrity-gs04.sys.eng.rdu2.dc.redhat.com"
   ```

2. **Verify node is Ready**
   ```python
   readyNodes = client.list_ready_nodes()
   assert node in readyNodes, f"node {node} is not Ready"
   ```

3. **Execute a command on the node via `execOnNode()`**
   ```python
   kernel = execOnNode(
       client, node, "uname -r",
       podName="krkn-hostscan", namespace=ns,
   )
   logs.info(f"node {node} kernel release: {kernel!r}")
   assert kernel and kernel.strip(), "no output from host-side exec"
   ```

4. **Bonus: scan dmesg for BSOD-relevant signals**
   ```python
   scan = execOnNode(
       client, node,
       "dmesg 2>/dev/null | grep -iE 'split.?lock|#AC|hypervisor' || true",
       podName="krkn-hostscan", namespace=ns,
   )
   logs.info(f"host kernel-log scan on {node}:\n{scan}")
   ```

**Why is this test useful?**  
It proves the plumbing works for host-side injection. When you want to inject vCPU stall or time-skew, you'll use this same `execOnNode()` pattern.

---

## Part 4: Supporting Libraries

### libs/command_runner.py
```python
class CommandRunner:
    def run(self, cmd, shell=False, retries=1):
        """Run a command (via shell or list), return CommandResult."""
        # Returns: CommandResult(success, stdout, stderr, returncode)
```

Used everywhere: `runner.run("oc get vm ...", shell=True)`

---

### libs/yaml_parser.py
```python
class ConfigLoader:
    @staticmethod
    def loadAndSave(template_path, output_path, context_variables):
        """Load YAML, replace ${VAR} with context values, save."""
        # Reads vm-config-tlbflush-on.yaml
        # Replaces ${VM_NAME} with actual name
        # Writes replaced_config/bsod-auto-742.yaml
```

---

### libs/vm.py
```python
class VirtctlSSH:
    def __init__(self, vmName, namespace, username, identityFile):
        ...
    
    def executeRemoteCommand(self, remoteCmd) -> CommandResult:
        """SSH into the guest via virtctl, run a command."""
        # Used by test_sample1.py to reach inside the guest
```

---

### libs/ssh_tunnel.py
```python
class VirtctlSshTunnel:
    def __init__(self, target, namespace, identityFile, binPath, kubeconfig):
        ...
    
    def ensure(self):
        """Establish ControlMaster tunnel if not alive."""
    
    def runPowershell(self, script: str) -> CommandResult:
        """Run PowerShell over the tunnel."""
    
    def send(self, localPath, remotePath) -> CommandResult:
        """Upload file."""
    
    def receive(self, remotePath, localPath) -> CommandResult:
        """Download file."""
    
    def close(self):
        """Tear down the tunnel."""
```

---

### config/vm-config-tlbflush-on.yaml
The VM template. Key lines:

```yaml
metadata:
  name: ${VM_NAME}  # Substituted at runtime

spec:
  nodeSelector:
    memory-backend: enabled  # Run on nodes with hugetlbfs

  domain:
    cpu:
      cores: 4
      model: EPYC-Genoa
    memory:
      guest: "16Gi"
    
    features:
      hyperv:
        synic: {}           # Synthetic interrupts
        synictimer: {}      # Synthetic timer
        reenlightenment: {} # TSC rescaling
        frequencies: {}     # CPU frequency hints
        spinlocks: 8191     # Optimized spinlock

  volumes:
    - dataVolume:
        name: ${VM_NAME}  # Cloned from hjoshi-boot-disk
```

**Why these features?**  
Every one is a **timing/interrupt shortcut** that the guest kernel relies on the hypervisor to provide. If the hypervisor stalls vCPUs, skews time, or has TLB issues, these are the code paths that break.

---

## The Full Test Flow Diagram

```
pytest runs test_vmSurvivesVirtLauncherKill
    │
    ├─→ conftest.py: krknChaos fixture
    │   └─ Initialize KrknKubernetes client from KUBECONFIG
    │
    ├─→ Test reads marker: @pytest.mark.krkn(...)
    │   └─ Merges with KRKN_DEFAULTS
    │
    ├─→ Test Step 1: Find virt-launcher pod
    │   └─ client.list_pods(..., label_selector=...)
    │
    ├─→ Test Step 2: Verify VM running
    │   └─ runner.run("oc get vmi ... --phase")
    │
    ├─→ Test Step 3: CHAOS — kill the pod
    │   └─ client.delete_pod(originalPod, ns)
    │
    ├─→ Test Step 4: Poll for recovery (loop 30 times, 10s apart)
    │   ├─ client.list_pods(...) — is there a new pod?
    │   ├─ client.is_pod_running(newPod, ns) — is it up?
    │   └─ runner.run("oc get vmi ... --phase") — is VMI Running?
    │
    ├─→ Test Step 5: Assert recovered
    │   └─ assert recovered, "did not recover in 300s"
    │
    └─→ Cleanup (conftest.py teardown)
        └─ (No VM cleanup in test_chaos — uses persistent hjoshi-win2022)
```

---

## What Each Pytest Concept Means in bsodpoc

| Pytest Concept | How bsodpoc uses it | Purpose |
|---|---|---|
| **Fixture** | `vm_create`, `krknChaos`, `ssh_tunnel_connection` | Reuse setup code across tests |
| **`yield`** | `vm_create yields results, then deletes VMs` | Guarantee cleanup even on test failure |
| **Marker** | `@pytest.mark.krkn(...)` | Parametrize tests without hardcoding |
| **`indirect=True`** | `@pytest.mark.parametrize("vm_create", [(2, "ns")], indirect=True)` | Pass parameters to fixture (not test) |
| **Assertion** | `assert pods`, `assert recovered` | Fail the test if something went wrong |
| **`request` object** | `request.param`, `request.node.get_closest_marker()` | Access pytest internals (params, markers) |
| **Class-based tests** | `class TestChaos: def test_vmSurvivesVirtLauncherKill()` | Organize related tests together |

---

## How to Run the Tests

### Run all tests
```bash
cd /home/hijoshi/bsodpoc
pytest tests/ -v
```

### Run only the chaos tests
```bash
pytest tests/test_chaos.py -v
```

### Run only tests with the `krkn` marker
```bash
pytest -m krkn -v
```

### Run with live logs
```bash
pytest tests/ -v -s  # -s shows stdout/print statements
```

### Run a single test
```bash
pytest tests/test_chaos.py::TestChaos::test_vmSurvivesVirtLauncherKill -v
```

---

## Key Takeaways

1. **Fixtures are the spine** — `conftest.py` defines reusable setup (`vm_create`, `krknChaos`). Tests request them as parameters.

2. **Markers parametrize tests** — `@pytest.mark.krkn(vmName=..., timeout=...)` declares test parameters visibly at the top.

3. **`yield` guarantees cleanup** — Even if a test crashes mid-way, teardown code after `yield` always runs.

4. **Assertions fail tests** — `assert recovered` means "if recovery didn't happen, fail this test with this message."

5. **Pod-kill scenario tests recovery** — Kill the pod, poll for a new one + VMI Running, assert it came back.

6. **Host-side reach is proven** — `execOnNode()` on the worker proves we can inject stress (vCPU stall, time-skew, CPU hog).

7. **Everything is logged** — Every step prints to pytest log (`logs.info`), so you can trace what happened if a test fails.

---

## Next: Write Your Own Test

To add a **vCPU stall** scenario:

```python
@pytest.mark.krkn(
    vmName="hjoshi-win2022",
    namespace="windows-bsod",
    stallSeconds=30,
    recoverTimeout=300,
)
def test_vmBugchecksUnderVcpuStall(self, krknChaos):
    """Stall the qemu process; expect CLOCK_WATCHDOG_TIMEOUT."""
    client = krknChaos.client
    params = krknChaos.params
    ns = params["namespace"]
    vmName = params["vmName"]
    stallSeconds = params["stallSeconds"]
    
    # Find the node
    nodeRes = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
        shell=True,
    )
    node = nodeRes.stdout.strip()
    
    # CHAOS: freeze the qemu process
    execOnNode(
        client, node,
        f"pkill -STOP -f qemu-kvm && sleep {stallSeconds} && pkill -CONT -f qemu-kvm",
        podName=f"vcpu-stall-{vmName}", namespace=ns
    )
    
    # Guest experiences 100% steal time
    # If reenlightenment is broken: Windows bugchecks with 0x101
    
    # The detector (watch-crash.sh) catches it
    # You just injected the stress; detection is the detector's job
```

That's the pattern: **inject chaos, let the detector catch it.**

# krkn-lib Functionality Roadmap for BSOD Test Scenarios

**Purpose:** Map all krkn-lib capabilities to BSOD stress injection and assertion patterns.

---

## The BSOD Testing Triangle

```
         ┌─────────────────────┐
         │   INJECT CHAOS      │ (krkn-lib)
         │ (stress the guest)  │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   DETECT CRASH      │ (detector repo)
         │ (watch-crash.sh)    │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   ANALYZE EVIDENCE  │ (detector repo)
         │ (collect-guest.ps1) │
         └─────────────────────┘
```

**bsodpoc's job:** Build the injection layer. Detection/analysis is the detector's job.

---

## Stress Injection Methods (krkn-lib capabilities)

### 1. POD OPERATIONS — Pod-Level Chaos

| Scenario | krkn-lib function | What happens | Expected BSOD |
|----------|-------------------|--------------|---|
| **Pod kill** | `delete_pod(pod, ns)` | virt-launcher pod vanishes → VMI controller reschedules | N/A (tests recovery, not crash) |
| **Pod creation** | `create_pod(body, ns)` | Create stress pods (e.g., memory hog) on same node | N/A (indirect stress) |
| **Pod exec** | `exec_cmd_in_pod(cmd, pod, ns)` | Run command inside virt-launcher | N/A (limited use; guest is isolated) |

**Status:** `test_vmSurvivesVirtLauncherKill` implemented ✅

---

### 2. HOST/NODE OPERATIONS — Direct Hypervisor Stress (Highest Value)

| Scenario | krkn-lib function | Command | Expected BSOD | Implementation |
|----------|-------------------|---------|---|---|
| **vCPU stall** | `exec_command_on_node(node, cmd, pod, ns)` | `pkill -STOP -f qemu-kvm; sleep 45; pkill -CONT -f qemu-kvm` | **0x101** CLOCK_WATCHDOG_TIMEOUT or **0x20001** HYPERVISOR_ERROR | ⏳ TODO |
| **Time skew** | `exec_command_on_node(...)` | `date -s '+15 minutes'` | **0x133** DPC_WATCHDOG_VIOLATION | ⏳ TODO |
| **CPU steal** | `exec_command_on_node(...)` | `stress-ng --cpu $(nproc) --timeout 120s` | Timeout-based watchdog (0x101) | ⏳ TODO |
| **Host dmesg scan** | `exec_command_on_node(...)` | `dmesg \| grep -E 'split.?lock\|#AC\|hypervisor'` | N/A (detection only) | ✅ test_hostSideKernelScanOnVmNode |

**Pattern:**
```python
# Get the node the VM runs on
nodeRes = runner.run(
    f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
    shell=True
)
node = nodeRes.stdout.strip()

# Execute privileged command on the node
result = client.exec_command_on_node(
    node_name=node,
    command=["your", "command", "here"],
    exec_pod_name=f"stress-{vmName}",
    exec_pod_namespace=ns
)
```

**Status:** Infrastructure ready (via `execOnNode()` helper); scenarios not yet implemented ⏳

---

### 3. JOB-BASED STRESS — Sustained Workload

| Scenario | krkn-lib function | Payload | Expected BSOD | Implementation |
|----------|-------------------|---------|---|---|
| **Memory hog** | `create_job(body, ns)` | `stress-ng --vm 4 --vm-bytes 90%` on same node | **0x1A** MEMORY_MANAGEMENT (page faults) | ⏳ TODO |
| **CPU burn** | `create_job(body, ns)` | `stress-ng --cpu $(nproc)` on same node | vCPU scheduling latency (0x101) | ⏳ TODO |
| **I/O pressure** | `create_job(body, ns)` | `fio --write=100%` on same node | Depends on qemu I/O path | ⏳ TODO |
| **Cleanup** | `delete_job(name, ns)` | Delete the job | N/A | N/A |

**Job body example:**
```python
memory_hog_job = {
    "apiVersion": "batch/v1",
    "kind": "Job",
    "metadata": {"name": f"mem-hog-{vmName}"},
    "spec": {
        "template": {
            "spec": {
                # Critical: same node as the VM
                "nodeSelector": {"kubernetes.io/hostname": node},
                "restartPolicy": "Never",
                "containers": [{
                    "name": "stress",
                    "image": "registry.access.redhat.com/ubi9/ubi",
                    "command": ["stress-ng", "--vm", "4", "--vm-bytes", "90%", "--timeout", "300s"],
                    "resources": {
                        "requests": {"memory": "28Gi", "cpu": "4"},
                        "limits": {"memory": "28Gi", "cpu": "4"}
                    }
                }]
            }
        }
    }
}
job = client.create_job(memory_hog_job, ns)
```

**Status:** Not implemented ⏳

---

### 4. NETWORK FAULTS — Edge Cases

| Scenario | krkn-lib function | Method | Expected impact | Implementation |
|----------|-------------------|--------|---|---|
| **Block traffic** | `create_net_policy(body, ns)` | NetworkPolicy deny-all | Guest SSH timeout (not BSOD) | Low priority 🔵 |
| **Cleanup** | `delete_net_policy(name, ns)` | Delete policy | Resume traffic | N/A |

**Status:** Not recommended for BSOD (doesn't trigger bugchecks, just timeouts)

---

### 5. MONITORING & ASSERTIONS — Verify VM State

| Function | Purpose | BSOD testing use | Implementation |
|----------|---------|---|---|
| `list_pods(ns, label_selector)` | Find virt-launcher | Locate target pod | ✅ Used in pod-kill test |
| `get_pod_info(pod, ns)` | Pod details (node, containers) | Get node info for stress injection | ⏳ TODO |
| `is_pod_running(pod, ns)` | Check pod running | Assert recovery | ✅ Used in pod-kill test |
| `monitor_pods_by_label(selector, ns)` | Watch pod status changes | Real-time recovery tracking | ⏳ TODO |
| `list_ready_nodes()` | Get healthy worker nodes | Node selection for stress | ✅ Used in kernel-scan test |
| `get_node_cpu_count(node)` | CPU cores on node | Size CPU stress appropriately | ⏳ TODO |
| `get_nodes_infos()` | Memory/CPU/disk per node | Capacity planning | ⏳ TODO |
| `watch_node_status(node, status, timeout)` | Wait for node state | Verify node stability | ⏳ TODO |
| `custom_object_client` | Access KubeVirt custom objects | Read VM/VMI status directly | ⏳ TODO (for structured assertions) |

**Status:** Partial; core assertions in place, structured queries not yet added

---

## Complete BSOD Test Scenario Matrix

### Tier 0: Infrastructure Proof (Implemented ✅)

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod")
def test_vmSurvivesVirtLauncherKill(krknChaos):
    """Pod-kill scenario: forces VMI controller to reschedule."""
    # Uses: delete_pod, list_pods, is_pod_running
```

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod")
def test_hostSideKernelScanOnVmNode(krknChaos):
    """Host-side command execution proof."""
    # Uses: exec_command_on_node, list_ready_nodes
```

---

### Tier 1: Direct Hypervisor Stress (Enlightenment Exercise)

#### Scenario 1A: vCPU Stall

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod", stallSeconds=30)
def test_vmBugchecksUnderVcpuStall(krknChaos):
    """
    vCPU starvation → guest sees 100% steal time → reenlightenment tested.
    Expected: CLOCK_WATCHDOG_TIMEOUT (0x101) if reenlightenment broken.
    """
    client = krknChaos.client
    params = krknChaos.params
    ns = params["namespace"]
    vmName = params["vmName"]
    stallSeconds = params["stallSeconds"]
    runner = CommandRunner()
    
    # 1. Get the node
    nodeRes = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
        shell=True
    )
    node = nodeRes.stdout.strip()
    
    # 2. Verify VM is running before chaos
    before = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
        shell=True
    )
    assert before.stdout == "Running", f"VM not Running before chaos"
    
    # 3. CHAOS: freeze qemu
    logs.info(f"CHAOS: SIGSTOP qemu on {node} for {stallSeconds}s")
    execOnNode(
        client, node,
        f"pkill -STOP -f qemu-kvm && sleep {stallSeconds} && pkill -CONT -f qemu-kvm",
        podName=f"vcpu-stall-{vmName}",
        namespace=ns
    )
    
    # 4. Guest now experiences vCPU starvation
    # detector's watch-crash.sh will catch CLOCK_WATCHDOG_TIMEOUT
    
    # 5. Poll for recovery (or crash)
    time.sleep(5)  # Let guest react
    after = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
        shell=True
    )
    
    # EITHER: VM recovered (phase = Running) → reenlightenment worked ✅
    # OR: VM crashed (phase = Failed) → detector caught BSOD ✅
    assert after.stdout in ["Running", "Failed"], f"Unexpected phase: {after.stdout}"
```

**krkn-lib functions used:**
- `exec_command_on_node(node, cmd, pod, ns)` — inject SIGSTOP/SIGCONT
- `list_pods(ns, label_selector)` — find virt-launcher (implicitly via oc)

---

#### Scenario 1B: Time Skew

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod", timeSkewMinutes=15)
def test_vmBugchecksUnderTimeSkew(krknChaos):
    """
    Host clock jump → TSC discontinuity → DPC watchdog fires.
    Expected: DPC_WATCHDOG_VIOLATION (0x133) if reenlightenment broken.
    """
    # Similar pattern to vCPU stall:
    # 1. Get node
    # 2. Verify VM running
    # 3. CHAOS: date -s on host
    # 4. Poll for recovery/crash
    
    execOnNode(
        client, node,
        f"date -s '+{timeSkewMinutes} minutes'",
        podName=f"time-skew-{vmName}",
        namespace=ns
    )
```

**krkn-lib functions used:**
- `exec_command_on_node(node, cmd, pod, ns)` — inject date command

---

### Tier 2: Resource Contention Stress

#### Scenario 2A: Memory Hog (via Job)

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod", hogPercent=80)
def test_vmUnderMemoryPressure(krknChaos):
    """
    Hugepage contention → swap/page faults → memory corruption.
    Expected: MEMORY_MANAGEMENT (0x1A) if Verifier enabled.
    """
    client = krknChaos.client
    params = krknChaos.params
    ns = params["namespace"]
    vmName = params["vmName"]
    hogPercent = params["hogPercent"]
    runner = CommandRunner()
    
    # 1. Get the node
    nodeRes = runner.run(
        f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
        shell=True
    )
    node = nodeRes.stdout.strip()
    
    # 2. Get node memory so we can hog 80% of it
    readyNodes = client.list_ready_nodes()
    assert node in readyNodes
    
    nodesInfo = client.get_nodes_infos()  # Returns dict of {node: {memory: X, cpu: Y}}
    nodeMemory = nodesInfo[node]["memory"]  # e.g., "128Gi"
    hogMemory = str(int(nodeMemory.rstrip("Gi")) * hogPercent // 100) + "Gi"
    
    # 3. Create a memory hog job on the same node
    memory_hog_job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": f"mem-hog-{vmName}"},
        "spec": {
            "template": {
                "spec": {
                    "nodeSelector": {"kubernetes.io/hostname": node},
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "stress",
                        "image": "registry.access.redhat.com/ubi9/ubi",
                        "command": ["stress-ng", "--vm", "4", "--vm-bytes", f"{hogMemory}", "--timeout", "300s"],
                    }]
                }
            }
        }
    }
    
    job = client.create_job(memory_hog_job, ns)
    logs.info(f"Memory hog job created: {job.metadata.name}")
    
    # 4. VM now competes for hugepages with the hog
    time.sleep(60)  # Let stress build up
    
    # 5. Poll for crash
    deadline = time.time() + 300
    crashed = False
    while time.time() < deadline:
        vmiPhase = runner.run(
            f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
            shell=True
        ).stdout
        
        if vmiPhase == "Failed":
            logs.info(f"VM crashed (expected 0x1A MEMORY_MANAGEMENT)")
            crashed = True
            break
        time.sleep(10)
    
    # 6. Cleanup
    client.delete_job(f"mem-hog-{vmName}", ns)
    
    # 7. Assert either recovered or crashed (both are valid outcomes)
    logs.info(f"Memory hog test: crashed={crashed}")
```

**krkn-lib functions used:**
- `get_nodes_infos()` — get memory capacity
- `create_job(body, ns)` — launch stress job
- `delete_job(name, ns)` — cleanup
- `list_ready_nodes()` — verify node health

---

#### Scenario 2B: CPU Burn (via Job)

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod")
def test_vmUnderCpuBurn(krknChaos):
    """
    CPU hog → vCPU scheduling latency.
    Expected: Watchdog timeout (0x101) if DPC can't run.
    """
    # Similar to memory hog:
    # 1. Get node, node CPU count
    # 2. Create CPU burn job: stress-ng --cpu $(nproc) --timeout 300s
    # 3. Poll for crash/recovery
    # 4. Cleanup
    
    cpuCount = client.get_node_cpu_count(node)
    logs.info(f"Node {node} has {cpuCount} CPUs; burning all of them")
```

**krkn-lib functions used:**
- `get_node_cpu_count(node)` — size the CPU burn
- `create_job(body, ns)` — launch CPU hog
- `delete_job(name, ns)` — cleanup

---

### Tier 3: Structured VM/VMI Assertions

#### Using CustomObjectsApi for Detailed Checks

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod")
def test_vmRecoveryWasNotLiveMigration(krknChaos):
    """
    Verify that after pod-kill, the recovery was a RESTART (not a migration).
    This requires reading the structured VMI status, not just phase.
    """
    client = krknChaos.client
    params = krknChaos.params
    ns = params["namespace"]
    vmName = params["vmName"]
    
    # Kill the pod (same as pod-kill test)
    pods = client.list_pods(namespace=ns, label_selector=f"vm.kubevirt.io/name={vmName}")
    originalPod = pods[0]
    client.delete_pod(originalPod, ns)
    
    # Wait for recovery
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            # Use custom_object_client to read VMI status
            vmi = client.custom_object_client.get_namespaced_custom_object(
                group="kubevirt.io", version="v1",
                namespace=ns, plural="virtualmachineinstances",
                name=vmName
            )
            
            # Check that recovery was NOT a live migration
            migrationState = vmi["status"].get("migrationState")
            assert not migrationState, "Recovery was a migration (bad!)"
            
            # Check phase is Running
            phase = vmi["status"].get("phase")
            if phase == "Running":
                logs.info("✓ VM recovered via restart (not migration)")
                return
        except Exception as e:
            logs.info(f"waiting: {e}")
        
        time.sleep(10)
    
    pytest.fail("VM did not recover within 300s")
```

**krkn-lib functions used:**
- `custom_object_client` — structured VM/VMI read (read-only)

**Benefit over `oc get vmi`:**  
You get the full object tree as JSON, not string parsing. Can assert on specific fields:
- `status.migrationState` — proved it was a restart
- `status.conditions[]` — detailed state machine
- `metadata.uid` — proved it's a NEW VMI (if uid changed)

---

## Complete Test Implementation Checklist

### Phase 0: Prove the plumbing (✅ Done)

- [x] Pod-kill scenario (`test_vmSurvivesVirtLauncherKill`)
- [x] Host-side exec proof (`test_hostSideKernelScanOnVmNode`)
- [x] `execOnNode()` helper for privileged commands
- [x] Fixture structure (`vm_create`, `krknChaos`, `ssh_tunnel_connection`)

### Phase 1: Hypervisor stress (⏳ Todo)

- [ ] vCPU stall scenario (`test_vmBugchecksUnderVcpuStall`)
  - Uses: `exec_command_on_node()` with pkill -STOP/-CONT
  - Assertion: Guest phase remains Running OR enters Failed
  - Expected BSOD: 0x101 or 0x20001

- [ ] Time-skew scenario (`test_vmBugchecksUnderTimeSkew`)
  - Uses: `exec_command_on_node()` with date -s
  - Assertion: Guest survives or crashes with 0x133
  - Expected BSOD: 0x133 DPC_WATCHDOG_VIOLATION

### Phase 2: Resource contention (⏳ Todo)

- [ ] Memory hog scenario (`test_vmUnderMemoryPressure`)
  - Uses: `create_job()`, `get_nodes_infos()`, `delete_job()`
  - Assertion: Guest survives under hugepage contention
  - Expected BSOD: 0x1A MEMORY_MANAGEMENT

- [ ] CPU burn scenario (`test_vmUnderCpuBurn`)
  - Uses: `create_job()`, `get_node_cpu_count()`, `delete_job()`
  - Assertion: Guest survives under scheduling latency
  - Expected BSOD: 0x101 (if DPC latency detector fires)

### Phase 3: Structured assertions (⏳ Todo)

- [ ] VMI recovery detail checks
  - Uses: `custom_object_client.get_namespaced_custom_object()`
  - Assertions: migration vs restart, uid changed, conditions evolved
  - Benefit: Proof of HOW recovery happened, not just THAT it happened

### Phase 4: Integration with detector (⏳ Todo)

- [ ] Post-chaos hook to auto-invoke detector
- [ ] Parse detector's evidence-summary.json
- [ ] Assert bugcheck code matches expected code
- [ ] Cross-check host-signals (TLB-flush correlation)

---

## krkn-lib Function Mapping to Test Scenarios

| Test | Primary krkn function | Secondary functions |
|---|---|---|
| `test_vmSurvivesVirtLauncherKill` | `delete_pod()` | `list_pods()`, `is_pod_running()` |
| `test_hostSideKernelScanOnVmNode` | `exec_command_on_node()` | `list_ready_nodes()` |
| `test_vmBugchecksUnderVcpuStall` (⏳) | `exec_command_on_node()` | `list_pods()` (via oc) |
| `test_vmBugchecksUnderTimeSkew` (⏳) | `exec_command_on_node()` | `list_pods()` (via oc) |
| `test_vmUnderMemoryPressure` (⏳) | `create_job()`, `delete_job()` | `get_nodes_infos()`, `list_ready_nodes()` |
| `test_vmUnderCpuBurn` (⏳) | `create_job()`, `delete_job()` | `get_node_cpu_count()`, `list_ready_nodes()` |
| `test_vmRecoveryWasNotLiveMigration` (⏳) | `custom_object_client.get_namespaced_custom_object()` | `delete_pod()`, `list_pods()` |

---

## Summary: What's Required

### Already in Place ✅
1. Fixture infrastructure (`conftest.py`)
2. Pod-kill scenario
3. Host-side command execution proof
4. `execOnNode()` helper function
5. pytest markers + parametrization

### Needs Implementation ⏳

**High Priority (direct hypervisor stress):**
1. vCPU stall test (`pkill -STOP qemu`)
2. Time-skew test (`date -s`)

**Medium Priority (resource contention):**
3. Memory hog test (via `create_job()`)
4. CPU burn test (via `create_job()`)

**Low Priority (polish):**
5. Structured VM assertions (via `custom_object_client`)
6. Detector integration (auto-collect evidence on crash)
7. Node stability monitoring (via `watch_node_status()`)

---

## How to Implement Them

**Template for any new scenario:**

```python
@pytest.mark.krkn(vmName="hjoshi-win2022", namespace="windows-bsod", <param>=<value>)
def test_vm<ScenarioName>(krknChaos):
    """
    One-line description.
    Expected BSOD: 0xXXXX (or N/A if testing recovery).
    """
    client = krknChaos.client
    params = krknChaos.params
    ns = params["namespace"]
    vmName = params["vmName"]
    runner = CommandRunner()
    
    # 1. Resolve target (node, pod, etc.)
    nodeRes = runner.run(f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'", shell=True)
    node = nodeRes.stdout.strip()
    
    # 2. Sanity check: VM running before chaos
    before = runner.run(f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", shell=True)
    assert before.stdout == "Running", "VM not Running before chaos"
    
    # 3. CHAOS: inject stress via krkn-lib
    # Option A: execOnNode() for host-side commands
    result = execOnNode(client, node, "<command>", podName=f"<name>-{vmName}", namespace=ns)
    
    # Option B: create_job() for sustained workload
    job = client.create_job(job_body, ns)
    
    # 4. Poll for outcome
    time.sleep(5)  # Let guest react
    deadline = time.time() + 300
    while time.time() < deadline:
        vmiPhase = runner.run(f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", shell=True).stdout
        
        if vmiPhase in ["Running", "Failed"]:
            logs.info(f"Outcome: phase={vmiPhase}")
            break
        time.sleep(10)
    
    # 5. Cleanup (if needed)
    if job:
        client.delete_job(job.metadata.name, ns)
    
    # 6. Assert success
    assert vmiPhase in ["Running", "Failed"], f"Unexpected phase: {vmiPhase}"
    # Either VM recovered (Running) OR detector caught crash (Failed)
```

---

## Next Steps

1. **Pick one scenario to implement next** (recommend: vCPU stall)
2. **Copy the template above**
3. **Replace `<command>` with `pkill -STOP -f qemu-kvm && sleep 30 && pkill -CONT -f qemu-kvm`**
4. **Run:** `pytest tests/test_chaos.py::TestChaos::test_vmBugchecksUnderVcpuStall -v`
5. **In parallel terminal, watch detector:** `./src/scripts/host/watch-crash.sh --ns windows-bsod --vm hjoshi-win2022`
6. **Collect evidence and analyze**

Ready to implement the first scenario together?

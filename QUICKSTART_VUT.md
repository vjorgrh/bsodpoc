# VUT Quick Start Guide

## What is VUT?

**VUT** = **V**M **U**nder **T**est - A pytest fixture for **krkn-lib VM management**:
- Get VM status (CPU, memory, running state)
- Query running instance state (node, phase)
- Scale VM resources (CPU cores, memory)
- Delete VMs

## Installation

VUT is automatically available when tests are run with pytest:

```bash
pytest tests/test_vut.py -v
```

No additional installation needed beyond:
- Kubernetes cluster with KubeVirt
- Python 3.11 with pytest
- krkn-lib 5.0.0 (for VM operations)

## Usage Examples

### Get VM Status

```python
def test_vm_status(vut):
    vm = vut("win2022-vm-hjoshi1")
    
    status = vm.get_vm_status()
    print(f"CPU: {status['cpu_cores']}")
    print(f"Memory: {status['memory']}")
    print(f"RunStrategy: {status['runStrategy']}")
```

### Get Running Instance Info

```python
def test_vm_running(vut):
    vm = vut("win2022-vm-hjoshi1")
    
    vmi = vm.get_vmi_status()
    print(f"Phase: {vmi['phase']}")
    print(f"Node: {vmi['node']}")
```

### Scale VM Resources

```python
def test_scaling(vut):
    vm = vut("win2022-vm-hjoshi1")
    
    # Scale to 8 CPUs and 32Gi memory
    updated = vm.scale_vm(cpu=8, memory="32Gi")
    
    # Verify
    status = vm.get_vm_status()
    assert status["cpu_cores"] == 8
    assert status["memory"] == "32Gi"
```

### Work with Multiple VMs

```python
def test_multiple_vms(vutCreate):
    # Get access to multiple VMs
    vms = vutCreate("vm-1", "vm-2", "vm-3")
    
    for vm_name, vm in vms.items():
        status = vm.get_vm_status()
        print(f"{vm_name}: CPU={status['cpu_cores']}")
```

## Return Values

### get_vm_status()

Returns a dict with:
```python
{
    "name": str,               # VM name
    "namespace": str,
    "cpu_cores": int,
    "memory": str,             # e.g., "16Gi"
    "running": Optional[bool], # May be None
    "runStrategy": str,        # e.g., "Always"
    "creation_time": str,      # ISO format
}
```

### get_vmi_status()

Returns a dict with:
```python
{
    "name": str,               # VM name
    "phase": str,              # e.g., "Running"
    "node": str,               # K8s node name
    "conditions": list,        # Various conditions
}
```

### scale_vm(cpu, memory)

Returns the updated VM spec dict (or raises exception on failure).

## Common Patterns

### Before/After Testing

```python
def test_before_after(vut):
    vm = vut("my-vm")
    
    # Before state
    before = vm.get_vm_status()
    
    # Do something
    vm.scale_vm(cpu=8, memory="32Gi")
    
    # After state
    after = vm.get_vm_status()
    assert before["cpu_cores"] != after["cpu_cores"]
```

### Scaling with Restoration

```python
def test_scaling_restore(vut):
    vm = vut("my-vm")
    
    # Get original
    original = vm.get_vm_status()
    
    # Scale up
    vm.scale_vm(cpu=8, memory="32Gi")
    
    # Scale back
    vm.scale_vm(cpu=original["cpu_cores"], memory=original["memory"])
```

## SSH/Command Execution

**VUT does NOT include SSH/command execution.**

For SSH access to VMs, use the `sshTunnelConnection` fixture from `tunnel_fixtures.py`:

```python
def test_with_ssh(sshTunnelConnection):
    tunnel = sshTunnelConnection("win2022-vm-hjoshi1")
    result = tunnel.runShell("whoami")
    print(result.stdout)
```

You can also combine both:

```python
def test_combined(vut, sshTunnelConnection):
    # VM management via krkn-lib
    vm = vut("my-vm")
    vm.scale_vm(cpu=8, memory="32Gi")
    
    # SSH commands via tunnel
    tunnel = sshTunnelConnection("my-vm")
    result = tunnel.runShell("Get-Process")
    print(result.stdout)
```

## See Also

- **Full Documentation**: `docs/VUT_FIXTURES.md`
- **Test Examples**: `tests/test_vut.py`
- **Implementation**: `fixtures/vut_fixtures.py`
- **SSH Tunneling**: `fixtures/tunnel_fixtures.py`, `libs/ssh_tunnel.py`

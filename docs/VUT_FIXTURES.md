# VUT Fixtures - VM Under Test

The VUT (VM Under Test) fixture provides a unified interface for:
- **VM Management**: Create, read, update, delete, and scale VMs via krkn-lib
- **SSH Commands**: Execute commands and PowerShell scripts on VMs via virtctl
- **File Transfer**: Upload/download files to/from VMs via virtctl scp

## Architecture

```
test_code
    ↓
VMUnderTest (unified interface)
    ├─ SSH ops → libs/asyncssh_tunnel.py → virtctl ssh/scp commands
    └─ krkn-lib ops → fixtures/krknlib_fixtures.py → Kubernetes custom objects
```

## Quick Start

### Basic Command Execution

```python
def test_vm_operation(vut):
    vm = vut("my-vm-name")
    
    # Run a command
    result = vm.send_cmd("hostname")
    assert result["success"]
    print(result["stdout"])
    
    # Run PowerShell on Windows VMs
    ps_result = vm.run_powershell("Get-Process | Measure-Object | Select -ExpandProperty Count")
    assert ps_result["success"]
```

### File Transfer

```python
def test_file_ops(vut):
    from pathlib import Path
    vm = vut("my-vm-name")
    
    # Upload file
    test_file = Path("/tmp/test.txt")
    test_file.write_text("Hello")
    vm.send_file(test_file, "C:\\temp\\test.txt")  # Windows path
    
    # Download file
    vm.recv_file("C:\\temp\\result.txt", Path("/tmp/result.txt"))
```

### VM Operations (krkn-lib)

```python
def test_vm_crud(vut):
    vm = vut("my-vm-name")
    
    # Get VM status
    status = vm.get_vm_status()
    print(f"CPU: {status['cpu_cores']}, Memory: {status['memory']}")
    
    # Scale VM resources
    updated = vm.scale_vm(cpu=8, memory="32Gi")
    
    # Get running instance status
    vmi_status = vm.get_vmi_status()
    print(f"Phase: {vmi_status['phase']}, Node: {vmi_status['node']}")
```

### Creating Multiple VMs

```python
def test_multiple_vms(vutCreate):
    # Create 2 VMs from templates
    vms = vutCreate("vm-1", "vm-2")
    
    for vm_name, vm in vms.items():
        result = vm.send_cmd("whoami")
        print(f"{vm_name}: {result['stdout']}")
```

## Running Tests

### Prerequisites

1. **Kubernetes cluster** with KubeVirt installed
2. **virtctl** CLI available (v0.59+)
3. **Template VMs** in the cluster (for vutCreate fixture)
4. **SSH key** for VM access at `~/.ssh/openshift-qe.pem`

### Basic Test Run

```bash
# Run all VUT tests
pytest tests/test_vut.py -v

# Run specific test
pytest tests/test_vut.py::TestVUT::test_vut_send_command -v

# With logging
pytest tests/test_vut.py -v --log-cli-level=INFO
```

### Environment Variables

- `KUBECONFIG`: Path to kubeconfig (default: `~/.kube/config`)
- `NAMESPACE`: K8s namespace for VMs (default: `test123`)

### Example Test Setup

To run the example tests, first create test VMs:

```bash
# Create a namespace
oc create ns test123

# Create a base Windows VM (or Linux VM)
# This would be done via KubeVirt manifests in your cluster
# After creating, the tests can reference it by name
```

## Implementation Details

### AsyncVMUnderTest Class

The async core class that wraps virtctl commands:

```python
vm = AsyncVMUnderTest(
    vm_name="win2022-test",
    namespace="test123",
    kubeconfig="/home/user/.kube/config",
    identity_file="/home/user/.ssh/openshift-qe.pem"
)

# All methods are async
await vm.send_cmd("whoami")
await vm.send_file(Path("/local/file"), "/remote/path")
```

### SyncAsyncVMUnderTest Class

Synchronous wrapper for pytest (which doesn't support async fixtures natively):

```python
vm = SyncAsyncVMUnderTest(...)
# Methods are synchronous
vm.send_cmd("whoami")
```

### VMUnderTest Class

High-level unified fixture combining:
- SSH tunnel methods: `send_cmd()`, `run_powershell()`, `send_file()`, `recv_file()`
- krkn-lib methods: `get_vm_status()`, `scale_vm()`, `delete_vm()`

## Known Limitations

1. **No persistent SSH connections**: Each command spawns a new virtctl process (similar to how `oc exec` works)
2. **No shell escaping needed**: Commands are passed directly to virtctl, no shell interpretation
3. **Windows-specific**: Tests assume Windows VMs (Administrator user); Linux VMs would need different credentials
4. **Template-based creation**: `vutCreate()` requires pre-existing template VMs in the cluster

## Troubleshooting

### "virtualmachine.kubevirt.io not found"

The test VM doesn't exist in the cluster. Create it or use a different VM name.

### "Connection closed by UNKNOWN port 65535"

Virtctl SSH is failing - check:
- VM is running: `oc get vm -A`
- SSH key has correct permissions: `chmod 600 ~/.ssh/openshift-qe.pem`
- Administrator user exists on the VM

### SSH Key Not Found

The fixture looks for SSH keys at:
1. `~/.ssh/openshift-qe.pem` (default)
2. Custom path via `vut("vm-name", ssh_key="/path/to/key")`

### "exit status 255"

General SSH/virtctl failure. Check:
- KUBECONFIG is set correctly
- Cluster connectivity: `oc cluster-info`
- virtctl is installed: `which virtctl`

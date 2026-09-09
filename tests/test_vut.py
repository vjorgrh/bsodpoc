"""VUT (VM Under Test) fixture integration tests.

These tests demonstrate the VUT fixture for krkn-lib VM management operations.
Tests use the existing win2022-vm-hjoshi1 VM.

For SSH command execution on VMs, use the sshTunnelConnection fixture from tunnel_fixtures.py.
"""
import logging

import pytest

logs = logging.getLogger()


@pytest.mark.krkn
class TestVUT:
    """Test VUT fixture: krkn-lib VM management (status, scaling, deletion)."""

    def test_vut_get_vm_status(self, vut):
        """Test getting VM configuration via krkn-lib."""
        vm = vut("win2022-vm-hjoshi1")

        status = vm.get_vm_status()
        assert status["name"] == "win2022-vm-hjoshi1"
        assert status["cpu_cores"] > 0
        assert status["memory"] is not None
        assert status["runStrategy"] is not None

        logs.info(f"✓ VM status: {status['name']}, CPUs={status['cpu_cores']}, Memory={status['memory']}, RunStrategy={status['runStrategy']}")

    def test_vut_get_vmi_status(self, vut):
        """Test getting VMInstance (running) status via krkn-lib."""
        vm = vut("win2022-vm-hjoshi1")

        vmi_status = vm.get_vmi_status()
        assert vmi_status["name"] == "win2022-vm-hjoshi1"
        assert vmi_status["phase"] == "Running"
        assert vmi_status["node"] is not None

        logs.info(f"✓ VMI status: phase={vmi_status['phase']}, node={vmi_status['node']}")

    def test_vut_vm_specs(self, vut):
        """Test VM specs and verify they are accessible."""
        vm = vut("win2022-vm-hjoshi1")

        status = vm.get_vm_status()

        # Verify basic properties are present
        assert status["namespace"] is not None
        assert status["cpu_cores"] > 0
        assert status["memory"] is not None
        assert status["runStrategy"] is not None
        assert status["creation_time"] is not None

        logs.info(f"✓ VM fully accessible:")
        logs.info(f"  Name: {status['name']}")
        logs.info(f"  Namespace: {status['namespace']}")
        logs.info(f"  CPUs: {status['cpu_cores']}")
        logs.info(f"  Memory: {status['memory']}")
        logs.info(f"  RunStrategy: {status['runStrategy']}")
        logs.info(f"  Running: {status['running']}")

    def test_vut_scale_vm(self, vut):
        """Test scaling VM resources via krkn-lib.

        Note: This test scales the VM to 8 cores/32Gi.
        Original resources will be restored after test (via conftest cleanup).
        """
        vm = vut("win2022-vm-hjoshi1")

        # Get original state
        original = vm.get_vm_status()
        original_cpu = original["cpu_cores"]
        original_memory = original["memory"]

        logs.info(f"Original: CPU={original_cpu}, Memory={original_memory}")

        # Scale up
        updated = vm.scale_vm(cpu=8, memory="32Gi")
        assert updated is not None
        logs.info(f"✓ VM scaled to CPU=8, Memory=32Gi")

        # Verify scaling via status query
        new_status = vm.get_vm_status()
        assert new_status["cpu_cores"] == 8
        assert new_status["memory"] == "32Gi"
        logs.info(f"✓ Verified: CPU={new_status['cpu_cores']}, Memory={new_status['memory']}")

        # Scale back to original
        restored = vm.scale_vm(cpu=original_cpu, memory=original_memory)
        logs.info(f"✓ Restored to original: CPU={original_cpu}, Memory={original_memory}")

    def test_vut_multiple_vms(self, vutCreate):
        """Test getting VUT access to multiple VMs."""
        # Get access to VMs (they must exist in cluster)
        vms = vutCreate("win2022-vm-hjoshi1")

        # Check we got the VM
        assert len(vms) == 1
        assert "win2022-vm-hjoshi1" in vms

        # Query status on each
        for vm_name, vm in vms.items():
            status = vm.get_vm_status()
            assert status["cpu_cores"] > 0
            logs.info(f"✓ {vm_name}: CPU={status['cpu_cores']}, Memory={status['memory']}")

    def test_vut_integration_status_scaling(self, vut):
        """Test integrated workflow: get status, scale, verify."""
        vm = vut("win2022-vm-hjoshi1")

        # Step 1: Get initial status
        initial = vm.get_vm_status()
        logs.info(f"1. Initial status: {initial['name']}, CPU={initial['cpu_cores']}")

        # Step 2: Get running instance info
        vmi = vm.get_vmi_status()
        logs.info(f"2. Running on node: {vmi['node']}")

        # Step 3: Scale to new resources
        scaled = vm.scale_vm(cpu=6, memory="24Gi")
        logs.info(f"3. Scaled to CPU=6, Memory=24Gi")

        # Step 4: Verify new resources
        final = vm.get_vm_status()
        assert final["cpu_cores"] == 6
        assert final["memory"] == "24Gi"
        logs.info(f"4. Verified: CPU={final['cpu_cores']}, Memory={final['memory']}")

        # Step 5: Restore original
        vm.scale_vm(cpu=initial["cpu_cores"], memory=initial["memory"])
        logs.info(f"5. Restored to original: CPU={initial['cpu_cores']}, Memory={initial['memory']}")

"""VM CRUD operations tests using krkn-lib and KubeVirt."""
import logging
import pytest
import time

logs = logging.getLogger()


@pytest.mark.krkn(namespace="windows-bsod")
class TestVMCRUD:
    """Test CRUD operations for VMs via krkn-lib."""

    def test_create_vm_clone(self, krknChaos):
        """Create a new VM by cloning the existing template VM."""
        clone_name = "win2022-vm-clone-1"

        # CREATE: Clone the existing VM
        created_vm = krknChaos.create_vm_from_template(
            clone_name=clone_name,
            base_vm="win2022-vm-hjoshi1",
            cpu=4,
            memory="16Gi"
        )

        assert created_vm is not None, "VM creation failed"
        assert created_vm["metadata"]["name"] == clone_name
        logs.info(f"✓ VM {clone_name} created successfully")

    def test_create_dv_clone(self, krknChaos):
        """Create a new DataVolume by cloning the existing template DV."""
        clone_name = "win2022-dv-clone-1"

        # CREATE: Clone the existing DV
        created_dv = krknChaos.create_dv_from_template(
            clone_name=clone_name,
            base_dv="win2022-dv-hjoshi1",
            size="120Gi"
        )

        assert created_dv is not None, "DV creation failed"
        assert created_dv["metadata"]["name"] == clone_name
        logs.info(f"✓ DV {clone_name} created successfully")

    def test_read_vm_status(self, krknChaos):
        """Read and verify VM configuration and status."""
        vm_name = "win2022-vm-hjoshi1"

        # READ: Get VM status
        status = krknChaos.get_vm_status(vm_name)

        assert status["name"] == vm_name
        assert status["cpu_cores"] > 0, "CPU cores should be > 0"
        assert status["memory"] is not None, "Memory should be set"
        assert status["runStrategy"] == "Always"
        logs.info(f"✓ VM {vm_name} status verified: CPU={status['cpu_cores']}, Memory={status['memory']}")

    def test_read_vmi_status(self, krknChaos):
        """Read VMInstance (runtime) status."""
        vm_name = "win2022-vm-hjoshi1"

        # READ: Get VMI status (if VM is running)
        vmi_status = krknChaos.get_vmi_status(vm_name)

        assert vmi_status is not None
        logs.info(f"✓ VMI {vm_name} phase: {vmi_status.get('phase', 'Unknown')}")

        if vmi_status.get("phase") == "Running":
            assert vmi_status.get("node") is not None, "Running VM should be assigned to a node"
            logs.info(f"✓ VMI running on node: {vmi_status['node']}")

    def test_scale_vm_cpu(self, krknChaos):
        """Scale VM CPU resources."""
        clone_name = "win2022-vm-scale-cpu-1"

        # CREATE: Clone the VM for scaling test
        krknChaos.create_vm_from_template(clone_name=clone_name, cpu=2, memory="8Gi")

        # UPDATE: Scale CPU from 2 to 4
        updated_vm = krknChaos.scale_vm_resources(
            vm_name=clone_name,
            cpu=4,
            namespace="windows-bsod"
        )

        assert updated_vm["spec"]["template"]["spec"]["domain"]["cpu"]["cores"] == 4
        logs.info(f"✓ VM {clone_name} CPU scaled to 4 cores")

    def test_scale_vm_memory(self, krknChaos):
        """Scale VM memory resources."""
        clone_name = "win2022-vm-scale-mem-1"

        # CREATE: Clone the VM for scaling test
        krknChaos.create_vm_from_template(clone_name=clone_name, cpu=4, memory="8Gi")

        # UPDATE: Scale memory from 8Gi to 16Gi
        updated_vm = krknChaos.scale_vm_resources(
            vm_name=clone_name,
            memory="16Gi",
            namespace="windows-bsod"
        )

        assert updated_vm["spec"]["template"]["spec"]["domain"]["memory"]["guest"] == "16Gi"
        logs.info(f"✓ VM {clone_name} memory scaled to 16Gi")

    def test_scale_vm_cpu_and_memory(self, krknChaos):
        """Scale both CPU and memory resources simultaneously."""
        clone_name = "win2022-vm-scale-both-1"

        # CREATE: Clone the VM
        krknChaos.create_vm_from_template(clone_name=clone_name, cpu=2, memory="4Gi")

        # UPDATE: Scale both CPU and memory
        updated_vm = krknChaos.scale_vm_resources(
            vm_name=clone_name,
            cpu=8,
            memory="32Gi",
            namespace="windows-bsod"
        )

        assert updated_vm["spec"]["template"]["spec"]["domain"]["cpu"]["cores"] == 8
        assert updated_vm["spec"]["template"]["spec"]["domain"]["memory"]["guest"] == "32Gi"
        logs.info(f"✓ VM {clone_name} scaled: CPU=8, Memory=32Gi")

    def test_delete_vm(self, krknChaos):
        """Delete a VM."""
        clone_name = "win2022-vm-delete-1"

        # CREATE: Clone the VM
        krknChaos.create_vm_from_template(clone_name=clone_name)

        # DELETE: Remove the VM
        deleted = krknChaos.delete_vm(vm_name=clone_name, namespace="windows-bsod")

        assert deleted is True, "VM deletion failed"
        logs.info(f"✓ VM {clone_name} deleted successfully")

    def test_delete_dv(self, krknChaos):
        """Delete a DataVolume."""
        clone_name = "win2022-dv-delete-1"

        # CREATE: Clone the DV
        krknChaos.create_dv_from_template(clone_name=clone_name)

        # DELETE: Remove the DV
        deleted = krknChaos.delete_dv(dv_name=clone_name, namespace="windows-bsod")

        assert deleted is True, "DV deletion failed"
        logs.info(f"✓ DV {clone_name} deleted successfully")

    def test_vm_lifecycle_complete(self, krknChaos):
        """Complete VM lifecycle: CREATE → READ → UPDATE → DELETE."""
        clone_name = "win2022-vm-lifecycle-1"
        dv_name = "win2022-dv-lifecycle-1"

        # PHASE 1: CREATE
        logs.info("═" * 60)
        logs.info("PHASE 1: CREATE")
        logs.info("═" * 60)

        krknChaos.create_dv_from_template(clone_name=dv_name, size="120Gi")
        krknChaos.create_vm_from_template(clone_name=clone_name, cpu=2, memory="8Gi")
        logs.info(f"✓ Created VM {clone_name} and DV {dv_name}")

        # PHASE 2: READ
        logs.info("═" * 60)
        logs.info("PHASE 2: READ")
        logs.info("═" * 60)

        status = krknChaos.get_vm_status(clone_name)
        assert status["cpu_cores"] == 2
        assert status["memory"] == "8Gi"
        logs.info(f"✓ Verified VM status: CPU={status['cpu_cores']}, Memory={status['memory']}")

        # PHASE 3: UPDATE
        logs.info("═" * 60)
        logs.info("PHASE 3: UPDATE (SCALE)")
        logs.info("═" * 60)

        krknChaos.scale_vm_resources(vm_name=clone_name, cpu=4, memory="16Gi")
        updated_status = krknChaos.get_vm_status(clone_name)
        assert updated_status["cpu_cores"] == 4
        assert updated_status["memory"] == "16Gi"
        logs.info(f"✓ Scaled VM: CPU=4, Memory=16Gi")

        # PHASE 4: DELETE
        logs.info("═" * 60)
        logs.info("PHASE 4: DELETE")
        logs.info("═" * 60)

        krknChaos.delete_vm(vm_name=clone_name)
        krknChaos.delete_dv(dv_name=dv_name)
        logs.info(f"✓ Deleted VM {clone_name} and DV {dv_name}")

        logs.info("═" * 60)
        logs.info("✓ COMPLETE LIFECYCLE TEST PASSED")
        logs.info("═" * 60)

    def test_create_multiple_vms(self, krknChaos):
        """Create multiple VMs at once (scaling test)."""
        num_clones = 3
        clone_names = [f"win2022-vm-multi-{i+1}" for i in range(num_clones)]

        logs.info(f"Creating {num_clones} VM clones...")

        # CREATE: Multiple VMs
        for clone_name in clone_names:
            krknChaos.create_vm_from_template(
                clone_name=clone_name,
                cpu=2,
                memory="8Gi"
            )

        logs.info(f"✓ Created {num_clones} VMs successfully")

        # VERIFY: Read status of all created VMs
        for clone_name in clone_names:
            status = krknChaos.get_vm_status(clone_name)
            assert status["cpu_cores"] == 2
            assert status["memory"] == "8Gi"

        logs.info(f"✓ Verified all {num_clones} VMs are correctly configured")

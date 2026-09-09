"""VUT (VM Under Test) fixture: krkn-lib VM management (CRUD, status, scaling).

For SSH tunnel access to VMs, use the sshTunnelConnection fixture from tunnel_fixtures.py.
This fixture focuses on krkn-lib operations: get_vm_status, scale_vm, delete_vm, etc.
"""
import logging
from typing import Optional

import pytest

from fixtures.krknlib_fixtures import KrknContext

logs = logging.getLogger()


class VMUnderTest:
    """VUT: krkn-lib VM management interface (status, scaling, deletion)."""

    def __init__(
        self,
        vm_name: str,
        namespace: str,
        krknChaos: KrknContext,
    ) -> None:
        self.vm_name = vm_name
        self.namespace = namespace
        self.krknChaos = krknChaos

    # ─────────────────────────────────────────────────────────────────
    # VM Status Operations
    # ─────────────────────────────────────────────────────────────────

    def get_vm_status(self) -> dict:
        """Get VM configuration status (CPU, memory, running state, etc.)."""
        logs.info(f"[{self.vm_name}] Getting VM status")
        return self.krknChaos.get_vm_status(self.vm_name, self.namespace)

    def get_vmi_status(self) -> dict:
        """Get VMInstance (running) status (phase, node, conditions)."""
        logs.info(f"[{self.vm_name}] Getting VMI status")
        return self.krknChaos.get_vmi_status(self.vm_name, self.namespace)

    # ─────────────────────────────────────────────────────────────────
    # VM Management Operations
    # ─────────────────────────────────────────────────────────────────

    def scale_vm(self, cpu: Optional[int] = None, memory: Optional[str] = None) -> dict:
        """Scale VM resources (CPU cores and/or memory)."""
        logs.info(f"[{self.vm_name}] Scaling: CPU={cpu}, Memory={memory}")
        return self.krknChaos.scale_vm_resources(
            vm_name=self.vm_name,
            cpu=cpu,
            memory=memory,
            namespace=self.namespace,
        )

    def delete_vm(self) -> bool:
        """Delete VM with graceful termination."""
        logs.info(f"[{self.vm_name}] Deleting VM")
        return self.krknChaos.delete_vm(self.vm_name, self.namespace)


@pytest.fixture
def vut(krknChaos):
    """VUT fixture: Create VM management objects for testing.

    Usage:
        def test_vm_status(vut):
            vm = vut("my-vm-name")
            status = vm.get_vm_status()
            assert status["running"] == True
    """
    vuts: list[VMUnderTest] = []

    def _make(
        vm_name: str,
        namespace: Optional[str] = None,
    ) -> VMUnderTest:
        namespace = namespace or "windows-bsod"

        vm_under_test = VMUnderTest(
            vm_name=vm_name,
            namespace=namespace,
            krknChaos=krknChaos,
        )

        vuts.append(vm_under_test)
        logs.info(f"Created VUT for {vm_name}")
        return vm_under_test

    yield _make

    # Cleanup: close any resources (currently none, but kept for extensibility)
    for vm in vuts:
        try:
            pass  # No cleanup needed for krkn-lib wrapper
        except Exception as e:
            logs.warning(f"Error cleaning up VUT: {e}")


@pytest.fixture
def vutCreate(vut):
    """Get VUT access to multiple existing VMs.

    Usage:
        def test_multiple_vms(vutCreate):
            vms = vutCreate("vm-1", "vm-2", "vm-3")
            for vm_name, vm in vms.items():
                status = vm.get_vm_status()
                print(f"{vm_name}: {status}")
    """

    def _get_vms(*vm_names: str) -> dict:
        vms_by_name = {}
        for vm_name in vm_names:
            vm_under_test = vut(vm_name)
            vms_by_name[vm_name] = vm_under_test
            logs.info(f"✓ Got VUT for existing VM {vm_name}")
        return vms_by_name

    return _get_vms

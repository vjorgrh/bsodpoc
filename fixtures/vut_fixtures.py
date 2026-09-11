"""VUT (VM Under Test) fixture: krkn-lib VM management (CRUD, status, scaling).

For SSH tunnel access to VMs, use the sshTunnelConnection fixture from tunnel_fixtures.py.
This fixture focuses on krkn-lib operations: get_vm_status, scale_vm, delete_vm, etc.
"""
import logging
from typing import Optional

import pytest

from libs.vmundertest import VmUnderTest

logs = logging.getLogger()


@pytest.fixture
def vut(krknChaos):
    """VUT fixture: Create VM management objects for testing.

    Usage:
        def test_vm_status(vut):
            vm = vut("my-vm-name")
            status = vm.get_vm_status()
            assert status["running"] == True
    """
    vuts: list[VmUnderTest] = []

    def _make(
        vm_name: str,
        namespace: Optional[str] = None,
    ) -> VmUnderTest:
        from libs.common import DEFAULT_NAMESPACE
        namespace = namespace or DEFAULT_NAMESPACE

        vm_under_test = VmUnderTest(
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

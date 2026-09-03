import pytest
import logging

from libs.vm import VirtctlSSH

logs = logging.getLogger()

class TestExample():
     """Test class for BSOD tests"""

     @pytest.mark.bsod
     @pytest.mark.parametrize("vm_create", [2], indirect=True)
     def test_vm_create(self, vm_create):
         created_vms = vm_create
         for vm_name in created_vms:
            logs.info(f"vm created: {vm_name}")

         # The fixture was asked (via parametrize) to create 2 VMs; assert it did.
         assert len(created_vms) == 2, f"expected 2 VMs created, got {len(created_vms)}: {created_vms}"

         # Sanity-check guest reachability on the persistent VM via virtctl ssh.
         winSsh = VirtctlSSH(
                    vmName="hjoshi-win2022",
                    namespace="windows-bsod",
                    username="Administrator",
                    identityFile="~/.ssh/id_ed25519",
                   )
         info = winSsh.executeRemoteCommand(remoteCmd="powershell Get-Service -Name sshd")
         assert info.success, f"virtctl ssh failed: {info.stderr}"
         assert "Running" in info.stdout, f"sshd not Running on guest: {info.stdout!r}"

import pytest
import logging

from libs.vm import VirtctlSSH

logs = logging.getLogger()

class TestExample():
     """Test class for BSOD tests"""

     @pytest.mark.bsod
     @pytest.mark.parametrize("vm_create", [2], indirect=True)
     def test_vm_create(self, vm_create):
         logs.info("This is first test")
         created_vms = vm_create
         for vm_name in created_vms:
            logs.info(f"vm created: {vm_name}")

         winSsh = VirtctlSSH(
                    vmName="hjoshi-win2022",
                    namespace="windows-bsod",
                    username="Administrator",
                    identityFile="~/.ssh/id_ed25519",
                   )
         info = winSsh.executeRemoteCommand(remoteCmd="powershell Get-Service -Name sshd")
         if info.success:
            logs.info(info.stdout)

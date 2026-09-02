import pytest
import logging
import traceback
import os

from src.vm import VirtctlSSH

logs = logging.getLogger()

class TestExample():
     """Test class for BSOD tests"""

     @pytest.mark.bsod
     #@pytest.mark.parametrize("vm_create", [2], indirect=True)
     def test_vm_create(self, vm_create):
         logs.info("This is first test")
         #results =  vm_create
         #for k,v in results.items():
         #   logs.info(f"vm name: {k}, status: {v.stdout}") 
         win_ssh = VirtctlSSH(
                    vm_name="win2022-vm-vvijay11",
                    namespace="windows-bsod",
                    username="Administrator",
                    identity_file="~/.ssh/id_ed25519",
                   ) 
         info = win_ssh.execute_remote_command(remote_cmd="powershell Get-Service -Name sshd")
         if info.success:
            logs.info(info.stdout) 

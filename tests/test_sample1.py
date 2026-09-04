import pytest
import logging
    @pytest.mark.check
     def test_vm_create_tunnel(self, ssh_tunnel_connection):
         logs.info("This is tunnel check test")
         tunnel = ssh_tunnel_connection("win2022-vm-vvijay11","windows-bsod")

         start = time.perf_counter()
         result = tunnel.run_powershell("Get-ComputerInfo | Select-Object CsName")
         end = time.perf_counter()
         logs.info(f"Time took to execute: {end-start}")
         assert result.success
         logs.info(result.stdout)

         start = time.perf_counter()
         result = tunnel.run_powershell("Get-ComputerInfo | Select-Object CsName")
         end = time.perf_counter()
         logs.info(f"Time took to execute: {end-start}")
         assert result.success
         logs.info(f"Tunnel:{result.stdout}")

         start = time.perf_counter()
         result = tunnel.send("/Users/vvijay/scripts/guest/churn.ps1","C:/scripts/")
         end = time.perf_counter()
         logs.info(f"Time took to execute: {end-start}")
         assert result.success

         start = time.perf_counter()
         result = tunnel.receive("C:/scripts/churn.ps1", "/Users/vvijay/scripts/check")
         end = time.perf_counter()
         logs.info(f"Time took to execute: {end-start}")
         assert result.success
import traceback
import os
import time

logs = logging.getLogger()

class TestExample():
     """Test class for BSOD tests"""

     @pytest.mark.bsod
     @pytest.mark.parametrize("vm_create", [(2,"windows-bsod"),], indirect=True)
     def test_vm_create(self, vm_create):
         results =  vm_create
         for k,v in results.items():
            logs.info(f"vm name: {k}, status: {v.stdout}")
         win_ssh = VirtctlSSH(
                    vm_name="win2022-vm-vvijay11",
                    namespace="windows-bsod",
                    username="Administrator",
                    identity_file="~/.ssh/openshift-qe.pem",
                   )
         info = win_ssh.execute_remote_command(remote_cmd="powershell Get-Service -Name sshd")
         if info.success:
            logs.info(info.stdout)

     @pytest.mark.tunnel
     @pytest.mark.parametrize("vm_create", [(2,"windows-bsod"),], indirect=True)
     def test_vm_tunnel(self, vm_with_tunnel):
         logs.info("This is tunnel test")
         for vm_name, tunnel in vm_with_tunnel.items():
            result = tunnel.run_powershell("Get-ComputerInfo | Select-Object CsName")
            assert result.success
            result = tunnel.send("/Users/vvijay/scripts/guest/churn.ps1","C:/scripts/")
            assert result.success
            result = tunnel.receive("C:/scripts/churn.ps1", "/Users/vvijay/scripts/check")
            assert result.success

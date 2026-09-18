import pytest
import logging
import time

from libs.OpenShift.LP.Virt.VM.VM import VirtctlSSH

logs = logging.getLogger()

# vvijay's tunnel scenarios below reference paths on their own workstation
# (/Users/vvijay/...) and the VM 'win2022-vm-vvijay11', which is not present on
# the cluster (the running one is 'win2022-vm-vvijay1'). Skipped until those are
# parameterised; drop the marker once they point at real, shared locations.
TUNNEL_SKIP_REASON = (
    "needs vvijay's local script paths and the win2022-vm-vvijay11 VM; "
    'unskip once both are parameterised'
)

class TestExample():
     '''Test class for BSOD tests'''

     @pytest.mark.bsod
     @pytest.mark.parametrize('vmCreate', [(2, 'benchmark-runner')], indirect=True)
     def test_VmCreate(self, vmCreate):
         results = vmCreate
         for vmName, status in results.items():
            logs.info(f'vm name: {vmName}, status: {status.stdout}')

         # The fixture was asked (via parametrize) to create 2 VMs; assert it did.
         assert len(results) == 2, f'expected 2 VMs created, got {len(results)}: {list(results)}'

         # Sanity-check guest reachability on the persistent VM via virtctl ssh.
         winSsh = VirtctlSSH(
                    vmName='hjoshi-win2022',
                    namespace='windows-bsod',
                    username='Administrator',
                    identityFile='~/.ssh/id_ed25519',
                   )
         info = winSsh.ExecuteRemoteCommand(remoteCmd='powershell Get-Service -Name sshd')
         assert info.success, f'virtctl ssh failed: {info.stderr}'
         assert 'Running' in info.stdout, f'sshd not Running on guest: {info.stdout!r}'

     @pytest.mark.check
     @pytest.mark.skip(reason=TUNNEL_SKIP_REASON)
     def test_VmCreateTunnel(self, sshTunnelConnection):
         '''Times repeated PowerShell calls over one reused ControlMaster tunnel.'''
         logs.info('This is tunnel check test')
         tunnel = sshTunnelConnection('win2022-vm-vvijay11', 'benchmark-runner')

         start = time.perf_counter()
         result = tunnel.RunPowerShell('Get-ComputerInfo | Select-Object CsName')
         end = time.perf_counter()
         logs.info(f'Time took to execute: {end-start}')
         assert result.success
         logs.info(result.stdout)

         start = time.perf_counter()
         result = tunnel.RunPowerShell('Get-ComputerInfo | Select-Object CsName')
         end = time.perf_counter()
         logs.info(f'Time took to execute: {end-start}')
         assert result.success
         logs.info(f'Tunnel:{result.stdout}')

         start = time.perf_counter()
         result = tunnel.Send('/Users/vvijay/scripts/guest/churn.ps1', 'C:/scripts/')
         end = time.perf_counter()
         logs.info(f'Time took to execute: {end-start}')
         assert result.success

         start = time.perf_counter()
         result = tunnel.Recv('C:/scripts/churn.ps1', '/Users/vvijay/scripts/check')
         end = time.perf_counter()
         logs.info(f'Time took to execute: {end-start}')
         assert result.success

     @pytest.mark.benchmark
     @pytest.mark.parametrize('windowsVMScale', [2], indirect=True)
     def test_CreateVmsTunnel(self, vmTunnel):
        for vmName, tunnel in vmTunnel.items():
             logs.info(f'vm name: {vmName}')
             logs.info(f'tunnel: {tunnel}')

'''SSH tunnel fixtures for reaching into Windows guests via virtctl.'''
import logging
import os
from pathlib import Path
from typing import Optional

import pytest

from libs.utils.CmdExec import CmdExec
from libs.OpenShift.LP.Virt.VM.RHOVssh import RHOVsshCon
from fixtures.common import DEFAULT_NAMESPACE

logs = logging.getLogger()


def FindVirtctlPath(runner: Optional[CmdExec] = None) -> str:
    '''Resolves the absolute path to the virtctl binary on PATH.'''
    runner = runner or CmdExec()
    result = runner.Run(['which', 'virtctl'])
    logs.info(f'virtctl path: {result.stdout}')
    if not result.success:
        raise FileNotFoundError('virtctl not found on PATH')
    return result.stdout


@pytest.fixture
def sshTunnelConnection(request):
    '''Creates RHOVsshCon instances for VMs under test; closes them all at teardown.'''
    tunnels: list[RHOVsshCon] = []

    def _make(
        vmName: str = '',
        namespace: str = DEFAULT_NAMESPACE,
        idFile: Optional[str] = None,
        user: str = 'Administrator',
        identityFile: Optional[Path] = None,
        **kwargs,
    ) -> RHOVsshCon:
        vm = kwargs.get('host', vmName)
        keyPath = idFile or (str(identityFile) if identityFile else os.path.expanduser('~/.ssh/id_ed25519'))
        tunnel = RHOVsshCon(
            ns=kwargs.get('ns', namespace),
            host=vm,
            user=user,
            idFile=keyPath,
            binPath=FindVirtctlPath(),
            kubeconfig=os.environ.get('KUBECONFIG'),
        )
        tunnels.append(tunnel)
        return tunnel

    yield _make

    for tunnel in tunnels:
        tunnel.Close()


@pytest.fixture
def vmWithTunnel(vmCreate, sshTunnelConnection):
    '''Composes vmCreate + sshTunnelConnection: one SSH tunnel per created VM.'''
    return {vmName: sshTunnelConnection(vmName) for vmName in vmCreate}

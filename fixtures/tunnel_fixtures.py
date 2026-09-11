"""SSH tunnel fixtures for reaching into Windows guests via virtctl."""
import logging
import os
from pathlib import Path
from typing import Optional

import pytest

from libs.command_runner import CommandRunner
from libs.ssh_tunnel import VirtctlSshTunnel
from fixtures.common import DEFAULT_NAMESPACE

logs = logging.getLogger()


def findVirtctlPath(runner: Optional[CommandRunner] = None) -> str:
    """Resolves the absolute path to the virtctl binary on PATH."""
    runner = runner or CommandRunner()
    result = runner.run(["which", "virtctl"], retries=0)
    logs.info(f"virtctl path: {result.stdout}")
    if not result.success:
        raise FileNotFoundError("virtctl not found on PATH")
    return result.stdout


@pytest.fixture
def sshTunnelConnection(request):
    """Creates VirtctlSshTunnel instances for VMs under test; closes them all at teardown."""
    tunnels: list[VirtctlSshTunnel] = []

    def _make(identityFile: Path, vmName: str, namespace: str = DEFAULT_NAMESPACE) -> VirtctlSshTunnel:
        tunnel = VirtctlSshTunnel(
            target=f"Administrator@vm/{vmName}",
            namespace=namespace,
            identityFile=str(identityFile),
            binPath=findVirtctlPath(),
            kubeconfig=os.environ.get("KUBECONFIG"),
        )
        tunnels.append(tunnel)
        return tunnel

    yield _make

    for tunnel in tunnels:
        tunnel.close()


@pytest.fixture
def vmWithTunnel(vmCreate, sshTunnelConnection):
    """Composes vmCreate + sshTunnelConnection: one SSH tunnel per created VM."""
    return {vmName: sshTunnelConnection(vmName) for vmName in vmCreate}

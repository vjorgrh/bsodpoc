from pathlib import Path
import pytest
import logging
import random
import os
import time

from libs.command_runner import CommandRunner
from libs.yaml_parser import ConfigLoader
from libs.ssh_tunnel import VirtctlSshTunnel

logs = logging.getLogger()

@pytest.fixture(scope="function")
def vm_create(request):
    results = {}
    runner = CommandRunner()
    vm_config = request.config.rootpath / "config" / "vm-config-tlbflush-on.yaml"
    logs.info(f"Creating VM from this config: {vm_config}")
    count, namespace = request.param
    for i in range(count):
        vm_name = "bsod-auto-" + str(random.randint(1,15))
        context_variables = {"VM_NAME": vm_name}
        replaced_config = request.config.rootpath / "replaced_config" / Path(vm_name).with_suffix(".yaml") 
        ConfigLoader.load_and_save(vm_config, replaced_config, context_variables)
        create = runner.run(f"oc apply -f {replaced_config}", shell=True)
        if create.success:
           logs.info(f"VM created with name {vm_name}")
           time.sleep(10)
           results[vm_name] = runner.run(f"oc get vm/{vm_name}  -n {namespace} -o custom-columns=\"STATUS:.status.printableStatus\" --no-headers", shell=True)
    yield results


def find_virtctl_path(runner: CommandRunner | None = None) -> str:
    """Resolves the absolute path to the virtctl binary on PATH."""
    runner = runner or CommandRunner()
    result = runner.run(["which", "virtctl"], retries=0)
    logs.info(f"virtctl path: {result.stdout}")
    if not result.success:
        raise FileNotFoundError("virtctl not found on PATH")
    return result.stdout


@pytest.fixture
def ssh_tunnel_connection(request):
    """Creates VirtctlSshTunnel instances for VMs under test; closes them all at teardown."""
    tunnels: list[VirtctlSshTunnel] = []

    def _make(vm_name: str, namespace: str) -> VirtctlSshTunnel:
        tunnel = VirtctlSshTunnel(
            target=f"Administrator@vm/{vm_name}",
            namespace=namespace,
            identity_file=str(Path.home() / ".ssh" / "id_ed25519"),
            bin_path=find_virtctl_path(),
            kubeconfig=os.environ.get("KUBECONFIG"),
        )
        tunnels.append(tunnel)
        return tunnel

    yield _make

    for tunnel in tunnels:
        tunnel.close()

@pytest.fixture
def vm_with_tunnel(vm_create, ssh_tunnel_connection):
    """Composes vm_create + ssh_tunnel_connection: one SSH tunnel per created VM."""
    return {vm_name: ssh_tunnel_connection(vm_name) for vm_name in vm_create}

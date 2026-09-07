from pathlib import Path
from typing import NamedTuple, Any, Dict, Optional, Tuple, Union
import pytest
import logging
import random
import os
import time

from libs.command_runner import CommandRunner
from libs.yaml_parser import ConfigLoader
from libs.ssh_tunnel import VirtctlSshTunnel

logs = logging.getLogger()

# Every VM in this POC lives here; used as the fallback whenever a fixture or
# marker does not name a namespace explicitly.
DEFAULT_NAMESPACE = "windows-bsod"


@pytest.fixture(scope="function")
def vm_create(request):
    """Create N VMs from the templated config and yield their names + status.

    Parametrise indirectly with a ``(count, namespace)`` tuple::

        @pytest.mark.parametrize("vm_create", [(2, "windows-bsod")], indirect=True)

    A bare int is also accepted and falls back to ``DEFAULT_NAMESPACE``.

    :return: dict mapping the created VM name to the ``CommandResult`` of its
        status lookup. Iterating the dict yields the VM names.
    """
    results = {}
    runner = CommandRunner()
    vm_config = request.config.rootpath / "config" / "vm-config-tlbflush-on.yaml"
    logs.info(f"Creating VM from this config: {vm_config}")

    # Accept both (count, namespace) and a bare count.
    param = getattr(request, "param", (1, DEFAULT_NAMESPACE))
    count, namespace = (param, DEFAULT_NAMESPACE) if isinstance(param, int) else param

    for _ in range(count):
        vm_name = f"bsod-auto-{random.randint(100, 999)}"
        context_variables = {"VM_NAME": vm_name}
        replaced_config = request.config.rootpath / "replaced_config" / Path(vm_name).with_suffix(".yaml")

        # Fixed method call from load_and_save to loadAndSave
        ConfigLoader.loadAndSave(vm_config, replaced_config, context_variables)

        create = runner.run(f"oc apply -f {replaced_config}", shell=True)
        if create.success:
            logs.info(f"VM created with name {vm_name}")
            time.sleep(10)
            results[vm_name] = runner.run(
                f"oc get vm/{vm_name} -n {namespace} "
                f"-o custom-columns=\"STATUS:.status.printableStatus\" --no-headers",
                shell=True,
            )

    yield results

    # Teardown logic
    for vm_name in results:
        logs.info(f"Cleaning up VM {vm_name}")
        runner.run(f"oc delete vm {vm_name} -n {namespace}", shell=True)


# Repo-wide defaults for krkn chaos scenarios. A test's @pytest.mark.krkn(...)
# only needs to declare what differs; anything omitted falls back to these.
KRKN_DEFAULTS: Dict[str, Any] = {
    "namespace": DEFAULT_NAMESPACE,
    "vmName": "hjoshi-win2022",
    "recoverTimeout": 300,
}


class KrknContext(NamedTuple):
    """Bundle handed to a test: the krkn-lib client plus the marker's parameters."""
    client: Any                 # krkn_lib.k8s.KrknKubernetes instance
    params: Dict[str, Any]      # KRKN_DEFAULTS merged with @pytest.mark.krkn(...) kwargs


@pytest.fixture(scope="function")
def krknChaos(request):
    """Provide a krkn-lib chaos client to a test and read its @pytest.mark.krkn(...) params.

    Pair this fixture with the custom ``krkn`` marker: the marker *declares* which
    chaos scenario a test wants (and any parameters), and this fixture *builds the
    client* the test uses to run it, e.g.::

        @pytest.mark.krkn(scenario="pod-kill", labelSelector="kubevirt.io=virt-launcher")
        def test_vmSurvivesVirtLauncherKill(self, vmCreate, krknChaos):
            client = krknChaos.client            # krkn_lib KrknKubernetes
            scenario = krknChaos.params["scenario"]
            ...

    The scenario logic itself (select pods -> kill -> wait -> assert recovery) is
    written in the test on top of krkn-lib primitives such as
    ``client.select_pods_by_label(...)`` and ``client.delete_pod(...)``.
    """
    # Import lazily so the rest of the suite still collects when krkn-lib is absent.
    from krkn_lib.k8s import KrknKubernetes

    marker = request.node.get_closest_marker("krkn")
    # Marker kwargs override the repo-wide defaults; a test declares only the diff.
    params = {**KRKN_DEFAULTS, **(marker.kwargs if marker else {})}

    kubeconfigPath = os.environ.get("KUBECONFIG") or os.path.expanduser("~/.kube/config")
    logs.info(f"Initialising krkn-lib client with kubeconfig: {kubeconfigPath}")
    client = KrknKubernetes(kubeconfig_path=kubeconfigPath)

    yield KrknContext(client=client, params=params)

    # Teardown: scenario-specific state restoration belongs to the individual test
    # (this fixture only provides the client + params, per "fixture + marker only").
    logs.info("krknChaos fixture teardown complete")


def findVirtctlPath(runner: Optional[CommandRunner] = None) -> str:
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

    def _make(vmName: str, namespace: str = DEFAULT_NAMESPACE) -> VirtctlSshTunnel:
        tunnel = VirtctlSshTunnel(
            target=f"Administrator@vm/{vmName}",
            namespace=namespace,
            identityFile=str(Path.home() / ".ssh" / "id_ed25519"),
            binPath=findVirtctlPath(),
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
    return {vmName: ssh_tunnel_connection(vmName) for vmName in vm_create}

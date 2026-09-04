from pathlib import Path
from typing import NamedTuple, Any, Dict
import pytest
import logging
import random
import os
import time

from libs.command_runner import CommandRunner
from libs.yaml_parser import ConfigLoader

logs = logging.getLogger()

@pytest.fixture(scope="function")
def vm_create(request):
    results = {}
    runner = CommandRunner()
    vm_config = request.config.rootpath / "config" / "vm-config-tlbflush-on.yaml"
    
    count = getattr(request, "param", 1)
    created_vms = []

    for _ in range(count):
        vm_name = f"virt-launcher-hjoshi-{random.randint(100, 999)}"
        context_variables = {"VM_NAME": vm_name}
        replaced_config = request.config.rootpath / "replaced_config" / Path(vm_name).with_suffix(".yaml")

        # Fixed method call from load_and_save to loadAndSave
        ConfigLoader.loadAndSave(vm_config, replaced_config, context_variables)
        
        create = runner.run(f"oc apply -f {replaced_config}", shell=True)
        if create.success:
            logs.info(f"VM created with name {vm_name}")
            created_vms.append(vm_name)

    yield created_vms

    # Teardown logic
    for vm_name in created_vms:
        logs.info(f"Cleaning up VM {vm_name}")
        runner.run(f"oc delete vm {vm_name} -n windows-bsod", shell=True)


# Repo-wide defaults for krkn chaos scenarios. A test's @pytest.mark.krkn(...)
# only needs to declare what differs; anything omitted falls back to these.
KRKN_DEFAULTS: Dict[str, Any] = {
    "namespace": "windows-bsod",
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

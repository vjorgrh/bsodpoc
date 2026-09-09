"""krkn-lib chaos scenario fixtures."""
import logging  # Standard Python logging module for tracking test events
import os  # Operating system module to access environment variables and file paths
from typing import Any, Dict, NamedTuple  # Type hinting utilities for clearer code definitions

import pytest  # Pytest testing framework for defining fixtures and hooks

from fixtures.common import DEFAULT_NAMESPACE  # Import global default namespace string from common fixtures

# Retrieve root logger instance to record fixture log messages
logs = logging.getLogger()

# Repo-wide fallback defaults for krkn chaos scenarios.
# If a test's @pytest.mark.krkn(...) marker doesn't specify a key, it uses these defaults.
KRKN_DEFAULTS: Dict[str, Any] = {
    "namespace": DEFAULT_NAMESPACE,  # Default target Kubernetes namespace ("windows-bsod")
    "vmName": "win2022-vm-hjoshi1",  # Default target Virtual Machine name
    "recoverTimeout": 300,  # Default recovery time SLA in seconds (5 minutes)
}


class KrknContext(NamedTuple):
    """Bundle handed to a test: the krkn-lib client plus the marker's parameters."""
    client: Any                 # Instantiated krkn_lib.k8s.KrknKubernetes client object
    params: Dict[str, Any]      # Merged dictionary containing KRKN_DEFAULTS + custom marker kwargs


@pytest.fixture(scope="function")  # Define a Pytest fixture that runs fresh for every individual test function
def krknChaos(request):
    """Provide a krkn-lib chaos client to a test and read its @pytest.mark.krkn(...) params."""
    
    # LAZY IMPORT: Import KrknKubernetes inside the fixture function rather than at the top of the file.
    # This prevents Pytest collection errors if krkn-lib is not installed in the execution environment.
    from krkn_lib.k8s import KrknKubernetes

    # Read the custom `@pytest.mark.krkn(...)` marker attached to the running test function
    marker = request.node.get_closest_marker("krkn")
    
    # Merge dictionary parameters:
    # Starts with KRKN_DEFAULTS and overrides them with any keyword arguments passed in the marker.
    params = {**KRKN_DEFAULTS, **(marker.kwargs if marker else {})}

    # Resolve KUBECONFIG path: check $KUBECONFIG environment variable first, fallback to ~/.kube/config
    kubeconfigPath = os.environ.get("KUBECONFIG") or os.path.expanduser("~/.kube/config")
    
    # Log the kubeconfig path being used to initialize the client
    logs.info(f"Initialising krkn-lib client with kubeconfig: {kubeconfigPath}")
    
    # Instantiate the krkn-lib Kubernetes API client object using the resolved kubeconfig
    client = KrknKubernetes(kubeconfig_path=kubeconfigPath)

    # YIELD / SETUP FINISHED:
    # Pause fixture execution here and hand the KrknContext (client + parameters) to the test function.
    yield KrknContext(client=client, params=params)

    # TEARDOWN PHASE:
    # Automatically executes after the test case finishes (whether it passed, failed, or threw an error).
    logs.info("krknChaos fixture teardown complete")  # Log fixture cleanup completion
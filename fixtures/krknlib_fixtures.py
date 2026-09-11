"""krkn-lib chaos scenario fixtures."""
import logging  # Standard Python logging module for tracking test events
import os  # Operating system module to access environment variables and file paths
import time  # Time module for sleep/delays during polling
from typing import Any, Dict, NamedTuple  # Type hinting utilities for clearer code definitions

import pytest  # Pytest testing framework for defining fixtures and hooks

from libs.common import DEFAULT_NAMESPACE  # Import global default namespace string from common

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

    def create_vm_from_template(self, clone_name: str, base_vm: str = "win2022-vm-hjoshi1",
                                cpu: int = 4, memory: str = "16Gi", namespace: str = None) -> Dict[str, Any]:
        """Create a new VM by cloning an existing VM template."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)

        # Get the source VM manifest
        source_vm = self.client.custom_object_client.get_namespaced_custom_object(
            group="kubevirt.io", version="v1", namespace=namespace,
            plural="virtualmachines", name=base_vm
        )

        # Create new VM manifest by cloning and modifying the source
        new_vm = self._clone_vm_manifest(source_vm, clone_name, cpu, memory)

        # Apply the new VM to the cluster
        created_vm = self.client.custom_object_client.create_namespaced_custom_object(
            group="kubevirt.io", version="v1", namespace=namespace,
            plural="virtualmachines", body=new_vm
        )
        logs.info(f"✓ Created VM: {clone_name} in namespace {namespace}")
        return created_vm

    def create_dv_from_template(self, clone_name: str, base_dv: str = "win2022-dv-hjoshi1",
                               size: str = "120Gi", namespace: str = None) -> Dict[str, Any]:
        """Create a new DataVolume by cloning an existing DV template."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)

        # Get the source DV manifest
        source_dv = self.client.custom_object_client.get_namespaced_custom_object(
            group="cdi.kubevirt.io", version="v1beta1", namespace=namespace,
            plural="datavolumes", name=base_dv
        )

        # Create new DV manifest by cloning and modifying the source
        new_dv = self._clone_dv_manifest(source_dv, clone_name, size)

        # Apply the new DV to the cluster
        created_dv = self.client.custom_object_client.create_namespaced_custom_object(
            group="cdi.kubevirt.io", version="v1beta1", namespace=namespace,
            plural="datavolumes", body=new_dv
        )
        logs.info(f"✓ Created DataVolume: {clone_name} in namespace {namespace}")
        return created_dv

    def get_vm_status(self, vm_name: str, namespace: str = None) -> Dict[str, Any]:
        """Get detailed VM status and configuration."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        vm = self.client.custom_object_client.get_namespaced_custom_object(
            group="kubevirt.io", version="v1", namespace=namespace,
            plural="virtualmachines", name=vm_name
        )
        status = {
            "name": vm["metadata"]["name"],
            "namespace": vm["metadata"]["namespace"],
            "cpu_cores": vm["spec"]["template"]["spec"]["domain"]["cpu"]["cores"],
            "memory": vm["spec"]["template"]["spec"]["domain"]["memory"]["guest"],
            "running": vm["spec"]["running"] if "running" in vm["spec"] else None,
            "runStrategy": vm["spec"].get("runStrategy", "Halted"),
            "creation_time": vm["metadata"]["creationTimestamp"],
        }
        logs.info(f"VM Status: {vm_name} - {status}")
        return status

    def get_vmi_status(self, vm_name: str, namespace: str = None) -> Dict[str, Any]:
        """Get VMInstance (running) status."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        try:
            vmi = self.client.custom_object_client.get_namespaced_custom_object(
                group="kubevirt.io", version="v1", namespace=namespace,
                plural="virtualmachineinstances", name=vm_name
            )
            status = {
                "name": vmi["metadata"]["name"],
                "phase": vmi["status"].get("phase", "Unknown"),
                "node": vmi["status"].get("nodeName", "Unscheduled"),
                "conditions": vmi["status"].get("conditions", []),
            }
            logs.info(f"VMI Status: {vm_name} - phase: {status['phase']}, node: {status['node']}")
            return status
        except Exception as e:
            logs.warning(f"VMI not found or error: {vm_name} - {e}")
            return {"phase": "NotRunning", "node": None}

    def scale_vm_resources(self, vm_name: str, cpu: int = None, memory: str = None, namespace: str = None) -> Dict[str, Any]:
        """Scale VM CPU and/or memory resources."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)

        vm = self.client.custom_object_client.get_namespaced_custom_object(
            group="kubevirt.io", version="v1", namespace=namespace,
            plural="virtualmachines", name=vm_name
        )

        # Update CPU if provided
        if cpu is not None:
            vm["spec"]["template"]["spec"]["domain"]["cpu"]["cores"] = cpu
            vm["spec"]["template"]["spec"]["domain"]["resources"]["limits"]["cpu"] = str(cpu)
            vm["spec"]["template"]["spec"]["domain"]["resources"]["requests"]["cpu"] = str(cpu)
            logs.info(f"Scaling VM {vm_name} CPU to {cpu} cores")

        # Update memory if provided
        if memory is not None:
            vm["spec"]["template"]["spec"]["domain"]["memory"]["guest"] = memory
            vm["spec"]["template"]["spec"]["domain"]["resources"]["limits"]["memory"] = memory
            vm["spec"]["template"]["spec"]["domain"]["resources"]["requests"]["memory"] = memory
            logs.info(f"Scaling VM {vm_name} memory to {memory}")

        # Apply the patched VM
        updated_vm = self.client.custom_object_client.patch_namespaced_custom_object(
            group="kubevirt.io", version="v1", namespace=namespace,
            plural="virtualmachines", name=vm_name, body=vm
        )
        logs.info(f"✓ Scaled VM: {vm_name} (CPU: {cpu}, Memory: {memory})")
        return updated_vm

    def delete_vm(self, vm_name: str, namespace: str = None, wait: bool = False) -> bool:
        """Delete a VM and optionally wait for deletion."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        try:
            self.client.custom_object_client.delete_namespaced_custom_object(
                group="kubevirt.io", version="v1", namespace=namespace,
                plural="virtualmachines", name=vm_name
            )
            logs.info(f"✓ Deleted VM: {vm_name}")
            return True
        except Exception as e:
            logs.error(f"Failed to delete VM {vm_name}: {e}")
            return False

    def delete_dv(self, dv_name: str, namespace: str = None) -> bool:
        """Delete a DataVolume."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        try:
            self.client.custom_object_client.delete_namespaced_custom_object(
                group="cdi.kubevirt.io", version="v1beta1", namespace=namespace,
                plural="datavolumes", name=dv_name
            )
            logs.info(f"✓ Deleted DataVolume: {dv_name}")
            return True
        except Exception as e:
            logs.error(f"Failed to delete DV {dv_name}: {e}")
            return False

    def wait_for_dv_ready(self, dv_name: str, namespace: str = None, timeout: int = 900, poll_interval: int = 10) -> bool:
        """Wait for DataVolume to be Ready (import from S3 completes)."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        start_time = time.time()

        logs.info(f"⏳ Waiting for DV {dv_name} to be Ready (timeout: {timeout}s = 15 minutes)...")

        while time.time() - start_time < timeout:
            try:
                dv = self.client.custom_object_client.get_namespaced_custom_object(
                    group="cdi.kubevirt.io", version="v1beta1", namespace=namespace,
                    plural="datavolumes", name=dv_name
                )

                phase = dv.get("status", {}).get("phase", "Unknown")
                progress = dv.get("status", {}).get("progress", "0%")

                # Check if Ready condition is True
                conditions = dv.get("status", {}).get("conditions", [])
                ready_condition = next((c for c in conditions if c["type"] == "Ready"), None)
                is_ready = ready_condition and ready_condition.get("status") == "True" if ready_condition else False

                logs.info(f"DV {dv_name} phase: {phase}, progress: {progress}, ready: {is_ready}")

                if is_ready and phase == "Succeeded":
                    logs.info(f"✓ DV {dv_name} is Ready!")
                    return True

                time.sleep(poll_interval)

            except Exception as e:
                logs.warning(f"Error checking DV status: {e}")
                time.sleep(poll_interval)

        logs.error(f"✗ DV {dv_name} did not become Ready within {timeout} seconds")
        return False

    def wait_for_vm_ready(self, vm_name: str, namespace: str = None, timeout: int = 300, poll_interval: int = 10) -> bool:
        """Wait for VM to be Running (VMInstance created and Running)."""
        namespace = namespace or self.params.get("namespace", DEFAULT_NAMESPACE)
        start_time = time.time()

        logs.info(f"⏳ Waiting for VM {vm_name} to be Running (timeout: {timeout}s)...")

        while time.time() - start_time < timeout:
            try:
                vmi_status = self.get_vmi_status(vm_name, namespace)
                phase = vmi_status.get("phase", "Unknown")
                node = vmi_status.get("node", "Unscheduled")

                logs.info(f"VMI {vm_name} phase: {phase}, node: {node}")

                if phase == "Running" and node != "Unscheduled":
                    logs.info(f"✓ VM {vm_name} is Running on {node}!")
                    return True

                time.sleep(poll_interval)

            except Exception as e:
                logs.warning(f"Error checking VM status: {e}")
                time.sleep(poll_interval)

        logs.error(f"✗ VM {vm_name} did not become Running within {timeout} seconds")
        return False

    def _clone_vm_manifest(self, source_vm: Dict, clone_name: str, cpu: int, memory: str) -> Dict:
        """Internal: Create a new VM manifest by cloning an existing one."""
        new_vm = dict(source_vm)
        new_vm["metadata"]["name"] = clone_name
        new_vm["metadata"].pop("resourceVersion", None)
        new_vm["metadata"].pop("uid", None)
        new_vm["metadata"].pop("generation", None)
        new_vm["metadata"]["creationTimestamp"] = None

        # Update labels to reference new VM name
        new_vm["spec"]["template"]["metadata"]["labels"]["kubevirt.io/vm"] = clone_name

        # Update resource limits and DV reference
        new_vm["spec"]["template"]["spec"]["domain"]["cpu"]["cores"] = cpu
        new_vm["spec"]["template"]["spec"]["domain"]["memory"]["guest"] = memory
        new_vm["spec"]["template"]["spec"]["domain"]["resources"]["limits"]["cpu"] = str(cpu)
        new_vm["spec"]["template"]["spec"]["domain"]["resources"]["requests"]["cpu"] = str(cpu)
        new_vm["spec"]["template"]["spec"]["domain"]["resources"]["limits"]["memory"] = memory
        new_vm["spec"]["template"]["spec"]["domain"]["resources"]["requests"]["memory"] = memory

        # Update volume to reference new DV name
        for volume in new_vm["spec"]["template"]["spec"]["volumes"]:
            if "persistentVolumeClaim" in volume:
                dv_clone_name = clone_name.replace("vm-", "dv-")
                volume["persistentVolumeClaim"]["claimName"] = dv_clone_name

        return new_vm

    def _clone_dv_manifest(self, source_dv: Dict, clone_name: str, size: str) -> Dict:
        """Internal: Create a new DV manifest by cloning an existing one."""
        new_dv = dict(source_dv)
        new_dv["metadata"]["name"] = clone_name
        new_dv["metadata"].pop("resourceVersion", None)
        new_dv["metadata"].pop("uid", None)
        new_dv["metadata"].pop("generation", None)
        new_dv["metadata"]["creationTimestamp"] = None

        # Update storage size
        new_dv["spec"]["storage"]["resources"]["requests"]["storage"] = size

        # Remove status fields
        new_dv.pop("status", None)

        return new_dv


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
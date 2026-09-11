import time  # Provides time-related functions like sleep() and time() for timestamps/deadlines
import logging  # Provides standard logging capabilities to output test progress and messages

import pytest  # The main Pytest testing framework used for writing and running test cases

from libs.command_runner import CommandRunner  # Custom helper class to run local shell/CLI commands (like oc)
from libs.common import get_namespace, get_target_name, execOnNode  # Helper functions for environment-based config

# Retrieves the root logger instance so we can record logs (e.g., logs.info, logs.warning)
logs = logging.getLogger()

# Get namespace and target name from environment or use defaults
DEFAULT_NAMESPACE = get_namespace()
DEFAULT_TARGET_NAME = get_target_name()


class TestChaos():
	"""krkn-lib chaos scenarios for BSOD/VM resiliency."""

	# Custom Pytest marker defining scenario metadata passed directly to the `krknChaos` fixture
	@pytest.mark.krkn(
		vmName=DEFAULT_TARGET_NAME,  # Target resource name (VM, benchmark runner, etc - from env or default)
		namespace=DEFAULT_NAMESPACE,  # Target Kubernetes namespace (from env or default)
		labelSelector=f"vm.kubevirt.io/name={DEFAULT_TARGET_NAME}",  # KubeVirt label selector to locate backing pod
		recoverTimeout=300,  # Maximum SLA time allowed for recovery (in seconds)
	)
	def test_vmSurvivesVirtLauncherKill(self, krknChaos):
		"""Chaos: kill the VM's virt-launcher pod and assert KubeVirt recovers it."""
		client = krknChaos.client  # Extract krkn-lib Kubernetes client instance from fixture
		params = krknChaos.params  # Extract scenario parameters dictionary from fixture
		ns = params["namespace"]  # Store namespace string ("windows-bsod")
		vmName = params["vmName"]  # Store VM name string ("win2022-vm-hjoshi1")
		selector = params["labelSelector"]  # Store label selector string
		recoverTimeout = params.get("recoverTimeout", 300)  # Get recovery timeout SLA (default: 300s)
		runner = CommandRunner()  # Instantiate helper to execute local shell commands

		# 1. Find the live virt-launcher pod backing the VM via krkn-lib
		pods = client.list_pods(namespace=ns, label_selector=selector)  # Search pods matching label
		assert pods, f"no virt-launcher pod found for {vmName} — is the VM running?"  # Fail test if pod isn't found
		originalPod = pods[0]  # Get the pod name of the active virt-launcher pod
		logs.info(f"target virt-launcher pod: {originalPod}")  # Log target pod name

		# Sanity Check: Ensure the VirtualMachineInstance (VMI) is in "Running" state before injecting chaos
		before = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", shell=True)  # Query VMI status via oc
		assert before.stdout == "Running", f"VM not Running before chaos: {before.stdout!r}"  # Assert VM is healthy

		# 2. INJECT CHAOS: Delete the VM's backing virt-launcher pod to simulate a pod/node crash
		logs.info(f"CHAOS: deleting virt-launcher pod {originalPod}")  # Log chaos action
		client.delete_pod(originalPod, ns)  # Issue delete pod API request via krkn-lib

		# 3. Assert recovery: Poll until a NEW launcher pod reaches Running AND the VMI phase returns to Running
		deadline = time.time() + recoverTimeout  # Calculate deadline timestamp (current time + 300s)
		recovered = False  # Initialize recovery status flag as False

		while time.time() < deadline:  # Loop continuously until deadline is reached
			current = client.list_pods(namespace=ns, label_selector=selector)  # Get current list of pods matching label
			newPods = [p for p in current if p != originalPod]  # Filter out the killed pod to identify any new pod
			vmiPhase = runner.run(  # Query OpenShift for current VMI phase
				f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
				shell=True).stdout  # Get stdout string from command result

			# Check if a new pod exists, is running according to krkn-lib, and the VMI phase is "Running"
			if newPods and client.is_pod_running(newPods[0], ns) and vmiPhase == "Running":
				logs.info(f"recovered: new pod {newPods[0]} Running, VMI phase {vmiPhase}")  # Log success
				recovered = True  # Set recovery flag to True
				break  # Exit polling loop early since VM recovered successfully

			logs.info(f"waiting for recovery ... (VMI phase={vmiPhase!r})")  # Log waiting state
			time.sleep(10)  # Wait 10 seconds before polling again

		# Final Assertion: Verify that the VM recovered before the deadline expired
		assert recovered, (
			f"VM {vmName} did not recover within {recoverTimeout}s after virt-launcher kill")

	# Custom Pytest marker defining parameters for host kernel scan scenario
	@pytest.mark.krkn(
		vmName=DEFAULT_TARGET_NAME,  # Target resource name (from env or default)
		namespace=DEFAULT_NAMESPACE,  # Target Kubernetes namespace (from env or default)
	)
	def test_hostSideKernelScanOnVmNode(self, krknChaos):
		"""Host-side reach: run a command on the worker node that runs the VM."""
		client = krknChaos.client  # Extract krkn-lib client from fixture
		params = krknChaos.params  # Extract scenario parameters from fixture
		ns = params["namespace"]  # Store namespace string
		vmName = params["vmName"]  # Store VM name string
		runner = CommandRunner()  # Instantiate shell command runner

		# 1. Resolve which worker node the target VMI is currently running on
		nodeRes = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",  # Extract node name via oc
			shell=True,
		)
		assert nodeRes.success and nodeRes.stdout, (  # Fail test if command failed or returned empty output
			f"could not resolve node for {vmName}: {nodeRes.stderr}")
		node = nodeRes.stdout.strip()  # Clean up whitespace/newlines from node name string
		logs.info(f"VM {vmName} runs on node {node}")  # Log target worker node name

		# 2. Sanity check: Ensure the target worker node is reported as Ready by krkn-lib
		readyNodes = client.list_ready_nodes()  # Get list of all Ready nodes in cluster
		assert node in readyNodes, f"node {node} is not Ready (ready: {readyNodes})"  # Assert node health

		# 3. Host-side command execution: Execute 'uname -r' on the host node to verify execution access
		kernel = execOnNode(
			client, node, "uname -r",  # Command to run on host
			podName="krkn-hostscan", namespace=ns,  # Helper pod configuration
		)
		logs.info(f"node {node} kernel release: {kernel!r}")  # Log host kernel version
		assert kernel and kernel.strip(), (  # Assert command returned valid stdout output
			f"no output from host-side exec on {node} — helper pod failed")

		# 4. Scan host kernel log (dmesg) for BSOD-relevant error signatures (split-lock, #AC, hypervisor errors)
		scan = execOnNode(
			client, node,
			"dmesg 2>/dev/null | grep -iE 'split.?lock|#AC|hypervisor' || true",  # Search dmesg without failing shell
			podName="krkn-hostscan", namespace=ns,  # Helper pod configuration
		)
		logs.info(f"host kernel-log scan on {node}:\n{scan}")  # Log captured dmesg entries for debugging

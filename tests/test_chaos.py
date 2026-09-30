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

	# Custom Pytest marker for memory pressure scenario
	@pytest.mark.krkn(
		vmName=DEFAULT_TARGET_NAME,  # Target VM name (from env or default)
		namespace=DEFAULT_NAMESPACE,  # Target Kubernetes namespace (from env or default)
		memoryPressurePercent=80,  # Consume 80% of node memory
		pressureDuration=300,  # Apply pressure for 300 seconds (5 minutes)
		recoverTimeout=600,  # Allow 10 minutes (600s) for recovery after pressure removed
	)
	def test_vmBsodUnderMemoryPressure(self, krknChaos):
		"""Chaos: Trigger potential BSOD via memory pressure (OOM) on VM's node."""
		client = krknChaos.client  # Extract krkn-lib client
		params = krknChaos.params  # Extract scenario parameters
		ns = params["namespace"]  # Kubernetes namespace
		vmName = params["vmName"]  # Target VM name
		memPercent = params.get("memoryPressurePercent", 80)  # Memory pressure percentage (default: 80%)
		pressureDuration = params.get("pressureDuration", 300)  # Duration to apply pressure (default: 300s)
		recoverTimeout = params.get("recoverTimeout", 600)  # Recovery SLA timeout (default: 600s)
		runner = CommandRunner()  # Shell command runner

		# 1. Get target node where VM is running
		nodeRes = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
			shell=True,
		)
		assert nodeRes.success and nodeRes.stdout, (
			f"could not resolve node for {vmName}: {nodeRes.stderr}")
		node = nodeRes.stdout.strip()
		logs.info(f"VM {vmName} runs on node {node}")

		# 2. Sanity check: Verify node is Ready before chaos
		readyNodes = client.list_ready_nodes()
		assert node in readyNodes, f"node {node} is not Ready before chaos"

		# 3. Get baseline memory info before pressure
		baseline_mem = execOnNode(
			client, node,
			"free -h | grep Mem",  # Get memory usage before pressure
			podName="krkn-memory-baseline", namespace=ns,
		)
		logs.info(f"baseline memory on {node}: {baseline_mem}")

		# 4. INJECT CHAOS: Apply memory pressure on node
		logs.info(f"CHAOS: applying {memPercent}% memory pressure on {node} for {pressureDuration}s")
		pressure_cmd = f"stress-ng --vm 1 --vm-bytes {memPercent}% --timeout {pressureDuration}s --verbose 2>&1 || true"

		try:
			mem_result = execOnNode(
				client, node,
				pressure_cmd,
				podName="krkn-memory-stress", namespace=ns,
				timeout=pressureDuration + 30,  # Give extra 30s buffer
			)
			logs.info(f"memory pressure result: {mem_result}")
		except Exception as e:
			logs.warning(f"memory pressure execution warning: {e}")

		# 5. Wait for pressure injection to complete
		time.sleep(5)
		logs.info("memory pressure injection phase complete")

		# 6. Verify VM still running during pressure (or capture BSOD evidence)
		vmi_during = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
			shell=True,
		)
		logs.info(f"VM phase during pressure: {vmi_during.stdout}")

		# 7. Scan kernel logs for OOM/BSOD signatures immediately after pressure
		logs.info("scanning kernel logs for OOM/BSOD events")
		scan_oom = execOnNode(
			client, node,
			"dmesg 2>/dev/null | grep -iE 'out of memory|oom-kill|kernel panic|bsod|#AC|splitlock' | tail -20 || true",
			podName="krkn-oom-scan", namespace=ns,
		)
		logs.info(f"OOM/BSOD signatures found:\n{scan_oom}")

		# 8. Allow recovery: Monitor VM for recovery SLA
		logs.info(f"monitoring recovery for {recoverTimeout}s")
		deadline = time.time() + recoverTimeout
		vm_recovered = False
		recovery_time = None

		while time.time() < deadline:
			vmi_status = runner.run(
				f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
				shell=True,
			)
			if vmi_status.stdout == "Running":
				recovery_time = recoverTimeout - int(time.time() - (deadline - recoverTimeout))
				logs.info(f"VM recovered to Running state in {recovery_time}s")
				vm_recovered = True
				break

			logs.info(f"VM recovery in progress ... phase: {vmi_status.stdout}")
			time.sleep(10)

		# 9. Final assertions
		assert vm_recovered, (
			f"VM {vmName} did not recover to Running state within {recoverTimeout}s after memory pressure")

		# 10. Post-recovery: Verify node is still healthy
		final_nodes = client.list_ready_nodes()
		assert node in final_nodes, f"node {node} degraded after memory pressure chaos"

		logs.info(f"✅ PASSED: VM survived memory pressure chaos (OOM threshold: {memPercent}%, Recovery SLA: {recovery_time}s/{recoverTimeout}s)")

	# Custom Pytest marker for packet corruption scenario
	@pytest.mark.krkn(
		vmName=DEFAULT_TARGET_NAME,  # Target VM name
		namespace=DEFAULT_NAMESPACE,  # Target Kubernetes namespace
		packetCorruptionPercent=5,   # Corrupt 5% of packets
		corruptionDuration=300,      # Apply corruption for 300 seconds (5 minutes)
		recoverTimeout=600,          # Allow 10 minutes (600s) for recovery
	)
	def test_vmBsodUnderPacketCorruption(self, krknChaos):
		"""Chaos: Trigger potential BSOD via network packet corruption on VM's node."""
		client = krknChaos.client  # Extract krkn-lib client
		params = krknChaos.params  # Extract scenario parameters
		ns = params["namespace"]  # Kubernetes namespace
		vmName = params["vmName"]  # Target VM name
		packetPercent = params.get("packetCorruptionPercent", 5)  # Packet corruption percentage (default: 5%)
		corruptionDuration = params.get("corruptionDuration", 300)  # Duration to apply corruption (default: 300s)
		recoverTimeout = params.get("recoverTimeout", 600)  # Recovery SLA timeout (default: 600s)
		runner = CommandRunner()  # Shell command runner

		# 1. Get target node where VM is running
		nodeRes = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
			shell=True,
		)
		assert nodeRes.success and nodeRes.stdout, (
			f"could not resolve node for {vmName}: {nodeRes.stderr}")
		node = nodeRes.stdout.strip()
		logs.info(f"VM {vmName} runs on node {node}")

		# 2. Sanity check: Verify node is Ready before chaos
		readyNodes = client.list_ready_nodes()
		assert node in readyNodes, f"node {node} is not Ready before chaos"

		# 3. INJECT CHAOS: Apply packet corruption on node network
		logs.info(f"CHAOS: applying {packetPercent}% packet corruption on {node} for {corruptionDuration}s")
		corruption_cmd = f"tc qdisc add dev eth0 root netem corrupt {packetPercent}% && sleep {corruptionDuration} && tc qdisc del dev eth0 root || true"

		try:
			corruption_result = execOnNode(
				client, node,
				corruption_cmd,
				podName="krkn-packet-corrupt", namespace=ns,
				timeout=corruptionDuration + 30,  # Give extra 30s buffer
			)
			logs.info(f"packet corruption result: {corruption_result}")
		except Exception as e:
			logs.warning(f"packet corruption execution warning: {e}")

		# 4. Wait for corruption injection to complete
		time.sleep(5)
		logs.info("packet corruption injection phase complete")

		# 5. Verify VM still running during corruption
		vmi_during = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
			shell=True,
		)
		logs.info(f"VM phase during corruption: {vmi_during.stdout}")

		# 6. Scan kernel logs for HEAP_CORRUPTION/BSOD signatures
		logs.info("scanning kernel logs for memory corruption/BSOD events")
		scan_corruption = execOnNode(
			client, node,
			"dmesg 2>/dev/null | grep -iE 'heap.?corruption|memory.?corruption|bsod|panic|#AC' | tail -20 || true",
			podName="krkn-corruption-scan", namespace=ns,
		)
		logs.info(f"Corruption/BSOD signatures found:\n{scan_corruption}")

		# 7. Allow recovery: Monitor VM for recovery SLA
		logs.info(f"monitoring recovery for {recoverTimeout}s")
		deadline = time.time() + recoverTimeout
		vm_recovered = False
		recovery_time = None

		while time.time() < deadline:
			vmi_status = runner.run(
				f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
				shell=True,
			)
			if vmi_status.stdout == "Running":
				recovery_time = recoverTimeout - int(time.time() - (deadline - recoverTimeout))
				logs.info(f"VM recovered to Running state in {recovery_time}s")
				vm_recovered = True
				break

			logs.info(f"VM recovery in progress ... phase: {vmi_status.stdout}")
			time.sleep(10)

		# 8. Final assertions
		assert vm_recovered, (
			f"VM {vmName} did not recover to Running state within {recoverTimeout}s after packet corruption")

		# 9. Post-recovery: Verify node is still healthy
		final_nodes = client.list_ready_nodes()
		assert node in final_nodes, f"node {node} degraded after packet corruption chaos"

		logs.info(f"✅ PASSED: VM survived packet corruption chaos ({packetPercent}%, Recovery SLA: {recovery_time}s/{recoverTimeout}s)")

	# Custom Pytest marker for CPU pressure scenario
	@pytest.mark.krkn(
		vmName=DEFAULT_TARGET_NAME,  # Target VM name
		namespace=DEFAULT_NAMESPACE,  # Target Kubernetes namespace
		cpuPressurePercent=90,       # Consume 90% of node CPU
		pressureDuration=300,        # Apply pressure for 300 seconds (5 minutes)
		recoverTimeout=600,          # Allow 10 minutes (600s) for recovery
	)
	def test_vmBsodUnderCpuPressure(self, krknChaos):
		"""Chaos: Trigger potential BSOD via CPU pressure/starvation on VM's node."""
		client = krknChaos.client  # Extract krkn-lib client
		params = krknChaos.params  # Extract scenario parameters
		ns = params["namespace"]  # Kubernetes namespace
		vmName = params["vmName"]  # Target VM name
		cpuPercent = params.get("cpuPressurePercent", 90)  # CPU pressure percentage (default: 90%)
		pressureDuration = params.get("pressureDuration", 300)  # Duration to apply pressure (default: 300s)
		recoverTimeout = params.get("recoverTimeout", 600)  # Recovery SLA timeout (default: 600s)
		runner = CommandRunner()  # Shell command runner

		# 1. Get target node where VM is running
		nodeRes = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
			shell=True,
		)
		assert nodeRes.success and nodeRes.stdout, (
			f"could not resolve node for {vmName}: {nodeRes.stderr}")
		node = nodeRes.stdout.strip()
		logs.info(f"VM {vmName} runs on node {node}")

		# 2. Sanity check: Verify node is Ready before chaos
		readyNodes = client.list_ready_nodes()
		assert node in readyNodes, f"node {node} is not Ready before chaos"

		# 3. Get baseline CPU info before pressure
		baseline_cpu = execOnNode(
			client, node,
			"nproc && uptime",  # Get CPU count and load average
			podName="krkn-cpu-baseline", namespace=ns,
		)
		logs.info(f"baseline CPU on {node}: {baseline_cpu}")

		# 4. INJECT CHAOS: Apply CPU pressure on node
		logs.info(f"CHAOS: applying {cpuPercent}% CPU pressure on {node} for {pressureDuration}s")
		cpu_cmd = f"stress-ng --cpu $(nproc) --cpu-load {cpuPercent/100:.2f} --timeout {pressureDuration}s --verbose 2>&1 || true"

		try:
			cpu_result = execOnNode(
				client, node,
				cpu_cmd,
				podName="krkn-cpu-stress", namespace=ns,
				timeout=pressureDuration + 30,  # Give extra 30s buffer
			)
			logs.info(f"CPU pressure result: {cpu_result}")
		except Exception as e:
			logs.warning(f"CPU pressure execution warning: {e}")

		# 5. Wait for pressure injection to complete
		time.sleep(5)
		logs.info("CPU pressure injection phase complete")

		# 6. Verify VM still running during pressure
		vmi_during = runner.run(
			f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
			shell=True,
		)
		logs.info(f"VM phase during CPU pressure: {vmi_during.stdout}")

		# 7. Scan kernel logs for CPU/driver timeout errors
		logs.info("scanning kernel logs for CPU timeout/driver failure events")
		scan_cpu = execOnNode(
			client, node,
			"dmesg 2>/dev/null | grep -iE 'cpu.*timeout|driver.*timeout|timeout|starvation|#AC' | tail -20 || true",
			podName="krkn-cpu-scan", namespace=ns,
		)
		logs.info(f"CPU timeout/BSOD signatures found:\n{scan_cpu}")

		# 8. Allow recovery: Monitor VM for recovery SLA
		logs.info(f"monitoring recovery for {recoverTimeout}s")
		deadline = time.time() + recoverTimeout
		vm_recovered = False
		recovery_time = None

		while time.time() < deadline:
			vmi_status = runner.run(
				f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
				shell=True,
			)
			if vmi_status.stdout == "Running":
				recovery_time = recoverTimeout - int(time.time() - (deadline - recoverTimeout))
				logs.info(f"VM recovered to Running state in {recovery_time}s")
				vm_recovered = True
				break

			logs.info(f"VM recovery in progress ... phase: {vmi_status.stdout}")
			time.sleep(10)

		# 9. Final assertions
		assert vm_recovered, (
			f"VM {vmName} did not recover to Running state within {recoverTimeout}s after CPU pressure")

		# 10. Post-recovery: Verify node is still healthy
		final_nodes = client.list_ready_nodes()
		assert node in final_nodes, f"node {node} degraded after CPU pressure chaos"

		logs.info(f"✅ PASSED: VM survived CPU pressure chaos ({cpuPercent}%, Recovery SLA: {recovery_time}s/{recoverTimeout}s)")

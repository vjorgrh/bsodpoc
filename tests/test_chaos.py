import time
import logging

import pytest

from libs.command_runner import CommandRunner

logs = logging.getLogger()


class TestChaos():
    """krkn-lib chaos scenarios for BSOD/VM resiliency."""

    @pytest.mark.krkn(
        vmName="hjoshi-win2022",
        namespace="windows-bsod",
        labelSelector="vm.kubevirt.io/name=hjoshi-win2022",
        recoverTimeout=300,
    )
    def test_vmSurvivesVirtLauncherKill(self, krknChaos):
        """Chaos: kill the VM's virt-launcher pod and assert KubeVirt recovers it.

        Deleting the virt-launcher pod of a running VMI simulates a node/pod
        failure. With ``runStrategy: Always`` KubeVirt must reschedule a new
        launcher pod and bring the VMI back to ``Running``. This test uses the
        krkn-lib client (from the ``krknChaos`` fixture) to find and kill the
        pod, and ``oc`` for the VMI-level recovery assertion.
        """
        client = krknChaos.client
        params = krknChaos.params
        ns = params["namespace"]
        vmName = params["vmName"]
        selector = params["labelSelector"]
        recoverTimeout = params.get("recoverTimeout", 300)
        runner = CommandRunner()

        # 1. Find the live virt-launcher pod backing the VM.
        pods = client.list_pods(namespace=ns, label_selector=selector)
        assert pods, f"no virt-launcher pod found for {vmName} — is the VM running?"
        originalPod = pods[0]
        logs.info(f"target virt-launcher pod: {originalPod}")

        # Sanity: the VM must be Running before we break it, otherwise the
        # recovery assertion below is meaningless.
        before = runner.run(
            f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", shell=True)
        assert before.stdout == "Running", f"VM not Running before chaos: {before.stdout!r}"

        # 2. CHAOS: kill the virt-launcher pod (simulates node/pod failure).
        logs.info(f"CHAOS: deleting virt-launcher pod {originalPod}")
        client.delete_pod(originalPod, ns)

        # 3. Assert recovery: a NEW launcher pod reaches Running AND the VMI
        #    returns to Running, within recoverTimeout.
        deadline = time.time() + recoverTimeout
        recovered = False
        while time.time() < deadline:
            current = client.list_pods(namespace=ns, label_selector=selector)
            newPods = [p for p in current if p != originalPod]
            vmiPhase = runner.run(
                f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
                shell=True).stdout
            if newPods and client.is_pod_running(newPods[0], ns) and vmiPhase == "Running":
                logs.info(f"recovered: new pod {newPods[0]} Running, VMI phase {vmiPhase}")
                recovered = True
                break
            logs.info(f"waiting for recovery ... (VMI phase={vmiPhase!r})")
            time.sleep(10)

        assert recovered, (
            f"VM {vmName} did not recover within {recoverTimeout}s after virt-launcher kill")

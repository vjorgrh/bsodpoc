import time
import logging

import pytest

from libs.utils.CmdExec import CmdExec

logs = logging.getLogger()

# Default helper image for host-side exec. krkn-lib's own exec_command_on_node
# hardcodes docker.io/fedora/tools, which Docker Hub no longer serves (pull =>
# 'access denied'). UBI9 is public and this Red Hat cluster already pulls it.
NODE_EXEC_IMAGE = 'registry.access.redhat.com/ubi9/ubi'


def ExecOnNode(client, node, command, podName, namespace,
               image=NODE_EXEC_IMAGE, timeout=120):
    '''
    Run a shell command on a node via a transient privileged pod, using
    krkn-lib primitives directly.

    This replaces krkn-lib's ``exec_command_on_node`` wrapper, which (a) hardcodes
    a dead image, (b) waits 500s before failing, and (c) never deletes the pod.
    Here we build the same privileged/hostNetwork/dbus pod but with a pullable
    image, a short timeout, and guaranteed cleanup.

    :param command:
        the command as a single shell string (e.g. 'uname -r').
        It is handed to krkn-lib as ``[command]`` so it runs under ``bash -c
        '<command>'``; passing a token list instead (['uname', '-r']) makes
        krkn-lib build ``bash -c uname -r``, where ``-r`` becomes a positional
        param and is silently dropped.
    :return: the command's stdout as a string.
    '''
    podBody = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': podName},
        'spec': {
            'hostNetwork': True,
            'nodeName': node,
            'restartPolicy': 'Never',
            'containers': [{
                'name': 'hosttools',
                'image': image,
                'command': ['/bin/sh', '-c', 'sleep infinity'],
                'securityContext': {'privileged': True},
                'volumeMounts': [{
                    'mountPath': '/run/dbus/system_bus_socket',
                    'name': 'dbus',
                    'readOnly': True,
                }],
            }],
            'volumes': [{
                'name': 'dbus',
                'hostPath': {'path': '/run/dbus/system_bus_socket'},
            }],
        },
    }

    # Best-effort pre-clean in case a previous run left the pod behind.
    try:
        client.delete_pod(podName, namespace)
        time.sleep(3)
    except Exception:
        pass

    try:
        client.create_pod(podBody, namespace, timeout)
        # Pass as a single-element list so krkn-lib runs `bash -c '<command>'`.
        return client.exec_cmd_in_pod([command], podName, namespace)
    finally:
        try:
            client.delete_pod(podName, namespace)
        except Exception:
            logs.warning(f'could not delete helper pod {podName} in {namespace}')


class TestChaos():
    '''krkn-lib chaos scenarios for BSOD/VM resiliency.'''

    @pytest.mark.krkn(
        vmName='hjoshi-win2022',
        namespace='windows-bsod',
        labelSelector='vm.kubevirt.io/name=hjoshi-win2022',
        recoverTimeout=300,
    )
    def test_VmSurvivesVirtLauncherKill(self, krknChaos):
        '''
        Chaos: kill the VM's virt-launcher pod and assert KubeVirt recovers it.

        Deleting the virt-launcher pod of a running VMI simulates a node/pod
        failure. With ``runStrategy: Always`` KubeVirt must reschedule a new
        launcher pod and bring the VMI back to ``Running``. This test uses the
        krkn-lib client (from the ``krknChaos`` fixture) to find and kill the
        pod, and ``oc`` for the VMI-level recovery assertion.
        '''
        client = krknChaos.client
        params = krknChaos.params
        ns = params['namespace']
        vmName = params['vmName']
        selector = params['labelSelector']
        recoverTimeout = params.get('recoverTimeout', 300)
        runner = CmdExec()

        # 1. Find the live virt-launcher pod backing the VM.
        pods = client.list_pods(namespace=ns, label_selector=selector)
        assert pods, f'no virt-launcher pod found for {vmName} — is the VM running?'
        originalPod = pods[0]
        logs.info(f'target virt-launcher pod: {originalPod}')

        # Sanity: the VM must be Running before we break it, otherwise the
        # recovery assertion below is meaningless.
        before = runner.Run(
            f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'", shell=True)
        assert before.stdout == 'Running', f'VM not Running before chaos: {before.stdout!r}'

        # 2. CHAOS: kill the virt-launcher pod (simulates node/pod failure).
        logs.info(f'CHAOS: deleting virt-launcher pod {originalPod}')
        client.delete_pod(originalPod, ns)

        # 3. Assert recovery: a NEW launcher pod reaches Running AND the VMI
        #    returns to Running, within recoverTimeout.
        deadline = time.time() + recoverTimeout
        recovered = False
        while time.time() < deadline:
            current = client.list_pods(namespace=ns, label_selector=selector)
            newPods = [p for p in current if p != originalPod]
            vmiPhase = runner.Run(
                f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.phase}}'",
                shell=True).stdout
            if newPods and client.is_pod_running(newPods[0], ns) and vmiPhase == 'Running':
                logs.info(f'recovered: new pod {newPods[0]} Running, VMI phase {vmiPhase}')
                recovered = True
                break
            logs.info(f'waiting for recovery ... (VMI phase={vmiPhase!r})')
            time.sleep(10)

        assert recovered, (
            f'VM {vmName} did not recover within {recoverTimeout}s after virt-launcher kill')

    @pytest.mark.krkn(
        vmName='hjoshi-win2022',
        namespace='windows-bsod',
    )
    def test_HostSideKernelScanOnVmNode(self, krknChaos):
        '''
        Host-side reach: run a command on the worker node that runs the VM.

        Spins up a transient privileged pod on the target node (via krkn-lib
        primitives create_pod/exec_cmd_in_pod/delete_pod) and runs a shell
        command with host visibility. That host level is exactly where the
        TLB-flush / ``HYPERVISOR_ERROR`` split-lock (#AC) signatures appear in
        the kernel log; those never reach the Windows guest dump. This test is
        the foundation lever for host-side fault injection, but is written
        non-destructively: it only reads.

        Steps:
          1. Resolve which node the VMI runs on (KubeVirt-specific -> ``oc``).
          2. Sanity-check that node is Ready via krkn-lib.
          3. Run a host-side command (``uname -r``) on it via krkn-lib and
             assert we get output back — proving host-side execution works.
          4. As bonus evidence, scan ``dmesg`` for split-lock/#AC/hypervisor
             lines and log them (not asserted: a clean host is the healthy case).
        '''
        client = krknChaos.client
        params = krknChaos.params
        ns = params['namespace']
        vmName = params['vmName']
        runner = CmdExec()

        # 1. Which node is the VM running on? (KubeVirt VMI status -> node name.)
        nodeRes = runner.Run(
            f"oc get vmi {vmName} -n {ns} -o jsonpath='{{.status.nodeName}}'",
            shell=True,
        )
        assert nodeRes.success and nodeRes.stdout, (
            f'could not resolve node for {vmName}: {nodeRes.stderr}')
        node = nodeRes.stdout.strip()
        logs.info(f'VM {vmName} runs on node {node}')

        # 2. That node must be Ready (krkn-lib node inventory).
        readyNodes = client.list_ready_nodes()
        assert node in readyNodes, f'node {node} is not Ready (ready: {readyNodes})'

        # 3. Host-side command: prove we can execute on the node.
        kernel = ExecOnNode(
            client, node, 'uname -r',
            podName='krkn-hostscan', namespace=ns,
        )
        logs.info(f'node {node} kernel release: {kernel!r}')
        assert kernel and kernel.strip(), (
            f'no output from host-side exec on {node} — helper pod failed')

        # 4. Bonus evidence: scan the host kernel log for BSOD-relevant signatures.
        scan = ExecOnNode(
            client, node,
            "dmesg 2>/dev/null | grep -iE 'split.?lock|#AC|hypervisor' || true",
            podName='krkn-hostscan', namespace=ns,
        )
        logs.info(f'host kernel-log scan on {node}:\n{scan}')

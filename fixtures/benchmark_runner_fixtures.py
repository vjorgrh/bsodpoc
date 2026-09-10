"""benchmark-runner fixtures: real OC client + Windows VM provisioning (single and scale)."""
import logging
import os
import tempfile
import time
import pytest

logs = logging.getLogger()

from benchmark_runner.workloads.windows_vm import WindowsVM

class WindowsVMScale(WindowsVM):
     def _initialize_run(self):
        super()._initialize_run()
        self._name = self._name.removesuffix('_scale')

@pytest.fixture(scope="session")
def oc():
    """
    SingletonOCLogin logs in once per process and caches it,so this
    (and any workload class that builds its own OC internally) shares
    a single login.
    """
    #check kubeconfig option of doing it
    from benchmark_runner.common.oc.oc import OC
    return OC(kubeadmin_password=os.environ["KUBEADMIN_PASSWORD"])

@pytest.fixture
def windowsVMScale(oc, request):
    """
    Creates single/multiple VM's in the cluster using benchmark runner
    Number of VM's to create is a param to a fixture
    This fixture refers to below environment variables:
    WORKER_NODE: Name of any 1 worker node in the cluster
    NAMESPACE: Namespace VM's will be deployed, default namespace is benchmark-runner
    WINDOWS_URL: Windows image url for VM deployment
    KUBEADMIN_PASSWORD: console kubeadmin password
    DELETE_ALL: This will delete all existing objects in namespace. 
                Default is True i.e. all objects in the namespace  will be deleted 
                Set to False if no exisitng object are to be removed
    RUN_ARTIFACTS_PATH: The path where log and yaml file will be generated
                        If not provided a temp directory is created
    """
    from benchmark_runner.main.environment_variables import environment_variables
    from benchmark_runner.main.temporary_environment_variables import TemporaryEnvironmentVariables
    from benchmark_runner.workloads.workloads_operations import WorkloadsOperations

    # Accept both (count, namespace) and a bare count.
    scale = getattr(request, "param", 1)
    logs.info(f"Create {scale} vm")
    with TemporaryEnvironmentVariables():
        env = environment_variables.environment_variables_dict
        env['run_type'] = 'test_ci'
        env['kubeadmin_password'] = env.get('kubeadmin_password')
        env['windows_url'] = env.get('windows_url')
        env['run_artifacts_path'] = env.get('run_artifacts_path') or tempfile.mkdtemp()
        logs.info(f"Run artifcats path: {env['run_artifacts_path']}) 
        env['namespace'] = env.get('namespace')
        if scale > 1:
           scale_nodes = [os.environ.get("WORKER_NODE")]
           env['workload'] = 'windows_vm_scale'
           env['scale'] = str(scale)
           env['scale_nodes'] = str(scale_nodes)
        else:
           env['workload'] = 'windows_vm'
        vmops = WorkloadsOperations()
        vmops.initialize_workload()
        vm = WindowsVMScale()
        yield vm

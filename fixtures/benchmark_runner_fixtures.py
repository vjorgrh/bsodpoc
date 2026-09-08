"""benchmark-runner fixtures: real OC client + Windows VM provisioning (single and scale)."""
import logging
import os
import tempfile

import pytest

logs = logging.getLogger()


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
def windowsVM(oc):
    """
    To create a single VM in the setup with benchmark runner
    This fixture refers to below environment values
    NAMESPACE: Namespace where objects would be deployed
    WINDOWS_URL: Windows image url for VM deployment
    KUBEADMIN_PASSWORD: console kubeadmin password
    CREATE_VMS_ONLY: This will on;ly create the VM and does not eprfrom any other operations
    """
    from benchmark_runner.main.environment_variables import environment_variables
    from benchmark_runner.main.temporary_environment_variables import TemporaryEnvironmentVariables
    from benchmark_runner.workloads.windows_vm import WindowsVM
    from benchmark_runner.workloads.workloads_operations import WorkloadsOperations

    with TemporaryEnvironmentVariables():
        env = environment_variables.environment_variables_dict
        env['workload'] = 'windows_vm'
        env['run_type'] = 'test_ci'
        env['kubeadmin_password'] = os.environ["KUBEADMIN_PASSWORD"]
        env['windows_url'] = os.environ["WINDOWS_URL"]
        env['run_artifacts_path'] = tempfile.mkdtemp()
        env['namespace'] = env.get('namespace') or 'benchmark-runner'
        vmops = WorkloadsOperations()
        vmops.initialize_workload()
        vm = WindowsVM()
        yield vm

        # best-effort teardown if the test didn't already clean up
        if oc.vm_exists(vm_name=vm._vm_name):
            oc.delete_vm_sync(
                yaml=os.path.join(env['run_artifacts_path'], f'{vm._name}.yaml'),
                vm_name=vm._vm_name,
            )


@pytest.fixture
def windowsVMScale(oc):
    """
    Create multiple VM's in the setup with benchmark runner
    This fixture refers to below environment values
    WORKER_NODE_0: Worker node where VM is to be deployed
    WORKER_NODE_1" Worker node where VM is tobe deployed
    NAMESPACE: Namespace where objects would be deployed
    WINDOWS_URL: Windows image url for VM deployment
    KUBEADMIN_PASSWORD: console kubeadmin password
    SCALE: No of VM's to create
    CREATE_VMS_ONLY: This will on;ly create the VM and does not eprfrom any other operations
    """
    from benchmark_runner.main.environment_variables import environment_variables
    from benchmark_runner.main.temporary_environment_variables import TemporaryEnvironmentVariables
    from benchmark_runner.workloads.windows_vm import WindowsVM
    from benchmark_runner.workloads.workloads_operations import WorkloadsOperations

    scale = int(os.environ.get("SCALE", "2"))
    workerNode0 = os.environ.get("WORKER_NODE_0")
    workerNode1 = os.environ.get("WORKER_NODE_1")

    scale_nodes = [workerNode0, workerNode1]
    dir_path = tempfile.mkdtemp()
    logs.info(f"Temporary directory created at: {dir_path}")
    with TemporaryEnvironmentVariables():
        env = environment_variables.environment_variables_dict
        env['workload'] = 'windows_vm_scale'
        env['run_type'] = 'test_ci'
        env['kubeadmin_password'] = os.environ["KUBEADMIN_PASSWORD"]
        env['windows_url'] = os.environ["WINDOWS_URL"]
        env['run_artifacts_path'] = dir_path
        env['namespace'] = os.environ["NAMESPACE"]
        env['scale'] = str(scale)
        env['scale_nodes'] = str(scale_nodes)
        env['threads_limit'] = os.environ.get("THREADS_LIMIT", "")  # '' -> defaults to scale*len(scale_nodes)
        env['bulk_sleep_time'] = os.environ.get("BULK_SLEEP_TIME", "30")
        env['elasticsearch'] = ''
        vmops = WorkloadsOperations()
        vmops.initialize_workload()
        vm = WindowsVM()
        yield vm
        # only needed if delete_all was overridden to False for the test
        if not env.get('delete_all', True) and hasattr(vm, '_workload_name'):
            for vm_num in range(scale * len(scale_nodes)):
                vm_name = f'{vm._workload_name}-{vm._trunc_uuid}-{vm_num}'
                if oc.vm_exists(vm_name=vm_name):
                    oc.delete_vm_sync(
                        yaml=os.path.join(env['run_artifacts_path'], f'{vm._name}_{vm_num}.yaml'),
                        vm_name=vm_name,
                    )

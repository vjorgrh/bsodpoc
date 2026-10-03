'''
BenchmarkRunner fixtures - VM provisioning at scale.

https://github.com/redhat-performance/benchmark-runner
'''
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Generator

import pytest

from fixtures.CommonConstant import LPQE__DEF__NAMESPACE
from libs.CustomTypes import NamedDict
from libs.OpenShift.LP.Virt.VM.VM import VM


logs = logging.getLogger()
_DEF__FXT_CFG = NamedDict(
    workloadName='windows',
    workloadKind='vm',
    count=1,
    cliCfg=NamedDict(
        ocCfg={},
        vcCfg={},
    ),
    ns=LPQE__DEF__NAMESPACE,
    gstCfg=NamedDict(
        usrCrd=NamedDict(
            sshUsr='qa-usr',
            sshKey='~/.ssh/openshift-qe.pem',
        ),
    ),
)


@pytest.fixture(scope='module')
def brMakeVMs(request, ocCLI, virtCtlCLI) -> Generator[Any, Any, Any]:
    '''
    Provision VMs via benchmark-runner and yield `list[VM]` wrappers.

    Calls `benchmark_runner.main.main.main()` with the required
    environment variables.  VMs are running when yielded.

    Configure via indirect parametrize with `dict`:
        @pytest.mark.parametrize(
            'brMakeVMs,',
            [({'count': 3},)],
            indirect=True,
        )

        Fixture Configuration:
          - workloadName:
            Template directory name inside benchmark-runner
            (default: `'windows'`).
          - workloadKind:
            Resource kind suffix (default: `'vm'`).
          - count:
            Number of VMs to create (default: `1`).
          - cliCfg:
            Configuration options for CLIs:
              - ocCfg:
                  Configuration options for `OCcli`.
              - vcCfg:
                  Configuration options for `VirtCtlCLI`.
          - ns:
            Kubernetes Namespace (default: `LPQE__DEF__NAMESPACE`).
          - gstCfg:
            Guest System configurations:
              - usrCrd:
                User Credential to connect to the Guest System.
                  - sshUsr: SSH UserName (default: `'qa-usr'`).
                  - sshKey: Path to the SSH private key (default:
                    `'~/.ssh/openshift-qe.pem'`).

    :return: `list` of `VM` instances.
    '''
    # Import lazily so the TCs are still collected if these modules are absent.
    from benchmark_runner.main.environment_variables import (
        environment_variables,
    )
    from benchmark_runner.main.main import main as brMain
    from benchmark_runner.main.temporary_environment_variables import (
        TemporaryEnvironmentVariables,
    )

    fxtCfg = _DEF__FXT_CFG | getattr(request, 'param', {})
    count = fxtCfg.count
    ns = fxtCfg.ns
    vmList = []

    logs.info(f'Creating {count} VM(s) via benchmark-runner')
    with TemporaryEnvironmentVariables():
        env = environment_variables.environment_variables_dict
        env['workload'] = f"{fxtCfg.workloadName}_{fxtCfg.workloadKind}"
        env['run_type'] = 'test_ci'
        env['namespace'] = ns
        env['run_artifacts_path'] = (
            env.get('run_artifacts_path') or tempfile.mkdtemp()
        )
        if (count > 1):
            env['scale'] = str(count)
            env['scale_nodes'] = str([os.environ.get('WORKER_NODE')])
        brMain()

        # The VMs are now running. Wrap each in a `VM` object.
        sshKey = Path(env.get('run_artifacts_path', ''), 'ssh', 'vm_key')
        sshKey = (
            str(sshKey) if sshKey.is_file()
            else fxtCfg.gstCfg.usrCrd.sshKey
        )
        truncUUID = env.get('trunc_uuid', '')

    for i in range(count):
        suffix = f'-{truncUUID}'
        if (count > 1): suffix += f'-{i}'
        vmList.append(VM(
            name=(f"{fxtCfg.workloadName}-{fxtCfg.workloadKind}" + suffix),
            ns=ns,
            oc=ocCLI(ns=ns, **fxtCfg.cliCfg.ocCfg),
            virtCtl=virtCtlCLI(ns=ns, **fxtCfg.cliCfg.vcCfg),
            sshUsr=fxtCfg.gstCfg.usrCrd.sshUsr,
            sshKey=sshKey,
        ))

    yield vmList

    for vm in vmList:
        vm.RmvSSH()

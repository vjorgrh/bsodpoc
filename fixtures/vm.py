'''Ad-hoc VM creation via templated YAML + `oc apply`.'''
import logging
import random
import time
from pathlib import Path

import pytest

from libs.utils.CmdExec import CmdExec
from libs.utils.YAML import ConfigLoader
from fixtures.common import DEFAULT_NAMESPACE

logs = logging.getLogger()


@pytest.fixture(scope='function')
def vmCreate(request):
    '''
    Create N VMs from the templated config and yield their names + status.

    Parametrise indirectly with a ``(count, namespace)`` tuple::

        @pytest.mark.parametrize('vm_create', [(2, 'windows-bsod')], indirect=True)

    A bare int is also accepted and falls back to ``DEFAULT_NAMESPACE``.

    :return:
        dict mapping the created VM name to the ``CmdRes`` of its
        status lookup. Iterating the dict yields the VM names.
    '''
    results = {}
    runner = CmdExec()
    vm_config = request.config.rootpath / 'config' / 'vm-config-tlbflush-on.yaml'
    logs.info(f'Creating VM from this config: {vm_config}')

    # Accept both (count, namespace) and a bare count.
    param = getattr(request, 'param', (1, DEFAULT_NAMESPACE))
    count, namespace = (param, DEFAULT_NAMESPACE) if isinstance(param, int) else param

    for _ in range(count):
        vm_name = f'bsod-auto-{random.randint(100, 999)}'
        context_variables = {'VM_NAME': vm_name}
        replaced_config = request.config.rootpath / 'replaced_config' / Path(vm_name).with_suffix('.yaml')

        ConfigLoader.loadAndSave(vm_config, replaced_config, context_variables)

        create = runner.Run(f'oc apply -f {replaced_config}', shell=True)
        if create.success:
            logs.info(f'VM created with name {vm_name}')
            time.sleep(10)
            results[vm_name] = runner.Run(
                f'oc get vm/{vm_name} -n {namespace} '
                f'-o custom-columns="STATUS:.status.printableStatus" --no-headers',
                shell=True,
            )

    yield results

    # Teardown logic
    for vm_name in results:
        logs.info(f'Cleaning up VM {vm_name}')
        runner.Run(f'oc delete vm {vm_name} -n {namespace}', shell=True)

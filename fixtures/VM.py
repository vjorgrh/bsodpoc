'''VM creation fixture using OCcli.NewRes and VM wrapper.'''
import logging
import sys
from typing import Any, Generator

import pytest

from fixtures.CommonConstant import LPQE__DEF__NAMESPACE
from libs.CustomTypes import NamedDict
from libs.OpenShift.LP.Virt.VM.VM import VM
from libs.utils.YAML import YAMLcfg


logs = logging.getLogger()
_DEF__FXT_CFG = NamedDict(
    count=1,
    cliCfg=NamedDict(
        ocCfg={},
        vcCfg={},
    ),
    ns=LPQE__DEF__NAMESPACE,
    configFile='config--vm--template.yaml',
    namePfx='lpqe-test',
    timeout='15m',
    gstCfg=NamedDict(
        usrCrd=NamedDict(
            sshUsr='qa-usr',
            sshKey='~/.ssh/openshift-qe.pem',
        ),
    ),
)


@pytest.fixture(scope='function')
def vmCreate(request, ocCLI, virtCtlCLI) -> Generator[Any, Any, Any]:
    '''
    Create VMs from a Jinja2 template and yield `VM` wrapper objects.

    Configure via indirect parametrize with `dict`:
        @pytest.mark.parametrize(
            'vmCreate,',
            [({'count': 2, 'ns': 'bsod-test'},)],
            indirect=True,
        )
        @pytest.mark.parametrize('vmCreate,', [({'count': 5},)], indirect=True)

        Fixture Configuration:
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
          - configFile:
            Template configuration file under `config/`
            (default: `'config--vm--template.yaml'`).
          - namePfx:
            Prefix for generated VM names (default: `'lpqe-test'`).
          - timeout:
            Wait timeout for VM creation (default: `'15m'`).
          - gstCfg:
            Guest System configurations:
              - usrCrd:
                User Credential to connect to the Guest System.
                  - sshUsr: SSH UserName (default: `'qa-usr'`).
                  - sshKey: Path to the SSH private key (default:
                    `'~/.ssh/openshift-qe.pem'`).

    :return: `list` of `VM` instances.
    '''
    fxtCfg = _DEF__FXT_CFG | getattr(request, 'param', {})
    ns = fxtCfg.ns
    templPath = request.config.rootpath / 'config' / fxtCfg.configFile
    vmList = []
    ownVMs = []

    try:
        sfxLen = len(str(max(fxtCfg.count - 1, 0)))
        for idx in range(fxtCfg.count):
            vmName = (
                f'{fxtCfg.namePfx}'
                f"{f'-{idx:0{sfxLen}d}' if (fxtCfg.count > 1) else ''}"
            )
            ctxData = {'vmName': vmName}
            oc = ocCLI(ns=ns, **fxtCfg.cliCfg.ocCfg)

            (lookupOK, prevUID, lookupErr) = VM.GetVMuid(oc, vmName)
            if not lookupOK:
                raise RuntimeError(
                    f'Could not establish whether VM `{vmName}` already '
                    f'exists: {lookupErr}'
                )

            yamlStr = YAMLcfg.Render(templPath, ctxData)
            phase, ocRes = oc.NewRes(yamlStr, waitTime=fxtCfg.timeout)
            applied = (
                (phase.name == 'WAITED') or
                ((phase.name == 'APPLIED') and ocRes.success)
            )
            (lookupOK, curUID, lookupErr) = VM.GetVMuid(oc, vmName)
            if (applied and not prevUID):
                if lookupOK:
                    if curUID: ownVMs.append((vmName, curUID, oc))
                else:
                    raise RuntimeError(
                        f'Could not establish ownership of VM `{vmName}` after '
                        f'apply: {lookupErr}'
                    )
            if ocRes.success:
                logs.info(f'VM `{vmName}` created (phase: `{phase.name}`).')
            else:
                logs.warning(
                    f'VM `{vmName}` creation failed at `{phase.name}`: '
                    f'{ocRes.stderr}'
                )

            vmList.append(VM(
                name=vmName,
                ns=ns,
                oc=oc,
                virtCtl=virtCtlCLI(ns=ns, **fxtCfg.cliCfg.vcCfg),
                **fxtCfg.gstCfg.usrCrd,
            ))

        yield vmList
    finally:
        primExc = sys.exc_info()[1]
        clnFail = []

        for vm in vmList:
            try: vm.RmvSSH()
            except Exception as ex:
                clnFail.append(f'Close SSH for `{vm.name}`: {ex}')
                logs.exception(f'Could not close SSH for VM `{vm.name}`.')

        for (vmName, ownUID, oc) in ownVMs:
            try:
                (lookupOK, curUID, lookupErr) = VM.GetVMuid(oc, vmName)
                if not lookupOK:
                    clnFail.append(
                        f'Verify ownership of `{vmName}` before deletion: '
                        f'{lookupErr}'
                    )
                    logs.error(
                        f'Could not verify ownership of VM `{vmName}` before '
                        f'deletion: {lookupErr}'
                    )
                    continue
                if not curUID:
                    logs.info(f'VM `{vmName}` is already absent.')
                    continue
                if (curUID != ownUID):
                    logs.warning(
                        f'Not deleting VM `{vmName}` because its UID changed.'
                    )
                    continue

                phase, result = oc.DelRes(f'VirtualMachine/{vmName}')
                if not result.success:
                    clnFail.append(
                        f'Delete `{vmName}` at `{phase.name}`: {result.stderr}'
                    )
                    logs.error(
                        f'Could not clean up VM `{vmName}` at '
                        f'`{phase.name}`: {result.stderr}'
                    )
                    continue
                logs.info(f'Cleaned up VM `{vmName}`.')
            except Exception as ex:
                clnFail.append(f'Delete `{vmName}`: {ex}')
                logs.exception(f'Could not clean up VM `{vmName}`.')

        if (clnFail and (primExc is None)):
            raise RuntimeError(
                'VM cleanup failed: ' + '; '.join(clnFail)
            )

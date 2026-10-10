'''CLI tool fixtures - factory producers for Cobra-based CLI wrappers.'''
import pytest

from fixtures.CommonConstant import LPQE__DEF__NAMESPACE
from libs.OpenShift.LP.Virt.CLI.VirtCtl import VirtCtlCLI as _VirtCtlCLI
from libs.OpenShift.OCP.CLI.OC import OCcli as _OCcli


@pytest.fixture(name='ocCLI', scope='module')
def OCcli():
    '''
    Module-scoped `oc` CLI factory.

    Call with keyword options to configure defaults for the returned instance.
    Defaults to `n=LPQE__DEF__NAMESPACE` if not overridden.
    '''
    def _make(ns=LPQE__DEF__NAMESPACE, **defOpts):
        return _OCcli(n=ns, **defOpts)
    return _make


@pytest.fixture(name='virtCtlCLI', scope='module')
def VirtCtlCLI():
    '''
    Module-scoped `virtctl` CLI factory.

    Call with keyword options to configure defaults for the returned instance.
    Defaults to `n=LPQE__DEF__NAMESPACE` if not overridden.
    '''
    def _make(ns=LPQE__DEF__NAMESPACE, **defOpts):
        return _VirtCtlCLI(n=ns, **defOpts)
    return _make

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

import fixtures.VM as MUT
from libs.CustomTypes import NamedDict
from libs.OpenShift.OCP.CLI.OC import OCcli
from libs.Utils.CmdExec import CmdRes
import Utils


def CommandResult(success: bool, stderr: str = '') -> CmdRes:
    return CmdRes('', stderr, 0 if success else 1, success)


def OCmock(name: str | None = None) -> mock.MagicMock:
    return mock.create_autospec(OCcli, instance=True, name=name)


def Request(param: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        param={} if param is None else param,
        config=SimpleNamespace(rootpath=Path('/repo')),
    )


def test_VMcreate_NegativeCountIsRejectedBeforeAnyOperation() -> None:
    vmList = []
    ownVMs = []
    ocFactory = mock.MagicMock()
    virtCtlFactory = mock.MagicMock()

    with pytest.raises(ValueError, match='must not be negative'):
        MUT.VMcreate(
            Request(),
            vmList,
            ownVMs,
            ocCLI=ocFactory,
            virtCtlCLI=virtCtlFactory,
            count=-1,
        )

    assert vmList == []
    assert ownVMs == []
    ocFactory.assert_not_called()
    virtCtlFactory.assert_not_called()


def test_VMcreate_ZeroCountReturnsEmptyWithoutAnyOperation() -> None:
    vmList = []
    ownVMs = []
    ocFactory = mock.MagicMock()
    virtCtlFactory = mock.MagicMock()

    result = MUT.VMcreate(
        Request(),
        vmList,
        ownVMs,
        ocCLI=ocFactory,
        virtCtlCLI=virtCtlFactory,
        count=0,
    )

    assert result == []
    assert vmList == []
    assert ownVMs == []
    ocFactory.assert_not_called()
    virtCtlFactory.assert_not_called()


def test_VMcreate_BatchReturnsNewVMsAndAppendsConfirmedOwnership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'rendered yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (True, 'uid-zero', ''),
        (True, '', ''),
        (True, '', ''),
    ]
    vmZero = mock.MagicMock(name='vmZero')
    vmOne = mock.MagicMock(name='vmOne')
    MUT.VM.side_effect = [vmZero, vmOne]
    ocZero = OCmock('ocZero')
    ocOne = OCmock('ocOne')
    ocZero.NewRes.return_value = (
        SimpleNamespace(name='WAITED'),
        CommandResult(True),
    )
    ocOne.NewRes.return_value = (
        SimpleNamespace(name='APPLIED'),
        CommandResult(True),
    )
    ocFactory = mock.MagicMock(side_effect=[ocZero, ocOne])
    virtCtlFactory = mock.MagicMock()
    vmList = []
    ownVMs = []

    created = MUT.VMcreate(
        Request(),
        vmList,
        ownVMs,
        ocCLI=ocFactory,
        virtCtlCLI=virtCtlFactory,
        count=2,
        namePfx='unit',
        configFile='template.yaml',
        timeout='4m',
        cliCfg=NamedDict(
            ocCfg={'context': 'oc-context'},
            vcCfg={'kubeconfig': '/virt-kubeconfig'},
        ),
        gstCfg=NamedDict(
            usrCrd=NamedDict(sshUsr='unit-user'),
        ),
    )

    assert created == [vmZero, vmOne]
    assert vmList == [vmZero, vmOne]
    assert ownVMs == [(ocZero, 'unit-0', 'uid-zero')]
    assert MUT.YAMLcfg.Render.call_args_list == [
        mock.call(Path('/repo/conf/template.yaml'), {'vmName': 'unit-0'}),
        mock.call(Path('/repo/conf/template.yaml'), {'vmName': 'unit-1'}),
    ]
    assert ocFactory.call_args_list == [
        mock.call(ns='default', context='oc-context'),
        mock.call(ns='default', context='oc-context'),
    ]
    assert virtCtlFactory.call_args_list == [
        mock.call(ns='default', kubeconfig='/virt-kubeconfig'),
        mock.call(ns='default', kubeconfig='/virt-kubeconfig'),
    ]
    ocZero.NewRes.assert_called_once_with('rendered yaml', waitTime='4m')
    ocOne.NewRes.assert_called_once_with('rendered yaml', waitTime='4m')
    assert [item.kwargs['name'] for item in MUT.VM.call_args_list] == [
        'unit-0',
        'unit-1',
    ]
    assert all(item.kwargs['ns'] == 'default' for item in MUT.VM.call_args_list)
    assert all(item.kwargs['sshUsr'] == 'unit-user' for item in MUT.VM.call_args_list)
    assert all(
        item.kwargs['sshKey'] == '~/.ssh/openshift-qe.pem'
        for item in MUT.VM.call_args_list
    )


def test_VMcreate_ReusesExistingVMWithoutRenderOrApply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.VM.GetVMuid.return_value = (True, 'existing', '')
    oc = OCmock()
    vmList = []
    ownVMs = []

    created = MUT.VMcreate(
        Request(),
        vmList,
        ownVMs,
        ocCLI=mock.MagicMock(return_value=oc),
        virtCtlCLI=mock.MagicMock(),
        reuseExisting=True,
        namePfx='single',
    )

    assert created == [MUT.VM.return_value]
    assert vmList == created
    assert ownVMs == []
    MUT.YAMLcfg.Render.assert_not_called()
    oc.NewRes.assert_not_called()


def test_VMcreate_PreflightLookupFailureRaisesWithoutTracking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    MUT.VM.GetVMuid.return_value = (False, '', 'lookup failed')
    vmList = []
    ownVMs = []

    with pytest.raises(RuntimeError, match='lookup failed'):
        MUT.VMcreate(
            Request(),
            vmList,
            ownVMs,
            ocCLI=mock.MagicMock(),
            virtCtlCLI=mock.MagicMock(),
        )

    assert vmList == []
    assert ownVMs == []


def test_VMcreate_ExistingVMWithoutReuseIsRejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    MUT.VM.GetVMuid.return_value = (True, 'existing', '')

    with pytest.raises(RuntimeError, match='already exists'):
        MUT.VMcreate(
            Request(),
            [],
            [],
            ocCLI=mock.MagicMock(),
            virtCtlCLI=mock.MagicMock(),
        )


def test_VMcreate_FailedNewResLogsWarningAndReturnsWrapper(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (False, '', 'not found'),
    ]
    oc = OCmock()
    oc.NewRes.return_value = (
        SimpleNamespace(name='DRY_RUN'),
        CommandResult(False, 'apply failed'),
    )
    vmList = []
    ownVMs = []

    with caplog.at_level('WARNING'):
        created = MUT.VMcreate(
            Request(),
            vmList,
            ownVMs,
            ocCLI=mock.MagicMock(return_value=oc),
            virtCtlCLI=mock.MagicMock(),
        )

    assert created == [MUT.VM.return_value]
    assert vmList == created
    assert ownVMs == []
    assert 'creation failed' in caplog.text


def test_VMcreate_SuccessfulApplyWithFailedOwnershipLookupRaises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (False, '', 'lookup failed after apply'),
    ]
    oc = OCmock()
    oc.NewRes.return_value = (
        SimpleNamespace(name='WAITED'),
        CommandResult(True),
    )

    with pytest.raises(RuntimeError, match='establish ownership'):
        MUT.VMcreate(
            Request(),
            [],
            [],
            ocCLI=mock.MagicMock(return_value=oc),
            virtCtlCLI=mock.MagicMock(),
        )


def test_VMcreate_NestedOverridesDoNotMutateDefaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    MUT.VM.GetVMuid.return_value = (True, 'existing', '')
    defaultNestedValues = (
        dict(MUT._DEF__FXT_CFG.cliCfg.ocCfg),
        dict(MUT._DEF__FXT_CFG.cliCfg.vcCfg),
        dict(MUT._DEF__FXT_CFG.gstCfg.usrCrd),
    )
    ocFactory = mock.MagicMock(return_value=OCmock())
    virtCtlFactory = mock.MagicMock()

    MUT.VMcreate(
        Request(),
        [],
        [],
        ocCLI=ocFactory,
        virtCtlCLI=virtCtlFactory,
        reuseExisting=True,
        cliCfg=NamedDict(ocCfg={'context': 'custom'}),
        gstCfg=NamedDict(usrCrd=NamedDict(sshUsr='custom-user')),
    )
    MUT.VMcreate(
        Request(),
        [],
        [],
        ocCLI=ocFactory,
        virtCtlCLI=virtCtlFactory,
        reuseExisting=True,
    )

    assert (
        dict(MUT._DEF__FXT_CFG.cliCfg.ocCfg),
        dict(MUT._DEF__FXT_CFG.cliCfg.vcCfg),
        dict(MUT._DEF__FXT_CFG.gstCfg.usrCrd),
    ) == defaultNestedValues
    assert ocFactory.call_args_list == [
        mock.call(ns='default', context='custom'),
        mock.call(ns='default'),
    ]
    assert virtCtlFactory.call_args_list == [
        mock.call(ns='default'),
        mock.call(ns='default'),
    ]
    assert MUT.VM.call_args_list[0].kwargs['sshUsr'] == 'custom-user'
    assert MUT.VM.call_args_list[0].kwargs['sshKey'] == '~/.ssh/openshift-qe.pem'
    assert MUT.VM.call_args_list[1].kwargs['sshUsr'] == 'qa-usr'
    assert MUT.VM.call_args_list[1].kwargs['sshKey'] == '~/.ssh/openshift-qe.pem'


def test_FxtVM_InitialNegativeFailsBeforeYieldWithoutCleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': -1}),
        mock.MagicMock(),
        mock.MagicMock(),
    )

    with pytest.raises(ValueError, match='must not be negative'):
        next(generator)

    MUT.VM.CleanUpVMs.assert_not_called()


def test_FxtVM_InitialZeroYieldsFrozenEmptyBundleWithoutCleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 0}),
        mock.MagicMock(),
        mock.MagicMock(),
    )

    bundle = next(generator)

    assert isinstance(bundle, MUT.FxtObjVM)
    assert bundle.vmList == []
    with pytest.raises(FrozenInstanceError):
        bundle.vmList = []
    generator.close()
    MUT.VM.CleanUpVMs.assert_not_called()


def test_FxtVM_InitialSuccessUsesSelectedConfigAndCleansOnClose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (True, 'initial-uid', ''),
    ]
    vm = mock.MagicMock(name='initialVM')
    MUT.VM.return_value = vm
    oc = OCmock()
    oc.NewRes.return_value = (
        SimpleNamespace(name='WAITED'),
        CommandResult(True),
    )
    ocFactory = mock.MagicMock(return_value=oc)
    virtCtlFactory = mock.MagicMock()
    generator = MUT.FxtVM.__wrapped__(
        Request({
            'count': 1,
            'ns': 'initial-ns',
            'namePfx': 'initial',
            'configFile': 'initial.yaml',
            'cliCfg': NamedDict(
                ocCfg={'context': 'initial-context'},
                vcCfg={'kubeconfig': '/initial-config'},
            ),
        }),
        ocFactory,
        virtCtlFactory,
    )

    bundle = next(generator)

    assert bundle.vmList == [vm]
    ocFactory.assert_called_once_with(
        ns='initial-ns',
        context='initial-context',
    )
    virtCtlFactory.assert_called_once_with(
        ns='initial-ns',
        kubeconfig='/initial-config',
    )
    MUT.YAMLcfg.Render.assert_called_once_with(
        Path('/repo/conf/initial.yaml'),
        {'vmName': 'initial'},
    )
    generator.close()
    MUT.VM.CleanUpVMs.assert_called_once_with(
        bundle.vmList,
        [(oc, 'initial', 'initial-uid')],
    )


def test_FxtVM_PerCallReturnsAreAggregatedAcrossBatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (True, '', ''),
        (True, '', ''),
        (True, '', ''),
        (True, '', ''),
        (True, '', ''),
    ]
    vmOne = mock.MagicMock(name='vmOne')
    vmTwo = mock.MagicMock(name='vmTwo')
    vmThree = mock.MagicMock(name='vmThree')
    MUT.VM.side_effect = [vmOne, vmTwo, vmThree]
    ocFactory = mock.MagicMock()
    ocFactory.return_value.NewRes.return_value = (
        SimpleNamespace(name='APPLIED'),
        CommandResult(True),
    )
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 0}),
        ocFactory,
        mock.MagicMock(),
    )
    bundle = next(generator)

    firstBatch = bundle.vmCreate(count=1, namePfx='first')
    secondBatch = bundle.vmCreate(count=2, namePfx='second')

    assert firstBatch == [vmOne]
    assert secondBatch == [vmTwo, vmThree]
    assert bundle.vmList == [vmOne, vmTwo, vmThree]
    generator.close()
    MUT.VM.CleanUpVMs.assert_called_once_with(bundle.vmList, [])


def test_FxtVM_VMcreateAllowsCLIOverrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    MUT.VM.GetVMuid.return_value = (True, 'existing', '')
    defaultOC = mock.MagicMock()
    defaultVirtCtl = mock.MagicMock()
    selectedOC = mock.MagicMock(return_value=OCmock())
    selectedVirtCtl = mock.MagicMock()
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 0}),
        defaultOC,
        defaultVirtCtl,
    )
    bundle = next(generator)

    created = bundle.vmCreate(
        count=1,
        reuseExisting=True,
        ns='selected-ns',
        cliCfg=NamedDict(
            ocCfg={'context': 'selected-context'},
            vcCfg={'kubeconfig': '/selected-config'},
        ),
        ocCLI=selectedOC,
        virtCtlCLI=selectedVirtCtl,
    )

    assert created == [MUT.VM.return_value]
    selectedOC.assert_called_once_with(
        ns='selected-ns',
        context='selected-context',
    )
    selectedVirtCtl.assert_called_once_with(
        ns='selected-ns',
        kubeconfig='/selected-config',
    )
    defaultOC.assert_not_called()
    defaultVirtCtl.assert_not_called()
    generator.close()


@pytest.mark.parametrize('argument', ['request', 'vmList', 'ownVMs'])
def test_FxtVM_VMcreateRejectsInternalKeywordReplacementBeforeOperations(
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    ocFactory = mock.MagicMock()
    virtCtlFactory = mock.MagicMock()
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 0}),
        ocFactory,
        virtCtlFactory,
    )
    bundle = next(generator)
    sharedVMs = bundle.vmCreate.args[1]
    sharedOwnership = bundle.vmCreate.args[2]

    with pytest.raises(TypeError, match='multiple values'):
        bundle.vmCreate(**{argument: object()})

    assert bundle.vmCreate.args[1] is sharedVMs
    assert bundle.vmCreate.args[2] is sharedOwnership
    assert bundle.vmList is sharedVMs
    assert bundle.vmList == []
    assert sharedOwnership == []
    MUT.VM.GetVMuid.assert_not_called()
    ocFactory.assert_not_called()
    virtCtlFactory.assert_not_called()
    generator.close()


def test_FxtVM_PreyieldPartialFailureCleansCreatedVMs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (True, 'uid-zero', ''),
        (False, '', 'second lookup failed'),
    ]
    vmZero = mock.MagicMock(name='vmZero')
    MUT.VM.return_value = vmZero
    ocZero = OCmock('ocZero')
    ocOne = OCmock('ocOne')
    ocZero.NewRes.return_value = (
        SimpleNamespace(name='WAITED'),
        CommandResult(True),
    )
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 2, 'namePfx': 'preyield'}),
        mock.MagicMock(side_effect=[ocZero, ocOne]),
        mock.MagicMock(),
    )

    with pytest.raises(RuntimeError, match='second lookup failed'):
        next(generator)

    MUT.VM.CleanUpVMs.assert_called_once_with(
        [vmZero],
        [(ocZero, 'preyield-0', 'uid-zero')],
    )


def test_FxtVM_PostyieldPartialFailureCleansCreatedVMsOnClose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, 'VM')
    Utils.AutoPatch(monkeypatch, MUT.YAMLcfg, 'Render')
    MUT.YAMLcfg.Render.return_value = 'yaml'
    MUT.VM.GetVMuid.side_effect = [
        (True, '', ''),
        (True, 'uid-zero', ''),
        (False, '', 'second lookup failed'),
    ]
    vmZero = mock.MagicMock(name='vmZero')
    MUT.VM.return_value = vmZero
    ocZero = OCmock('ocZero')
    ocOne = OCmock('ocOne')
    ocZero.NewRes.return_value = (
        SimpleNamespace(name='WAITED'),
        CommandResult(True),
    )
    generator = MUT.FxtVM.__wrapped__(
        Request({'count': 0}),
        mock.MagicMock(side_effect=[ocZero, ocOne]),
        mock.MagicMock(),
    )
    bundle = next(generator)

    with pytest.raises(RuntimeError, match='second lookup failed'):
        bundle.vmCreate(count=2, namePfx='postyield')

    MUT.VM.CleanUpVMs.assert_not_called()
    generator.close()
    MUT.VM.CleanUpVMs.assert_called_once_with(
        [vmZero],
        [(ocZero, 'postyield-0', 'uid-zero')],
    )

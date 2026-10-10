from unittest import mock

import pytest

import fixtures.CLI as MUT
import Utils


def test_OCcli_UsesDefaultAndCustomOptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, '_OCcli')
    factory = MUT.OCcli.__wrapped__()

    first = factory()
    second = factory(ns='custom', kubeconfig='/kube')

    assert first is MUT._OCcli.return_value
    assert second is MUT._OCcli.return_value
    assert MUT._OCcli.call_args_list == [
        mock.call(n='default'),
        mock.call(n='custom', kubeconfig='/kube'),
    ]


def test_VirtCtlCLI_UsesDefaultAndCustomOptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Utils.AutoPatch(monkeypatch, MUT, '_VirtCtlCLI')
    factory = MUT.VirtCtlCLI.__wrapped__()

    first = factory()
    second = factory(ns='custom', kubeconfig='/kube')

    assert first is MUT._VirtCtlCLI.return_value
    assert second is MUT._VirtCtlCLI.return_value
    assert MUT._VirtCtlCLI.call_args_list == [
        mock.call(n='default'),
        mock.call(n='custom', kubeconfig='/kube'),
    ]

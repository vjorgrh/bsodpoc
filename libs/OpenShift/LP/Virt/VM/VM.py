'''
KubeVirt VirtualMachine wrapper with lifecycle and SSH management.
'''
import logging
from typing import Optional

from libs.CustomTypes import NamedDict
from libs.OpenShift.LP.Virt.CLI.VirtCtl import VirtCtlCLI
from libs.OpenShift.LP.Virt.VM.RHOVssh import RHOVsshCon
from libs.OpenShift.OCP.CLI.OC import OCcli


logs = logging.getLogger(__name__)


class VM:
    '''
    Wrapper around a KubeVirt `VirtualMachine` resource.

    Provides `Start`/`Stop` lifecycle via `virtCtl`, and lazy SSH
    access via `RHOVsshCon`.
    '''

    @staticmethod
    def GetVMuid(oc: OCcli, vmName: str) -> tuple[bool, str, str]:
        '''Return the VM UID lookup status, UID, and error output.'''
        result = oc.Run(
            'get',
            f'VirtualMachine/{vmName}',
            o='jsonpath={.metadata.uid}',
            ignore_not_found=True,
        )
        return (result.success, result.stdout.strip(), result.stderr.strip())

    def __init__(
        self,
        name: str,
        ns: str,
        oc: Optional[OCcli] = None,
        virtCtl: Optional[VirtCtlCLI] = None,
        sshUsr: str = 'qa-usr',
        sshKey: Optional[str] = None,
    ) -> None:
        '''
        :param name: VM resource name.
        :param ns: Kubernetes Namespace.
        :param oc:
            Optional `OCcli` instance. If `None`, a default instance is created
            with `ns` pre-configured.
        :param virtCtl:
            Optional `VirtCtlCLI` instance. If `None`, a default instance is
            created with `ns` pre-configured.
        :param sshUsr: SSH UserName (default: `'qa-usr'`).
        :param sshKey:
            Path to the SSH private key. If `None`, depends on the `ssh` client
            used (for OpenSSH, it defaults to `~/.ssh/id_<xxx>`).
        '''
        self.name = name
        self.namespace = ns
        self.cli = NamedDict(
            oc=(oc or OCcli(n=ns)),
            virtCtl=(virtCtl or VirtCtlCLI(n=ns)),
        )
        self.sshUsr = sshUsr
        self.sshKey = sshKey
        self._ssh: Optional[RHOVsshCon] = None

    def _Status(self) -> str:
        '''Query the VM's current `printableStatus` via `oc get`.'''
        result = self.cli.oc.Run(
            'get', f'VirtualMachine/{self.name}',
            o="jsonpath='{.status.printableStatus}'",
        )
        return result.stdout.strip("'") if result.success else ''

    def Start(self) -> bool:
        '''
        Start the VM if not already running or transitioning.

        :return: `True` if the VM is starting or was already active.
        '''
        if self._Status() in (
            'Running', 'Starting', 'Scheduling', 'Provisioning', 'Migrating'
        ): return True
        return self.cli.virtCtl.Run('start', self.name).success

    def Stop(self) -> bool:
        '''
        Stop the VM if not already stopped or transitioning.

        :return: `True` if the VM is stopping or was already inactive.
        '''
        if self._Status() in ('Stopped', 'Stopping'): return True
        return self.cli.virtCtl.Run('stop', self.name).success

    def NewSSH(self, probeTO: int = 300, **kwargs) -> RHOVsshCon:
        '''
        Create a new `RHOVsshCon` instance for this VM.

        Probes SSH readiness before returning. Blocks up to `probeTO` seconds
        waiting for SSH Server in the VM to become reachable.

        :param probeTO: SSH probe timeout in seconds (default: `300`).
        :param kwargs:
            Forwarded to `RHOVsshCon.__init__` (override `user`, `idFile`,
            `kubeconfig`, etc.).
        :return:
            A new `RHOVsshCon` instance, probed for readiness.
        '''
        defArgs = {
            'ns': self.namespace,
            'host': self.name,
            'user': self.sshUsr,
            'idFile': self.sshKey or '~/.ssh/id_ed25519',
        }
        conn = RHOVsshCon(**{**defArgs, **kwargs})
        conn.Probe(timeout=probeTO)
        return conn

    def RmvSSH(self) -> None:
        '''Remove and close the SSH connection, if active.'''
        if self._ssh is not None:
            self._ssh.Close()
            self._ssh = None

    @property
    def ssh(self) -> RHOVsshCon:
        '''Lazy default SSH connection (created on first access).'''
        if self._ssh is None:
            self._ssh = self.NewSSH()
        return self._ssh

import logging
import os
from pathlib import Path
from typing import Optional

from libs.utils.CmdExec import CmdExec, CmdRes

logs = logging.getLogger(__name__)


class RHOVsshCon:
    '''
    Persistent SSH ControlMaster connection to a RHOV/KubeVirt VM,
    established via `virtctl ssh`.
    '''

    def __init__(
        self,
        ns: str,
        host: str,
        user: str,
        idFile: str,
        kubeconfig: Optional[str] = None,
        binPath: str = 'virtctl',
        ctrlPersist: str = '4h',
        cmdExec: Optional[CmdExec] = None,
    ) -> None:
        '''
        Initialize the SSH ControlMaster connection settings.

        :param ns: Kubernetes Namespace where the target VM resides.
        :param host: Name of the target VM.
        :param user: SSH username to connect as.
        :param idFile: Path to the SSH private key used for authentication.
        :param kubeconfig:
            Optional path to `KUBECONFIG` file for CLI invocation
            (default: read from Env. Var. `KUBECONFIG` or `None`).
        :param binPath: Path to the `virtctl` executable (default: 'virtctl').
        :param ctrlPersist: ControlMaster idle timeout (default: '4h').
        :param cmdExec: Optional command executor instance.
        '''
        self.ns = ns
        self.host = host
        self.user = user
        self.idFile = idFile
        self.kubeconfig = kubeconfig or os.environ.get('KUBECONFIG') or None
        self.binPath = binPath
        self.ctrlPersist = ctrlPersist
        self.cmdExec = cmdExec or CmdExec()
        self.target = f'{user}@{host}'
        self.ctrlPath = f'/tmp/ssh..{user}@{host}..sock'

    def IsAlive(self) -> bool:
        '''
        Check if the ControlMaster socket is active and responding.

        :return: True if the master connection is alive, False otherwise.
        '''
        result = self.cmdExec.Run(
            ['ssh', '-O', 'check', '-o', f'ControlPath={self.ctrlPath}', 'muxSock'],
        )
        return result.success

    def Connect(self) -> None:
        '''
        Establish the persistent ControlMaster connection if not already active.

        :raises RuntimeError: If tunnel establishment fails.
        '''
        if self.IsAlive(): return

        self.Close()    # Tear down any stale socket before re-establishing.
        cmd = [
            self.binPath,
            *(['--kubeconfig', self.kubeconfig] if self.kubeconfig else []),
            '-n', self.ns,
            'ssh',
            '-t', '-o UserKnownHostsFile=/dev/null',
            '-t', '-o StrictHostKeyChecking=no',
            '-t', '-o ControlMaster=yes',
            '-t', f'-o ControlPath={self.ctrlPath}',
            '-t', f'-o ControlPersist={self.ctrlPersist}',
            '-t', '-N',
            '-i', self.idFile,
            f'{self.user}@vm/{self.host}',
        ]
        logs.info(f'Establishing SSH ControlMaster tunnel to `{self.target}`.')
        result = self.cmdExec.Run(cmd)
        if not result.success:
            raise RuntimeError(f'Failed to establish SSH tunnel to {self.target}: {result.stderr}')

    def Close(self) -> None:
        '''Tear down the ControlMaster connection, if active.'''
        self.cmdExec.Run(
            ['ssh', '-O', 'exit', '-o', f'ControlPath={self.ctrlPath}', 'muxSock'],
        )

    def RunShell(self, command: str, stdin: Optional[str] = None) -> CmdRes:
        '''
        Run a command in the VM's default shell.

        :param command: Shell command to execute on the remote guest.
        :param stdin:
            Optional raw input piped verbatim to standard input.
            Caller must include trailing line terminator if required by the
            last input line.
        :return: CmdRes containing execution result.
        '''
        self.Connect()
        cmd = [
            'ssh',
            '-o', 'ControlMaster=no',
            '-o', f'ControlPath={self.ctrlPath}',
            'muxSock',
            command,
        ]
        logs.info(f'Running remote command on {self.target}: {command}')
        return self.cmdExec.Run(cmd, stdin=stdin)

    def RunPowerShell(self, script: str) -> CmdRes:
        '''
        Run a PowerShell script on the VM.

        :param script:
            PowerShell script text (piped verbatim to standard input).
            Caller must include trailing line terminator if required by the
            last input line.
        :return: CmdRes containing execution result.
        '''
        return self.RunShell('powershell.exe -NonInteractive -File -', script)

    def Send(self, localPath: Path, remotePath: str) -> CmdRes:
        '''
        Copy local files to the VM via SCP.

        :param localPath: Local file path to send.
        :param remotePath: Destination file path on the remote guest.
        :return: CmdRes with the SCP result.
        '''
        self.Connect()
        cmd = [
            'scp',
            '-o', 'ControlMaster=no',
            '-o', f'ControlPath={self.ctrlPath}',
            str(localPath),
            f'muxSock:{remotePath}',
        ]
        logs.info(f'Copying {localPath} to {self.target}:{remotePath}')
        return self.cmdExec.Run(cmd)

    def Recv(self, remotePath: Path, localPath: str) -> CmdRes:
        '''
        Copy remote files from the VM to local filesystem via SCP.

        :param remotePath: Source file path on the remote guest.
        :param localPath: Destination file path on the local machine.
        :return: CmdRes with the SCP result.
        '''
        self.Connect()
        cmd = [
            'scp',
            '-o', 'ControlMaster=no',
            '-o', f'ControlPath={self.ctrlPath}',
            f'muxSock:{remotePath}',
            str(localPath),
        ]
        logs.info(f'Downloading {self.target}:{remotePath} to {localPath}')
        return self.cmdExec.Run(cmd)

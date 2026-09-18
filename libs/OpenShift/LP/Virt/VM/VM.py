import logging
import os
from typing import List, Optional

from libs.utils.CmdExec import CmdExec, CmdRes

logs = logging.getLogger(__name__)

class VirtctlSSH:
     '''SSH connections and command execution in VMs using virtctl'''

     def __init__(
        self,
        vmName: str,
        namespace: str,
        username: str,
        identityFile: Optional[str] = None,
        runner: Optional[CmdExec] = None
      ):
        self.vmName = vmName
        self.namespace = namespace
        self.username = username
        self.identityFile = identityFile
        self.runner = runner or CmdExec()


     def _buildBaseSshCmd(self) -> List[str]:

        cmd = [
              'virtctl',
              'ssh',
              f'vmi/{self.vmName}',
              '-n',
              self.namespace,
              '--username',
              self.username,
        ]

        if self.identityFile:
            # Expand tilde (~) to full user directory path
            expanded_key = os.path.expanduser(self.identityFile)
            cmd.extend(['--identity-file', expanded_key])
        return cmd

     def ExecuteRemoteCommand(self, remoteCmd: str, timeout: int = 60) -> CmdRes:
         fullCommand = self._buildBaseSshCmd()
         fullCommand.extend(['--command', remoteCmd])
         logs.info(f'Executing remote command on {self.vmName} ...')
         execution = self.runner.Run(fullCommand)
         return execution

import logging
import os 
from typing import List, Optional

from .command_runner import CommandRunner, CommandResult

logs = logging.getLogger(__name__)

class VirtctlSSH:
     """SSH connections and command execution in VM's using virtctl"""

     def __init__(
        self,
        vmName: str,
        namespace: str,
        username: str,
        identityFile: Optional[str] = None,
        runner: Optional[CommandRunner] = None
      ):
        self.vmName = vmName
        self.namespace = namespace
        self.username = username
        self.identityFile = identityFile
        self.runner = runner or CommandRunner()


     def _buildBaseSshCmd(self) -> List[str]:

        cmd = [
              "virtctl",
              "ssh",
              f"vmi/{self.vmName}",
              "-n",
              self.namespace,
              "--username",
              self.username,
        ]

        if self.identityFile:
            # Expand tilde (~) to full user directory path
            expanded_key = os.path.expanduser(self.identityFile)
            cmd.extend(["--identity-file", expanded_key])
        return cmd

     def executeRemoteCommand(self, remoteCmd: str, timeout: int = 60) -> CommandResult:
         fullCommand = self._buildBaseSshCmd()
         fullCommand.extend(["--command", remoteCmd])
         logs.info(f"Executing remote command on {self.vmName} ...")
         execution = self.runner.run(fullCommand)
         return execution

import logging
from typing import List, Optional

from .command_runner import CommandRunner

logs = logging.getLogger(__name__)

class VirtctlSSH:
     """SSH connections and command execution in VM's using virtctl"""

     def __init__(
        self,
        vm_name: str,
        namespace: str,
        username: str,
        identity_file: Optional[str] = None,
        runner: Optional[CommandRunner] = None
      ):
        self.vm_name = vm_name
        self.namespace = namespace
        self.username = username
        self.identity_file = identity_file
        self.runner = runner or CommandRunner()


     def _build_base_ssh_cmd(self) -> List[str]:

        cmd = [
              "virtctl",
              "ssh",
              f"vmi/{self.vm_name}",
              "-n",
              self.namespace,
              "--username",
              self.username,
        ]
      
        if self.identity_file:
           cmd.extend(["--identity-file", self.identity_file])
        return cmd

     def execute_remote_command(self, remote_cmd: str, timeout: int = 60) -> str:
         full_command = self._build_base_ssh_cmd()
         full_command.extend(["--command", remote_cmd])
         logs.info(f"Executing remote command on {self.vm_name} ...")
         execution =  self.runner.run(full_command)
         return execution 

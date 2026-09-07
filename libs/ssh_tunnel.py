import re
import logging
from pathlib import Path
from typing import Optional

from .command_runner import CommandRunner, CommandResult

logs = logging.getLogger(__name__)

class VirtctlSshTunnel:
    """Persistent SSH ControlMaster tunnel into a VM, established via `virtctl ssh`."""

    def __init__(
        self,
        target: str,
        namespace: str,
        identityFile: str,
        binPath: str = "virtctl",
        kubeconfig: Optional[str] = None,
        controlPersist: str = "4h",
        runner: Optional[CommandRunner] = None,
    ) -> None:
        self.target = target
        self.namespace = namespace
        self.identityFile = identityFile
        self.binPath = binPath
        self.kubeconfig = kubeconfig
        self.controlPersist = controlPersist
        self.runner = runner or CommandRunner()
        socketTarget = re.sub(r"@[^/]*/", "@", target)
        self.controlPath = f"/tmp/ssh..{socketTarget}..sock"

    def isAlive(self) -> bool:
        """Returns True if the ControlMaster socket is alive and reachable."""
        result = self.runner.run(
            ["ssh", "-O", "check", "-o", f"ControlPath={self.controlPath}", self.target],
            retries=0,
        )
        return result.success

    def ensure(self) -> None:
        """Establishes the ControlMaster connection if one isn't already alive."""
        if self.isAlive():
            return

        self.runner.run(
            ["ssh", "-O", "exit", "-o", f"ControlPath={self.controlPath}", self.target],
            retries=0,
        )

        kubeconfigPrefix = f"KUBECONFIG={self.kubeconfig} " if self.kubeconfig else ""
        cmd = (
            f'{kubeconfigPrefix}{self.binPath} -n {self.namespace} ssh '
            f'-t "-o UserKnownHostsFile=/dev/null" '
            f'-t "-o StrictHostKeyChecking=no" '
            f'-t "-o ControlMaster=yes" '
            f'-t "-o ControlPath={self.controlPath}" '
            f'-t "-o ControlPersist={self.controlPersist}" '
            f'-t "-N" '
            f'-i {self.identityFile} '
            f'{self.target}'
        )
        logs.info(f"Establishing SSH ControlMaster tunnel to {self.target}")
        result = self.runner.run(cmd, shell=True, retries=0)
        if not result.success:
            raise RuntimeError(f"Failed to establish SSH tunnel to {self.target}: {result.stderr}")

    def close(self) -> None:
        """Tears down the ControlMaster connection, if any."""
        self.runner.run(
            ["ssh", "-O", "exit", "-o", f"ControlPath={self.controlPath}", self.target],
            retries=0,
        )

    def runPowershell(self, script: str) -> CommandResult:
        """Runs a PowerShell script on the VM over the existing (or newly established) tunnel."""
        self.ensure()
        body = script if script.endswith("\n") else script + "\n"
        cmd = (
            f'ssh -o ControlMaster=no -o "ControlPath={self.controlPath}" {self.target} '
            f"'powershell.exe -NonInteractive -File -' <<'PS_EOF'\n"
            f"{body}\n"
            f"PS_EOF"
        )
        logs.info(f"Running remote PowerShell script on {self.target}")
        return self.runner.run(cmd, shell=True, retries=0)

    def runShell(self, command: str) -> CommandResult:
        """Runs a shell command (or script) on the VM over the existing (or newly established) tunnel."""
        self.ensure()
        cmd = [
            "ssh",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.controlPath}",
            self.target,
            command,
        ]
        logs.info(f"Running remote command on {self.target}: {command}")
        return self.runner.run(cmd, retries=0)

    def send(self, localPath: Path, remotePath: str) -> CommandResult:
        """Copies a local file to the VM over the existing (or newly established) tunnel."""
        self.ensure()
        target = re.sub(r"@vm/", "@", self.target)
        cmd = [
            "scp",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.controlPath}",
            str(localPath),
            f"{target}:/{remotePath}",
        ]
        logs.info(f"Copying {localPath} to {target}:{remotePath}")
        return self.runner.run(cmd, retries=0)

    def receive(self, remotePath: Path, localPath: str) -> CommandResult:
        """Receives a remote file in the VM over the existing (or newly established) tunnel."""
        self.ensure()
        target = re.sub(r"@vm/", "@", self.target)
        cmd = [
            "scp",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.controlPath}",
            f"{target}:/{remotePath}",
            str(localPath),
        ]
        logs.info(f"Downloading {target}:{remotePath} to {localPath}")
        return self.runner.run(cmd, retries=0)

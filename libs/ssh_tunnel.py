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
        identity_file: str,
        bin_path: str = "virtctl",
        kubeconfig: Optional[str] = None,
        control_persist: str = "4h",
        runner: Optional[CommandRunner] = None,
    ) -> None:
        self.target = target
        self.namespace = namespace
        self.identity_file = identity_file
        self.bin_path = bin_path
        self.kubeconfig = kubeconfig
        self.control_persist = control_persist
        self.runner = runner or CommandRunner()
        socket_target = re.sub(r"@[^/]*/", "@", target)
        self.control_path = f"/tmp/ssh..{socket_target}..sock"

    def is_alive(self) -> bool:
        """Returns True if the ControlMaster socket is alive and reachable."""
        result = self.runner.run(
            ["ssh", "-O", "check", "-o", f"ControlPath={self.control_path}", self.target],
            retries=0,
        )
        return result.success

    def ensure(self) -> None:
        """Establishes the ControlMaster connection if one isn't already alive."""
        if self.is_alive():
            return

        self.runner.run(
            ["ssh", "-O", "exit", "-o", f"ControlPath={self.control_path}", self.target],
            retries=0,
        )

        kubeconfig_prefix = f"KUBECONFIG={self.kubeconfig} " if self.kubeconfig else ""
        cmd = (
            f'{kubeconfig_prefix}{self.bin_path} -n {self.namespace} ssh '
            f'-t "-o UserKnownHostsFile=/dev/null" '
            f'-t "-o StrictHostKeyChecking=no" '
            f'-t "-o ControlMaster=yes" '
            f'-t "-o ControlPath={self.control_path}" '
            f'-t "-o ControlPersist={self.control_persist}" '
            f'-t "-N" '
            f'-i {self.identity_file} '
            f'{self.target}'
        )
        logs.info(f"Establishing SSH ControlMaster tunnel to {self.target}")
        result = self.runner.run(cmd, shell=True, retries=0)
        if not result.success:
            raise RuntimeError(f"Failed to establish SSH tunnel to {self.target}: {result.stderr}")

    def close(self) -> None:
        """Tears down the ControlMaster connection, if any."""
        self.runner.run(
            ["ssh", "-O", "exit", "-o", f"ControlPath={self.control_path}", self.target],
            retries=0,
        )

    def run_powershell(self, script: str) -> CommandResult:
        """Runs a PowerShell script on the VM over the existing (or newly established) tunnel."""
        self.ensure()
        body = script if script.endswith("\n") else script + "\n"
        cmd = (
            f'ssh -o ControlMaster=no -o "ControlPath={self.control_path}" {self.target} '
            f"'powershell.exe -NonInteractive -File -' <<'PS_EOF'\n"
            f"{body}\n"
            f"PS_EOF"
        )
        logs.info(f"Running remote PowerShell script on {self.target}")
        return self.runner.run(cmd, shell=True, retries=0)

    def run_shell(self, command: str) -> CommandResult:
        """Runs a shell command (or script) on the VM over the existing (or newly established) tunnel."""
        self.ensure()
        cmd = [
            "ssh",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.control_path}",
            self.target,
            command,
        ]
        logs.info(f"Running remote command on {self.target}: {command}")
        return self.runner.run(cmd, retries=0)

    def send(self, local_path: Path, remote_path: str) -> CommandResult:
        """Copies a local file to the VM over the existing (or newly established) tunnel."""
        self.ensure()
        target = re.sub(r"@vm/", "@", self.target)
        cmd = [
            "scp",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.control_path}",
            str(local_path),
            f"{target}:/{remote_path}",
        ]
        logs.info(f"Copying {local_path} to {target}:{remote_path}")
        return self.runner.run(cmd, retries=0)

    def receive(self, remote_path: Path, local_path: str) -> CommandResult:
        """Receives a remote file in the VM over the existing (or newly established) tunnel."""
        self.ensure()
        target = re.sub(r"@vm/", "@", self.target)
        cmd = [
            "scp",
            "-o", "ControlMaster=no",
            "-o", f"ControlPath={self.control_path}",
            f"{target}:/{remote_path}",
            str(local_path),
        ]
        logs.info(f"Downloading {target}:{remote_path} to {local_path}")
        return self.runner.run(cmd, retries=0)

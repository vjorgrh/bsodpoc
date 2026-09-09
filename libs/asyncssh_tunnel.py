"""AsyncSSH-based SSH tunnel for VM access via virtctl (modern approach)."""
import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import asyncssh

logs = logging.getLogger(__name__)


class AsyncVMUnderTest:
    """AsyncSSH-based SSH tunnel into a VM via virtctl with session multiplexing."""

    def __init__(
        self,
        vm_name: str,
        namespace: str,
        kubeconfig: Optional[str] = None,
        identity_file: Optional[str] = None,
        ssh_key_passphrase: Optional[str] = None,
    ) -> None:
        self.vm_name = vm_name
        self.namespace = namespace
        self.kubeconfig = kubeconfig or ""
        self.identity_file = identity_file or str(Path.home() / ".ssh" / "id_ed25519")
        self.ssh_key_passphrase = ssh_key_passphrase

        # Target format for virtctl
        self.target = f"Administrator@vm/{vm_name}"
        self.connection: Optional[asyncssh.SSHClientConnection] = None

    async def connect(self) -> None:
        """Test connection availability via virtctl."""
        logs.info(f"Testing virtctl SSH access to {self.vm_name}")
        try:
            # Just verify virtctl can reach the VM via a simple command
            env = dict(os.environ)
            if self.kubeconfig:
                env["KUBECONFIG"] = self.kubeconfig

            # Disable SSH askpass prompts
            env["DISPLAY"] = ""
            env["SSH_ASKPASS_REQUIRE"] = "never"

            result = await asyncio.create_subprocess_exec(
                "virtctl",
                "-n", self.namespace,
                "ssh",
                "-i", self.identity_file,
                "-t", "-o StrictHostKeyChecking=no",
                "-c", "echo 'Connected'",
                f"Administrator@vm/{self.vm_name}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await result.communicate()
            if result.returncode == 0:
                logs.info(f"✓ SSH access verified for {self.vm_name}")
                self.connection = True  # Mark as connected
            else:
                raise Exception(f"SSH verification failed: {stderr.decode()}")
        except Exception as e:
            logs.error(f"Failed to verify SSH access to {self.vm_name}: {e}")
            raise

    async def send_cmd(self, cmd: str, timeout: int = 30) -> dict:
        """Run a command on the VM over SSH via virtctl."""
        await self.connect()

        logs.info(f"Running command on {self.vm_name}: {cmd}")

        try:
            env = dict(os.environ)
            if self.kubeconfig:
                env["KUBECONFIG"] = self.kubeconfig

            proc = await asyncio.create_subprocess_exec(
                "virtctl",
                "-n", self.namespace,
                "ssh",
                "-i", self.identity_file,
                "-t", "-o StrictHostKeyChecking=no",
                "-c", cmd,
                f"Administrator@vm/{self.vm_name}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            logs.error(f"Command timed out on {self.vm_name}: {cmd}")
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timeout",
                "exit_code": 124,
            }
        except Exception as e:
            logs.error(f"Command failed on {self.vm_name}: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }

    async def run_powershell(self, script: str, timeout: int = 60) -> dict:
        """Run PowerShell script on Windows VM via virtctl."""
        # Build PowerShell command
        ps_cmd = f"powershell.exe -NonInteractive -Command '{script}'"

        logs.info(f"Running PowerShell on {self.vm_name}")

        try:
            await self.connect()
            env = dict(os.environ)
            if self.kubeconfig:
                env["KUBECONFIG"] = self.kubeconfig

            proc = await asyncio.create_subprocess_exec(
                "virtctl",
                "-n", self.namespace,
                "ssh",
                "-i", self.identity_file,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-c", ps_cmd,
                f"Administrator@vm/{self.vm_name}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            logs.error(f"PowerShell timed out on {self.vm_name}")
            return {
                "success": False,
                "stdout": "",
                "stderr": "PowerShell timeout",
                "exit_code": 124,
            }
        except Exception as e:
            logs.error(f"PowerShell failed on {self.vm_name}: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }

    async def send_file(self, local_path: Path, remote_path: str) -> bool:
        """Upload file to VM via virtctl scp."""
        await self.connect()

        logs.info(f"Uploading {local_path} to {self.vm_name}:{remote_path}")

        try:
            env = dict(os.environ)
            if self.kubeconfig:
                env["KUBECONFIG"] = self.kubeconfig

            proc = await asyncio.create_subprocess_exec(
                "virtctl",
                "-n", self.namespace,
                "scp",
                "-i", self.identity_file,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                str(local_path),
                f"Administrator@vm/{self.vm_name}:{remote_path}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            _, stderr = await proc.communicate()
            if proc.returncode == 0:
                logs.info(f"✓ Uploaded {local_path} to {self.vm_name}:{remote_path}")
                return True
            else:
                logs.error(f"Upload failed: {stderr.decode()}")
                return False
        except Exception as e:
            logs.error(f"Failed to upload file: {e}")
            return False

    async def recv_file(self, remote_path: str, local_path: Path) -> bool:
        """Download file from VM via virtctl scp."""
        await self.connect()

        logs.info(f"Downloading {self.vm_name}:{remote_path} to {local_path}")

        try:
            env = dict(os.environ)
            if self.kubeconfig:
                env["KUBECONFIG"] = self.kubeconfig

            proc = await asyncio.create_subprocess_exec(
                "virtctl",
                "-n", self.namespace,
                "scp",
                "-i", self.identity_file,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                f"Administrator@vm/{self.vm_name}:{remote_path}",
                str(local_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            _, stderr = await proc.communicate()
            if proc.returncode == 0:
                logs.info(f"✓ Downloaded {self.vm_name}:{remote_path} to {local_path}")
                return True
            else:
                logs.error(f"Download failed: {stderr.decode()}")
                return False
        except Exception as e:
            logs.error(f"Failed to download file: {e}")
            return False

    async def close(self) -> None:
        """Close connection (virtctl doesn't maintain persistent connections)."""
        logs.info(f"Closing connection to {self.vm_name}")
        self.connection = None

    def __del__(self) -> None:
        """Cleanup on object destruction."""
        self.connection = None


class SyncAsyncVMUnderTest:
    """Synchronous wrapper around AsyncVMUnderTest for pytest."""

    def __init__(
        self,
        vm_name: str,
        namespace: str,
        kubeconfig: Optional[str] = None,
        identity_file: Optional[str] = None,
        ssh_key_passphrase: Optional[str] = None,
    ) -> None:
        self.vm_under_test = AsyncVMUnderTest(
            vm_name=vm_name,
            namespace=namespace,
            kubeconfig=kubeconfig,
            identity_file=identity_file,
            ssh_key_passphrase=ssh_key_passphrase,
        )
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    def send_cmd(self, cmd: str, timeout: int = 30) -> dict:
        """Synchronous wrapper for send_cmd."""
        return self._loop.run_until_complete(
            self.vm_under_test.send_cmd(cmd, timeout)
        )

    def run_powershell(self, script: str, timeout: int = 60) -> dict:
        """Synchronous wrapper for run_powershell."""
        return self._loop.run_until_complete(
            self.vm_under_test.run_powershell(script, timeout)
        )

    def send_file(self, local_path: Path, remote_path: str) -> bool:
        """Synchronous wrapper for send_file."""
        return self._loop.run_until_complete(
            self.vm_under_test.send_file(local_path, remote_path)
        )

    def recv_file(self, remote_path: str, local_path: Path) -> bool:
        """Synchronous wrapper for recv_file."""
        return self._loop.run_until_complete(
            self.vm_under_test.recv_file(remote_path, local_path)
        )

    def close(self) -> None:
        """Close the connection."""
        self._loop.run_until_complete(self.vm_under_test.close())
        self._loop.close()

    def __del__(self) -> None:
        """Cleanup."""
        try:
            if self._loop and not self._loop.is_closed():
                self.close()
        except Exception:
            pass

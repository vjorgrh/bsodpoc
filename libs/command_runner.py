import subprocess
import time
import logging
from typing import List, Union, NamedTuple, Optional

logs = logging.getLogger(__name__)

class CommandResult(NamedTuple):
     """Structured immutable output for executed commands."""
     stdout: str
     stderr: str
     exitCode: int
     success: bool


class CommandRunner:
    """Execute shell commands locally with retry logic and structured error handling.

    Provides subprocess execution with configurable retries, timeout handling,
    and Red Hat-compliant error reporting via structured logging.
    """
    def __init__(self, defaultRetries: int = 3, wait: int = 3) -> None:
        """Initialize CommandRunner with retry configuration.

        Args:
            defaultRetries: Number of retries on command failure (default: 3)
            wait: Seconds to wait between retries (default: 3)
        """
        self.defaultRetries = defaultRetries
        self.wait = wait


    def run(self, command: Union[str, List[str]], retries: Optional[int] = None, shell: bool = False) -> CommandResult:
        """Execute a command locally with retry logic.

        Args:
            command: String (if shell=True) or List of strings (if shell=False).
            retries: Overrides default retry count if provided
            shell: True to run via shell wrapper (use with caution for security).

        Returns:
            CommandResult with stdout, stderr, exitCode, and success flag.
        """
        maxAttempts = (retries if retries is not None else self.defaultRetries) + 1
        for attempt in range(1, maxAttempts + 1):
            try:
                result = subprocess.run(
                    command,
                    shell=shell,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0:
                    logs.warning(
                        f"Command failed with exit code {result.returncode}: "
                        f"{result.stderr.strip()} (Attempt {attempt}/{maxAttempts}). "
                        f"Command: {command}"
                    )

                    if attempt < maxAttempts:
                        logs.info(f"Retrying execution in {self.wait}s (attempt {attempt}/{maxAttempts - 1})")
                        time.sleep(self.wait)
                        continue

                return CommandResult(
                    stdout=result.stdout.strip(),
                    stderr=result.stderr.strip(),
                    exitCode=result.returncode,
                    success=(result.returncode == 0))

            except (FileNotFoundError, PermissionError) as ex:
                logs.error(
                    f"Critical environment exception ({type(ex).__name__}): {ex}. "
                    f"Command: {command}"
                )
                return CommandResult(stdout="", stderr=str(ex), exitCode=-2, success=False)
            except subprocess.SubprocessError as ex:
                logs.warning(
                    f"Subprocess exception ({type(ex).__name__}): {ex} "
                    f"(Attempt {attempt}/{maxAttempts}). Command: {command}"
                )
                if attempt < maxAttempts:
                    logs.info(f"Retrying execution in {self.wait}s (attempt {attempt}/{maxAttempts - 1})")
                    time.sleep(self.wait)
                else:
                    return CommandResult(stdout="", stderr=str(ex), exitCode=-2, success=False)
        return CommandResult(stdout="", stderr="Max execution retries exceeded", exitCode=-3, success=False)

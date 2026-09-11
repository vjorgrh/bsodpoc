"""VmUnderTest: Convenience wrapper for VM management operations."""
import logging
from typing import Optional

logs = logging.getLogger()


class VmUnderTest:
    """VUT: krkn-lib VM management interface (status, scaling, deletion)."""

    def __init__(
        self,
        vm_name: str,
        namespace: str,
        krknChaos,
    ) -> None:
        self.vm_name = vm_name
        self.namespace = namespace
        self.krknChaos = krknChaos

    # ─────────────────────────────────────────────────────────────────
    # VM Status Operations
    # ─────────────────────────────────────────────────────────────────

    def get_vm_status(self) -> dict:
        """Get VM configuration status (CPU, memory, running state, etc.)."""
        logs.info(f"[{self.vm_name}] Getting VM status")
        return self.krknChaos.get_vm_status(self.vm_name, self.namespace)

    def get_vmi_status(self) -> dict:
        """Get VMInstance (running) status (phase, node, conditions)."""
        logs.info(f"[{self.vm_name}] Getting VMI status")
        return self.krknChaos.get_vmi_status(self.vm_name, self.namespace)

    # ─────────────────────────────────────────────────────────────────
    # VM Management Operations
    # ─────────────────────────────────────────────────────────────────

    def scale_vm(self, cpu: Optional[int] = None, memory: Optional[str] = None) -> dict:
        """Scale VM resources (CPU cores and/or memory)."""
        logs.info(f"[{self.vm_name}] Scaling: CPU={cpu}, Memory={memory}")
        return self.krknChaos.scale_vm_resources(
            vm_name=self.vm_name,
            cpu=cpu,
            memory=memory,
            namespace=self.namespace,
        )

    def delete_vm(self) -> bool:
        """Delete VM with graceful termination."""
        logs.info(f"[{self.vm_name}] Deleting VM")
        return self.krknChaos.delete_vm(self.vm_name, self.namespace)

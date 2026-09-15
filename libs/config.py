"""Production-grade configuration management using environment variables.

Supports any target type (VM, benchmark runner, pod, etc) and any namespace.

Environment variables:
- NAMESPACE: Kubernetes namespace (default: windows-bsod)
- TARGET_NAME: Target resource name - VM, benchmark runner, pod, etc (default: win2022-vm-hjoshi1)
- TARGET_TYPE: Optional documentation field (vm, benchmark, pod, etc)
"""

import os
import logging
from functools import lru_cache
from typing import Optional

logs = logging.getLogger()


class KrknConfig:
	"""Production-grade configuration loader using generic environment variables."""

	@lru_cache(maxsize=1)
	def get_namespace(self) -> str:
		"""
		Get Kubernetes namespace with priority fallback chain.

		Priority (highest to lowest):
		1. NAMESPACE environment variable
		2. Hardcoded default: "windows-bsod"

		Returns:
			str: Kubernetes namespace
		"""
		namespace = os.getenv("NAMESPACE", "windows-bsod")
		logs.info(f"Using namespace: {namespace}")
		return namespace

	@lru_cache(maxsize=1)
	def get_target_name(self) -> str:
		"""
		Get target resource name (VM, benchmark runner, pod, etc).

		Priority (highest to lowest):
		1. TARGET_NAME environment variable
		2. Hardcoded default: "win2022-vm-hjoshi1"

		Returns:
			str: Target resource name
		"""
		target_name = os.getenv("TARGET_NAME", "win2022-vm-hjoshi1")
		logs.info(f"Using target: {target_name}")
		return target_name

	@lru_cache(maxsize=1)
	def get_target_type(self) -> Optional[str]:
		"""
		Get target type for documentation (vm, benchmark, pod, etc).

		Returns:
			Optional[str]: Target type or None if not specified
		"""
		target_type = os.getenv("TARGET_TYPE")
		if target_type:
			logs.info(f"Target type: {target_type}")
		return target_type

	def get_config_summary(self) -> str:
		"""Get a summary of current configuration."""
		summary = f"Namespace: {self.get_namespace()}, Target: {self.get_target_name()}"
		target_type = self.get_target_type()
		if target_type:
			summary += f" (type: {target_type})"
		return summary


# Global singleton instance
_config_instance = None


def get_config() -> KrknConfig:
	"""Get or create global config instance."""
	global _config_instance
	if _config_instance is None:
		_config_instance = KrknConfig()
	return _config_instance


# Helper functions with caching for backwards compatibility
@lru_cache(maxsize=1)
def get_namespace() -> str:
	"""Get Kubernetes namespace."""
	return get_config().get_namespace()


@lru_cache(maxsize=1)
def get_target_name() -> str:
	"""Get target resource name (VM, benchmark runner, pod, etc)."""
	return get_config().get_target_name()


def get_target_type() -> Optional[str]:
	"""Get target type for documentation."""
	return get_config().get_target_type()


# Aliases for backwards compatibility with old variable names
@lru_cache(maxsize=1)
def get_vm_name() -> str:
	"""Alias for get_target_name (backwards compatibility)."""
	return get_target_name()

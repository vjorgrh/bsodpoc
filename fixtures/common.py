"""Constants and helpers shared across fixture modules."""

import os
import logging
import time

logs = logging.getLogger()

# Default namespace constant (used as fallback throughout fixtures)
DEFAULT_NAMESPACE = "test123"

# Import production-grade configuration system
# Generic names: NAMESPACE, TARGET_NAME, TARGET_TYPE
from fixtures.config import (
	get_namespace,
	get_target_name,
	get_target_type,
	get_vm_name,  # Alias for backwards compatibility
)


# Default container image used for host-level execution helper pods.
# Uses Red Hat's Universal Base Image (UBI9), which is publicly available on enterprise clusters.
NODE_EXEC_IMAGE = "registry.access.redhat.com/ubi9/ubi"


def execOnNode(client, node, command, podName, namespace,
               image=NODE_EXEC_IMAGE, timeout=120):
	"""Run a shell command on a node via a transient privileged pod, using
	krkn-lib primitives directly.
	"""
	# Construct a Kubernetes Pod dictionary manifest to be submitted via the API
	podBody = {
		"apiVersion": "v1",  # Core Kubernetes API version
		"kind": "Pod",  # Object type is a Pod
		"metadata": {"name": podName},  # Set the pod's metadata name
		"spec": {
			"hostNetwork": True,  # Allow pod to share the host worker node's network namespace
			"nodeName": node,  # Force Kubernetes to schedule this pod on the specific target node
			"restartPolicy": "Never",  # Do not restart container if it exits or completes
			"containers": [{  # List of containers inside the helper pod
				"name": "hosttools",  # Container identifier name
				"image": image,  # Container image to pull (UBI9)
				"command": ["/bin/sh", "-c", "sleep infinity"],  # Keep pod running indefinitely so we can exec into it
				"securityContext": {"privileged": True},  # Grant root/host kernel access privileges
				"volumeMounts": [{  # Mount host paths inside the container
					"mountPath": "/run/dbus/system_bus_socket",  # Mount destination path inside container
					"name": "dbus",  # Reference volume name
					"readOnly": True,  # Mount as read-only for security
				}],
			}],
			"volumes": [{  # Define host volumes to expose to the container
				"name": "dbus",  # Volume name
				"hostPath": {"path": "/run/dbus/system_bus_socket"},  # Physical host socket path
			}],
		},
	}

	# Best-effort pre-clean: Delete any lingering helper pod from a previous test run
	try:
		client.delete_pod(podName, namespace)  # Attempt to delete pod using krkn-lib client
		time.sleep(3)  # Wait 3 seconds for cluster cleanup
	except Exception:  # Catch and ignore errors if the pod didn't exist
		pass

	try:
		# Create the privileged helper pod on the target node and wait until it is Running (up to timeout)
		client.create_pod(podBody, namespace, timeout)

		# Execute the shell command inside the pod using krkn-lib and return its stdout.
		# Wrapped in a single-item list so krkn-lib passes it correctly to `bash -c "<command>"`
		return client.exec_cmd_in_pod([command], podName, namespace)
	finally:
		# Guarantee teardown: This block ALWAYS runs, even if creation or execution failed/crashed
		try:
			client.delete_pod(podName, namespace)  # Delete the transient helper pod to clean up node
		except Exception:  # If pod deletion fails, log a warning without crashing the entire test suite
			logs.warning(f"could not delete helper pod {podName} in {namespace}")

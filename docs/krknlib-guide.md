# krkn-lib in this project

How this repo uses [krkn-lib](https://github.com/krkn-chaos/krkn-lib) (Red Hat
Kraken's chaos library) to drive BSOD / VM-resiliency chaos tests against Windows
VMs on OpenShift Virtualization (KubeVirt).

> TL;DR — **krkn-lib injects the fault at the pod/node level; `oc` verifies
> recovery at the VM/VMI level.** krkn-lib understands pods and nodes, but has no
> concept of KubeVirt `VirtualMachine`/`VirtualMachineInstance` resources.

## Requirements

- Python **3.11** — krkn-lib 5.0.0 does not support newer interpreters. Use the
  provided `.venv`.
- `oc` and `virtctl` on `PATH`, logged in to the target cluster.
- A valid `KUBECONFIG` (or `~/.kube/config`) — used by **both** `oc` and krkn-lib.

## How it's wired: fixture + marker

Tests never import krkn-lib directly. A single fixture builds the client and hands
it to the test, bundled with the scenario's parameters.

```
@pytest.mark.krkn(...)          # declares the scenario params
        │
        ▼
krknChaos fixture (conftest.py) # builds KrknKubernetes(kubeconfig), merges params
        │
        ▼
KrknContext(client, params)     # what the test receives
```

- **`@pytest.mark.krkn(vmName=..., namespace=..., labelSelector=..., recoverTimeout=...)`**
  declares *what* scenario the test wants.
- **`krknChaos`** fixture (`conftest.py`) builds one `KrknKubernetes` client from
  the kubeconfig and yields it as `KrknContext(client, params)`.
- **`KRKN_DEFAULTS`** (`conftest.py`) supplies repo-wide defaults
  (`namespace`, `vmName`, `recoverTimeout`); a marker only needs to declare the diff:

  ```python
  params = {**KRKN_DEFAULTS, **(marker.kwargs if marker else {})}
  ```

Inside a test:

```python
def test_something(self, krknChaos):
    client = krknChaos.client      # krkn_lib.k8s.KrknKubernetes
    params = krknChaos.params       # merged defaults + marker kwargs
```

## krkn-lib primitives we use

Only a small, deliberate slice of krkn-lib's ~90 methods:

| krkn-lib call                                   | Role                                        |
| ----------------------------------------------- | ------------------------------------------- |
| `client.list_pods(namespace, label_selector)`   | Find the virt-launcher pod(s) behind the VM |
| `client.delete_pod(pod, ns)`                    | **The chaos** — kill the pod                |
| `client.is_pod_running(pod, ns)`                | Confirm the replacement pod came up         |
| `client.list_ready_nodes()`                     | Verify the VM's node is Ready               |
| `client.create_pod(body, ns, timeout)`          | Spin up a transient host-exec pod           |
| `client.exec_cmd_in_pod([cmd], pod, ns)`        | Run a command on the node                   |

## The two scenarios (`tests/test_chaos.py`)

### 1. `test_vmSurvivesVirtLauncherKill` — pod-kill + recovery

Simulates a node/pod failure and asserts KubeVirt self-heals:

1. `list_pods` → find the live virt-launcher pod.
2. `oc get vmi ... status.phase` → confirm the VM is `Running` first.
3. `delete_pod` → **the fault**.
4. Poll `list_pods` / `is_pod_running` **and** `oc get vmi status.phase` until a
   NEW launcher pod is `Running` and the VMI is back to `Running`
   (within `recoverTimeout`). With `runStrategy: Always`, KubeVirt must recover.

> ⚠️ **Disruptive** — this kills the live `hjoshi-win2022` launcher pod. Skip it
> with `--deselect` when you don't want disruption (see below).

### 2. `test_hostSideKernelScanOnVmNode` — host-side reach (read-only)

Proves we can execute on the worker node that runs the VM — the host level where
TLB-flush / `HYPERVISOR_ERROR` / split-lock (#AC) signatures show up in the kernel
log (they never reach the Windows guest dump):

1. `oc get vmi ... status.nodeName` → resolve the node.
2. `list_ready_nodes` → sanity-check it's Ready.
3. `execOnNode(... "uname -r")` → run a host-side command, assert output.
4. `execOnNode(... dmesg | grep -iE 'split.?lock|#AC|hypervisor')` → scan the
   host kernel log for BSOD-relevant signatures (logged, not asserted — a clean
   host is the healthy case).

## Division of labor: krkn-lib vs `oc`

| Layer                        | Tool     | Why                                                        |
| ---------------------------- | -------- | --------------------------------------------------------- |
| Pods, nodes, exec            | krkn-lib | Native support                                            |
| VM / VMI (`status.phase`, `status.nodeName`) | `oc`     | krkn-lib has no KubeVirt VM/VMI awareness |
| Guest (inside Windows)       | `virtctl ssh` | See `libs/vm.py` (`VirtctlSSH`)                       |

## Known krkn-lib bugs we work around

Both are handled by the module-level `execOnNode()` helper in `tests/test_chaos.py`,
a hand-rolled replacement for krkn-lib's `exec_command_on_node`:

1. **Dead node-exec image.** `exec_command_on_node` hardcodes
   `docker.io/fedora/tools`, which Docker Hub no longer serves → `ImagePullBackOff`,
   ~500s hang, and the pod is never cleaned up.
   **Fix:** we build the pod ourselves with a pullable image
   `registry.access.redhat.com/ubi9/ubi` (`NODE_EXEC_IMAGE`), a short timeout, and
   guaranteed cleanup in a `finally`.

2. **Argument drop in `exec_cmd_in_pod`.** It prepends `["bash", "-c"]` to the
   command, so a token list like `["uname", "-r"]` becomes `bash -c uname -r` —
   `-r` becomes a positional param and is silently dropped.
   **Fix:** we pass the command as a **single shell string in a one-element list**,
   `[command]`, so it runs as `bash -c "<command>"`.

## Running

Always use the `.venv` interpreter so `krkn_lib` resolves:

```bash
# Everything (includes the disruptive pod-kill):
.venv/bin/pytest tests/ -v

# Non-disruptive (skip the pod-kill):
.venv/bin/pytest tests/ -v \
  --deselect tests/test_chaos.py::TestChaos::test_vmSurvivesVirtLauncherKill

# Only krkn chaos scenarios:
.venv/bin/pytest -m krkn -v

# With an HTML report:
.venv/bin/pytest tests/ -v --html=report.html --self-contained-html
```

## File map

| File                          | Responsibility                                              |
| ----------------------------- | ---------------------------------------------------------- |
| `conftest.py`                 | `krknChaos` fixture, `KRKN_DEFAULTS`, `KrknContext`, `vm_create` |
| `tests/test_chaos.py`         | The two krkn-lib chaos scenarios + `execOnNode()` helper   |
| `libs/command_runner.py`      | Retry-wrapped `subprocess` runner (`oc` / `virtctl`)       |
| `libs/vm.py`                  | `VirtctlSSH` — run commands inside the Windows guest       |
| `libs/yaml_parser.py`         | Render `${VAR}` placeholders in VM YAML templates          |

# pytest

Pytest suite for chaos / BSOD resiliency testing of Windows VMs on OpenShift
Virtualization (KubeVirt). It provisions VMs three ways — templated YAML via
`oc apply`, or the [benchmark-runner](https://github.com/redhat-performance/benchmark-runner)
library (single VM or scaled across nodes) — reaches into guests over
`virtctl ssh`, and injects failures using
[krkn-lib](https://github.com/krkn-chaos/krkn-lib).

## Layout

- `libs/` — helper modules:
  - `CmdExec.py` — `CmdExec`, a retry-wrapped `subprocess` runner
    returning a structured `CmdRes`.
  - `vm.py` — `VirtctlSSH`, runs commands inside a guest via `virtctl ssh`.
  - `yaml_parser.py` — `ConfigLoader.loadAndSave`, renders a YAML template's
    `${VAR}` placeholders and writes the result.
- `config/` — source VM YAML templates (e.g. `vm-config-tlbflush-on.yaml`).
- `conftest.py` — just a `pytest_plugins` list registering the fixture modules
  under `fixtures/`; defines no fixtures itself.
- `fixtures/` — shared fixtures, one module per concern:
  - `vm_fixtures.py` — `vmCreate`: renders a VM config with a generated name,
    applies it via `oc`, yields the created VM names, and deletes them on
    teardown.
  - `krknlib_fixtures.py` — `krknChaos`: builds a krkn-lib `KrknKubernetes`
    client and exposes it (with the test's `@pytest.mark.krkn(...)` params) as
    a `KrknContext`.
  - `tunnel_fixtures.py` — `sshTunnelConnection`/`vmWithTunnel`: persistent
    `virtctl ssh` tunnels into a guest.
  - `benchmark_runner_fixtures.py` — `oc`/`windowsVM`/`windowsVMScale`:
    provisions Windows VMs (single or scaled across nodes) via
    benchmark-runner. See [`docs/benchmark-runner-guide.md`](docs/benchmark-runner-guide.md).
  - `common.py` — shared constants (`DEFAULT_NAMESPACE`).
- `tests/` — test cases:
  - `test_sample1.py` — VM creation + guest `sshd` reachability check, plus
    `test_benchmark_runner` (the benchmark-runner scale scenario).
  - `test_chaos.py` — krkn-lib chaos scenarios (virt-launcher pod-kill recovery,
    host-side node exec / kernel scan). See [`docs/krknlib-guide.md`](docs/krknlib-guide.md).

## Requirements

- Python 3.11 (krkn-lib 5.0.0 does not support newer interpreters; use the
  provided `.venv`).
- `oc` and `virtctl` CLIs configured and logged in to the target cluster.
- A valid `KUBECONFIG` (or `~/.kube/config`) — used by both `oc` and krkn-lib.
- Python dependencies pinned in `requirements.txt` (installed in `.venv`).
- For `benchmark`-marked tests: `benchmark-runner` installed (**not currently
  pinned in `requirements.txt`**) plus `KUBEADMIN_PASSWORD`, `WINDOWS_URL`,
  and (for the scale fixture) `NAMESPACE`, `WORKER_NODE_0`, `WORKER_NODE_1`,
  `SCALE` env vars — see [`docs/benchmark-runner-guide.md`](docs/benchmark-runner-guide.md).

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running tests

Use the `.venv` interpreter so `krkn_lib` resolves:

```bash
.venv/bin/pytest
# or: source .venv/bin/activate && pytest
```

Run only BSOD-marked tests:

```bash
.venv/bin/pytest -m bsod
```

Run only krkn-lib chaos scenarios:

```bash
.venv/bin/pytest -m krkn
```

Skip the disruptive virt-launcher pod-kill scenario:

```bash
.venv/bin/pytest --deselect tests/test_chaos.py::TestChaos::test_vmSurvivesVirtLauncherKill
```

Run only benchmark-runner scenarios (requires the env vars listed under
Requirements):

```bash
.venv/bin/pytest -m benchmark
```

Configuration (log format, test discovery, markers) lives in `pytest.ini`.

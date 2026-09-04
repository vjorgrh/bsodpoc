# pytest

Pytest suite for chaos / BSOD resiliency testing of Windows VMs on OpenShift
Virtualization (KubeVirt). It provisions VMs from templated YAML via
`oc apply`, reaches into guests over `virtctl ssh`, and injects failures using
[krkn-lib](https://github.com/krkn-chaos/krkn-lib).

## Layout

- `libs/` — helper modules:
  - `command_runner.py` — `CommandRunner`, a retry-wrapped `subprocess` runner
    returning a structured `CommandResult`.
  - `vm.py` — `VirtctlSSH`, runs commands inside a guest via `virtctl ssh`.
  - `yaml_parser.py` — `ConfigLoader.loadAndSave`, renders a YAML template's
    `${VAR}` placeholders and writes the result.
- `config/` — source VM YAML templates (e.g. `vm-config-tlbflush-on.yaml`).
- `conftest.py` — shared fixtures:
  - `vm_create` — renders a VM config with a generated name, applies it via `oc`,
    yields the created VM names, and deletes them on teardown.
  - `krknChaos` — builds a krkn-lib `KrknKubernetes` client and exposes it (with
    the test's `@pytest.mark.krkn(...)` params) as a `KrknContext`.
- `tests/` — test cases:
  - `test_sample1.py` — VM creation + guest `sshd` reachability check.
  - `test_chaos.py` — krkn-lib chaos scenarios (virt-launcher pod-kill recovery,
    host-side node exec / kernel scan).
- `replaced_config/` — rendered VM YAMLs are written here at runtime (gitignored).

## Requirements

- Python 3.11 (krkn-lib 5.0.0 does not support newer interpreters; use the
  provided `.venv`).
- `oc` and `virtctl` CLIs configured and logged in to the target cluster.
- A valid `KUBECONFIG` (or `~/.kube/config`) — used by both `oc` and krkn-lib.
- Python dependencies pinned in `requirements.txt` (installed in `.venv`).

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

Configuration (log format, test discovery, markers) lives in `pytest.ini`.

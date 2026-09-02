# pytest

Pytest suite for creating and validating OpenShift Virtualization (`oc apply`/KubeVirt) VMs from templated YAML configs.

## Layout

- `src/` — helper modules for running shell commands and rendering YAML config templates.
- `config/` — source VM YAML templates (e.g. `vm-config-tlbflush-on.yaml`).
- `conftest.py` — shared fixtures, including `vm_create`, which renders a VM config, applies it via `oc`, and returns VM statuses.
- `tests/` — test cases (e.g. `test_vm_create`).

## Requirements

- Python 3.14+
- `oc` CLI configured and logged in to the target OpenShift cluster
- Dependencies: `pyyaml`, `pytest`

## Running tests

```bash
pytest
```

Run only BSOD-marked tests:

```bash
pytest -m bsod
```

Configuration (log format, test discovery, markers) lives in `pytest.ini`.

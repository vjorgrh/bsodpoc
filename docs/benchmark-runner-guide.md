# benchmark-runner in this project

How this repo uses [benchmark-runner](https://github.com/redhat-performance/benchmark-runner)
as a library to provision and scale Windows VMs on OpenShift Virtualization
(KubeVirt) for benchmark-marked tests.

> TL;DR — **`vmops.initialize_workload()` must run before `WindowsVM()` is
> used.** That call is what renders `windows_dv.yaml`/`windows_vm.yaml` from
> benchmark-runner's Jinja2 templates into `run_artifacts_path`. Skip it and
> `WindowsVM.run()` has no YAML to `oc create -f` and fails.

## Requirements

- `benchmark-runner` installed (`pip install benchmark-runner`) in the same
  `.venv` as the rest of the suite. **Not currently pinned in
  `requirements.txt`** — add it there, or it only works because it happens to
  already be importable in your environment.
- `oc` on `PATH`, logged in to the target cluster (`OC` shells out to it).
- CNV (OpenShift Virtualization) already installed on the cluster —
  `initialize_workload()` checks this and raises `CNVNotInstalled` if not.
- Env vars: `KUBEADMIN_PASSWORD`, `WINDOWS_URL` always; `NAMESPACE`,
  `WORKER_NODE_0`, `WORKER_NODE_1`, `SCALE` additionally for the scale
  fixture (see below).

## How it's wired

Tests don't call benchmark-runner's classes directly — three fixtures in
`fixtures/benchmark_runner_fixtures.py` build everything from process env
vars and hand the test a ready-to-run object. `conftest.py` itself is just a
`pytest_plugins` list registering that module (and the other fixture
modules) — it defines no fixtures directly:

```
oc fixture (fixtures/benchmark_runner_fixtures.py)   # real OC client, session-scoped
        │
        ▼
windowsVM / windowsVMScale (fixtures/benchmark_runner_fixtures.py)
        │  1. TemporaryEnvironmentVariables(): scope env var writes to this fixture
        │  2. WorkloadsOperations().initialize_workload()  # renders the YAMLs
        │  3. WindowsVM()                                   # the object the test drives
        ▼
test calls windowsVM.run() / windowsVMScale.run()
```

- **`oc`** (`fixtures/benchmark_runner_fixtures.py:11-20`) — a real
  `benchmark_runner.common.oc.oc.OC` client, session-scoped.
  `SingletonOCLogin` caches the actual `oc login` process-wide, so
  constructing it more than once is cheap.
- **`windowsVM`** (`fixtures/benchmark_runner_fixtures.py:23-54`) — a single
  Windows VM, workload `windows_vm`.
- **`windowsVMScale`** (`fixtures/benchmark_runner_fixtures.py:59-93`) —
  `SCALE` VMs per node across `[WORKER_NODE_0, WORKER_NODE_1]`, workload
  `windows_vm_scale`. Note: `windows_vm_scale` isn't in benchmark-runner's
  own CLI-validated `workloads_list` (its `main.py` entry point would reject
  it) — that check only runs in the CLI path, not here, since the fixture
  instantiates `WindowsVM()` directly instead of going through
  benchmark-runner's own dispatcher.

Inside a test:

```python
@pytest.mark.benchmark
def test_benchmark_runner(self, windowsVMScale):
    assert windowsVMScale.run() is not False
```

## benchmark-runner primitives we use

| Call | Role |
| --- | --- |
| `OC(kubeadmin_password=...)` | Real cluster client; also used directly for fixture teardown |
| `TemporaryEnvironmentVariables()` | Scopes env var writes to the fixture; restores prior state on `__exit__` |
| `WorkloadsOperations().initialize_workload()` | CNV check, `delete_all()` (default `DELETE_ALL=True`), node cache clear, and — the part we actually need — `TemplateOperations.generate_yamls()`, which renders `windows_dv.yaml` + `windows_vm.yaml` into `run_artifacts_path` |
| `WindowsVM().run()` | Applies `windows_dv.yaml` (CDI import), waits for `Succeeded`, applies `windows_vm.yaml`, waits for VM readiness, uploads to ES if configured, deletes on `DELETE_ALL` |
| `oc.vm_exists(...)` / `oc.delete_vm_sync(...)` | Fixture-side best-effort cleanup, only relevant if `DELETE_ALL` was overridden to `False` |

## The one scenario (`tests/test_sample1.py`)

### `test_benchmark_runner` — scale VM provisioning + built-in workload run

```python
@pytest.mark.benchmark
def test_benchmark_runner(self, windowsVMScale):
    assert windowsVMScale.run() is not False
```

`windowsVMScale.run()` drives the entire benchmark-runner lifecycle for
`SCALE * 2` (two worker nodes) Windows VMs in one call: CDI import (once,
shared via the `windows-clone-dv` PVC), per-VM `VirtualMachine` creation
(each cloning that PVC), guest readiness wait, the workload's run step, then
teardown.

## Gotchas to know before touching these fixtures

1. **`DELETE_ALL` defaults to `True`.** `initialize_workload()` calls
   `self.delete_all()` before creating anything — every run of `windowsVM`/
   `windowsVMScale` deletes pre-existing benchmark-runner-managed resources
   in the target namespace first. Disruptive if something else in that
   namespace is mid-run.
2. **Namespace handling differs between the two fixtures.** `windowsVM`
   defaults to namespace `'benchmark-runner'` if unset; `windowsVMScale`
   does `os.environ["NAMESPACE"]` with no fallback and raises `KeyError` if
   you forget to set it.
3. **ES upload is disabled inconsistently.** `windowsVMScale` explicitly sets
   `env['elasticsearch'] = ''`; `windowsVM` does not, so it will attempt a
   real Elasticsearch upload if `ELASTICSEARCH` happens to be set in your
   shell when the test runs.
4. **Multiprocessing/SSL caveat (from benchmark-runner's own docs).**
   `windowsVMScale` spawns `multiprocessing.Process` per VM. Don't add a
   Python-level HTTPS call (a new fixture doing `requests`/an ES client, for
   example) ahead of `initialize_workload()`/`vm.run()` in the main pytest
   process for scale tests — mixing in-process OpenSSL state across a fork
   is a known SIGSEGV (`exitcode=-11`) risk. The current `oc` fixture is
   safe because `oc login` shells out to the `oc` binary rather than doing
   OpenSSL work in-process.
5. **Fixture teardown is a no-op in the common case.** With `DELETE_ALL=True`
   (the default), `WindowsVM.run()` already deletes everything itself before
   the fixture resumes after `yield` — the `oc.vm_exists(...)` check in
   teardown will correctly find nothing left to clean up.

## Running

```bash
# Requires benchmark-runner installed in .venv (see Requirements above)
export KUBEADMIN_PASSWORD=...
export WINDOWS_URL=http://.../windows2022.qcow2

# Scale path (the one test that currently exercises this):
export NAMESPACE=windows-bsod
export WORKER_NODE_0=worker-0
export WORKER_NODE_1=worker-1
export SCALE=2

.venv/bin/pytest -m benchmark -v
```

The single-VM `windowsVM` fixture isn't exercised by any current test — to
use it, request `windowsVM` instead of `windowsVMScale` in a test.

## File map

| File | Responsibility |
| --- | --- |
| `conftest.py` | `pytest_plugins` list wiring in the fixture modules below |
| `fixtures/benchmark_runner_fixtures.py` | `oc`, `windowsVM`, `windowsVMScale` fixtures |
| `tests/test_sample1.py` | `test_benchmark_runner` — the one benchmark-runner scenario |
| `pytest.ini` | `benchmark` marker declaration |

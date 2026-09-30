# Pytest Automation: Integrated Dependency Management

## Overview

The pytest automation system is now **fully integrated into pytest hooks**. No shell scripts needed!

**When you run `pytest`, it automatically:**
- ✅ PHASE 1: Pre-cleanup (removes old optional libraries)
- ✅ PHASE 2: Modular install (installs only needed dependencies based on test markers)
- ✅ PHASE 3: Run tests (pytest executes normally)
- ✅ PHASE 4: Post-cleanup (removes optional libs if tests pass)

## Quick Start

### Run tests with full automation
```bash
pytest tests/ -v
```

### Run tests AND cleanup optional dependencies after success
```bash
pytest tests/ -v --cleanup-krknlib --cleanup-reporting --cleanup-benchmark
```

### Run only specific tests
```bash
pytest tests/test_chaos.py -v --cleanup-krknlib
pytest tests/test_sample1.py::TestExample::test_vm_create -v
```

### Cleanup everything optional
```bash
pytest tests/ -v --cleanup-all
```

## How It Works

### PHASE 1: Pre-Cleanup (pytest_sessionstart hook)
Before tests run, old optional libraries are safely removed:
- `krkn-lib` (chaos testing) — 80MB
- `pytest-html` (reporting) — 30MB
- `allure-pytest` (reporting) — included
- `benchmark-runner` (performance) — 200MB
- `kubernetes`, `requests` (transitive deps)

**Safety:** If a package doesn't exist, it's silently skipped (self-healing).

### PHASE 2: Modular Install (pytest_collection_finish hook)
After tests are collected, only needed dependencies are installed:

**Always installed:**
- `base.txt` — pytest framework (~50MB)
- `vm.txt` — VM config (PyYAML) (~5MB)
- `reporting.txt` — reporting tools (~30MB)

**Conditional (based on test markers):**
- `krknlib.txt` — if tests use `@pytest.mark.krkn` (~80MB)
- `benchmark.txt` — if tests use `@pytest.mark.benchmark` (~200MB)

### PHASE 3: Run Tests
Pytest executes normally with all collected dependencies available.

### PHASE 4: Post-Cleanup (pytest_sessionfinish hook)
**Only if tests PASSED (exit code 0):**
- If `--cleanup-krknlib`: removes krkn-lib (~80MB freed)
- If `--cleanup-reporting`: removes reporting tools (~30MB freed)
- If `--cleanup-benchmark`: removes benchmark-runner (~200MB freed)
- If `--cleanup-all`: removes everything optional (~310MB freed)

**If tests FAILED:** All dependencies are kept for debugging.

## Command-Line Flags

| Flag | Effect |
|------|--------|
| `--cleanup-krknlib` | Remove krkn-lib after tests pass |
| `--cleanup-reporting` | Remove reporting tools after tests pass |
| `--cleanup-benchmark` | Remove benchmark-runner after tests pass |
| `--cleanup-all` | Remove all optional dependencies |
| (no flag) | Keep all dependencies (default) |

## Memory Savings

| Cleanup | Saves |
|---------|-------|
| Just krknlib | 80MB |
| Just reporting | 30MB |
| Just benchmark | 200MB |
| All optional | 310MB |

## Architecture

```
conftest.py
  ↓ (imports)
scripts/pytest_automation.py
  ├─ pytest_sessionstart()     ← PHASE 1: Pre-cleanup
  ├─ pytest_collection_finish()  ← PHASE 2: Modular install
  └─ pytest_sessionfinish()    ← PHASE 4: Post-cleanup
```

## Modular Requirements

```
requirements/
├── base.txt          ← Core pytest (always)
├── vm.txt            ← VM config (always)
├── krknlib.txt       ← Chaos testing (optional)
├── reporting.txt     ← HTML reports (optional)
└── benchmark.txt     ← Performance tools (optional)
```

Each file is independent and can be installed/removed separately.

## Examples

### Full chaos testing with cleanup
```bash
pytest tests/test_chaos.py -v --cleanup-krknlib --cleanup-reporting
```
- Installs: base + vm + krknlib + reporting
- Runs: test_chaos.py
- Cleans: krknlib (80MB) + reporting (30MB)
- Result: Only base + vm remain (~55MB)

### Quick VM test (no cleanup)
```bash
pytest tests/test_sample1.py::TestExample::test_vm_create -v
```
- Installs: base + vm
- Runs: test_vm_create
- Cleans: nothing
- Result: All deps remain (for next test)

### Full benchmark with max cleanup
```bash
pytest tests/ -k benchmark -v --cleanup-all
```
- Installs: base + vm + reporting + benchmark
- Runs: all benchmark tests
- Cleans: everything optional (krknlib + reporting + benchmark)
- Result: Only base + vm remain (~55MB)

## Troubleshooting

### Tests import a library that's not installed
**Cause:** The library isn't in any requirements/*.txt file for the detected markers.
**Fix:** Add the library to the appropriate requirements file and re-run.

### Want to keep dependencies for debugging
**Solution:** Don't use cleanup flags. Just run:
```bash
pytest tests/test_chaos.py -v
```
All deps stay installed.

### Manual cleanup later
**If you need to clean up later without running tests:**
```bash
# Using pip directly
pip uninstall -y krkn-lib pytest-html allure-pytest benchmark-runner

# Or run tests without --cleanup flags first
pytest tests/ -v  # Pre-cleanup runs, then no post-cleanup
```

## Migration Notes

**Before (with shell scripts):**
```bash
./scripts/run-tests-modular.sh krknlib --cleanup-krknlib
```

**Now (integrated with pytest):**
```bash
pytest tests/test_chaos.py -v --cleanup-krknlib
```

The automation is now **built into pytest** — cleaner, simpler, no external scripts needed.

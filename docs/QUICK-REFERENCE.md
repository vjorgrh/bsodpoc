# Quick Reference: Pytest Automation

## How It Works (1 minute version)

```
pytest tests/ -v
  ↓
PHASE 1: Delete old libs (pytest-html, allure, ...)
  ↓
PHASE 2: Scan test markers → Install needed libs from requirements/
  ├─ Always: base.txt + vm.txt + reporting.txt
  └─ If @pytest.mark.krkn: add krknlib.txt
  ├─ If @pytest.mark.benchmark: add benchmark.txt
  ↓
PHASE 3: Run tests
  ↓
PHASE 4: Cleanup if tests pass + flags provided
```

---

## Command Cheat Sheet

| Task | Command |
|------|---------|
| Run all tests | `pytest tests/ -v` |
| Run all tests + cleanup | `pytest tests/ -v --cleanup-all` |
| Run chaos tests | `pytest tests/test_chaos.py -v` |
| Run VM tests | `pytest tests/test_sample1.py -v` |
| Run specific test | `pytest tests/test_sample1.py::TestExample::test_vm_create -v` |
| Collect only (no run) | `pytest tests/ -v --collect-only` |

---

## Cleanup Flags

```bash
--cleanup-krknlib       # Remove krkn-lib (80MB freed)
--cleanup-reporting     # Remove pytest-html/allure (30MB freed)
--cleanup-benchmark     # Remove benchmark-runner (200MB freed)
--cleanup-all           # Remove all above (310MB freed)
```

---

## Library Installation Summary

| Requirement File | Libraries | Always? | Size |
|------------------|-----------|---------|------|
| base.txt | pytest, pluggy, packaging | YES | 50MB |
| vm.txt | PyYAML | YES | 5MB |
| krknlib.txt | krkn-lib | IF @krkn | 80MB |
| benchmark.txt | (empty) | IF @benchmark | 0MB |
| reporting.txt | pytest-html, allure | YES | 30MB |

---

## Test Marker Detection

The system scans all tests and looks for markers:
- `@pytest.mark.krkn` → Install krknlib.txt
- `@pytest.mark.benchmark` → Install benchmark.txt
- `@pytest.mark.bsod`, `@pytest.mark.tunnel`, etc. → No special action needed

---

## How to Use for Different Scenarios

### Quick Test Run (No Cleanup)
```bash
pytest tests/test_sample1.py -v
```
Installs: 85MB (base + vm + reporting)
Keeps: All deps

### Production Run (Max Cleanup)
```bash
pytest tests/ -v --cleanup-all
```
Installs: 165MB (all)
Keeps: 55MB (base + vm only)
Freed: 110MB

### Debugging (Keep Everything)
```bash
pytest tests/test_chaos.py -v
```
Installs: 165MB
Keeps: 165MB
Keeps all deps for inspection

### Selective Cleanup
```bash
pytest tests/ -v --cleanup-krknlib
```
Installs: 165MB
Keeps: 85MB (base + vm + reporting)
Freed: 80MB

---

## What Actually Gets Installed

### Always Present
- pytest (framework)
- PyYAML (VM config)
- pytest-html, allure-pytest (reporting)

### Conditionally (if markers detected)
- krkn-lib (chaos testing)
- benchmark-runner (performance testing)

### Memory Usage
- Minimal: 55MB (base + vm)
- Full: 165MB (all optional included)
- Typical: 85-165MB depending on tests

---

## Troubleshooting

**Q: Library not found error**
A: Marker for that library not detected. Check if test has proper marker annotation.

**Q: Want to keep deps for debugging**
A: Just run without `--cleanup-*` flags.

**Q: Want to cleanup manually later**
A: Run: `pip uninstall -y krkn-lib pytest-html allure-pytest`

**Q: Tests failed, deps still here**
A: By design! Failed tests keep deps for debugging.

---

## Files Involved

```
conftest.py
  └─ Imports hooks from:

scripts/pytest_automation.py
  ├─ pytest_sessionstart()      [PHASE 1: Pre-cleanup]
  ├─ pytest_collection_finish() [PHASE 2: Modular install]
  └─ pytest_sessionfinish()     [PHASE 4: Post-cleanup]

requirements/
  ├─ base.txt
  ├─ vm.txt
  ├─ krknlib.txt
  ├─ benchmark.txt
  └─ reporting.txt
```

---

## Memory Savings Examples

### Before: Single requirements.txt
```
All deps always installed = 165MB footprint
```

### After: Modular + Cleanup
```
Baseline (base + vm): 55MB
+ krknlib: +80MB → 135MB
+ reporting: included in "always"
Then cleanup krknlib: -80MB → 55MB ✅
```

**Savings: 110MB+ with cleanup enabled**

---

## Documentation

- **PYTEST-AUTOMATION.md** - Full usage guide
- **DRY-RUN-ANALYSIS.md** - Detailed breakdown of what happens
- **INSTALLATION-FLOW-DIAGRAM.md** - Visual flow diagrams
- **COMPLETE-PYTEST-AUTOMATION-GUIDE.md** - Comprehensive reference
- **QUICK-REFERENCE.md** - This file (cheat sheet)

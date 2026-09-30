# Initial Setup Guide

## Before vs After

### Old Way (Single requirements.txt)
```bash
git clone <repo>
cd bsodpoc
python3.11 -m venv .venv
pip install -r requirements.txt      ← Single monolithic file
pytest tests/ -v                     ← All deps already installed
```

### New Way (Modular + Automated)
```bash
git clone <repo>
cd bsodpoc
python3.11 -m venv .venv
# Now either:
# Option A: pytest auto-installs (lazy loading)
pytest tests/ -v                     ← PHASE 2 installs libs automatically
# OR
# Option B: Pre-install all upfront
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
pytest tests/ -v                     ← Libs already there
```

---

## Initial Setup Options

### Option A: Lazy Loading (Recommended for development)
**When to use:** Daily development, quick testing

```bash
# 1. Create venv
python3.11 -m venv .venv

# 2. Run pytest (PHASE 2 auto-installs)
pytest tests/ -v
```

**What happens:**
- ✅ PHASE 1: Pre-cleanup (nothing to clean yet)
- ✅ PHASE 2: Detects markers, installs requirements/base.txt, requirements/vm.txt, etc.
- ✅ PHASE 3: Tests run
- ✅ PHASE 4: (no cleanup flags) keeps all deps

**Advantages:**
- Minimal initial setup
- Only installs what's needed for your tests
- Works immediately: just run `pytest tests/ -v`

**Disadvantages:**
- First run takes a bit longer (installs deps)

---

### Option B: Pre-install Everything (Recommended for CI/CD)
**When to use:** CI/CD pipelines, production, or you want all deps ready

```bash
# 1. Create venv
python3.11 -m venv .venv

# 2. Install all requirements upfront
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
pip install -r requirements/benchmark.txt

# 3. Run pytest (will skip install since all deps present)
pytest tests/ -v
```

**What happens:**
- 🔧 Pre-install all 165MB (5 files)
- ✅ PHASE 1: Pre-cleanup (removes old)
- ⚡ PHASE 2: Skips install (all deps already there!)
- ✅ PHASE 3: Tests run
- ✅ PHASE 4: (no cleanup flags) keeps all deps

**Advantages:**
- All deps ready upfront
- Faster pytest startup (no install in PHASE 2)
- Mirrors old behavior (`pip install requirements.txt`)

**Disadvantages:**
- Takes time upfront (165MB)
- Installs optional deps even if not needed

---

### Option C: Pre-install Only Essentials
**When to use:** When you know you only need base + vm (no chaos)

```bash
# 1. Create venv
python3.11 -m venv .venv

# 2. Install only base requirements
pip install -r requirements/base.txt
pip install -r requirements/vm.txt

# 3. Run specific tests
pytest tests/test_sample1.py -v
```

**What happens:**
- 🔧 Pre-install 55MB (just essentials)
- ✅ PHASE 1: Pre-cleanup
- ⚡ PHASE 2: Skips base+vm install, only installs reporting.txt
- ✅ PHASE 3: Tests run
- ✅ PHASE 4: (no cleanup) keeps all

**Advantages:**
- Minimal footprint initially (55MB)
- Fast pytest startup

**Disadvantages:**
- Can't run chaos tests (no krkn-lib)
- Need to install manually if tests change

---

## Command Comparison

| Scenario | Command | Time | Deps | Notes |
|----------|---------|------|------|-------|
| **Lazy (dev)** | `pytest tests/ -v` | Slower 1st run | Auto | Minimal setup |
| **Pre-install all (CI)** | `pip install -r req...` + `pytest` | Faster runs | 165MB | Mirrors old way |
| **Pre-install essentials** | `pip install base vm` + `pytest test_sample1.py` | Medium | 55MB | Limited |

---

## Step-by-Step: Fresh Start to Running Tests

### Path A: Lazy Loading (Fast Setup)
```bash
# Step 1: Clone and create venv
git clone <repo>
cd bsodpoc
python3.11 -m venv .venv

# Step 2: Run pytest (everything else automatic)
.venv/bin/pytest tests/ -v

# Behind the scenes:
# ├─ PHASE 1: Pre-cleanup
# ├─ PHASE 2: Installs base + vm + krknlib + reporting (165MB)
# ├─ PHASE 3: Runs 6 tests
# └─ PHASE 4: No cleanup (keeps all)
```

**Timeline:**
- Venv creation: ~10 sec
- First pytest run: ~2 min (includes 165MB install)
- Subsequent runs: ~30 sec (no install)

---

### Path B: Pre-install All (CI/CD)
```bash
# Step 1: Clone and create venv
git clone <repo>
cd bsodpoc
python3.11 -m venv .venv

# Step 2: Install all requirements upfront
.venv/bin/pip install -r requirements/base.txt
.venv/bin/pip install -r requirements/vm.txt
.venv/bin/pip install -r requirements/krknlib.txt
.venv/bin/pip install -r requirements/reporting.txt
.venv/bin/pip install -r requirements/benchmark.txt

# Step 3: Run pytest (skips install in PHASE 2)
.venv/bin/pytest tests/ -v

# Behind the scenes:
# ├─ PHASE 1: Pre-cleanup
# ├─ PHASE 2: Skips install (all deps ready) ⚡
# ├─ PHASE 3: Runs 6 tests
# └─ PHASE 4: No cleanup (keeps all)
```

**Timeline:**
- Venv creation: ~10 sec
- Installing all deps: ~2 min (includes 165MB)
- Each pytest run: ~30 sec (no install)

---

## How to Check What's Installed

After initial setup, check what's in venv:

```bash
# Show all installed packages
.venv/bin/pip list

# Show specific packages
.venv/bin/pip list | grep -E "pytest|krkn|allure|yaml"

# Check venv size
du -sh .venv

# Expected: ~165MB if all installed, ~55MB if base+vm only
```

---

## Initial Setup for Different Team Members

### For Developers (Quick local testing)
```bash
python3.11 -m venv .venv
pytest tests/ -v                    ← Just run, PHASE 2 installs
```

### For CI/CD Pipeline
```bash
python3.11 -m venv .venv
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
pytest tests/ -v
```

### For Documentation/Static Analysis Tools
```bash
python3.11 -m venv .venv
pip install -r requirements/base.txt
pytest tests/ --collect-only        ← Just collect, don't run
```

---

## What If You Need Fresh Install Later?

### Clean and reinstall everything

```bash
# Option 1: Full cleanup and reinstall
rm -rf .venv
python3.11 -m venv .venv
pytest tests/ -v                    ← Auto-installs via PHASE 2

# Option 2: Keep venv, reinstall libs
.venv/bin/pip uninstall -y \
  pytest krkn-lib pytest-html allure-pytest \
  allure-python-commons benchmark-runner
.venv/bin/pip install -r requirements/base.txt
.venv/bin/pip install -r requirements/vm.txt
pytest tests/ -v
```

---

## Troubleshooting Initial Setup

### Q: "Module not found" on first pytest run
**A:** PHASE 2 should have installed it. Check:
```bash
.venv/bin/pip list | grep <package>
```
If missing, manually install:
```bash
pip install -r requirements/krknlib.txt
```

### Q: Takes too long on first run
**A:** First run includes library installation (2 min normal). Subsequent runs are 30sec.

### Q: Want to skip auto-install and pre-install instead
**A:** Run pip install for all requirements/*.txt before pytest:
```bash
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
pytest tests/ -v
```

### Q: How do I migrate from old requirements.txt?
**A:** The old `requirements.txt` is deleted. Use modular approach:
```bash
# Old way (no longer works):
# pip install -r requirements.txt

# New way:
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
```

---

## Summary Table

| Method | Setup Time | Pytest Time | Space | Best For |
|--------|-----------|-------------|-------|----------|
| **Lazy** | 10 sec | 2 min (1st), 30 sec (rest) | Auto | Developers |
| **Pre-install** | 2 min | 30 sec | 165MB | CI/CD |
| **Essentials** | 30 sec | 1 min | 55MB | Limited testing |

---

## Recommended Setup for Your Workflow

### Development Machine (Lazy)
```bash
python3.11 -m venv .venv
pytest tests/ -v
# Just run it, PHASE 2 handles installation
```

### CI/CD Pipeline (Pre-install)
```bash
python3.11 -m venv .venv
pip install -r requirements/base.txt
pip install -r requirements/vm.txt
pip install -r requirements/krknlib.txt
pip install -r requirements/reporting.txt
pytest tests/ -v --cleanup-all
# Everything ready, auto-cleanup saves memory
```

### Docker Container
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN python3.11 -m venv .venv
RUN .venv/bin/pip install -r requirements/base.txt
RUN .venv/bin/pip install -r requirements/vm.txt
RUN .venv/bin/pip install -r requirements/krknlib.txt
RUN .venv/bin/pip install -r requirements/reporting.txt
CMD [".venv/bin/pytest", "tests/", "-v", "--cleanup-all"]
```

---

## Key Differences from Old Way

| Aspect | Old Way | New Way |
|--------|---------|---------|
| **File** | requirements.txt | requirements/ (5 files) |
| **Installation** | Manual: `pip install -r req.txt` | Auto: `pytest` (PHASE 2) OR manual pip |
| **All deps always?** | YES (165MB) | NO (only needed) |
| **Cleanup** | Manual or nothing | Auto with `--cleanup-*` flags |
| **Markers** | None | Drives conditional installation |
| **Shell scripts** | run-tests-modular.sh | Integrated in pytest hooks |

---

## Quick Start Decision Tree

```
Starting fresh?
  ├─ YES
  │  ├─ Just want to run tests?
  │  │  └─ Run: pytest tests/ -v
  │  │     (PHASE 2 auto-installs)
  │  │
  │  └─ Setting up CI/CD?
  │     ├─ pip install -r requirements/base.txt
  │     ├─ pip install -r requirements/vm.txt
  │     ├─ pip install -r requirements/krknlib.txt
  │     ├─ pip install -r requirements/reporting.txt
  │     └─ pytest tests/ -v --cleanup-all
  │
  └─ Already have venv?
     └─ Run: pytest tests/ -v
        (PHASE 1 cleans, PHASE 2 checks/installs as needed)
```

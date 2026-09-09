================================================================================
MODULAR REQUIREMENTS STRUCTURE
================================================================================

FOLDER: requirements/
PURPOSE: Segregated dependency management by fixture and test type

FILES:
------
base.txt              - Core pytest framework (ALWAYS KEEP)
vm.txt                - VM creation/configuration (ALWAYS KEEP)
krknlib.txt           - krkn-lib chaos scenarios (OPTIONAL - cleanup after tests)
reporting.txt         - HTML reports & allure (OPTIONAL - cleanup after tests)
benchmark.txt         - Performance benchmarking (OPTIONAL - cleanup after tests)

INSTALLATION:
-------------

# Full install (all features)
pip install -r requirements/base.txt requirements/vm.txt requirements/krknlib.txt requirements/reporting.txt

# Minimal (VM tests only)
pip install -r requirements/base.txt requirements/vm.txt

# Chaos tests only
pip install -r requirements/base.txt requirements/vm.txt requirements/krknlib.txt

USAGE WITH SCRIPTS:
-------------------

# Run krkn-lib tests, cleanup krknlib after success
./scripts/run-tests-modular.sh krknlib --cleanup-krknlib

# Run VM tests, minimal setup, no cleanup
./scripts/run-tests-modular.sh vm

# Run all tests, cleanup everything optional
./scripts/run-tests-modular.sh all --cleanup-krknlib --cleanup-reporting

# Manual cleanup anytime
./scripts/cleanup-libs.sh --krknlib --reporting

CLEANUP FLAGS:
--------------
--cleanup-krknlib      Remove krkn-lib (~80MB)
--cleanup-reporting    Remove reporting tools (~30MB)
--cleanup-benchmark    Remove benchmark-runner (~200MB)
--all                  Remove all optional dependencies

MEMORY SAVINGS:
---------------
krknlib:       80MB
reporting:     30MB
benchmark:    200MB

DEFAULT BEHAVIOR:
-----------------
✅ Base framework stays installed (always needed)
✅ VM config stays installed (always needed)
⚠️  Optional deps only removed if test passes AND flag provided
⚠️  Failed tests keep all deps for debugging

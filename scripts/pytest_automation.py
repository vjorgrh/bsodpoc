"""
pytest_automation.py
Automated dependency management for pytest
- PHASE 1: Pre-cleanup (remove old optional libs)
- PHASE 2: Modular install (install only needed libs based on markers)
- PHASE 3: Run tests (pytest executes)
- PHASE 4: Post-cleanup (cleanup if tests pass)

Usage: Import this in conftest.py
"""

import subprocess
import sys
import os
import json
from pathlib import Path

# Colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

PROJECT_ROOT = Path(__file__).parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PIP = str(VENV_DIR / "bin" / "pip")


def log_section(msg: str) -> None:
    print(f"{BLUE}╔════════════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║{NC} {GREEN}{msg}{NC}")
    print(f"{BLUE}╚════════════════════════════════════════════════════════════════╝{NC}")


def log_info(msg: str) -> None:
    print(f"{GREEN}✅{NC} {msg}")


def log_warn(msg: str) -> None:
    print(f"{YELLOW}⚠️{NC}  {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}❌{NC} {msg}")


def log_success(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{NC}")


def safe_pip_uninstall(package: str) -> bool:
    """Safely uninstall a package (no error if missing)."""
    try:
        result = subprocess.run(
            [VENV_PIP, "show", package],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            log_info(f"Uninstalling {package}...")
            subprocess.run(
                [VENV_PIP, "uninstall", "-y", package],
                capture_output=True,
                timeout=60
            )
            return True
        else:
            log_warn(f"{package} not installed (skip)")
            return False
    except Exception as e:
        log_warn(f"Could not uninstall {package}: {e}")
        return False


def safe_pip_install(req_file: str) -> bool:
    """Safely install from requirements file."""
    try:
        if not os.path.exists(req_file):
            log_error(f"Requirement file not found: {req_file}")
            return False
        log_info(f"Installing from {req_file}...")
        result = subprocess.run(
            [VENV_PIP, "install", "-q", "-r", req_file],
            capture_output=True,
            timeout=120
        )
        if result.returncode != 0:
            log_error(f"Failed to install from {req_file}")
            return False
        return True
    except Exception as e:
        log_error(f"Error installing {req_file}: {e}")
        return False


def detect_test_markers(session) -> set:
    """Scan collected test items to detect which markers are used."""
    markers = set()
    try:
        for item in session.items:
            for marker in item.iter_markers():
                markers.add(marker.name)
    except Exception:
        pass
    return markers


def get_installed_packages() -> list:
    """Get list of all installed packages using pip list --format=json"""
    try:
        result = subprocess.run(
            [VENV_PIP, "list", "--format=json"],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return [pkg['name'].lower() for pkg in packages]
    except Exception:
        pass
    return []


def get_packages_to_remove() -> list:
    """Get list of ALL packages to remove except base framework and system packages"""
    installed = get_installed_packages()

    # Packages to KEEP (base framework + system packages + all dependencies)
    keep_packages = {
        # Base test framework
        "pytest",
        "pytest-metadata",
        "pluggy",
        "packaging",
        "iniconfig",
        "pyyaml",
        # Direct dependencies of pytest
        "pygments",
        # System packages to always keep
        "pip",
        "setuptools",
        "wheel",
        # Add any other critical transitive dependencies here
        "typing-extensions",
        "attrs",
    }

    packages_to_remove = []

    # For loop: iterate through installed packages
    # Remove EVERYTHING except base framework and system packages
    for pkg_name in installed:
        if pkg_name not in keep_packages:
            packages_to_remove.append(pkg_name)

    return packages_to_remove


def pytest_addoption(parser) -> None:
    """Register custom command-line options for pytest."""
    parser.addoption(
        "--namespace",
        action="store",
        default=None,
        help="Kubernetes namespace (overrides NAMESPACE env var, default: windows-bsod)",
    )
    parser.addoption(
        "--target-name",
        action="store",
        default=None,
        help="Target resource name: VM, benchmark runner, pod, etc (overrides TARGET_NAME env var)",
    )
    parser.addoption(
        "--target-type",
        action="store",
        default=None,
        help="Target type for documentation: vm, benchmark, pod, etc (overrides TARGET_TYPE env var)",
    )
    parser.addoption(
        "--cleanup-krknlib",
        action="store_true",
        default=False,
        help="Clean up krkn-lib dependencies after test execution (frees ~80MB)",
    )
    parser.addoption(
        "--cleanup-reporting",
        action="store_true",
        default=False,
        help="Clean up reporting tools after test execution (frees ~30MB)",
    )
    parser.addoption(
        "--cleanup-benchmark",
        action="store_true",
        default=False,
        help="Clean up benchmark-runner after test execution (frees ~200MB)",
    )
    parser.addoption(
        "--cleanup-all",
        action="store_true",
        default=False,
        help="Clean up all optional dependencies after test execution (frees ~310MB)",
    )


def pytest_configure(config) -> None:
    """
    EARLY HOOK: Apply CLI options to environment variables before test collection.
    This ensures namespace and target from CLI override environment variables.
    """
    namespace = config.getoption("--namespace")
    target_name = config.getoption("--target-name")
    target_type = config.getoption("--target-type")

    if namespace:
        os.environ["NAMESPACE"] = namespace
        log_info(f"Using namespace from CLI: {namespace}")

    if target_name:
        os.environ["TARGET_NAME"] = target_name
        log_info(f"Using target from CLI: {target_name}")

    if target_type:
        os.environ["TARGET_TYPE"] = target_type
        log_info(f"Using target type from CLI: {target_type}")


def install_all_requirements() -> bool:
    """
    Install all requirements from requirements/ folder using a for loop.
    Equivalent to: for req in base vm krknlib reporting benchmark; do pip install -r "requirements/$req.txt"; done
    """
    req_dir = PROJECT_ROOT / "requirements"
    requirements = ["base", "vm", "krknlib", "reporting", "benchmark"]

    installed_count = 0
    skipped_count = 0
    failed_count = 0

    log_section("INSTALL ALL REQUIREMENTS (For Loop)")
    log_info(f"Installing from: {req_dir}")

    # For loop: iterate through all requirement files
    for req_name in requirements:
        req_file = str(req_dir / f"{req_name}.txt")

        if not os.path.exists(req_file):
            log_warn(f"{req_name}.txt not found (skip)")
            skipped_count += 1
            continue

        # Check if file has content (not empty/commented)
        try:
            with open(req_file, 'r') as f:
                content = f.read().strip()
                if not content or all(line.startswith('#') or not line.strip() for line in content.split('\n')):
                    log_warn(f"{req_name}.txt is empty/commented (skip)")
                    skipped_count += 1
                    continue
        except Exception as e:
            log_warn(f"Could not read {req_name}.txt: {e}")
            skipped_count += 1
            continue

        # Install this requirement
        if safe_pip_install(req_file):
            log_success(f"{req_name}.txt installed")
            installed_count += 1
        else:
            log_error(f"Failed to install {req_name}.txt")
            failed_count += 1

    print()
    log_section("INSTALLATION SUMMARY")
    log_info(f"Installed: {installed_count}")
    if skipped_count > 0:
        log_warn(f"Skipped: {skipped_count}")
    if failed_count > 0:
        log_error(f"Failed: {failed_count}")
        return False

    log_success("All requirements installed successfully!")
    return True


def pytest_sessionstart(session) -> None:
    """
    PHASE 1 & 2: Pre-cleanup + modular install
    Runs BEFORE test collection and execution.
    """
    log_section("PHASE 1: PRE-CLEANUP (Remove Old Libraries)")

    if not VENV_DIR.exists():
        log_error(f"Virtual environment not found at {VENV_DIR}")
        sys.exit(1)

    log_info(f"Python venv: {VENV_DIR}")
    log_info("Cleaning up optional libraries from previous runs...")

    safe_pip_uninstall("krkn-lib")
    safe_pip_uninstall("pytest-html")
    safe_pip_uninstall("allure-pytest")
    safe_pip_uninstall("allure-python-commons")
    safe_pip_uninstall("benchmark-runner")
    safe_pip_uninstall("kubernetes")
    safe_pip_uninstall("requests")

    log_success("Pre-cleanup complete")


def pytest_collection_finish(session) -> None:
    """
    PHASE 2: Modular install (after test collection, before execution)
    Detects which markers are in collected tests and installs only needed libs.
    """
    log_section("PHASE 2: MODULAR INSTALL (Install Required Dependencies)")

    markers = detect_test_markers(session)
    log_info(f"Detected test markers: {markers if markers else 'none'}")

    req_dir = PROJECT_ROOT / "requirements"

    log_info("Installing base requirements (always needed)...")
    safe_pip_install(str(req_dir / "base.txt"))
    safe_pip_install(str(req_dir / "vm.txt"))

    if "krkn" in markers or any("chaos" in item.name for item in session.items):
        log_info("Installing krknlib (krkn-lib chaos tests detected)...")
        safe_pip_install(str(req_dir / "krknlib.txt"))

    if "benchmark" in markers:
        log_info("Installing benchmark runner...")
        safe_pip_install(str(req_dir / "benchmark.txt"))

    log_info("Installing reporting tools...")
    safe_pip_install(str(req_dir / "reporting.txt"))

    log_success("✅ Modular installation complete")


def pytest_sessionfinish(session, exitstatus: int) -> None:
    """
    PHASE 4: Auto-cleanup on success
    If tests passed (exitstatus == 0), cleanup optional libs based on flags.
    If tests failed, keep deps for debugging.
    """
    log_section("PHASE 4: POST-CLEANUP (Optional Dependency Cleanup)")

    if exitstatus == 0:
        log_success("Tests PASSED (exit code 0) - Running post-cleanup")

        # Get cleanup flags from pytest config
        cleanup_all = session.config.getoption("--cleanup-all")
        cleanup_krknlib = session.config.getoption("--cleanup-krknlib") or cleanup_all
        cleanup_reporting = session.config.getoption("--cleanup-reporting") or cleanup_all
        cleanup_benchmark = session.config.getoption("--cleanup-benchmark") or cleanup_all

        cleanup_performed = False

        # With --cleanup-all, remove ALL optional packages
        if cleanup_all:
            log_info("Cleaning up ALL optional dependencies...")

            # Get packages to remove dynamically from pip list
            packages_to_remove = get_packages_to_remove()

            if packages_to_remove:
                try:
                    log_info(f"Removing {len(packages_to_remove)} packages...")

                    # Use batch uninstall for efficiency
                    result = subprocess.run(
                        [VENV_PIP, "uninstall", "-y"] + packages_to_remove,
                        capture_output=True,
                        timeout=120
                    )

                    if result.returncode == 0:
                        log_success("All optional packages removed (~310MB freed)")
                        cleanup_performed = True
                    else:
                        # Fallback: uninstall individually with for loop
                        log_warn("Batch uninstall failed, trying individual removal...")
                        for package in packages_to_remove:
                            log_info(f"Removing: {package}")
                            safe_pip_uninstall(package)
                        log_success("Optional packages cleanup completed")
                        cleanup_performed = True

                except Exception as e:
                    log_error(f"Error during cleanup: {e}")
                    # Fallback: loop through and uninstall individually
                    for package in packages_to_remove:
                        safe_pip_uninstall(package)
                    cleanup_performed = True
        else:
            # Selective cleanup based on individual flags
            installed = get_installed_packages()

            if cleanup_krknlib:
                log_info("Cleaning up krkn-lib and dependencies...")
                krknlib_packages = [pkg for pkg in installed if any(kw in pkg for kw in ["krkn", "kubernetes", "requests"])]
                for pkg in krknlib_packages:
                    log_info(f"Removing: {pkg}")
                    safe_pip_uninstall(pkg)
                log_success("krkn-lib removed (~80MB freed)")
                cleanup_performed = True

            if cleanup_reporting:
                log_info("Cleaning up reporting tools...")
                reporting_packages = [pkg for pkg in installed if any(kw in pkg for kw in ["allure", "pytest-html", "jinja", "markupsafe"])]
                for pkg in reporting_packages:
                    log_info(f"Removing: {pkg}")
                    safe_pip_uninstall(pkg)
                log_success("Reporting tools removed (~30MB freed)")
                cleanup_performed = True

            if cleanup_benchmark:
                log_info("Cleaning up benchmark-runner...")
                benchmark_packages = [pkg for pkg in installed if "benchmark" in pkg]
                for pkg in benchmark_packages:
                    log_info(f"Removing: {pkg}")
                    safe_pip_uninstall(pkg)
                log_success("benchmark-runner removed (~200MB freed)")
                cleanup_performed = True

        if not cleanup_performed:
            log_warn("No cleanup flags provided - keeping all optional dependencies")
            log_info("To cleanup, re-run with: pytest tests/ -v --cleanup-krknlib --cleanup-reporting --cleanup-benchmark")
            log_info("Or cleanup everything: pytest tests/ -v --cleanup-all")
    else:
        log_error(f"Tests FAILED (exit code {exitstatus})")
        log_warn("Keeping all dependencies for debugging")

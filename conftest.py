import sys
from pathlib import Path

pytest_plugins = [
    "fixtures.vm_fixtures",
    "fixtures.krknlib_fixtures",
    "fixtures.tunnel_fixtures",
    "fixtures.vut_fixtures",
    "fixtures.benchmark_runner_fixtures",
]

# Register pytest automation hooks (dependency management)
from scripts.pytest_automation import (
    pytest_addoption,
    pytest_configure,
    pytest_sessionstart,
    pytest_collection_finish,
    pytest_sessionfinish,
)

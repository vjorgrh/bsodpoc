# Project Guidelines

## Code Style & Architecture
- Target Python 3.11 (the `.venv` interpreter; krkn-lib 5.0.0 does not support newer versions). Use type hints for all function signatures.
- Follow PEP 8 guidelines strictly
- Prefer explicit imports over wildcard imports.

## Testing Guidelines (Pytest)
- Place all tests in the 'tests/' directory matching the source layout
- Use descriptive test name starting with 'test_' (e.g. 'test_vm_create')
- Prefer pytest fixtures over setup/teardown methods
- Put shared fixtures inside conftest.py

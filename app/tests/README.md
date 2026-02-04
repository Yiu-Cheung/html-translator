# Automated Tests for HTML Translation Tool

This directory contains automated tests for the HTML Translation Tool.

## Test Suite

### test_project_settings.py
Comprehensive tests for per-project settings functionality covering:

- **Test 10.1**: Fresh installation - project creation with settings.json
- **Test 10.2**: Migration - loading legacy projects without settings.json
- **Test 10.3**: Project switching - settings isolation between projects
- **Test 10.4**: Settings modification - verifying changes only affect current project
- **Test 10.5**: Project creation from template - settings copying
- **Test 10.6**: Malformed settings.json - error handling and fallback
- **Test 10.7**: Global config persistence - UI settings separate from project settings

## Running Tests

### Run all tests:
```bash
python -m pytest
```

### Run specific test file:
```bash
python -m pytest app/tests/test_project_settings.py
```

### Run with verbose output:
```bash
python -m pytest -v
```

### Run specific test class:
```bash
python -m pytest app/tests/test_project_settings.py::TestFreshInstallation
```

### Run specific test:
```bash
python -m pytest app/tests/test_project_settings.py::TestFreshInstallation::test_create_new_project_creates_settings_json
```

## Test Coverage

All tests use temporary directories for isolation and are cleaned up automatically.

Test classes:
- `TestFreshInstallation`: 2 tests
- `TestMigration`: 2 tests
- `TestProjectSwitching`: 3 tests (includes model switching optimization test)
- `TestSettingsModification`: 1 test
- `TestProjectCreationFromTemplate`: 2 tests
- `TestMalformedSettings`: 2 tests
- `TestGlobalConfigPersistence`: 2 tests

**Total: 14 tests**

## Requirements

- pytest >= 7.0.0

Install with:
```bash
pip install pytest
```

## Adding New Tests

1. Create test file with `test_*.py` naming convention
2. Use pytest fixtures for setup/teardown
3. Follow existing test patterns for consistency
4. Run tests to verify they pass
5. Update this README if adding new test categories

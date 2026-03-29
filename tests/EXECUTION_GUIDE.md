# Test Execution Guide

Complete guide for running and managing the watch party test suite.

## Setup

### 1. Install Dependencies

```bash
# From project root
pip install -r tests/requirements.txt

# Or manually
pip install pytest pytest-cov pytest-mock
```

### 2. Verify Setup

```bash
pytest --version
python -c "import watch_party_config; print('Config loaded')"
```

## Basic Execution

### Run All Tests

```bash
pytest tests/
```

**Output:**
```
tests/test_permissions.py::TestRoleLevels::test_role_levels_exist PASSED
tests/test_permissions.py::TestRoleLevels::test_role_levels_values PASSED
...
======================== 205 passed in 4.23s ========================
```

### Run Single Test File

```bash
pytest tests/test_permissions.py
```

### Run Single Test Class

```bash
pytest tests/test_permissions.py::TestRoleLevels
```

### Run Single Test

```bash
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist
```

## Verbose Output

### Show Test Names and Results

```bash
pytest tests/ -v
```

**Output:**
```
tests/test_permissions.py::TestRoleLevels::test_role_levels_exist PASSED [ 0%]
tests/test_permissions.py::TestRoleLevels::test_role_levels_values PASSED [ 1%]
tests/test_permissions.py::TestRoleLevels::test_role_levels_ordered PASSED [ 2%]
...
```

### Show Print Statements

```bash
pytest tests/ -v -s
```

### Show Local Variables on Failure

```bash
pytest tests/ -v -l
```

## Coverage Reports

### Generate Coverage Report

```bash
pytest tests/ --cov=. --cov-report=term
```

**Output:**
```
Name                          Stmts   Miss  Cover
-------------------------------------------------
watch_party_config.py            50      2    96%
web_dashboard_enhanced.py       200     15    92%
...
-------------------------------------------------
TOTAL                           500     25    95%
```

### Generate HTML Coverage Report

```bash
pytest tests/ --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in browser.

### Generate XML Coverage Report

```bash
pytest tests/ --cov=. --cov-report=xml
```

## Filtering Tests

### Run Tests by Name Pattern

```bash
# Run all permission tests
pytest tests/ -k "permission"

# Run all chat tests
pytest tests/ -k "chat"

# Run all sync tests
pytest tests/ -k "sync"
```

### Run Tests by Marker

```bash
# Run unit tests only
pytest tests/ -m unit

# Run integration tests only
pytest tests/ -m integration

# Run API tests only
pytest tests/ -m api
```

### Run Tests Excluding Pattern

```bash
# Skip slow tests
pytest tests/ -m "not slow"

# Skip tests requiring bot
pytest tests/ -m "not requires_bot"
```

## Output Formats

### Short Traceback

```bash
pytest tests/ --tb=short
```

### Long Traceback

```bash
pytest tests/ --tb=long
```

### No Traceback

```bash
pytest tests/ --tb=no
```

### Line Traceback

```bash
pytest tests/ --tb=line
```

## Parallel Execution

### Run Tests in Parallel

```bash
# Install pytest-xdist first
pip install pytest-xdist

# Run with auto-detected CPU count
pytest tests/ -n auto

# Run with specific number of workers
pytest tests/ -n 4
```

## Stopping on Failure

### Stop After First Failure

```bash
pytest tests/ -x
```

### Stop After N Failures

```bash
pytest tests/ --maxfail=3
```

## Test Selection

### Run Last Failed Tests

```bash
pytest tests/ --lf
```

### Run Failed Tests First

```bash
pytest tests/ --ff
```

### Run Tests Modified Since Last Run

```bash
pytest tests/ --changed-since=HEAD
```

## Debugging

### Drop into Debugger on Failure

```bash
pytest tests/ --pdb
```

### Drop into Debugger on Error

```bash
pytest tests/ --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Show Local Variables on Failure

```bash
pytest tests/ -l
```

### Capture Output

```bash
# Show captured output
pytest tests/ -s

# Don't capture output
pytest tests/ --capture=no
```

## Reporting

### Generate JUnit XML Report

```bash
pytest tests/ --junit-xml=report.xml
```

### Generate HTML Report

```bash
pip install pytest-html
pytest tests/ --html=report.html --self-contained-html
```

### Generate JSON Report

```bash
pip install pytest-json-report
pytest tests/ --json-report --json-report-file=report.json
```

## Performance Testing

### Show Slowest Tests

```bash
pytest tests/ --durations=10
```

### Benchmark Tests

```bash
pip install pytest-benchmark
pytest tests/ --benchmark-only
```

## Continuous Integration

### Run Tests with CI Output

```bash
pytest tests/ --tb=short -v --junit-xml=test-results.xml
```

### Run Tests with Coverage for CI

```bash
pytest tests/ \
  --cov=. \
  --cov-report=xml \
  --cov-report=term \
  --junit-xml=test-results.xml \
  -v
```

## Test Organization

### Run Tests by Category

```bash
# Permissions tests
pytest tests/test_permissions.py -v

# Socket.IO tests
pytest tests/test_socketio_events.py -v

# API tests
pytest tests/test_api_endpoints.py -v

# Storage tests
pytest tests/test_storage_streaming.py -v

# Chat tests
pytest tests/test_chat.py -v

# Sync tests
pytest tests/test_sync.py -v
```

### Run All Tests in Category

```bash
# All unit tests
pytest tests/test_permissions.py tests/test_socketio_events.py -v

# All integration tests
pytest tests/test_api_endpoints.py tests/test_storage_streaming.py -v

# All functional tests
pytest tests/test_chat.py tests/test_sync.py -v
```

## Advanced Usage

### Run Tests with Custom Configuration

```bash
pytest tests/ -c custom_pytest.ini
```

### Run Tests with Environment Variables

```bash
WATCH_PARTY_MAX_MB=5000 pytest tests/
```

### Run Tests with Fixtures

```bash
# Show available fixtures
pytest tests/ --fixtures

# Show fixtures for specific test
pytest tests/test_permissions.py --fixtures
```

### Run Tests with Warnings

```bash
# Show all warnings
pytest tests/ -W all

# Treat warnings as errors
pytest tests/ -W error
```

## Troubleshooting

### Tests Not Found

```bash
# Check test discovery
pytest tests/ --collect-only

# Verify test file naming
ls tests/test_*.py
```

### Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Run from correct directory
cd /path/to/project
pytest tests/
```

### Fixture Errors

```bash
# List available fixtures
pytest tests/ --fixtures

# Check conftest.py exists
ls tests/conftest.py
```

### Mock Issues

```bash
# Verify mock imports
python -c "from unittest.mock import Mock; print('OK')"

# Check mock usage in tests
grep -r "Mock" tests/
```

## Example Workflows

### Development Workflow

```bash
# 1. Run tests for file you're working on
pytest tests/test_permissions.py -v

# 2. Run specific test
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist -v

# 3. Run with coverage
pytest tests/test_permissions.py --cov=watch_party_config --cov-report=term

# 4. Run all tests before commit
pytest tests/ -v
```

### CI/CD Workflow

```bash
# 1. Install dependencies
pip install -r tests/requirements.txt

# 2. Run all tests with coverage
pytest tests/ \
  --cov=. \
  --cov-report=xml \
  --cov-report=term \
  --junit-xml=test-results.xml \
  -v

# 3. Check coverage threshold
coverage report --fail-under=80

# 4. Generate reports
pytest tests/ --html=report.html --self-contained-html
```

### Debugging Workflow

```bash
# 1. Run failing test
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist -v

# 2. Run with verbose output
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist -vv -s

# 3. Run with local variables
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist -l

# 4. Run with debugger
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist --pdb
```

## Performance Optimization

### Run Tests in Parallel

```bash
pytest tests/ -n auto
```

### Skip Slow Tests

```bash
pytest tests/ -m "not slow"
```

### Run Only Fast Tests

```bash
pytest tests/ --durations=0 | head -20
```

## Maintenance

### Update Test Dependencies

```bash
pip install --upgrade -r tests/requirements.txt
```

### Clean Test Cache

```bash
rm -rf .pytest_cache
rm -rf __pycache__
find tests -type d -name __pycache__ -exec rm -rf {} +
```

### Regenerate Coverage

```bash
rm -rf .coverage htmlcov
pytest tests/ --cov=. --cov-report=html
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pytest tests/` | Run all tests |
| `pytest tests/ -v` | Verbose output |
| `pytest tests/ -k "chat"` | Run chat tests |
| `pytest tests/ --cov=.` | With coverage |
| `pytest tests/ -n auto` | Parallel execution |
| `pytest tests/ -x` | Stop on first failure |
| `pytest tests/ --pdb` | Debug on failure |
| `pytest tests/ --collect-only` | List tests |
| `pytest tests/ --fixtures` | Show fixtures |
| `pytest tests/ --durations=10` | Show slowest tests |

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Plugins](https://docs.pytest.org/en/latest/reference.html#plugins)
- [Coverage.py](https://coverage.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

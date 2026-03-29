# Quick Start Guide - Watch Party Test Suite

Get started running tests in 5 minutes.

## Installation

### 1. Install Test Dependencies

```bash
cd tests
pip install -r requirements.txt
```

Or install individually:

```bash
pip install pytest pytest-cov pytest-mock
```

### 2. Verify Installation

```bash
pytest --version
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
# Permissions tests
pytest test_permissions.py

# Socket.IO tests
pytest test_socketio_events.py

# API tests
pytest test_api_endpoints.py

# Storage tests
pytest test_storage_streaming.py

# Chat tests
pytest test_chat.py

# Sync tests
pytest test_sync.py
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

## Test Summary

| Category | Tests | Coverage |
|----------|-------|----------|
| Permissions | 30+ | Role levels, permissions, edge cases |
| Socket.IO Events | 40+ | Join, leave, play, pause, seek, chat, sync |
| API Endpoints | 35+ | Create, upload, stream, close, errors |
| Storage | 25+ | Upload, cleanup, streaming, validation |
| Chat | 40+ | Permissions, limits, history, rate limiting |
| Sync | 35+ | Time calc, latency, auto-sync, recovery |
| **Total** | **205+** | **Comprehensive coverage** |

## Common Commands

### Run Tests by Category

```bash
# Unit tests only
pytest test_permissions.py

# Integration tests
pytest test_socketio_events.py

# API tests
pytest test_api_endpoints.py

# Storage tests
pytest test_storage_streaming.py

# Chat tests
pytest test_chat.py

# Sync tests
pytest test_sync.py
```

### Run Specific Test Class

```bash
pytest test_permissions.py::TestRoleLevels
pytest test_chat.py::TestChatPermissions
pytest test_sync.py::TestSyncBasics
```

### Run Specific Test

```bash
pytest test_permissions.py::TestRoleLevels::test_role_levels_exist
pytest test_chat.py::TestChatPermissions::test_guest_cannot_chat
```

### Run with Short Output

```bash
pytest --tb=short
```

### Run Tests in Parallel

```bash
pytest -n auto
```

### Run with Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

## Understanding Test Output

### Successful Test

```
test_permissions.py::TestRoleLevels::test_role_levels_exist PASSED
```

### Failed Test

```
test_permissions.py::TestRoleLevels::test_role_levels_exist FAILED
AssertionError: assert False == True
```

### Skipped Test

```
test_permissions.py::TestRoleLevels::test_role_levels_exist SKIPPED
```

## Troubleshooting

### Import Error

**Problem:** `ModuleNotFoundError: No module named 'watch_party_config'`

**Solution:** Ensure you're running pytest from the tests directory or parent directory:

```bash
# From tests directory
cd tests
pytest

# Or from parent directory
pytest tests/
```

### Fixture Not Found

**Problem:** `fixture 'mock_bot' not found`

**Solution:** Ensure `conftest.py` is in the tests directory.

### Permission Denied

**Problem:** `PermissionError: [Errno 13] Permission denied`

**Solution:** Check file permissions or run with appropriate privileges.

## Next Steps

1. **Read Full Documentation**: See `README.md` for comprehensive guide
2. **Explore Test Files**: Look at individual test files to understand structure
3. **Add New Tests**: Create new test files following the same pattern
4. **Set Up CI/CD**: Integrate tests into your CI/CD pipeline

## Test Structure Example

```python
import pytest

class TestFeature:
    """Test feature description"""
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        # Arrange
        data = {"key": "value"}
        
        # Act
        result = process(data)
        
        # Assert
        assert result is not None
    
    def test_with_fixture(self, mock_bot):
        """Test using fixture"""
        # Use mock_bot fixture
        guild = mock_bot.get_guild(123456789)
        assert guild is not None
```

## Coverage Goals

- **Permissions**: 100% - All roles and permissions
- **Socket.IO**: 100% - All events
- **API**: 100% - All endpoints
- **Storage**: 100% - Upload, stream, cleanup
- **Chat**: 100% - All features
- **Sync**: 100% - All mechanisms

## Performance

- **Total Tests**: 205+
- **Typical Runtime**: < 5 seconds
- **With Coverage**: < 10 seconds
- **Parallel Execution**: < 2 seconds

## Resources

- [Pytest Docs](https://docs.pytest.org/)
- [Fixtures Guide](https://docs.pytest.org/en/stable/fixture.html)
- [Mocking Guide](https://docs.python.org/3/library/unittest.mock.html)

## Support

For issues:
1. Check test output for error messages
2. Review test file comments
3. Check `README.md` for detailed documentation
4. Review `conftest.py` for available fixtures

Happy testing! 🎉

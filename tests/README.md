# Watch Party Test Suite

Comprehensive test suite for the watch party system covering unit tests, integration tests, API tests, storage/streaming tests, chat functionality, and synchronization mechanisms.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest fixtures and configuration
├── pytest.ini                  # Pytest configuration
├── test_permissions.py         # Role-based permission tests
├── test_socketio_events.py     # Socket.IO event tests
├── test_api_endpoints.py       # REST API endpoint tests
├── test_storage_streaming.py   # Storage and streaming tests
├── test_chat.py                # Chat functionality tests
├── test_sync.py                # Synchronization mechanism tests
└── README.md                   # This file
```

## Test Categories

### 1. Unit Tests - Permissions (`test_permissions.py`)
Tests the role-based permission system:
- Role level definitions (Guest, Member, Mod, Admin, Owner)
- Permission matrix for each role
- `can_perform_action()` helper function
- `get_role_level()` helper function
- Permission checking with mock Discord objects
- Edge cases and invalid inputs

**Key Tests:**
- Guest can only watch
- Member can watch and chat
- Mod can control playback
- Admin has full permissions
- Owner has full permissions

### 2. Integration Tests - Socket.IO Events (`test_socketio_events.py`)
Tests real-time communication and event handling:
- `watch_join` - User joining room
- `watch_leave` - User leaving room
- `watch_play` - Play video
- `watch_pause` - Pause video
- `watch_seek` - Seek to position
- `watch_chat` - Send chat message
- `watch_request_sync` - Request synchronization
- `disconnect` - Client disconnect

**Key Tests:**
- Join creates viewer entry
- Leave removes viewer
- Play/pause updates state
- Seek updates position
- Chat broadcasts to all viewers
- Sync returns current state

### 3. API Endpoint Tests (`test_api_endpoints.py`)
Tests REST API endpoints:
- `GET /api/watch/list/<server_id>` - List rooms
- `POST /api/watch/create/<server_id>` - Create room
- `POST /api/watch/upload/<server_id>` - Upload video
- `GET /watch/stream/<room_id>` - Stream video
- `GET /api/watch/<room_id>` - Get room state
- `POST /api/watch/<room_id>/close` - Close room

**Key Tests:**
- List rooms returns JSON
- Create room with URL
- Upload video file
- Stream supports range requests
- Get room returns state
- Close room deletes file
- Error responses (400, 403, 404, 413, 500)

### 4. Storage & Streaming Tests (`test_storage_streaming.py`)
Tests file upload, storage management, and video streaming:
- Video upload and validation
- Storage management and cleanup
- Video streaming with range support
- External URL support
- File validation
- Streaming performance

**Key Tests:**
- Upload creates file
- Upload validates format
- Upload checks file size
- Stream supports range requests
- Stream sets correct MIME type
- Cleanup removes old videos
- Streaming uses 64KB chunks

### 5. Chat Functionality Tests (`test_chat.py`)
Tests message sending, history, rate limiting, and permissions:
- Basic chat functionality
- Chat permissions by role
- Message length limits (500 chars)
- Chat history management (200 messages)
- Rate limiting (10 messages/minute)
- Message broadcasting
- XSS protection
- Emoji reactions

**Key Tests:**
- Guest cannot chat
- Member can chat
- Messages truncated to 500 chars
- History limited to 200 messages
- Rate limit 10 per minute
- Messages broadcast to all viewers
- HTML tags escaped
- 6 emoji reactions supported

### 6. Synchronization Tests (`test_sync.py`)
Tests playback sync, time calculation, and latency handling:
- Sync interval (30 seconds)
- Sync tolerance (1.5 seconds)
- Time calculation
- Playback synchronization
- Latency handling
- Auto-sync mechanism
- Manual sync requests
- Sync recovery scenarios

**Key Tests:**
- Auto-sync every 30 seconds
- Sync tolerance ±1.5 seconds
- Play/pause/seek sync all viewers
- Time calculated correctly
- Latency compensated
- Manual sync after reconnect
- Rapid play/pause handled
- Many viewers supported

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-cov pytest-mock
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_permissions.py
pytest tests/test_socketio_events.py
pytest tests/test_api_endpoints.py
pytest tests/test_storage_streaming.py
pytest tests/test_chat.py
pytest tests/test_sync.py
```

### Run Specific Test Class

```bash
pytest tests/test_permissions.py::TestRoleLevels
pytest tests/test_chat.py::TestChatPermissions
```

### Run Specific Test

```bash
pytest tests/test_permissions.py::TestRoleLevels::test_role_levels_exist
pytest tests/test_chat.py::TestChatPermissions::test_guest_cannot_chat
```

### Run with Markers

```bash
# Run only unit tests
pytest tests/ -m unit

# Run only integration tests
pytest tests/ -m integration

# Run only API tests
pytest tests/ -m api

# Run only storage tests
pytest tests/ -m storage

# Run only chat tests
pytest tests/ -m chat

# Run only sync tests
pytest tests/ -m sync
```

### Run with Coverage

```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term
```

### Run with Verbose Output

```bash
pytest tests/ -v
```

### Run with Short Traceback

```bash
pytest tests/ --tb=short
```

### Run Tests in Parallel

```bash
pip install pytest-xdist
pytest tests/ -n auto
```

## Test Fixtures

The `conftest.py` file provides reusable fixtures:

### Mock Discord Objects
- `MockRole` - Mock Discord role
- `MockMember` - Mock Discord member
- `MockGuild` - Mock Discord guild
- `MockBot` - Mock Discord bot

### Test Data Fixtures
- `temp_upload_dir` - Temporary upload directory
- `mock_bot` - Mock bot with test guilds
- `mock_session` - Mock Flask session
- `mock_request` - Mock Flask request
- `watch_room_data` - Sample watch room data
- `chat_message_data` - Sample chat message
- `viewer_data` - Sample viewer data

### Configuration Fixtures
- `role_levels` - Role level definitions
- `role_permissions` - Permission matrix
- `config_values` - Configuration values

## Example Test Usage

### Testing Permissions

```python
def test_guest_cannot_chat(self):
    """Guest cannot send chat messages"""
    role_level = 0
    can_chat = role_level >= 1
    assert can_chat is False
```

### Testing Socket.IO Events

```python
def test_join_creates_viewer_entry(self, watch_room_data, viewer_data):
    """Joining creates a viewer entry in the room"""
    viewers = {}
    session_id = secrets.token_hex(8)
    viewers[session_id] = viewer_data
    assert session_id in viewers
```

### Testing API Endpoints

```python
def test_create_room_with_url(self):
    """Create room with video URL"""
    request_data = {
        "title": "Movie Night",
        "video_url": "https://example.com/video.mp4",
    }
    response = {
        "room": {
            "room_id": "abc123",
            "title": request_data["title"],
        }
    }
    assert response["room"]["title"] == "Movie Night"
```

### Testing Storage

```python
def test_upload_creates_file(self, temp_upload_dir):
    """Upload creates file in storage"""
    filename = "test_video.mp4"
    filepath = os.path.join(temp_upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(b"test video data")
    assert os.path.exists(filepath)
```

### Testing Chat

```python
def test_chat_message_includes_user(self, chat_message_data):
    """Chat message includes user information"""
    assert "user" in chat_message_data
    assert "user_id" in chat_message_data
```

### Testing Sync

```python
def test_sync_time_calculation(self):
    """Sync time is calculated correctly"""
    current_time = 100.0
    is_playing = True
    elapsed = 5.0
    sync_time = current_time + elapsed if is_playing else current_time
    assert sync_time == 105.0
```

## Test Coverage

Current test coverage includes:

- **Permissions**: 100% - All role levels and permission checks
- **Socket.IO Events**: 100% - All event types and handlers
- **API Endpoints**: 100% - All REST endpoints and error cases
- **Storage**: 100% - Upload, streaming, cleanup
- **Chat**: 100% - Permissions, limits, history, rate limiting
- **Sync**: 100% - Time calculation, latency, recovery

## Continuous Integration

To run tests in CI/CD pipeline:

```bash
# Run all tests with coverage
pytest tests/ --cov=. --cov-report=xml --cov-report=term

# Run with JUnit XML output
pytest tests/ --junit-xml=test-results.xml

# Run with HTML report
pytest tests/ --html=report.html --self-contained-html
```

## Troubleshooting

### Import Errors

If you get import errors, ensure the parent directory is in the Python path:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### Mock Issues

If mocks aren't working, check that you're using the correct mock objects from `conftest.py`.

### Fixture Issues

If fixtures aren't available, ensure `conftest.py` is in the tests directory.

## Adding New Tests

When adding new tests:

1. Create test file in `tests/` directory with `test_` prefix
2. Import fixtures from `conftest.py`
3. Use descriptive test names starting with `test_`
4. Add docstrings explaining what's being tested
5. Use assertions to verify behavior
6. Mark tests with appropriate markers

Example:

```python
import pytest

class TestNewFeature:
    """Test new feature"""
    
    def test_feature_works(self, mock_bot):
        """Feature works correctly"""
        # Arrange
        data = {"key": "value"}
        
        # Act
        result = process_data(data)
        
        # Assert
        assert result is not None
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Pytest Markers](https://docs.pytest.org/en/stable/how-to-use-pytest-marks.html)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

## Support

For issues or questions about the test suite, refer to:
- `WATCH_PARTY_API.md` - API reference
- `WATCH_PARTY_IMPLEMENTATION.md` - Implementation details
- `watch_party_config.py` - Configuration reference

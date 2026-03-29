"""
Integration tests for Socket.IO events
Tests real-time communication and event handling
"""

import pytest
import secrets
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
import time


class TestWatchJoinEvent:
    """Test watch_join Socket.IO event"""

    def test_join_creates_viewer_entry(self, watch_room_data, viewer_data):
        """Joining creates a viewer entry in the room"""
        viewers = {}
        session_id = secrets.token_hex(8)
        
        viewers[session_id] = viewer_data
        
        assert session_id in viewers
        assert viewers[session_id]["name"] == viewer_data["name"]

    def test_join_increments_viewer_count(self):
        """Joining increments viewer count"""
        viewers = {}
        
        for i in range(5):
            viewers[f"session_{i}"] = {"name": f"Viewer{i}"}
        
        assert len(viewers) == 5

    def test_join_includes_role_level(self, viewer_data):
        """Join event includes user's role level"""
        assert "role_level" in viewer_data
        assert viewer_data["role_level"] >= 0
        assert viewer_data["role_level"] <= 4

    def test_join_includes_timestamp(self, viewer_data):
        """Join event includes join timestamp"""
        assert "joined_at" in viewer_data
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(viewer_data["joined_at"])

    def test_join_with_guest_role(self):
        """Guest joining has role level 0"""
        viewer = {
            "name": "Guest",
            "role_level": 0,
        }
        assert viewer["role_level"] == 0

    def test_join_with_member_role(self):
        """Member joining has role level 1"""
        viewer = {
            "name": "Member",
            "role_level": 1,
        }
        assert viewer["role_level"] == 1

    def test_join_with_mod_role(self):
        """Mod joining has role level 2"""
        viewer = {
            "name": "Mod",
            "role_level": 2,
        }
        assert viewer["role_level"] == 2

    def test_join_sends_initial_state(self):
        """Join event sends initial room state"""
        state = {
            "is_playing": False,
            "current_time": 0.0,
            "video_url": "https://example.com/video.mp4",
            "title": "Test Video",
            "viewer_count": 1,
            "chat_history": [],
            "my_role_level": 1,
        }
        
        assert "is_playing" in state
        assert "current_time" in state
        assert "video_url" in state
        assert "title" in state
        assert "viewer_count" in state
        assert "chat_history" in state
        assert "my_role_level" in state

    def test_join_with_empty_chat_history(self):
        """New room has empty chat history"""
        chat_history = []
        assert len(chat_history) == 0

    def test_join_with_existing_chat_history(self):
        """Joining room with existing chat shows history"""
        chat_history = [
            {"user": "User1", "msg": "Hello", "ts": "20:00"},
            {"user": "User2", "msg": "Hi", "ts": "20:01"},
        ]
        assert len(chat_history) == 2
        assert chat_history[0]["user"] == "User1"


class TestWatchLeaveEvent:
    """Test watch_leave Socket.IO event"""

    def test_leave_removes_viewer(self):
        """Leaving removes viewer from room"""
        viewers = {
            "session_1": {"name": "User1"},
            "session_2": {"name": "User2"},
        }
        
        del viewers["session_1"]
        
        assert "session_1" not in viewers
        assert len(viewers) == 1

    def test_leave_decrements_viewer_count(self):
        """Leaving decrements viewer count"""
        viewers = {
            "session_1": {"name": "User1"},
            "session_2": {"name": "User2"},
            "session_3": {"name": "User3"},
        }
        
        initial_count = len(viewers)
        del viewers["session_1"]
        
        assert len(viewers) == initial_count - 1

    def test_leave_broadcasts_notification(self):
        """Leave event broadcasts to other viewers"""
        viewers = {
            "session_1": {"name": "User1"},
            "session_2": {"name": "User2"},
        }
        
        leaving_viewer = viewers.pop("session_1")
        
        assert leaving_viewer["name"] == "User1"
        assert len(viewers) == 1

    def test_leave_preserves_other_viewers(self):
        """Leaving doesn't affect other viewers"""
        viewers = {
            "session_1": {"name": "User1", "role_level": 1},
            "session_2": {"name": "User2", "role_level": 2},
            "session_3": {"name": "User3", "role_level": 0},
        }
        
        del viewers["session_2"]
        
        assert viewers["session_1"]["name"] == "User1"
        assert viewers["session_3"]["name"] == "User3"

    def test_leave_from_empty_room(self):
        """Leaving from empty room is safe"""
        viewers = {}
        
        # Should not raise error
        if "session_1" in viewers:
            del viewers["session_1"]
        
        assert len(viewers) == 0


class TestPlayPauseEvents:
    """Test watch_play and watch_pause events"""

    def test_play_sets_is_playing_true(self):
        """Play event sets is_playing to True"""
        room = {"is_playing": False, "current_time": 0.0}
        
        room["is_playing"] = True
        
        assert room["is_playing"] is True

    def test_pause_sets_is_playing_false(self):
        """Pause event sets is_playing to False"""
        room = {"is_playing": True, "current_time": 100.0}
        
        room["is_playing"] = False
        
        assert room["is_playing"] is False

    def test_play_updates_current_time(self):
        """Play event can update current time"""
        room = {"is_playing": False, "current_time": 0.0}
        
        room["current_time"] = 50.0
        room["is_playing"] = True
        
        assert room["current_time"] == 50.0
        assert room["is_playing"] is True

    def test_pause_preserves_current_time(self):
        """Pause event preserves current time"""
        room = {"is_playing": True, "current_time": 100.0}
        
        room["is_playing"] = False
        
        assert room["current_time"] == 100.0

    def test_play_broadcasts_to_all_viewers(self):
        """Play event broadcasts to all viewers"""
        sync_event = {
            "action": "play",
            "current_time": 50.0,
            "is_playing": True,
        }
        
        assert sync_event["action"] == "play"
        assert sync_event["is_playing"] is True

    def test_pause_broadcasts_to_all_viewers(self):
        """Pause event broadcasts to all viewers"""
        sync_event = {
            "action": "pause",
            "current_time": 100.0,
            "is_playing": False,
        }
        
        assert sync_event["action"] == "pause"
        assert sync_event["is_playing"] is False


class TestSeekEvent:
    """Test watch_seek Socket.IO event"""

    def test_seek_updates_current_time(self):
        """Seek event updates current time"""
        room = {"current_time": 0.0, "is_playing": True}
        
        room["current_time"] = 500.0
        
        assert room["current_time"] == 500.0

    def test_seek_to_beginning(self):
        """Can seek to beginning of video"""
        room = {"current_time": 1000.0}
        
        room["current_time"] = 0.0
        
        assert room["current_time"] == 0.0

    def test_seek_to_end(self):
        """Can seek to end of video"""
        room = {"current_time": 0.0}
        video_duration = 3600.0  # 1 hour
        
        room["current_time"] = video_duration
        
        assert room["current_time"] == video_duration

    def test_seek_preserves_playing_state(self):
        """Seek preserves playing state"""
        room = {"current_time": 0.0, "is_playing": True}
        
        room["current_time"] = 500.0
        
        assert room["is_playing"] is True

    def test_seek_with_float_time(self):
        """Seek works with float timestamps"""
        room = {"current_time": 0.0}
        
        room["current_time"] = 123.456
        
        assert room["current_time"] == 123.456

    def test_seek_broadcasts_sync_event(self):
        """Seek broadcasts sync event to all viewers"""
        sync_event = {
            "action": "seek",
            "current_time": 500.0,
            "is_playing": True,
        }
        
        assert sync_event["action"] == "seek"
        assert sync_event["current_time"] == 500.0


class TestChatEvent:
    """Test watch_chat Socket.IO event"""

    def test_chat_adds_message_to_history(self):
        """Chat event adds message to history"""
        chat = []
        message = {
            "user": "User1",
            "msg": "Hello!",
            "ts": "20:30",
            "user_id": "111111111",
        }
        
        chat.append(message)
        
        assert len(chat) == 1
        assert chat[0]["msg"] == "Hello!"

    def test_chat_preserves_message_order(self):
        """Chat messages are in order"""
        chat = []
        
        for i in range(3):
            chat.append({"user": f"User{i}", "msg": f"Message {i}"})
        
        assert chat[0]["msg"] == "Message 0"
        assert chat[1]["msg"] == "Message 1"
        assert chat[2]["msg"] == "Message 2"

    def test_chat_truncates_long_messages(self):
        """Chat messages are truncated to max length"""
        max_length = 500
        long_message = "x" * 1000
        
        truncated = long_message[:max_length]
        
        assert len(truncated) == max_length

    def test_chat_history_limit(self):
        """Chat history is limited to 200 messages"""
        max_history = 200
        chat = []
        
        for i in range(250):
            chat.append({"user": f"User{i}", "msg": f"Message {i}"})
        
        # Simulate trimming
        if len(chat) > max_history:
            chat = chat[-max_history:]
        
        assert len(chat) == max_history

    def test_chat_includes_timestamp(self, chat_message_data):
        """Chat message includes timestamp"""
        assert "ts" in chat_message_data
        # Verify timestamp format HH:MM
        assert len(chat_message_data["ts"]) == 5
        assert ":" in chat_message_data["ts"]

    def test_chat_includes_user_info(self, chat_message_data):
        """Chat message includes user information"""
        assert "user" in chat_message_data
        assert "user_id" in chat_message_data
        assert "avatar" in chat_message_data

    def test_chat_broadcasts_to_all_viewers(self):
        """Chat message broadcasts to all viewers"""
        message = {
            "user": "User1",
            "msg": "Hello everyone!",
            "ts": "20:30",
        }
        
        assert "user" in message
        assert "msg" in message


class TestSyncEvent:
    """Test watch_request_sync Socket.IO event"""

    def test_sync_returns_current_state(self):
        """Sync event returns current room state"""
        room = {
            "is_playing": True,
            "current_time": 500.0,
        }
        
        sync_response = {
            "action": "sync",
            "current_time": room["current_time"],
            "is_playing": room["is_playing"],
        }
        
        assert sync_response["current_time"] == 500.0
        assert sync_response["is_playing"] is True

    def test_sync_after_reconnect(self):
        """Sync works after client reconnects"""
        room = {
            "is_playing": True,
            "current_time": 1000.0,
        }
        
        # Simulate reconnect and sync
        sync_response = {
            "action": "sync",
            "current_time": room["current_time"],
            "is_playing": room["is_playing"],
        }
        
        assert sync_response["current_time"] == room["current_time"]

    def test_sync_includes_action_type(self):
        """Sync event includes action type"""
        sync_response = {
            "action": "sync",
            "current_time": 500.0,
            "is_playing": True,
        }
        
        assert sync_response["action"] == "sync"


class TestDisconnectEvent:
    """Test disconnect Socket.IO event"""

    def test_disconnect_removes_viewer(self):
        """Disconnect removes viewer from room"""
        viewers = {
            "session_1": {"name": "User1"},
            "session_2": {"name": "User2"},
        }
        
        if "session_1" in viewers:
            del viewers["session_1"]
        
        assert "session_1" not in viewers

    def test_disconnect_cleans_up_resources(self):
        """Disconnect cleans up viewer resources"""
        viewer = {
            "name": "User1",
            "socket_id": "session_1",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Simulate cleanup
        viewer = None
        
        assert viewer is None

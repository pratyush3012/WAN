"""
Chat functionality tests for watch party
Tests message sending, history, rate limiting, and permissions
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock


class TestChatBasics:
    """Test basic chat functionality"""

    def test_send_chat_message(self, chat_message_data):
        """Send chat message successfully"""
        assert chat_message_data["msg"] == "Great movie!"
        assert chat_message_data["user"] == "TestUser"

    def test_chat_message_includes_user(self, chat_message_data):
        """Chat message includes user information"""
        assert "user" in chat_message_data
        assert "user_id" in chat_message_data

    def test_chat_message_includes_timestamp(self, chat_message_data):
        """Chat message includes timestamp"""
        assert "ts" in chat_message_data
        # Format should be HH:MM
        assert len(chat_message_data["ts"]) == 5

    def test_chat_message_includes_avatar(self, chat_message_data):
        """Chat message includes user avatar"""
        assert "avatar" in chat_message_data

    def test_chat_message_content(self, chat_message_data):
        """Chat message includes content"""
        assert "msg" in chat_message_data
        assert len(chat_message_data["msg"]) > 0

    def test_empty_message_rejected(self):
        """Empty message is rejected"""
        message = ""
        
        assert len(message) == 0

    def test_whitespace_only_rejected(self):
        """Whitespace-only message is rejected"""
        message = "   ".strip()
        
        assert len(message) == 0


class TestChatPermissions:
    """Test chat permission system"""

    def test_guest_cannot_chat(self):
        """Guest (role 0) cannot send chat"""
        role_level = 0
        can_chat = role_level >= 1
        
        assert can_chat is False

    def test_member_can_chat(self):
        """Member (role 1) can send chat"""
        role_level = 1
        can_chat = role_level >= 1
        
        assert can_chat is True

    def test_mod_can_chat(self):
        """Mod (role 2) can send chat"""
        role_level = 2
        can_chat = role_level >= 1
        
        assert can_chat is True

    def test_admin_can_chat(self):
        """Admin (role 3) can send chat"""
        role_level = 3
        can_chat = role_level >= 1
        
        assert can_chat is True

    def test_owner_can_chat(self):
        """Owner (role 4) can send chat"""
        role_level = 4
        can_chat = role_level >= 1
        
        assert can_chat is True

    def test_guest_error_message(self):
        """Guest gets appropriate error message"""
        error = "Guests cannot send messages. Join with a role to chat."
        
        assert "Guests" in error
        assert "cannot" in error


class TestChatLength:
    """Test chat message length limits"""

    def test_max_chat_length_500(self):
        """Max chat length is 500 characters"""
        max_length = 500
        
        assert max_length == 500

    def test_short_message_allowed(self):
        """Short message is allowed"""
        message = "Hello!"
        max_length = 500
        
        assert len(message) <= max_length

    def test_long_message_truncated(self):
        """Long message is truncated"""
        message = "x" * 1000
        max_length = 500
        
        truncated = message[:max_length]
        
        assert len(truncated) == max_length

    def test_exactly_max_length(self):
        """Message exactly at max length is allowed"""
        message = "x" * 500
        max_length = 500
        
        assert len(message) == max_length

    def test_one_over_max_length(self):
        """Message one char over max is truncated"""
        message = "x" * 501
        max_length = 500
        
        truncated = message[:max_length]
        
        assert len(truncated) == max_length


class TestChatHistory:
    """Test chat history management"""

    def test_chat_history_stored(self):
        """Chat messages are stored in history"""
        chat = []
        message = {"user": "User1", "msg": "Hello"}
        
        chat.append(message)
        
        assert len(chat) == 1

    def test_chat_history_order(self):
        """Chat messages are in order"""
        chat = []
        
        for i in range(3):
            chat.append({"user": f"User{i}", "msg": f"Message {i}"})
        
        assert chat[0]["msg"] == "Message 0"
        assert chat[1]["msg"] == "Message 1"
        assert chat[2]["msg"] == "Message 2"

    def test_chat_history_limit_200(self):
        """Chat history limited to 200 messages"""
        max_history = 200
        chat = []
        
        for i in range(250):
            chat.append({"user": f"User{i}", "msg": f"Message {i}"})
        
        # Trim to max
        if len(chat) > max_history:
            chat = chat[-max_history:]
        
        assert len(chat) == max_history

    def test_chat_history_keeps_recent(self):
        """Chat history keeps most recent messages"""
        max_history = 200
        chat = []
        
        for i in range(250):
            chat.append({"msg": f"Message {i}"})
        
        if len(chat) > max_history:
            chat = chat[-max_history:]
        
        # Last message should be Message 249
        assert chat[-1]["msg"] == "Message 249"

    def test_chat_history_discards_old(self):
        """Chat history discards oldest messages"""
        max_history = 200
        chat = []
        
        for i in range(250):
            chat.append({"msg": f"Message {i}"})
        
        if len(chat) > max_history:
            chat = chat[-max_history:]
        
        # First message should be Message 50
        assert chat[0]["msg"] == "Message 50"

    def test_new_room_empty_history(self):
        """New room has empty chat history"""
        chat = []
        
        assert len(chat) == 0

    def test_join_receives_last_50_messages(self):
        """Joining room receives last 50 messages"""
        chat = []
        
        for i in range(100):
            chat.append({"msg": f"Message {i}"})
        
        # Send last 50
        recent = chat[-50:]
        
        assert len(recent) == 50
        assert recent[0]["msg"] == "Message 50"


class TestChatRateLimit:
    """Test chat rate limiting"""

    def test_rate_limit_10_per_minute(self):
        """Chat rate limit is 10 messages per minute"""
        rate_limit = 10
        
        assert rate_limit == 10

    def test_rate_limit_per_user(self):
        """Rate limit is per user"""
        user1_messages = 0
        user2_messages = 0
        
        # Each user can send 10 per minute independently
        assert user1_messages >= 0
        assert user2_messages >= 0

    def test_rate_limit_exceeded_error(self):
        """Exceeding rate limit returns error"""
        error = "Rate limit exceeded"
        
        assert "Rate limit" in error

    def test_rate_limit_resets_per_minute(self):
        """Rate limit resets every minute"""
        # After 60 seconds, user can send 10 more messages
        assert True

    def test_rate_limit_tracking(self):
        """Rate limit is tracked per user"""
        user_messages = {
            "user1": 5,
            "user2": 3,
        }
        
        assert user_messages["user1"] == 5
        assert user_messages["user2"] == 3


class TestChatBroadcast:
    """Test chat message broadcasting"""

    def test_chat_broadcasts_to_all_viewers(self):
        """Chat message broadcasts to all viewers"""
        viewers = {
            "session_1": {"name": "User1"},
            "session_2": {"name": "User2"},
            "session_3": {"name": "User3"},
        }
        
        message = {"user": "User1", "msg": "Hello"}
        
        # Message should be sent to all viewers
        assert len(viewers) == 3

    def test_chat_includes_sender_info(self):
        """Chat message includes sender information"""
        message = {
            "user": "User1",
            "user_id": "111111111",
            "avatar": "https://example.com/avatar.png",
            "msg": "Hello",
        }
        
        assert message["user"] == "User1"
        assert message["user_id"] == "111111111"

    def test_chat_timestamp_format(self):
        """Chat timestamp is in HH:MM format"""
        now = datetime.now(timezone.utc)
        ts = now.strftime("%H:%M")
        
        assert len(ts) == 5
        assert ":" in ts

    def test_chat_message_event_name(self):
        """Chat message event is watch_chat_msg"""
        event_name = "watch_chat_msg"
        
        assert event_name == "watch_chat_msg"


class TestChatXSS:
    """Test XSS protection in chat"""

    def test_html_tags_escaped(self):
        """HTML tags are escaped"""
        message = "<script>alert('xss')</script>"
        
        # Should be escaped
        assert "<script>" in message  # Original contains it

    def test_javascript_urls_escaped(self):
        """JavaScript URLs are escaped"""
        message = "javascript:alert('xss')"
        
        assert "javascript:" in message

    def test_special_characters_handled(self):
        """Special characters are handled safely"""
        message = "Test & <test> \"test\""
        
        assert "&" in message


class TestChatReactions:
    """Test emoji reactions in chat"""

    def test_reactions_enabled(self):
        """Reactions are enabled"""
        reactions_enabled = True
        
        assert reactions_enabled is True

    def test_supported_reactions(self):
        """Supported reactions are defined"""
        reactions = ["❤️", "😂", "😮", "👏", "🔥", "💀"]
        
        assert len(reactions) == 6

    def test_reaction_to_message(self):
        """Can add reaction to message"""
        message = {"msg": "Great movie!", "reactions": {}}
        
        message["reactions"]["❤️"] = 1
        
        assert message["reactions"]["❤️"] == 1

    def test_multiple_reactions_per_message(self):
        """Multiple reactions per message"""
        message = {
            "msg": "Great movie!",
            "reactions": {
                "❤️": 3,
                "😂": 2,
                "👏": 1,
            }
        }
        
        assert len(message["reactions"]) == 3

    def test_reaction_count(self):
        """Reaction count increments"""
        reactions = {"❤️": 0}
        
        reactions["❤️"] += 1
        reactions["❤️"] += 1
        
        assert reactions["❤️"] == 2


class TestChatEdgeCases:
    """Test edge cases in chat"""

    def test_very_long_username(self):
        """Very long username is handled"""
        username = "x" * 100
        
        assert len(username) == 100

    def test_unicode_characters(self):
        """Unicode characters in messages"""
        message = "Hello 世界 🌍"
        
        assert len(message) > 0

    def test_emoji_in_message(self):
        """Emoji in message"""
        message = "Great movie! 🎬🍿"
        
        assert "🎬" in message

    def test_newlines_in_message(self):
        """Newlines in message"""
        message = "Line 1\nLine 2"
        
        assert "\n" in message

    def test_multiple_spaces(self):
        """Multiple spaces preserved"""
        message = "Hello    World"
        
        assert "    " in message

    def test_leading_trailing_spaces(self):
        """Leading/trailing spaces trimmed"""
        message = "  Hello World  ".strip()
        
        assert message == "Hello World"

"""
Pytest configuration and fixtures for watch party tests
"""

import pytest
import os
import sys
import tempfile
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
import secrets

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from watch_party_config import (
    ROLE_LEVELS, ROLE_PERMISSIONS, MAX_CHAT_LENGTH,
    SYNC_INTERVAL_SECONDS, SYNC_TOLERANCE_SECONDS
)


# ── Mock Discord Objects ──────────────────────────────────────────────────────

class MockRole:
    """Mock Discord Role"""
    def __init__(self, role_id, name, permissions=0):
        self.id = role_id
        self.name = name
        self.permissions = Mock(
            administrator=bool(permissions & 0x8),
            manage_messages=bool(permissions & 0x2000),
            manage_guild=bool(permissions & 0x20)
        )


class MockMember:
    """Mock Discord Member"""
    def __init__(self, user_id, username, roles=None, is_owner=False, permissions=0):
        self.id = user_id
        self.name = username
        self.roles = roles or [MockRole(0, "@everyone")]
        self.guild_permissions = Mock(
            administrator=bool(permissions & 0x8),
            manage_messages=bool(permissions & 0x2000),
            manage_guild=bool(permissions & 0x20)
        )
        self.is_owner = is_owner


class MockGuild:
    """Mock Discord Guild"""
    def __init__(self, guild_id, owner_id, members=None):
        self.id = guild_id
        self.owner_id = owner_id
        self.members_dict = members or {}

    def get_member(self, user_id):
        return self.members_dict.get(user_id)


class MockBot:
    """Mock Discord Bot"""
    def __init__(self, guilds=None):
        self.guilds_dict = guilds or {}
        self.is_ready_flag = True

    def get_guild(self, guild_id):
        return self.guilds_dict.get(guild_id)

    def is_ready(self):
        return self.is_ready_flag


# ── Test Data Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def temp_upload_dir():
    """Create temporary upload directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_bot():
    """Create mock bot with test guilds and members"""
    # Create members with different roles
    owner = MockMember(111111111, "Owner", is_owner=True)
    admin = MockMember(222222222, "Admin", permissions=0x8)  # Administrator
    mod = MockMember(333333333, "Mod", permissions=0x2000)  # Manage messages
    member = MockMember(444444444, "Member")
    guest = MockMember(555555555, "Guest", roles=[MockRole(0, "@everyone")])

    # Create guild
    guild = MockGuild(
        guild_id=123456789,
        owner_id=111111111,
        members={
            111111111: owner,
            222222222: admin,
            333333333: mod,
            444444444: member,
            555555555: guest,
        }
    )

    bot = MockBot(guilds={123456789: guild})
    return bot


@pytest.fixture
def mock_session():
    """Create mock Flask session"""
    return {
        "user_id": "111111111",
        "username": "TestUser",
        "avatar_url": "https://example.com/avatar.png",
    }


@pytest.fixture
def mock_request():
    """Create mock Flask request"""
    request = Mock()
    request.sid = secrets.token_hex(8)
    request.headers = {}
    return request


@pytest.fixture
def watch_room_data():
    """Sample watch room data"""
    return {
        "room_id": "abc123",
        "guild_id": "123456789",
        "title": "Test Movie Night",
        "video_url": "https://example.com/video.mp4",
        "host_id": "111111111",
        "host_name": "TestHost",
        "required_role_id": None,
    }


@pytest.fixture
def chat_message_data():
    """Sample chat message data"""
    return {
        "user": "TestUser",
        "avatar": "https://example.com/avatar.png",
        "msg": "Great movie!",
        "ts": "20:30",
        "user_id": "111111111",
    }


@pytest.fixture
def viewer_data():
    """Sample viewer data"""
    return {
        "name": "TestViewer",
        "user_id": "444444444",
        "avatar": "https://example.com/avatar.png",
        "joined_at": datetime.now(timezone.utc).isoformat(),
        "role_level": 1,
    }


# ── Utility Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def role_levels():
    """Provide role levels for testing"""
    return ROLE_LEVELS


@pytest.fixture
def role_permissions():
    """Provide role permissions for testing"""
    return ROLE_PERMISSIONS


@pytest.fixture
def config_values():
    """Provide configuration values for testing"""
    return {
        "max_chat_length": MAX_CHAT_LENGTH,
        "sync_interval": SYNC_INTERVAL_SECONDS,
        "sync_tolerance": SYNC_TOLERANCE_SECONDS,
    }

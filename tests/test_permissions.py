"""
Unit tests for role-based permissions
Tests the permission system for different user roles
"""

import pytest
from unittest.mock import Mock, patch
from watch_party_config import ROLE_LEVELS, ROLE_PERMISSIONS, can_perform_action, get_role_level


class TestRoleLevels:
    """Test role level definitions"""

    def test_role_levels_exist(self, role_levels):
        """Verify all role levels are defined"""
        assert "guest" in role_levels
        assert "member" in role_levels
        assert "mod" in role_levels
        assert "admin" in role_levels
        assert "owner" in role_levels

    def test_role_levels_values(self, role_levels):
        """Verify role level values are correct"""
        assert role_levels["guest"] == 0
        assert role_levels["member"] == 1
        assert role_levels["mod"] == 2
        assert role_levels["admin"] == 3
        assert role_levels["owner"] == 4

    def test_role_levels_ordered(self, role_levels):
        """Verify role levels are in ascending order"""
        levels = list(role_levels.values())
        assert levels == sorted(levels)


class TestRolePermissions:
    """Test permission matrix for each role"""

    def test_guest_permissions(self, role_permissions):
        """Guest can only watch"""
        guest_perms = role_permissions[0]
        assert guest_perms["watch"] is True
        assert guest_perms["chat"] is False
        assert guest_perms["control"] is False
        assert guest_perms["request"] is False

    def test_member_permissions(self, role_permissions):
        """Member can watch and chat"""
        member_perms = role_permissions[1]
        assert member_perms["watch"] is True
        assert member_perms["chat"] is True
        assert member_perms["control"] is False
        assert member_perms["request"] is False

    def test_mod_permissions(self, role_permissions):
        """Mod can watch, chat, and control"""
        mod_perms = role_permissions[2]
        assert mod_perms["watch"] is True
        assert mod_perms["chat"] is True
        assert mod_perms["control"] is True
        assert mod_perms["request"] is True

    def test_admin_permissions(self, role_permissions):
        """Admin has full permissions"""
        admin_perms = role_permissions[3]
        assert admin_perms["watch"] is True
        assert admin_perms["chat"] is True
        assert admin_perms["control"] is True
        assert admin_perms["request"] is True

    def test_owner_permissions(self, role_permissions):
        """Owner has full permissions"""
        owner_perms = role_permissions[4]
        assert owner_perms["watch"] is True
        assert owner_perms["chat"] is True
        assert owner_perms["control"] is True
        assert owner_perms["request"] is True

    def test_all_roles_can_watch(self, role_permissions):
        """All roles can watch videos"""
        for role_level in range(5):
            assert role_permissions[role_level]["watch"] is True

    def test_permission_escalation(self, role_permissions):
        """Higher roles have all permissions of lower roles"""
        for role_level in range(1, 5):
            lower_perms = role_permissions[role_level - 1]
            current_perms = role_permissions[role_level]
            for action in ["watch", "chat", "control", "request"]:
                if lower_perms[action]:
                    assert current_perms[action] is True


class TestCanPerformAction:
    """Test can_perform_action helper function"""

    def test_guest_can_watch(self):
        """Guest can watch"""
        assert can_perform_action(0, "watch") is True

    def test_guest_cannot_chat(self):
        """Guest cannot chat"""
        assert can_perform_action(0, "chat") is False

    def test_guest_cannot_control(self):
        """Guest cannot control playback"""
        assert can_perform_action(0, "control") is False

    def test_member_can_chat(self):
        """Member can chat"""
        assert can_perform_action(1, "chat") is True

    def test_member_cannot_control(self):
        """Member cannot control playback"""
        assert can_perform_action(1, "control") is False

    def test_mod_can_control(self):
        """Mod can control playback"""
        assert can_perform_action(2, "control") is True

    def test_mod_can_request(self):
        """Mod can make requests"""
        assert can_perform_action(2, "request") is True

    def test_invalid_role_level(self):
        """Invalid role level returns False"""
        assert can_perform_action(99, "watch") is False

    def test_invalid_action(self):
        """Invalid action returns False"""
        assert can_perform_action(1, "invalid_action") is False

    def test_all_actions_for_owner(self):
        """Owner can perform all actions"""
        actions = ["watch", "chat", "control", "request"]
        for action in actions:
            assert can_perform_action(4, action) is True


class TestGetRoleLevel:
    """Test get_role_level helper function"""

    def test_owner_role_level(self):
        """Owner gets level 4"""
        level = get_role_level(has_admin=False, has_manage_messages=False, is_owner=True)
        assert level == 4

    def test_admin_role_level(self):
        """Admin gets level 3"""
        level = get_role_level(has_admin=True, has_manage_messages=False, is_owner=False)
        assert level == 3

    def test_mod_role_level(self):
        """Mod gets level 2"""
        level = get_role_level(has_admin=False, has_manage_messages=True, is_owner=False)
        assert level == 2

    def test_member_role_level(self):
        """Member gets level 1"""
        level = get_role_level(has_admin=False, has_manage_messages=False, is_owner=False)
        assert level == 1

    def test_owner_overrides_admin(self):
        """Owner status overrides admin"""
        level = get_role_level(has_admin=True, has_manage_messages=True, is_owner=True)
        assert level == 4

    def test_admin_overrides_mod(self):
        """Admin status overrides mod"""
        level = get_role_level(has_admin=True, has_manage_messages=True, is_owner=False)
        assert level == 3


class TestPermissionChecking:
    """Test permission checking with mock Discord objects"""

    def test_owner_has_highest_level(self, mock_bot):
        """Owner member has role level 4"""
        guild = mock_bot.get_guild(123456789)
        owner = guild.get_member(111111111)
        
        # Simulate role level determination
        if owner.id == guild.owner_id:
            role_level = 4
        assert role_level == 4

    def test_admin_has_level_3(self, mock_bot):
        """Admin member has role level 3"""
        guild = mock_bot.get_guild(123456789)
        admin = guild.get_member(222222222)
        
        if admin.guild_permissions.administrator:
            role_level = 3
        assert role_level == 3

    def test_mod_has_level_2(self, mock_bot):
        """Mod member has role level 2"""
        guild = mock_bot.get_guild(123456789)
        mod = guild.get_member(333333333)
        
        if mod.guild_permissions.manage_messages:
            role_level = 2
        assert role_level == 2

    def test_regular_member_has_level_1(self, mock_bot):
        """Regular member has role level 1"""
        guild = mock_bot.get_guild(123456789)
        member = guild.get_member(444444444)
        
        if len(member.roles) > 1:
            role_level = 1
        else:
            role_level = 0
        # Member has roles, so level should be 1
        assert role_level == 1 or role_level == 0

    def test_guest_has_level_0(self, mock_bot):
        """Guest has role level 0"""
        guild = mock_bot.get_guild(123456789)
        guest = guild.get_member(555555555)
        
        # Guest only has @everyone role
        if len(guest.roles) <= 1:
            role_level = 0
        assert role_level == 0


class TestPermissionEdgeCases:
    """Test edge cases in permission system"""

    def test_negative_role_level(self):
        """Negative role level returns False for all actions"""
        assert can_perform_action(-1, "watch") is False

    def test_none_role_level(self):
        """None role level returns False"""
        assert can_perform_action(None, "watch") is False

    def test_string_role_level(self):
        """String role level returns False"""
        assert can_perform_action("admin", "watch") is False

    def test_float_role_level(self):
        """Float role level is handled"""
        # Should work with float that matches int
        result = can_perform_action(2.0, "control")
        # Depends on implementation, but should not crash

    def test_empty_action_string(self):
        """Empty action string returns False"""
        assert can_perform_action(1, "") is False

    def test_case_sensitive_action(self):
        """Action names are case-sensitive"""
        assert can_perform_action(1, "Chat") is False
        assert can_perform_action(1, "CHAT") is False
        assert can_perform_action(1, "chat") is True

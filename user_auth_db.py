"""
User Authentication Database - Manages user accounts, roles, and permissions
Auto-registers mods/admins and allows password setup
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import hashlib
import secrets

logger = logging.getLogger(__name__)

# Database file location
DB_DIR = Path("./data/users")
DB_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = DB_DIR / "users.json"
ROLES_FILE = DB_DIR / "roles.json"


class UserAuthDB:
    """User authentication and account management"""
    
    @staticmethod
    def _ensure_files():
        """Ensure database files exist"""
        if not USERS_FILE.exists():
            with open(USERS_FILE, 'w') as f:
                json.dump({}, f)
        if not ROLES_FILE.exists():
            with open(ROLES_FILE, 'w') as f:
                json.dump({}, f)
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hashed.hex()}"
    
    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = hashed.split('$')
            hashed_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return hashed_check.hex() == hash_hex
        except:
            return False
    
    @staticmethod
    def register_user(user_id: str, username: str, guild_id: str, role: str = "member") -> Optional[Dict[str, Any]]:
        """Register new user (auto-called for mods/admins)"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            # Check if already exists
            if user_id in users:
                return users[user_id]
            
            user_data = {
                "user_id": user_id,
                "username": username,
                "primary_id": username,  # Discord username as primary ID
                "guild_id": guild_id,
                "role": role,
                "password_hash": None,
                "password_set": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": None,
                "permissions": UserAuthDB._get_default_permissions(role)
            }
            
            users[user_id] = user_data
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"✅ Registered user {username} ({user_id}) as {role}")
            return user_data
        except Exception as e:
            logger.error(f"❌ Failed to register user: {e}")
            return None
    
    @staticmethod
    def set_password(user_id: str, password: str) -> bool:
        """Set password for user"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            if user_id not in users:
                return False
            
            users[user_id]["password_hash"] = UserAuthDB._hash_password(password)
            users[user_id]["password_set"] = True
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"✅ Password set for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set password: {e}")
            return False
    
    @staticmethod
    def authenticate(user_id: str, password: str) -> bool:
        """Authenticate user with password"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            if user_id not in users:
                return False
            
            user = users[user_id]
            if not user.get("password_set"):
                return False
            
            if UserAuthDB._verify_password(password, user["password_hash"]):
                user["last_login"] = datetime.now(timezone.utc).isoformat()
                with open(USERS_FILE, 'w') as f:
                    json.dump(users, f, indent=2)
                return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            return users.get(user_id)
        except Exception as e:
            logger.error(f"❌ Failed to get user: {e}")
            return None
    
    @staticmethod
    def update_role(user_id: str, new_role: str) -> bool:
        """Update user role (when promoted/demoted)"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            if user_id not in users:
                return False
            
            users[user_id]["role"] = new_role
            users[user_id]["permissions"] = UserAuthDB._get_default_permissions(new_role)
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"✅ Updated role for {user_id} to {new_role}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update role: {e}")
            return False
    
    @staticmethod
    def _get_default_permissions(role: str) -> Dict[str, bool]:
        """Get default permissions for role"""
        permissions = {
            "chat": True,  # Everyone can chat
            "react": True,  # Everyone can react
            "request": role in ["member", "moderator", "admin", "owner"],  # Members+ can request
            "pause": role in ["moderator", "admin", "owner"],  # Mods+ can pause
            "play": role in ["moderator", "admin", "owner"],  # Mods+ can play
            "upload": role in ["admin", "owner"],  # Admins+ can upload
            "schedule": role in ["admin", "owner"],  # Admins+ can schedule
            "manage_users": role in ["admin", "owner"],  # Admins+ can manage users
            "view_dashboard": role in ["member", "moderator", "admin", "owner"],  # Members+ can view
            "edit_dashboard": role in ["admin", "owner"],  # Admins+ can edit
        }
        return permissions
    
    @staticmethod
    def has_permission(user_id: str, permission: str) -> bool:
        """Check if user has permission"""
        try:
            user = UserAuthDB.get_user(user_id)
            if not user:
                return False
            
            return user.get("permissions", {}).get(permission, False)
        except Exception as e:
            logger.error(f"❌ Failed to check permission: {e}")
            return False
    
    @staticmethod
    def get_all_users_by_role(guild_id: str, role: str) -> List[Dict[str, Any]]:
        """Get all users with specific role in guild"""
        try:
            UserAuthDB._ensure_files()
            
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            
            return [u for u in users.values() if u.get("guild_id") == guild_id and u.get("role") == role]
        except Exception as e:
            logger.error(f"❌ Failed to get users by role: {e}")
            return []

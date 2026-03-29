"""
Watch Party Configuration
Centralized settings for the watch party feature
"""

import os
from pathlib import Path

# ── Storage Configuration ──────────────────────────────────────────────────────
UPLOAD_FOLDER = os.getenv("WATCH_PARTY_UPLOAD_DIR", "./uploads/watch_party")
MAX_UPLOAD_MB = int(os.getenv("WATCH_PARTY_MAX_MB", 10240))  # 10GB default
ALLOWED_VIDEO_EXTS = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
VIDEO_CLEANUP_HOURS = int(os.getenv("WATCH_PARTY_CLEANUP_HOURS", 24))

# Create upload folder if it doesn't exist
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# ── Playback Configuration ─────────────────────────────────────────────────────
SYNC_INTERVAL_SECONDS = 30  # Auto-sync every 30 seconds
SYNC_TOLERANCE_SECONDS = 1.5  # Tolerance before forcing sync
DEFAULT_VOLUME = 1.0
DEFAULT_LOOP = False

# ── Chat Configuration ─────────────────────────────────────────────────────────
MAX_CHAT_LENGTH = 500
MAX_CHAT_HISTORY = 200
CHAT_RATE_LIMIT = 10  # Messages per minute per user
GUEST_CHAT_ENABLED = False  # Guests cannot chat

# ── Role Permissions ───────────────────────────────────────────────────────────
ROLE_LEVELS = {
    "guest": 0,      # No role
    "member": 1,     # Any server role
    "mod": 2,        # Manage messages or manage guild
    "admin": 3,      # Administrator permission
    "owner": 4,      # Server owner
}

# Permission matrix: role_level -> [can_watch, can_chat, can_control, can_request]
ROLE_PERMISSIONS = {
    0: {"watch": True, "chat": False, "control": False, "request": False},  # Guest
    1: {"watch": True, "chat": True, "control": False, "request": False},   # Member
    2: {"watch": True, "chat": True, "control": True, "request": True},     # Mod
    3: {"watch": True, "chat": True, "control": True, "request": True},     # Admin
    4: {"watch": True, "chat": True, "control": True, "request": True},     # Owner
}

# ── Viewer Configuration ───────────────────────────────────────────────────────
MAX_CONCURRENT_VIEWERS = 500
VIEWER_TIMEOUT_SECONDS = 300  # Remove viewer if inactive for 5 minutes
SHOW_VIEWER_LIST = True

# ── Performance Configuration ──────────────────────────────────────────────────
CHUNK_SIZE = 65536  # 64KB chunks for streaming
BUFFER_SIZE = 1024 * 1024  # 1MB buffer
STREAM_TIMEOUT = 30  # Seconds

# ── Logging Configuration ──────────────────────────────────────────────────────
LOG_FILE = "./logs/watch_party.log"
LOG_LEVEL = os.getenv("WATCH_PARTY_LOG_LEVEL", "INFO")

# ── Feature Flags ──────────────────────────────────────────────────────────────
ENABLE_REACTIONS = True
ENABLE_CHAT = True
ENABLE_REQUESTS = True
ENABLE_LOOPING = True
ENABLE_EXTERNAL_URLS = True
ENABLE_FILE_UPLOAD = True

# ── Validation ─────────────────────────────────────────────────────────────────
def validate_config():
    """Validate configuration settings"""
    errors = []
    
    if MAX_UPLOAD_MB < 100:
        errors.append("MAX_UPLOAD_MB must be at least 100MB")
    
    if SYNC_INTERVAL_SECONDS < 5:
        errors.append("SYNC_INTERVAL_SECONDS must be at least 5 seconds")
    
    if MAX_CHAT_LENGTH < 50:
        errors.append("MAX_CHAT_LENGTH must be at least 50 characters")
    
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create upload folder: {e}")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(errors))
    
    return True

# Validate on import
try:
    validate_config()
except ValueError as e:
    print(f"⚠️ Watch Party Config Warning: {e}")

# ── Helper Functions ──────────────────────────────────────────────────────────
def get_role_level(has_admin: bool, has_manage_messages: bool, is_owner: bool) -> int:
    """
    Determine role level based on permissions
    
    Args:
        has_admin: User has administrator permission
        has_manage_messages: User has manage messages permission
        is_owner: User is server owner
    
    Returns:
        Role level (0-4)
    """
    if is_owner:
        return ROLE_LEVELS["owner"]
    if has_admin:
        return ROLE_LEVELS["admin"]
    if has_manage_messages:
        return ROLE_LEVELS["mod"]
    return ROLE_LEVELS["member"]

def can_perform_action(role_level: int, action: str) -> bool:
    """
    Check if a role can perform an action
    
    Args:
        role_level: User's role level (0-4)
        action: Action to check (watch, chat, control, request)
    
    Returns:
        True if allowed, False otherwise
    """
    if role_level not in ROLE_PERMISSIONS:
        return False
    return ROLE_PERMISSIONS[role_level].get(action, False)

def get_storage_info() -> dict:
    """Get storage information"""
    import shutil
    
    stat = shutil.disk_usage(UPLOAD_FOLDER)
    return {
        "total_gb": stat.total / (1024**3),
        "used_gb": stat.used / (1024**3),
        "free_gb": stat.free / (1024**3),
        "percent_used": (stat.used / stat.total) * 100,
    }

def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable format"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}PB"

# ── Export Configuration ───────────────────────────────────────────────────────
__all__ = [
    "UPLOAD_FOLDER",
    "MAX_UPLOAD_MB",
    "ALLOWED_VIDEO_EXTS",
    "VIDEO_CLEANUP_HOURS",
    "SYNC_INTERVAL_SECONDS",
    "SYNC_TOLERANCE_SECONDS",
    "MAX_CHAT_LENGTH",
    "MAX_CHAT_HISTORY",
    "CHAT_RATE_LIMIT",
    "GUEST_CHAT_ENABLED",
    "ROLE_LEVELS",
    "ROLE_PERMISSIONS",
    "get_role_level",
    "can_perform_action",
    "get_storage_info",
    "format_bytes",
]

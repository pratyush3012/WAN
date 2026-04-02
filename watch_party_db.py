"""
Watch Party Database - Persistent storage for all settings and data
Saves all configurations so they don't need to be reconfigured
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Database file location — align with DATA_DIR on Render (/data) or ./data locally
_data_root = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DB_DIR = Path(_data_root) / "watch_party"
try:
    DB_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    DB_DIR = Path("./data/watch_party")
    DB_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = DB_DIR / "settings.json"
ROOMS_FILE = DB_DIR / "rooms.json"
UPLOADS_FILE = DB_DIR / "uploads.json"


class WatchPartyDB:
    """Persistent database for watch party settings and data"""
    
    @staticmethod
    def load_settings(guild_id: str) -> Dict[str, Any]:
        """Load guild settings from database"""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r') as f:
                    all_settings = json.load(f)
                    return all_settings.get(str(guild_id), {})
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
        return {}
    
    @staticmethod
    def save_settings(guild_id: str, settings: Dict[str, Any]) -> bool:
        """Save guild settings to database"""
        try:
            all_settings = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r') as f:
                    all_settings = json.load(f)
            
            all_settings[str(guild_id)] = settings
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(all_settings, f, indent=2)
            
            logger.info(f"Saved settings for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    @staticmethod
    def get_welcome_config(guild_id: str) -> Dict[str, Any]:
        """Get welcome channel configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        return settings.get("welcome", {})
    
    @staticmethod
    def set_welcome_config(guild_id: str, config: Dict[str, Any]) -> bool:
        """Save welcome channel configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        settings["welcome"] = config
        return WatchPartyDB.save_settings(guild_id, settings)
    
    @staticmethod
    def get_role_config(guild_id: str) -> Dict[str, Any]:
        """Get role configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        return settings.get("roles", {})
    
    @staticmethod
    def set_role_config(guild_id: str, config: Dict[str, Any]) -> bool:
        """Save role configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        settings["roles"] = config
        return WatchPartyDB.save_settings(guild_id, settings)
    
    @staticmethod
    def get_watch_party_config(guild_id: str) -> Dict[str, Any]:
        """Get watch party specific configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        return settings.get("watch_party", {})
    
    @staticmethod
    def set_watch_party_config(guild_id: str, config: Dict[str, Any]) -> bool:
        """Save watch party configuration"""
        settings = WatchPartyDB.load_settings(guild_id)
        settings["watch_party"] = config
        return WatchPartyDB.save_settings(guild_id, settings)
    
    @staticmethod
    def save_upload_info(room_id: str, upload_info: Dict[str, Any]) -> bool:
        """Save upload information for tracking"""
        try:
            uploads = {}
            if UPLOADS_FILE.exists():
                with open(UPLOADS_FILE, 'r') as f:
                    uploads = json.load(f)
            
            uploads[room_id] = {
                **upload_info,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(UPLOADS_FILE, 'w') as f:
                json.dump(uploads, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving upload info: {e}")
            return False
    
    @staticmethod
    def get_upload_info(room_id: str) -> Optional[Dict[str, Any]]:
        """Get upload information"""
        try:
            if UPLOADS_FILE.exists():
                with open(UPLOADS_FILE, 'r') as f:
                    uploads = json.load(f)
                    return uploads.get(room_id)
        except Exception as e:
            logger.error(f"Error loading upload info: {e}")
        return None
    
    @staticmethod
    def save_room_data(room_id: str, room_data: Dict[str, Any]) -> bool:
        """Save room data for persistence"""
        try:
            rooms = {}
            if ROOMS_FILE.exists():
                with open(ROOMS_FILE, 'r') as f:
                    rooms = json.load(f)
            
            rooms[room_id] = {
                **room_data,
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(ROOMS_FILE, 'w') as f:
                json.dump(rooms, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving room data: {e}")
            return False
    
    @staticmethod
    def get_room_data(room_id: str) -> Optional[Dict[str, Any]]:
        """Get saved room data"""
        try:
            if ROOMS_FILE.exists():
                with open(ROOMS_FILE, 'r') as f:
                    rooms = json.load(f)
                    return rooms.get(room_id)
        except Exception as e:
            logger.error(f"Error loading room data: {e}")
        return None
    
    @staticmethod
    def get_all_rooms(guild_id: str) -> List[Dict[str, Any]]:
        """Get all rooms for a guild"""
        try:
            if ROOMS_FILE.exists():
                with open(ROOMS_FILE, 'r') as f:
                    rooms = json.load(f)
                    return [r for r in rooms.values() if r.get("guild_id") == str(guild_id)]
        except Exception as e:
            logger.error(f"Error loading rooms: {e}")
        return []
    
    @staticmethod
    def delete_room_data(room_id: str) -> bool:
        """Delete room data"""
        try:
            if ROOMS_FILE.exists():
                with open(ROOMS_FILE, 'r') as f:
                    rooms = json.load(f)
                
                if room_id in rooms:
                    del rooms[room_id]
                    
                    with open(ROOMS_FILE, 'w') as f:
                        json.dump(rooms, f, indent=2)
                    
                    return True
        except Exception as e:
            logger.error(f"Error deleting room data: {e}")
        return False
    
    @staticmethod
    def export_all_data(guild_id: str) -> Dict[str, Any]:
        """Export all data for a guild"""
        return {
            "settings": WatchPartyDB.load_settings(guild_id),
            "rooms": WatchPartyDB.get_all_rooms(guild_id),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def import_data(guild_id: str, data: Dict[str, Any]) -> bool:
        """Import data for a guild"""
        try:
            if "settings" in data:
                WatchPartyDB.save_settings(guild_id, data["settings"])
            
            if "rooms" in data:
                for room in data["rooms"]:
                    WatchPartyDB.save_room_data(room.get("room_id"), room)
            
            return True
        except Exception as e:
            logger.error(f"Error importing data: {e}")
            return False
